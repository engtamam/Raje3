#!/usr/bin/env python3
"""Generate apps/mobile/lib/theme/app_colors.g.dart FROM the same source of
truth the web console already uses — config/product.json (brand.accent) and
ui/packages/ui/src/theme/theme.config.ts (the `light` palette).

WHY A GENERATOR, NOT A HAND COPY. apps/mobile/lib/theme/app_theme.dart used
to hand-copy every colour as a literal `Color(0xFF...)`, retyped once from
theme.config.ts/product.json. That is exactly the drift class
ci/check_a_hardcoded_color_does_not_shadow_a_token.py already exists to
catch on the WEB side (a CSS/TS file that snapshots a theme.config.ts hex
instead of reading the variable) — this script closes the same hole for the
mobile side, where there is no CSS variable to read at runtime and a Dart
`const Color(...)` genuinely has to be a literal. So instead of a human
retyping the literal, this script derives it, and
ci/check_mobile_theme_is_generated.py fails the build if the checked-in
generated file and this script's current output ever disagree.

HOW IT READS A TYPESCRIPT FILE FROM PYTHON. There is no existing non-TS
consumer of theme.config.ts's literal values in this repo (the tailwind
preset reads CSS custom properties at runtime, not the source file) — the
closest precedent is check_a_hardcoded_color_does_not_shadow_a_token.py,
which already regex-extracts the `light: Palette = { ... }` block to get at
its literal hex values. This script reuses that exact extraction technique
rather than inventing a TS parser or a Node toolchain for one file.
`config/product.json` is read the same way check_product_config.py already
reads it — plain `json.loads`, stdlib only.

SCOPE: colour tokens only (per the owner's own instruction) — not locales,
not the API contract. Those are separate, already-noted drift concerns in
apps/mobile/README.md.

Usage:
    python scripts/gen_mobile_theme.py            # writes the .g.dart file
    python scripts/gen_mobile_theme.py --check     # exits 1 if the file would change (no write)
    python scripts/gen_mobile_theme.py --print     # prints the generated content to stdout
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRODUCT_JSON = ROOT / "config" / "product.json"
THEME_CONFIG_TS = ROOT / "ui" / "packages" / "ui" / "src" / "theme" / "theme.config.ts"
OUTPUT = ROOT / "apps" / "mobile" / "lib" / "theme" / "app_colors.g.dart"

LIGHT_BLOCK_RE = re.compile(r"const light: Palette = \{(.*?)\n\};", re.DOTALL)
# Any quoted `'key': 'value',` line inside the light block — hex or an rgb(...) string
# (e.g. `overlay: 'rgb(22 19 40 / 0.45)'`). Expression-valued lines (the accent-derived
# fields, computed from ACCENT_LIGHT.* below) are NOT quoted in theme.config.ts, so this
# naturally skips them — they're computed separately from product.json instead.
PALETTE_LINE_RE = re.compile(r"^\s*'?([\w-]+)'?:\s*'([^']*)',?\s*$")

# theme.config.ts key -> Dart field name. Only the fields AppColors actually declares —
# same shape the reference-derived token class already had, just sourced now.
FIELD_MAP = {
    "surface-0": "surface0",
    "surface-1": "surface1",
    "surface-2": "surface2",
    "surface-3": "surface3",
    "text-primary": "textPrimary",
    "text-secondary": "textSecondary",
    "text-muted": "textMuted",
    "border-subtle": "borderSubtle",
    "border-strong": "borderStrong",
    "accent-contrast": "accentContrast",
    "success": "success",
    "success-soft": "successSoft",
    "success-on-soft": "successOnSoft",
    "warning": "warning",
    "warning-soft": "warningSoft",
    "warning-on-soft": "warningOnSoft",
    "danger": "danger",
    "danger-soft": "dangerSoft",
    "danger-on-soft": "dangerOnSoft",
    "danger-contrast": "dangerContrast",
    "info": "info",
    "info-soft": "infoSoft",
    "info-on-soft": "infoOnSoft",
}


def _hex_channels(hexstr: str) -> tuple[int, int, int]:
    h = hexstr.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def mix(frm: str, to: str, amount: float) -> str:
    """Same algorithm as theme.config.ts's own `mix()` — channels indexed from 0/2/4
    (not 1/3/5 — that off-by-one is the exact bug that file's own comment documents
    having shipped once already). Kept in lockstep on purpose: a second, independently
    "corrected" implementation is how two copies of the same formula quietly diverge."""
    r1, g1, b1 = _hex_channels(frm)
    r2, g2, b2 = _hex_channels(to)

    def m(a: int, b: int) -> str:
        return format(round(a + (b - a) * amount), "02x")

    return f"#{m(r1, r2)}{m(g1, g2)}{m(b1, b2)}"


def _dart_color(hexstr: str) -> str:
    h = hexstr.lstrip("#").lower()
    return f"Color(0xFF{h.upper()})"


def _overlay_to_argb(value: str) -> str:
    """theme.config.ts overlay is `rgb(r g b / a)` (CSS colour-4 syntax). Convert to a
    Flutter ARGB literal."""
    m = re.match(r"rgb\((\d+)\s+(\d+)\s+(\d+)\s*/\s*([\d.]+)\)", value)
    if not m:
        raise ValueError(f"unrecognized overlay colour format: {value!r}")
    r, g, b, a = int(m.group(1)), int(m.group(2)), int(m.group(3)), float(m.group(4))
    alpha = round(a * 255)
    return f"Color(0x{alpha:02X}{r:02X}{g:02X}{b:02X})"


def _extract_light_palette() -> dict[str, str]:
    text = THEME_CONFIG_TS.read_text(encoding="utf-8")
    m = LIGHT_BLOCK_RE.search(text)
    if not m:
        raise RuntimeError(
            f"could not find `const light: Palette = {{ ... }}` in {THEME_CONFIG_TS} — "
            "this generator needs re-pointing, not a hand-edit of its output"
        )
    values: dict[str, str] = {}
    for line in m.group(1).splitlines():
        lm = PALETTE_LINE_RE.match(line)
        if lm:
            values[lm.group(1)] = lm.group(2)
    return values


def _load_brand_accent() -> tuple[str, str]:
    data = json.loads(PRODUCT_JSON.read_text(encoding="utf-8"))
    accent = data["brand"]["accent"]
    return accent["light"], accent["dark"]


def generate() -> str:
    palette = _extract_light_palette()
    accent_light, _accent_dark = _load_brand_accent()

    accent_hex = accent_light
    accent_hover_hex = mix(accent_light, "#000000", 0.22)
    accent_soft_hex = mix(accent_light, "#ffffff", 0.88)
    accent_on_soft_hex = mix(accent_light, "#000000", 0.22)

    if "overlay" not in palette:
        raise RuntimeError("theme.config.ts light palette is missing 'overlay' — re-check the extraction")

    lines: list[str] = []
    lines.append("// GENERATED FILE — DO NOT EDIT BY HAND.")
    lines.append("//")
    lines.append("// Produced by scripts/gen_mobile_theme.py from:")
    lines.append("//   - config/product.json (brand.accent)")
    lines.append("//   - ui/packages/ui/src/theme/theme.config.ts (the `light` palette)")
    lines.append("//")
    lines.append("// Re-run `python scripts/gen_mobile_theme.py` after either source changes.")
    lines.append("// ci/check_mobile_theme_is_generated.py fails the build if this file drifts")
    lines.append("// from what the generator would currently produce.")
    lines.append("")
    lines.append("import 'package:flutter/material.dart';")
    lines.append("")
    lines.append("/// Colour tokens sourced from Raje3's own web design system —")
    lines.append("/// see the header of this file for exactly where each value comes from.")
    lines.append("class AppColors {")
    lines.append(f"  static const Color accent = {_dart_color(accent_hex)};")
    lines.append(f"  static const Color accentHover = {_dart_color(accent_hover_hex)};")
    lines.append(f"  static const Color accentSoft = {_dart_color(accent_soft_hex)};")
    lines.append(f"  static const Color accentOnSoft = {_dart_color(accent_on_soft_hex)};")
    lines.append(f"  static const Color accentContrast = {_dart_color(palette['accent-contrast'])};")
    lines.append("")

    def emit(comment: str, *keys: str) -> None:
        lines.append(f"  // {comment}")
        for key in keys:
            field = FIELD_MAP[key]
            lines.append(f"  static const Color {field} = {_dart_color(palette[key])};")
        lines.append("")

    emit("SURFACES", "surface-0", "surface-1", "surface-2", "surface-3")
    emit("TEXT", "text-primary", "text-secondary", "text-muted")
    emit("BORDERS", "border-subtle", "border-strong")
    emit("SUCCESS", "success", "success-soft", "success-on-soft")
    emit("WARNING", "warning", "warning-soft", "warning-on-soft")
    emit("DANGER", "danger", "danger-soft", "danger-on-soft", "danger-contrast")
    emit("INFO", "info", "info-soft", "info-on-soft")

    lines.append(f"  static const Color overlay = {_overlay_to_argb(palette['overlay'])};")
    lines.append("")
    lines.append("  // Convenience aliases matching common Material naming, so widgets that")
    lines.append("  // expect AppColors.primary/error/white keep working.")
    lines.append("  static const Color primary = accent;")
    lines.append("  static const Color error = danger;")
    lines.append("  static const Color white = Color(0xFFFFFFFF);")
    lines.append("  static const Color black = Color(0xFF000000);")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    content = generate()

    if "--print" in argv:
        print(content)
        return 0

    if "--check" in argv:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else None
        if current != content:
            print(f"{OUTPUT} is out of date with theme.config.ts/product.json — "
                  f"run `python scripts/gen_mobile_theme.py` and commit the result")
            return 1
        print(f"{OUTPUT} is up to date")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content, encoding="utf-8", newline="\n")
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
