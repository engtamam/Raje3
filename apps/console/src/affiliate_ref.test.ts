/**
 * `?aff=` — the one value on the shop's own door that never comes from the owner typing anything.
 */
import { afterEach, describe, expect, it } from 'vitest';
import { affiliateRefFromUrl } from './auth';

afterEach(() => window.history.replaceState({}, '', '/'));

describe('affiliateRefFromUrl', () => {
  it('reads the id off ?aff=', () => {
    window.history.replaceState({}, '', '/?aff=aff-abc123');
    expect(affiliateRefFromUrl()).toBe('aff-abc123');
  });

  it('is empty when nobody arrived on a marketer link', () => {
    window.history.replaceState({}, '', '/');
    expect(affiliateRefFromUrl()).toBe('');
  });
});
