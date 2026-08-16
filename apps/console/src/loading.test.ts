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

import { hasFailed, isLoading, isReady } from './loading';

describe('the three states of a fetched value', () => {
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

  it('a falsy value that arrived is ready', () => {
    // 0 and '' are answers too — a balance of zero is a balance.
    expect(isReady(0)).toBe(true);
    expect(isReady('')).toBe(true);
  });
});
