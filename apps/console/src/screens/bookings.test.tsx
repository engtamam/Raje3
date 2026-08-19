/**
 * The bookings grid — the branch chooser, the read, and the actions a tapped card offers
 * (Stage 6/7, docs/خطة-تنفيذ-الحجوزات.md §6/§7).
 *
 * MOCKS `../api`, NOT `../catalog` — this screen calls the named functions in api.ts directly
 * (the same convention Visit.tsx uses), so that is the seam a test has to watch.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { createElement } from 'react';

const asked: { fn: string; args: unknown[] }[] = [];

const BOOKING = {
  id: 'bkg_1', branch_id: 'b1', operator_id: 'op1', customer_id: 'c1',
  service_ids: ['svc1'], starts_at: 1786860000, duration_minutes: 30,
  status: 'booked', series_id: null, series_seq: null, visit_id: null,
  payment_status: 'none', deposit_amount_minor: null, note: '', reason_no_show: null, created: 1, created_by: '',
  updated: 1, cancelled_reason: null, thumb_up: null, rev: 1,
} as const;

// A SINGLE OVERRIDABLE ROW — most tests want the plain default; the payment-pill test below
// swaps this for one carrying a real deposit before rendering, and restores it in `afterEach`.
let bookingsOverride: typeof BOOKING[] = [BOOKING];

vi.mock('../api', async (importOriginal) => {
  const real = await importOriginal<typeof import('../api')>();
  return {
    ...real,
    listBookings: async (...args: unknown[]) => {
      asked.push({ fn: 'listBookings', args });
      return { bookings: bookingsOverride };
    },
    fetchCatalogue: async () => ({
      services: [
        { id: 'svc1', name: 'قص شعر', duration_minutes: 30, cycle_days: 21 },
        { id: 'svc2', name: 'تلميع', duration_minutes: 0, cycle_days: 0 },
      ],
      tracks_vehicle: false, fields: [],
    }),
    setServiceDuration: async (...args: unknown[]) => {
      asked.push({ fn: 'setServiceDuration', args });
      return {};
    },
    noShowRisk: async (...args: unknown[]) => {
      asked.push({ fn: 'noShowRisk', args });
      return { considered: 4, no_shows: 3, risky: true };
    },
    nearestSlot: async (...args: unknown[]) => {
      asked.push({ fn: 'nearestSlot', args });
      return { starts_at: 1786860000 };
    },
    listBookingStaff: async () => ([{ id: 'op1', name: 'سارة', active: true, has_pin: false, branch_id: '' }]),
    suggestByPrefix: async (...args: unknown[]) => {
      asked.push({ fn: 'suggestByPrefix', args });
      return [{ id: 'c1', phone: '966501234567', name: 'محمد' }];
    },
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

afterEach(() => { asked.length = 0; bookingsOverride = [BOOKING]; cleanup(); });

const { BookingsScreen } = await import('./Bookings');

const session = {} as never;

function open(props: Partial<Parameters<typeof BookingsScreen>[0]> = {}) {
  return render(createElement(BookingsScreen, {
    session, branch: '', branches: [], onBranch: () => {}, ...props,
  }));
}

// SCOPED TO THE GRID ONLY. The filter row's own service <select> carries the same service names
// as every card on it — real and correct in production, but it means an unscoped
// `card()` matches the <option> too the moment more than one card exists.
const grid = () => screen.getByTestId('rj-grid');
const card = () => within(grid()).getByText(/قص شعر/);
const queryCard = () => within(grid()).queryByText(/قص شعر/);

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
    await waitFor(() => expect(card()).toBeTruthy());
  });

  it('bannerless when nothing is overdue, banner-and-jump when something is', async () => {
    // BOOKING.starts_at (1786860000) is well in the past by the time this suite runs — a fixed
    // past epoch, not `Date.now()`, so this test needs nothing more than the default mock to
    // exercise the overdue path. "افتح الأقدم" opens the same action sheet a tap on the card would.
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => screen.getByText('افتح الأقدم'));
    expect(screen.getByText('حجزٌ واحد فات وقته ولم يُغلق بعد.')).toBeTruthy();
    screen.getByText('افتح الأقدم').click();
    await waitFor(() => expect(screen.getByText('حضر')).toBeTruthy());
  });

  it('opens an action sheet when a card is tapped', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => card());
    card().click();
    await waitFor(() => expect(screen.getByText('حضر')).toBeTruthy());
    expect(screen.getByText('لم يحضر')).toBeTruthy();
    expect(screen.getByText('إلغاء الحجز')).toBeTruthy();
  });

  it('marks attendance from the action sheet', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => card());
    card().click();
    await waitFor(() => screen.getByText('حضر'));
    screen.getByText('حضر').click();
    await waitFor(() => expect(asked.some((a) => a.fn === 'attendBooking')).toBe(true));
    expect(asked.find((a) => a.fn === 'attendBooking')?.args[1]).toBe('bkg_1');
  });

  it('cancels from the action sheet', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => card());
    card().click();
    await waitFor(() => screen.getByText('إلغاء الحجز'));
    screen.getByText('إلغاء الحجز').click();
    await waitFor(() => expect(asked.some((a) => a.fn === 'cancelBooking')).toBe(true));
  });

  it('filters visible cards by chip, with no new request', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    // TWO MATCHES BEFORE FILTERING: the booking card itself, and the same name as a <option> in
    // the filter row's own service select (always in the DOM — jsdom does not apply the `sm:`
    // breakpoint that picks inline-row-vs-mobile-chip at a real viewport width). Filtering the
    // card away leaves exactly the option.
    await waitFor(() => expect(screen.getAllByText(/قص شعر/)).toHaveLength(2));
    const before = asked.filter((a) => a.fn === 'listBookings').length;
    // BOOKING.payment_status is 'none', so "عربون" excludes the one card on screen — the same
    // outcome the old search-by-text test proved, now over a chip instead of a query.
    fireEvent.click(screen.getAllByText('عربون')[0]);
    await waitFor(() => expect(screen.getAllByText(/قص شعر/)).toHaveLength(1));
    expect(asked.filter((a) => a.fn === 'listBookings').length).toBe(before);
  });

  it('shows the deposit amount right on the card, not just a coloured dot', async () => {
    bookingsOverride = [{ ...BOOKING, payment_status: 'deposit', deposit_amount_minor: 5000 }];
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => screen.getByText('عربون 50'));
  });

  // "finds a customer's own booking by his phone number" removed with the phone-lookup filter —
  // `suggestByPrefix` never answers a real caller (search-service's public route requires a user
  // Bearer token, and `operations` sends the wrong credential for it), so the field only ever
  // showed a box that could never return a match. Pulled from the UI until the platform fix
  // (drafted, committed in `platform/`, awaiting Tamam's own release) actually ships.
});

describe('حجز جديد', () => {
  it('opens the booking dialog', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => screen.getByLabelText('حجز جديد'));
    screen.getByLabelText('حجز جديد').click();
    await waitFor(() => expect(screen.getByText(/جوّال العميل/)).toBeTruthy());
  });

  it('a deposit with no amount marks exactly that field red on a press, never disables «احجز»', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => screen.getByLabelText('حجز جديد'));
    screen.getByLabelText('حجز جديد').click();
    await waitFor(() => screen.getByRole('dialog'));
    const dialog = () => within(screen.getByRole('dialog'));

    dialog().getByText('عربون').click();
    await waitFor(() => dialog().getByLabelText(/^مبلغ العربون/));
    // «احجز» is always clickable — a fresh, entirely empty dialog is no exception.
    expect(dialog().getByText('احجز').closest('button')?.disabled).toBe(false);

    // A press with nothing filled in teaches, not just refuses — every empty required field
    // gets its own red line, the deposit amount among them.
    dialog().getByText('احجز').click();
    await waitFor(() => dialog().getByText('مبلغ العربون مطلوب'));
    expect(dialog().getByText('الجوال مطلوب')).toBeTruthy();
    expect(dialog().getByText('اختر خدمة واحدة على الأقل')).toBeTruthy();

    fireEvent.change(dialog().getByLabelText(/^مبلغ العربون/), { target: { value: '50' } });
    await waitFor(() => expect(dialog().queryByText('مبلغ العربون مطلوب')).toBeNull());
  });

  it('opens the same dialog from an empty cell click — no separate flow', async () => {
    const { container } = open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => card());
    // The column background itself, not a card — clicking a card opens the action sheet instead.
    const column = container.querySelectorAll('.border-s')[1];
    fireEvent.click(column);
    await waitFor(() => expect(screen.getByText(/جوّال العميل/)).toBeTruthy());
  });

  it('fixes a missing duration from inside the dialog, never sends him away', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => screen.getByLabelText('حجز جديد'));
    screen.getByLabelText('حجز جديد').click();
    await waitFor(() => screen.getByRole('dialog'));
    const dialog = () => within(screen.getByRole('dialog'));
    await waitFor(() => dialog().getByText('تلميع'));
    // svc2 ('تلميع') carries duration_minutes: 0 in the mock catalogue — picking it is what
    // triggers the fix row, the same refusal the server itself would make on save. Scoped to the
    // dialog: the filter row's own service <select> carries the same name as an <option>.
    dialog().getByText('تلميع').click();
    await waitFor(() => screen.getByText(/تلميع — بلا مدة مضبوطة/));

    fireEvent.change(screen.getByLabelText('مدة تلميع بالدقائق'), { target: { value: '20' } });
    screen.getByText('حفظ').click();

    await waitFor(() => expect(asked.some((a) => a.fn === 'setServiceDuration')).toBe(true));
    const call = asked.find((a) => a.fn === 'setServiceDuration');
    expect(call?.args[1]).toBe('svc2');
    expect(call?.args[2]).toBe(20);
    // The refusal is gone and the total now counts what was just saved — no refetch of the
    // whole catalogue needed for the dialog to reflect its own write.
    await waitFor(() => expect(screen.queryByText(/بلا مدة مضبوطة/)).toBeNull());
    expect(screen.getByText(/المدة الإجمالية: 20 دقيقة/)).toBeTruthy();
  });
});

describe('السحب والإفلات', () => {
  it('marks the card as being dragged the moment a drag starts', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => card());
    const cardEl = card().closest('[draggable="true"]') as HTMLElement;
    expect(cardEl.getAttribute('draggable')).toBe('true');

    fireEvent.dragStart(cardEl);
    await waitFor(() => expect(cardEl.className).toContain('rj-card-dragging'));
  });

  it('cards for a cancelled or closed booking are never draggable', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => card());
    card().click();
    await waitFor(() => screen.getByText('إلغاء الحجز'));
    screen.getByText('إلغاء الحجز').click();
    await waitFor(() => expect(asked.some((a) => a.fn === 'cancelBooking')).toBe(true));
    // A cancelled booking is filtered out of the grid entirely (§7) — nothing left to drag.
    expect(queryCard()).toBeNull();
  });
});

describe('احجز الجلسة القادمة', () => {
  it('offers the next session after marking attendance, when the service has a real cycle', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => card());
    card().click();
    await waitFor(() => screen.getByText('حضر'));
    screen.getByText('حضر').click();
    await waitFor(() => expect(screen.getByText(/احجز الجلسة القادمة/)).toBeTruthy());
  });

  it('opens the booking dialog with the customer already known — no phone search needed', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => card());
    card().click();
    await waitFor(() => screen.getByText('حضر'));
    screen.getByText('حضر').click();
    await waitFor(() => screen.getByText(/احجز الجلسة القادمة/));
    screen.getByText(/احجز الجلسة القادمة/).click();
    await waitFor(() => expect(screen.getByText(/عميل معروف/)).toBeTruthy());
  });
});

describe('booking dialog — Stage 8', () => {
  it('shows the no-show risk note once a known customer is picked, never before', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => screen.getByLabelText('حجز جديد'));
    screen.getByLabelText('حجز جديد').click();
    await waitFor(() => screen.getByText(/جوّال العميل/));
    expect(screen.queryByText(/غاب عن/)).toBeNull();
  });

  it('offers "أقرب فتحة" once the dialog is open', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => screen.getByLabelText('حجز جديد'));
    screen.getByLabelText('حجز جديد').click();
    await waitFor(() => expect(screen.getByText('أقرب فتحة')).toBeTruthy());
  });
});
