/**
 * «تبديل الاشتراك الأساسي» — audit gap #5, now on the v0.16.33 Stripe-style split («مافي
 * رصيد سالب أو استرداد إطلاقاً»). An UPGRADE charges the prorated difference and switches
 * immediately; a DOWNGRADE schedules the same target for the next renewal at full price and
 * touches nothing now — never a credit, never a negative balance. Both directions are offered;
 * only the label, the confirmation text, and what happens on confirm differ.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render as rtlRender, screen } from '@testing-library/react';
import type { ReactElement } from 'react';
import { OperatorI18nProvider } from '../operator-i18n';

// `hasBase` inside Plans.tsx reads from THIS prop (the entitlements view), not from
// billing.my_subscriptions — a shop with a real base subscription still needs `checked: true`
// and a truthy `base` here for the card to read as owned at all.
const OWNED = { checked: true, message: '', keys: [], apps: [],
                base: { plan_id: 'base_cheap', status: 'active', renews_at: 0 } };

const PLANS = [
  { id: 'base_cheap', name: 'الأساس', active: true, listed: true,
    prices: [{ interval: 'month', amount_minor: 9900, currency: 'SAR' }],
    limits: { 'messages.monthly': { kind: 'counter', limit: 500 } } },
  { id: 'base_pro', name: 'الأساس الموسّع', active: true, listed: true,
    prices: [{ interval: 'month', amount_minor: 19900, currency: 'SAR' }],
    limits: { 'messages.monthly': { kind: 'counter', limit: 2000 } } },
];

const changeCalls: unknown[] = [];
const cancelScheduledCalls: unknown[] = [];
// WHICH BASE `billing.my_subscriptions` ANSWERS WITH, AND WHAT IT HAS SCHEDULED — mutable per
// test, because `hasBase` (the `owned` prop) and `baseSub` (this) are two SEPARATE reads in the
// real app and must agree with each other for a test to say anything real about either.
let currentPlanId = 'base_cheap';
let pendingPlanId = '';

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }, body?: unknown) => {
      if (a.id === 'billing.plans') return { plans: PLANS };
      if (a.id === 'billing.my_subscriptions') {
        return { subscriptions: [{ id: 'sub_1', plan_id: currentPlanId, status: 'active',
                                    pending_plan_id: pendingPlanId }] };
      }
      if (a.id === 'subscription.payment_state') return { enabled: true };
      if (a.id === 'billing.change_plan') {
        changeCalls.push(body);
        const target = PLANS.find((p) => p.id === (body as { plan_id: string }).plan_id);
        const current = PLANS.find((p) => p.id === currentPlanId);
        const isUpgrade = (target?.prices[0].amount_minor ?? 0) >= (current?.prices[0].amount_minor ?? 0);
        if (isUpgrade) return { applied: 'upgraded', proration_minor: 6500 };
        pendingPlanId = target?.id ?? '';
        return { applied: 'scheduled_downgrade', pending_plan_id: pendingPlanId, proration_minor: 0 };
      }
      if (a.id === 'billing.cancel_scheduled_change') {
        cancelScheduledCalls.push(body);
        pendingPlanId = '';
        return { cancelled_scheduled_change: true };
      }
      return {};
    },
  };
});

const { PlansPane } = await import('./Plans');

afterEach(() => {
  cleanup(); changeCalls.length = 0; cancelScheduledCalls.length = 0;
  currentPlanId = 'base_cheap'; pendingPlanId = '';
});

const session = {} as never;

// PlansPane now reads `useOperatorI18n()` — wrap once so every existing `render(<...>)` call
// site below stays unchanged.
function render(ui: ReactElement) {
  return rtlRender(<OperatorI18nProvider session={session}>{ui}</OperatorI18nProvider>);
}
const catalog = { services: [], unreachable: [] } as never;

function open() {
  return render(<PlansPane session={session} catalog={catalog} owned={OWNED} onGoConnect={() => {}} />);
}

describe('«تبديل الاشتراك الأساسي» — upgrade', () => {
  it('marks only the plan actually owned, and offers «بدّل إلى هذه» on the higher tier', async () => {
    open();
    await screen.findAllByText('الأساس الموسّع');
    // The owned tier shows its honest status badge (now carrying what the deleted summary
    // card used to say), not a switch button.
    expect(screen.getByText('فعّال')).toBeTruthy();
    // The higher tier gets exactly one switch offer — not a second «فعّل الأساس».
    expect(screen.getAllByRole('button', { name: 'بدّل إلى هذه' })).toHaveLength(1);
    expect(screen.queryByRole('button', { name: 'فعّل الأساس' })).toBeNull();
  });

  it('confirms, then calls billing.change_plan with the base subscription id and the new plan id', async () => {
    open();
    await screen.findAllByText('الأساس الموسّع');
    fireEvent.click(screen.getByRole('button', { name: 'بدّل إلى هذه' }));
    await screen.findByText(/تأكيد التبديل إلى «الأساس الموسّع»/);

    fireEvent.click(screen.getByRole('button', { name: 'تأكيد التبديل' }));
    await screen.findByText('تم التبديل ✓');
    expect(changeCalls).toEqual([{ id: 'sub_1', plan_id: 'base_pro' }]);
  });

  it('states the upgrade as an immediate charge, and the result as a real collection (v0.16.33)', async () => {
    open();
    await screen.findAllByText('الأساس الموسّع');
    fireEvent.click(screen.getByRole('button', { name: 'بدّل إلى هذه' }));
    expect(await screen.findByText(/بعد تحصيل فرق السعر لبقية هذه الفترة من بطاقتك/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'تأكيد التبديل' }));
    expect(await screen.findByText(/حُصِّل 65 ريال فرق السعر لبقية هذه الفترة/)).toBeTruthy();
  });
});

describe('«تبديل الاشتراك الأساسي» — downgrade, scheduled at renewal, never a credit (v0.16.33)', () => {
  it('offers «جدولة التبديل عند التجديد» toward a cheaper base tier — no longer hidden', async () => {
    // Owns the EXPENSIVE tier now — the other listed tier is a downgrade. Both the entitlements
    // view AND billing.my_subscriptions have to agree it's base_pro, same as the real app.
    currentPlanId = 'base_pro';
    const ownedPro = { checked: true, message: '', keys: [], apps: [],
                       base: { plan_id: 'base_pro', status: 'active', renews_at: 0 } };
    render(<PlansPane session={session} catalog={catalog} owned={ownedPro} onGoConnect={() => {}} />);
    await screen.findAllByText('الأساس');
    expect(screen.getByRole('button', { name: 'جدولة التبديل عند التجديد' })).toBeTruthy();
  });

  it('confirms with the «لا يُخصم شيء الآن» promise, schedules it, and shows «تراجع» on the owned card', async () => {
    currentPlanId = 'base_pro';
    const ownedPro = { checked: true, message: '', keys: [], apps: [],
                       base: { plan_id: 'base_pro', status: 'active', renews_at: 0 } };
    render(<PlansPane session={session} catalog={catalog} owned={ownedPro} onGoConnect={() => {}} />);
    await screen.findAllByText('الأساس');
    fireEvent.click(screen.getByRole('button', { name: 'جدولة التبديل عند التجديد' }));
    // The one thing he must know before confirming: nothing is charged or credited today.
    expect(await screen.findByText(/لا يُخصم شيء الآن/)).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'تأكيد التبديل' }));
    await screen.findByText('تم التبديل ✓');
    expect(changeCalls).toEqual([{ id: 'sub_1', plan_id: 'base_cheap' }]);
    // «تراجع عن التبديل» now lives on the card he still owns — the subscription he keeps until renewal.
    expect(await screen.findByRole('button', { name: 'تراجع عن التبديل' })).toBeTruthy();
  });

  it('«تراجع عن التبديل» calls billing.cancel_scheduled_change with the base subscription id', async () => {
    currentPlanId = 'base_pro';
    pendingPlanId = 'base_cheap';
    const ownedPro = { checked: true, message: '', keys: [], apps: [],
                       base: { plan_id: 'base_pro', status: 'active', renews_at: 0 } };
    render(<PlansPane session={session} catalog={catalog} owned={ownedPro} onGoConnect={() => {}} />);
    fireEvent.click(await screen.findByRole('button', { name: 'تراجع عن التبديل' }));
    await vi.waitFor(() => expect(cancelScheduledCalls).toEqual([{ id: 'sub_1' }]));
  });
});
