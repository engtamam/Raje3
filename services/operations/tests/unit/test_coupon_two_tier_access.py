"""Two-tier coupon access (owner decision, 2026-09-19).

STRONG (`operations.grant_coupon_direct`, owner/manager only) reaches the standalone «تحالف
استراتيجي» page and everything on it. WEAK (`operations.grant_coupon`) reaches only the
visit-recording screen's own shortcut checkbox — now held by supervisor, operator AND marketer.

This required decoupling "may submit a grant" from "may open the standalone page": the real grant
action (`operations.grant_coupon`, POST /coupons/grant) now advertises the WEAK capability in the
catalogue so weak-tier roles see the visit-screen checkbox at all (nav.ts / Visit.tsx both gate on
the action's PRESENCE in the caller's catalogue, which is driven by this declared capability) —
while a new, route-less action, `operations.coupons_page`, keeps the STRONG capability purely so
nav.ts / Coupons.tsx can still require it for the standalone page.

Actual authorization of the standalone POST /coupons/grant endpoint is untouched (still
`_GRANT_COUPON_DIRECT` in staff.py, covered by test_coupons_api.py) — this file only covers the
catalogue-declaration and role-membership side of the split.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.user_actions import USER_ACTIONS

ROOT = Path(__file__).resolve().parents[4]
STRONG = "operations.grant_coupon_direct"
WEAK = "operations.grant_coupon"


def _by_id(action_id: str) -> dict:
    for a in USER_ACTIONS:
        if a["id"] == action_id:
            return a
    raise AssertionError(f"no such action: {action_id}")


def test_the_real_grant_action_now_accepts_the_weak_capability():
    """A weak-tier holder must actually be able to submit — not just see a button that 403s."""
    assert _by_id("operations.grant_coupon")["capability"] == WEAK


def test_the_new_page_gate_action_stays_strong_only():
    """`operations.coupons_page` is the ONLY thing keeping weak-tier roles off the standalone
    page now that the grant action itself accepts the weak capability."""
    page = _by_id("operations.coupons_page")
    assert page["capability"] == STRONG
    assert page["id"] not in {"operations.grant_coupon"}


def test_the_preferences_toggle_stays_strong_only():
    """Untouched by this change — the shop-wide on/off switch for the visit checkbox is still
    owner/manager only."""
    assert _by_id("operations.coupon_preferences_set")["capability"] == STRONG


def test_the_four_readonly_coupon_actions_stay_weak_gated():
    """History/stats/check/prefs-get were already available to weak-tier holders before this
    change (read-only conveniences for a visit-linked grant) and nothing about the new split
    changes that."""
    for action_id in (
        "operations.coupon_history", "operations.coupon_stats",
        "operations.coupon_check", "operations.coupon_preferences_get",
    ):
        assert _by_id(action_id)["capability"] == WEAK


def _roles() -> dict[str, set[str]]:
    data = json.loads((ROOT / "services/operations/data/roles.seed.json").read_text(encoding="utf-8"))
    return {r["name"]: set(r["capabilities"]) for r in data["roles"]}


def test_owner_and_manager_keep_the_strong_tier_unchanged():
    roles = _roles()
    for name in ("owner", "manager"):
        assert STRONG in roles[name]
        assert WEAK in roles[name]


def test_supervisor_loses_the_standalone_page_but_keeps_the_visit_shortcut():
    roles = _roles()
    assert STRONG not in roles["supervisor"]
    assert WEAK in roles["supervisor"]


def test_operator_is_unchanged_weak_only():
    roles = _roles()
    assert STRONG not in roles["operator"]
    assert WEAK in roles["operator"]


def test_marketer_gains_the_visit_shortcut_but_not_the_standalone_page():
    roles = _roles()
    assert STRONG not in roles["marketer"]
    assert WEAK in roles["marketer"]


def test_deploy_seed_stays_byte_identical_in_roles():
    """The real sync gate is ci/check_roles.py; this is a narrower, coupon-specific sanity check
    that both files were edited together rather than just one."""
    deploy = json.loads((ROOT / "deploy/seed/roles.json").read_text(encoding="utf-8"))
    deploy_roles = {r["name"]: set(r["capabilities"]) for r in deploy["roles"]}
    assert deploy_roles == _roles()
