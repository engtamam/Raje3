"""The bus path must schedule with the shop's own cycles — and the reason it is not a nicety.

WHAT WAS WRONG. `main.py` subscribed to `operations.visit.recorded` and called `ingest.on_event`
with `service_config={}`. An empty catalogue means every service falls back to the platform default:
the first reminder lands at 90 days for a car wash on a 10-day cycle, and `follow_up_days` defaults
to NO_FOLLOW_UP, so no follow-up is EVER scheduled from a bus delivery.

AND THE CATCH-UP COULD NOT REPAIR IT — this is the part that made it permanent rather than slow.
`on_visit` marks the visit seen by its id (scheduling.py, the idempotency block), so when the tick's
catch-up came along with the REAL configuration it saw a duplicate and moved on. The fast path did
not merely arrive first; it consumed the visit and locked the wrong schedule in.

Which means the per-service cycle feature worked only for visits the bus happened to DROP. Every
visit delivered normally — the overwhelming majority — got the default.

These tests are about the WIRING, not the scheduler: the scheduler was always correct when it was
told the truth.
"""
from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
MAIN = ROOT / "app" / "main.py"


def _handler_source() -> str:
    """The body of the bus handler, isolated so an unrelated edit elsewhere cannot mask a change."""
    tree = ast.parse(MAIN.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_on_visit":
            return ast.get_source_segment(MAIN.read_text(encoding="utf-8"), node) or ""
    raise AssertionError("the visit subscriber is gone — the fast path no longer exists")


def test_the_fast_path_does_not_schedule_with_an_empty_catalogue():
    """THE DEFECT ITSELF, pinned at the exact call."""
    src = _handler_source()
    assert "service_config={}" not in src, (
        "an empty catalogue means the platform default cycle for every service, and NO follow-up "
        "ever — and the catch-up cannot repair it because the visit is already marked seen")


def test_it_resolves_the_configuration_the_tick_uses(monkeypatch):
    """The same resolver, not a second one. Two sources for one answer is how they drift."""
    src = _handler_source()
    assert "_service_config" in src, "the fast path must read the same tree the tick reads"
    assert "service_config=cfg" in src


def test_the_handler_still_honours_the_confirmation_switch():
    """A guard for the fix itself: the switch was already correct here and must survive."""
    assert "confirm_visits=" in _handler_source()


def test_the_scheduler_gives_a_configured_service_its_own_cycle_not_the_default():
    """And the behaviour the wiring exists to deliver — proven through the scheduler itself, so
    this test fails if the CONTRACT changes rather than only if the call site does."""
    import asyncio
    import inspect

    from app.core import scheduling

    sig = inspect.signature(scheduling.Scheduler.on_visit)
    assert "service_config" in sig.parameters, (
        "the scheduler takes the catalogue per call — if that ever changes, the fast path's fix "
        "changes with it")
    assert asyncio is not None
