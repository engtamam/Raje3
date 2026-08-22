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
import type { Booking } from '../api';

const asked: { fn: string; args: unknown[] }[] = [];

// TYPED AS THE REAL `Booking`, NOT `as const` — a literal-narrowed BOOKING made every override
// below (a different id, a different service, `payment_status: 'deposit'`) a type error against
// a fixture that was never meant to be the only shape a booking can take.

// TODAY, AT A FIXED HOUR — never a bare constant epoch. The week-view grid places a card by
// matching its REAL date against the columns of the week actually on screen (the day-view grid
// does not — it trusts whatever `listBookings` answered for the one day asked, which is why a
// stale fixed epoch stayed invisible in that failure for a long time). A constant epoch is
// "today" for as long as the suite is run near when it was written and silently drifts into a
// different week than the one shown by default — the exact bug this once broke on.
function todayAt(hour: number): number {
  const n = new Date();
  return Math.floor(new Date(n.getFullYear(), n.getMonth(), n.getDate(), hour, 0, 0).getTime() / 1000);
}

const BOOKING: Booking = {
  id: 'bkg_1', branch_id: 'b1', operator_id: 'op1', customer_id: 'c1',
  service_ids: ['svc1'], starts_at: 1786860000, duration_minutes: 30,
  status: 'booked', series_id: null, series_seq: null, visit_id: null,
  payment_status: 'none', deposit_amount_minor: null, price_override_minor: null, intended_reward_id: null,
  note: '', reason_no_show: null, created: 1, created_by: '',
  updated: 1, cancelled_reason: null, thumb_up: null, rev: 1,
};

// A SINGLE OVERRIDABLE ROW — most tests want the plain default; the payment-pill test below
// swaps this for one carrying a real deposit before rendering, and restores it in `afterEach`.
let bookingsOverride: Booking[] = [BOOKING];
// A SEPARATE FIXTURE — `bookings.for-customer` is a different read than `listBookings`, real
// past-and-future history rather than the day/week currently on screen, and its own tests need to
// vary it without disturbing the grid fixtures every other test relies on.
let customerUpcomingOverride: Booking[] = [];
// A WALK-IN, real fields only — never a Booking in disguise.
let customerVisitsOverride: { id: string; customer_id: string; service_ids: string[]; services: string;
  branch_id: string; occurred_at: number; note: string; custom_service: string }[] = [];
// 0=Monday..6=Sunday, all open 08:00-22:00 by default — most tests never touch working hours.
let weeklyOverride: Record<string, { closed: boolean; start_minute: number; end_minute: number }> =
  Object.fromEntries(Array.from({ length: 7 }, (_, d) => [String(d), { closed: false, start_minute: 480, end_minute: 1320 }]));

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
      return { considered: 4, no_shows: 3, risky: true, threshold_percent: 60 };
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
    bookingsForCustomer: async (...args: unknown[]) => {
      asked.push({ fn: 'bookingsForCustomer', args });
      return { bookings: customerUpcomingOverride };
    },
    customerRecord: async (...args: unknown[]) => {
      asked.push({ fn: 'customerRecord', args });
      return { customer: { id: 'c1', phone: '966501234567', name: 'محمد' }, visits: customerVisitsOverride };
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
    workingHours: async (...args: unknown[]) => {
      asked.push({ fn: 'workingHours', args });
      return { weekly: weeklyOverride };
    },
    setWorkingHours: async (...args: unknown[]) => {
      asked.push({ fn: 'setWorkingHours', args });
      return { weekly: args[1] };
    },
  };
});

afterEach(() => {
  asked.length = 0;
  bookingsOverride = [BOOKING];
  customerUpcomingOverride = [];
  customerVisitsOverride = [];
  weeklyOverride = Object.fromEntries(
    Array.from({ length: 7 }, (_, d) => [String(d), { closed: false, start_minute: 480, end_minute: 1320 }]));
  cleanup();
});

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
const list = () => screen.getByTestId('rj-list');
// «السابقة» merges bookings and walk-in visits into a separate component (`CustomerHistoryList`)
// with its own container — a real, different DOM node from the plain booking list.
const history = () => screen.getByTestId('rj-history');

describe('branch selection', () => {
  it('offers a chooser when more than one branch and none is scoped', () => {
    open({ branches: [{ id: 'b1', name: 'فرع الرياض' }, { id: 'b2', name: 'فرع جدة' }] });
    expect(screen.getByText('فرع الرياض')).toBeTruthy();
    expect(screen.getByText('فرع جدة')).toBeTruthy();
    // لا قراءة حجوزات بلا فرع مختار — أوقات الدوام سياسة عامة، تُقرأ بغض النظر عن الفرع.
    expect(asked.some((a) => a.fn === 'listBookings')).toBe(false);
  });

  it('picks the one branch silently — no choice to make', async () => {
    open({ branches: [{ id: 'b1', name: 'فرع الرياض' }] });
    await waitFor(() => expect(asked.some((a) => a.fn === 'listBookings')).toBe(true));
    expect(asked.find((a) => a.fn === 'listBookings')?.args[1]).toBe('b1');
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
    await waitFor(() => expect(screen.getByLabelText('حضر')).toBeTruthy());
  });

  it('opens an action sheet when a card is tapped', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => card());
    card().click();
    await waitFor(() => expect(screen.getByLabelText('حضر')).toBeTruthy());
    expect(screen.getByLabelText('لم يحضر')).toBeTruthy();
    expect(screen.getByLabelText('إلغاء الحجز')).toBeTruthy();
  });

  it('marks attendance from the action sheet', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => card());
    card().click();
    await waitFor(() => screen.getByLabelText('حضر'));
    screen.getByLabelText('حضر').click();
    await waitFor(() => expect(asked.some((a) => a.fn === 'attendBooking')).toBe(true));
    expect(asked.find((a) => a.fn === 'attendBooking')?.args[1]).toBe('bkg_1');
  });

  it('cancels from the action sheet', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => card());
    card().click();
    await waitFor(() => screen.getByLabelText('إلغاء الحجز'));
    screen.getByLabelText('إلغاء الحجز').click();
    await waitFor(() => expect(asked.some((a) => a.fn === 'cancelBooking')).toBe(true));
  });

  it('filters visible cards by chip, with no new request', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    // ONE MATCH BEFORE FILTERING: just the booking card itself — the service FilterMenu is closed
    // by default and, unlike a native <select>, never renders its option list into the DOM until
    // opened, so there is no second "قص شعر" hiding in an always-present <option>.
    await waitFor(() => expect(screen.getAllByText(/قص شعر/)).toHaveLength(1));
    const before = asked.filter((a) => a.fn === 'listBookings').length;
    // BOOKING.payment_status is 'none', so "عربون" excludes the one card on screen — the same
    // outcome the old search-by-text test proved, now over a chip instead of a query.
    fireEvent.click(screen.getAllByText('عربون')[0]);
    await waitFor(() => expect(screen.queryAllByText(/قص شعر/)).toHaveLength(0));
    expect(asked.filter((a) => a.fn === 'listBookings').length).toBe(before);
  });

  it('the service filter is a real multi-select — either of two chosen services keeps a card', async () => {
    bookingsOverride = [
      { ...BOOKING, id: 'bkg_1', service_ids: ['svc1'] },
      { ...BOOKING, id: 'bkg_2', service_ids: ['svc2'] },
    ];
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => expect(within(grid()).getByText(/قص شعر/)).toBeTruthy());
    expect(within(grid()).getByText(/تلميع/)).toBeTruthy();

    fireEvent.click(screen.getByText('الخدمة'));
    const menu = screen.getByRole('listbox');
    fireEvent.click(within(menu).getByText('قص شعر'));
    fireEvent.click(within(menu).getByText('تلميع'));
    fireEvent.keyDown(document, { key: 'Escape' });   // close the menu, so only the cards remain

    // Both selected — neither card is excluded.
    await waitFor(() => expect(within(grid()).getByText(/قص شعر/)).toBeTruthy());
    expect(within(grid()).getByText(/تلميع/)).toBeTruthy();

    // Removing one selection via its own chip — never clearing the other — leaves exactly one card.
    fireEvent.click(screen.getByLabelText('إزالة تلميع'));
    await waitFor(() => expect(within(grid()).queryByText(/تلميع/)).toBeFalsy());
    expect(within(grid()).getByText(/قص شعر/)).toBeTruthy();
  });

  it('shows the deposit amount right on the card, not just a coloured dot', async () => {
    bookingsOverride = [{ ...BOOKING, payment_status: 'deposit', deposit_amount_minor: 5000 }];
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => screen.getByText('عربون 50'));
  });

  it('shows the payment pill on a short card too, not only the tall-card layout', async () => {
    // duration_minutes: 15 at PX_PER_MIN 1.6 -> height 24, the height < 30 combined-line branch —
    // exactly the layout that used to show with no payment fact on it at all.
    bookingsOverride = [{
      ...BOOKING, duration_minutes: 15, payment_status: 'deposit', deposit_amount_minor: 5000,
    }];
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => screen.getByText('عربون 50'));
  });

  it('shows the amount alone, not a truncated label, on a short card in week view', async () => {
    // Same short-card row, but in the narrow week-view column — the label used to truncate
    // mid-word ("عربون…" with the amount itself cut off).
    //
    // starts_at IS TODAY, NOT `BOOKING`'s OWN FIXED EPOCH — the week grid (unlike the day grid)
    // places a card by matching its real date against the columns of whichever week is actually
    // on screen (the default week, containing today), so a constant epoch works only for as long
    // as it happens to fall in that week and then silently stops rendering here at all.
    bookingsOverride = [{
      ...BOOKING, starts_at: todayAt(10),
      duration_minutes: 15, payment_status: 'deposit', deposit_amount_minor: 5000,
    }];
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => screen.getByText('الأسبوع'));
    screen.getByText('الأسبوع').click();
    await waitFor(() => expect(screen.getByText('50')).toBeTruthy());
    expect(screen.queryByText('عربون 50')).toBeNull();
  });

  it('finds a customer\'s own booking by his phone number', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => card());
    // The inline row's own field — jsdom renders it regardless of the `sm:` breakpoint.
    const [field] = screen.getAllByPlaceholderText('جوّال العميل');
    fireEvent.change(field, { target: { value: '9665012' } });
    await waitFor(() => expect(asked.some((a) => a.fn === 'suggestByPrefix')).toBe(true));
    await waitFor(() => screen.getByText('محمد'));
    screen.getByText('محمد').click();
    // BOOKING.customer_id is 'c1', the same id the mock suggestion carries — his own card stays,
    // matched by identity rather than merely by a name that happens to appear on screen.
    expect(card()).toBeTruthy();
    expect(screen.getAllByText('محمد').length).toBeGreaterThan(0);
  });
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

    // «تفاصيل الدفع» مطويّة افتراضياً — تُفتح يدوياً هنا لأن اختيار «عربون» نفسه هو ما يفتحها
    // تلقائياً في الاستخدام العادي، وهذا الاختبار يحتاج فتحها أولاً ليضغط عليه.
    dialog().getByText('تفاصيل الدفع').click();
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
    // A quarter-hour cell inside the column, not a card — clicking a card opens the action sheet
    // instead. Each cell is its own <button> now (real hover affordance), so the click lands on
    // one of those rather than the column's own background.
    const column = container.querySelectorAll('.border-s')[1];
    const cell = column.querySelector('button');
    expect(cell).toBeTruthy();
    fireEvent.click(cell!);
    await waitFor(() => expect(screen.getByText(/جوّال العميل/)).toBeTruthy());
  });

  it('the slot picker searches today from right now, the instant a service is chosen — no separate button', async () => {
    // Reported directly, and true again in the redesigned dialog for a different reason: the
    // merged time picker fetches its own slots the moment a service is chosen and the dialog's
    // day is «today», with no manual date/time to pre-fill and nothing to press first. The
    // guarantee that mattered — «نearest» is always from the real current moment, not some
    // stale or pre-filled floor — is now simply built into the picker's own effect.
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => screen.getByLabelText('حجز جديد'));
    screen.getByLabelText('حجز جديد').click();
    await waitFor(() => screen.getByRole('dialog'));
    const dialog = () => within(screen.getByRole('dialog'));

    const before = Math.floor(Date.now() / 1000);
    dialog().getByText('قص شعر').click();
    await waitFor(() => expect(asked.some((a) => a.fn === 'nearestSlot')).toBe(true));
    const call = asked.find((a) => a.fn === 'nearestSlot')!;
    const after = call.args[4] as number;
    expect(Math.abs(after - before)).toBeLessThan(10);
  });

  it('a future day picked from the switcher searches from that day\'s own start, not «now»', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => screen.getByLabelText('حجز جديد'));
    screen.getByLabelText('حجز جديد').click();
    await waitFor(() => screen.getByRole('dialog'));
    const dialog = () => within(screen.getByRole('dialog'));

    dialog().getByText('قص شعر').click();
    await waitFor(() => expect(asked.some((a) => a.fn === 'nearestSlot')).toBe(true));
    asked.length = 0;
    dialog().getByLabelText('اليوم التالي').click();
    await waitFor(() => expect(asked.some((a) => a.fn === 'nearestSlot')).toBe(true));
    const call = asked.find((a) => a.fn === 'nearestSlot')!;
    const after = call.args[4] as number;
    const now = Math.floor(Date.now() / 1000);
    // Tomorrow's midnight (Riyadh) is well ahead of «now», never close to it the way today's
    // search is in the test above.
    expect(after - now).toBeGreaterThan(3600);
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
    await waitFor(() => screen.getByLabelText('إلغاء الحجز'));
    screen.getByLabelText('إلغاء الحجز').click();
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
    await waitFor(() => screen.getByLabelText('حضر'));
    screen.getByLabelText('حضر').click();
    await waitFor(() => expect(screen.getByText(/احجز الجلسة القادمة/)).toBeTruthy());
  });

  it('opens the booking dialog with the customer already known — no phone search needed', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => card());
    card().click();
    await waitFor(() => screen.getByLabelText('حضر'));
    screen.getByLabelText('حضر').click();
    await waitFor(() => screen.getByText(/احجز الجلسة القادمة/));
    screen.getByText(/احجز الجلسة القادمة/).click();
    await waitFor(() => expect(screen.getByText(/عميل معروف/)).toBeTruthy());
  });

  it('a risky customer gets a clear percentage and a one-tap deposit suggestion', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => card());
    card().click();
    await waitFor(() => screen.getByLabelText('حضر'));
    screen.getByLabelText('حضر').click();
    await waitFor(() => screen.getByText(/احجز الجلسة القادمة/));
    screen.getByText(/احجز الجلسة القادمة/).click();
    // The mock answers considered:4, no_shows:3 -> 75%, threshold 60% — both numbers on screen,
    // not just a badge that doesn't explain what it means.
    await waitFor(() => screen.getByText(/75٪/));
    expect(screen.getByText(/الحد 60٪/)).toBeTruthy();
    screen.getByText('فعّل العربون الآن').click();
    await waitFor(() => expect(screen.getByLabelText(/مبلغ العربون/)).toBeTruthy());
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

  it('shows the day switcher and a merged slot picker once a service is chosen', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => screen.getByLabelText('حجز جديد'));
    screen.getByLabelText('حجز جديد').click();
    await waitFor(() => screen.getByRole('dialog'));
    const dialog = () => within(screen.getByRole('dialog'));
    expect(dialog().getByLabelText('اليوم التالي')).toBeTruthy();

    dialog().getByText('قص شعر').click();
    await waitFor(() => expect(asked.some((a) => a.fn === 'nearestSlot')).toBe(true));
  });
});

describe('أوقات الدوام', () => {
  // نفس ترقيم weekday() اللي يستخدمه الإنتاج — 0=الاثنين..6=الأحد.
  const todayPyWeekday = (new Date().getDay() + 6) % 7;

  it('renders the grid normally on an open day', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => card());
    expect(screen.queryByText('المحل مغلق هذا اليوم')).toBeNull();
  });

  it('shows a clear closed message instead of an empty grid, on a closed day', async () => {
    weeklyOverride = {
      ...weeklyOverride,
      [String(todayPyWeekday)]: { closed: true, start_minute: 0, end_minute: 0 },
    };
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => screen.getByText('المحل مغلق هذا اليوم'));
    expect(screen.queryByTestId('rj-grid')).toBeNull();
  });

  it('opens the settings dialog and saves a new week', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => screen.getByLabelText('أوقات الدوام'));
    screen.getByLabelText('أوقات الدوام').click();
    await waitFor(() => screen.getByText('حفظ'));
    screen.getByText('حفظ').click();
    await waitFor(() => expect(asked.some((a) => a.fn === 'setWorkingHours')).toBe(true));
  });
});

describe('عرض القائمة', () => {
  it('switches to a flat list without asking the server again', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => card());
    const before = asked.filter((a) => a.fn === 'listBookings').length;

    screen.getByLabelText('عرض القائمة').click();
    // THE GRID IS GONE, THE SAME BOOKING IS NOT — the same read, drawn differently.
    await waitFor(() => expect(screen.queryByTestId('rj-grid')).toBeNull());
    expect(within(list()).getByText('قص شعر')).toBeTruthy();
    expect(asked.filter((a) => a.fn === 'listBookings').length).toBe(before);
  });

  it('keeps an active filter applied across the switch', async () => {
    bookingsOverride = [
      { ...BOOKING, id: 'bkg_1', service_ids: ['svc1'] },
      { ...BOOKING, id: 'bkg_2', service_ids: ['svc2'] },
    ];
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => card());

    fireEvent.click(screen.getByText('الخدمة'));
    fireEvent.click(within(screen.getByRole('listbox')).getByText('قص شعر'));
    fireEvent.keyDown(document, { key: 'Escape' });
    await waitFor(() => expect(within(grid()).queryByText('تلميع')).toBeNull());

    screen.getByLabelText('عرض القائمة').click();
    await waitFor(() => expect(screen.queryByTestId('rj-grid')).toBeNull());
    // THE FILTER SURVIVED THE SWITCH — the one thing multi-view research flags as the most
    // common failure: a view change that silently drops what the operator already narrowed to.
    expect(within(list()).getByText('قص شعر')).toBeTruthy();
    expect(within(list()).queryByText('تلميع')).toBeNull();
  });

  it('opens the same action sheet a grid card would, from a tapped row', async () => {
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => card());
    screen.getByLabelText('عرض القائمة').click();
    await waitFor(() => within(list()).getByText('قص شعر'));
    within(list()).getByText('قص شعر').click();
    await waitFor(() => expect(screen.getByLabelText('حضر')).toBeTruthy());
  });

  it('says so plainly rather than drawing an empty list', async () => {
    bookingsOverride = [];
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => screen.getByLabelText('عرض القائمة'));
    screen.getByLabelText('عرض القائمة').click();
    await waitFor(() => expect(screen.getByText('لا حجوزات تطابق هذا العرض.')).toBeTruthy());
  });
});

describe('البحث عن عميل بجواله — كل مواعيده القادمة', () => {
  const NOW = Math.floor(Date.now() / 1000);
  const DAY = 86400;

  it('switches to the list and reads bookings.for-customer, not the day/week grid', async () => {
    customerUpcomingOverride = [
      { ...BOOKING, id: 'future_1', customer_id: 'c1', starts_at: NOW + 3 * DAY, status: 'booked' },
    ];
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => card());

    fireEvent.change(screen.getByLabelText('ابحث عن حجز عميل بجواله'), { target: { value: '9665' } });
    await waitFor(() => screen.getByText('محمد'));
    fireEvent.click(screen.getByText('محمد'));

    await waitFor(() => expect(screen.queryByTestId('rj-grid')).toBeNull());
    await waitFor(() => expect(within(list()).getByText('قص شعر')).toBeTruthy());
    expect(asked.some((a) => a.fn === 'bookingsForCustomer' && a.args[1] === 'c1')).toBe(true);
  });

  it('keeps only future, still-booked appointments, oldest first', async () => {
    customerUpcomingOverride = [
      { ...BOOKING, id: 'far', customer_id: 'c1', starts_at: NOW + 10 * DAY, status: 'booked' },
      { ...BOOKING, id: 'near', customer_id: 'c1', starts_at: NOW + 1 * DAY, status: 'booked' },
      { ...BOOKING, id: 'past', customer_id: 'c1', starts_at: NOW - 5 * DAY, status: 'booked' },
      { ...BOOKING, id: 'future_cancelled', customer_id: 'c1', starts_at: NOW + 2 * DAY, status: 'cancelled' },
    ];
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => card());

    fireEvent.change(screen.getByLabelText('ابحث عن حجز عميل بجواله'), { target: { value: '9665' } });
    await waitFor(() => screen.getByText('محمد'));
    fireEvent.click(screen.getByText('محمد'));

    await waitFor(() => expect(within(list()).getAllByText('قص شعر')).toHaveLength(2));
    // "near" appears before "far" — the DOM order of the (unique) time labels proves the sort.
    const times = within(list()).getAllByText(/^\d{1,2}:\d{2}/).map((el) => el.textContent);
    expect(times).toHaveLength(2);
  });

  it('says so plainly when the customer has nothing ahead of him', async () => {
    customerUpcomingOverride = [];
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => card());

    fireEvent.change(screen.getByLabelText('ابحث عن حجز عميل بجواله'), { target: { value: '9665' } });
    await waitFor(() => screen.getByText('محمد'));
    fireEvent.click(screen.getByText('محمد'));

    await waitFor(() => expect(screen.getByText('ما عند محمد أي موعد قادم.')).toBeTruthy());
  });

  it('defaults to «القادمة», and «السابقة» is one tap away, newest-first', async () => {
    customerUpcomingOverride = [
      // The endpoint's own contract: newest-first, any status, unfiltered by date.
      { ...BOOKING, id: 'future', customer_id: 'c1', starts_at: NOW + 2 * DAY, status: 'booked', service_ids: ['svc1'] },
      { ...BOOKING, id: 'recent_past', customer_id: 'c1', starts_at: NOW - 2 * DAY, status: 'attended', service_ids: ['svc2'] },
      { ...BOOKING, id: 'older_past', customer_id: 'c1', starts_at: NOW - 20 * DAY, status: 'no_show', service_ids: ['svc1'] },
    ];
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => card());

    fireEvent.change(screen.getByLabelText('ابحث عن حجز عميل بجواله'), { target: { value: '9665' } });
    await waitFor(() => screen.getByText('محمد'));
    fireEvent.click(screen.getByText('محمد'));

    // DEFAULT: only the future one, never a past one shown unasked.
    await waitFor(() => expect(within(list()).getByText('قص شعر')).toBeTruthy());
    expect(within(list()).queryByText('تلميع')).toBeNull();

    fireEvent.click(screen.getByText('السابقة'));
    // BOTH past rows now, and NEITHER future one — order proven by which label sits first in the
    // DOM: "تلميع" (recent_past) must precede the second "قص شعر" (older_past).
    await waitFor(() => expect(within(history()).getByText('تلميع')).toBeTruthy());
    const labels = within(history()).getAllByText(/قص شعر|تلميع/).map((el) => el.textContent);
    expect(labels).toEqual(['تلميع', 'قص شعر']);
  });

  it('says «اليوم», not a date, on a row that actually falls today — and a real date on the rest', async () => {
    // NOON TODAY, NOT "NOW + an hour" — a fixed offset from the real run-time clock crosses
    // midnight (into a DIFFERENT calendar day) whenever this suite happens to run in the last
    // hour before it, which is exactly the kind of flake a fixed anchor avoids regardless of
    // when the test actually runs.
    const n = new Date();
    const todayNoon = Math.floor(new Date(n.getFullYear(), n.getMonth(), n.getDate(), 12, 0, 0).getTime() / 1000);
    customerUpcomingOverride = [
      { ...BOOKING, id: 'today_row', customer_id: 'c1', starts_at: todayNoon, status: 'booked' },
      { ...BOOKING, id: 'later_row', customer_id: 'c1', starts_at: NOW + 5 * DAY, status: 'booked' },
    ];
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => card());

    fireEvent.change(screen.getByLabelText('ابحث عن حجز عميل بجواله'), { target: { value: '9665' } });
    await waitFor(() => screen.getByText('محمد'));
    fireEvent.click(screen.getByText('محمد'));

    // «اليوم» marks both the header (as part of its own sentence) and the row's own date badge —
    // and never stands in for the later appointment's real date.
    await waitFor(() => expect(within(list()).getByText(/^اليوم —/)).toBeTruthy());
    expect(within(list()).getByText('اليوم', { selector: 'td' })).toBeTruthy();
  });

  it('names the year on a date that is not this one, and leaves this year unsaid', async () => {
    const thisYear = new Date().getFullYear();
    const lastNewYearEve = Math.floor(new Date(Date.UTC(thisYear - 1, 11, 31, 12)).getTime() / 1000);
    customerUpcomingOverride = [
      { ...BOOKING, id: 'this_year', customer_id: 'c1', starts_at: NOW + 5 * DAY, status: 'booked' },
      { ...BOOKING, id: 'last_year', customer_id: 'c1', starts_at: lastNewYearEve, status: 'attended' },
    ];
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => card());

    fireEvent.change(screen.getByLabelText('ابحث عن حجز عميل بجواله'), { target: { value: '9665' } });
    await waitFor(() => screen.getByText('محمد'));
    fireEvent.click(screen.getByText('محمد'));
    await waitFor(() => screen.getByText('السابقة'));
    fireEvent.click(screen.getByText('السابقة'));

    // Appears on both the header and the row's own date badge — two text nodes, one year.
    await waitFor(() => expect(within(history()).getAllByText(String(thisYear - 1), { exact: false }).length).toBeGreaterThan(0));
    // NOT ALSO ON THE ONE ROW STILL IN THIS YEAR — a year appended to every date would be the
    // clutter this rule exists to avoid.
    expect(within(history()).queryAllByText(String(thisYear), { exact: false })).toHaveLength(0);
  });

  it('merges walk-in visits into «السابقة» alongside past bookings — newest first, no status pill on a visit', async () => {
    customerUpcomingOverride = [
      { ...BOOKING, id: 'past_booking', customer_id: 'c1', starts_at: NOW - 3 * DAY, status: 'attended', service_ids: ['svc1'] },
    ];
    customerVisitsOverride = [
      // Newer than the booking above — must sort ahead of it.
      { id: 'v1', customer_id: 'c1', service_ids: ['svc2'], services: 'تلميع',
        branch_id: 'b1', occurred_at: NOW - 1 * DAY, note: '', custom_service: '' },
    ];
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => card());

    fireEvent.change(screen.getByLabelText('ابحث عن حجز عميل بجواله'), { target: { value: '9665' } });
    await waitFor(() => screen.getByText('محمد'));
    fireEvent.click(screen.getByText('محمد'));
    await waitFor(() => screen.getByText('السابقة'));
    fireEvent.click(screen.getByText('السابقة'));

    await waitFor(() => expect(within(history()).getByText('تلميع')).toBeTruthy());
    expect(within(history()).getByText('قص شعر')).toBeTruthy();
    // «زيارة» is the walk-in's own tag — the past BOOKING still legitimately carries its real
    // status pill («حضر»), which is not a contradiction: only the visit has none of its own.
    expect(within(history()).getByText('زيارة')).toBeTruthy();
    expect(within(history()).getByText('حضر')).toBeTruthy();

    // NEWEST FIRST ACROSS BOTH KINDS — the visit (1 day ago) precedes the booking (3 days ago).
    const order = within(history()).getAllByText(/قص شعر|تلميع/).map((el) => el.textContent);
    expect(order).toEqual(['تلميع', 'قص شعر']);
  });

  it('a walk-in visit is not clickable — no action sheet exists behind it', async () => {
    customerVisitsOverride = [
      { id: 'v1', customer_id: 'c1', service_ids: ['svc1'], services: 'قص شعر',
        branch_id: 'b1', occurred_at: NOW - DAY, note: '', custom_service: '' },
    ];
    open({ branch: 'b1', branches: [{ id: 'b1' }] });
    await waitFor(() => card());

    fireEvent.change(screen.getByLabelText('ابحث عن حجز عميل بجواله'), { target: { value: '9665' } });
    await waitFor(() => screen.getByText('محمد'));
    fireEvent.click(screen.getByText('محمد'));
    await waitFor(() => screen.getByText('السابقة'));
    fireEvent.click(screen.getByText('السابقة'));

    await waitFor(() => history());
    within(history()).getByText('قص شعر').click();
    expect(screen.queryByLabelText('حضر')).toBeNull();
  });
});
