/**
 * `feature.rating`'s own line under a plan card — SOLD_UNBUILT (ci/check_entitlements.py), the
 * plan itself is `listed: false`, but the wording has to exist NOW so it is ready the day the
 * plan flips — same discipline `feature.bookings` followed while its own stages were in progress.
 */
import { describe, expect, it } from 'vitest';
import { planLines, type Plan } from './billingShared';

function plan(limits: Plan['limits']): Plan {
  return { id: 'p1', name: 'التقييم', limits };
}

describe('feature.rating wording', () => {
  it('renders a real Arabic sentence, not the raw machine key', () => {
    const lines = planLines(plan({ 'feature.rating': { kind: 'boolean', limit: 1 } }));
    expect(lines).toContain('تقييم العملاء بعد الزيارة');
    expect(lines.some((l) => l.includes('feature.rating'))).toBe(false);
  });

  it('is omitted, not printed as «لا», when the plan does not grant it', () => {
    const lines = planLines(plan({ 'feature.rating': { kind: 'boolean', limit: 0 } }));
    expect(lines).toHaveLength(0);
  });

  it('is omitted entirely when the key is absent from a plan\'s limits', () => {
    const lines = planLines(plan({}));
    expect(lines).toHaveLength(0);
  });
});
