"""Two paths that must never learn what a subscription is.

§16.4.2 separates four behaviours when an establishment stops paying: the data stays, the sending
stops, the customer's page keeps working, and the dashboard keeps rendering. Only one of those is
code that does something. The other three are behaviours by ABSENCE — nothing deletes, nothing
gates — and an absence is exactly what a refactor removes by accident, with nothing failing.

So two of them are held mechanically here.

────────────────────────────────────────────────────────────────────────────────────────────────
THE CUSTOMER'S PAGE MUST NOT CONSULT BILLING

The customer did not fail to pay. Turning his page off punishes him for somebody else's decision,
and it puts our name on a broken page opened by a person with no part in the invoice — who then
tells the shop owner the SHOP's link is broken, which is the opposite of the pressure we want.

`portal` reads from peers and holds nothing, so today this is true by construction. It stops being
true the first time somebody adds "and check they are subscribed" to a read path, which will look
like a small correctness fix.

────────────────────────────────────────────────────────────────────────────────────────────────
AND THE DASHBOARD MUST KEEP RENDERING

The at-risk list piling up is the truest pressure in this product, and the most honest: it is his
own number about his own customers, not a warning we wrote. A dashboard that goes blank on the day
he stops paying replaces the strongest reason to come back with a locked door.

`insights` DOES talk to billing, legitimately, and the first version of this guard failed on all
six places it does. Two different things were being conflated:

  READING a number to show it        — the weekly report's balance line reads messages.monthly so
                                       the owner sees "820 of 1000". That is a number about his
                                       shop, and it must keep being shown when he stops paying.
  GATING what is served on a key     — the association engine is a paid feature (§10.6) and asking
                                       whether it is bought is the gate working.

So the rule is not "insights never mentions billing" — that would ban the balance line, which is
the sixth line of the only report most owners read.

Nor is it a per-line one. The second attempt flagged `allowed_keys()` and `peers.entitled(...)`,
which ARE the engine gate: a line-by-line heuristic cannot tell a gate from the gate it is looking
for, because they are the same lines.

What it actually is: the SET of entitlement keys named anywhere in `insights/app/core` must be
exactly {feature.insights.engine}. One key, one paid feature, and everything else served to
everybody. That is checkable, it is precise, and it fails the moment somebody adds
`feature.campaigns` to a dashboard read — which is the regression worth catching.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

# A read path that reaches for any of these is a read path that has learned about money.
BILLING_SIGNS = re.compile(
    r"BILLING_SERVICE_URL|/internal/billing/|entitlements/check|usage/consume|"
    r"messages\.monthly|subscription_status|is_subscribed")

# The ONE key insights is allowed to gate on, and the reason it is allowed: the association engine
# is a paid feature (spec §10.6), so asking whether it is bought is the gate working, not a
# dashboard refusing to render.
INSIGHTS_ALLOWED = "feature.insights.engine"

# Every entitlement key named, wherever it appears. The SET is what matters, not the lines: a
# per-line rule cannot tell a gate from the gate it is looking for, because they are the same
# lines - allowed_keys() and peers.entitled(...) ARE the engine gate.
FEATURE_KEY = re.compile(r"feature\.[a-z0-9_.]+")

SKIP_PARTS = {".venv", "node_modules", "__pycache__", ".pytest_cache", "tests", "site-packages"}


def _files(service: str):
    base = ROOT / "services" / service / "app"
    if not base.exists():
        return
    for f in base.rglob("*.py"):
        if SKIP_PARTS.intersection(f.parts):
            continue
        yield f


def main() -> int:
    problems: list[str] = []

    # ── portal: nothing, at all ────────────────────────────────────────────────────────────────
    for f in _files("portal"):
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if BILLING_SIGNS.search(line):
                problems.append(
                    f"{f.relative_to(ROOT).as_posix()}:{n}: the customer's page consults billing. "
                    f"The customer is not the one who did not pay, and a page that breaks when his "
                    f"shop's invoice does puts our name on it in front of somebody with no part in "
                    f"it (§16.4.2).\n    {line.strip()[:100]}")

    # ── insights: exactly one entitlement key exists in core/ ─────────────────────────────────
    found: dict[str, str] = {}
    for f in _files("insights"):
        # Plumbing is exempt by LOCATION. A BILLING_SERVICE_URL in config.py and a client in
        # adapters/peers gate nothing; what matters is which keys core/ knows the names of.
        if "core" not in f.parts:
            continue
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            for key in FEATURE_KEY.findall(line):
                found.setdefault(key, f"{f.relative_to(ROOT).as_posix()}:{n}")

    for key, where in sorted(found.items()):
        if key == INSIGHTS_ALLOWED:
            continue
        problems.append(
            f"{where}: insights knows about the entitlement key {key!r}. The association engine "
            f"is a paid feature; the dashboard is not — and a dashboard that goes blank on the day "
            f"he stops paying replaces the strongest reason to come back with a locked door "
            f"(§16.4.2). Exactly one key belongs here: {INSIGHTS_ALLOWED}.")

    for p in problems:
        print(f"\033[31m  x {p}\033[0m")
    if problems:
        print(f"\n\033[31m  x {len(problems)} path(s) that must not know about a subscription\033[0m")
        return 1
    print("\033[32m  ok the customer's page and the dashboard do not consult a subscription\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
