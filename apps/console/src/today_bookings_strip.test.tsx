/**
 * Today's bookings strip (Stage 9, docs/وصف-تطبيق-الحجوزات.md §6.3) — one tap opens the visit
 * outright, via the same booking->visit gateway the grid's own action sheet calls.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render as rtlRender, screen, waitFor } from '@testing-library/react';
import type { ReactElement } from 'react';
import { OperatorI18nProvider } from './operator-i18n';

// TodayBookingsStrip now reads `useOperatorI18n()` — wrap once here so every existing
// `render(<...>)` call site below stays unchanged.
const SESSION_FOR_I18N = { tenant: 't1', operator: '', operatorName: '', token: 'tok' } as never;
function render(ui: ReactElement) {
  return rtlRender(<OperatorI18nProvider session={SESSION_FOR_I18N}>{ui}</OperatorI18nProvider>);
}
import { createElement } from 'react';

const asked: { fn: string; args: unknown[] }[] = [];

const BOOKING = {
  id: 'bkg_1', branch_id: 'b1', operator_id: 'op1', customer_id: 'c1',
  service_ids: ['svc1'], starts_at: 1786860000, duration_minutes: 30,
  status: 'booked', series_id: null, series_seq: null, visit_id: null,
  payment_status: 'none', deposit_amount_minor: null, note: '', reason_no_show: null, created: 1, created_by: '',
  updated: 1, cancelled_reason: null, thumb_up: null, rev: 1,
} as const;

vi.mock('./api', async (importOriginal) => {
  const real = await importOriginal<typeof import('./api')>();
  return {
    ...real,
    listBookings: async (...args: unknown[]) => {
      asked.push({ fn: 'listBookings', args });
      return { bookings: [BOOKING, { ...BOOKING, id: 'bkg_2', status: 'attended' }] };
    },
    listBookingStaff: async () => ([{ id: 'op1', name: 'سارة', active: true, has_pin: false }]),
    attendBooking: async (...args: unknown[]) => {
      asked.push({ fn: 'attendBooking', args });
      return { ...BOOKING, status: 'attended' };
    },
  };
});

afterEach(() => { asked.length = 0; cleanup(); });

const { TodayBookingsStrip } = await import('./TodayBookingsStrip');
const SERVICES = [{ id: 'svc1', name: 'قص شعر' }];

function open(branchId = 'b1') {
  return render(createElement(TodayBookingsStrip, {
    session: {} as never, branchId, services: SERVICES,
  }));
}

describe('today\'s bookings strip', () => {
  it('renders nothing with no branch — never guesses which one', () => {
    open('');
    expect(asked).toHaveLength(0);
  });

  it('shows the time, the operator and the service for each booking', async () => {
    open();
    await waitFor(() => expect(screen.getByText(/سارة/)).toBeTruthy());
    expect(screen.getByText(/قص شعر/)).toBeTruthy();
  });

  it('opens the visit with one tap — the same booking->visit gateway the grid uses', async () => {
    open();
    await waitFor(() => screen.getByLabelText('حضر'));
    screen.getByLabelText('حضر').click();
    await waitFor(() => expect(asked.some((a) => a.fn === 'attendBooking')).toBe(true));
    expect(asked.find((a) => a.fn === 'attendBooking')?.args[1]).toBe('bkg_1');
  });

  it('removes the card from the strip once the visit is opened', async () => {
    open();
    await waitFor(() => screen.getByLabelText('حضر'));
    screen.getByLabelText('حضر').click();
    await waitFor(() => expect(screen.queryByText(/سارة/)).toBeNull());
  });

  it('only offers still-booked appointments — an already-attended one is not shown twice', async () => {
    open();
    await waitFor(() => expect(screen.getAllByLabelText('حضر')).toHaveLength(1));
  });
});
