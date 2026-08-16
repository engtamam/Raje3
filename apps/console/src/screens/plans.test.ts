/**
 * The store groups by WHAT A ROW GRANTS — never by its name, and never by its place in a list.
 *
 * WHAT THIS REPLACES. The screen was a ladder of four tiers and its test checked `planDelta`, the
 * function that printed «كل ما في الأساسية +». There is no ladder now: a base, apps bought one by
 * one, and capacity packs. The grouping is the whole screen, so it is what gets tested.
 *
 * AND IT IS READ OFF THE LIMITS. A name would put the price list in two places, and the copy in
 * code is the one that goes stale the day marketing renames a row.
 */
import { describe, expect, it } from 'vitest';
import { appKey, canBuy, kindOf, type Plan } from './Plans';

const plan = (name: string, limits: Record<string, { kind?: string; limit: number }>) =>
  ({ id: name, name, limits } as Plan);

const BASE = plan('الأساس', {
  'messages.monthly': { kind: 'counter', limit: -1 },
  'staff.seats': { kind: 'gauge', limit: 5 },
  'feature.campaigns': { kind: 'boolean', limit: 0 },
});
const CAMPAIGNS = plan('الحملات', {
  'feature.campaigns': { kind: 'boolean', limit: 1 },
  'templates.custom': { kind: 'counter', limit: 1 },
});
const SEATS = plan('10 مقاعد إضافية', { 'staff.seats': { kind: 'gauge', limit: 10 } });

describe('kindOf', () => {
  it('knows the base by the METER it carries, not by its name', () => {
    // `messages.monthly` is the one key an app may never repeat, so carrying it and being a whole
    // subscription are the same fact — and it is the same field operations decides from.
    expect(kindOf(BASE)).toBe('base');
  });

  it('does not read a declared zero as a grant', () => {
    // THE TRAP IN THE DATA. The base carries every app at 0 so no screen has to tell «not bought»
    // from «never heard of» — read as grants, the base would be filed as an app too.
    expect(kindOf(BASE)).not.toBe('app');
  });

  it('knows an app by the one feature it turns on', () => {
    expect(kindOf(CAMPAIGNS)).toBe('app');
  });

  it('files a row that grants no feature as capacity', () => {
    expect(kindOf(SEATS)).toBe('capacity');
  });

  it('files a row with no limits at all as capacity rather than crashing', () => {
    expect(kindOf({ id: 'x', name: 'x' } as Plan)).toBe('capacity');
  });
});

describe('appKey', () => {
  it('names the key the card asks `owned` about', () => {
    expect(appKey(CAMPAIGNS)).toBe('feature.campaigns');
  });

  it('is empty for capacity, which is bought again rather than owned', () => {
    expect(appKey(SEATS)).toBe('');
  });
});


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

// --- د-15 · a button that could never buy ------------------------------------------------------

describe('canBuy', () => {
  it('does not offer a purchase this browser cannot pay for', () => {
    // THE DEFECT. The screen posted `{ plan_id }` and nothing else, and `subscription.activate`
    // decides `paid = bool(payment_token)` — so every paid row was drawn as a live button and
    // answered 402 on press. Only the base got through, and only because its 14-day trial skips
    // the payment check entirely, which is why nobody noticed.
    expect(canBuy({ hasAction: true, gatewayEnabled: true, canMint: false })).toBe(false);
  });

  it('does not offer a purchase with no gateway behind it', () => {
    expect(canBuy({ hasAction: true, gatewayEnabled: false, canMint: true })).toBe(false);
  });

  it('does not offer a purchase his role cannot make', () => {
    expect(canBuy({ hasAction: false, gatewayEnabled: true, canMint: true })).toBe(false);
  });

  it('offers it when all three are true', () => {
    // The day the card form lands, this is the only combination that changes — and it changes in
    // `payment.ts`, not here.
    expect(canBuy({ hasAction: true, gatewayEnabled: true, canMint: true })).toBe(true);
  });
});
