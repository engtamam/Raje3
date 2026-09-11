/**
 * «تطبيقات تتبع تسجيل زيارة/الحجوزات منطقياً» — owner's own rule (2026-09-11): برنامج النقاط/
 * التقييم/فرصي/الحملات are useless without a real sales-recording app under them, and
 * `plan.requires_any` already refuses BUYING one without holding one of the two first. This pins
 * the follow-on half: cancelling the LAST prerequisite an owner holds cascades to cancel every
 * dependent app with it, in the same request — never a silent orphaned subscription still billing.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { DENIED } from '../loading';

const VISIT = { id: 'plan_visit', name: 'تسجيل زيارة', active: true, listed: true,
  prices: [{ interval: 'month', amount_minor: 9900, currency: 'SAR' }],
  limits: { 'feature.visit': { kind: 'boolean', limit: 1 } } };
const LOYALTY = { id: 'plan_loyalty', name: 'برنامج النقاط', active: true, listed: true,
  prices: [{ interval: 'month', amount_minor: 9900, currency: 'SAR' }],
  limits: { 'feature.loyalty': { kind: 'boolean', limit: 1 } } };
const CAMPAIGNS = { id: 'plan_campaigns', name: 'الحملات', active: true, listed: true,
  prices: [{ interval: 'month', amount_minor: 9900, currency: 'SAR' }],
  limits: { 'feature.campaigns': { kind: 'boolean', limit: 1 } } };
const CONTACTS = { id: 'plan_contacts', name: 'جهات الاتصال', active: true, listed: true,
  prices: [{ interval: 'month', amount_minor: 0, currency: 'SAR' }],
  limits: { 'feature.contacts': { kind: 'boolean', limit: 1 } } };

let subs: Array<{ id: string; plan_id: string; status: string;
  current_period_end: number; cancel_at_period_end: boolean }> = [
  { id: 'sub_visit', plan_id: 'plan_visit', status: 'active',
    current_period_end: Math.floor(Date.UTC(2026, 8, 20) / 1000), cancel_at_period_end: false },
  { id: 'sub_loyalty', plan_id: 'plan_loyalty', status: 'active',
    current_period_end: Math.floor(Date.UTC(2026, 8, 20) / 1000), cancel_at_period_end: false },
  { id: 'sub_campaigns', plan_id: 'plan_campaigns', status: 'active',
    current_period_end: Math.floor(Date.UTC(2026, 8, 20) / 1000), cancel_at_period_end: false },
  // A held app that is NOT one of the four dependents — must never be touched by the cascade.
  { id: 'sub_contacts', plan_id: 'plan_contacts', status: 'active',
    current_period_end: 0, cancel_at_period_end: false },
];

const cancelCalls: string[] = [];

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }, body?: { id?: string }) => {
      if (a.id === 'billing.plans') return { plans: [VISIT, LOYALTY, CAMPAIGNS, CONTACTS] };
      if (a.id === 'billing.my_subscriptions') return { subscriptions: subs };
      if (a.id === 'subscription.payment_state') return { enabled: true };
      if (a.id === 'billing.cancel') {
        const subId = body?.id ?? '';
        cancelCalls.push(subId);
        subs = subs.map((s) => (s.id === subId ? { ...s, cancel_at_period_end: true } : s));
        return { id: subId, cancel_at_period_end: true };
      }
      return {};
    },
  };
});

const { PlansPane } = await import('./Plans');

afterEach(cleanup);

const session = {} as never;
const catalog = { services: [], unreachable: [] } as never;

describe('cancelling the last prerequisite cascades to its dependent apps', () => {
  it('cancelling تسجيل زيارة (the only prerequisite held) also cancels برنامج النقاط والحملات', async () => {
    render(<PlansPane session={session} catalog={catalog} owned={DENIED} onGoConnect={() => {}} />);

    const stopButtons = await screen.findAllByRole('button', { name: /إيقاف تجديد/ });
    // «إيقاف تجديد هذا التطبيق» on تسجيل زيارة's own card — opens the confirm dialog, fires nothing yet.
    const visitCard = (await screen.findByText('تسجيل زيارة')).closest('article');
    expect(visitCard).toBeTruthy();
    const visitStop = stopButtons.find((b) => visitCard?.contains(b));
    expect(visitStop).toBeTruthy();
    fireEvent.click(visitStop!);

    // THE WARNING NAMES BOTH DEPENDENTS BEFORE ANY CALL FIRES — the point of computing it ahead
    // of the confirm press, not after.
    await screen.findByText(/برنامج النقاط، الحملات|الحملات، برنامج النقاط/);
    expect(cancelCalls.length).toBe(0);

    fireEvent.click(await screen.findByRole('button', { name: 'تأكيد إيقاف التجديد' }));

    await waitFor(() => expect(cancelCalls).toContain('sub_visit'));
    expect(cancelCalls).toContain('sub_loyalty');
    expect(cancelCalls).toContain('sub_campaigns');
    // جهات الاتصال is not one of the four dependent apps — never touched.
    expect(cancelCalls).not.toContain('sub_contacts');
  });
});
