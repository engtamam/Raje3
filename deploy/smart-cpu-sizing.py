#!/usr/bin/env python3
"""smart-cpu-sizing.py — compute each service's CPU request from the CLUSTER'S REAL SIZE, not a
number written once by hand and never revisited.

THE PROBLEM THIS REPLACES. Every deploy/services/*.values.yaml carries a hand-picked cpu request
(20m-200m today), sized for the box we happened to be testing on. Resize the box — bigger or
smaller — or add a service, and every one of those numbers is silently wrong again until someone
remembers to redo the arithmetic by hand. This script does that arithmetic every time it runs
instead, against whatever the cluster actually reports right now.

HOW IT DECIDES (three tiers, weighted by REAL EVIDENCE from a live load test, not guesswork):
  hot (weight 3):    the services that visibly restarted under real concurrent load today
                     (api-gateway, insights, reminders, operations) — confirmed via
                     `kubectl get pods` restart counts during the concurrency=53 test.
  medium (weight 2): services insights' own dashboard fans out into, or that run on every
                     login (billing-service, loyalty, tenant-service, identity-service).
  cold (weight 1):   everything else — batch/admin/reporting services that a real load test
                     never touched.

THE FORMULA. (node's allocatable cpu - a fixed infra reserve for k3s+Calico, ~1000m measured live
this session) split proportionally by weight, then clamped to [MIN_CPU_M, MAX_CPU_M] so a bad
weight or a tiny node can never starve a service below its proven-safe floor, or let one service
claim the whole box.

NEVER BREAKS THE DEPLOY. If the cluster can't be reached, or the node reports something this
script cannot parse, it changes NOTHING and exits 0 with a warning — the existing hand-written
numbers stay exactly as they are. A missing capability degrades to the status quo, never to a
failed install.

Usage:
  python3 deploy/smart-cpu-sizing.py --dry-run              # preview only, touches nothing
  python3 deploy/smart-cpu-sizing.py --apply                # write the computed numbers
  python3 deploy/smart-cpu-sizing.py --dry-run --node-cpu-millicores 4000   # test against a
                                                              # hypothetical box size, no cluster
                                                              # access needed
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SERVICES_DIR = ROOT / "deploy" / "services"

# ── the tiers, and why (see module docstring) ────────────────────────────────────────────────
# api-gateway gets its OWN tier above the other three hot services: proven live this session that
# 100m still let it restart once under a concentrated burst, because it structurally carries every
# OTHER service's traffic on top of its own — a distinct case from "one busy service", confirmed
# by the 100m->200m bump that session made and then verified via restart-count monitoring.
HOTTEST = {"api-gateway"}
HOT = {"insights", "reminders", "operations", "compliance-service"}
MEDIUM = {"billing-service", "loyalty", "tenant-service", "identity-service"}
WEIGHT = {"hottest": 5, "hot": 3, "medium": 2, "cold": 1}

# EVERYTHING NOT IN deploy/services' OWN TIER SYSTEM, measured live on this exact box: kube-system
# (calico-node + coredns + metrics-server + local-path-provisioner, ~450m) PLUS base-services' own
# fixed infra pods that carry no tier (postgres, redis, pgbouncer, objectstore, console, edge,
# ~370m) = ~820m, plus a margin for CronJob transient churn and the fact that a rollout briefly
# runs an old and a new pod at once. A fixed reserve, not a percentage — infra overhead doesn't
# shrink just because the box got bigger, so subtracting a flat amount is the honest model.
#
# THIS NUMBER WAS WRONG ONCE, LIVE, AND IT MATTERS WHY. The first version guessed 1000m without
# measuring kube-system at all (assumed calico/k3s's OWN process overhead, not pod-scheduled
# requests, when in fact calico-node alone reserves real scheduler-visible cpu). Combined with a
# sanity-gate bug (below) that compared tier floors against the whole node instead of against THIS
# budget, applying it live pushed the node to 99% allocated and stuck several pods (including
# tenant-service) in Pending for real. Recovered by hand; this number and the gate are both fixed
# from that measurement, not from a second guess.
INFRA_RESERVE_M = 900

# Never below the lowest number ALREADY PROVEN SAFE for that tier, live, today — a single global
# floor breaks this: with 26 services splitting ~1000m of real budget on THIS box, a flat 20m
# floor still let the math recommend 79m for the hot tier, a REGRESSION from the 100-200m already
# proven necessary this session (the crash-loop this whole investigation started from). The floor
# has to be per-tier, not per-script, so the tool can never recommend going backwards on the
# services we have live evidence about — it can only ever propose MORE for them, never less.
MIN_CPU_M = {"hottest": 200, "hot": 100, "medium": 50, "cold": 12}
MAX_CPU_M = 300


def tier_of(service: str) -> str:
    if service in HOTTEST:
        return "hottest"
    if service in HOT:
        return "hot"
    if service in MEDIUM:
        return "medium"
    return "cold"


def detect_node_cpu_millicores() -> int | None:
    """Sum of allocatable CPU across all nodes, in millicores. None if it cannot be determined —
    the caller must treat that as "do nothing", never as zero."""
    try:
        out = subprocess.run(
            ["kubectl", "get", "nodes", "-o", "json"],
            capture_output=True, text=True, timeout=15, check=True,
        ).stdout
    except Exception:
        return None
    try:
        data = json.loads(out)
        total = 0
        for node in data.get("items", []):
            cpu = node.get("status", {}).get("allocatable", {}).get("cpu", "")
            total += _parse_cpu_to_millicores(cpu)
        return total or None
    except Exception:
        return None


def _parse_cpu_to_millicores(cpu: str) -> int:
    cpu = (cpu or "").strip()
    if not cpu:
        return 0
    if cpu.endswith("m"):
        return int(cpu[:-1])
    # A bare number is whole cores (kubectl's own convention for allocatable.cpu).
    return int(float(cpu) * 1000)


def compute_shares(services: list[str], node_cpu_m: int) -> dict[str, int]:
    """FLOOR-PLUS-BONUS, not proportional-then-clamp. The first version computed each service's
    share independently from the whole budget, then clamped up to its tier's floor when the raw
    share fell short — which meant clamping never gave anything back: floors summing well under
    budget in isolation still pushed the REAL total over it once every tier that needed clamping
    was added up (confirmed live: floors passed their own sanity check, the actual computed total
    did not, and it shipped anyway — nothing compared the two). This model can't make that mistake
    structurally: every service gets its floor FIRST, hard, then whatever budget is left over is
    handed out as a bonus proportional to weight, capped at MAX_CPU_M. The sum of the result is
    provably <= budget by construction — there is no separate total to fall out of sync with."""
    budget = max(0, node_cpu_m - INFRA_RESERVE_M)
    floors = {s: MIN_CPU_M[tier_of(s)] for s in services}
    floor_sum = sum(floors.values())
    leftover = max(0, budget - floor_sum)
    weights = {s: WEIGHT[tier_of(s)] for s in services}
    total_weight = sum(weights.values()) or 1
    shares = {}
    for s in services:
        bonus = leftover * weights[s] / total_weight
        shares[s] = min(MAX_CPU_M, floors[s] + round(bonus))
    return shares


_CPU_LINE_RE = re.compile(r"^(\s*cpu:\s*)(\d+)m(\s*(?:#.*)?)$", re.MULTILINE)


def apply_to_file(path: Path, new_cpu_m: int, dry_run: bool) -> tuple[int | None, bool]:
    """Returns (old_value_m, changed). Only touches the FIRST cpu: line under resources.requests —
    every one of these files has exactly one (verified live across the fleet before writing this)."""
    text = path.read_text(encoding="utf-8")
    m = _CPU_LINE_RE.search(text)
    if not m:
        return None, False
    old_m = int(m.group(2))
    if old_m == new_cpu_m:
        return old_m, False
    if dry_run:
        return old_m, True
    new_line = f"{m.group(1)}{new_cpu_m}m  # smart-cpu-sizing.py: {tier_of(path.stem.removesuffix('.values'))} tier, node budget-derived"
    new_text = text[: m.start()] + new_line + text[m.end():]
    path.write_text(new_text, encoding="utf-8")
    return old_m, True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write the computed values (default: dry-run)")
    ap.add_argument("--dry-run", action="store_true", help="preview only, the default if --apply is omitted")
    ap.add_argument("--node-cpu-millicores", type=int, default=None,
                     help="override cluster detection — test a hypothetical box size with no cluster access")
    ap.add_argument("--values-dir", type=Path, default=DEFAULT_SERVICES_DIR,
                     help="directory of *.values.yaml to size (default: deploy/services). Pass "
                          "deploy/pinned here too if that is what's actually about to be rolled — "
                          "sizing the directory nothing reads from would be a silent no-op.")
    args = ap.parse_args()
    apply = args.apply and not args.dry_run
    SERVICES_DIR = args.values_dir

    node_cpu_m = args.node_cpu_millicores
    if node_cpu_m is None:
        node_cpu_m = detect_node_cpu_millicores()
    if node_cpu_m is None:
        print("smart-cpu-sizing: could not detect cluster CPU capacity — leaving every "
              "values.yaml untouched (this is the safe fallback, not an error).", file=sys.stderr)
        return 0

    files = sorted(SERVICES_DIR.glob("*.values.yaml"))
    services = [f.stem.removesuffix(".values") for f in files]
    shares = compute_shares(services, node_cpu_m)

    # SANITY GATE, BEFORE TOUCHING ANYTHING. The per-tier floors are hard minimums — if their sum
    # alone doesn't fit in the BUDGET (node capacity minus everything NOT in this tier system —
    # kube-system, fixed infra pods, CronJob/rollout churn margin), no amount of proportional math
    # can fix that, and writing these numbers anyway would recreate the exact "Insufficient cpu"
    # scheduling failure this whole investigation started from (a rollout pod stuck Pending
    # because reservations exceeded real capacity).
    #
    # THIS MUST COMPARE AGAINST THE BUDGET, NOT THE RAW NODE SIZE — comparing against node_cpu_m
    # directly was the bug that let this ship once: floors summing to 1208m passed a check against
    # a 2000m node (1208 < 2000, looks fine) while the REAL usable budget after INFRA_RESERVE_M was
    # only ~1100m — so the floors alone already overcommitted the node the moment every other fixed
    # pod was counted, and nothing here said so before it was applied live.
    budget = max(0, node_cpu_m - INFRA_RESERVE_M)
    floor_sum = sum(MIN_CPU_M[tier_of(s)] for s in services)
    if floor_sum > budget:
        print(f"smart-cpu-sizing: the proven-safe floors alone ({floor_sum}m) exceed this node's "
              f"real service budget ({budget}m = {node_cpu_m}m allocatable - {INFRA_RESERVE_M}m "
              f"infra reserve) — this box is too small for the current tier floors. Leaving every "
              f"values.yaml untouched; a smaller fleet, a bigger box, or lower floors are the real "
              f"fix, not silently overcommitting.", file=sys.stderr)
        return 0

    print(f"node allocatable: {node_cpu_m}m   infra reserve: {INFRA_RESERVE_M}m   "
          f"service budget: {max(0, node_cpu_m - INFRA_RESERVE_M)}m")
    print(f"{'service':<24} {'tier':<8} {'old':>6} {'new':>6}")
    any_changed = False
    for f in files:
        svc = f.stem.removesuffix(".values")
        new_m = shares[svc]
        old_m, changed = apply_to_file(f, new_m, dry_run=not apply)
        any_changed = any_changed or changed
        flag = " (changed)" if changed else ""
        old_disp = f"{old_m}m" if old_m is not None else "?"
        print(f"{svc:<24} {tier_of(svc):<8} {old_disp:>6} {new_m:>5}m{flag}")

    if not apply:
        print("\n(dry-run — nothing written; pass --apply to write these values)")
    elif not any_changed:
        print("\nAll services already at their computed values — nothing to write.")
    else:
        print("\nWritten. Re-run deploy/ship.sh for the changed services to take effect.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
