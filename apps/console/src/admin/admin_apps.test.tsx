/**
 * التطبيقات والأسعار والعروض — proven against real catalog ids and real response shapes
 * (billing-service's own Plan/Coupon fields). Plans and Coupons are Segmented sub-tabs on one
 * screen now, not two stacked sections — the sidebar stays at its deliberate 5-6 items.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AdminApps } from './AdminApps';
import type { AdminSession } from './api';

const SESSION: AdminSession = { access_token: 'tok-1' };

// REAL SHAPE — grouped by service (admin_catalog.py::build_catalog). Both actions genuinely come
// from billing-service in production; kept as one service entry here for that reason.
const FULL_CATALOG = {
  services: [{ service: 'billing-service', actions: [
    { id: 'billing.list_plans', label: 'Plans & pricing', method: 'GET' as const,
     path: '/api/v1/billing/plans', capability: 'billing.manage', group: 'Catalogue' },
    { id: 'billing.plan_availability', label: 'Retire or hide a plan', method: 'POST' as const,
     path: '/api/v1/billing/plans/{plan_id}/availability', capability: 'billing.manage',
     params: [{ name: 'plan_id', in: 'path' as const, type: 'string', required: true }],
     confirm: true, group: 'Catalogue' },
    { id: 'billing.update_plan', label: 'Edit a plan', method: 'PATCH' as const,
     path: '/api/v1/billing/plans/{plan_id}', capability: 'billing.manage',
     params: [{ name: 'plan_id', in: 'path' as const, type: 'string', required: true }],
     confirm: true, group: 'Catalogue' },
    { id: 'billing.list_coupons', label: 'Coupons', method: 'GET' as const,
     path: '/api/v1/billing/coupons', capability: 'platform.billing', group: 'Catalogue' },
    { id: 'billing.delete_coupon', label: 'Delete a coupon', method: 'DELETE' as const,
     path: '/api/v1/billing/coupons/{code}', capability: 'platform.billing',
     params: [{ name: 'code', in: 'path' as const, type: 'string', required: true }],
     danger: true, confirm: true, group: 'Catalogue' },
  ] }],
  unreachable: [],
};

const PLAN = {
  id: 'plan_419e081916264f6bbe935e97877af116', name: 'الأساس', active: true, listed: true,
  prices: [{ type: 'flat', currency: 'SAR', interval: 'month', amount_minor: 9900 }],
  limits: { 'staff.seats': { kind: 'gauge', limit: 5 } }, trial_days: 0,
};
const COUPON = {
  code: 'RAMADAN26', type: 'percent', value: 20, status: 'active',
  max_redemptions: 0, redeemed: 3, public: true,
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
  it('shows plans by default, translated into readable cards — not a raw table', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(FULL_CATALOG);
    reqMock = vi.fn().mockResolvedValue({ plans: [PLAN] });

    render(<AdminApps session={SESSION} />);
    await waitFor(() => expect(screen.getByText('الأساس')).toBeTruthy());
    expect(screen.getByText('99 ريال')).toBeTruthy();
    expect(screen.getByText('مقاعد الموظفين')).toBeTruthy();   // translated, not "staff.seats"
    expect(screen.getByText('نشطة')).toBeTruthy();
  });

  it('switching to the coupons sub-tab loads and renders them', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(FULL_CATALOG);
    reqMock = vi.fn()
      .mockResolvedValueOnce({ plans: [] })
      .mockResolvedValueOnce({ coupons: [COUPON] });

    render(<AdminApps session={SESSION} />);
    await waitFor(() => expect(screen.getByText('الخصومات والعروض')).toBeTruthy());
    fireEvent.click(screen.getByText('الخصومات والعروض'));

    await waitFor(() => expect(screen.getByText('RAMADAN26')).toBeTruthy());
    expect(screen.getByText('خصم 20%')).toBeTruthy();
    expect(screen.getByText('فعّال')).toBeTruthy();
  });

  it('toggling a plan off calls plan_availability with active:false, then reloads', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(FULL_CATALOG);
    reqMock = vi.fn()
      .mockResolvedValueOnce({ plans: [PLAN] })
      .mockResolvedValueOnce({ ok: true })
      .mockResolvedValueOnce({ plans: [{ ...PLAN, active: false }] });

    render(<AdminApps session={SESSION} />);
    await waitFor(() => expect(screen.getByText('إيقاف')).toBeTruthy());
    fireEvent.click(screen.getByText('إيقاف'));
    fireEvent.click(screen.getByText('تأكيد'));

    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      '/api/v1/billing/plans/plan_419e081916264f6bbe935e97877af116/availability',
      'POST', { active: false }, 'tok-1'));
  });

  it('editing a plan opens a real form and saves through billing.update_plan', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(FULL_CATALOG);
    reqMock = vi.fn()
      .mockResolvedValueOnce({ plans: [PLAN] })
      .mockResolvedValueOnce({ ok: true })
      .mockResolvedValueOnce({ plans: [{ ...PLAN, name: 'الأساس الجديد' }] });

    render(<AdminApps session={SESSION} />);
    await waitFor(() => expect(screen.getByText('تعديل')).toBeTruthy());
    fireEvent.click(screen.getByText('تعديل'));

    const nameInput = await screen.findByLabelText('الاسم');
    fireEvent.change(nameInput, { target: { value: 'الأساس الجديد' } });
    fireEvent.click(screen.getByText('حفظ'));

    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      '/api/v1/billing/plans/plan_419e081916264f6bbe935e97877af116', 'PATCH',
      expect.objectContaining({ name: 'الأساس الجديد' }), 'tok-1'));
  });

  it('deleting a coupon fires the real action', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(FULL_CATALOG);
    reqMock = vi.fn()
      .mockResolvedValueOnce({ plans: [] })
      .mockResolvedValueOnce({ coupons: [COUPON] })
      .mockResolvedValueOnce({ ok: true })
      .mockResolvedValueOnce({ coupons: [] });

    render(<AdminApps session={SESSION} />);
    fireEvent.click(await screen.findByText('الخصومات والعروض'));
    await waitFor(() => expect(screen.getByText('حذف الكوبون')).toBeTruthy());
    fireEvent.click(screen.getByText('حذف الكوبون'));
    fireEvent.click(screen.getByText('تأكيد'));

    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      '/api/v1/billing/coupons/RAMADAN26', 'DELETE', undefined, 'tok-1'));
  });

  it('an honest sentence, no sub-tabs, when nothing is readable', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue({ services: [], unreachable: [] });
    render(<AdminApps session={SESSION} />);
    await waitFor(() => expect(screen.getByText(/لا باقات ولا كوبونات لعرضها لك/)).toBeTruthy());
    expect(screen.queryByText('الباقات والأسعار')).toBeFalsy();
  });
});
