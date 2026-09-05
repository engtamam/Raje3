"""The rating reply's own bus subscription in main.py — pinned the same way
test_bus_fast_path_config.py pins the visit/booking subscriptions: read the wiring itself, so this
fails if the call site drifts rather than only if behaviour happens to still work."""
from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
MAIN = ROOT / "app" / "main.py"


def _handler_source() -> str:
    tree = ast.parse(MAIN.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_on_whatsapp_message":
            return ast.get_source_segment(MAIN.read_text(encoding="utf-8"), node) or ""
    raise AssertionError("the rating reply's bus subscriber is gone")


def test_the_handler_calls_the_rating_consumer():
    src = _handler_source()
    assert "container.rating_consumer.handle" in src


def test_it_subscribes_to_whatsapp_message_not_a_narrower_or_different_topic():
    text = MAIN.read_text(encoding="utf-8")
    assert '"whatsapp.message"' in text


def test_the_handler_does_not_assume_the_payload_carries_a_message():
    """`message` can be absent (a status/receipt change published under the same topic shape
    elsewhere) — the handler must not KeyError on it."""
    src = _handler_source()
    assert "or {}" in src or ".get(" in src
