/**
 * What a plan ADDS — the only part a reader is actually choosing between.
 */
import { describe, expect, it } from 'vitest';
import { planDelta } from './Plans';

const plan = (name: string, limits: Record<string, { limit: number; kind?: string }>) =>
  ({ id: name, name, limits } as never);

describe('planDelta', () => {
    // THE KEYS ARE READ OUT OF LIMIT_WORDS, NOT GUESSED. My first version invented `seats`, and the
  // test failed against code that was correct — a name is not a detail here: an unknown key is
  // silently skipped, so a guessed one produces an empty list and a passing-looking screen.
  const basic = plan('الأساسية', { branches: { limit: 1 }, 'staff.seats': { limit: 5 } });
  const smart = plan('الذكية', { branches: { limit: 1 }, 'staff.seats': { limit: 12 } });

  it('keeps the whole list for the cheapest plan — nothing sits below it', () => {
    expect(planDelta(basic, undefined)).toHaveLength(2);
  });

  it('drops what is identical and keeps what grew', () => {
    const lines = planDelta(smart, basic);
    // The branch count is unchanged and stays quiet; the seats went 5 → 12 and must be said.
    expect(lines.some((l) => l.includes('12'))).toBe(true);
    expect(lines.some((l) => l.includes('فروع'))).toBe(false);
  });

  it('says nothing at all when a tier adds nothing — rather than repeating the one below', () => {
    expect(planDelta(basic, basic)).toEqual([]);
  });
});
