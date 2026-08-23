import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { AdminHome } from './AdminHome';
import type { AdminSession } from './api';

const SESSION: AdminSession = { access_token: 'tok-1' };

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

// REAL SHAPE — grouped by service (admin_catalog.py::build_catalog), two different services on
// purpose, matching production.
const FULL_CATALOG = {
  services: [
    { service: 'billing-service', actions: [
      { id: 'billing.platform_invoices', label: 'x', method: 'GET' as const,
       path: '/api/v1/billing/admin/invoices', capability: 'platform.billing' },
    ] },
    { service: 'tenant-service', actions: [
      { id: 'tenant.list', label: 'x', method: 'GET' as const, path: '/api/v1/tenants', capability: 'platform.tenants' },
    ] },
  ],
  unreachable: [],
};

describe('AdminHome', () => {
  it('shows real revenue and tenant counts computed from the catalog\'s own actions', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(FULL_CATALOG);
    reqMock = vi.fn()
      .mockResolvedValueOnce({ invoices: [{ total_minor: 500000, refunded_minor: 0, created: 'x' }], next_cursor: null })
      .mockResolvedValueOnce({ invoices: [], next_cursor: null })
      .mockResolvedValueOnce({ tenants: [{ id: 't1', status: 'active', created_at: '2000-01-01T00:00:00Z' }] });

    render(<AdminHome session={SESSION} />);
    await waitFor(() => expect(screen.getByText('إجمالي المحلات النشطة')).toBeTruthy());
    expect(screen.getByText('الإيراد الكلي هالشهر')).toBeTruthy();
    expect(screen.getByText('1')).toBeTruthy();
  });

  it('a caller with neither capability sees an honest sentence, not blank tiles', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue({ services: [], unreachable: [] });
    reqMock = vi.fn();

    render(<AdminHome session={SESSION} />);
    await waitFor(() => expect(screen.getByText(/لا أرقام مالية لعرضها لك/)).toBeTruthy());
    expect(screen.queryByText('إجمالي المحلات النشطة')).toBeFalsy();
  });

  it('a catalog fetch failure says so plainly', async () => {
    fetchCatalogMock = vi.fn().mockRejectedValue(new Error('network'));
    render(<AdminHome session={SESSION} />);
    await waitFor(() => expect(screen.getByRole('alert')).toBeTruthy());
  });
});
