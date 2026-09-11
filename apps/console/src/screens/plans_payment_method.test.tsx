/**
 * «متأخر الدفع» honesty and «تحديث بطاقة الدفع» gating — audit gap #3, console side. The button
 * must stay invisible until BOTH the backend route exists in the catalogue AND this build can
 * actually mint a token — never rendered-and-refused.
 *
 * `canMintToken` (payment.ts) is frozen at module-load from `import.meta.env`, so every test here
 * stubs the env and re-imports Plans.tsx fresh via `vi.resetModules()` — same discipline as
 * payment.test.ts and card_form.test.tsx.
 *
 * NO BASE ROW ANY MORE (الأساس retired 2026-09-10) — every fixture here is an app subscription;
 * the past-due alert and «تحديث بطاقة الدفع» must work off ANY subscription, not a base-specific
 * one (see `pastDueSub` in Plans.tsx itself).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render as rtlRender, screen } from '@testing-library/react';

const PLANS = [
  { id: 'campaigns', name: 'الحملات', active: true, listed: true,
    prices: [{ interval: 'month', amount_minor: 9900, currency: 'SAR' }],
    limits: { 'feature.campaigns': { kind: 'boolean', limit: 1 } } },
];

let catalogActionIds: string[] = [];
let subscriptions: Array<{ id: string; plan_id: string; status: string }> =
  [{ id: 'sub_1', plan_id: 'campaigns', status: 'past_due' }];

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => (catalogActionIds.includes(id)
      ? { id, label: id, method: 'GET', path: `/${id}` } : undefined),
    call: async (_s: unknown, a: { id: string }) => {
      if (a.id === 'billing.plans') return { plans: PLANS };
      if (a.id === 'billing.my_subscriptions') return { subscriptions };
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
  // `vi.resetModules()` above means `./Plans` is a DIFFERENT module instance than any
  // `OperatorI18nProvider` imported at this file's top — re-import it fresh from the same graph.
  const { OperatorI18nProvider } = await import('../operator-i18n');
  return rtlRender(
    <OperatorI18nProvider session={session}>
      <PlansPane session={session} catalog={catalog} owned={DENIED} onGoConnect={() => {}} />
    </OperatorI18nProvider>,
  );
}

beforeEach(() => {
  catalogActionIds = ['billing.plans', 'billing.my_subscriptions', 'subscription.payment_state', 'billing.cancel'];
  subscriptions = [{ id: 'sub_1', plan_id: 'campaigns', status: 'past_due' }];
});

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
});

describe('past_due, said honestly', () => {
  it('shows the past-due alert banner when a charge is failing', async () => {
    await open();
    await screen.findByText(/حدّث بطاقتك/);
  });
});

describe('«تحديث بطاقة الدفع» — never rendered-and-refused', () => {
  it('stays hidden while the backend has no update_payment_method action, even with a key configured', async () => {
    vi.stubEnv('VITE_MOYASAR_PUBLISHABLE_KEY', 'pk_test_abc');
    await open();
    await screen.findByText(/حدّث بطاقتك/);
    expect(screen.queryByRole('button', { name: 'تحديث بطاقة الدفع' })).toBeNull();
  });

  it('stays hidden with the action present but no publishable key configured', async () => {
    vi.stubEnv('VITE_MOYASAR_PUBLISHABLE_KEY', '');
    catalogActionIds.push('billing.update_payment_method');
    await open();
    await screen.findByText(/حدّث بطاقتك/);
    expect(screen.queryByRole('button', { name: 'تحديث بطاقة الدفع' })).toBeNull();
  });

  it('appears once both are true', async () => {
    vi.stubEnv('VITE_MOYASAR_PUBLISHABLE_KEY', 'pk_test_abc');
    catalogActionIds.push('billing.update_payment_method');
    await open();
    expect(await screen.findByRole('button', { name: 'تحديث بطاقة الدفع' })).toBeTruthy();
  });
});

describe('a trialing subscription is not «متوقف» — confirmed bug (screenshot)', () => {
  it('reads «تجريبي» on the app card, not the generic «متوقف»', async () => {
    // billing-service's Subscription.status defaults to "trialing", not "active" — every
    // subscription starts here until its first run_cycle bills it. The status label only ever
    // recognised "active" as working and printed «متوقف» for everything else, including a
    // brand-new, perfectly healthy trial.
    subscriptions = [{ id: 'sub_1', plan_id: 'campaigns', status: 'trialing' }];
    await open();
    await screen.findByText('تجريبي');
    expect(screen.queryByText('متوقف')).toBeNull();
  });
});
