#!/usr/bin/env python3
# =============================================================================
# check_field_labels.py — every <Field label=…> binds to a real control.
#
# THE PLATFORM'S `Field` OWNS THE LABEL AND NOT THE CONTROL. It generates an id, points its
# `<label htmlFor>` at it, and leaves wiring that id onto the child to the caller (its own comment
# says so). Omit `htmlFor` + a matching `id` and the label renders, looks perfect, and is bound to
# nothing:
#
#   - a screen reader announces an unnamed text box, which is the whole form for anyone using one,
#   - tapping the label does not focus the input — on a phone that is a missed target, not a nicety,
#   - and getByLabel() cannot find it, so the e2e test that fills it fails as a 60s timeout with no
#     clue as to why. That is exactly how this was found: five fields in «نقاط الولاء» and one in the
#     sign-up pane, all shipped, all invisible to anything that is not a pair of eyes.
#
# A card group is the one legitimate exception — it has no single element to point at, so it is not
# a Field at all: it carries role="group" + aria-label instead.
# =============================================================================
from __future__ import annotations

import glob
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

FIELD = re.compile(r"<Field\b[^>]*\blabel=", re.S)


def main() -> int:
    problems: list[str] = []
    total = 0
    for pattern in ("apps/*/src/**/*.tsx", "apps/*/src/*.tsx"):
        for path in sorted(glob.glob(str(ROOT / pattern), recursive=True)):
            text = Path(path).read_text(encoding="utf-8")
            rel = str(Path(path).relative_to(ROOT)).replace("\\", "/")
            # ONLY THE KIT'S Field, and this scoping is the fix for a false alarm that stood
            # red for weeks. `Services.tsx` defines a LOCAL `Field` that WRAPS its control in a
            # <label> — a binding that needs no id and has nothing wrong with it — and this
            # guard flagged all three of its uses. A red guard nobody can turn green is worse
            # than no guard: it teaches the next reader that red is the normal colour, and the
            # day a real unbound label appears it is the fourth line in a list already ignored.
            if "@base-ui/design-system/Field" not in text:
                continue
            for m in re.finditer(r"<Field\b(.*?)>", text, re.S):
                attrs = m.group(1)
                if "label=" not in attrs:
                    continue
                total += 1
                line = text.count("\n", 0, m.start()) + 1
                # A COMPUTED ID IS STILL AN ID. A list renders one Field per row, so its id has to
                # carry the row's key — `htmlFor={`br-${branch.id}`}` — and a guard that only
                # understands quoted strings would push the author into a constant id repeated
                # once per row, which is the accessibility bug this file exists to catch.
                htmlfor = (re.search(r'htmlFor="([^"]+)"', attrs)
                           or re.search(r'htmlFor=(\{[^}]*\})', attrs))
                if not htmlfor:
                    problems.append(f"{rel}:{line} — <Field label=…> with no htmlFor: the label is "
                                    f"bound to a generated id no control carries, so it names "
                                    f"nothing to a screen reader and focuses nothing when tapped")
                    continue
                # the control has to carry that same id, and it lives in the children right after.
                body = text[m.end():m.end() + 800]
                want = htmlfor.group(1)
                # The same shape either way: a literal must appear as id="…", an expression as
                # id={…} spelled identically — different spellings of "the same" id are how a
                # binding silently breaks.
                bound = f'id={want}' if want.startswith("{") else f'id="{want}"'
                if bound not in body:
                    problems.append(f"{rel}:{line} — htmlFor=\"{htmlfor.group(1)}\" and no control "
                                    f"under it carries that id")

    for p in problems:
        print(f"{C_R}  ✗ {p}{C_N}")
    if problems:
        print(f"\n{C_R}  ✗ {len(problems)} label(s) bound to nothing{C_N}")
        return 1
    print(f"{C_G}  ✔ all {total} labelled fields bind to a real control{C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
