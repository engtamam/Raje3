/**
 * «كوبونات» — the grant form, the two tabs, and the live phone-check hint. Each backend call is
 * faked at the `catalog.call` boundary, same discipline as `rating.test.tsx`.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render as rtlRender, screen, waitFor } from '@testing-library/react';
import type { ReactElement } from 'react';
import { OperatorI18nProvider } from '../operator-i18n';
import { CouponsScreen } from './Coupons';

const SESSION = { tenant: 't1', operator: '', operatorName: '', token: 'tok' } as never;

const STATS = {
  grants_this_month: 3, current_cap_percent: 20, ceiling_percent: 35,
  next_tier_percent: 30, next_tier_grants_needed: 5,
  history: [
    { month_key: '2026-04', grants: 1 }, { month_key: '2026-05', grants: 2 },
    { month_key: '2026-06', grants: 0 }, { month_key: '2026-07', grants: 4 },
    { month_key: '2026-08', grants: 2 }, { month_key: '2026-09', grants: 3 },
  ],
};

const HISTORY = {
  attempts: [
    { id: 'a1', beneficiary_phone_last4: '4821', percent_requested: 10, scope: 'feature.bookings',
     outcome: 'granted', created: Math.floor(Date.now() / 1000), per_app: { 'feature.bookings': 'attached' } },
    { id: 'a2', beneficiary_phone_last4: '9910', percent_requested: 25, scope: 'all',
     outcome: 'over_cap', created: Math.floor(Date.now() / 1000), per_app: {} },
  ],
};

let grantCalls: Record<string, unknown>[] = [];

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }, params?: Record<string, unknown>) => {
      if (a.id === 'operations.coupon_stats') return STATS;
      if (a.id === 'operations.coupon_history') return HISTORY;
      if (a.id === 'operations.coupon_check') {
        const phone = String(params?.phone ?? '');
        if (phone.endsWith('99')) return { registered: true, already_granted_this_month: true };
        if (phone.endsWith('00')) return { registered: false, already_granted_this_month: false };
        return { registered: true, already_granted_this_month: false };
      }
      if (a.id === 'operations.grant_coupon') {
        grantCalls.push(params ?? {});
        return { id: 'att1', outcome: 'granted', per_app: { 'feature.bookings': 'attached' } };
      }
      return {};
    },
  };
});

const catalog = { services: [], unreachable: [] } as never;

function render(ui: ReactElement) {
  return rtlRender(<OperatorI18nProvider session={SESSION}>{ui}</OperatorI18nProvider>);
}

afterEach(() => { cleanup(); grantCalls = []; });

describe('«كوبونات»', () => {
  it('shows the current cap and the grant form', async () => {
    render(<CouponsScreen session={SESSION} catalog={catalog} />);
    await waitFor(() => expect(screen.getByText('20%')).toBeTruthy());
    expect(screen.getByText('امنح كوبوناً')).toBeTruthy();
  });

  it('shows the log tab by default, with a real refusal reason', async () => {
    render(<CouponsScreen session={SESSION} catalog={catalog} />);
    await waitFor(() => expect(screen.getAllByText('تجاوزت سقفك الحالي').length).toBeGreaterThan(0));
  });

  it('switches to the stats tab and renders the tier ladder', async () => {
    render(<CouponsScreen session={SESSION} catalog={catalog} />);
    fireEvent.click(screen.getByText('الإحصائيات'));
    await waitFor(() => expect(screen.getByTestId('coupon-ladder')).toBeTruthy());
    expect(screen.getByTestId('coupon-kpi-month').textContent).toContain('3');
  });

  it('the live phone hint warns when the beneficiary already has a coupon this month', async () => {
    render(<CouponsScreen session={SESSION} catalog={catalog} />);
    const phoneInput = screen.getByPlaceholderText('05xxxxxxxx');
    fireEvent.change(phoneInput, { target: { value: '0512345699' } });
    await waitFor(() => expect(screen.getByText('عنده كوبون منك هذا الشهر بالفعل')).toBeTruthy(),
      { timeout: 1000 });
  });

  it('the live phone hint flags an unregistered number', async () => {
    render(<CouponsScreen session={SESSION} catalog={catalog} />);
    const phoneInput = screen.getByPlaceholderText('05xxxxxxxx');
    fireEvent.change(phoneInput, { target: { value: '0512345600' } });
    await waitFor(() => expect(screen.getByText('هذا الرقم ليس محلاً مسجّلاً عندنا')).toBeTruthy(),
      { timeout: 1000 });
  });
});
