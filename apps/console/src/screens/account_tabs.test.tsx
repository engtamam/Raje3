/**
 * «حسابي» after «دخولي» was removed: the switch survived the move, and the invoices got a door.
 *
 * WHAT THE TAB WAS. Three cards of prose — your phone is your login, a session lasts 31 days, here
 * is how to reset a password — and one checkbox. Everything on it except the checkbox was a thing
 * to READ, and a settings tab nobody can act on is a tab opened once.
 *
 * THE RISK IN REMOVING IT IS NOT THE REMOVAL. It is the switch: a preference that quietly stops
 * being reachable does not raise an error, it just never gets changed again — and its owner finds
 * out by a report that keeps arriving after he thought he had stopped it. So this file's first
 * job is that the switch is still there, still reads its state, and still saves.
 *
 * AND THE INVOICES CAME OUT OF THE STORE. They were the second half of a tab whose first half is a
 * catalogue of apps: a person arriving for a receipt scrolled past things to buy.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render as rtlRender, screen, waitFor } from '@testing-library/react';
import type { ReactElement } from 'react';
import { OperatorI18nProvider } from '../operator-i18n';

const calls: { id: string; body?: unknown }[] = [];
let digestState: Record<string, unknown> = { on: true, decided: true };

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }, body?: unknown) => {
      calls.push({ id: a.id, body });
      if (a.id === 'insights.digest_state') return digestState;
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

  it('keeps the weekly-report switch reachable, and reads its state', async () => {
    render(<AccountScreen session={session} catalog={catalog} openOn="login" />);
    // «منشأتي» itself is now split into sub-tabs; the switch lives under «الهوية والإعدادات».
    fireEvent.click(await screen.findByText('الهوية والإعدادات'));
    const box = await screen.findByLabelText('تقريري الأسبوعي على واتساب');
    expect(box.getAttribute('aria-checked')).toBe('true');
    await waitFor(() => expect(calls.some((c) => c.id === 'insights.digest_state')).toBe(true));
  });

  it('still saves when he turns the report off', async () => {
    render(<AccountScreen session={session} catalog={catalog} openOn="login" />);
    fireEvent.click(await screen.findByText('الهوية والإعدادات'));
    const box = await screen.findByLabelText('تقريري الأسبوعي على واتساب');
    fireEvent.click(box);
    await waitFor(() => {
      const save = calls.find((c) => c.id === 'insights.digest');
      expect(save?.body).toEqual({ on: false });
    });
  });

  it('gives the invoices a tab of their own', async () => {
    render(<AccountScreen session={session} catalog={catalog} openOn="invoices" />);
    expect(await screen.findByText('فواتيري')).toBeTruthy();
  });

  it('does not leave the invoices in the app store as well', async () => {
    // TWO PLACES FOR ONE THING is how a screen starts disagreeing with itself: one of the copies
    // gets the next fix and the other keeps answering.
    render(<AccountScreen session={session} catalog={catalog} openOn="billing" />);
    await screen.findByText('متجر التطبيقات');
    expect(screen.queryByText('فواتيري')).toBeNull();
  });
});
