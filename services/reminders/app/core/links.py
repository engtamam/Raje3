"""The customer's page as a customer can reach it: one absolute URL, built in one place.

WHY THIS FILE EXISTS. The page at `/p/{ref}` was built, served, tested and documented — and no
line in any service ever turned that path into an address. A customer holding a phone cannot tap
`/p/abc123`. So the retention story a shop buys, and the withdrawal tap PDPL requires be as easy as
granting, both depended on a URL nobody composed.

IT REFUSES RATHER THAN GUESSING. There is no default host here and there must never be one. A
guessed base sends every customer of every shop to somebody else's domain, or to a name that does
not resolve, and the failure is invisible from our side: the message is accepted, delivered, and
reports success. `raje3.sa` hardcoded as a fallback would be worse still — it would work in
production and silently misdirect every test and pilot install.

Not knowing our own address is a configuration fault at boot, not a per-message accident, and this
is the sentence an operator gets instead of a broken link.

THE REFERENCE IS THE CREDENTIAL. `/p/{ref}` is public by design: whoever holds the link opens the
page (portal/manifest.py). That makes the link itself a secret, which is why the portal strips its
own referrer — and why nothing here logs a composed URL.
"""
from __future__ import annotations

import re

# What a reference may contain. Not cosmetic: the reference lands in a URL, and a value carrying a
# slash or a query character would silently point somewhere else entirely — `abc/../admin` reaching
# a different path, or `abc?x=` swallowing what follows it. Refused rather than escaped, because a
# reference that needs escaping is not one we issued.
SAFE_REFERENCE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


class LinkError(Exception):
    """Raised instead of returning a link nobody can tap. Carries what to fix, in Arabic."""


def _base(public_base_url: str) -> str:
    base = (public_base_url or "").strip().rstrip("/")
    if not base:
        raise LinkError(
            "عنوان الموقع العام غير مضبوط (PUBLIC_BASE_URL) — لا تُرسَل رسالة برابطٍ لا يفتح.")
    if not base.startswith(("http://", "https://")):
        # A base without a scheme produces `raje3.sa/p/abc`, which WhatsApp renders as plain text
        # and no phone treats as a link.
        raise LinkError(f"عنوان الموقع العام «{base}» بلا http/https — لن يُقرأ كرابط.")
    return base


def _reference(reference: str) -> str:
    ref = (reference or "").strip()
    if not SAFE_REFERENCE.fullmatch(ref):
        raise LinkError("مُعرِّف صفحة العميل غير صالح — لا يُبنى رابطٌ من قيمةٍ لا نعرفها.")
    return ref


def customer_page(public_base_url: str, reference: str) -> str:
    """Where the customer reads their points, offers and history."""
    return f"{_base(public_base_url)}/p/{_reference(reference)}"


def stop_link(public_base_url: str, reference: str) -> str:
    """One tap to stop marketing — and it is a legal requirement, not a courtesy.

    Kept beside `customer_page` on purpose: the day somebody changes how a page URL is built, the
    withdrawal link must change with it. Two functions in one file cannot drift; two functions in
    two files did, everywhere this codebase has looked.
    """
    return f"{customer_page(public_base_url, reference)}/stop"
