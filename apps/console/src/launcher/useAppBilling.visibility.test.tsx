/**
 * `useAppBilling`'s own `visibleOverrideKeys` param (core/app_visibility.py's console half) — an
 * unlisted plan stays excluded from `plans`/`planByKey` by default, exactly like before this
 * param existed, and is included ONLY when its own feature key is in the override list.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useAppBilling } from './useAppBilling';

const PLAN_LISTED = {
  id: 'plan_visit', name: 'تسجيل زيارة', active: true, listed: true,
  prices: [{ interval: 'month', amount_minor: 0, currency: 'SAR' }],
  limits: { 'feature.visit': { kind: 'boolean', limit: 1 } },
};
const PLAN_UNLISTED = {
  id: 'plan_partner_loyalty', name: 'ولاء الشركاء', active: true, listed: false,
  prices: [{ interval: 'month', amount_minor: 0, currency: 'SAR' }],
  limits: { 'feature.partner_loyalty': { kind: 'boolean', limit: 1 } },
};

let plansResponse: unknown[] = [PLAN_LISTED, PLAN_UNLISTED];

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }) => {
      if (a.id === 'billing.plans') return { plans: plansResponse };
      if (a.id === 'billing.my_subscriptions') return { subscriptions: [] };
      if (a.id === 'subscription.payment_state') return { enabled: true };
      if (a.id === 'billing.discount_preview') return { previews: {}, potential: {} };
      return {};
    },
  };
});

const session = {} as never;
const catalog = { services: [], unreachable: [] } as never;

afterEach(() => {
  vi.clearAllMocks();
  plansResponse = [PLAN_LISTED, PLAN_UNLISTED];
});

// Same flush pattern as useAppBilling.cart.test.tsx's own `setUp()` — several chained promises
// resolve before `plans` settles (load() fires three parallel calls), so a single microtask flush
// is not enough.
async function setUp(overrideKeys?: string[]) {
  const { result } = renderHook(() => useAppBilling(session, catalog, overrideKeys));
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  return result;
}

describe('useAppBilling visibility overrides', () => {
  it('excludes an unlisted plan by default, same as before the param existed', async () => {
    const result = await setUp();
    expect(result.current.planByKey['feature.visit']).toBeTruthy();
    expect(result.current.planByKey['feature.partner_loyalty']).toBeUndefined();
  });

  it('includes an unlisted plan when its key is in visibleOverrideKeys', async () => {
    const result = await setUp(['feature.partner_loyalty']);
    expect(result.current.planByKey['feature.partner_loyalty']).toBeTruthy();
    expect(result.current.planByKey['feature.partner_loyalty'].id).toBe('plan_partner_loyalty');
  });

  it('an override for a DIFFERENT key never leaks visibility onto this one', async () => {
    const result = await setUp(['feature.some_other_app']);
    expect(result.current.planByKey['feature.partner_loyalty']).toBeUndefined();
  });

  it('still excludes an inactive plan even with a visibility override for it', async () => {
    plansResponse = [PLAN_LISTED, { ...PLAN_UNLISTED, active: false }];
    const result = await setUp(['feature.partner_loyalty']);
    expect(result.current.planByKey['feature.partner_loyalty']).toBeUndefined();
  });
});
