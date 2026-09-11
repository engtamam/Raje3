/**
 * «BookingDialog» — a failed earn/offer/balance read used to start `null`, the same value its own
 * `.catch(() => setX(null))` set on failure, so a customer with a live offer or redeemable reward
 * whose read simply failed looked exactly like one with neither — nothing was ever shown, and
 * nobody was ever told the read had failed (م · النمط 1).
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render as rtlRender, screen, waitFor } from '@testing-library/react';
import type { CustomerHit } from '../api';
import { OperatorI18nProvider } from '../operator-i18n';

let earnMock: () => Promise<unknown>;
let customerByPhoneMock: () => Promise<unknown>;

vi.mock('../api', async (importOriginal) => {
  const real = await importOriginal<typeof import('../api')>();
  return {
    ...real,
    earnSettings: (...args: unknown[]) => earnMock(),
    customerByPhone: (...args: unknown[]) => customerByPhoneMock(),
    offerFor: () => Promise.resolve({ service_ids: [] }),
    balanceFor: () => Promise.resolve({ points: 0, rewards: [], to_next_reward: 0 }),
    noShowRisk: () => Promise.resolve(null),
    suggestByPrefix: () => Promise.resolve([]),
  };
});

const { BookingDialog } = await import('./BookingDialog');

afterEach(() => { cleanup(); vi.clearAllMocks(); });

const CUSTOMER: CustomerHit = { id: 'cus1', phone: '0500000001', name: 'سالم' };
const SERVICES = [
  { id: 'svc1', name: 'قص شعر', duration_minutes: 30, price_minor: 5000, active: true },
];

// BookingDialog now reads `useOperatorI18n()` — wrap once so `open()` stays unchanged.
function open() {
  return rtlRender(
    <OperatorI18nProvider session={{} as never}>
    <BookingDialog
      session={{} as never}
      branchId="brn1"
      date="2026-09-05"
      initialCustomer={CUSTOMER}
      services={SERVICES as never}
      staff={[]}
      onClose={() => {}}
      onCreated={() => {}}
    />
    </OperatorI18nProvider>,
  );
}

describe('BookingDialog — a failed loyalty read, named', () => {
  it('says the read failed when earnSettings rejects, never shows nothing at all', async () => {
    earnMock = () => Promise.reject(new Error('boom'));
    customerByPhoneMock = () => Promise.resolve({ customer: { subject_ref: 'ref1' } });
    open();
    await waitFor(() => expect(
      screen.getByText(/تعذّرت قراءة نقاط هذا العميل وعروضه/),
    ).toBeTruthy());
  });

  it('says the read failed when the customer\'s own offer/balance lookup rejects', async () => {
    earnMock = () => Promise.resolve({ services: {}, groups: {}, service_group: {}, general: {}, packages: {} });
    customerByPhoneMock = () => Promise.reject(new Error('boom'));
    open();
    await waitFor(() => expect(
      screen.getByText(/تعذّرت قراءة نقاط هذا العميل وعروضه/),
    ).toBeTruthy());
  });

  it('shows no failure sentence once every read succeeds', async () => {
    earnMock = () => Promise.resolve({ services: {}, groups: {}, service_group: {}, general: {}, packages: {} });
    customerByPhoneMock = () => Promise.resolve({ customer: { subject_ref: 'ref1' } });
    open();
    await screen.findByText('قص شعر');
    expect(screen.queryByText(/تعذّرت قراءة نقاط هذا العميل وعروضه/)).toBeNull();
  });
});
