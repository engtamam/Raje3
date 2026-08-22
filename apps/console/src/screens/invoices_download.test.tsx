/**
 * «تنزيل المستند»/«تنزيل الإيصال» — the download buttons that never existed (audit #4,
 * 2026-08-22). Three routes were built, tested and served for months with no console call.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

const downloadCalls: Array<{ id: string; invoiceId: string }> = [];

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }) => {
      if (a.id === 'billing.my_invoices') {
        return {
          invoices: [
            { id: 'inv_1', number: 'INV-001', status: 'paid', total_minor: 11500,
              issued_at: '2026-08-01', doc_type: 'tax_invoice' },
            { id: 'inv_2', number: 'INV-002', status: 'paid', total_minor: 9900,
              issued_at: '2026-07-01', doc_type: 'receipt' },
          ],
        };
      }
      return {};
    },
    downloadUrl: async (_s: unknown, a: { id: string }, params: { id: string }) => {
      downloadCalls.push({ id: a.id, invoiceId: params.id });
      return 'blob:mock-url';
    },
  };
});

const { InvoicesPane } = await import('./AccountPanes');

afterEach(() => { cleanup(); downloadCalls.length = 0; });

const session = {} as never;
const catalog = { services: [], unreachable: [] } as never;

function open() {
  return render(<InvoicesPane session={session} catalog={catalog} />);
}

describe('«فواتيري» — real downloads', () => {
  it('offers «تنزيل المستند» on every invoice, and opens the blob it resolves to', async () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null);
    open();
    const buttons = await screen.findAllByRole('button', { name: 'تنزيل المستند' });
    expect(buttons).toHaveLength(2);
    fireEvent.click(buttons[0]);
    await vi.waitFor(() => expect(downloadCalls).toContainEqual({ id: 'billing.invoice_document', invoiceId: 'inv_1' }));
    expect(openSpy).toHaveBeenCalledWith('blob:mock-url', '_blank', 'noreferrer');
  });

  it('offers «تنزيل الإيصال» only for the paid tax-invoice row, never for a plain receipt row', async () => {
    open();
    await screen.findAllByRole('button', { name: 'تنزيل المستند' });
    // Exactly one row (inv_1: tax_invoice + paid) gets the second download.
    expect(screen.getAllByRole('button', { name: 'تنزيل الإيصال' })).toHaveLength(1);
  });

  it('shows a fixed sentence, not a raw status, when a download fails', async () => {
    downloadCalls.length = 0;
    vi.doMock('../catalog', async (importOriginal) => {
      const real = await importOriginal<typeof import('../catalog')>();
      return {
        ...real,
        action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
        call: async (_s: unknown, a: { id: string }) => (a.id === 'billing.my_invoices'
          ? { invoices: [{ id: 'inv_1', number: 'INV-001', status: 'paid', total_minor: 100,
                          issued_at: '2026-08-01', doc_type: 'receipt' }] }
          : {}),
        downloadUrl: async () => { throw new Error('boom'); },
      };
    });
    vi.resetModules();
    const { InvoicesPane: Fresh } = await import('./AccountPanes');
    render(<Fresh session={session} catalog={catalog} />);
    fireEvent.click(await screen.findByRole('button', { name: 'تنزيل المستند' }));
    expect(await screen.findByText('تعذّر تنزيل المستند الآن. حاول بعد قليل.')).toBeTruthy();
  });
});
