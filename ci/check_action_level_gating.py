#!/usr/bin/env python3
"""PHASE 4 of the permission-gate effort (2026-09-26) — a REAL, BLOCKING gate.

Builds on ci/report_action_level_gating.py (PHASE 2, a report, never wired into guards.yml).
That script counts, per screen file, how many real interactive controls it has and how many
times it consults the catalogue at all, and prints two buckets:

  - a "coverage ratio" (controls : catalogue checks) for the majority of screens — NOT reliable
    enough to auto-fail on, since a screen can legitimately have more controls than checks (one
    check gates several controls, or several controls share one nav-level gate) without being
    wrong. Stays advisory only, exactly as PHASE 2 always intended.
  - a "CONFIRMED full gap" list — real controls, ZERO catalogue checks anywhere in the file. This
    signal cannot lie the same way: a screen with at least one write-triggering control and not
    one single `.hasAll(`/`CapabilityGate(` (mobile) or `action(catalog,`/`<Can ` (console)
    consultation is either an unfixed real gap, or a screen this script cannot see the real
    permission story for (pre-catalogue, or gated on a capability the catalogue never declares an
    action id for). PHASE 3 worked every real one of these to zero across both apps
    (see [[permission-gate-phase3-apps-bucket]], [[permission-gate-phase4-console-11-gaps]]).

WHAT THIS GATE ENFORCES. Any file that lands in the CONFIRMED bucket and is NOT in the explicit
EXEMPT map below fails the build. Every current member of that bucket has already been read,
control by control, and is exempted here for a REASON stated next to it — never a blanket
allowance. A new screen that grows a real, ungated write control (or an old one that regresses)
raises the confirmed-gap count above the exempt list's size and fails here immediately.

The exempt list is not "trust the file forever" — it is dated to THIS commit's audit. A future
change to any exempted file must re-examine whether its reason still holds (e.g. `bookings.manage`
gaining a declared catalogue action id would let BookingSettingsDialog.tsx be un-exempted and
actually gated); this script does not know that on its own, so it cannot re-verify the reason —
only a human editing this file when the underlying fact changes can.

Usage:
    python ci/check_action_level_gating.py            # both apps
    python ci/check_action_level_gating.py --mobile    # apps/mobile only
    python ci/check_action_level_gating.py --console   # apps/console only

Exit 0 — every CONFIRMED-gap file is either fixed or explicitly exempted with a reason.
Exit 1 — a CONFIRMED-gap file exists that is not in EXEMPT.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_action_level_gating import scan_console, scan_mobile  # noqa: E402

# path (relative to repo root, forward slashes) -> why this file's zero catalogue checks are not
# a real permission gap, verified control-by-control at the time it was added here.
EXEMPT: dict[str, str] = {
    # ── console ──────────────────────────────────────────────────────────────────────────────
    "apps/console/src/screens/BookingsMonthView.tsx":
        "day/month navigation only (onSelectDay/onSelectMonth) — no API call in the file at all.",
    "apps/console/src/screens/BookingsYearView.tsx":
        "month/day navigation only (onSelectMonth/onSelectDay) — no API call in the file at all.",
    "apps/console/src/screens/CardForm.tsx":
        "its one onClick is the ghost 'cancel' button, a local onCancel callback — no write.",
    "apps/console/src/screens/Door.tsx":
        "its one onClick toggles local `shown` state — no write, no API import in the file.",
    "apps/console/src/screens/Legal.tsx":
        "its one onClick toggles the locale shown locally — no write, no API import in the file.",
    "apps/console/src/screens/ReferralGrantCelebration.tsx":
        "all three onClicks close the celebration overlay (local callbacks) — no write.",
    "apps/console/src/screens/WelcomeTrial.tsx":
        "its one onClick is the dismiss button (local onDone callback) — no write.",
    "apps/console/src/screens/Visit.tsx":
        "whole screen is nav-level gated (services/services_layout requires); its one real write "
        "(the coupon section) is already individually gated — a script false positive confirmed "
        "by direct read, same precedent as Services.tsx's edit form.",
    # ── mobile ───────────────────────────────────────────────────────────────────────────────
    "apps/mobile/lib/features/auth/login_screen.dart":
        "reached before any session/catalogue exists — its one IconButton is a password-visibility "
        "toggle, not a write.",
    "apps/mobile/lib/features/auth/signup_screen.dart":
        "reached before any session/catalogue exists — its controls are a password-visibility "
        "toggle and a 'go to login' nav link, not a write.",
    "apps/mobile/lib/features/apps/payment_webview_screen.dart":
        "its two controls are the close button and a webview retry/reload — neither is a "
        "catalogue-gated write.",
    "apps/mobile/lib/features/auth/verify_phone_screen.dart":
        "reached before any session/catalogue exists — its controls submit/resend an OTP code, "
        "not a catalogue write.",
    "apps/mobile/lib/features/bookings/new_booking_sheet.dart":
        "its 4 IconButtons are day-navigation chevrons and a quantity +/- stepper — local state "
        "only, not writes. The sheet's real write (create/reschedule) fires from PrimaryButton, "
        "outside this scanner's control list, and is reachable only through an entry point "
        "(bookings_screen.dart's FAB / booking_details_sheet.dart's edit button) already gated "
        "on 'bookings.create'.",
}


def _confirmed(rows: list[tuple[str, int, int]]) -> list[tuple[str, int]]:
    return [(rel, controls) for rel, controls, gates in rows if gates == 0]


def _check(title: str, rows: list[tuple[str, int, int]]) -> list[str]:
    failures: list[str] = []
    confirmed = _confirmed(rows)
    print(f"\n▸ {title}")
    if not confirmed:
        print("  ✔ no confirmed full gaps")
        return failures
    for rel, controls in confirmed:
        reason = EXEMPT.get(rel)
        if reason is None:
            failures.append(rel)
            print(f"  ✗ {rel}  ({controls} control(s), 0 catalogue checks) — NOT exempted, real gap")
        else:
            print(f"  ─ {rel}  ({controls} control(s), 0 catalogue checks) — exempted: {reason}")
    return failures


def main(argv: list[str]) -> int:
    do_mobile = "--console" not in argv
    do_console = "--mobile" not in argv

    failures: list[str] = []
    if do_mobile:
        failures += _check("mobile (apps/mobile/lib/features/**/*.dart)", scan_mobile())
    if do_console:
        failures += _check("console (apps/console/src/screens/*.tsx)", scan_console())

    if failures:
        print(f"\n✗ {len(failures)} screen(s) have a real write control with zero catalogue "
              "checks and no exemption reason recorded in ci/check_action_level_gating.py's "
              "EXEMPT map. Either gate the control (action(catalog,'id')/<Can>/hasAll/"
              "CapabilityGate) or, if it genuinely has nothing to gate on, add it to EXEMPT with "
              "a stated reason.")
        for rel in failures:
            print(f"    {rel}")
        return 1

    print("\n✔ every screen with a real write control either checks the catalogue at least once, "
          "or is explicitly exempted with a stated reason. See project memory "
          "[[permission-gate-phase4-console-11-gaps]].")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
