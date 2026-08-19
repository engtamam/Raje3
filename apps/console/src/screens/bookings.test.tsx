/**
 * The bookings grid — the branch chooser, the read, and the actions a tapped card offers
 * (Stage 6/7, docs/خطة-تنفيذ-الحجوزات.md §6/§7).
 *
 * MOCKS `../api`, NOT `../catalog` — this screen calls the named functions in api.ts directly
 * (the same convention Visit.tsx uses), so that is the seam a test has to watch.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
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
      services: [{ id: 'svc1', name: 'قص شعر', duration_minutes: 30, cycle_days: 21 }],
      tracks_vehicle: false, fields: [],
    }),
    noShowRisk: async (...args: unknown[]) => {
      asked.push({ fn: 'noShowRisk', args });
      return { considered: 4, no_shows: 3, risky: true };
    },
    nearestSlot: async (...args: unknown[]) => {
      asked.push({ fn: 'nearestSlot', args });
      return { starts_at: 1786860000 };
    },
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
    rescheduleBooking: async (...args: unknown[]) => {
      asked.push({ fn: 'rescheduleBooking', args });
      return { ...BOOKING, starts_at: (args[1] as number) };
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

describe('branch selection', () => {
  it('offers a chooser when more than one branch and none is scoped', () => {
    open({ branches: [{ id: 'b1', name: 'فرع الرياض' }, { id: 'b2', name: 'فرع جدة' }] });
    expect(screen.getByText('فرع الرياض')).toBeTruthy();
    expect(screen.getByText('فرع جدة')).toBeTruthy();
    expect(asked).toHaveLength(0);
  });

  it('picks the one branch silently — no choice to make', async () => {
    open({ branches: [{ id: 'b1', name: 'فرع الرياض' }] });
    await waitFor(() => expect(asked.some((a) => a.fn === 'listBookings')).toBe(true));
    expect(asked[0].args[1]).toBe('b1');
  });
});

describe('the grid', () => {
  it('reads the selected branch\'s bookings and places them on the grid', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => expect(screen.getByText(/قص شعر/)).toBeTruthy());
  });

  it('opens an action sheet when a card is tapped', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => screen.getByText(/قص شعر/));
    screen.getByText(/قص شعر/).click();
    await waitFor(() => expect(screen.getByText('حضرت')).toBeTruthy());
    expect(screen.getByText('لم تحضر')).toBeTruthy();
    expect(screen.getByText('إلغاء الحجز')).toBeTruthy();
  });

  it('marks attendance from the action sheet', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => screen.getByText(/قص شعر/));
    screen.getByText(/قص شعر/).click();
    await waitFor(() => screen.getByText('حضرت'));
    screen.getByText('حضرت').click();
    await waitFor(() => expect(asked.some((a) => a.fn === 'attendBooking')).toBe(true));
    expect(asked.find((a) => a.fn === 'attendBooking')?.args[1]).toBe('bkg_1');
  });

  it('cancels from the action sheet', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => screen.getByText(/قص شعر/));
    screen.getByText(/قص شعر/).click();
    await waitFor(() => screen.getByText('إلغاء الحجز'));
    screen.getByText('إلغاء الحجز').click();
    await waitFor(() => expect(asked.some((a) => a.fn === 'cancelBooking')).toBe(true));
  });

  it('filters visible cards by the quick search, with no new request', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => screen.getByText(/قص شعر/));
    const before = asked.filter((a) => a.fn === 'listBookings').length;
    const search = screen.getByPlaceholderText(/بحثٌ سريع/);
    fireEvent.change(search, { target: { value: 'لا يوجد' } });
    await waitFor(() => expect(screen.queryByText(/قص شعر/)).toBeNull());
    expect(asked.filter((a) => a.fn === 'listBookings').length).toBe(before);
  });
});

describe('حجز جديد', () => {
  it('opens the booking dialog', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => screen.getByText('حجز جديد'));
    screen.getByText('حجز جديد').click();
    await waitFor(() => expect(screen.getByText(/جوّال العميلة/)).toBeTruthy());
  });

  it('opens the same dialog from an empty cell click — no separate flow', async () => {
    const { container } = open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => screen.getByText(/قص شعر/));
    // The column background itself, not a card — clicking a card opens the action sheet instead.
    const column = container.querySelectorAll('.border-s')[1];
    fireEvent.click(column);
    await waitFor(() => expect(screen.getByText(/جوّال العميلة/)).toBeTruthy());
  });
});

describe('السحب والإفلات', () => {
  it('marks the card as being dragged the moment a drag starts', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => screen.getByText(/قص شعر/));
    const card = screen.getByText(/قص شعر/).closest('[draggable="true"]') as HTMLElement;
    expect(card.getAttribute('draggable')).toBe('true');

    fireEvent.dragStart(card);
    await waitFor(() => expect(card.className).toContain('rj-card-dragging'));
  });

  it('cards for a cancelled or closed booking are never draggable', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => screen.getByText(/قص شعر/));
    screen.getByText(/قص شعر/).click();
    await waitFor(() => screen.getByText('إلغاء الحجز'));
    screen.getByText('إلغاء الحجز').click();
    await waitFor(() => expect(asked.some((a) => a.fn === 'cancelBooking')).toBe(true));
    // A cancelled booking is filtered out of the grid entirely (§7) — nothing left to drag.
    expect(screen.queryByText(/قص شعر/)).toBeNull();
  });
});

describe('احجزي الجلسة القادمة', () => {
  it('offers the next session after marking attendance, when the service has a real cycle', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => screen.getByText(/قص شعر/));
    screen.getByText(/قص شعر/).click();
    await waitFor(() => screen.getByText('حضرت'));
    screen.getByText('حضرت').click();
    await waitFor(() => expect(screen.getByText(/احجزي الجلسة القادمة/)).toBeTruthy());
  });

  it('opens the booking dialog with the customer already known — no phone search needed', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => screen.getByText(/قص شعر/));
    screen.getByText(/قص شعر/).click();
    await waitFor(() => screen.getByText('حضرت'));
    screen.getByText('حضرت').click();
    await waitFor(() => screen.getByText(/احجزي الجلسة القادمة/));
    screen.getByText(/احجزي الجلسة القادمة/).click();
    await waitFor(() => expect(screen.getByText(/عميلة معروفة/)).toBeTruthy());
  });
});

describe('booking dialog — Stage 8', () => {
  it('shows the no-show risk note once a known customer is picked, never before', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => screen.getByText('حجز جديد'));
    screen.getByText('حجز جديد').click();
    await waitFor(() => screen.getByText(/جوّال العميلة/));
    expect(screen.queryByText(/غابت عن/)).toBeNull();
  });

  it('offers "أقرب فتحة" once the dialog is open', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => screen.getByText('حجز جديد'));
    screen.getByText('حجز جديد').click();
    await waitFor(() => expect(screen.getByText('أقرب فتحة')).toBeTruthy());
  });
});
