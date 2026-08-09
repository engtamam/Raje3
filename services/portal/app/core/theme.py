"""A readable palette from whatever colour a shop gives us.

PORTED FROM base-services' theme engine, NOT INVENTED. platform/ui/packages/ui/src/theme already
solves this — `relLuminance` picks ink that contrasts with any tint, `mix` derives the ramp the
built-in palette uses, and `applyTheme` emits the whole thing as CSS custom properties. This is the
same arithmetic in Python, because this page renders on the server and cannot run their TypeScript.

WHY NOT JUST USE THEIR REACT COMPONENTS. Because this page is opened from a WhatsApp message by
someone standing in a shop with one bar of signal, and a JavaScript bundle costs the first paint.
Their library is right for the owner's dashboard and our admin panel, where a person has already
decided to sit down and work. Here we take the TOKENS and the MATHS and leave the runtime.

THE PROBLEM THIS SOLVES. A shop supplies a brand colour. It might be near-white, near-black, a
saturated red, or a colour their designer picked for a printed sign under sunlight. Whatever it is,
the page must remain readable — and the failure we refuse is grey-on-grey rendered confidently and
called "their brand".

So: the accent is used where it can be, ink is chosen to contrast with it, and a colour that cannot
carry text simply does not get text on it. The shop's identity survives; the readability is not
negotiable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_HEX = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

# The product's own accent, used when a shop has not chosen one. Deep green: the colour of the
# product, not of any shop, and it is only ever seen by a shop that supplied nothing.
DEFAULT_ACCENT = "#0F5F4E"

# WCAG AA for normal text. Not a preference — 4.5:1 is the line below which a real person with
# ordinary eyesight in ordinary light stops being able to read comfortably.
MIN_CONTRAST = 4.5

# AND A SECOND THRESHOLD, for the accent against the PAGE rather than against its own text.
#
# The first version checked only readability and passed #F5F5F5: near-white with dark ink is
# 16:1, entirely readable — and completely invisible as a button on a white page. A shop would
# supply their pale brand colour, every control would vanish, and nothing would have failed.
#
# 3:1 is WCAG's threshold for non-text UI components, and it is the right one here: this is not
# about reading the label, it is about seeing that there is something to press.
MIN_UI_CONTRAST = 3.0


def _norm(hex_colour: str) -> str | None:
    """A hex string to six lowercase digits, or None if it is not a colour.

    None rather than a raise: this value comes from a shop's settings, and a page that 500s because
    somebody typed 'أخضر' into a colour field is a page that punishes a customer for an owner's
    typo.
    """
    m = _HEX.match((hex_colour or "").strip())
    if not m:
        return None
    v = m.group(1).lower()
    return "".join(c * 2 for c in v) if len(v) == 3 else v


def _rgb(hex6: str) -> tuple[int, int, int]:
    return int(hex6[0:2], 16), int(hex6[2:4], 16), int(hex6[4:6], 16)


def _channel(c: int) -> float:
    """One sRGB channel, linearised. The 0.03928 branch is the sRGB transfer curve, not a fudge —
    perceived brightness is not proportional to the byte value."""
    s = c / 255
    return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4


def luminance(hex_colour: str) -> float:
    """Relative luminance, 0 (black) to 1 (white). The same function as their `relLuminance`."""
    h = _norm(hex_colour) or "000000"
    r, g, b = (_channel(c) for c in _rgb(h))
    # The coefficients are the human eye's sensitivity per channel — green carries most of the
    # perceived brightness, which is why a saturated blue looks dark and a saturated yellow does
    # not, at the same "value".
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    """The WCAG contrast ratio between two colours, 1 (identical) to 21 (black on white)."""
    la, lb = luminance(a), luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def mix(from_hex: str, to_hex: str, amount: float) -> str:
    """Blend toward `to_hex`. Mirrors their `mix`, so a shop's accent derives its ramp exactly the
    way the built-in palette does — a page that mixed differently would look like a different
    product wearing the same tokens."""
    f = _norm(from_hex) or "000000"
    t = _norm(to_hex) or "ffffff"
    fr, fg, fb = _rgb(f)
    tr, tg, tb = _rgb(t)
    amount = max(0.0, min(1.0, amount))
    out = tuple(round(a + (b - a) * amount) for a, b in ((fr, tr), (fg, tg), (fb, tb)))
    return "#%02x%02x%02x" % out


def ink_for(background: str) -> str:
    """Text that can be read on this background — dark ink on a light tint, light on a dark one.

    Near-black and near-white rather than pure: pure black on a colour is harsh and reads as a
    rendering error, and pure white on a mid tone glares. These two are what their palette uses.
    """
    return "#111827" if luminance(background) > 0.45 else "#F9FAFB"


@dataclass(frozen=True)
class Theme:
    accent: str
    accent_ink: str
    accent_soft: str
    accent_soft_ink: str
    surface: str
    surface_2: str
    text: str
    text_muted: str
    border: str
    # Whether the shop's own colour survived. False means it could not carry text at any usable
    # ink and we fell back — surfaced rather than hidden so the console can TELL the owner instead
    # of quietly ignoring what they chose.
    brand_applied: bool

    def css_variables(self) -> str:
        """The theme as CSS custom properties, the same shape their `applyTheme` emits."""
        return "".join(f"--{k}:{v};" for k, v in (
            ("accent", self.accent), ("accent-ink", self.accent_ink),
            ("accent-soft", self.accent_soft), ("accent-soft-ink", self.accent_soft_ink),
            ("surface", self.surface), ("surface-2", self.surface_2),
            ("text", self.text), ("text-muted", self.text_muted), ("border", self.border)))


def build_theme(brand_colour: str | None) -> Theme:
    """Derive the page's palette from a shop's brand colour.

    THE ACCENT IS A BACKGROUND FOR TEXT, so the test is whether SOME ink reads on it — not whether
    it is pretty. A colour that fails that test is not rendered as a text background at all; the
    shop keeps its colour on the accents that carry no words, and the page stays readable.
    """
    accent = _norm(brand_colour or "") or _norm(DEFAULT_ACCENT)
    accent = f"#{accent}"
    surface = "#ffffff"
    ink = ink_for(accent)
    # TWO TESTS, AND BOTH MUST PASS. Can its own label be read on it, and can it be SEEN against
    # the page? A colour can pass either alone: near-white passes the first and fails the second.
    applied = (bool(_norm(brand_colour or ""))
               and contrast(accent, ink) >= MIN_CONTRAST
               and contrast(accent, surface) >= MIN_UI_CONTRAST)

    if not applied:
        # THE ADJUSTMENT. Darken toward black in steps until both tests pass. The HUE IS THEIRS
        # throughout — we are moving along their colour, not replacing it — and a shop that gave
        # us pale mint gets deep mint rather than our green.
        candidate = accent
        for step in (0.15, 0.3, 0.45, 0.6, 0.75, 0.85):
            candidate = mix(accent, "#000000", step)
            if (contrast(candidate, ink_for(candidate)) >= MIN_CONTRAST
                    and contrast(candidate, surface) >= MIN_UI_CONTRAST):
                break
        accent = candidate
        ink = ink_for(accent)

    # A 12% tint of the accent on white: the surface for a quiet panel that should still feel like
    # the shop's. Its ink is computed the same way rather than assumed dark — a near-black brand
    # produces a tint that is still dark.
    soft = mix(accent, "#ffffff", 0.88)
    return Theme(
        accent=accent,
        accent_ink=ink,
        accent_soft=soft,
        accent_soft_ink=ink_for(soft),
        surface=surface,
        surface_2="#F7F8F9",
        text="#111827",
        text_muted="#6B7280",
        border="#E5E7EB",
        brand_applied=applied)
