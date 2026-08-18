/**
 * الحجوزات — the branch chooser, the read, and the actions each row offers (Stage 6,
 * docs/خطة-تنفيذ-الحجوزات.md §6).
 *
 * MOCKS `../api`, NOT `../catalog` — unlike `overdue.test.tsx`, this screen calls the named
 * functions in api.ts directly (the same convention Visit.tsx uses), so that is the seam a test
 * has to watch to prove the wire rather than a stubbed state.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { createElement } from 'react';

const asked: { fn: string; args: unknown[] }[] = [];

const BOOKING = {
  id: 'bkg_1', branch_id: 'b1', operator_id: 'op1', customer_id: 'c1',
  service_ids: ['svc1'], starts_at: 1786860000, duration_minutes: 30,
  status: 'booked', series_id: null, series_seq: null, visit_id: null,
  deposit_taken: false, note: '', reason_no_show: null, created: 1, created_by: '',
  updated: 1, cancelled_reason: null, thumb_up: null, rev: 1,
} as const;

vi.mock('../api', async (importOriginal) => {
  const real = await importOriginal<typeof import('../api')>();
  return {
    ...real,
    listBookings: async (...args: unknown[]) => {
      asked.push({ fn: 'listBookings', args });
      return { bookings: [BOOKING] };
    },
    fetchCatalogue: async () => ({
      services: [{ id: 'svc1', name: 'قص شعر', duration_minutes: 30 }], tracks_vehicle: false, fields: [],
    }),
    listBookingStaff: async () => ([{ id: 'op1', name: 'سارة', active: true, has_pin: false, branch_id: '' }]),
    attendBooking: async (...args: unknown[]) => {
      asked.push({ fn: 'attendBooking', args });
      return { ...BOOKING, status: 'attended' };
    },
    cancelBooking: async (...args: unknown[]) => {
      asked.push({ fn: 'cancelBooking', args });
      return { ...BOOKING, status: 'cancelled' };
    },
    noShowBooking: async (...args: unknown[]) => {
      asked.push({ fn: 'noShowBooking', args });
      return { ...BOOKING, status: 'no_show' };
    },
  };
});

afterEach(() => { asked.length = 0; cleanup(); });

const { BookingsScreen } = await import('./Bookings');

const session = {} as never;

function open(props: Partial<Parameters<typeof BookingsScreen>[0]> = {}) {
  return render(createElement(BookingsScreen, {
    session, branch: '', branches: [], onBranch: () => {}, ...props,
  }));
}

describe('اختيار الفرع', () => {
  it('يعرض منتقي الفروع حين لا يكون هناك فرعٌ واحد مختار', () => {
    open({ branches: [{ id: 'b1', name: 'فرع الرياض' }, { id: 'b2', name: 'فرع جدة' }] });
    expect(screen.getByText('فرع الرياض')).toBeTruthy();
    expect(screen.getByText('فرع جدة')).toBeTruthy();
    expect(asked).toHaveLength(0);
  });

  it('يختار الفرع الوحيد صامتاً حين لا يوجد إلا فرعٌ واحد — لا خيار', async () => {
    open({ branches: [{ id: 'b1', name: 'فرع الرياض' }] });
    await waitFor(() => expect(asked.some((a) => a.fn === 'listBookings')).toBe(true));
    expect(asked[0].args[1]).toBe('b1');
  });

  it('لا يسأل شيئاً قبل أن يختار — نفس قاعدة «محلّي»', () => {
    open({ branches: [{ id: 'b1' }, { id: 'b2' }] });
    expect(asked.filter((a) => a.fn === 'listBookings')).toHaveLength(0);
  });
});

describe('جدول اليوم', () => {
  it('يقرأ حجوزات الفرع المختار', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => expect(screen.getByText(/قص شعر/)).toBeTruthy());
    expect(screen.getByText(/سارة/)).toBeTruthy();
  });

  it('يعرض حالة الحجز', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => expect(screen.getByText('محجوز')).toBeTruthy());
  });

  it('يسجّل الحضور بضغطة، ويحدّث الصف فوراً', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => screen.getByText('حضرت'));
    screen.getByText('حضرت').click();
    await waitFor(() => expect(asked.some((a) => a.fn === 'attendBooking')).toBe(true));
    expect(asked.find((a) => a.fn === 'attendBooking')?.args[1]).toBe('bkg_1');
  });

  it('يلغي الحجز بضغطة', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => screen.getByText('إلغاء'));
    screen.getByText('إلغاء').click();
    await waitFor(() => expect(asked.some((a) => a.fn === 'cancelBooking')).toBe(true));
  });
});

describe('حجز جديد', () => {
  it('يفتح نافذة الحجز', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => screen.getByText('حجز جديد'));
    screen.getByText('حجز جديد').click();
    await waitFor(() => expect(screen.getByText(/جوّال العميلة/)).toBeTruthy());
  });
});
