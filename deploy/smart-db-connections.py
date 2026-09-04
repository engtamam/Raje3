#!/usr/bin/env python3
"""smart-db-connections.py — size Postgres's max_connections (and PgBouncer's matching share of
it) from the REAL memory this box has, fully automatically, with a self-healing rollback if it
ever gets it wrong.

RUNS SERVER-SIDE ONLY (needs `kubectl` pointed at the live cluster) — same integration point as
smart-cpu-sizing.py, called from deploy/server/update.sh right before a rollout.

WHY THIS IS ALLOWED TO APPLY ITSELF WHEN smart-cpu-sizing.py's OWN COUSIN CHANGE IS NOT. Raising a
stateless service's cpu request restarts THAT ONE POD — worst case, a few seconds of one service
being slow to reschedule. This restarts POSTGRES — the one shared database every other service in
the fleet depends on. Applying that unsupervised is only responsible if the tool WATCHES its own
result and UNDOES it the instant something looks wrong, rather than trusting the arithmetic and
walking away. That watch-and-revert loop (`apply_and_verify`, below) is the whole reason this file
is longer than the CPU one — it is not extra caution for its own sake, it is the price of removing
the human approval step Tamam explicitly asked to remove.

THE FORMULA (sourced, not invented — see the two web searches this session's own conversation
ran): reserve 15% of the memory GIVEN TO THIS POSTGRES POD for the OS/kernel overhead inside the
container, another 10% for internal maintenance work (vacuum, autovacuum, indexing), and 15-25% as
shared_buffers (this file uses 20%, the middle of the commonly-cited 15-25% range). Whatever is
left over, divided by ~10MB, is the safe number of additional connections — the same rule of thumb
this session's own research turned up (available_memory / 10MB ≈ max_connections).

THE POD'S OWN MEMORY BUDGET IS SIZED FIRST, SEPARATELY, FROM THE NODE'S REAL HEADROOM — the
formula above answers "how many connections can THIS MUCH memory support", not "how much memory
should Postgres have". That second question is answered the same way smart-cpu-sizing.py answers
it for CPU: look at what the node actually has left after everything else running on it, take a
conservative slice of that (never all of it — the same 20-30% additional-headroom guidance this
session's research found, applied here as "grow the pod's memory footprint by at most 30% of the
node's currently-UNUSED memory"), and never shrink below what is already running safely.

NEVER REGRESSES. The new max_connections is always >= the current live value; the new PgBouncer
MAX_DB_CONNECTIONS is always >= its current value. A computation that comes out lower than what is
already running is discarded — that would be an actual regression, not a rejected improvement.

NEVER APPLIES BLIND. `apply_and_verify` patches the StatefulSet, waits for the single Postgres pod
to become genuinely Ready (a real `pg_isready`-backed readiness probe, not just "Running"), and if
that does not happen within READY_TIMEOUT_S, patches the exact previous values right back and waits
for THAT to become Ready too — the fully-automatic version of "if you're not sure, put it back".

Usage (server-side, needs a working `kubectl`):
  python3 deploy/smart-db-connections.py                 # compute, apply, verify, self-heal if needed
  python3 deploy/smart-db-connections.py --dry-run        # compute and print only, touch nothing
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time

NS = "base-services"
STS = "postgres"
PGBOUNCER_DEPLOY = "pgbouncer"

# Reserved fractions WITHIN Postgres's own pod memory — see module docstring for the source.
OS_RESERVE_FRACTION = 0.15
MAINTENANCE_RESERVE_FRACTION = 0.10
SHARED_BUFFERS_FRACTION = 0.20
MB_PER_CONNECTION = 10

# The pod's own memory footprint never grows by more than this fraction of the node's CURRENTLY
# UNUSED memory in one pass — the same "don't spend the whole headroom at once" lesson the CPU
# tool learned live this session, applied here from the start rather than after a near-miss.
MAX_GROWTH_FRACTION_OF_FREE = 0.30
# An absolute ceiling on the pod's own memory request/limit — so a freak reading can never ask for
# an unreasonable jump in one run, self-healing rollback or not.
MAX_POSTGRES_MEMORY_MI = 2048

READY_TIMEOUT_S = 90
POLL_INTERVAL_S = 3


def run(args: list[str]) -> str:
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=30).stdout


def run_json(args: list[str]):
    return json.loads(run(args))


def mi_from_k8s_mem(s: str) -> int:
    """'256Mi' -> 256, '1Gi' -> 1024, '7962060Ki' -> ~7776 (node allocatable's own unit, confirmed
    live — kubectl reports NODE memory in Ki, not Mi/Gi), '512M' -> ~488 (decimal->binary),
    bare bytes -> /1024/1024."""
    s = s.strip()
    if s.endswith("Ki"):
        return int(int(s[:-2]) / 1024)
    if s.endswith("Mi"):
        return int(s[:-2])
    if s.endswith("Gi"):
        return int(float(s[:-2]) * 1024)
    if s.endswith("K"):
        return int(int(s[:-1]) * 1000 / 1_048_576)
    if s.endswith("M"):
        return int(float(s[:-1]) * 1_000_000 / 1_048_576)
    if s.endswith("G"):
        return int(float(s[:-1]) * 1_000_000_000 / 1_048_576)
    return int(int(s) / 1_048_576)


def node_memory_mi() -> tuple[int, int]:
    """(allocatable_mi, currently_requested_mi_across_all_namespaces)."""
    node = run_json(["kubectl", "get", "nodes", "-o", "json"])
    allocatable = sum(mi_from_k8s_mem(n["status"]["allocatable"]["memory"]) for n in node["items"])
    total_requested = 0
    for ns_flag in (["-A"],):
        pods = run_json(["kubectl", "get", "pods", *ns_flag, "-o", "json"])
        for p in pods["items"]:
            if p.get("status", {}).get("phase") in ("Succeeded", "Failed"):
                continue
            for c in p["spec"].get("containers", []):
                mem = c.get("resources", {}).get("requests", {}).get("memory")
                if mem:
                    total_requested += mi_from_k8s_mem(mem)
    return allocatable, total_requested


def get_postgres_state():
    sts = run_json(["kubectl", "-n", NS, "get", "statefulset", STS, "-o", "json"])
    container = sts["spec"]["template"]["spec"]["containers"][0]
    mem_request_mi = mi_from_k8s_mem(container["resources"]["requests"]["memory"])
    mem_limit_mi = mi_from_k8s_mem(container["resources"]["limits"]["memory"])
    args = container.get("args", [])
    max_conn = 100          # postgres's own compiled-in default, until proven otherwise below
    shared_buffers_mb = 128  # postgres's own compiled-in default (128MB)
    for i, a in enumerate(args):
        if a == "-c" and i + 1 < len(args):
            setting = args[i + 1]
            if setting.startswith("max_connections="):
                max_conn = int(setting.split("=", 1)[1])
            elif setting.startswith("shared_buffers="):
                v = setting.split("=", 1)[1]
                shared_buffers_mb = int(v[:-2]) if v.endswith("MB") else int(v)
    return {
        "mem_request_mi": mem_request_mi, "mem_limit_mi": mem_limit_mi,
        "max_connections": max_conn, "shared_buffers_mb": shared_buffers_mb, "args": args,
    }


def get_pgbouncer_max_db_connections() -> int | None:
    dep = run_json(["kubectl", "-n", NS, "get", "deployment", PGBOUNCER_DEPLOY, "-o", "json"])
    for c in dep["spec"]["template"]["spec"]["containers"][0].get("env", []):
        if c["name"] == "MAX_DB_CONNECTIONS":
            return int(c["value"])
    return None


def compute_plan(node_alloc_mi: int, node_requested_mi: int, pg: dict) -> dict:
    # Step 1 — how much bigger can Postgres's OWN memory footprint safely get?
    free_mi = max(0, node_alloc_mi - node_requested_mi)
    growth_budget_mi = int(free_mi * MAX_GROWTH_FRACTION_OF_FREE)
    new_mem_mi = min(MAX_POSTGRES_MEMORY_MI, pg["mem_request_mi"] + growth_budget_mi)
    new_mem_mi = max(new_mem_mi, pg["mem_request_mi"])  # never shrink

    # Step 2 — within THAT budget, the sourced formula: reserve OS + maintenance + shared_buffers,
    # divide what's left by ~10MB/connection.
    shared_buffers_mb = max(pg["shared_buffers_mb"], int(new_mem_mi * SHARED_BUFFERS_FRACTION))
    reserved_mb = int(new_mem_mi * (OS_RESERVE_FRACTION + MAINTENANCE_RESERVE_FRACTION))
    available_for_connections_mb = max(0, new_mem_mi - shared_buffers_mb - reserved_mb)
    computed_max_conn = available_for_connections_mb // MB_PER_CONNECTION

    new_max_conn = max(pg["max_connections"], computed_max_conn)  # never regress

    return {
        "new_mem_mi": new_mem_mi, "new_shared_buffers_mb": shared_buffers_mb,
        "new_max_connections": new_max_conn, "free_mi_before": free_mi,
    }


def patch_postgres(mem_mi: int, mem_limit_mi: int, max_conn: int, shared_buffers_mb: int) -> None:
    args = [
        "postgres", "-c", "ssl=on",
        "-c", "ssl_cert_file=/etc/postgres-tls/tls.crt",
        "-c", "ssl_key_file=/etc/postgres-tls/tls.key",
        "-c", f"max_connections={max_conn}",
        "-c", f"shared_buffers={shared_buffers_mb}MB",
    ]
    patch = [
        {"op": "replace", "path": "/spec/template/spec/containers/0/args", "value": args},
        {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/memory",
         "value": f"{mem_mi}Mi"},
        {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/memory",
         "value": f"{mem_limit_mi}Mi"},
    ]
    subprocess.run(["kubectl", "-n", NS, "patch", "statefulset", STS, "--type=json",
                    "-p", json.dumps(patch)], check=True, timeout=30)
    # A StatefulSet does not restart its pod on a template change by itself the way a Deployment's
    # rollout does — it waits for the pod to be deleted. Force it, deliberately, right here, so
    # "patched" and "restarting" happen in the same breath this script controls.
    subprocess.run(["kubectl", "-n", NS, "delete", "pod", f"{STS}-0", "--wait=false"],
                    check=True, timeout=30)


def wait_ready(timeout_s: int) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            out = run(["kubectl", "-n", NS, "get", "pod", f"{STS}-0",
                       "-o", "jsonpath={.status.containerStatuses[0].ready}"])
            if out.strip() == "true":
                return True
        except subprocess.CalledProcessError:
            pass
        time.sleep(POLL_INTERVAL_S)
    return False


def set_pgbouncer_max_db_connections(value: int) -> None:
    patch = {"spec": {"template": {"spec": {"containers": [
        {"name": PGBOUNCER_DEPLOY, "env": [{"name": "MAX_DB_CONNECTIONS", "value": str(value)}]}
    ]}}}}
    subprocess.run(["kubectl", "-n", NS, "patch", "deployment", PGBOUNCER_DEPLOY,
                    "--type=strategic", "-p", json.dumps(patch)], check=True, timeout=30)


def apply_and_verify(pg: dict, plan: dict) -> bool:
    print(f"applying: memory {pg['mem_request_mi']}Mi -> {plan['new_mem_mi']}Mi, "
          f"max_connections {pg['max_connections']} -> {plan['new_max_connections']}, "
          f"shared_buffers {pg['shared_buffers_mb']}MB -> {plan['new_shared_buffers_mb']}MB")
    patch_postgres(plan["new_mem_mi"], pg["mem_limit_mi"] if pg["mem_limit_mi"] >= plan["new_mem_mi"]
                    else plan["new_mem_mi"] * 2,
                    plan["new_max_connections"], plan["new_shared_buffers_mb"])
    if wait_ready(READY_TIMEOUT_S):
        print("postgres came back Ready with the new settings — keeping them.")
        return True

    print(f"postgres did NOT become Ready within {READY_TIMEOUT_S}s on the new settings — "
          f"reverting to the previous known-good values.", file=sys.stderr)
    patch_postgres(pg["mem_request_mi"], pg["mem_limit_mi"], pg["max_connections"], pg["shared_buffers_mb"])
    if wait_ready(READY_TIMEOUT_S):
        print("reverted successfully — postgres is back on its previous settings and Ready.", file=sys.stderr)
    else:
        print("REVERT ALSO DID NOT BECOME READY IN TIME — this needs a human, now. "
              "Check `kubectl -n base-services describe pod postgres-0` immediately.", file=sys.stderr)
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="compute and print only, apply nothing")
    args = ap.parse_args()

    try:
        node_alloc_mi, node_requested_mi = node_memory_mi()
        pg = get_postgres_state()
    except Exception as exc:
        print(f"smart-db-connections: could not read live cluster state ({exc}) — "
              f"leaving postgres untouched (safe fallback, not an error).", file=sys.stderr)
        return 0

    plan = compute_plan(node_alloc_mi, node_requested_mi, pg)

    print(f"node: {node_alloc_mi}Mi allocatable, {node_requested_mi}Mi requested "
          f"({plan['free_mi_before']}Mi free)")
    print(f"postgres now: {pg['mem_request_mi']}Mi mem, {pg['max_connections']} max_connections, "
          f"{pg['shared_buffers_mb']}MB shared_buffers")
    print(f"postgres proposed: {plan['new_mem_mi']}Mi mem, {plan['new_max_connections']} "
          f"max_connections, {plan['new_shared_buffers_mb']}MB shared_buffers")

    if plan["new_max_connections"] <= pg["max_connections"]:
        print("no improvement available right now (no safe headroom, or already at a good size) "
              "— leaving postgres untouched.")
        return 0

    if args.dry_run:
        print("(dry-run — nothing applied)")
        return 0

    ok = apply_and_verify(pg, plan)
    if not ok:
        return 1

    try:
        current_pgb = get_pgbouncer_max_db_connections()
        # Keep the same 80% safety margin below Postgres's own ceiling this fleet already runs
        # with (80 of 100) — a fixed proportion, not a fixed number, so it scales with whatever
        # max_connections just became.
        new_pgb = int(plan["new_max_connections"] * 0.8)
        if current_pgb is not None and new_pgb > current_pgb:
            set_pgbouncer_max_db_connections(new_pgb)
            print(f"pgbouncer MAX_DB_CONNECTIONS: {current_pgb} -> {new_pgb}")
    except Exception as exc:
        print(f"postgres itself is fine, but updating pgbouncer's own share failed ({exc}) — "
              f"fix that separately; it is not a reason to revert postgres.", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
