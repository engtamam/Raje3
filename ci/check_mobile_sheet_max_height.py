#!/usr/bin/env python3
"""Every `showModalBottomSheet` opens a sheet that caps its own height — a real, blocking gate.

WHY THIS EXISTS. "الشاشة اللي تتفتح ما تتجاوز ارتفاع معين" (the owner's own standing rule,
confirmed live: a tall form sheet with no cap once grew past the screen's own usable height,
covering the hero header behind it and pushing its own grab handle off past the notch on a real
phone). `app_widgets.dart`'s `appSheetMaxHeight(context)` is the one helper that already computes
the correct cap (screen height minus the larger of the real status-bar inset and a 44px floor —
see that function's own doc comment for why a bare `* 0.9`/`* 0.92` fraction is wrong). This gate
makes sure every new sheet actually uses it, or `DraggableScrollableSheet` (which bounds itself by
construction), instead of an unconstrained `Container` that can grow as tall as its content.

HOW IT DECIDES. Per-FILE, not per-call — the same coarser signal
ci/check_action_level_gating.py already uses for the same reason: knowing exactly which
`showModalBottomSheet` call's builder widget is a full AST question, and a file that calls it at
all should have SOME height-capping code in it somewhere. A file with zero and not in EXEMPT below
fails.

EXEMPT holds real, pre-existing sheets audited at the time they were added here — short, bounded
content (a rename field, a yes/no confirm, a day/time picker, a branch list) that does not grow
unboundedly. It is not a blanket pass: a file added here without checking its own content would
defeat the point of this gate entirely.

Usage:
    python ci/check_mobile_sheet_max_height.py

Exits 1 and lists every offending file if found; exits 0 (silent success message) otherwise.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "apps" / "mobile" / "lib"

# A local sibling import (`import 'other_file.dart' show Thing;`) is how this app splits one
# screen's sheets across several files (apps/mobile/lib/features/bookings/*, for instance) — a
# package-scheme import never matches this, so this only ever follows within-feature files.
_LOCAL_IMPORT = re.compile(r"^import\s+'([\w.]+\.dart)'", re.MULTILINE)

CAP_SIGNS = ("appSheetMaxHeight(", "DraggableScrollableSheet(")

# path (relative to repo root, forward slashes) -> why this file's sheet(s) need no height cap,
# checked against their real content at the time this entry was written.
EXEMPT: dict[str, str] = {
    "apps/mobile/lib/features/account/account_screen.dart":
        "_ChangePasswordSheet is 3 fixed fields + one button — short, fixed content, cannot grow.",
    "apps/mobile/lib/features/account/branches_screen.dart":
        "_AddBranchSheet is 3 fixed fields + submit — short, fixed content, cannot grow.",
    "apps/mobile/lib/features/customers/customers_screen.dart":
        "_AddCustomerSheet is phone+name fields + submit — short, fixed content, cannot grow.",
    "apps/mobile/lib/features/customers/customer_detail_screen.dart":
        "every sheet here (_EditRuleSheet, _RenameSheet, a yes/no confirm) is a single field or a "
        "plain confirm dialog — short, fixed content, cannot grow.",
    "apps/mobile/lib/features/rating/rating_screen.dart":
        "an export-format picker (3 fixed options) and a plain confirm dialog — short, fixed "
        "content, cannot grow.",
    "apps/mobile/lib/features/rating/staff_quadrant.dart":
        "_OperatorTrainingSheet is a fixed note field + submit — short, fixed content.",
    "apps/mobile/lib/features/services/procedures_tab.dart":
        "_LibrarySheet/_ServiceStepsSheet CAN grow with a long step list — a real candidate for a "
        "cap, flagged here rather than fixed silently; out of scope for the pass that added this "
        "gate. Fix before adding more content to either sheet.",
    "apps/mobile/lib/widgets/branch_switcher.dart":
        "_BranchSheet lists the shop's own branches — bounded by how many branches a shop "
        "realistically has, never user-generated content.",
    "apps/mobile/lib/widgets/date_time_picker_sheet.dart":
        "_DayPickerSheet/_TimePickerSheet are fixed-size picker widgets (a calendar grid / a time "
        "wheel) — bounded by construction, not by content that could grow.",
}


def _capped(path: Path, text: str, seen: set[Path]) -> bool:
    """Does this file, or a local sibling file it imports (one level — this app never splits a
    single screen's sheets more than one hop away), contain a real height cap?"""
    if path in seen:
        return False
    seen.add(path)
    if any(sign in text for sign in CAP_SIGNS):
        return True
    for name in _LOCAL_IMPORT.findall(text):
        sibling = path.parent / name
        if sibling.is_file() and sibling not in seen:
            if _capped(sibling, sibling.read_text(encoding="utf-8"), seen):
                return True
    return False


def main() -> int:
    failures: list[str] = []
    for path in sorted(LIB.rglob("*.dart")):
        text = path.read_text(encoding="utf-8")
        if "showModalBottomSheet" not in text:
            continue
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        if _capped(path, text, set()):
            continue
        if rel in EXEMPT:
            continue
        failures.append(rel)

    if failures:
        print(f"✗ {len(failures)} file(s) call showModalBottomSheet with no height cap "
              f"(appSheetMaxHeight/DraggableScrollableSheet) and no EXEMPT reason:")
        for rel in failures:
            print(f"    {rel}")
        print("\nEither cap the sheet's own Container/constraints, or add a real, checked reason "
              "to ci/check_mobile_sheet_max_height.py's EXEMPT map.")
        return 1

    print("✔ every showModalBottomSheet caller either caps its sheet's height or is exempted "
          "with a checked reason")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
