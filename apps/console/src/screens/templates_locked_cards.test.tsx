/**
 * «القوالب» — a card for an app the shop has NOT bought renders LOCKED (Locked.tsx's own
 * `AppGate`/`LockedCard`), never hidden. `booking_confirmed` needs `feature.bookings`;
 * `rating_requested` needs `feature.rating` — neither reason's OWN `source` field alone was
 * enough for `rating_requested` (it carries none), so Messages.tsx names its app by hand.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const REASONS = [
  { id: 'booking_confirmed', label: 'تأكيد حجز', when: 'بعد الحجز',
    cls: 'service', cls_label: 'خدمية', on: true, can_switch: true },
  { id: 'rating_requested', label: 'طُلب تقييم', when: 'بدل التأكيد العادي',
    cls: 'service', cls_label: 'خدمية', on: true, can_switch: true },
  { id: 'visit_recorded', label: 'سُجّلت زيارة', when: 'بعد الزيارة',
    cls: 'service', cls_label: 'خدمية', on: true, can_switch: true },
];

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }) => {
      if (a.id === 'reminders.reasons') return { reasons: REASONS };
      return {};
    },
  };
});

const { MessagesScreen } = await import('./Messages');

afterEach(cleanup);

const session = {} as never;
const catalog = { services: [], unreachable: [] } as never;

// A shop that owns NEITHER the bookings NOR the rating app.
const owned = {
  checked: true, message: '', keys: [], apps: [], base: null,
} as never;

function open() {
  return render(
    <MemoryRouter><MessagesScreen session={session} catalog={catalog} owned={owned} /></MemoryRouter>,
  );
}

describe('«القوالب» — locked cards for an app the shop has not bought', () => {
  it('locks the booking-confirmation card, offering the store link rather than the text', async () => {
    open();
    await screen.findAllByText('سُجّلت زيارة');
    expect(screen.queryByText('تأكيد حجز')).toBeNull();
    expect(screen.getAllByText('أضِفه من متجر التطبيقات').length).toBeGreaterThan(0);
  });

  it('locks the rating-request card the same way', async () => {
    open();
    await screen.findAllByText('سُجّلت زيارة');
    expect(screen.queryByText('طُلب تقييم')).toBeNull();
  });

  it('never locks an ordinary card that needs no extra app', async () => {
    open();
    expect(await screen.findAllByText('سُجّلت زيارة')).toBeTruthy();
  });
});
