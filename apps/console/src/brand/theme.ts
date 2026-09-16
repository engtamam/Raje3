/**
 * راجِع's look — which is now OUR OWN palette, not the kit's default, and applied through the
 * kit's own mechanism rather than around it.
 *
 * THE HISTORY THIS FILE USED TO CARRY. Until 2026-08-22 this file pinned the accent to the kit's
 * default brand gold (`#B8862B`) and hand-corrected two derived tints, because
 * `platform/ui`'s own `mix()` stripped a `#` and then indexed as though it were still there —
 * `--accent-soft` landed on #f1ec0f, a highlighter yellow, worn as the active sidebar item all
 * day. That bug is fixed upstream now (theme.config.ts's `mix` indexes from zero correctly, and
 * `applyTheme` derives `--accent-on-soft` from the soft tint's own luminance), so the
 * hand-correction this file carried is gone — exactly as its own comment said it should be the
 * day the fix landed.
 *
 * AND THE BRAND ITSELF CHANGED. The warm-cream/gold "sealed document" identity was retired in
 * favor of a violet/teal/coral direction, built first on the shop
 * console's «محلّي» screen and then promoted to the platform theme
 * (platform/ui/…/theme.config.ts) and the product's own accent (config/product.json,
 * `brand.accent`) — the ONE place a rebrand belongs, per that file's own doc comment. This file
 * no longer overrides the accent at all: the kit's own theme, fed by our product config, already
 * carries the right colour.
 */
import { applyTheme } from '../../../../ui/packages/ui/src/theme';
import { applyDir } from '../../../../ui/packages/ui/src/i18n';

/**
 * LIGHT, AND THAT IS NOT A DEFAULT. A dark theme is unreadable on a tablet in an open workshop at
 * noon, which is where the field screen lives — and the owner's sections are on the same app, so
 * one appearance is one fewer thing to be wrong about. The owner's console may offer the toggle
 * later; the field screen must not.
 */
export function applyRaje3(): void {
  applyTheme('light');
  applyDir('ar');
}
