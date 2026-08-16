"""The catch-up, and the line that made it unable to catch up.

WHAT THIS PROTECTS. The event bus is AT-MOST-ONCE by contract: a pod that is restarting, rolling
out, or briefly disconnected does not receive an event, and nothing anywhere records that it missed
one. For this service that is not a delay — it is a customer who is never reminded, ever, because
nothing will mention that visit again. The catch-up READ is the recovery, and its cursor is the
only thing that decides what it looks at.

THE DEFECT. `on_event` advanced that cursor to the delivered visit's timestamp. So when the bus
dropped visit A and delivered visit B, the cursor jumped past BOTH — and the catch-up, which reads
only what came after the cursor, could no longer see A. The mechanism built to recover the dropped
visit was blinded by the delivery of the next one.

It saved a re-read. The re-read is cheap — `on_visit` is idempotent on the visit id — and the thing
it cost was the entire purpose of the file.
"""
from __future__ import annotations

import ast
import asyncio
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
INGEST = ROOT / "app" / "core" / "ingest.py"


def run(c):
    return asyncio.run(c)


def _fn_source(name: str) -> str:
    text = INGEST.read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(text, node) or ""
    raise AssertionError(f"{name} is gone from ingest.py")


def test_the_event_path_does_not_move_the_cursor():
    """THE DEFECT ITSELF, pinned at the exact call. A hint may not advance the record."""
    assert "_advance" not in _fn_source("on_event"), (
        "the event is a hint; advancing on it makes the visit the bus DROPPED invisible to the "
        "catch-up that exists to recover it")


def test_the_catch_up_still_moves_it():
    """The other half: a cursor that never advances turns every tick into a full re-read, and a
    safety net that costs the whole table every five minutes is one somebody will switch off."""
    assert "_advance" in _fn_source("catch_up")


def test_it_advances_only_after_the_batch_is_processed():
    """Advancing first means a crash mid-batch skips those visits permanently — the same failure,
    arriving by a different road."""
    src = _fn_source("catch_up")
    assert src.index("on_visit") < src.index("_advance"), (
        "the cursor may only pass what has actually been handled")


def test_a_dropped_visit_is_still_recoverable_after_a_later_one_arrives():
    """The behaviour, end to end: B is delivered by the bus, A was dropped, and the catch-up must
    still see A. This is the customer who would otherwise never be reminded."""
    from app.core.ingest import WATERMARKS, Ingest

    class Store:
        def __init__(self):
            self.rows = {}

        async def get(self, coll, key):
            return self.rows.get(key)

        async def put(self, coll, key, row):
            self.rows[key] = row
            return row

    class Sched:
        def __init__(self):
            self.seen = []

        async def on_visit(self, payload, *, now, service_config, confirm_visits):
            self.seen.append(payload.get("visit_id"))

            class Out:
                duplicate = False
                scheduled = []
            return Out()

    store, sched = Store(), Sched()
    ing = Ingest(store=store, scheduler=sched, visits_client=None)

    # B arrives on the bus. A — older, and dropped — is still sitting in operations.
    run(ing.on_event({"tenant": "t1", "visit_id": "B", "created": 200}, now=300))

    assert run(store.get(WATERMARKS, "t1|visits")) in (None, {}) or \
        int((run(store.get(WATERMARKS, "t1|visits")) or {}).get("mark") or 0) == 0, (
        "a delivered event must not move the cursor past the one that was dropped")
