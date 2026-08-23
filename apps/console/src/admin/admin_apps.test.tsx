/**
 * التطبيقات والأسعار والعروض — proven against real catalog ids: plans and coupons share the
 * same backend `group` ("Catalogue"), which is exactly why this screen names each list
 * explicitly rather than relying on the generic one-list-per-group picker.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { AdminApps } from './AdminApps';
import type { AdminSession } from './api';

const SESSION: AdminSession = { access_token: 'tok-1' };

// REAL SHAPE — grouped by service (admin_catalog.py::build_catalog). Both actions genuinely come
// from billing-service in production; kept as one service entry here for that reason.
const FULL_CATALOG = {
  services: [{ service: 'billing-service', actions: [
    { id: 'billing.list_plans', label: 'Plans & pricing', method: 'GET' as const,
     path: '/api/v1/billing/plans', capability: 'billing.manage', group: 'Catalogue' },
    { id: 'billing.update_plan', label: 'Edit a plan', method: 'PATCH' as const,
     path: '/api/v1/billing/plans/{plan_id}', capability: 'billing.manage',
     params: [{ name: 'plan_id', in: 'path' as const, type: 'string', required: true }],
     confirm: true, group: 'Catalogue' },
    { id: 'billing.list_coupons', label: 'Coupons', method: 'GET' as const,
     path: '/api/v1/billing/coupons', capability: 'platform.billing', group: 'Catalogue' },
    { id: 'billing.delete_coupon', label: 'Delete a coupon', method: 'DELETE' as const,
     path: '/api/v1/billing/coupons/{coupon_id}', capability: 'platform.billing',
     params: [{ name: 'coupon_id', in: 'path' as const, type: 'string', required: true }],
     danger: true, confirm: true, group: 'Catalogue' },
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

describe('AdminApps', () => {
  it('renders BOTH plans and coupons, even though they share one backend group', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(FULL_CATALOG);
    reqMock = vi.fn()
      .mockResolvedValueOnce({ plans: [{ id: 'plan-1', name: 'الأساسية', price_halalas: 9900 }] })
      .mockResolvedValueOnce({ coupons: [{ id: 'cpn-1', code: 'RAMADAN26', kind: 'percent' }] });

    render(<AdminApps session={SESSION} />);
    await waitFor(() => expect(screen.getByText('الباقات والأسعار')).toBeTruthy());
    expect(screen.getByText('الخصومات والعروض (كوبونات)')).toBeTruthy();
    await waitFor(() => expect(screen.getAllByText('الأساسية').length).toBeGreaterThan(0));
    expect(screen.getAllByText('RAMADAN26').length).toBeGreaterThan(0);
  });

  it('offers the coupon delete action, armed by its own row', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(FULL_CATALOG);
    reqMock = vi.fn()
      .mockResolvedValueOnce({ plans: [] })
      .mockResolvedValueOnce({ coupons: [{ id: 'cpn-1', code: 'RAMADAN26' }] });

    render(<AdminApps session={SESSION} />);
    await waitFor(() => expect(screen.getAllByText('Delete a coupon').length).toBeGreaterThan(0));
  });

  it('an honest sentence, no section headers, when nothing is readable', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue({ services: [], unreachable: [] });
    render(<AdminApps session={SESSION} />);
    await waitFor(() => expect(screen.getByText(/لا باقات ولا كوبونات لعرضها لك/)).toBeTruthy());
    expect(screen.queryByText('الباقات والأسعار')).toBeFalsy();
  });
});
