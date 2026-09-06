#!/usr/bin/env python3
"""Every `<AssistantHint anchor="...">` in the console has a real, matching KB entry — and every
KB entry is actually referenced by some icon on some screen.

WHY THIS EXISTS. `by_anchor()` (platform/services/assistant-service/app/core/retrieval.py) matches
an entry's `anchor` field EXACTLY, and a miss is not an error anywhere in the chain: AssistantHint
(apps/console/src/AssistantHint.tsx) reads a 404 as `{kind: 'empty'}` and renders the quiet
sentence «ما فيه شرح لهذا بعد» — by design, since that is also the correct, expected state before
Phase 4 content exists for a given anchor. The SAME quiet handling means a typo'd anchor, a KB
entry renamed on one side and not the other, or a screen wired to an anchor that was never
authored all look IDENTICAL to a user: a "؟" that never answers, forever, with nothing in any log
pointing at which of the two sides is wrong. ci/check_shop_kb_is_valid.py already guards the KB
files' own internal shape (id==anchor, no duplicates); this gate is the other half — the wiring
BETWEEN the two files nobody else compares.

TWO DIRECTIONS, BOTH CHECKED, matching this repo's own check_operator_translations_are_complete.py
shape (a key missing in one direction is exactly as real a bug as one missing in the other):

  - a screen references an anchor with no KB entry — the icon renders and never answers;
  - a KB entry no screen ever references — real, reviewed Arabic content nobody can ever open,
    written and then never wired the way every Phase 4 entry so far paired a JSON entry with the
    <AssistantHint> that asks for it.

    python ci/check_assistant_hint_anchors_exist.py
"""
from __future__ import annotations

import glob
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONSOLE_SRC = ROOT / "apps" / "console" / "src"
KB_DIR = ROOT / "deploy" / "kb" / "shop"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

# `<AssistantHint anchor="x.y" ...>` or `anchor={"x.y"}` — a plain string literal either way. A
# computed anchor (a template literal, a variable) is not matched and is not this gate's problem:
# it cannot be checked statically, the same limitation check_a_message_class_named_anywhere_is_a_
# class_that_exists.py accepts for its own dynamic cases.
_ANCHOR_RE = re.compile(r'<AssistantHint\b[^>]*\banchor=(?:"([^"]+)"|\{"([^"]+)"\})')


def used_anchors() -> dict[str, list[str]]:
    """anchor -> every file (relative path) that references it."""
    out: dict[str, list[str]] = {}
    for path in sorted(CONSOLE_SRC.rglob("*.tsx")):
        if ".test." in path.name:
            continue
        text = path.read_text(encoding="utf-8")
        if "<AssistantHint" not in text:
            continue
        rel = path.relative_to(ROOT).as_posix()
        for m in _ANCHOR_RE.finditer(text):
            anchor = m.group(1) or m.group(2)
            out.setdefault(anchor, []).append(rel)
    return out


def kb_anchors() -> dict[str, str]:
    """anchor -> the file (relative path) that declares it."""
    out: dict[str, str] = {}
    for path in sorted(KB_DIR.glob("*.json")) if KB_DIR.is_dir() else []:
        rel = path.relative_to(ROOT).as_posix()
        try:
            entries = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue   # check_shop_kb_is_valid.py's problem, not this gate's
        if not isinstance(entries, list):
            continue
        for e in entries:
            if isinstance(e, dict) and isinstance(e.get("anchor"), str) and e["anchor"]:
                out[e["anchor"]] = rel
    return out


def main() -> int:
    used = used_anchors()
    declared = kb_anchors()

    if not used and not declared:
        print(f"{C_R}  ✘ found no <AssistantHint> usage and no deploy/kb/shop/*.json entries — "
              f"this gate has nothing to check, which is not the same as finding nothing wrong"
              f"{C_N}")
        return 1

    problems: list[str] = []

    for anchor, files in sorted(used.items()):
        if anchor not in declared:
            where = ", ".join(files)
            problems.append(f"{anchor!r} is used by <AssistantHint> in {where} but no "
                            f"deploy/kb/shop/*.json entry declares it — the icon will render and "
                            f"never answer")

    for anchor, kb_file in sorted(declared.items()):
        if anchor in used:
            continue
        # NOT NECESSARILY A LITERAL `anchor="..."` — Plans.tsx's own `statusAnchor()` returns one
        # of several anchor strings picked at runtime from a label, so the literal never appears
        # next to `<AssistantHint`, only inside the helper that computes it (`return
        # 'store.trialStatus';`). A regex cannot resolve that call the way it resolves a plain
        # attribute, so before calling an anchor orphaned this falls back to the same literal
        # search `<AssistantHint>`'s own JSX attribute check uses: does this exact quoted string
        # appear ANYWHERE in the console's source at all. It would take a coincidental, unrelated
        # string exactly matching a `word.word` anchor id to false-negative here, far rarer than
        # the false positive this replaces.
        quoted = f"'{anchor}'"
        dquoted = f'"{anchor}"'
        if any(quoted in p.read_text(encoding="utf-8") or dquoted in p.read_text(encoding="utf-8")
               for p in CONSOLE_SRC.rglob("*.tsx") if ".test." not in p.name):
            continue
        problems.append(f"{anchor!r} is declared in {kb_file} but no <AssistantHint> in "
                        f"apps/console references it — written content nobody can ever open")

    if problems:
        print(f"{C_R}  ✘ {len(problems)} anchor mismatch(es) between the console and "
              f"deploy/kb/shop/:{C_N}")
        for p in problems:
            print(f"      {p}")
        return 1

    print(f"{C_G}  ✔ {len(used)} anchor(s) — every <AssistantHint> has a matching KB entry, and "
          f"every KB entry is referenced by some screen{C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
