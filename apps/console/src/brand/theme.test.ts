/**
 * The one colour rule this product cannot get wrong twice.
 *
 * The kit's own `mix` strips a `#` and then indexes as though it were still there, so every colour
 * derived from the brand gold came out wrong — `--accent-soft` landed on #f1ec0f, a highlighter
 * yellow, and wore it as the active item in the sidebar all day. Nothing we owned could fix it,
 * because the token itself was broken, and nothing failed: a wrong colour is not an exception.
 *
 * This is the assertion that would have caught it in a second, and the one that catches it coming
 * back the day the upstream fix lands and somebody deletes our correction along with it.
 */
import { describe, expect, it } from 'vitest';

import { softTint, onSoftInk } from './theme';

describe('the derived brand colours', () => {
  it('mixes from the right bytes — the kit reads the blue channel of white as 15', () => {
    // White is #ffffff. Any mix TOWARDS it must move every channel towards 255, never towards 15.
    expect(softTint()).toBe('#f6f0e6');
    // The broken value, named so a future reader knows exactly what regressed.
    expect(softTint()).not.toBe('#f1ec0f');
  });

  it('keeps the ink dark enough to read on that sand', () => {
    const ink = onSoftInk();
    const luminance = [1, 3, 5].map((i) => parseInt(ink.slice(i, i + 2), 16))
      .reduce((a, c) => a + c, 0) / 3;
    // A tablet on a workbench at noon: pale ink on a pale tint is the failure this guards.
    expect(luminance).toBeLessThan(120);
  });
});
