/**
 * «محفظتي» — the fund breakdown, and the absence discipline: a purpose-specific card (renewal,
 * commission) must never render for a shop it does not apply to.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { ApiError } from '../api';

let actionIds: Set<string>;
let callImpl: (session: unknown, a: { id: string }, body?: unknown) => Promise<unknown>;

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => (actionIds.has(id) ? { id, label: id, method: 'GET', path: `/${id}` } : undefined),
    call: async (session: unknown, a: { id: string }, body?: unknown) => callImpl(session, a, body),
  };
});

const { WalletPane } = await import('./Wallet');

const session = {} as never;
const catalog = { services: [], unreachable: [] } as never;

afterEach(() => { cleanup(); });

function withActions(extra: string[] = []) {
  actionIds = new Set(['wallet.my_balance', 'billing.my_subscriptions', ...extra]);
}

describe('WalletPane', () => {
  it('is absent entirely when wallet.my_balance is not in the catalogue', () => {
    actionIds = new Set([]);
    const { container } = render(<WalletPane session={session} catalog={catalog} />);
    expect(container.firstChild).toBeNull();
  });

  it('shows the total and the bundled AI-credit card', async () => {
    withActions();
    callImpl = async (_s, a) => {
      if (a.id === 'wallet.my_balance') return {
        currency: 'SAR', available_total: 20000,
        funds: { ai_credit: 10000, topup: 2345 }, held: {}, balance: 20000,
      };
      if (a.id === 'billing.my_subscriptions') return { subscriptions: [] };
      return {};
    };
    render(<WalletPane session={session} catalog={catalog} />);
    await waitFor(() => expect(screen.getByText('200 ريال')).toBeTruthy());
    expect(screen.getByText('وحدات الذكاء')).toBeTruthy();
    expect(screen.getByText('123.45 ريال')).toBeTruthy();   // the bundled ai_credit+topup total
  });

  it('a failed read shows the real failure sentence, not an empty screen', async () => {
    withActions();
    callImpl = async () => { throw new Error('boom'); };
    render(<WalletPane session={session} catalog={catalog} />);
    await waitFor(() => expect(screen.getByText('تعذّرت قراءة محفظتك')).toBeTruthy());
  });

  it('the renewal card is absent for a shop with no wallet-pinned subscription', async () => {
    withActions();
    callImpl = async (_s, a) => {
      if (a.id === 'wallet.my_balance') return {
        currency: 'SAR', available_total: 5000, funds: { ai_credit: 5000 }, held: {}, balance: 5000,
      };
      if (a.id === 'billing.my_subscriptions') return {
        subscriptions: [{ payment_gateway: 'tuwaiqpay', status: 'active' }],
      };
      return {};
    };
    render(<WalletPane session={session} catalog={catalog} />);
    await waitFor(() => expect(screen.getByText('وحدات الذكاء')).toBeTruthy());
    expect(screen.queryByText('رصيد تجديد الاشتراك')).toBeNull();
  });

  it('the renewal card appears for a shop pinned to pay-by-wallet', async () => {
    withActions();
    callImpl = async (_s, a) => {
      if (a.id === 'wallet.my_balance') return {
        currency: 'SAR', available_total: 5000,
        funds: { ai_credit: 5000, renewal: 3000 }, held: {}, balance: 8000,
      };
      if (a.id === 'billing.my_subscriptions') return {
        subscriptions: [{ payment_gateway: 'wallet', status: 'active' }],
      };
      return {};
    };
    render(<WalletPane session={session} catalog={catalog} />);
    await waitFor(() => expect(screen.getByText('رصيد تجديد الاشتراك')).toBeTruthy());
  });

  it('a canceled wallet-pinned subscription does not surface the renewal card', async () => {
    withActions();
    callImpl = async (_s, a) => {
      if (a.id === 'wallet.my_balance') return {
        currency: 'SAR', available_total: 5000, funds: { ai_credit: 5000 }, held: {}, balance: 5000,
      };
      if (a.id === 'billing.my_subscriptions') return {
        subscriptions: [{ payment_gateway: 'wallet', status: 'canceled' }],
      };
      return {};
    };
    render(<WalletPane session={session} catalog={catalog} />);
    await waitFor(() => expect(screen.getByText('وحدات الذكاء')).toBeTruthy());
    expect(screen.queryByText('رصيد تجديد الاشتراك')).toBeNull();
  });

  it('the commission card is absent for an ordinary (non-partner) shop', async () => {
    withActions();
    callImpl = async (_s, a) => {
      if (a.id === 'wallet.my_balance') return {
        currency: 'SAR', available_total: 5000, funds: { ai_credit: 5000 }, held: {}, balance: 5000,
      };
      if (a.id === 'billing.my_subscriptions') return { subscriptions: [] };
      return {};
    };
    render(<WalletPane session={session} catalog={catalog} />);
    await waitFor(() => expect(screen.getByText('وحدات الذكاء')).toBeTruthy());
    expect(screen.queryByText('عمولتك كشريك')).toBeNull();
  });

  it('the commission card appears for a partner account', async () => {
    withActions(['partner.my_shops']);
    callImpl = async (_s, a) => {
      if (a.id === 'wallet.my_balance') return {
        currency: 'SAR', available_total: 5000,
        funds: { ai_credit: 5000, commission: 1500 }, held: {}, balance: 6500,
      };
      if (a.id === 'billing.my_subscriptions') return { subscriptions: [] };
      return {};
    };
    render(<WalletPane session={session} catalog={catalog} />);
    await waitFor(() => expect(screen.getByText('عمولتك كشريك')).toBeTruthy());
  });

  it('a held amount is subtracted from the shown balance', async () => {
    withActions();
    callImpl = async (_s, a) => {
      if (a.id === 'wallet.my_balance') return {
        currency: 'SAR', available_total: 8000,
        funds: { ai_credit: 10000 }, held: { ai_credit: 2000 }, balance: 10000,
      };
      if (a.id === 'billing.my_subscriptions') return { subscriptions: [] };
      return {};
    };
    render(<WalletPane session={session} catalog={catalog} />);
    // 10000 - 2000 = 8000 halalas = 80 ريال, shown inside the AI-credit card's hint.
    await waitFor(() => expect(screen.getByText(/80 ريال مضمّن/)).toBeTruthy());
  });

  it('the manual top-up button is absent when billing.wallet_topup_checkout is not in the catalogue', async () => {
    withActions();
    callImpl = async (_s, a) => {
      if (a.id === 'wallet.my_balance') return {
        currency: 'SAR', available_total: 5000, funds: { ai_credit: 5000 }, held: {}, balance: 5000,
      };
      if (a.id === 'billing.my_subscriptions') return { subscriptions: [] };
      return {};
    };
    render(<WalletPane session={session} catalog={catalog} />);
    await waitFor(() => expect(screen.getByText('وحدات الذكاء')).toBeTruthy());
    expect(screen.queryByText('شحن رصيدي يدوياً')).toBeNull();
  });

  describe('manual top-up', () => {
    let originalLocation: Location;

    function setup() {
      withActions(['billing.wallet_topup_checkout']);
      callImpl = async (_s, a) => {
        if (a.id === 'wallet.my_balance') return {
          currency: 'SAR', available_total: 5000, funds: { ai_credit: 5000 }, held: {}, balance: 5000,
        };
        if (a.id === 'billing.my_subscriptions') return { subscriptions: [] };
        return {};
      };
    }

    // jsdom does not implement real navigation — replace `window.location` with a plain
    // writable stub so setting `.href` is observable instead of throwing "not implemented".
    beforeEach(() => {
      originalLocation = window.location;
      // @ts-expect-error — deliberately narrowing for the test's own stub
      delete window.location;
      // @ts-expect-error — same
      window.location = { href: 'https://shop.raje3.sa/wallet' } as Location;
    });
    afterEach(() => {
      // @ts-expect-error — restoring the real Location object after the test's own stub
      window.location = originalLocation;
    });

    it('opens a dialog, and redirects the browser to the gateway on success', async () => {
      setup();
      const topupCall = vi.fn().mockResolvedValue({
        checkout: { ok: true, redirect_url: 'https://onboarding-prod.tuwaiqpay.com.sa/pay/abc' },
      });
      const realCallImpl = callImpl;
      callImpl = async (s, a, body) => {
        if (a.id === 'billing.wallet_topup_checkout') return topupCall(s, a, body);
        return realCallImpl(s, a, body);
      };

      render(<WalletPane session={session} catalog={catalog} />);
      fireEvent.click(await screen.findByText('شحن رصيدي يدوياً'));
      await screen.findByText('شحن رصيدك');

      // starts at a real, valid default (50 ريال — multiples of 10, +/- stepper, no free amount
      // and no "empty" state per the owner's own 2026-09-09 decision) — submitting immediately
      // must already work. Scoped to the stepper's own group: without a real ai-unit rate wired
      // (not in `withActions()` here), the units preview below it falls back to the same riyal
      // text, so an unscoped query matches two elements.
      const amountGroup = () => screen.getByRole('group', { name: 'المبلغ' });
      expect(within(amountGroup()).getByText('50 ريال')).toBeTruthy();
      fireEvent.click(screen.getByText('الدفع الآن'));

      await waitFor(() => expect(topupCall).toHaveBeenCalledWith(
        session, expect.objectContaining({ id: 'billing.wallet_topup_checkout' }),
        expect.objectContaining({ amount_minor: 5000 }),
      ));
      await waitFor(() => expect(window.location.href).toBe(
        'https://onboarding-prod.tuwaiqpay.com.sa/pay/abc',
      ));
    });

    it('the +/- stepper moves in multiples of 10 riyals', async () => {
      setup();
      render(<WalletPane session={session} catalog={catalog} />);
      fireEvent.click(await screen.findByText('شحن رصيدي يدوياً'));
      await screen.findByText('شحن رصيدك');

      const amountGroup = () => screen.getByRole('group', { name: 'المبلغ' });
      fireEvent.click(screen.getByLabelText('زيادة 10 ريال'));
      expect(within(amountGroup()).getByText('60 ريال')).toBeTruthy();
      fireEvent.click(screen.getByLabelText('إنقاص 10 ريال'));
      fireEvent.click(screen.getByLabelText('إنقاص 10 ريال'));
      expect(within(amountGroup()).getByText('40 ريال')).toBeTruthy();
    });

    it('shows a real Arabic sentence for a known backend error code, not the raw code', async () => {
      setup();
      const realCallImpl = callImpl;
      callImpl = async (s, a, body) => {
        if (a.id === 'billing.wallet_topup_checkout') {
          throw new ApiError(400, { detail: 'AMOUNT_EXCEEDS_MAX' }, 'x');
        }
        return realCallImpl(s, a, body);
      };

      render(<WalletPane session={session} catalog={catalog} />);
      fireEvent.click(await screen.findByText('شحن رصيدي يدوياً'));
      await screen.findByText('شحن رصيدك');

      // the backend can still refuse a client-valid amount (e.g. a per-shop cap) — the dialog
      // does not need to reproduce the exact threshold to prove it maps the error sentence.
      fireEvent.click(screen.getByText('الدفع الآن'));

      await waitFor(() => expect(
        screen.getByText('هذا المبلغ أكبر من الحد المسموح للشحن اليدوي.'),
      ).toBeTruthy());
      expect(screen.queryByText(/AMOUNT_EXCEEDS_MAX/)).toBeNull();
    });
  });
});
