/**
 * «إضافة موظفين/فروع» — the capacity add-on stepper (+/-), Odoo-style per-unit licensing on ONE
 * subscription rather than a repeated «أضِف» purchasing a new row each time.
 *
 * THE FIRST UNIT (nothing owned yet) still goes through the ordinary card-form purchase — a real
 * subscription needs a payment token the first time — so pressing + at quantity 0 is only asserted
 * to open the card form with `quantity: 1` remembered; `card_form.test.tsx` already covers the
 * token mechanics themselves. EVERY UNIT AFTER THAT is `billing.change_plan` on the SAME
 * subscription id with a new `quantity` — no second row, ever.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render as rtlRender, screen } from '@testing-library/react';

const PLANS = [
  { id: 'base', name: 'الأساس', active: true, listed: true,
    prices: [{ interval: 'month', amount_minor: 9900, currency: 'SAR' }],
    limits: { 'messages.monthly': { kind: 'counter', limit: 500 } } },
  { id: 'seat_pack', name: 'موظف إضافي', active: true, listed: true,
    prices: [{ interval: 'month', amount_minor: 5000, currency: 'SAR' }],
    limits: { 'staff.seats': { kind: 'gauge', limit: 1 } } },
];

const OWNED = { checked: true, message: '', keys: [], apps: [],
                base: { plan_id: 'base', status: 'active', renews_at: 0 } };

const changeCalls: unknown[] = [];
const cancelCalls: unknown[] = [];
// Mutable per test — the capacity row's own subscription, or none at all.
let seatSub: { id: string; plan_id: string; status: string; quantity?: number } | null = null;

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }, body?: unknown) => {
      if (a.id === 'billing.plans') return { plans: PLANS };
      if (a.id === 'billing.my_subscriptions') {
        const subs = [{ id: 'sub_base', plan_id: 'base', status: 'active' }];
        if (seatSub) subs.push(seatSub);
        return { subscriptions: subs };
      }
      if (a.id === 'subscription.payment_state') return { enabled: true };
      if (a.id === 'billing.change_plan') {
        changeCalls.push(body);
        const b = body as { quantity: number };
        if (seatSub) seatSub = { ...seatSub, quantity: b.quantity };
        return { applied: 'upgraded', proration_minor: 0 };
      }
      if (a.id === 'billing.cancel') {
        cancelCalls.push(body);
        seatSub = null;
        return { cancelled: true };
      }
      return {};
    },
  };
});

async function open() {
  vi.resetModules();
  vi.stubEnv('VITE_MOYASAR_PUBLISHABLE_KEY', 'pk_test_abc');
  const { PlansPane } = await import('./Plans');
  // `vi.resetModules()` above means `./Plans` (and everything it imports, including operator-i18n's
  // own `createContext`) is a DIFFERENT module instance — a provider imported at this file's top
  // cannot satisfy `useOperatorI18n()` inside the freshly-imported `PlansPane`. Re-import the
  // provider fresh too, from the same module graph `PlansPane` was just pulled from.
  const { OperatorI18nProvider } = await import('../operator-i18n');
  return rtlRender(
    <OperatorI18nProvider session={{} as never}>
      <PlansPane session={{} as never} catalog={{ services: [], unreachable: [] } as never}
                 owned={OWNED} onGoConnect={() => {}} />
    </OperatorI18nProvider>,
  );
}

beforeEach(() => { seatSub = null; });
afterEach(() => {
  cleanup(); changeCalls.length = 0; cancelCalls.length = 0;
  vi.unstubAllEnvs(); vi.restoreAllMocks();
});

describe('capacity add-on — nothing bought yet', () => {
  it('reads as quantity 0, and pressing + opens the card form remembering quantity 1', async () => {
    await open();
    await screen.findByText('موظف إضافي');
    expect(screen.getByText('0')).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'زيادة مقعد' }));
    // The card form only opens for a real purchase — proves `choose(plan, 1)` fired, not
    // `billing.change_plan` (there is no subscription yet to change).
    expect(await screen.findByLabelText('رقم البطاقة')).toBeTruthy();
    expect(changeCalls).toEqual([]);
  });
});

describe('capacity add-on — already holds 2 units', () => {
  beforeEach(() => { seatSub = { id: 'sub_seat', plan_id: 'seat_pack', status: 'active', quantity: 2 }; });

  it('shows the quantity and the unit price times it', async () => {
    await open();
    await screen.findByText('موظف إضافي');
    expect(screen.getByText('2')).toBeTruthy();
    expect(screen.getByText('100 ريال')).toBeTruthy();   // 2 × 50
  });

  it('+ calls billing.change_plan on the SAME subscription id with quantity 3', async () => {
    await open();
    await screen.findByText('موظف إضافي');
    fireEvent.click(screen.getByRole('button', { name: 'زيادة مقعد' }));
    await vi.waitFor(() => expect(changeCalls).toEqual(
      [{ id: 'sub_seat', plan_id: 'seat_pack', quantity: 3 }]));
  });

  it('- calls billing.change_plan with quantity 1 (never a new row, never a cancel)', async () => {
    await open();
    await screen.findByText('موظف إضافي');
    fireEvent.click(screen.getByRole('button', { name: 'إنقاص مقعد' }));
    await vi.waitFor(() => expect(changeCalls).toEqual(
      [{ id: 'sub_seat', plan_id: 'seat_pack', quantity: 1 }]));
    expect(cancelCalls).toEqual([]);
  });
});

describe('capacity add-on — down to the last unit', () => {
  beforeEach(() => { seatSub = { id: 'sub_seat', plan_id: 'seat_pack', status: 'active', quantity: 1 }; });

  it('- opens the confirm dialog instead of calling change_plan with quantity 0', async () => {
    await open();
    await screen.findByText('موظف إضافي');
    fireEvent.click(screen.getByRole('button', { name: 'إنقاص مقعد' }));
    expect(await screen.findByText(/تأكيد إيقاف تجديد «موظف إضافي»/)).toBeTruthy();
    expect(changeCalls).toEqual([]);

    fireEvent.click(screen.getByRole('button', { name: 'تأكيد إيقاف التجديد' }));
    await vi.waitFor(() => expect(cancelCalls).toEqual([{ id: 'sub_seat' }]));
  });
});
