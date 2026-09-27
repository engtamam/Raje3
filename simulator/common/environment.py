"""Stage 4 of the simulator's own build plan (see ../README.md): a real environment. Two separate
concerns, both first-class here rather than an afterthought (see the README's own "Environment"
section, and the research behind it — Gremlin's "blast radius", Chaos Toolkit's rollback-vs-
teardown split):

  1. `run_service` — spins up a REAL process (a real `uvicorn` server, a real socket, a real event
     loop of its own) and guarantees it is torn down afterward, success or failure. This is what
     lets later stages hit an action through the SAME interface a real till/console would, not an
     in-process shortcut.
  2. `BlastRadius` / `RollbackOnFailure` — safety primitives. `BlastRadius` is a scenario's own
     declared promise about which tenant it is allowed to touch, checked at the one place a
     scenario's actions actually name a tenant, so an adversarial/security scenario can never
     drift into real data by a copy-paste mistake. `RollbackOnFailure` is a DIFFERENT thing from
     teardown: teardown always runs (stop the process); rollback only runs when something inside
     actually failed, and undoes whatever that run created BEFORE the ordinary teardown happens.
"""
from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import sys
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


class BlastRadiusViolation(Exception):
    """Raised the moment a scenario's own action tries to touch a tenant it never declared. Fails
    the action, never silently narrows or redirects it — a scenario that gets this wrong needs to
    see it fail loudly, the same "refuse, don't guess" posture the rest of this platform takes."""


@dataclass
class BlastRadius:
    """The one tenant a scenario is allowed to touch. Deliberately a single exact tenant, not a
    prefix or pattern — the whole point is that an adversarial/security scenario (stage 7) cannot
    accidentally widen its own scope by a fuzzy match; a scenario that genuinely needs more than
    one tenant declares more than one `BlastRadius` and checks the right one at the right action."""

    tenant: str

    def check(self, target_tenant: str) -> None:
        if target_tenant != self.tenant:
            raise BlastRadiusViolation(
                f"action tried to touch tenant {target_tenant!r}, "
                f"outside this scenario's declared blast radius ({self.tenant!r})")


@dataclass
class RollbackOnFailure:
    """`async with RollbackOnFailure(cleanup):` — `cleanup` runs ONLY if the `with` block raises,
    and runs BEFORE the exception propagates further (so a caller wrapping this in its own
    teardown sees a system already cleaned up, not a race between the two). Never touched on the
    success path — an ordinary teardown handles that separately, and running a "failure cleanup"
    on every success too would blur the two concepts this class exists to keep distinct."""

    cleanup: Callable[[], Awaitable[None]]

    async def __aenter__(self) -> "RollbackOnFailure":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        if exc_type is not None:
            await self.cleanup()
        return False  # never swallow the original exception


@dataclass
class ServiceHandle:
    """A real, running service. `base_url` is what an Action talks to over real HTTP — the same
    interface a real till/console would use, per this simulator's own whole reason for existing."""

    name: str
    base_url: str
    process: subprocess.Popen


def _free_port() -> int:
    """Ask the OS for a port nobody is listening on right now — avoids two scenarios (or two runs
    of the same one) colliding on a hardcoded port number."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def _wait_healthy(base_url: str, *, health_path: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    async with httpx.AsyncClient() as client:
        while time.monotonic() < deadline:
            try:
                r = await client.get(base_url + health_path, timeout=1.0)
                if r.status_code == 200:
                    return
            except httpx.HTTPError as exc:                                    # noqa: BLE001
                last_error = exc
            await asyncio.sleep(0.1)
    raise TimeoutError(
        f"{base_url} never answered {health_path} with 200 within {timeout}s "
        f"(last error: {last_error})")


@asynccontextmanager
async def run_service(name: str, *, app_import: str, cwd: Path, port: int | None = None,
                      env: dict[str, str] | None = None, health_path: str = "/healthz",
                      startup_timeout: float = 15.0) -> AsyncIterator[ServiceHandle]:
    """Spawn `app_import` (e.g. `"app.main:app"`) as a REAL `uvicorn` subprocess with `cwd` as its
    working directory (so its own relative imports/config resolve exactly as they would running
    for real), wait for it to answer `health_path` with 200, yield a `ServiceHandle`, and ALWAYS
    terminate the process on the way out — success, failure, or an exception raised inside the
    `with` block all take the same teardown path, via `finally`.
    """
    port = port if port is not None else _free_port()
    base_url = f"http://127.0.0.1:{port}"
    full_env = {**os.environ, **(env or {})}

    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", app_import, "--host", "127.0.0.1", "--port", str(port),
         "--log-level", "warning"],
        cwd=str(cwd), env=full_env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    try:
        try:
            await _wait_healthy(base_url, health_path=health_path, timeout=startup_timeout)
        except TimeoutError as exc:
            # THE PROCESS NEVER GOT HEALTHY — attach its own output to the failure, because
            # "connection refused" alone tells a caller nothing about WHY it never came up (a
            # missing env var, a config validation error, a port already in use). Terminate it
            # here (not just in the outer `finally`) so reading stdout after `kill()` sees
            # everything it ever printed, not a stream still open on a half-dead process.
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5.0)
            output = process.stdout.read().decode(errors="replace") if process.stdout else ""
            raise TimeoutError(f"{exc}\n--- {name}'s own stdout/stderr ---\n{output}") from exc
        yield ServiceHandle(name=name, base_url=base_url, process=process)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5.0)
