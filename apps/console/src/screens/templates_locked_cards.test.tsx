/**
 * «القوالب» — a card for an app the shop has NOT bought stays FULLY VISIBLE and previewable, with
 * the app's own real feature list + buy link (Locked.tsx's own `LockedCard`) ALONGSIDE it — never
 * swapped away for a generic upsell card, which is what this used to do (owner's own words:
 * "حتى لو مقفلة العرض المفروض يكون متاح بحيث يشوفها ويجربها ويتحمس يشتريها"). Only the on/off
 * switch is replaced, since turning on a send he cannot pay for makes no sense; the card's own
 * label, its preview button, and the buy-this-app pitch all show at once.
 * `booking_confirmed` needs `feature.bookings`; `rating_requested` needs `feature.rating` —
 * neither reason's OWN `source` field alone was enough for `rating_requested` (it carries none),
 * so Messages.tsx names its app by hand.
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

describe('«القوالب» — a locked card stays visible and previewable, with the pitch beside it', () => {
  it('shows the booking-confirmation card itself AND the store pitch, never one instead of the other', async () => {
    open();
    await screen.findAllByText('سُجّلت زيارة');
    // THE CARD ITSELF — still there, still readable, still openable for a real preview.
    expect(await screen.findByText('تأكيد حجز')).toBeTruthy();
    // AND THE PITCH TO BUY IT — same card row, not a substitute for it.
    expect(screen.getAllByText('أضِفه من متجر التطبيقات').length).toBeGreaterThan(0);
    // THE SWITCH IS WHAT ACTUALLY LOCKS — turning on a send he cannot pay for makes no sense.
    expect(screen.getAllByText('بعد الشراء').length).toBeGreaterThan(0);
  });

  it('shows the rating-request card the same way', async () => {
    open();
    await screen.findAllByText('سُجّلت زيارة');
    expect(await screen.findByText('طُلب تقييم')).toBeTruthy();
  });

  it('never shows the store pitch beside an ordinary card that needs no extra app', async () => {
    open();
    await screen.findAllByText('سُجّلت زيارة');
    // Only two locked cards on this shop (booking + rating) — سُجّلت زيارة itself needs nothing.
    expect(screen.getAllByText('أضِفه من متجر التطبيقات').length).toBe(2);
  });
});
