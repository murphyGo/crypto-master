"""Exercise the real CLI boundary with a deterministic native-process stand-in."""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from src.ai._codex.auth import read_auth, write_auth
from src.ai._codex.process import CliProcessError
from src.ai.codex import CodexCLI
from src.ai.exceptions import ClaudeExecutionError, ClaudeTimeoutError
from src.ai.factory import create_llm_client
from src.ai.ports import LLMClient


@pytest.fixture
def native(tmp_path):
    home = tmp_path.resolve() / "auth"
    home.mkdir(mode=0o700)
    write_auth(
        home / "auth.json",
        json.dumps(
            {
                "auth_mode": "chatgpt",
                "tokens": {
                    "id_token": "fixture-id",
                    "access_token": "fixture-access",
                    "refresh_token": "fixture-refresh",
                    "account_id": "fixture-account",
                },
            }
        ).encode(),
    )
    binary = tmp_path / "codex"
    binary.write_text(f"#!{sys.executable}\n" + r"""
import json, os, subprocess, sys, time
from pathlib import Path
if sys.argv[1:] == ["--version"]:
    print("codex-cli 0.153.4")
    raise SystemExit(0)
home = Path(os.environ["CODEX_HOME"])
prompt = sys.stdin.read()
assert prompt not in sys.argv
assert "EXCHANGE_API_KEY" not in os.environ
assert "OPENAI_API_KEY" not in os.environ
assert "ANTHROPIC_API_KEY" not in os.environ
assert "--ephemeral" in sys.argv
assert "--sandbox" in sys.argv and "read-only" in sys.argv
assert "-" == sys.argv[-1]
(home / "entered").write_text("yes")
if prompt in ("sleep", "retry"):
    attempt = home / "attempt"
    count = int(attempt.read_text()) if attempt.exists() else 0
    attempt.write_text(str(count + 1))
    if prompt == "sleep" or count == 0:
        subprocess.Popen([sys.executable, "-c", "import time; from pathlib import Path; p=Path(" + repr(str(home / "heartbeat")) + "); "
                          "exec('while True:\\n p.write_text(str(time.monotonic()))\\n time.sleep(0.03)'.replace('\\\\n','\\n'))"])
        time.sleep(30)
if prompt == "serialize":
    active = home / "active"
    fd = os.open(active, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    time.sleep(0.2)
    auth = home / "auth.json"
    payload = json.loads(auth.read_text())
    payload["tokens"]["refresh_token"] += "-rotated"
    auth.write_text(json.dumps(payload))
    active.unlink()
answer = '{"signal":"neutral","confidence":0.5,"reasoning":"fixture"}'
if prompt == "secret":
    answer = "fixture-access"
elif prompt == "empty":
    answer = "  \n"
elif prompt == "text":
    answer = "# strategy\nA bounded candidate."
Path(sys.argv[sys.argv.index("--output-last-message") + 1]).write_text(answer)
item_type = "command_execution" if prompt == "tool" else "agent_message"
print(json.dumps({"type":"item.completed", "item":{"type":item_type,"text":answer}}))
print(json.dumps({"type":"turn.completed"}))
""")
    binary.chmod(0o700)
    return home, binary


def client(native, **kwargs):
    home, binary = native
    return CodexCLI(
        auth_home=home,
        codex_path=str(binary),
        timeout=kwargs.pop("timeout", 5),
        max_retries=kwargs.pop("max_retries", 0),
        **kwargs,
    )


async def wait_for(path):
    for _ in range(200):
        if path.exists():
            return
        await asyncio.sleep(0.01)
    pytest.fail(f"fixture did not create {path.name}")


async def test_text_json_and_parent_credentials_are_isolated(native, monkeypatch):
    for name in ("EXCHANGE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.setenv(name, "parent-secret")
    adapter = client(native)
    assert isinstance(adapter, LLMClient)
    assert await adapter.complete("text") == "# strategy\nA bounded candidate."
    assert (await adapter.analyze("json"))["signal"] == "neutral"


@pytest.mark.parametrize("prompt", ["tool", "secret", "empty"])
async def test_rejects_unexpected_tools_secrets_and_empty_answer(native, prompt):
    with pytest.raises(ClaudeExecutionError) as error:
        await client(native).complete(prompt)
    assert "fixture-access" not in str(error.value)
    assert error.value.stderr is None


@pytest.mark.parametrize("bad_mode", [0o644, 0o666])
async def test_auth_permissions_fail_before_native_execution(native, bad_mode):
    home, _ = native
    (home / "auth.json").chmod(bad_mode)
    with pytest.raises(ClaudeExecutionError):
        await client(native).complete("text")
    assert not (home / "entered").exists()


async def test_timeout_reaps_child_and_grandchild(native):
    home, _ = native
    task = asyncio.create_task(client(native, timeout=0.8).complete("sleep"))
    await wait_for(home / "heartbeat")
    with pytest.raises(ClaudeTimeoutError):
        await task
    heartbeat = (home / "heartbeat").read_text()
    await asyncio.sleep(0.15)
    assert (home / "heartbeat").read_text() == heartbeat
    assert await client(native).complete("text")


async def test_cancellation_waits_for_cleanup_before_next_call(native):
    home, _ = native
    task = asyncio.create_task(client(native).complete("sleep"))
    await wait_for(home / "heartbeat")
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    heartbeat = (home / "heartbeat").read_text()
    await asyncio.sleep(0.15)
    assert (home / "heartbeat").read_text() == heartbeat
    assert await client(native).complete("text")


async def test_timeout_retries_once_and_preserves_contract(native):
    home, _ = native
    assert await client(native, timeout=0.5, max_retries=1).complete("retry")
    assert (home / "attempt").read_text() == "2"


def test_cross_process_serialization_preserves_each_auth_rotation(native):
    home, binary = native
    script = (
        "import asyncio, sys; from pathlib import Path; from src.ai.codex import CodexCLI; "
        "asyncio.run(CodexCLI(auth_home=Path(sys.argv[1]), codex_path=sys.argv[2], "
        "timeout=5, max_retries=0).complete('serialize'))"
    )
    workers = [
        subprocess.Popen(
            [sys.executable, "-c", script, str(home), str(binary)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for _ in range(2)
    ]
    for worker in workers:
        _, stderr = worker.communicate(timeout=15)
        assert worker.returncode == 0, stderr.decode()
    payload = json.loads(read_auth(home / "auth.json").raw)
    assert payload["tokens"]["refresh_token"].endswith("-rotated-rotated")
    assert not (home / "active").exists()


async def test_admission_timeout_does_not_interrupt_lock_owner(native):
    home, _ = native
    owner = asyncio.create_task(client(native).complete("serialize"))
    await wait_for(home / "active")
    with pytest.raises(ClaudeTimeoutError, match="admission"):
        await client(native, timeout=0.05).complete("text")
    assert await owner
    assert (home / "auth.json").exists()


async def test_cleanup_failure_quarantines_auth_stream(native):
    home, _ = native
    with patch(
        "src.ai.codex.CodexRunner.close", side_effect=CliProcessError("cleanup")
    ):
        with pytest.raises(ClaudeExecutionError, match="cleanup_failed"):
            await client(native).complete("text")
    assert (home / ".runtime-quarantined").exists()
    with pytest.raises(ClaudeExecutionError, match="quarantined"):
        await client(native).complete("text")


async def test_quarantine_write_failure_retains_lock_until_process_restart(native):
    home, _ = native
    original_open = os.open
    held_fds = []

    def open_with_failed_marker(path, flags, *args, **kwargs):
        if Path(path) == home / ".runtime-quarantined":
            raise OSError("fixture failure that must not escape")
        fd = original_open(path, flags, *args, **kwargs)
        if Path(path) == home / ".runtime.lock":
            held_fds.append(fd)
        return fd

    try:
        with patch("src.ai.codex.os.open", side_effect=open_with_failed_marker):
            with patch(
                "src.ai.codex.CodexRunner.close", side_effect=CliProcessError("cleanup")
            ):
                with pytest.raises(
                    ClaudeExecutionError, match="^codex_cleanup_failed$"
                ):
                    await client(native).complete("text")
        with pytest.raises(ClaudeTimeoutError, match="admission"):
            await client(native, timeout=0.05).complete("text")
    finally:
        for fd in held_fds:
            os.close(fd)


def test_factory_explicit_provider_and_timeout(monkeypatch):
    from src import config
    from src.ai.claude import ClaudeCLI

    try:
        monkeypatch.setenv("LLM_PROVIDER", "codex")
        monkeypatch.setattr(config, "_settings", None)
        adapter = create_llm_client(timeout=123)
        assert isinstance(adapter, CodexCLI)
        assert adapter.timeout == 123
        monkeypatch.setenv("LLM_PROVIDER", "claude")
        monkeypatch.setattr(config, "_settings", None)
        assert isinstance(create_llm_client(), ClaudeCLI)
    finally:
        monkeypatch.setattr(config, "_settings", None)
