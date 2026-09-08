"""No name, no authorship-timestamp, in a comment — see the house rule this enforces (memory:
لا اسم وتاريخ بالتعليقات): "التعليق يشرح السبب، لا مين طلبه ومتى" — a comment explains WHY, never
WHO asked or WHEN. A comment that says "قرار تمام" or "(2026-09-08)" is a fact that rots the moment
the person leaves or the date passes — the reasoning it was attached to stays true either way, so
the byline never belonged there.

WHAT THIS CATCHES, ONLY THIS:

  1. The owner's name — "تمام" (Arabic, exact word — NOT "تماماً"/"إتمام", ordinary Arabic words
     that happen to contain the same letters) or "Tamam"/"tamam"/"TAMAM" (Latin, any case) — inside
     a COMMENT. The same word inside a STRING LITERAL is not scanned: "تمام" is also the ordinary
     Arabic word for "done/OK" and appears throughout the product as real UI copy (a button's own
     label, an AI reply fixture) — flagging every one of those would bury the real findings under
     noise nobody could triage. A comment has no such excuse; nothing user-facing is ever a comment.

  2. An authorship-timestamp shaped date — "(2026-09-08" or similar: an ISO date immediately after
     an opening paren, the exact shape this session's own comments kept reaching for ("(2026-09-08
     fix...)", "(found live, 2026-09-08)"). Deliberately narrow, not "any date in a comment": a
     comment legitimately names an external fact's own date all the time (Meta retiring an API
     version, a retention window) — those read as prose ("Meta retires v2 on 15 October 2026"),
     never as "(YYYY-MM-DD" bracketing the sentence like a byline. A blind date regex would flag
     every one of those true, useful facts as if they were a stamp — this pattern does not.

WHAT IT DOES NOT DO: parse comments with full language-aware precision. A `#`/`//` line comment and
a `/* ... */` block comment are both matched by a regex, not a real tokenizer — a `#` or `//`
sequence inside a string literal earlier on the same line could, in principle, be misread as the
start of a comment. Accepted: the alternative is a per-language parser for five languages, and every
real finding this gate has ever produced came from an actual comment.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# extension -> comment-line-prefix regex (line comments) and block-comment regex, or None.
#
# re.MULTILINE ON EVERY LINE PATTERN, NOT OPTIONAL. Without it `$` anchors to the end of the
# WHOLE FILE, not each line — so `#(.*)$` against a multi-line file matches (at most) one line
# near the very end, and every earlier `#` comment is silently never scanned at all. Found live:
# this gate's own first run said guards.yml was clean while a `#` comment three lines below the
# one it did catch carried the exact date-in-parens shape it exists to catch.
LANG = {
    ".py": {"line": re.compile(r"#(.*)$", re.M), "block": None},
    ".sh": {"line": re.compile(r"#(.*)$", re.M), "block": None},
    ".yaml": {"line": re.compile(r"#(.*)$", re.M), "block": None},
    ".yml": {"line": re.compile(r"#(.*)$", re.M), "block": None},
    ".ts": {"line": re.compile(r"//(.*)$", re.M), "block": re.compile(r"/\*(.*?)\*/", re.S)},
    ".tsx": {"line": re.compile(r"//(.*)$", re.M), "block": re.compile(r"/\*(.*?)\*/", re.S)},
    ".js": {"line": re.compile(r"//(.*)$", re.M), "block": re.compile(r"/\*(.*?)\*/", re.S)},
    ".jsx": {"line": re.compile(r"//(.*)$", re.M), "block": re.compile(r"/\*(.*?)\*/", re.S)},
}

# "تمام" as its own word — a following alif-family letter (ا أ إ آ), ة/ه, or an Arabic diacritic
# (تمامًا — tanwin fatha spelled as a combining mark right on the م, found live) turns it into a
# DIFFERENT word (تماماً/تمامًا, "completely") and a preceding إ makes it إتمام ("completion"), a
# real, unrelated, very common word in this codebase.
NAME_AR = re.compile(r"(?<![\wإ])تمام(?![\wاأإآةهً-ْ])")
NAME_LATIN = re.compile(r"\btamam\b", re.IGNORECASE)
# An opening paren directly followed by an ISO-ish date — the exact shape a byline takes here,
# not "any date anywhere in a comment" (see module docstring).
AUTHORSHIP_DATE = re.compile(r"\(\s*20\d{2}-\d{2}-\d{2}")


def comment_spans(text: str, ext: str) -> list[str]:
    """Every comment's own text (the part after # or // on a line, or between /* */), never the
    surrounding code — so a name or date inside a string literal is not this gate's business."""
    spec = LANG[ext]
    spans: list[str] = []
    if spec["block"] is not None:
        spans.extend(m.group(1) for m in spec["block"].finditer(text))
        text = spec["block"].sub("", text)  # do not re-match a block comment's own // inside it
    spans.extend(m.group(1) for m in spec["line"].finditer(text))
    return spans


def candidate_files() -> list[pathlib.Path]:
    """`git ls-files`, not a filesystem walk — git already knows exactly which files are ours
    (tracked, or untracked-but-not-.gitignore'd) and answers near-instantly no matter how large a
    dependency tree (node_modules, a stray local .venv-test never even added to .gitignore) sits
    next to it, because it reads its own index/exclude rules rather than touching every directory
    on disk. `-co --exclude-standard`: tracked files (`-c`) PLUS untracked ones respecting
    .gitignore (`-o --exclude-standard`) — a brand-new file not yet committed still gets checked."""
    out = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-co", "--exclude-standard"],
        capture_output=True, text=True, check=True).stdout.splitlines()
    # This file itself is exempt: a rule that describes the forbidden word must be able to name
    # that word, in full, in its own spec — see the module docstring and NAME_AR's own comment
    # just above, both of which quote "تمام" as the literal pattern being detected.
    self_path = pathlib.Path(__file__).resolve()
    return [ROOT / rel for rel in out
           if pathlib.PurePosixPath(rel).suffix in LANG
           and not rel.endswith((".test.ts", ".test.tsx", ".test.js"))
           and (ROOT / rel).resolve() != self_path]


def main() -> int:
    violations: list[str] = []

    for path in candidate_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        for span in comment_spans(text, path.suffix):
            rel = path.relative_to(ROOT)
            if NAME_AR.search(span) or NAME_LATIN.search(span):
                snippet = span.strip()[:100]
                violations.append(f"{rel} — names the owner in a comment: {snippet!r}")
            if AUTHORSHIP_DATE.search(span):
                snippet = span.strip()[:100]
                violations.append(f"{rel} — an authorship-timestamp-shaped date in a comment: {snippet!r}")

    if violations:
        print(f"  ✗ {len(violations)} name/date-in-comment finding(s):")
        for v in sorted(set(violations)):
            print(f"      · {v}")
        return 1

    print("  ✔ no comment names the owner or carries an authorship-timestamp-shaped date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
