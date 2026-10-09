"""Bounded, serialized Codex CLI runner compatible with the Claude test seam."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from src.ai._codex.auth import CodexAuthError, read_auth
from src.ai._codex.policy import CODEX_VERSION, codex_arguments, model_catalog
from src.ai._codex.process import (
    MAX_OUTPUT_BYTES,
)
from src.ai._codex.process import (
    CliProcessError as CodexExecutionError,
)
from src.ai._codex.process import (
    capture as _capture,
)
from src.ai._codex.process import (
    stop_process as _stop_process,
)

_logger = logging.getLogger(__name__)


def _record_timing(started: float, acquired: float | None) -> None:
    finished = time.monotonic()
    admitted = acquired if acquired is not None else finished
    _logger.info(
        "codex_call %s",
        json.dumps(
            {
                "lock_wait_s": round(max(0, admitted - started), 3),
                "execution_s": round(max(0, finished - admitted), 3),
            }
        ),
    )


def _check_events(raw: bytes) -> None:
    """Reject unexpected actions; prevention is the pinned tool-free configuration."""
    completed = False
    try:
        for line in raw.splitlines():
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError
            kind = event.get("type")
            if kind in ("item.started", "item.updated", "item.completed"):
                item = event.get("item")
                if not isinstance(item, dict) or item.get("type") not in (
                    "agent_message",
                    "reasoning",
                ):
                    raise ValueError
            elif kind not in ("thread.started", "turn.started", "turn.completed"):
                raise ValueError
            if kind == "turn.completed":
                completed = True
        if not completed:
            raise ValueError
    except (ValueError, UnicodeError):
        raise CodexExecutionError("codex_unexpected_event") from None


@dataclass(frozen=True)
class CodexConfig:
    model: str
    provider: str = "codex"


class CodexRunner:
    """One dedicated auth stream. close() prevents new calls and waits for quiescence."""

    def __init__(
        self,
        config: CodexConfig,
        auth_home: Path,
        *,
        deadline: float,
        binary: str = "codex",
        cancelled: threading.Event | None = None,
    ) -> None:
        if config.provider != "codex" or config.model is None:
            raise ValueError("codex_config_required")
        self.config = config
        self.auth_home = auth_home
        self.deadline = deadline
        self.binary = binary
        self._lock = threading.Lock()
        self._cancelled = cancelled if cancelled is not None else threading.Event()
        self._closed = False
        self._cleanup_failed = False
        self._active: subprocess.Popen[bytes] | None = None
        self._secrets = set(read_auth(auth_home / "auth.json").secrets)

    def close(self) -> None:
        self._cancelled.set()
        # The capture loop checks cancellation every 100ms, then reaps the group.
        if not self._lock.acquire(timeout=11):
            self._cleanup_failed = True
            raise CodexExecutionError("codex_cleanup_failed")
        try:
            self._closed = True
            if self._cleanup_failed or self._active is not None:
                raise CodexExecutionError("codex_cleanup_failed")
        finally:
            self._lock.release()

    def __call__(
        self,
        args: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: float,
        input: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        del capture_output, text
        started = time.monotonic()
        end = min(self.deadline, started + timeout)
        if (
            self._cleanup_failed
            or self._cancelled.is_set()
            or not self._lock.acquire(timeout=max(0.0, end - time.monotonic()))
        ):
            _record_timing(started, None)
            return subprocess.CompletedProcess(args, 124, "", "codex_timeout")
        acquired = time.monotonic()
        try:
            if (
                self._cleanup_failed
                or self._closed
                or self._cancelled.is_set()
                or end <= time.monotonic()
            ):
                return subprocess.CompletedProcess(args, 124, "", "codex_timeout")
            return self._run(input or "", end)
        except CodexExecutionError as exc:
            if str(exc) == "cli_timeout":
                return subprocess.CompletedProcess(
                    ["codex", "exec"], 124, "", "codex_timeout"
                )
            return subprocess.CompletedProcess(
                ["codex", "exec"], 1, "", "codex_execution_failed"
            )
        except (
            CodexAuthError,
            OSError,
            ValueError,
            subprocess.SubprocessError,
        ):
            # Never propagate exception text (including argv, stdout or auth paths).
            return subprocess.CompletedProcess(
                ["codex", "exec"], 1, "", "codex_execution_failed"
            )
        finally:
            self._lock.release()
            _record_timing(started, acquired)

    def _run(self, prompt: str, deadline: float) -> subprocess.CompletedProcess[str]:
        self._secrets.update(read_auth(self.auth_home / "auth.json").secrets)
        with tempfile.TemporaryDirectory(prefix="crypto-codex-call-") as temporary:
            root = Path(temporary)
            work = root / "work"
            home = root / "home"
            work.mkdir(mode=0o700)
            home.mkdir(mode=0o700)
            catalog = root / "models.json"
            catalog.write_text(
                json.dumps(model_catalog(self.config.model or "")), encoding="utf-8"
            )
            output_path = root / "answer.txt"
            argv = codex_arguments(self.config.model or "", catalog=catalog, work=work)
            argv[0] = self.binary
            argv[-1:-1] = ["--output-last-message", str(output_path)]
            # Construct, do not filter an inherited dict: new credential variables
            # added to the parent later must not enter this child.
            env = {
                "PATH": os.defpath,
                "HOME": str(home),
                "CODEX_HOME": str(self.auth_home),
                "TMPDIR": str(root),
                "LANG": "C.UTF-8",
            }
            version = subprocess.run(
                [self.binary, "--version"],
                capture_output=True,
                text=True,
                timeout=min(5.0, max(0.001, deadline - time.monotonic())),
                env=env,
                cwd=work,
                check=False,
            )
            if (
                version.returncode
                or version.stdout.strip() != f"codex-cli {CODEX_VERSION}"
            ):
                raise CodexExecutionError("codex_version_mismatch")
            process = subprocess.Popen(
                argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=work,
                env=env,
                start_new_session=True,
            )
            self._active = process
            try:
                events = _capture(
                    process, prompt.encode("utf-8"), deadline, self._cancelled
                )
            finally:
                try:
                    _stop_process(process)
                except Exception as exc:
                    _logger.error("codex_cleanup_failed cause=%s", type(exc).__name__)
                    self._cleanup_failed = True
                    self._cancelled.set()
                    raise CodexExecutionError("codex_cleanup_failed") from None
                else:
                    self._active = None
                finally:
                    for stream in (process.stdin, process.stdout, process.stderr):
                        if stream is not None:
                            stream.close()
            if process.returncode != 0:
                raise CodexExecutionError("codex_nonzero")
            _check_events(events)
            self._secrets.update(read_auth(self.auth_home / "auth.json").secrets)
            fd = os.open(output_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, "rb") as stream:
                result = stream.read(MAX_OUTPUT_BYTES + 1)
            if not result or len(result) > MAX_OUTPUT_BYTES:
                raise CodexExecutionError("codex_output_limit")
            answer = result.decode("utf-8")
            if any(secret in answer for secret in self._secrets):
                raise CodexExecutionError("codex_secret_output")
            return subprocess.CompletedProcess(["codex", "exec"], 0, answer, "")
