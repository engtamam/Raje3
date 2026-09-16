/**
 * The one colour rule this product cannot get wrong twice — now aimed at what actually ships.
 *
 * The old version of this file asserted two hand-corrected values because `platform/ui`'s `mix()`
 * used to strip a `#` and then index as though it were still there, turning the brand accent's
 * derived soft tint into a highlighter yellow. That bug is fixed upstream now, and this file's own
 * correction went with it — so the thing worth asserting has changed: not "did our patch compute
 * the right bytes", but "does applying راجِع's theme actually set the real brand accent on the
 * page", so a future regression (a stray override, a stale patch resurrected) fails here first.
 */
import { describe, expect, it } from 'vitest';

import { applyRaje3 } from './theme';

describe('راجِع theme', () => {
  it('applies the real product accent — violet, not a leftover gold', () => {
    applyRaje3();
    const accent = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim();
    // config/product.json's own `brand.accent.light` — the ONE place this colour is authored.
    expect(accent.toLowerCase()).toBe('#7c3aed');
  });

  it('forces the light appearance — the field screen must never render dark', () => {
    applyRaje3();
    const surface0 = getComputedStyle(document.documentElement).getPropertyValue('--surface-0').trim();
    // The dark theme's ground is a near-black plum; light's is a clean, glossy pure white
    // (rebranded 2026-09-16, second pass same day — the first pass's violet-tinted grey still
    // read "ممل", so the page itself went fully white, with `shadow`/`card-sheen` doing the lift a
    // tinted ground used to). Cheap, reliable signal without importing the palette module
    // directly into a test that should watch the DOM.
    expect(surface0.toLowerCase()).toBe('#ffffff');
  });

  it('sets Arabic as the document direction', () => {
    applyRaje3();
    expect(document.documentElement.dir).toBe('rtl');
  });
});
