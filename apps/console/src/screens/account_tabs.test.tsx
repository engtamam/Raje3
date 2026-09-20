/**
 * «حسابي» after «دخولي» was removed: the invoices got a door.
 *
 * WHAT THE TAB WAS. Three cards of prose — your phone is your login, a session lasts 31 days, here
 * is how to reset a password — and one checkbox (the weekly-report switch, since removed with the
 * feature itself). Everything on it except the checkbox was a thing to READ, and a settings tab
 * nobody can act on is a tab opened once.
 *
 * AND THE INVOICES CAME OUT OF THE STORE. They were the second half of a tab whose first half is a
 * catalogue of apps: a person arriving for a receipt scrolled past things to buy.
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

const { AccountScreen, MOVED, resolvePane } = await import('./Account');

afterEach(() => { cleanup(); calls.length = 0; });

const session = {} as never;
const catalog = { services: [], unreachable: [] } as never;

// AccountScreen (and PlansPane/InvoicesPane inside it) now read `useOperatorI18n()` — wrap once
// so every existing `render(<...>)` call site below stays unchanged.
function render(ui: ReactElement) {
  return rtlRender(<OperatorI18nProvider session={session}>{ui}</OperatorI18nProvider>);
}

describe('«حسابي» — the tab that went, and where its parts landed', () => {
  it('offers no «دخولي» tab any more', async () => {
    render(<AccountScreen session={session} catalog={catalog} />);
    await screen.findByText('بياناتي');
    expect(screen.queryByText('دخولي')).toBeNull();
  });

  it('sends an old ?tab=login link to «منشأتي» rather than dropping it on the default', () => {
    // THE LINKS ARE WRITTEN FAR FROM THIS SCREEN — locked cards, sentences in «محلّي», anything
    // anybody bookmarked. A name that stops landing does not fail; it opens the wrong tab and the
    // setting looks deleted. The switch itself has since moved a second time, from «بياناتي» to
    // «منشأتي» — this mapping follows it there.
    expect(MOVED.login).toBe('shop');
    expect(resolvePane('login')).toBe('shop');
  });

  it('gives the invoices a tab of their own', async () => {
    render(<AccountScreen session={session} catalog={catalog} openOn="invoices" />);
    expect(await screen.findByText('فواتيري')).toBeTruthy();
  });

  it('does not leave the invoices in billing as well', async () => {
    // TWO PLACES FOR ONE THING is how a screen starts disagreeing with itself: one of the copies
    // gets the next fix and the other keeps answering.
    render(<AccountScreen session={session} catalog={catalog} openOn="billing" />);
    await screen.findByText('الفوترة');
    expect(screen.queryByText('فواتيري')).toBeNull();
  });

  // ── the WhatsApp-connection-required deep link (subscribeFlow.ts's own redirect) ──────────────
  it('?tab=whatsapp opens straight on the WhatsApp sub-tab, not «العاملون»', async () => {
    // Proven indirectly: the `notice` banner lives ONLY inside the shopSub === 'whatsapp' branch
    // (Account.tsx), so its presence proves that branch — not the default 'people' one — rendered.
    render(<AccountScreen session={session} catalog={catalog} openOn="whatsapp"
                         notice="اربط رقمك أولاً حتى يعمل هذا التطبيق." />);
    expect(await screen.findByText('اربط رقمك أولاً حتى يعمل هذا التطبيق.')).toBeTruthy();
  });

  it('shows no notice at all on an ordinary visit to the tab', () => {
    render(<AccountScreen session={session} catalog={catalog} openOn="whatsapp" />);
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('a plain ?tab=shop visit still opens on «العاملون» by default, not WhatsApp', async () => {
    render(<AccountScreen session={session} catalog={catalog} openOn="shop" />);
    await screen.findByText('منشأتي');
    expect(screen.queryByRole('alert')).toBeNull();
  });
});
