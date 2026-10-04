#!/usr/bin/env python3
"""No `fromJson` field meant for display may fall back to a raw backend id when the server sends
no real name — a raw uuid/opaque-id string is never something a person should read on screen.

WHY THIS EXISTS. Found live, 2026-09-22: `ReminderRule.serviceName` (models/customer_model.dart)
read `json['service_name'] as String? ?? serviceId` — for a row the reminders service returns
with no `service_name` of its own, the customer detail screen's «دورات التذكير» card rendered
the raw `srv_56047a1bcef74b92b5d72f8baf2e2df7` id directly as the row's label. The fix moved the
fallback out of the model (a `null` name now stays `null`) and into the screen, which resolves a
real name from the shop's own service catalogue first and only shows an honest "unknown service"
label if even that comes up empty — never the id itself. This gate exists so the NEXT `_name`
field that falls back to its own sibling `_id` at parse time is caught here, not live on a
screen, the same "regression class caught once, gated forever" reasoning every other check in
this directory already holds to.

WHAT IT CATCHES: a `fromJson`-shaped assignment of the form
    xName: json['x_name'] as String? ?? xId
(or any `?? <identifier ending in Id>` on the same logical field-assignment line) — the exact
shape of the bug above. A field that falls back to a literal (`?? ''`, `?? 'غير معروف'`) is fine;
only a fallback to another *_id-suffixed identifier is flagged, since that is specifically an id
substituting for a name.

Usage:
    python ci/check_mobile_no_raw_id_fallback.py

Exits 1 and prints every violation if found; exits 0 (silent) if none.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOBILE_LIB = ROOT / "apps" / "mobile" / "lib"

# A field whose own name reads as a display label (…Name/…Title/…Label), assigned via `??` to an
# identifier that reads as an id (…Id/…id, or a raw `json['..._id']` lookup) on the same line.
PATTERN = re.compile(
    r"\b(\w*(?:Name|Title|Label))\s*:\s*[^,;\n]*\?\?\s*(\w*(?:Id|id)\b|json\[['\"]\w*_id['\"]\])"
)


def main() -> int:
    violations: list[str] = []
    for f in sorted(MOBILE_LIB.rglob("*.dart")):
        text = f.read_text(encoding="utf-8")
        for i, line in enumerate(text.split("\n"), start=1):
            m = PATTERN.search(line)
            if m:
                rel = f.relative_to(ROOT).as_posix()
                violations.append(
                    f"✗ {rel}:{i} — '{m.group(1)}' falls back to id-shaped '{m.group(2)}': "
                    f"{line.strip()}"
                )

    if violations:
        print("\n".join(violations))
        print(
            f"\n{len(violations)} field(s) fall back to a raw id — resolve a real name "
            "(e.g. from a catalogue lookup) at the call site instead, and give the model an "
            "honest null/empty fallback."
        )
        return 1

    print("✔ no display field falls back to a raw id")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
