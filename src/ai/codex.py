"""Async, serialized Codex CLI adapter with persistent automation-only auth."""

from __future__ import annotations

import asyncio
import fcntl
import os
import shutil
import stat
import threading
import time
from pathlib import Path
from typing import Any

from src.ai._codex.auth import CodexAuthError, read_auth
from src.ai._codex.process import CliProcessError
from src.ai._codex.runner import CodexConfig, CodexRunner
from src.ai.exceptions import (
    ClaudeExecutionError,
    ClaudeNotFoundError,
    ClaudeTimeoutError,
)
from src.ai.response import AnalysisResponseParser
from src.logger import get_logger


class CodexCLI(AnalysisResponseParser):
    """Satisfies LLMClient; legacy exception names retain consumer compatibility."""

    def __init__(
        self,
        timeout: float | None = None,
        codex_path: str = "codex",
        max_retries: int | None = None,
        model: str | None = None,
        auth_home: Path | None = None,
    ) -> None:
        from src.config import get_settings

        settings = get_settings()
        self.timeout = (
            float(settings.claude_cli_timeout_seconds) if timeout is None else timeout
        )
        self.max_retries = (
            settings.claude_cli_max_retries if max_retries is None else max_retries
        )
        self.model = settings.codex_cli_model if model is None else model
        self.auth_home = settings.codex_auth_home if auth_home is None else auth_home
        self.codex_path = codex_path
        self._logger = get_logger("crypto_master.ai.codex")
        if self.timeout <= 0 or not 0 <= self.max_retries <= 5 or not self.model:
            raise ValueError("invalid_codex_configuration")

    def is_available(self) -> bool:
        return shutil.which(self.codex_path) is not None

    async def analyze(self, prompt: str) -> dict[str, Any]:
        return self._parse_response(await self.complete(prompt))

    async def complete(self, prompt: str) -> str:
        if len(prompt.encode("utf-8")) > 1024 * 1024:
            raise ClaudeExecutionError("codex_prompt_limit")
        cancelled = threading.Event()
        task = asyncio.create_task(
            asyncio.to_thread(self._complete_blocking, prompt, cancelled)
        )
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled.set()
            # Do not release the auth stream while a native child can refresh it.
            # Repeated cancellation cannot abandon the worker during cleanup.
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    continue
                except Exception:
                    break
            if task.done() and not task.cancelled():
                task.exception()
            raise

    def _complete_blocking(self, prompt: str, cancelled: threading.Event) -> str:
        binary = shutil.which(self.codex_path)
        if binary is None:
            raise ClaudeNotFoundError("Codex CLI is not installed")
        started = time.monotonic()
        runner: CodexRunner | None = None
        lock_fd: int | None = None
        try:
            home = self.auth_home
            info = home.lstat()
            if (
                not home.is_absolute()
                or home.resolve() != home
                or not stat.S_ISDIR(info.st_mode)
                or stat.S_IMODE(info.st_mode) != 0o700
                or info.st_uid != os.getuid()
            ):
                raise CodexAuthError()
            lock_fd = os.open(
                home / ".runtime.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
            )
            lock_info = os.fstat(lock_fd)
            if (
                not stat.S_ISREG(lock_info.st_mode)
                or stat.S_IMODE(lock_info.st_mode) != 0o600
                or lock_info.st_uid != os.getuid()
            ):
                raise CodexAuthError()
            admission_deadline = started + self.timeout
            while True:
                if cancelled.is_set() or time.monotonic() >= admission_deadline:
                    raise ClaudeTimeoutError("Codex admission timeout", self.timeout)
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    cancelled.wait(0.05)
            if (home / ".runtime-quarantined").exists():
                raise ClaudeExecutionError("codex_runtime_quarantined")
            read_auth(home / "auth.json")
            budget = sum(self.timeout * 1.5**i for i in range(self.max_retries + 1))
            runner = CodexRunner(
                CodexConfig(self.model),
                home,
                deadline=started + budget,
                binary=binary,
                cancelled=cancelled,
            )
            for attempt in range(1, self.max_retries + 2):
                timeout = self.timeout * 1.5 ** (attempt - 1)
                result = runner(
                    [], capture_output=True, text=True, timeout=timeout, input=prompt
                )
                if result.returncode == 0:
                    answer = result.stdout.strip()
                    if not answer:
                        raise ClaudeExecutionError("codex_empty_response")
                    self._logger.info(
                        "codex_complete model=%s attempt=%d", self.model, attempt
                    )
                    return answer
                if result.returncode == 124:
                    if attempt <= self.max_retries and not cancelled.is_set():
                        continue
                    raise ClaudeTimeoutError("Codex CLI timeout", timeout, attempt)
                raise ClaudeExecutionError(
                    "codex_execution_failed", exit_code=result.returncode
                )
            raise ClaudeExecutionError("codex_execution_failed")
        except (CodexAuthError, OSError):
            raise ClaudeExecutionError("codex_auth_or_runtime_unavailable") from None
        finally:
            try:
                if runner is not None:
                    try:
                        runner.close()
                    except CliProcessError:
                        # A child that could still refresh must block subsequent
                        # callers, including the other process on this volume.
                        try:
                            marker = os.open(
                                self.auth_home / ".runtime-quarantined",
                                os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW,
                                0o600,
                            )
                            os.close(marker)
                        except OSError:
                            # If even the marker cannot be persisted, retain
                            # this open lock until process exit/restart. Never
                            # admit another caller beside an unreaped child.
                            lock_fd = None
                        raise ClaudeExecutionError("codex_cleanup_failed") from None
            finally:
                if lock_fd is not None:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
                    os.close(lock_fd)
