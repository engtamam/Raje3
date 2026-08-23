/**
 * المالية — الفواتير/الاشتراكات ترفض بلا فلتر (نفس فحص الخلفية `PLATFORM_LISTING_NEEDS_A_FILTER`
 * منعكِس بالواجهة قبل الطلب أصلاً)، والتسوية/العكس/الاسترجاع مبنية يدوياً لحقولها المركّبة.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AdminFinance } from './AdminFinance';
import type { AdminSession } from './api';

const SESSION: AdminSession = { access_token: 'tok-1' };

const CATALOG = {
  services: [{ service: 'billing-service', actions: [
    { id: 'billing.platform_invoices', label: 'x', method: 'GET' as const,
     path: '/api/v1/billing/admin/invoices', capability: 'platform.billing' },
    { id: 'billing.platform_subscriptions', label: 'x', method: 'GET' as const,
     path: '/api/v1/billing/admin/subscriptions', capability: 'platform.billing' },
    { id: 'billing.settle', label: 'x', method: 'POST' as const,
     path: '/api/v1/billing/invoices/{invoice_id}/settle', capability: 'platform.billing', confirm: true },
    { id: 'billing.list_settlements', label: 'x', method: 'GET' as const,
     path: '/api/v1/billing/invoices/{invoice_id}/settlements', capability: 'platform.billing' },
    { id: 'billing.reverse_settlement', label: 'x', method: 'POST' as const,
     path: '/api/v1/billing/settlements/{settlement_id}/reverse', capability: 'platform.billing', danger: true, confirm: true },
    { id: 'billing.refund', label: 'x', method: 'POST' as const,
     path: '/api/v1/billing/payments/{payment_id}/refund', capability: 'platform.billing', danger: true, confirm: true },
    { id: 'billing.reconcile_payment', label: 'x', method: 'POST' as const,
     path: '/api/v1/billing/payments/{payment_id}/reconcile', capability: 'platform.billing', confirm: true },
  ] }],
  unreachable: [],
};

let fetchCatalogMock: ReturnType<typeof vi.fn>;
let reqMock: ReturnType<typeof vi.fn>;

vi.mock('./catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('./catalog')>();
  return { ...real, fetchCatalog: (...args: unknown[]) => fetchCatalogMock(...args) };
});
vi.mock('./api', async (importOriginal) => {
  const real = await importOriginal<typeof import('./api')>();
  return { ...real, req: (...args: unknown[]) => reqMock(...args) };
});

afterEach(() => vi.clearAllMocks());

describe('AdminFinance — invoices', () => {
  it('refuses to search with no filter at all', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn();
    render(<AdminFinance session={SESSION} />);
    fireEvent.click(await screen.findByText('بحث'));
    await waitFor(() => expect(screen.getByText(/فلتر واحد على الأقل مطلوب/)).toBeTruthy());
    expect(reqMock).not.toHaveBeenCalled();
  });

  it('a saved view ("مدفوعات اليوم") searches with status=paid and a since date', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({ invoices: [], next_cursor: null });

    render(<AdminFinance session={SESSION} />);
    fireEvent.click(await screen.findByText('مدفوعات اليوم'));

    await waitFor(() => expect(reqMock).toHaveBeenCalled());
    const url = reqMock.mock.calls[0][0] as string;
    expect(url).toContain('status=paid');
    expect(url).toContain('since=');
  });

  it('renders invoice rows with riyal amounts', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({
      invoices: [{ id: 'inv-1', tenant: 'tnt_a', number: 'INV-001', subscription_id: 'sub-1',
                  status: 'paid', subtotal_minor: 9000, tax_minor: 1350, total_minor: 10350,
                  refunded_minor: 0, currency: 'SAR', created: '2026-08-01T00:00:00Z', paid_at: null }],
      next_cursor: null,
    });

    render(<AdminFinance session={SESSION} />);
    fireEvent.click(await screen.findByText('مدفوعات اليوم'));
    await waitFor(() => expect(screen.getAllByText('INV-001').length).toBeGreaterThan(0));
    expect(screen.getAllByText('103.50 ريال').length).toBeGreaterThan(0);
  });

  it('settling an invoice posts method/issuer/reference/amount_minor/paid_at', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn()
      .mockResolvedValueOnce({
        invoices: [{ id: 'inv-1', tenant: 'tnt_a', number: 'INV-001', subscription_id: '',
                    status: 'open', subtotal_minor: 10000, tax_minor: 0, total_minor: 10000,
                    refunded_minor: 0, currency: 'SAR', created: '2026-08-01T00:00:00Z', paid_at: null }],
        next_cursor: null,
      })
      .mockResolvedValueOnce({ settlement: { id: 's1' }, invoice_status: 'paid' })
      .mockResolvedValueOnce({ invoices: [], next_cursor: null });

    render(<AdminFinance session={SESSION} />);
    fireEvent.click(await screen.findByText('تجديدات لم تتم'));
    await waitFor(() => expect(screen.getAllByText('INV-001').length).toBeGreaterThan(0));

    fireEvent.click(screen.getAllByText('تسوية')[0]);
    fireEvent.change(await screen.findByLabelText('رقم المرجع'), { target: { value: 'REF-1' } });
    fireEvent.click(screen.getByText('متابعة'));
    await screen.findByText(/تأكيد تسوية/);
    fireEvent.click(screen.getByText('تأكيد'));

    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      '/api/v1/billing/invoices/inv-1/settle', 'POST',
      expect.objectContaining({ reference: 'REF-1', amount_minor: 10000 }), 'tok-1',
    ));
  });
});

describe('AdminFinance — subscriptions', () => {
  it('refuses to search with no filter', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn();
    render(<AdminFinance session={SESSION} />);
    fireEvent.click(await screen.findByText('الاشتراكات'));
    fireEvent.click(screen.getByText('بحث'));
    await waitFor(() => expect(screen.getByText(/فلتر واحد على الأقل مطلوب/)).toBeTruthy());
  });

  it('lists subscriptions for a chosen status', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({
      subscriptions: [{ id: 'sub-1', tenant: 'tnt_a', plan_id: 'plan-basic', status: 'active',
                       created: '2026-08-01T00:00:00Z', canceled_at: null }],
    });

    render(<AdminFinance session={SESSION} />);
    fireEvent.click(await screen.findByText('الاشتراكات'));
    fireEvent.change(screen.getByLabelText('المحل'), { target: { value: 'tnt_a' } });
    fireEvent.click(screen.getByText('بحث'));

    await waitFor(() => expect(screen.getAllByText('plan-basic').length).toBeGreaterThan(0));
  });
});

describe('AdminFinance — payment tools', () => {
  it('reconcile calls the route with the typed payment id', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({ ok: true, reconciled: true, provider_status: 'succeeded', payment_status: 'paid' });

    render(<AdminFinance session={SESSION} />);
    fireEvent.click(await screen.findByText('أدوات الدفع'));
    fireEvent.change(screen.getByLabelText('معرّف الدفعة (payment_id)'), { target: { value: 'pay-1' } });
    fireEvent.click(screen.getByText('مطابقة مع البوابة'));

    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      '/api/v1/billing/payments/pay-1/reconcile', 'POST', undefined, 'tok-1',
    ));
  });

  it('refund is armed with the payment id as the confirm text', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({ ok: true, status: 'refunded' });

    render(<AdminFinance session={SESSION} />);
    fireEvent.click(await screen.findByText('أدوات الدفع'));
    fireEvent.change(screen.getByLabelText('معرّف الدفعة (payment_id)'), { target: { value: 'pay-1' } });
    fireEvent.click(screen.getByText('استرجاع كامل'));

    await screen.findByText(/استرجاع الدفعة/);
    expect(reqMock).not.toHaveBeenCalled();
  });
});
