"""What counts as a plate — the smallest rule that still means something.

A TYRE SHOP THAT RECORDS A VISIT WITHOUT A PLATE HAS RECORDED HALF A VISIT. The vehicle is the
asset the whole sector turns on: the cycle is the car's, not the owner's (§13.2), the next reminder
is «سيارتك» and the screen finds the customer by plate before it finds him by phone. A row with no
plate cannot be found again by the one thing the counter searches by, and the owner discovers this
months later when a returning customer is invisible.

SO IT IS REQUIRED — AND THE RULE STOPS THERE.

We do not validate the Saudi plate FORMAT, and that is a decision rather than an omission. The
official form is three Arabic letters and up to four digits, mirrored into Latin; but the counter
sees temporary plates, transit plates, Gulf plates, diplomatic plates, a trailer's plate, and a car
whose plate is being replaced that week. A format check rejects every one of those, and the man
holding the phone with a customer waiting does not file a bug — he types «1» and moves on. That is
worse than no rule, because now the field is required AND meaningless.

WHAT WE ASK IS THAT IT LOOK LIKE A PLATE AT ALL: at least one letter and at least one digit. It
catches the two ways the field actually gets abused — a row of dashes, and a phone number typed
into the wrong box — and it accepts every real plate we could find, in either script.

ARABIC-INDIC DIGITS COUNT AS DIGITS. A keyboard set to Arabic produces ٤٥٦ and the man typing does
not know or care; refusing it would be our own defect wearing the shape of a rule. They are
normalised to Western digits on the way in, once, here — because a plate stored twice in two
scripts is a car nobody can find.
"""
# arabic-indic-digits: intentional — this module converts them to 0-9, so it must name them.
from __future__ import annotations

# ٠١٢٣٤٥٦٧٨٩ → 0123456789. Done at the edge so everything downstream — search, comparison, the
# message that prints the plate back to the customer — sees one form and only one.
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٠", "01234567890")


def normalise(plate: str) -> str:
    """Trim, collapse inner runs of space, and put every digit into Western form."""
    return " ".join((plate or "").translate(_ARABIC_DIGITS).split())


def is_plausible(plate: str) -> bool:
    """One letter and one digit, in any script, anywhere in the string."""
    text = normalise(plate)
    if not text:
        return False
    has_digit = any(ch.isdigit() for ch in text)
    # `isalpha` is unicode-aware, so Arabic letters answer True without a range of our own — and a
    # hand-written range is how the Persian ی or a stray tatweel becomes a rejected plate.
    has_letter = any(ch.isalpha() for ch in text)
    return has_digit and has_letter


REFUSAL = (
    "رقم اللوحة مطلوب لتسجيل الزيارة — أدخل حرفاً واحداً ورقماً واحداً على الأقل "
    "(مثال: ا ب ج 1234)."
)
