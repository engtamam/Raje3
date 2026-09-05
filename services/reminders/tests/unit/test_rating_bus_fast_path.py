"""Both paths into the scheduler must resolve rating eligibility THE SAME WAY — same bug class
test_bus_fast_path_config.py already pins for confirm_visits/service_config: a fast path that
resolves differently from the tick's catch-up means a shop with the rating app on sees the plain
confirmation whenever the bus happens to deliver instead of dropping the event.
"""
from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
MAIN = ROOT / "app" / "main.py"
INTERNAL = ROOT / "app" / "api" / "internal.py"


def _on_visit_source() -> str:
    tree = ast.parse(MAIN.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_on_visit":
            return ast.get_source_segment(MAIN.read_text(encoding="utf-8"), node) or ""
    raise AssertionError("the visit subscriber is gone — the fast path no longer exists")


def test_the_fast_path_resolves_rating_eligibility_per_tenant():
    src = _on_visit_source()
    assert "_rating_eligible" in src, (
        "a fast-path visit that never asks about the rating app always falls back to the plain "
        "confirmation, even for a shop that turned the rating app on")
    assert "_rating_delay_seconds" in src, (
        "eligible without the shop's own delay means every fast-path rating message uses the "
        "platform default instead of what the owner configured")


def test_the_fast_path_resolves_them_as_tenant_resolvers_not_a_shared_bool():
    """Same defect class as ج-5: a single answer computed once would apply one shop's rating
    settings to another shop's customer, since discover() reads across every tenant."""
    src = _on_visit_source()
    assert "lambda t: _rating_eligible(container, t)" in src
    assert "lambda t: _rating_delay_seconds(container, t)" in src


def _text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def test_discover_asks_rating_eligibility_per_tenant_not_a_shared_answer():
    src = _text(INTERNAL)
    assert "rating_eligible=lambda t: _rating_eligible(c, t)" in src
    assert "rating_delay_seconds=lambda t: _rating_delay_seconds(c, t)" in src


def test_catch_up_asks_rating_eligibility_for_the_one_tenant_it_already_knows():
    src = _text(INTERNAL)
    assert "rating_eligible=await _rating_eligible(c, tenant)" in src
    assert "rating_delay_seconds=await _rating_delay_seconds(c, tenant)" in src
