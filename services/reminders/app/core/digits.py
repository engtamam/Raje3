"""Arabic-Indic digits folded to Western ones, at every edge a person types on.

WHY THIS IS A MODULE AND NOT A LINE IN EACH CALLER. A keyboard set to Arabic produces ٠٥٠١٢٣٤٥٦٧
and the man typing does not think about it — he has typed his own phone number. Every value a
person hands us can arrive in either script, and the two must fold to one BEFORE anything compares,
stores or looks it up. `plate.py` learned this early and did it in its own file; `operations.py`
did not, and paid for it:

  * `_normalise_phone` filtered with `str.isdigit()`, which answers True for ٥ — so the digits
    survived in Arabic form, `startswith("966")` missed, `lstrip("0")` missed, and the number was
    stored as typed. The same person on two keyboards became TWO customers, which is the exact
    outcome that function's own docstring exists to prevent.

`str.isdigit()` IS THE TRAP, AND IT IS BANNED HERE. It is true for every decimal digit in Unicode,
so in an Arabic-market product it never means what the person writing it meant. It reads as «is
this 0-9» and answers «is this a digit in any script» —
`ci/check_a_digit_from_an_arabic_keyboard_is_still_a_digit.py` refuses it and points here.
"""
#: SHARED COPY — this module is pasted into every service, and its CODE must stay identical in
#: all of them. These are separate deployables with no package to share, so the copies are held
#: equal by `ci/check_a_module_copied_into_every_service_stays_one_module.py` rather than by
#: anybody remembering. Prose may differ; logic may not. Removing this line is itself a failure.
# arabic-indic-digits: intentional — this module converts them to 0-9, so it must name them.
from __future__ import annotations

#: ٠١٢٣٤٥٦٧٨٩ → 0123456789, and the Eastern-Arabic (Persian/Urdu) forms ۰۱۲۳۴۵۶۷۸۹ with them.
#: BOTH RANGES, because a phone sold in this market ships either keyboard and the person typing
#: cannot tell you which codepoint their thumb produced.
_FOLD = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

#: What «a digit» means everywhere in this product: exactly these ten characters.
WESTERN = "0123456789"


def western(text: str) -> str:
    """The same string with every Arabic-Indic or Eastern-Arabic digit in Western form."""
    return (text or "").translate(_FOLD)


def is_western_digit(ch: str) -> bool:
    """`str.isdigit()` said yes to ٥. This says what the caller meant."""
    return ch in WESTERN
