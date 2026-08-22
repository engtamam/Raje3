/**
 * «من تأخّر» asks. It did not, for as long as the tab existed.
 *
 * The lazy guard was written when a fetched value had two states and `null` meant «not asked for
 * yet». `loading.ts` gave it four, `undefined` became «not yet», and the guard kept the old word —
 * so opening the tab hit `overdue !== null`, returned early, and requested nothing. The screen sat
 * on its skeleton for ever with no failure to report and no empty state to show.
 *
 * NO LONGER TAB-GATED, ON PURPOSE. The same read now also feeds a «متأخر» badge on every row of
 * the default list itself, so it fires once on mount rather than waiting for the tab — the tests
 * below assert that, not the old "opens on tab click" behaviour.
 *
 * This renders the real screen and watches the wire: it asserts the two calls LEAVE. Asserting the
 * rendered rows would let the same bug back in through a stubbed state.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { createElement } from 'react';

const asked: string[] = [];
let recentOverride: { id: string; phone: string; name?: string; last_visit?: number; visit_count?: number }[] = [];
let scheduleOverride: { subject_ref: string; due_at: number }[] = [{ subject_ref: 'p1', due_at: 1 }];
let resolvedOverdueOverride: { id: string; phone: string; name?: string }[] = [];

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }) => {
      asked.push(a.id);
      if (a.id === 'operations.recent') return { customers: recentOverride };
      if (a.id === 'reminders.list_schedule') return { schedule: scheduleOverride };
      if (a.id === 'operations.customers_by_refs') return { customers: resolvedOverdueOverride };
      return { customers: [] };
    },
  };
});

afterEach(() => {
  asked.length = 0;
  recentOverride = [];
  scheduleOverride = [{ subject_ref: 'p1', due_at: 1 }];
  resolvedOverdueOverride = [];
  cleanup();
});

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
  it('asks the scheduler on mount, before the tab is ever opened', async () => {
    open();
    await waitFor(() => expect(asked).toContain('reminders.list_schedule'));
  });

  it('resolves the pseudonyms it got back into customers', async () => {
    open();
    await waitFor(() => expect(asked).toContain('operations.customers_by_refs'));
  });

  it('asks once, not once per render or per tab click — a failure is an answer, not a reason to retry', async () => {
    open();
    await waitFor(() => expect(asked).toContain('operations.customers_by_refs'));
    const tab = screen.getByText('من تأخّر');
    tab.click();
    tab.click();
    await new Promise((r) => setTimeout(r, 20));
    expect(asked.filter((a) => a === 'reminders.list_schedule')).toHaveLength(1);
  });

  it('badges an overdue customer on «عملائي» itself, from the same resolved read', async () => {
    recentOverride = [{ id: 'cus_1', phone: '966501111111', name: 'سالم' }];
    resolvedOverdueOverride = [{ id: 'cus_1', phone: '966501111111', name: 'سالم' }];
    open();
    await waitFor(() => screen.getByText('سالم'));
    await waitFor(() => expect(screen.getByText('متأخر')).toBeTruthy());
  });

  it('never badges a customer the overdue read did not name', async () => {
    recentOverride = [{ id: 'cus_2', phone: '966502222222', name: 'فهد' }];
    resolvedOverdueOverride = [];   // nobody overdue
    open();
    await waitFor(() => screen.getByText('فهد'));
    expect(screen.queryByText('متأخر')).toBeNull();
  });

  it('shows the free last-visit fact on a row that carries it, without inventing one that has not', async () => {
    recentOverride = [
      { id: 'cus_3', phone: '966503333333', name: 'عمر', last_visit: Math.floor(Date.now() / 1000) - 86400, visit_count: 4 },
      { id: 'cus_4', phone: '966504444444', name: 'خالد' },   // no last_visit at all
    ];
    open();
    await waitFor(() => screen.getByText('عمر'));
    expect(screen.getByText(/آخر زيارة أمس/)).toBeTruthy();
    expect(screen.getByText(/4 زيارة/)).toBeTruthy();
    // خالد never visited by this source's own account — nothing invented for him.
    expect(screen.getByText('خالد')).toBeTruthy();
  });

  it('keeps a row without the fact the same height as one with it — a placeholder, not an absence', async () => {
    recentOverride = [
      { id: 'cus_5', phone: '966505555555', name: 'مها', last_visit: Math.floor(Date.now() / 1000) - 86400, visit_count: 1 },
      { id: 'cus_6', phone: '966506666666', name: 'نورة' },
    ];
    open();
    await waitFor(() => screen.getByText('مها'));
    // نورة's row still carries a placeholder line — invisible, never rendered as absent text.
    const placeholder = screen.getByText('نورة').closest('button')?.querySelector('[aria-hidden="true"]');
    expect(placeholder).toBeTruthy();
    expect(placeholder?.className).toContain('invisible');
  });
});
