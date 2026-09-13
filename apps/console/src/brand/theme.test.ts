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
    expect(accent.toLowerCase()).toBe('#6a4cf5');
  });

  it('forces the light appearance — the field screen must never render dark', () => {
    applyRaje3();
    const surface0 = getComputedStyle(document.documentElement).getPropertyValue('--surface-0').trim();
    // The dark theme's ground is a near-black plum; light's is a clean near-white grey (rebranded
    // 2026-09-14, the owner's own instruction: white ground + violet accent, retiring the warm
    // paper cream from 2026-09-12). Cheap, reliable signal without importing the palette module
    // directly into a test that should watch the DOM.
    expect(surface0.toLowerCase()).toBe('#f7f8fa');
  });

  it('sets Arabic as the document direction', () => {
    applyRaje3();
    expect(document.documentElement.dir).toBe('rtl');
  });
});
