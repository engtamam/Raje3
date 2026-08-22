/**
 * «متأخر الدفع» honesty and «تحديث بطاقة الدفع» gating — audit gap #3, console side. The button
 * must stay invisible until BOTH the backend route exists in the catalogue AND this build can
 * actually mint a token — never rendered-and-refused.
 *
 * `canMintToken` (payment.ts) is frozen at module-load from `import.meta.env`, so every test here
 * stubs the env and re-imports Plans.tsx fresh via `vi.resetModules()` — same discipline as
 * payment.test.ts and card_form.test.tsx.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

const PLANS = [
  { id: 'base', name: 'الأساس', active: true, listed: true,
    prices: [{ interval: 'month', amount_minor: 9900, currency: 'SAR' }],
    limits: { 'messages.monthly': { kind: 'counter', limit: -1 } } },
];

let catalogActionIds: string[] = [];

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => (catalogActionIds.includes(id)
      ? { id, label: id, method: 'GET', path: `/${id}` } : undefined),
    call: async (_s: unknown, a: { id: string }) => {
      if (a.id === 'billing.plans') return { plans: PLANS };
      if (a.id === 'billing.my_subscriptions') {
        return { subscriptions: [{ id: 'sub_1', plan_id: 'base', status: 'past_due' }] };
      }
      if (a.id === 'subscription.payment_state') return { enabled: true };
      return {};
    },
  };
});

const session = {} as never;
const catalog = { services: [], unreachable: [] } as never;

async function open() {
  vi.resetModules();
  const { DENIED } = await import('../loading');
  const { PlansPane } = await import('./Plans');
  return render(<PlansPane session={session} catalog={catalog} owned={DENIED} onGoConnect={() => {}} />);
}

beforeEach(() => {
  catalogActionIds = ['billing.plans', 'billing.my_subscriptions', 'subscription.payment_state', 'billing.cancel'];
});

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
});

describe('past_due, said honestly', () => {
  it('shows «متأخر الدفع», never the generic «متوقف», when a charge is failing', async () => {
    await open();
    await screen.findByText('متأخر الدفع');
    expect(screen.queryByText('متوقف')).toBeNull();
    expect(screen.getByText(/حدّث بطاقتك/)).toBeTruthy();
  });
});

describe('«تحديث بطاقة الدفع» — never rendered-and-refused', () => {
  it('stays hidden while the backend has no update_payment_method action, even with a key configured', async () => {
    vi.stubEnv('VITE_MOYASAR_PUBLISHABLE_KEY', 'pk_test_abc');
    await open();
    await screen.findByText('متأخر الدفع');
    expect(screen.queryByRole('button', { name: 'تحديث بطاقة الدفع' })).toBeNull();
  });

  it('stays hidden with the action present but no publishable key configured', async () => {
    vi.stubEnv('VITE_MOYASAR_PUBLISHABLE_KEY', '');
    catalogActionIds.push('billing.update_payment_method');
    await open();
    await screen.findByText('متأخر الدفع');
    expect(screen.queryByRole('button', { name: 'تحديث بطاقة الدفع' })).toBeNull();
  });

  it('appears once both are true', async () => {
    vi.stubEnv('VITE_MOYASAR_PUBLISHABLE_KEY', 'pk_test_abc');
    catalogActionIds.push('billing.update_payment_method');
    await open();
    expect(await screen.findByRole('button', { name: 'تحديث بطاقة الدفع' })).toBeTruthy();
  });
});
