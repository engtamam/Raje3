"""One autonomous run — the simulator running itself end to end and printing what happened,
instead of a human driving each piece by hand one command at a time.

WHAT THIS ACTUALLY DOES, IN ORDER, ALL AGAINST REAL SPAWNED SERVICES:
  1. Spawns a real services/operations.
  2. Populates it with 30 real, independent tenants (`common/population.py`).
  3. Starts real background noise ticking against that pool (`common/background.py`) and, WHILE
     it keeps running, lets the composer (`common/story.py` + `apps/operations/story.py`) pick its
     own real, multi-step business narrative on a fresh tenant — never a human-ordered scenario.
  4. Runs the same generic security checks (forged signature, missing capability, adversarial
     input — `common/checks.py`) against a representative route in every one of the ten real apps
     this simulator drives, each its own freshly spawned instance.
  5. Prints one consolidated report — pass/fail counts and timing, not a wall of raw output.

WHAT THIS DOES NOT CLAIM: the composer's own step catalog (`apps/operations/story.py`) covers
operations only — the other nine apps are proven here on the SECURITY dimension (every one of
them refuses a forged token / a missing capability / adversarial input correctly), not with their
own autonomous business narrative, since no other app has a step catalog built for it yet (see the
README's own note on this being real, scoped future work).

Run: python -m simulator.run_autonomous
"""
from __future__ import annotations

import asyncio
import random
import time

from simulator.apps.bookings.service import spawn as spawn_bookings
from simulator.apps.campaigns.service import spawn as spawn_campaigns
from simulator.apps.coworking.service import spawn as spawn_coworking
from simulator.apps.error_collector.service import spawn as spawn_error_collector
from simulator.apps.insights.service import spawn as spawn_insights
from simulator.apps.loyalty.service import spawn as spawn_loyalty
from simulator.apps.operations.actions import RecordUniqueVisitAction
from simulator.apps.operations.service import spawn as spawn_operations
from simulator.apps.operations.story import build_steps, new_world
from simulator.apps.referrals.service import spawn as spawn_referrals
from simulator.apps.reminders.service import spawn as spawn_reminders
from simulator.apps.whatsapp_assistant.service import spawn as spawn_whatsapp_assistant
from simulator.common.background import run_background_noise
from simulator.common.checks import (
    check_adversarial_input_never_crashes, check_forged_signature_is_refused,
    check_wrong_capability_is_refused,
)
from simulator.common.population import populate
from simulator.common.story import compose_story
from simulator.shared.auth import auth_header, forged_auth_header

TENANT = "auto-run"

SECURITY_CASES = [
    ("operations", spawn_operations, "GET", "/api/v1/staff/operators", "operations.read"),
    ("loyalty", spawn_loyalty, "GET", "/api/v1/loyalty/balance/sub-auto-run", "loyalty.read"),
    ("bookings", spawn_bookings, "GET",
     "/api/v1/bookings?branch_id=branch-1&date=2026-01-01", "bookings.read"),
    ("reminders", spawn_reminders, "GET", "/api/v1/reminders/schedule", "reminders.read"),
    ("campaigns", spawn_campaigns, "GET", "/api/v1/campaigns/goals", "campaigns.read"),
    ("insights", spawn_insights, "GET", "/api/v1/insights/dashboard", "insights.read"),
    ("referrals", spawn_referrals, "GET", "/api/v1/referrals/campaigns", "referrals.manage"),
    ("coworking", spawn_coworking, "GET", "/api/v1/coworking/resources", "coworking.manage"),
    ("error-collector", spawn_error_collector, "GET", "/api/v1/signals", "platform.observability"),
    ("whatsapp-assistant", spawn_whatsapp_assistant, "GET", "/api/v1/assistant/features", None),
]


async def _security_sweep_one(label: str, spawn_fn, method: str, path: str, cap: str | None):
    async with spawn_fn() as svc:
        url = f"{svc.base_url}{path}"
        results = []
        forged = forged_auth_header(tenant=TENANT, caps=(cap,) if cap else ())
        results.append(("forged signature", await check_forged_signature_is_refused(
            method=method, url=url, json_body=None, forged_headers=forged)))
        if cap:
            no_cap = auth_header(tenant=TENANT, caps=())
            results.append(("missing capability", await check_wrong_capability_is_refused(
                method=method, url=url, json_body=None, headers=no_cap)))
        headers = auth_header(tenant=TENANT, caps=(cap,) if cap else ())
        results.append(("adversarial input", await check_adversarial_input_never_crashes(
            method=method, url=f"{url}{'&' if '?' in path else '?'}sim=%27%3Bdrop",
            json_body=None, headers=headers)))
        return label, results


async def main() -> None:
    started = time.monotonic()
    print("=" * 70)
    print("SIMULATOR — autonomous run")
    print("=" * 70)

    print("\n[1/4] spawning services/operations, populating 30 real tenants…")
    async with spawn_operations() as ops:
        def make_tenant_action(tenant_id: str):
            from simulator.apps.operations.actions import CreateBranchAction
            return CreateBranchAction(base_url=ops.base_url, tenant=tenant_id,
                                      branch_name="الفرع الرئيسي")
        pool_results = await populate(make_tenant_action, 30, concurrency=10,
                                      tenant_prefix="auto-run-shop")
        pool_ok = sum(1 for r in pool_results if r.result.ok)
        print(f"      {pool_ok}/{len(pool_results)} tenants created successfully")
        tenants = [r.tenant_id for r in pool_results if r.result.ok]

        print("\n[2/4] starting real background noise, composing a story on a fresh tenant "
             "while it runs…")

        def make_noise():
            tenant = random.choice(tenants)
            return RecordUniqueVisitAction(base_url=ops.base_url, tenant=tenant)

        async with run_background_noise(make_noise, rate_per_second=15.0) as noise:
            steps = build_steps(ops.base_url, TENANT)
            story = await compose_story(steps, world=new_world(), max_steps=60,
                                        rng=random.Random())
            await asyncio.sleep(0.3)  # let a few more noise ticks land after the story finishes
            noise_ticks = noise.count
            noise_ok = noise.ok_count

    print(f"      background noise: {noise_ok}/{noise_ticks} real visits recorded")
    print(f"      composed story: {len(story.history)} moves, "
         f"{len(set(story.step_names))} distinct kinds, {story.ok_count}/{len(story.history)} ok")
    for name in sorted(set(story.step_names)):
        print(f"        - {name}: {story.step_names.count(name)}×")

    print("\n[3/4] running the security sweep across every real app, one at a time…")
    # SEQUENTIAL, DELIBERATELY — ten real uvicorn spawns fired at once starves the CPU on this
    # machine and makes an otherwise-healthy run look hung (a real, established finding this
    # project's own experience already confirmed once for the full test suite); one at a time is
    # slower in wall-clock but the only version that stays honestly readable while it runs.
    sweep = []
    for label, spawn_fn, method, path, cap in SECURITY_CASES:
        sweep.append(await _security_sweep_one(label, spawn_fn, method, path, cap))

    total_checks = 0
    total_ok = 0
    print("\n[4/4] report")
    print("-" * 70)
    for label, results in sweep:
        for check_name, result in results:
            total_checks += 1
            total_ok += int(result.ok)
            mark = "OK " if result.ok else "FAIL"
            print(f"  [{mark}] {label:<20} {check_name:<20} {result.detail}")

    elapsed = time.monotonic() - started
    print("-" * 70)
    print(f"population: {pool_ok}/{len(pool_results)} ok  |  "
         f"noise: {noise_ok}/{noise_ticks} ok  |  "
         f"story: {story.ok_count}/{len(story.history)} ok, {len(set(story.step_names))} kinds  |  "
         f"security: {total_ok}/{total_checks} ok")
    print(f"total wall time: {elapsed:.1f}s")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
