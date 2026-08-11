"""Every declared action, and whether any screen calls it.

WHY THIS EXISTS. Six times in one day this codebase produced the same defect: a capability built,
tested, correct — and reachable by nothing. `core/ladder.py` had ten passing tests and no caller.
`Earner.from_visit` had four hundred and no caller. `svc_visit_confirmation` shipped in the first
template seed and nothing ever created the row. Every suite was green throughout, because a unit
test proves a function works and cannot see that nobody runs it.

`check_ui_actions.py` already asks the opposite question — does every action a SCREEN names exist?
That direction catches typos. This one catches abandonment, which is the more expensive of the two:
a typo fails loudly on the first click, and an orphan is silent for months.

AN UNCALLED ACTION IS NOT AUTOMATICALLY A BUG. Some belong to the till, some to a cron, some to our
own panel, and some are genuinely coming next week. So this REPORTS rather than fails, and the
allow-list below is where a deliberate one is written down WITH ITS REASON — which turns "we know
about that one" from a thing somebody remembers into a thing the repository says.

    python ci/check_unused_actions.py
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"
CONSOLE = ROOT / "apps" / "console" / "src"

# CALLED BY SOMETHING THAT IS NOT A SCREEN — each with the caller named, so a line that stops being
# true can be found. An entry here is a claim, and a claim with no caller is the bug this file
# exists to catch.
NOT_FOR_A_SCREEN: dict[str, str] = {
    "operations.verify_pin": "the field app's own PIN gate, before the shell mounts",
    "operations.customers_by_refs": "insights and the campaign preview, resolving pseudonyms in bulk",
    "subscription.activate": "our panel, when a plan is granted from outside the product",
    "billing.invoice_document": "the download button composes it from invoice_pdf/receipt",
    "billing.invoice_settlements": "read by the invoice row when a payment is disputed",
    "billing.start_checkout": "the payment provider's redirect, not a screen action",
    "billing.pause": "our panel — an owner pauses by cancelling, and support reverses it",
    "billing.reactivate": "our panel, the counterpart of pause",
    "billing.change_plan": "chosen from the plans grid, which calls subscribe on a live plan",
    "analytics.export": "the weekly digest job, not a screen",
    "analytics.retention": "the insights snapshot job",
    "compliance.accept_legal": "the legal gate on first sign-in",
    "tenant.close": "our panel only — an owner closing his own shop goes through support",
    "tenant.update_config": "no screen yet: timezone and calendar are read-only for now",
    "wallet.my_ledger": "wallet is not sold in any plan (§6.8)",
    "wallet.my_balance": "wallet is not sold in any plan (§6.8)",
}


def declared() -> dict[str, str]:
    """action id -> the service that declares it."""
    out: dict[str, str] = {}
    for path in SERVICES.glob("*/app/user_actions.py"):
        service = path.parts[-3]
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            for key, value in zip(node.keys, node.values):
                if (isinstance(key, ast.Constant) and key.value == "id"
                        and isinstance(value, ast.Constant) and isinstance(value.value, str)):
                    out[value.value] = service
    return out


def paths_of(actions: dict) -> dict[str, str]:
    """action id -> its declared path, so a literal URL can be matched back to the action."""
    out: dict[str, str] = {}
    for path in SERVICES.glob("*/app/user_actions.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            entry = {}
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and isinstance(value, ast.Constant):
                    entry[key.value] = value.value
            if "id" in entry and "path" in entry:
                out[entry["id"]] = entry["path"]
    return out


def named_by_the_console(by_path: dict[str, str]) -> set[str]:
    """Every action the console reaches — by id, OR by writing its URL out longhand.

    THE SECOND HALF IS NOT A CONVENIENCE. `api.ts` composes literal paths for the field screen, so
    an id-only search reports `loyalty.redeem` as called by nothing while the redemption sheet
    calls it on every visit. Reporting that as an orphan would send somebody to delete a live
    route — a check that lies in the expensive direction.
    """
    text = chr(10).join(p.read_text(encoding="utf-8") for p in CONSOLE.rglob("*.ts*"))
    seen: set[str] = set()
    for match in re.finditer(r"['\"]([a-z_]+(?:\.[a-z_]+)+)['\"]", text):
        seen.add(match.group(1))

    for action, path in by_path.items():
        # The literal prefix before any {param} — enough to identify the route in a template
        # string without pretending to parse one.
        stem = path.split("{")[0].rstrip("/")
        if stem and stem in text:
            seen.add(action)
    return seen


def main() -> int:
    all_actions = declared()
    used = named_by_the_console(paths_of(all_actions))

    orphans = {a: s for a, s in sorted(all_actions.items())
               if a not in used and a not in NOT_FOR_A_SCREEN}
    stale = [a for a in NOT_FOR_A_SCREEN if a not in all_actions]

    print(f"declared: {len(all_actions)}   named by a screen: "
          f"{len([a for a in all_actions if a in used])}   "
          f"accounted for elsewhere: {len(NOT_FOR_A_SCREEN)}")

    if stale:
        # A REASON FOR AN ACTION THAT NO LONGER EXISTS is a note nobody will ever delete, and it
        # makes the rest of the list less believable.
        print("\nallow-list entries for actions that no longer exist:")
        for a in stale:
            print(f"  - {a}")

    if orphans:
        print(f"\n{len(orphans)} action(s) nothing calls — each is either a screen we owe or a "
              f"line for the allow-list:")
        for action, service in orphans.items():
            print(f"  {service:<12} {action}")
    else:
        print("\nevery declared action is either called by a screen or accounted for.")

    # REPORTS, NEVER FAILS. See the module note: an orphan is a question, not a verdict, and a
    # check that blocks a deploy over a question is a check people learn to skip.
    return 0


if __name__ == "__main__":
    sys.exit(main())
