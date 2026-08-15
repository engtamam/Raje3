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

/**
 * WHICH DOOR THE PURCHASE GOES THROUGH — asserted on the source, because it is the kind of line
 * that reads correctly and does the wrong thing.
 *
 * THE DEFECT. The screen called `billing.subscribe`, which is billing-service's OWN route: the
 * platform's, shared by every product built on it, and knowing nothing about WhatsApp. Ours —
 * `subscription.activate` — is the only path that enforces «لا اشتراك مدفوع قبل ربط واتساب»
 * (§6.2.1). The gate was written, tested, and standing on a road nobody drove down: a shop could
 * buy the top plan and then discover it cannot send a single message.
 */
describe('the purchase path', () => {
  it('prefers our own subscribe route over billing’s raw one', async () => {
    // THE SOURCE ITSELF, through vite's `?raw` — no node APIs, so this runs exactly the same way
    // the app is built. An import that stopped resolving would fail the test rather than read an
    // empty string, so this cannot pass by finding nothing.
    const mod = await import('./Plans.tsx?raw');
    const src = mod.default;
    expect(src.length).toBeGreaterThan(0);
    const ours = src.indexOf("'subscription.activate'");
    const theirs = src.indexOf("'billing.subscribe'");
    expect(ours).toBeGreaterThan(-1);
    // Ours is read FIRST; theirs may remain only as the fallback after it.
    expect(theirs === -1 || ours < theirs).toBe(true);
  });
});
