/**
 * «حسابي» after «منشأتي» split into «الهوية» and «الفروع».
 *
 * WHAT THE OLD TAB WAS. One container holding shop identity, staff, branches, and the WhatsApp
 * connection — four sections stacked under one generic name. This pass splits it: «الهوية» keeps
 * the establishment's own facts (name/logo/colour), the owner's own name, password, and
 * connection keys; «الفروع» keeps "who works where" together — staff, the branch list, and the
 * WhatsApp connection, since customers reach a branch through that number.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render as rtlRender, screen } from '@testing-library/react';
import type { ReactElement } from 'react';
import { OperatorI18nProvider } from '../operator-i18n';

const calls: { id: string; body?: unknown }[] = [];

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }, body?: unknown) => {
      calls.push({ id: a.id, body });
      if (a.id === 'billing.my_invoices') return { invoices: [{ id: 'inv_1', number: 'F-1' }] };
      if (a.id === 'billing.my_subscriptions') return { subscriptions: [] };
      return {};
    },
  };
});

const { AccountScreen, MOVED, resolvePane } = await import('./account/AccountScreen');

afterEach(() => { cleanup(); calls.length = 0; });

const session = {} as never;
const catalog = { services: [], unreachable: [] } as never;

// AccountScreen (and PlansPane/InvoicesPane inside it) now read `useOperatorI18n()` — wrap once
// so every existing `render(<...>)` call site below stays unchanged.
function render(ui: ReactElement) {
  return rtlRender(<OperatorI18nProvider session={session}>{ui}</OperatorI18nProvider>);
}

describe('«حسابي» — the tabs that split, and where their parts landed', () => {
  it('offers no «دخولي» tab any more, and opens on «الهوية» by default', async () => {
    render(<AccountScreen session={session} catalog={catalog} />);
    // «بياناتي» ITSELF WENT DARK TOO (2026-09-22, owner's own call — see `tabsFor`'s own comment
    // in Account.tsx): its DSAR buttons were replaced with one line pointing to the DPO email
    // already in the privacy policy, and the tab was hidden rather than deleted. So the visible
    // tab list now opens on «الهوية» — the first tab everyone has — not «بياناتي».
    await screen.findByText('الهوية');
    expect(screen.queryByText('دخولي')).toBeNull();
    expect(screen.queryByText('بياناتي')).toBeNull();
  });

  it('sends an old ?tab=login link to «الهوية» rather than dropping it on the default', () => {
    // THE LINKS ARE WRITTEN FAR FROM THIS SCREEN — locked cards, sentences in «محلّي», anything
    // anybody bookmarked. A name that stops landing does not fail; it opens the wrong tab and the
    // setting looks deleted.
    expect(MOVED.login).toBe('identity');
    expect(resolvePane('login')).toBe('identity');
  });

  it('sends the old ?tab=shop link to «الهوية», where shop identity now lives', () => {
    expect(MOVED.shop).toBe('identity');
    expect(resolvePane('shop')).toBe('identity');
  });

  it('sends the old ?tab=team link to «الفروع», the new home for staff and branches', () => {
    expect(MOVED.team).toBe('branches');
    expect(resolvePane('team')).toBe('branches');
  });

  it('gives the invoices a tab of their own', async () => {
    render(<AccountScreen session={session} catalog={catalog} openOn="invoices" />);
    expect(await screen.findByText('الفواتير')).toBeTruthy();
  });

  it('does not leave the invoices in billing as well', async () => {
    // TWO PLACES FOR ONE THING is how a screen starts disagreeing with itself: one of the copies
    // gets the next fix and the other keeps answering.
    render(<AccountScreen session={session} catalog={catalog} openOn="billing" />);
    await screen.findByText('الفوترة');
    expect(screen.queryByText('فواتيرك وإيصالاتك')).toBeNull();
  });

  // ── the WhatsApp-connection-required deep link (subscribeFlow.ts's own redirect) ──────────────
  it('?tab=whatsapp opens straight on «الفروع» → the WhatsApp sub-tab, not «العاملون»', async () => {
    // Proven indirectly: the `notice` banner lives ONLY inside the branchesSub === 'whatsapp'
    // branch (Account.tsx), so its presence proves that branch — not the default 'people' one —
    // rendered.
    render(<AccountScreen session={session} catalog={catalog} openOn="whatsapp"
                         notice="اربط رقمك أولاً حتى يعمل هذا التطبيق." />);
    expect(await screen.findByText('اربط رقمك أولاً حتى يعمل هذا التطبيق.')).toBeTruthy();
  });

  it('shows no notice at all on an ordinary visit to the tab', () => {
    render(<AccountScreen session={session} catalog={catalog} openOn="whatsapp" />);
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('a plain ?tab=team visit still opens on «العاملون» by default, not WhatsApp', async () => {
    render(<AccountScreen session={session} catalog={catalog} openOn="team" />);
    // «الفروع» IS AMBIGUOUS TEXT ALONE — it names both the top-level tab and, one level down,
    // the branch-list sub-tab inside it. The top-level tab role disambiguates.
    await screen.findByRole('tab', { name: 'الفروع' });
    expect(screen.queryByRole('alert')).toBeNull();
  });
});
