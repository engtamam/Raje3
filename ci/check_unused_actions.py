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
own panel. So the allow-list below is where a deliberate one is written down WITH ITS REASON —
which turns "we know about that one" from a thing somebody remembers into a thing the repository
says.

IT FAILS THE BUILD. It used to print and exit 0, and that is precisely how `whatsapp.register_number`
shipped with no caller: one warning line among many, unread, while every shop that connected sat
«مربوط» and mute for want of a field to type six digits into. The allow-list costs one line and a
reason; silence cost the product its WhatsApp path.

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

    # ── bookings: the backend is Stage 6 (docs/خطة-تنفيذ-الحجوزات.md); the console screen — the
    # catalogue link, the booking dialog, the read-only grid — is the stage's own remaining half
    # and is not built yet. Same shape as tenant.update_config above: the route is real and
    # tested, the caller is the next commit, not a gap in this one.
    "bookings.list": "no console screen yet — Stage 6's grid (docs/خطة-تنفيذ-الحجوزات.md)",
    "bookings.create": "no console screen yet — Stage 6's booking dialog",
    "bookings.reschedule": "no console screen yet — Stage 7's drag-and-drop calls this route",
    "bookings.edit_services": "no console screen yet — Stage 6's booking dialog",
    "bookings.edit_note": "no console screen yet — Stage 6's booking dialog",
    "bookings.cancel": "no console screen yet — Stage 6's booking dialog",
    "bookings.attend": "no console screen yet — Stage 6's booking dialog",
    "bookings.no_show": "no console screen yet — Stage 8's no-show flow",

    # ── written down by the audit, each with the reason it is not a gap ────────────────────────
    "reminders.get_prefs": "the CUSTOMER's own page renders these switches — portal calls the "
                           "internal route with his reference; the console never sees them",
    "reminders.set_prefs": "the same switches, saved from his page. An owner editing his "
                           "customer's notification choices is the one thing consent must not be",
    "partner.my_shops": "the till partner's own portal, not our console (§16.6.3)",
    "partner.my_statements": "the till partner's own portal — his commission, his screen",
    "partner.one_statement": "the till partner's own portal",
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


def platform_declared() -> set[str]:
    """Action ids the PLATFORM declares.

    NOT PART OF THE ORPHAN SCAN, deliberately: base-services ships two hundred actions and this
    product sells a handful of them, so listing the rest as "screens we owe" would bury the ones
    that are actually ours in noise.

    They are read for one purpose — an allow-list line naming one of them is a line about a real
    action, and reporting it as "no longer exists" every single run is the kind of permanent false
    alarm that teaches people to skip the whole report.
    """
    out: set[str] = set()
    for path in (ROOT / "platform" / "services").glob("*/app/user_actions.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            for key, value in zip(node.keys, node.values):
                if (isinstance(key, ast.Constant) and key.value == "id"
                        and isinstance(value, ast.Constant) and isinstance(value.value, str)):
                    out.add(value.value)
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
    # AN ALLOW-LIST LINE IS STALE ONLY IF THE ACTION IS GONE FROM BOTH SIDES. Half of these name a
    # PLATFORM action — billing's invoices, tenant's close, compliance's legal gate — and checking
    # them against our services alone reported nine real, live actions as vanished on every single
    # run. A guard that always prints something to ignore is a guard that gets ignored whole.
    known = set(all_actions) | platform_declared()
    stale = [a for a in NOT_FOR_A_SCREEN if a not in known]

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

    # ── IT FAILS NOW, AND HERE IS WHAT CHANGED THE ANSWER ────────────────────────────────────
    #
    # This file used to print and exit 0, on the reasoning that an orphan is a question rather than
    # a verdict. The reasoning was wrong in exactly one way, and it cost the product its whole
    # WhatsApp path: `whatsapp.register_number` shipped with no caller. It printed one warning line
    # among many, nobody read it, and every shop that connected sat «مربوط» and mute — because the
    # step that turns a connection into a number that sends had no field anywhere.
    #
    # A question nobody answers is a verdict, delivered late.
    #
    # AND THE ALLOW-LIST IS THE PRESSURE VALVE, not a lock: an action that genuinely belongs to a
    # cron, a till, or our own panel takes one line and its reason. What it may not do is stay
    # silent. A STALE entry fails too — a reason for something that no longer exists is what makes
    # the rest of the list stop being believed.
    if orphans or stale:
        print("\n  ✘ every declared action must be reachable, or written down with its reason in "
              "NOT_FOR_A_SCREEN above.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
