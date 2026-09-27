"""The one contract everything else in this simulator composes on top of.

An Action is the smallest unit of work: one real business step ("record a visit", "mint a
referral code"). It knows NOTHING about how it will be run (solo, concurrently, under load, with a
fault injected, under a security check) — that separation is the whole point (see the README's own
taxonomy): Gatling/Locust both prove that baking "how many, how fast" into the action itself is the
wrong design, and this project's own referral-system usage-cap bug was invisible specifically
because a test's "how it ran" (a bare in-process call) hid what "how it runs for real" (concurrent
HTTP callers) would have shown.

Context is the one thing shared across a run — every action reads from it and may write results
into it for a LATER action in the same scenario to read (stage 2's own job; stage 1 never chains
actions, but the shape needs to exist from day one so stage 2 does not have to change it).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class Context:
    """Shared, mutable state for one run. `data` is a free-form bag — an action reads whatever a
    previous action put there and may add its own; nothing here validates the shape, because the
    engine has no domain knowledge (see the README's own "engine owns no domain knowledge" rule)."""

    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionResult:
    """What running one action produced. `ok=False` with no `error` means the action itself
    decided it failed (an assertion inside it did not hold); `ok=False` with `error` set means the
    action raised and the engine caught it — the engine never lets one action's crash take down
    the whole run, the same "refuse, don't guess" posture the rest of this platform's own backend
    code already takes for a failing peer."""

    ok: bool
    detail: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    error: BaseException | None = None

    def __repr__(self) -> str:
        status = "OK" if self.ok else "FAIL"
        detail = f" — {self.detail}" if self.detail else ""
        if self.error is not None:
            detail += f" ({type(self.error).__name__}: {self.error})"
        return f"<ActionResult {status}{detail}>"


class Action(Protocol):
    """Anything with a `name` and an async `run` is an Action — no base class required, so an
    action can be as small as a bare async function wrapped in `FunctionAction` below, or a real
    class with its own setup for a specific app's own real interface later."""

    name: str

    async def run(self, ctx: Context) -> ActionResult: ...


@dataclass
class FunctionAction:
    """The simplest possible Action: wrap a plain async function. Used for the engine's own tests
    and for trivial scenarios; real per-app actions (stage 5 onward) will usually be their own
    small classes instead, once they need setup (an HTTP client, a base URL) beyond one function."""

    name: str
    fn: Any  # Callable[[Context], Awaitable[ActionResult]] — typed loosely to avoid importing
    #  Callable/Awaitable machinery for what is, right now, one line of use.

    async def run(self, ctx: Context) -> ActionResult:
        return await self.fn(ctx)
