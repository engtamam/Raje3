/**
 * «بدّل الباقة» — audit gap #5. The switch button must only ever target the RIGHT base tier (not
 * every base card lighting up as owned the moment he owns any one of them), and must call
 * billing.change_plan rather than re-subscribing.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

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

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }, body?: unknown) => {
      if (a.id === 'billing.plans') return { plans: PLANS };
      if (a.id === 'billing.my_subscriptions') {
        return { subscriptions: [{ id: 'sub_1', plan_id: 'base_cheap', status: 'active' }] };
      }
      if (a.id === 'subscription.payment_state') return { enabled: true };
      if (a.id === 'billing.change_plan') { changeCalls.push(body); return { proration_minor: 6500 }; }
      return {};
    },
  };
});

const { PlansPane } = await import('./Plans');

afterEach(() => { cleanup(); changeCalls.length = 0; });

const session = {} as never;
const catalog = { services: [], unreachable: [] } as never;

function open() {
  return render(<PlansPane session={session} catalog={catalog} owned={OWNED} onGoConnect={() => {}} />);
}

describe('«بدّل الباقة»', () => {
  it('marks only the plan actually owned, and offers «بدّل إلى هذه» on the other tier', async () => {
    open();
    await screen.findAllByText('الأساس الموسّع');
    // The owned tier shows the settled badge, not a switch button.
    expect(screen.getByText('اشتراكك')).toBeTruthy();
    // The OTHER tier gets exactly one switch offer — not a second «فعّل الأساس».
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

  it('reports the computed proration as a fact, not a promise, and reports credit correctly', async () => {
    open();
    await screen.findAllByText('الأساس الموسّع');
    fireEvent.click(screen.getByRole('button', { name: 'بدّل إلى هذه' }));
    fireEvent.click(await screen.findByRole('button', { name: 'تأكيد التبديل' }));
    expect(await screen.findByText(/الفرق المحسوب لبقية هذه الفترة: 65 ريال إضافية/)).toBeTruthy();
  });
});
