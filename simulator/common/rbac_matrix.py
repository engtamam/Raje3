"""The exhaustive role x route matrix this platform's own research (see ../README.md's own
design-discussion trail) confirmed NOTHING checks today — every existing CI gate is static
analysis (do the two role files agree, is every capability reachable by someone); nothing actually
calls every route as every role and watches what happens. This module is that missing dynamic
check, built entirely on `discovery.py`'s auto-discovered routes and `shared/roles.py`'s real
roles — never a hand-maintained list of either.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import httpclient
from .discovery import DeclaredAction
from ..shared.auth import auth_header
from ..shared.roles import Role


@dataclass
class MatrixResult:
    action_id: str
    role_name: str
    expected_allowed: bool
    status_code: int
    ok: bool
    detail: str = ""


async def check_action_against_every_role(
    action: DeclaredAction, roles: dict[str, Role], *, base_url: str, tenant: str,
    path_params: dict[str, str] | None = None, json_body: dict | None = None,
    timeout: float = 10.0,
) -> list[MatrixResult]:
    """One declared route, tried as EVERY real role. The only judgement call this makes is
    binary: a role whose real capability set includes the route's own declared `capability`
    must NEVER be refused with 403 (a business refusal — 400, 404, a clean domain "no" — is fine
    and expected, only 403 means the AUTHORIZATION layer itself is the problem); a role WITHOUT
    it must ALWAYS get 403, never let through.

    A REAL, KNOWN LIMIT OF THIS SINGLE-CAPABILITY MODEL (found by actually running this against
    services/operations' own real catalog — see tests/test_stage9_rbac_matrix.py's own note for
    the exact cases): a route gated by `require_any_capability(...)` (an OR of several
    capabilities, only one of which the declaration names) or a route that enforces NO capability
    at all (declared one purely to group it in a catalog — both real, source-commented cases
    exist in this codebase today) will produce a result this function correctly computes but that
    is not automatically "wrong" — it means the single-capability model does not apply to that
    particular route, not that the platform's own authorization is broken. Callers sweeping many
    actions at once should expect a short, source-documented allowlist of such routes, the same
    way any other allowlist in this codebase is used only with a real, checked reason.

    `path_params` fills any `{name}` placeholder in the declared path (e.g. `{affiliate_id}`) —
    routes needing a real, already-created resource id are the caller's own setup, same as any
    other Action in this simulator; this function only owns the authorization question.
    """
    path = action.path
    for name, value in (path_params or {}).items():
        path = path.replace("{" + name + "}", value)
    url = f"{base_url}{path}"

    results: list[MatrixResult] = []
    for role in roles.values():
        headers = auth_header(tenant=tenant, caps=tuple(role.capabilities))
        r = await httpclient.request(action.method, url, headers=headers, json=json_body,
                                     timeout=timeout)
        expected_allowed = action.capability in role.capabilities
        if expected_allowed:
            ok = r.status_code != 403
            detail = ("" if ok else
                      f"role {role.name!r} HOLDS {action.capability!r} but was refused 403")
        else:
            ok = r.status_code == 403
            detail = ("" if ok else
                      f"role {role.name!r} LACKS {action.capability!r} but got "
                      f"{r.status_code}, not 403")
        results.append(MatrixResult(
            action_id=action.id, role_name=role.name, expected_allowed=expected_allowed,
            status_code=r.status_code, ok=ok, detail=detail))
    return results
