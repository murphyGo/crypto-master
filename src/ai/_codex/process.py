"""Bounded pipe capture and process-group cleanup for private CLI providers."""

from __future__ import annotations

import os
import selectors
import signal
import subprocess
import threading
import time
from contextlib import suppress

MAX_OUTPUT_BYTES = 4 * 1024 * 1024


class CliProcessError(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)


def stop_process(process: subprocess.Popen[bytes]) -> None:
    """Stop the process group even when the CLI launcher has already exited."""
    for sig, wait in ((signal.SIGTERM, 0.5), (signal.SIGKILL, 5.0)):
        with suppress(ProcessLookupError):
            os.killpg(process.pid, sig)
        try:
            process.wait(timeout=wait)
        except subprocess.TimeoutExpired:
            continue
    if process.poll() is None:
        raise CliProcessError("cli_cleanup_failed")


def capture(
    process: subprocess.Popen[bytes],
    prompt: bytes,
    deadline: float,
    cancelled: threading.Event,
) -> bytes:
    """Drain both pipes and write stdin concurrently, without unbounded communicate()."""
    assert (
        process.stdin is not None
        and process.stdout is not None
        and process.stderr is not None
    )
    output = bytearray()
    stderr_bytes = 0
    offset = 0
    with selectors.DefaultSelector() as selector:
        for stream, event in (
            (process.stdin, selectors.EVENT_WRITE),
            (process.stdout, selectors.EVENT_READ),
            (process.stderr, selectors.EVENT_READ),
        ):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, event)
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if cancelled.is_set() or remaining <= 0:
                raise CliProcessError("cli_timeout")
            for key, _ in selector.select(min(remaining, 0.1)):
                ready = key.fileobj
                if ready is process.stdin:
                    try:
                        offset += os.write(key.fd, prompt[offset : offset + 65536])
                    except BrokenPipeError:
                        offset = len(prompt)
                    if offset == len(prompt):
                        selector.unregister(ready)
                        process.stdin.close()
                else:
                    chunk = os.read(key.fd, 65536)
                    if not chunk:
                        selector.unregister(ready)
                    elif ready is process.stdout:
                        output.extend(chunk)
                    else:
                        stderr_bytes += len(chunk)
                    if (
                        len(output) > MAX_OUTPUT_BYTES
                        or stderr_bytes > MAX_OUTPUT_BYTES
                    ):
                        raise CliProcessError("cli_output_limit")
    while process.poll() is None:
        remaining = deadline - time.monotonic()
        if cancelled.is_set() or remaining <= 0:
            raise CliProcessError("cli_timeout")
        try:
            process.wait(timeout=min(0.1, remaining))
        except subprocess.TimeoutExpired:
            continue
    return bytes(output)
