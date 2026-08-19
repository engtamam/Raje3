/**
 * "مواعيده القادمة والسابقة، ونسبة حضوره" — docs/وصف-تطبيق-الحجوزات.md §3.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { createElement } from 'react';

const asked: { fn: string; args: unknown[] }[] = [];

const BOOKING = {
  id: 'bkg_1', branch_id: 'b1', operator_id: 'op1', customer_id: 'c1',
  service_ids: ['svc1'], duration_minutes: 30,
  series_id: null, series_seq: null, visit_id: null,
  payment_status: 'none', deposit_amount_minor: null, note: '', reason_no_show: null, created: 1, created_by: '',
  updated: 1, cancelled_reason: null, thumb_up: null, rev: 1,
} as const;

let response: { bookings: unknown[] } | 'fail' = { bookings: [] };

vi.mock('./api', async (importOriginal) => {
  const real = await importOriginal<typeof import('./api')>();
  return {
    ...real,
    bookingsForCustomer: async (...args: unknown[]) => {
      asked.push({ fn: 'bookingsForCustomer', args });
      if (response === 'fail') throw new Error('boom');
      return response;
    },
  };
});

afterEach(() => { asked.length = 0; response = { bookings: [] }; cleanup(); });

const { CustomerBookingHistory } = await import('./CustomerBookingHistory');

function open() {
  return render(createElement(CustomerBookingHistory, {
    session: {} as never, customerId: 'c1',
  }));
}

describe('قسم حجوزات صفحة العميل', () => {
  it('renders nothing when he has no bookings at all', async () => {
    response = { bookings: [] };
    open();
    await waitFor(() => expect(asked.some((a) => a.fn === 'bookingsForCustomer')).toBe(true));
    expect(screen.queryByText('الحجوزات')).toBeNull();
  });

  it('renders nothing on a failed read, same as an empty one', async () => {
    response = 'fail';
    open();
    await waitFor(() => expect(asked.some((a) => a.fn === 'bookingsForCustomer')).toBe(true));
    expect(screen.queryByText('الحجوزات')).toBeNull();
  });

  it('splits upcoming from past and computes the attendance rate from closed appointments only', async () => {
    const future = Math.floor(Date.now() / 1000) + 7 * 86400;
    const past = Math.floor(Date.now() / 1000) - 7 * 86400;
    response = {
      bookings: [
        { ...BOOKING, id: 'b1', starts_at: future, status: 'booked' },
        { ...BOOKING, id: 'b2', starts_at: past, status: 'attended' },
        { ...BOOKING, id: 'b3', starts_at: past - 86400, status: 'no_show' },
        // cancelled must not count toward the rate — it is not an attendance outcome.
        { ...BOOKING, id: 'b4', starts_at: past - 2 * 86400, status: 'cancelled' },
      ],
    };
    open();
    await waitFor(() => screen.getByText('الحجوزات'));
    expect(screen.getByText('القادمة')).toBeTruthy();
    expect(screen.getByText('السابقة')).toBeTruthy();
    // one attended of two closed (attended + no_show) -> 50%
    expect(screen.getByText(/50٪/)).toBeTruthy();
  });
});
