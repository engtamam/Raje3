"""Platform-scale infrastructure, piece 2: populating an already-running real service with MANY
real, independent tenants at once — so a scenario (or a new app being added) meets a platform that
already has thousands of real shops in it, not an empty sandbox with one hand-created tenant.

Kept app-agnostic on purpose, the same discipline `common/` already holds everywhere else (never
imports from `apps/`): the caller supplies `make_action(tenant_id) -> Action` — e.g.
`apps/operations/actions.py::CreateBranchAction` today, any other app's own "create my first real
record" action tomorrow, with zero changes here.

Bounded concurrency, same reasoning as `load.py::run_load`: creating thousands of tenants all at
once against one real process is not "realistic scale", it is just a self-inflicted overload — the
opposite of what this piece is for. The difference from `run_load` is what varies per invocation:
`run_load` repeats ONE caller/action `count` times; here every invocation is a DIFFERENT tenant
(a fresh, isolated `Context` per tenant is therefore not a choice, it is a correctness requirement
— two tenants must never share scratch data).
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from .action import Action, ActionResult, Context
from .engine import run_one


@dataclass
class TenantResult:
    tenant_id: str
    result: ActionResult


async def populate(make_action: Callable[[str], Action], count: int, *,
                    concurrency: int = 20, tenant_prefix: str = "sim-shop") -> list[TenantResult]:
    """Create `count` real, independent tenants against whatever `make_action` was built to call,
    at most `concurrency` genuinely concurrent at a time. Tenant ids are `{tenant_prefix}-{i}`,
    deterministic and distinct — a caller that needs to look one back up later (to run more
    scenarios against a specific tenant from the population) does not need to keep the return value
    around to do it.

    Returns one `TenantResult` per tenant, aligned to `tenant_id`, not completion order — unlike
    `run_concurrent`/`run_load`, "which tenant got which result" is the entire point of this call,
    never a detail a caller is expected to discard.
    """
    if count < 1:
        return []
    concurrency = max(1, concurrency)

    async def _one(tenant_id: str) -> TenantResult:
        result = await run_one(make_action(tenant_id), Context())
        return TenantResult(tenant_id=tenant_id, result=result)

    tenant_ids = [f"{tenant_prefix}-{i}" for i in range(count)]
    out: list[TenantResult] = []
    for start in range(0, len(tenant_ids), concurrency):
        batch_ids = tenant_ids[start:start + concurrency]
        batch = await asyncio.gather(*(_one(tid) for tid in batch_ids))
        out.extend(batch)
    return out
