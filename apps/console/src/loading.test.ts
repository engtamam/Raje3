/**
 * The three states, pinned — because the whole of م · النمط 1 was two states pretending to be
 * three, in twenty-seven places at once.
 *
 * The screens are covered by the CI gate (`ci/check_loading_is_not_failure.py`), which fails the
 * build if any of them collapses «not yet» back into «it failed». This pins the vocabulary those
 * screens are written against: if `isLoading(null)` ever answered true, every failure sentence in
 * the app would go quiet again and no screen test would notice.
 */
import { describe, expect, it } from 'vitest';

import { DENIED, hasFailed, isDenied, isLoading, isReady } from './loading';

describe('the four states of a fetched value', () => {
  it('undefined is «not yet»', () => {
    expect(isLoading(undefined)).toBe(true);
    expect(hasFailed(undefined)).toBe(false);
    expect(isReady(undefined)).toBe(false);
  });

  it('null is «it failed» — never «still loading»', () => {
    // THE COLLAPSE ITSELF. `null` meant both, so the skeleton rendered for ever and the sentence
    // written for the failure was unreachable code.
    expect(isLoading(null)).toBe(false);
    expect(hasFailed(null)).toBe(true);
    expect(isReady(null)).toBe(false);
  });

  it('an EMPTY answer is still an answer', () => {
    // «لا يوجد عملاء بعد» is a fact about the shop. Reading empty as an outage is the other half
    // of this family (م · النمط 2) and would put an apology in front of a correct screen.
    expect(isReady([])).toBe(true);
    expect(hasFailed([])).toBe(false);
    expect(isLoading([])).toBe(false);
  });

  it('DENIED is «not yours to see» — never empty, never failed, never loading', () => {
    // THE FOURTH STATE (م · النمط 2). Eleven screens resolved a missing capability to `[]`, so a
    // question about his ROLE was answered with a fact about his SHOP: «لا يوجد عملاء بعد» to a
    // shop with three thousand, and «لا أحد متأخر» — a congratulation — to a supervisor who was
    // never allowed to ask.
    expect(isDenied(DENIED)).toBe(true);
    expect(isReady(DENIED)).toBe(false);
    expect(hasFailed(DENIED)).toBe(false);
    expect(isLoading(DENIED)).toBe(false);
  });

  it('an empty list is not denied', () => {
    // The other direction matters just as much: a shop that genuinely has nothing must still be
    // told so, rather than being told the section is not his.
    expect(isDenied([])).toBe(false);
    expect(isReady([])).toBe(true);
  });

  it('a falsy value that arrived is ready', () => {
    // 0 and '' are answers too — a balance of zero is a balance.
    expect(isReady(0)).toBe(true);
    expect(isReady('')).toBe(true);
  });
});
