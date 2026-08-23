/**
 * «الدعم الفني» — the shop's own half of the support loop, the affiliate portal's TicketCarousel
 * (apps/console/src/affiliates/TicketCarousel.tsx) being the other: a shop raises a problem here,
 * a marketer sees it there and replies.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

let mineResult: Promise<{ tickets: unknown[] }>;
const calls: { id: string; body?: unknown }[] = [];

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }, body?: unknown) => {
      calls.push({ id: a.id, body });
      if (a.id === 'tickets.mine') return mineResult;
      return { ok: true };
    },
  };
});

const { SupportScreen } = await import('./Support');

const SESSION = { tenant: 't1', operator: '', operatorName: '', token: 'tok' };
const CATALOG = {} as never;

afterEach(() => { cleanup(); calls.length = 0; });

describe('SupportScreen', () => {
  it('shows an honest empty state before any ticket has been raised', async () => {
    mineResult = Promise.resolve({ tickets: [] });
    render(<SupportScreen session={SESSION} catalog={CATALOG} />);
    await waitFor(() => expect(screen.getByText('لا تذاكر بعد')).toBeTruthy());
  });

  it('lists a previously raised ticket with its status', async () => {
    mineResult = Promise.resolve({
      tickets: [{ id: 'tk1', subject: 'مشكلة بالفوترة', status: 'open' }],
    });
    render(<SupportScreen session={SESSION} catalog={CATALOG} />);
    await waitFor(() => expect(screen.getByText('مشكلة بالفوترة')).toBeTruthy());
    expect(screen.getByText('open')).toBeTruthy();
  });

  it('raising a ticket calls tickets.open with the form fields, then reloads the list', async () => {
    mineResult = Promise.resolve({ tickets: [] });
    render(<SupportScreen session={SESSION} catalog={CATALOG} />);
    await waitFor(() => expect(screen.getByText('لا تذاكر بعد')).toBeTruthy());

    fireEvent.change(screen.getByLabelText('نوع المشكلة', { exact: false }), { target: { value: 'فوترة' } });
    fireEvent.change(screen.getByLabelText('العنوان', { exact: false }), { target: { value: 'فاتورة مكررة' } });
    fireEvent.change(screen.getByLabelText('التفاصيل'), { target: { value: 'دُفعت مرتين هذا الشهر' } });

    mineResult = Promise.resolve({ tickets: [{ id: 'tk2', subject: 'فاتورة مكررة', status: 'new' }] });
    fireEvent.click(screen.getByRole('button', { name: /رفع التذكرة/ }));

    await waitFor(() => expect(calls.some((c) => c.id === 'tickets.open')).toBe(true));
    const opened = calls.find((c) => c.id === 'tickets.open')!;
    expect(opened.body).toEqual({ type: 'فوترة', subject: 'فاتورة مكررة', body: 'دُفعت مرتين هذا الشهر' });
    await waitFor(() => expect(screen.getByText(/رُفعت التذكرة/)).toBeTruthy());
  });

  it('refuses to submit with no type or subject', async () => {
    mineResult = Promise.resolve({ tickets: [] });
    render(<SupportScreen session={SESSION} catalog={CATALOG} />);
    await waitFor(() => expect(screen.getByText('لا تذاكر بعد')).toBeTruthy());
    expect((screen.getByRole('button', { name: /رفع التذكرة/ }) as HTMLButtonElement).disabled).toBe(true);
  });
});
