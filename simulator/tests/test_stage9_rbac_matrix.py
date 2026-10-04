"""The exhaustive role x route matrix — no hand-maintained route list, no hand-maintained role
list. `discovery.py` reads services/operations' OWN `app/user_actions.py`; `shared/roles.py`
reads the platform's OWN `deploy/seed/roles.json`. A new role, a new capability grant, or a new
declared route is picked up automatically the next time this runs — nothing here is edited when
any of those change on the code side.

This is the gap the roles/capabilities research this session found and named explicitly: every
existing CI gate is static analysis (do two role files agree, is a capability reachable by
someone); nothing calls every route as every role and watches what actually happens over real
HTTP. This file is that missing check, run for real.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from simulator.apps.operations.service import spawn
from simulator.common.discovery import discover_actions
from simulator.common.rbac_matrix import check_action_against_every_role
from simulator.shared.roles import load_roles

TENANT = "sim-stage9"
_OPERATIONS_DIR = Path(__file__).resolve().parents[2] / "services" / "operations"


def run(coro):
    return asyncio.run(coro)


def test_discovery_finds_real_declared_actions_not_an_empty_or_fake_list():
    actions = discover_actions(_OPERATIONS_DIR)
    assert len(actions) > 20, "expected services/operations' own real, sizeable action catalog"
    ids = {a.id for a in actions}
    assert "affiliate.list" in ids
    assert "affiliate.add" in ids


def test_roles_are_loaded_from_the_real_deploy_seed_file_not_hardcoded():
    roles = load_roles()
    assert "owner" in roles
    assert "operations.record" in roles["owner"].capabilities
    # the owner role is documented (deploy/seed/roles.json's own _comment) as holding every
    # capability anyone can be granted, EXCEPT `partner.read` — that one capability is deliberately
    # NOT the owner's to hold: it identifies the external till company authenticating to its own
    # statements under a contract, a role distinct from any human account, owner included (the
    # same file's own _comment: "partner is excluded on purpose... our terms with it are a
    # contract rather than a click"). A real, documented exception, not a gap in this check.
    all_caps_anyone_holds = {c for role in roles.values() for c in role.capabilities}
    assert all_caps_anyone_holds - {"partner.read"} <= roles["owner"].capabilities


# A REAL FINDING from actually running this sweep (not a workaround written to make failures go
# away): `check_action_against_every_role`'s own model assumes ONE declared capability is exactly
# what gates a route — true for the overwhelming majority of this service's own catalog, and
# false in two genuine, source-documented ways this sweep is not equipped to judge automatically:
#   1. A route gated by `require_any_capability(...)` (an OR of several capabilities) — the
#      declaration names only ONE of the acceptable capabilities, so a role holding a DIFFERENT
#      one from the same OR-set correctly gets through, which this matrix's single-capability
#      model reads as a false failure. (`operations.list_operators_for_bookings`/
#      `operations.list_branches_for_bookings` — services/operations/app/api/v1/staff.py's own
#      `_READ_OPERATORS_FOR_BOOKINGS = require_any_capability("operations.read", "bookings.read",
#      "bookings.write")`.)
#   2. A route with NO capability requirement at all — `Depends(require_user)` only — declared
#      with a capability purely so it appears grouped alongside related screens in a catalog,
#      never enforced. Both cases below carry their own explicit comment in the real source
#      admitting this ("not because it is actually gated on it"): `operations.whoami`
#      (admin_actions.py) and `subscription.apps_static_features` (api/v1/subscription.py).
#   3. `partner.my_shops`/`partner.my_statements` need an ADDITIONAL identity claim beyond any
#      capability (a real partner id the route resolves and 403s without — see partner.py's own
#      `_partner_id` helper) — a generic role-minted token, correct capability and all, still
#      gets refused for a reason this matrix has no way to supply generically.
# Every action NOT in this list is asserted strictly — a NEW mismatch anywhere else is real.
_KNOWN_NOT_SINGLE_CAPABILITY_GATED = {
    "operations.list_operators_for_bookings", "operations.list_branches_for_bookings",
    "operations.whoami", "subscription.apps_static_features",
    "partner.my_shops", "partner.my_statements",
}


def test_every_get_action_with_no_path_params_matches_every_real_role_correctly():
    """THE MAIN PROOF: every GET route services/operations itself declares, with no path
    parameter to resolve (so no per-route setup is needed), tried as literally every seeded role
    against a REAL running server — auto-discovered, not hand-picked."""
    actions = [a for a in discover_actions(_OPERATIONS_DIR)
              if a.method == "GET" and "{" not in a.path
              and a.id not in _KNOWN_NOT_SINGLE_CAPABILITY_GATED]
    assert len(actions) >= 5, "expected a real, non-trivial set of parameterless GET actions"
    roles = load_roles()

    async def _go():
        async with spawn() as svc:
            all_results = []
            for action in actions:
                results = await check_action_against_every_role(
                    action, roles, base_url=svc.base_url, tenant=TENANT)
                all_results.extend(results)
            return all_results

    all_results = run(_go())
    failures = [r for r in all_results if not r.ok]
    assert not failures, "\n".join(f"{r.action_id} / {r.role_name}: {r.detail}"
                                   for r in failures)
    # a real, sizeable matrix actually ran — not a vacuous pass over an empty list.
    assert len(all_results) == len(actions) * len(roles)


def test_the_matrix_catches_a_role_missing_the_narrower_affiliates_read_capability():
    """A targeted proof within the same generic sweep: `affiliate.list` requires
    `operations.affiliates_read` — this session's own deep-review fix (Phase 5c). `manager` does
    NOT hold it (an ordinary manager reads the customer book, not payout data — see
    deploy/seed/roles.json), `owner` does. The matrix must reflect exactly that, discovered from
    the real files, never asserted by name here as a hardcoded expectation about the ROUTE (only
    about which named roles the real file says hold what)."""
    actions = discover_actions(_OPERATIONS_DIR)
    action = next(a for a in actions if a.id == "affiliate.list")
    roles = load_roles()
    assert "operations.affiliates_read" not in roles["manager"].capabilities
    assert "operations.affiliates_read" in roles["owner"].capabilities

    async def _go():
        async with spawn() as svc:
            return await check_action_against_every_role(
                action, roles, base_url=svc.base_url, tenant=TENANT)

    results = run(_go())
    by_role = {r.role_name: r for r in results}
    assert by_role["manager"].status_code == 403
    assert by_role["owner"].status_code != 403
    assert all(r.ok for r in results)


def test_a_real_post_action_with_a_body_also_matches_every_role_correctly():
    """POST works too, not just GET — `affiliate.add` (operations.manage, owner-only in
    practice among the seeded roles) with a real, valid body."""
    actions = discover_actions(_OPERATIONS_DIR)
    action = next(a for a in actions if a.id == "affiliate.add")
    roles = load_roles()
    body = {"phone": "0511111111", "code": "MATRIX01", "discount_percent": 10,
           "reward_type": "fixed_points", "reward_params": {"points": 10}}

    async def _go():
        async with spawn() as svc:
            return await check_action_against_every_role(
                action, roles, base_url=svc.base_url, tenant=TENANT, json_body=body)

    results = run(_go())
    assert all(r.ok for r in results), [r.detail for r in results if not r.ok]
