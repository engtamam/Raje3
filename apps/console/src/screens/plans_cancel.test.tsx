/**
 * «إلغاء الاشتراك» — the self-service cancel button that did not exist (audit #2, 2026-08-22).
 * billing-service's cancel route was complete and reachable; nothing in this console ever called
 * it. These pin: the button targets the BASE subscription specifically (never an app row), asks
 * for confirmation before acting, and the screen reflects a pending cancellation honestly.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { DENIED } from '../loading';

const PLANS = [
  { id: 'base', name: 'الأساس', active: true, listed: true,
    prices: [{ interval: 'month', amount_minor: 9900, currency: 'SAR' }],
    limits: { 'messages.monthly': { kind: 'counter', limit: -1 } } },
];

let subs: Array<{ id: string; plan_id: string; status: string;
  current_period_end: number; cancel_at_period_end: boolean }> = [
  { id: 'sub_1', plan_id: 'base', status: 'active',
    current_period_end: Math.floor(Date.UTC(2026, 8, 20) / 1000), cancel_at_period_end: false },
];

const cancelCalls: unknown[] = [];

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }, body?: unknown) => {
      if (a.id === 'billing.plans') return { plans: PLANS };
      if (a.id === 'billing.my_subscriptions') return { subscriptions: subs };
      if (a.id === 'subscription.payment_state') return { enabled: true };
      if (a.id === 'billing.cancel') {
        cancelCalls.push(body);
        subs = subs.map((s) => (s.id === 'sub_1' ? { ...s, cancel_at_period_end: true } : s));
        return { id: 'sub_1', cancel_at_period_end: true };
      }
      return {};
    },
  };
});

const { PlansPane } = await import('./Plans');

afterEach(cleanup);

const session = {} as never;
const catalog = { services: [], unreachable: [] } as never;

function open() {
  return render(<PlansPane session={session} catalog={catalog} owned={DENIED} onGoConnect={() => {}} />);
}

describe('«إلغاء الاشتراك»', () => {
  it('asks for confirmation before cancelling, and cancels the BASE by its subscription id', async () => {
    open();
    const btn = await screen.findByRole('button', { name: 'إلغاء الاشتراك' });
    // Not yet acted on — no call fired by rendering the button alone.
    expect(cancelCalls.length).toBe(0);

    fireEvent.click(btn);
    await screen.findByText('تأكيد إلغاء الاشتراك');
    // The date already on the summary card is repeated in the confirmation — no surprise later.
    expect(screen.getByText(/يستمر محلّك يعمل بلا أي تغيير حتى/)).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'تأكيد الإلغاء' }));
    await screen.findByText('قيد الإلغاء');
    expect(cancelCalls).toEqual([{ id: 'sub_1' }]);
    // The button is gone once cancellation is pending — pressing it twice is not offered.
    expect(screen.queryByRole('button', { name: 'إلغاء الاشتراك' })).toBeNull();
  });

  it('backs out cleanly on «تراجع» without calling anything', async () => {
    cancelCalls.length = 0;
    subs = [{ id: 'sub_1', plan_id: 'base', status: 'active',
             current_period_end: Math.floor(Date.UTC(2026, 8, 20) / 1000), cancel_at_period_end: false }];
    open();
    fireEvent.click(await screen.findByRole('button', { name: 'إلغاء الاشتراك' }));
    await screen.findByText('تأكيد إلغاء الاشتراك');
    fireEvent.click(screen.getByRole('button', { name: 'تراجع' }));
    expect(screen.queryByText('تأكيد إلغاء الاشتراك')).toBeNull();
    expect(cancelCalls.length).toBe(0);
  });
});
