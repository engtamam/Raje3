import { afterEach, describe, expect, it, vi } from 'vitest';
import { monthRevenueHalalas, tenantCounts } from './platformMetrics';
import type { AdminCatalog } from './catalog';
import type { AdminSession } from './api';

const SESSION: AdminSession = { access_token: 'tok-1' };

const CATALOG: AdminCatalog = {
  actions: [
    { id: 'billing.platform_invoices', label: 'x', method: 'GET',
     path: '/api/v1/billing/admin/invoices', capability: 'platform.billing' },
    { id: 'tenant.list', label: 'x', method: 'GET', path: '/api/v1/tenants', capability: 'platform.tenants' },
  ],
};

let reqMock: ReturnType<typeof vi.fn>;

vi.mock('./api', async (importOriginal) => {
  const real = await importOriginal<typeof import('./api')>();
  return { ...real, req: (...args: unknown[]) => reqMock(...args) };
});

afterEach(() => vi.clearAllMocks());

describe('monthRevenueHalalas', () => {
  it('sums total_minor minus refunded_minor across every paid invoice', async () => {
    reqMock = vi.fn().mockResolvedValue({
      invoices: [
        { total_minor: 10000, refunded_minor: 0, created: '2026-08-05T00:00:00Z' },
        { total_minor: 5000, refunded_minor: 1000, created: '2026-08-10T00:00:00Z' },
      ],
      next_cursor: null,
    });
    const out = await monthRevenueHalalas(SESSION, CATALOG, 0);
    expect(out).toEqual({ ok: true, halalas: 14000 });
  });

  it('pages through cursors until next_cursor is null', async () => {
    reqMock = vi.fn()
      .mockResolvedValueOnce({ invoices: [{ total_minor: 100, refunded_minor: 0, created: 'x' }], next_cursor: 'c1' })
      .mockResolvedValueOnce({ invoices: [{ total_minor: 200, refunded_minor: 0, created: 'x' }], next_cursor: null });
    const out = await monthRevenueHalalas(SESSION, CATALOG, 0);
    expect(out).toEqual({ ok: true, halalas: 300 });
    expect(reqMock).toHaveBeenCalledTimes(2);
  });

  it('refuses honestly when the caller has no billing action in their catalog', async () => {
    reqMock = vi.fn();
    const out = await monthRevenueHalalas(SESSION, { actions: [] }, 0);
    expect(out.ok).toBe(false);
    expect(reqMock).not.toHaveBeenCalled();
  });
});

describe('tenantCounts', () => {
  it('counts total, active, and created-this-month from one flat call', async () => {
    const thisMonthStart = new Date();
    thisMonthStart.setUTCDate(1);
    thisMonthStart.setUTCHours(0, 0, 0, 0);
    const inThisMonth = new Date(thisMonthStart.getTime() + 86400000).toISOString();
    const lastMonth = new Date(thisMonthStart.getTime() - 86400000).toISOString();

    reqMock = vi.fn().mockResolvedValue({
      tenants: [
        { id: 't1', status: 'active', created_at: inThisMonth },
        { id: 't2', status: 'active', created_at: lastMonth },
        { id: 't3', status: 'suspended', created_at: lastMonth },
      ],
    });
    const out = await tenantCounts(SESSION, CATALOG);
    expect(out).toEqual({ ok: true, counts: { total: 3, active: 2, newThisMonth: 1 } });
  });

  it('refuses honestly when the caller has no tenant action in their catalog', async () => {
    reqMock = vi.fn();
    const out = await tenantCounts(SESSION, { actions: [] });
    expect(out.ok).toBe(false);
    expect(reqMock).not.toHaveBeenCalled();
  });
});
