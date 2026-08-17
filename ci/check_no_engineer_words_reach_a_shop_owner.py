"""A sentence a shop owner reads must contain nothing only an engineer can act on.

WHAT THIS CAUGHT, VERBATIM, ON HIS DASHBOARD:

    نرجو إرسال حقل branch_id مع كل عملية في طلب تسجيل الزيارة.

Printed under a heading about data coverage, in a grey box, on «محلّي». The owner of a workshop
read «حقل», then one of our internal field names, then «طلب تسجيل الزيارة» — three terms he does
not have — and concluded, in his own words, «ماهي مناسبة لمستخدم بسيط ما راح يفهم شي».

The sentence was not a mistake. It was written to be FORWARDED to his POS vendor's engineer, and
it is exactly right for that reader. The defect was printing it in the body, where it reads as an
instruction to the owner — who cannot act on it in any way at all. It now sits behind a copy
button, which is what «for somebody else» looks like on a screen.

THE SHAPE, AND WHY IT NEEDS A STANDING CHECK. Nobody writes this on purpose. It happens when the
person writing the string is thinking about the system rather than the reader, which is the normal
state of mind while writing that code — and it is invisible in review for the same reason. The
words below are the ones that only ever appear when that has happened.

THE RULE, WITH NO EXCEPTIONS TABLE. The user-facing strings in the files below carry none of these
terms. A technical string that genuinely must exist — the message for a vendor's engineer — lives
in a field named for that purpose (`request`), and this check knows that field by name rather than
by an exemption for the file that holds it.

WHAT IT CANNOT SEE, said plainly:
  · a sentence that is jargon without using any of these words. «تعذّرت المزامنة مع المزوّد» is
    unhelpful and passes; no word list catches that, and a human review is the only thing that
    does;
  · strings in files this check does not read. The scope is named below by path, and it is the
    owner-facing surfaces — never a list of allowed offenders.

    python ci/check_no_engineer_words_reach_a_shop_owner.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

#: Where an owner's own words are written. Both sides: the service composes the sentence and the
#: screen prints it, and either one can be the place the jargon enters.
SURFACES = (
    "services/insights/app/core/coverage.py",
    "apps/console/src/screens/Local.tsx",
)

#: Terms that only ever reach a string when its author was thinking about the system rather than
#: about the person reading it. Deliberately short: every entry has been seen in front of an owner.
BANNED = (
    "branch_id", "subject_ref", "tenant_id", "template_type", "idempotency",
    "endpoint", "API", "JSON", "payload", "webhook", "timeout",
    "null", "None", "HTTP", "500", "422",
)

#: The one field whose whole purpose is to be forwarded to somebody else's engineer. It is allowed
#: to be technical — that is what it is for — and the screen keeps it behind a copy button.
FORWARDED_FIELD = re.compile(r'^\s*"request"\s*:')

#: WHAT COUNTS AS A SENTENCE HE READS. Not "a line containing Arabic" — the first version of this
#: check used that, and it flagged four lines that were perfectly fine: `r.branch_id ?? ''` beside
#: an Arabic label, and `: null}` at the end of a JSX conditional. A gate that cries wolf teaches
#: the reader to scroll past it, so the SCOPE narrows and the pattern does not: only the contents
#: of a string literal, or the text between JSX tags, is something a person reads.
ARABIC = re.compile(r"[؀-ۿ]")
QUOTED = re.compile(r"'([^']*)'" + r'|"([^"]*)"')
JSX_TEXT = re.compile(r">([^<>{}]+)<")
#: WHOLE WORDS ONLY, so «null» inside «annullment» is not a finding. Written as a scan rather
#: than as a regex escape on purpose: an earlier revision expressed the word boundary as an
#: escape, the escape was mangled into a control character on its way into the file, and the
#: resulting pattern matched nothing at all — a gate that reported OK because it could not fail.
#: Plain character tests cannot be corrupted that way, and they say the rule out loud.
WORD_CHARS = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_')


def mentions(text: str, word: str) -> bool:
    """True when `word` stands alone in `text` rather than sitting inside a longer word."""
    at = text.find(word)
    while at != -1:
        before = text[at - 1] if at else ' '
        end = at + len(word)
        after = text[end] if end < len(text) else ' '
        if before not in WORD_CHARS and after not in WORD_CHARS:
            return True
        at = text.find(word, at + 1)
    return False


def sentences(line: str) -> list[str]:
    """Every part of this line a human would read as prose."""
    out = [g for m in QUOTED.finditer(line) for g in m.groups() if g]
    out += [m.group(1) for m in JSX_TEXT.finditer(line)]
    return [s for s in out if ARABIC.search(s)]


def offending_lines(path: pathlib.Path) -> list[tuple[int, str, str]]:
    out: list[tuple[int, str, str]] = []
    forwarded = False
    in_block_comment = False
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        # COMMENTS ARE FOR US, NOT FOR HIM — including the continuation lines of a block, which is
        # how this file's own explanation of the banned words slipped through the first version.
        if in_block_comment:
            if "*/" in stripped:
                in_block_comment = False
            continue
        if stripped.startswith("/*") and "*/" not in stripped:
            in_block_comment = True
            continue
        if stripped.startswith(("#", "//", "*", '"""')):
            continue
        if FORWARDED_FIELD.match(line):
            # The forwarded message may wrap onto the next line; skip both.
            forwarded = True
            continue
        if forwarded:
            # ONLY A GENUINE CONTINUATION. The first version ended this skip on a line NOT ending
            # in a comma — and since `request` is the last key of each entry and every dict line
            # ends in a comma, that swallowed the whole rest of the file: the gate read one entry
            # and reported OK for all of them. A skip that never ends is the same defect as an
            # exceptions table, arrived at by accident.
            forwarded = stripped.endswith(("(", "+"))
            continue
        for text in sentences(line):
            for word in BANNED:
                if mentions(text, word):
                    out.append((n, word, text[:110]))
    return out


def main() -> int:
    problems: list[str] = []
    for rel in SURFACES:
        path = ROOT / rel
        if not path.is_file():
            # SILENCE IS NOT AGREEMENT. A missing surface makes this vacuous, and a check that
            # passes for having read nothing is the failure it exists to prevent.
            print(f"FAIL: {rel} is missing — this gate read nothing, which is not the same as "
                  f"finding nothing")
            return 1
        for n, word, text in offending_lines(path):
            problems.append(f"  {rel}:{n}: «{word}» in a sentence an owner reads\n      {text}")

    if problems:
        print(f"FAIL: {len(problems)} line(s) put an engineer's word in front of a shop owner:")
        for p in problems:
            print(p)
        print("\n  He cannot act on it. Say what he loses, why, and the one thing he can do — and "
              "if the technical line must exist, put it in `request`, which is forwarded to "
              "somebody else's engineer and never printed in the body.")
        return 1

    print(f"OK: {len(SURFACES)} owner-facing surface(s), no engineer's vocabulary in any of them")
    return 0


if __name__ == "__main__":
    sys.exit(main())
