/**
 * The cart half of `useAppBilling` — adding/removing an app, the auto-add of an unmet
 * `plan.requires_any` dependency (the owner's own instruction: never a text-only suggestion,
 * the dependency travels in the same cart), and `finishCheckout`'s own success/failure handling.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useAppBilling } from './useAppBilling';

vi.mock('../payment', () => ({ canMintToken: true, confirmToken: vi.fn(), tokenizeCard: vi.fn() }));

const PLAN_VISIT = {
  id: 'plan_visit', name: 'تسجيل زيارة', active: true,
  prices: [{ interval: 'month', amount_minor: 0, currency: 'SAR' }],
  limits: { 'feature.visit': { kind: 'boolean', limit: 1 } },
};
const PLAN_BOOKINGS = {
  id: 'plan_bookings', name: 'الحجوزات', active: true,
  prices: [{ interval: 'month', amount_minor: 0, currency: 'SAR' }],
  limits: { 'feature.bookings': { kind: 'boolean', limit: 1 } },
};
const PLAN_LOYALTY = {
  id: 'plan_loyalty', name: 'نقاطي', active: true,
  prices: [{ interval: 'month', amount_minor: 9900, currency: 'SAR' }],
  limits: {
    'feature.loyalty': { kind: 'boolean', limit: 1 },
    'plan.requires_any': { kind: 'list', list: ['feature.visit', 'feature.bookings'] },
  },
};
const PLAN_CAMPAIGNS = {
  id: 'plan_campaigns', name: 'الحملات', active: true,
  prices: [{ interval: 'month', amount_minor: 4900, currency: 'SAR' }],
  limits: { 'feature.campaigns': { kind: 'boolean', limit: 1 } },
};

let checkoutCalls: unknown[] = [];
let checkoutShouldThrow: Error | null = null;
let heldSubs: unknown[] = [];

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }, body?: unknown) => {
      if (a.id === 'billing.plans') {
        return { plans: [PLAN_VISIT, PLAN_BOOKINGS, PLAN_LOYALTY, PLAN_CAMPAIGNS] };
      }
      if (a.id === 'billing.my_subscriptions') return { subscriptions: heldSubs };
      if (a.id === 'subscription.payment_state') return { enabled: true };
      if (a.id === 'billing.discount_preview') return { previews: {}, potential: {} };
      if (a.id === 'subscription.checkout') {
        checkoutCalls.push(body);
        if (checkoutShouldThrow) throw checkoutShouldThrow;
        return { notice: '' };
      }
      return {};
    },
  };
});

const session = {} as never;
const catalog = { services: [], unreachable: [] } as never;

afterEach(() => {
  vi.clearAllMocks();
  checkoutCalls = [];
  checkoutShouldThrow = null;
  heldSubs = [];
});

async function setUp() {
  const { result } = renderHook(() => useAppBilling(session, catalog));
  // Several chained promises resolve before `pay`/`plans`/`subs` all settle (load() fires three
  // parallel calls, each `.then()`-ing into state) — a single microtask flush is not enough.
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  return result;
}

describe('toggleCart', () => {
  it('adds a plan with no dependency plainly', async () => {
    const result = await setUp();
    act(() => result.current.toggleCart(PLAN_CAMPAIGNS));
    expect(result.current.cart).toEqual(['plan_campaigns']);
  });

  it('removes a plan already in the cart', async () => {
    const result = await setUp();
    act(() => result.current.toggleCart(PLAN_CAMPAIGNS));
    act(() => result.current.toggleCart(PLAN_CAMPAIGNS));
    expect(result.current.cart).toEqual([]);
  });

  it('auto-adds a dependency when neither held nor already in the cart', async () => {
    const result = await setUp();
    act(() => result.current.toggleCart(PLAN_LOYALTY));
    expect(result.current.cart).toEqual(['plan_loyalty', 'plan_visit']);
    expect(result.current.cartNotice).toContain('تسجيل زيارة');
  });

  it('does not auto-add when the dependency is already in the cart', async () => {
    const result = await setUp();
    act(() => result.current.toggleCart(PLAN_BOOKINGS));
    act(() => result.current.toggleCart(PLAN_LOYALTY));
    expect(result.current.cart).toEqual(['plan_bookings', 'plan_loyalty']);
  });

  it('does not auto-add when the dependency is already held', async () => {
    heldSubs = [{ id: 'sub_1', plan_id: 'plan_visit', status: 'active' }];
    const result = await setUp();
    act(() => result.current.toggleCart(PLAN_LOYALTY));
    expect(result.current.cart).toEqual(['plan_loyalty']);
    expect(result.current.cartNotice).toBe('');
  });

  it('clears the notice on a plain toggle after an auto-add happened earlier', async () => {
    const result = await setUp();
    act(() => result.current.toggleCart(PLAN_LOYALTY));
    expect(result.current.cartNotice).not.toBe('');
    act(() => result.current.toggleCart(PLAN_CAMPAIGNS));
    expect(result.current.cartNotice).toBe('');
  });
});

describe('cartTotalMinor', () => {
  it('sums the monthly price of every plan in the cart', async () => {
    const result = await setUp();
    act(() => result.current.toggleCart(PLAN_CAMPAIGNS)); // 4900, no dependency
    expect(result.current.cartTotalMinor).toBe(4900);
  });

  it('free apps (auto-added dependencies included) contribute zero', async () => {
    const result = await setUp();
    act(() => result.current.toggleCart(PLAN_LOYALTY)); // 9900 + free plan_visit auto-added
    expect(result.current.cartTotalMinor).toBe(9900);
  });
});

describe('checkout / finishCheckout', () => {
  it('opens the card form with every cart plan id', async () => {
    const result = await setUp();
    act(() => result.current.toggleCart(PLAN_CAMPAIGNS));
    act(() => result.current.checkout());
    expect(result.current.cardFormPending).toEqual({ kind: 'checkout', planIds: ['plan_campaigns'] });
  });

  it('does nothing on an empty cart', async () => {
    const result = await setUp();
    act(() => result.current.checkout());
    expect(result.current.cardFormPending).toBeNull();
  });

  it('finishCheckout sends every item with a month interval and the token', async () => {
    const result = await setUp();
    act(() => result.current.toggleCart(PLAN_LOYALTY)); // + auto-added plan_visit
    await act(async () => { await result.current.finishCheckout(result.current.cart, 'tok_1'); });
    expect(checkoutCalls).toEqual([{
      items: [{ plan_id: 'plan_loyalty', interval: 'month' }, { plan_id: 'plan_visit', interval: 'month' }],
      payment_token: 'tok_1',
    }]);
  });

  it('clears the cart and the card form on success', async () => {
    const result = await setUp();
    act(() => result.current.toggleCart(PLAN_CAMPAIGNS));
    act(() => result.current.checkout());
    await act(async () => { await result.current.finishCheckout(['plan_campaigns'], 'tok_1'); });
    expect(result.current.cart).toEqual([]);
    expect(result.current.cardFormPending).toBeNull();
    expect(result.current.cartError).toBe('');
  });

  it('keeps the cart and surfaces the error on a refused checkout', async () => {
    checkoutShouldThrow = new Error('هذا التطبيق يحتاج تفعيل تسجيل زيارة أولاً.');
    const result = await setUp();
    act(() => result.current.toggleCart(PLAN_CAMPAIGNS));
    act(() => result.current.checkout());
    await act(async () => { await result.current.finishCheckout(['plan_campaigns'], 'tok_1'); });
    expect(result.current.cart).toEqual(['plan_campaigns']);
    expect(result.current.cartError).toBe('هذا التطبيق يحتاج تفعيل تسجيل زيارة أولاً.');
  });

  it('a thrown non-Error value still surfaces a fallback sentence, never crashes', async () => {
    checkoutShouldThrow = 'not an Error instance' as unknown as Error;
    const result = await setUp();
    act(() => result.current.toggleCart(PLAN_CAMPAIGNS));
    await act(async () => { await result.current.finishCheckout(['plan_campaigns'], 'tok_1'); });
    expect(result.current.cartError).not.toBe('');
  });
});
