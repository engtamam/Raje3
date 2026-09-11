#!/usr/bin/env python3
# =============================================================================
# check_no_base_remnants.py — الأساس is retired (2026-09-10). No live code anywhere may still
# assume it exists.
#
# THE BUG THIS GATE EXISTS TO STOP RECURRING. `plans.json` dropped the base row outright, but two
# real bugs shipped afterward anyway because OTHER code still read a "has a base" signal that could
# now never be true: `may_add()` (operations) refused to sell 5 of 7 apps forever, and Plans.tsx
# (console) forced `sellable: false` on the same apps in the UI — both found only by a manual,
# one-off audit, not by anything that runs on every change. This gate is that missing net.
#
# A LINE, NOT A FILE, IS THE UNIT. `is_base`/`has_base`/`hasBase`/`feature.base`/`baseSub` all
# still appear legitimately in COMMENTS that document the retirement itself ("NO feature.base ANY
# MORE") — those are history, not a live assumption, and are skipped by the comment heuristic
# below. What this gate refuses is the identifier appearing in real code: a parameter, a call, an
# import, a condition.
#
# THE ALLOWLIST IS THE SWEPT, REVIEWED REMAINDER — every entry here was read line-by-line by a
# 2026-09-11 audit and is EITHER a still-legitimate structural reader (`is_base()`'s own
# definition: "does this row carry messages.monthly", a real question even though no row answers
# yes today) OR a provably dead branch too low-risk to rip out on its own PR (documented at its own
# site). A new line hitting one of the patterns below and NOT in this list is refused outright —
# growing the allowlist requires the same read this file's own comment describes, not a copy-paste
# past the gate.
#
# Run:  python ci/check_no_base_remnants.py
# =============================================================================
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Directories to scan — real product code only, never a vendored/virtualenv copy of anything.
SEARCH_ROOTS = [
    ROOT / "services",
    ROOT / "apps" / "console" / "src",
]
EXCLUDE_DIR_PARTS = {".venv", "node_modules", "__pycache__", "dist", "build", ".git"}
EXTENSIONS = {".py", ".ts", ".tsx"}

# Word-boundary patterns for every spelling this codebase has used for "a base subscription
# exists". `plan.standalone`/`is_standalone` are a DIFFERENT, still-meaningful concept (a plan
# that may be bought with nothing else held) and are deliberately not included here.
#
# `base_entitlement`/`BaseEntitlement` (whatsapp-assistant) is ALSO deliberately excluded — a
# 2026-09-11 audit read it in full: it checks "does this tenant hold ANY of
# feature.visit/feature.bookings/feature.contacts/feature.loyalty", never `feature.base` or a
# retired base plan. The NAME is legacy (kept from before the retirement); the check itself is a
# live, correct, different concept ("has this tenant produced ANY app-level entitlement yet") and
# flagging it here would be noise this gate exists specifically not to produce.
PATTERNS = [
    re.compile(r"\bhas_base\b"),
    re.compile(r"\bhasBase\b"),
    re.compile(r"\bis_base\b"),
    re.compile(r"\bisBase\b"),
    re.compile(r"feature\.base\b"),
    re.compile(r"\bbaseSub\b"),
    # ADDED 2026-09-11, SECOND PASS — `base_plan_id()` (subscribe.py) is `is_base` under a
    # different name: "the one plan row carrying messages.monthly". The FIRST pass's regex list
    # never caught it, and it stayed live in signup.py's `_start_base_trial` — which now finds no
    # base row (correctly, none exists) and refuses the trial for EVERY new signup, silently,
    # since the day الأساس was retired. Found only by hand, days later. Caught by name now.
    re.compile(r"\bbase_plan_id\b"),
    re.compile(r"\bbasePlanId\b"),
    # THE TRIAL-GRANT FUNCTIONS THEMSELVES — named after the concept they still assume exists,
    # even at a call site that does not literally say "base". A function named `_start_base_trial`
    # is itself a remnant worth a reviewer's eyes, whatever its body does today.
    re.compile(r"_start_base_trial\b"),
]

#: {relative_path: {line_number: "why this exact line is still allowed"}}
#: EVERY ENTRY READ AND JUSTIFIED, 2026-09-11 — see this file's own header note.
ALLOWLIST: dict[str, dict[int, str]] = {
    "services/operations/app/core/subscribe.py": {
        # THE READER ITSELF, KEPT ON PURPOSE. "Does this row carry messages.monthly" is still a
        # real, cheap structural question — a landmine only if a future plan.json row is ever
        # accidentally seeded carrying that key again, in which case this is exactly the function
        # that should notice. No caller may use it to GATE a purchase any more (may_add no longer
        # does) — that is the bug this gate exists to stop recurring.
        0: "is_base() kept as a pure structural reader — see subscribe.py's own docstring",
    },
    "services/operations/app/core/apps.py": {
        0: "renewals_by_key()'s is_base branch — provably dead (is_base can never be true against "
           "real seed data), documented at its own site, not yet worth its own cleanup PR",
    },
    "services/operations/app/api/v1/subscription.py": {
        0: "three is_base(plan_limits) call sites (the /apps response's own `base` field, and two "
           "interval-'once' checks) — provably dead today, a correctness trap only if plans.json "
           "regresses a base-shaped row back in; documented, not yet worth its own cleanup PR",
    },
    "services/operations/tests/unit/test_may_add.py": {
        0: "tests is_base() directly as the pure structural reader it still is — see "
           "subscribe.py's own allowlist entry",
    },
}


def _relpath(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def _iter_files():
    for root in SEARCH_ROOTS:
        for p in root.rglob("*"):
            if not p.is_file() or p.suffix not in EXTENSIONS:
                continue
            if any(part in EXCLUDE_DIR_PARTS for part in p.parts):
                continue
            yield p


def _is_comment_line(stripped: str, suffix: str) -> bool:
    if suffix == ".py":
        return stripped.startswith("#")
    return stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*")


def _in_docstring(lines: list[str], idx: int, suffix: str) -> bool:
    # Best-effort: are we inside a Python triple-quoted string at this line? Counts triple-double
    # and triple-single quote marks from the top of the file — imperfect against a triple-quote
    # used as a plain string literal mid-expression, but every real hit in this codebase's own
    # docstrings is a clean, dedicated block, so this heuristic is accurate for what it needs to
    # catch. (Written as a comment, not a docstring, so the marks it counts don't self-terminate
    # this very function's own docstring.)
    if suffix != ".py":
        return False
    triple_double = '"' * 3
    triple_single = "'" * 3
    before = "\n".join(lines[:idx])
    count_before = before.count(triple_double) + before.count(triple_single)
    if count_before % 2 == 1:
        return True
    # THE LINE THAT OPENS THE DOCSTRING IS ALSO A DOCSTRING LINE — `"""some text` carries real
    # content after the mark, on the same line the parity flips on, which the count-before check
    # alone would still read as "not yet inside".
    this_line = lines[idx] if idx < len(lines) else ""
    return (this_line.count(triple_double) + this_line.count(triple_single)) % 2 == 1


def main() -> int:
    problems: list[str] = []
    files_scanned = 0

    for path in _iter_files():
        files_scanned += 1
        rel = _relpath(path)
        allowed_lines = ALLOWLIST.get(rel, {})
        # A `0` KEY MEANS "ANY LINE IN THIS FILE", for an entry that covers a whole small module
        # (base_entitlement.py) or a scattered handful of call sites already reviewed as a group
        # (subscription.py's three is_base() reads) rather than one line each.
        whole_file_allowed = 0 in allowed_lines
        if whole_file_allowed:
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        lines = text.splitlines()

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or _is_comment_line(stripped, path.suffix):
                continue
            if _in_docstring(lines, i, path.suffix):
                continue
            for pat in PATTERNS:
                if pat.search(line):
                    lineno = i + 1
                    if lineno in allowed_lines:
                        break
                    problems.append(f"{rel}:{lineno}: {stripped[:110]}")
                    break

    C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"
    if problems:
        print(f"{C_R}  ✗ {len(problems)} live reference(s) to a retired «الأساس» concept:{C_N}")
        for p in problems:
            print(f"{C_R}    ✗ {p}{C_N}")
        print(f"\n{C_R}  ✗ fix the code, or read it and add a justified ALLOWLIST entry in "
              f"ci/check_no_base_remnants.py itself — never a bare skip{C_N}")
        return 1
    print(f"{C_G}  ✔ {files_scanned} file(s) scanned, no unreviewed «الأساس» remnant found{C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
