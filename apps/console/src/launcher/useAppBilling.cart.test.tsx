/**
 * The cart half of `useAppBilling` — adding/removing an app, the auto-add of an unmet
 * `plan.requires_any` dependency (the owner's own instruction: never a text-only suggestion,
 * the dependency travels in the same cart), and `checkout()`'s own hosted-pay-link flow
 * (`subscription.checkout_cart_link`, 2026-09-24, replacing the retired browser-tokenised
 * card-form pair).
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useAppBilling } from './useAppBilling';

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
  id: 'plan_loyalty', name: 'نقاط الولاء', active: true,
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
// DEFAULT: an all-free cart — billing already created it, no link to follow. Individual tests
// override this to a real `{checkout_url}` to exercise the redirect path instead.
let checkoutResponse: { checkout_required?: boolean; checkout_url?: string; notice?: string } =
  { checkout_required: false, notice: '' };
let heldSubs: unknown[] = [];
let previewCalls: unknown[] = [];
let previewResponse: unknown = null;
let previewShouldThrow: Error | null = null;

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
      if (a.id === 'subscription.checkout_cart_link') {
        checkoutCalls.push(body);
        if (checkoutShouldThrow) throw checkoutShouldThrow;
        return checkoutResponse;
      }
      if (a.id === 'subscription.checkout_preview') {
        previewCalls.push(body);
        if (previewShouldThrow) throw previewShouldThrow;
        return previewResponse;
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
  checkoutResponse = { checkout_required: false, notice: '' };
  heldSubs = [];
  previewCalls = [];
  previewResponse = null;
  previewShouldThrow = null;
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

describe('cartPreview', () => {
  it('fetches the real preview after an item is added, debounced', async () => {
    previewResponse = {
      currency: 'SAR', subtotal_minor: 4900, discount_minor: 0, tax_minor: 0, total_minor: 4900,
      items: [{ plan_id: 'plan_campaigns', interval: 'month', charged_now: true, on_trial: false,
               subtotal_minor: 4900, discount_minor: 0, tax_minor: 0, total_minor: 4900, prorated: false }],
    };
    const result = await setUp();
    act(() => result.current.toggleCart(PLAN_CAMPAIGNS));
    await act(async () => { await new Promise((r) => setTimeout(r, 250)); });
    expect(previewCalls).toEqual([{ items: [{ plan_id: 'plan_campaigns', interval: 'month' }] }]);
    expect(result.current.cartPreview).toEqual(previewResponse);
  });

  it('never fetches a preview for an empty cart', async () => {
    const result = await setUp();
    await act(async () => { await new Promise((r) => setTimeout(r, 250)); });
    expect(previewCalls).toEqual([]);
    expect(result.current.cartPreview).toBeNull();
  });

  it('surfaces a friendly error and clears the preview when billing cannot price the cart', async () => {
    previewShouldThrow = new Error('تعذّر حساب السعر.');
    const result = await setUp();
    act(() => result.current.toggleCart(PLAN_CAMPAIGNS));
    await act(async () => { await new Promise((r) => setTimeout(r, 250)); });
    expect(result.current.cartPreview).toBeNull();
    expect(result.current.cartPreviewError).toBe('تعذّر حساب السعر.');
    // A failed PRICE PREVIEW must never touch the cart itself — he can still check out.
    expect(result.current.cart).toEqual(['plan_campaigns']);
  });

  it('clears the preview once checkout empties the cart', async () => {
    previewResponse = {
      currency: 'SAR', subtotal_minor: 4900, discount_minor: 0, tax_minor: 0, total_minor: 4900,
      items: [],
    };
    const result = await setUp();
    act(() => result.current.toggleCart(PLAN_CAMPAIGNS));
    await act(async () => { await new Promise((r) => setTimeout(r, 250)); });
    expect(result.current.cartPreview).not.toBeNull();

    await act(async () => { await result.current.checkout(); });
    await act(async () => { await new Promise((r) => setTimeout(r, 250)); });
    expect(result.current.cart).toEqual([]);
    expect(result.current.cartPreview).toBeNull();
  });
});

describe('checkout', () => {
  it('does nothing on an empty cart', async () => {
    const result = await setUp();
    await act(async () => { await result.current.checkout(); });
    expect(checkoutCalls).toEqual([]);
  });

  it('sends every item with a month interval', async () => {
    const result = await setUp();
    act(() => result.current.toggleCart(PLAN_LOYALTY)); // + auto-added plan_visit
    await act(async () => { await result.current.checkout(); });
    expect(checkoutCalls).toEqual([{
      items: [{ plan_id: 'plan_loyalty', interval: 'month' }, { plan_id: 'plan_visit', interval: 'month' }],
    }]);
  });

  it('clears the cart on an all-free cart (checkout_required: false, no link to follow)', async () => {
    const result = await setUp();
    act(() => result.current.toggleCart(PLAN_CAMPAIGNS));
    await act(async () => { await result.current.checkout(); });
    expect(result.current.cart).toEqual([]);
    expect(result.current.cartError).toBe('');
  });

  it('navigates to the real pay-link when the cart actually costs something', async () => {
    checkoutResponse = { checkout_required: true, checkout_url: 'https://pay.example/cart_1' };
    // jsdom does not implement real navigation — a plain writable stub, same technique
    // wallet_pane.test.tsx's own redirect test uses, so `.assign` is observable rather than
    // throwing "not implemented".
    const originalLocation = window.location;
    const assign = vi.fn();
    // @ts-expect-error — deliberately narrowing for this test's own stub
    delete window.location;
    // @ts-expect-error — same
    window.location = { ...originalLocation, assign };
    try {
      const result = await setUp();
      act(() => result.current.toggleCart(PLAN_CAMPAIGNS));
      await act(async () => { await result.current.checkout(); });
      expect(assign).toHaveBeenCalledWith('https://pay.example/cart_1');
      // THE CART IS LEFT ALONE — the whole page is about to navigate away; clearing it here
      // would only matter if the redirect somehow failed, and the real page load makes that
      // moot anyway.
    } finally {
      // @ts-expect-error — restoring the real Location object after the test's own stub
      window.location = originalLocation;
    }
  });

  it('keeps the cart and surfaces the error on a refused checkout', async () => {
    checkoutShouldThrow = new Error('هذا التطبيق يحتاج تفعيل تسجيل زيارة أولاً.');
    const result = await setUp();
    act(() => result.current.toggleCart(PLAN_CAMPAIGNS));
    await act(async () => { await result.current.checkout(); });
    expect(result.current.cart).toEqual(['plan_campaigns']);
    expect(result.current.cartError).toBe('هذا التطبيق يحتاج تفعيل تسجيل زيارة أولاً.');
  });

  it('a thrown non-Error value still surfaces a fallback sentence, never crashes', async () => {
    checkoutShouldThrow = 'not an Error instance' as unknown as Error;
    const result = await setUp();
    act(() => result.current.toggleCart(PLAN_CAMPAIGNS));
    await act(async () => { await result.current.checkout(); });
    expect(result.current.cartError).not.toBe('');
  });
});
