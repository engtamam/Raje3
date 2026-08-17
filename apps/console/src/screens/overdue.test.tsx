/**
 * «من تأخّر» asks. It did not, for as long as the tab existed.
 *
 * The lazy guard was written when a fetched value had two states and `null` meant «not asked for
 * yet». `loading.ts` gave it four, `undefined` became «not yet», and the guard kept the old word —
 * so opening the tab hit `overdue !== null`, returned early, and requested nothing. The screen sat
 * on its skeleton for ever with no failure to report and no empty state to show.
 *
 * This renders the real screen and watches the wire: it asserts the two calls LEAVE. Asserting the
 * rendered rows would let the same bug back in through a stubbed state.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { createElement } from 'react';

const asked: string[] = [];

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }) => {
      asked.push(a.id);
      if (a.id === 'reminders.list_schedule') return { schedule: [{ subject_ref: 'p1', due_at: 1 }] };
      if (a.id === 'operations.customers_by_refs') return { customers: [] };
      return { customers: [] };
    },
  };
});

afterEach(() => { asked.length = 0; cleanup(); });

const { CustomersScreen } = await import('./Customers');

function open() {
  return render(
    createElement(MemoryRouter, null,
      // «كل الفروع» — the default scope, and the one this test is about: the list is not
      // narrowed here, so what it asserts is the overdue join and nothing else.
      createElement(CustomersScreen, { session: {} as never, catalog: {} as never, branch: '' })),
  );
}

describe('«من تأخّر»', () => {
  it('asks the scheduler the moment the tab is opened', async () => {
    open();
    screen.getByText('من تأخّر').click();
    await waitFor(() => expect(asked).toContain('reminders.list_schedule'));
  });

  it('resolves the pseudonyms it got back into customers', async () => {
    open();
    screen.getByText('من تأخّر').click();
    await waitFor(() => expect(asked).toContain('operations.customers_by_refs'));
  });

  it('asks once, not once per render — a failure is an answer, not a reason to retry', async () => {
    open();
    const tab = screen.getByText('من تأخّر');
    tab.click();
    await waitFor(() => expect(asked).toContain('operations.customers_by_refs'));
    tab.click();
    tab.click();
    await new Promise((r) => setTimeout(r, 20));
    expect(asked.filter((a) => a === 'reminders.list_schedule')).toHaveLength(1);
  });
});
