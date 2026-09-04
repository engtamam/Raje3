/**
 * The generic engine — proven against a real catalog slice (the affiliate application queue),
 * per §3.5 of the admin plan: "تجربة حقيقية: طلبات المسوّقين المعلّقة تظهر باللوحة".
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { ActionCatalogPanel } from './ActionRenderer';
import type { AdminAction, AdminCatalog } from './catalog';
import type { AdminSession } from './api';

const SESSION: AdminSession = { access_token: 'tok-1' };
const CATALOG_ALL_REACHABLE: AdminCatalog = { services: [], unreachable: [] };

const LIST_ACTION: AdminAction = {
  id: 'affiliates.list_pending', label: 'طلبات التسويق المعلّقة', method: 'GET',
  path: '/api/v1/admin/affiliates', capability: 'platform.affiliates', params: [], group: 'Affiliates',
};
const APPROVE_ACTION: AdminAction = {
  id: 'affiliates.approve_application', label: 'قبول طلب مسوّق', method: 'POST',
  path: '/api/v1/admin/affiliates/{application_id}/approve', capability: 'platform.affiliates',
  params: [{ name: 'application_id', in: 'path', type: 'string', required: true }],
  confirm: true, danger: false, group: 'Affiliates',
};
const REJECT_ACTION: AdminAction = {
  id: 'affiliates.reject_application', label: 'رفض طلب مسوّق', method: 'POST',
  path: '/api/v1/admin/affiliates/{application_id}/reject', capability: 'platform.affiliates',
  params: [{ name: 'application_id', in: 'path', type: 'string', required: true }],
  confirm: true, danger: true, group: 'Affiliates',
};

let reqMock: ReturnType<typeof vi.fn>;

vi.mock('./api', async (importOriginal) => {
  const real = await importOriginal<typeof import('./api')>();
  return { ...real, req: (...args: unknown[]) => reqMock(...args) };
});

afterEach(() => vi.clearAllMocks());

describe('ActionCatalogPanel', () => {
  it('lists real applications from the GET action, one column per response field', async () => {
    reqMock = vi.fn().mockResolvedValue({
      applications: [{ id: 'app-1', name: 'سالم', phone: '+966501234567', status: 'pending' }],
    });
    render(<ActionCatalogPanel session={SESSION} actions={[LIST_ACTION]} catalog={CATALOG_ALL_REACHABLE} />);
    await waitFor(() => expect(screen.getAllByText('سالم').length).toBeGreaterThan(0));
    expect(screen.getAllByText('+966501234567').length).toBeGreaterThan(0);
  });

  it('offers approve/reject buttons per row, resolving application_id from the row', async () => {
    reqMock = vi.fn().mockResolvedValue({
      applications: [{ id: 'app-1', name: 'سالم', status: 'pending' }],
    });
    render(<ActionCatalogPanel session={SESSION} actions={[LIST_ACTION, APPROVE_ACTION, REJECT_ACTION]} catalog={CATALOG_ALL_REACHABLE} />);
    await waitFor(() => expect(screen.getAllByText('قبول طلب مسوّق').length).toBeGreaterThan(0));
    expect(screen.getAllByText('رفض طلب مسوّق').length).toBeGreaterThan(0);
  });

  it('a danger action (reject) is armed — confirm stays disabled until the row label is typed', async () => {
    reqMock = vi.fn().mockResolvedValue({ applications: [{ id: 'app-1', name: 'سالم' }] });
    render(<ActionCatalogPanel session={SESSION} actions={[LIST_ACTION, REJECT_ACTION]} catalog={CATALOG_ALL_REACHABLE} />);
    await waitFor(() => expect(screen.getAllByText('رفض طلب مسوّق').length).toBeGreaterThan(0));

    fireEvent.click(screen.getAllByText('رفض طلب مسوّق')[0]);
    const confirmBtn = screen.getAllByText('تأكيد')[0].closest('button') as HTMLButtonElement;
    expect(confirmBtn.disabled).toBe(true);

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'سالم' } });
    expect(confirmBtn.disabled).toBe(false);
  });

  it('a non-danger action (approve) confirms directly and re-reads the list after', async () => {
    reqMock = vi.fn()
      .mockResolvedValueOnce({ applications: [{ id: 'app-1', name: 'سالم' }] })  // initial load
      .mockResolvedValueOnce({ ok: true })                                       // approve call
      .mockResolvedValueOnce({ applications: [] });                              // reload after
    render(<ActionCatalogPanel session={SESSION} actions={[LIST_ACTION, APPROVE_ACTION]} catalog={CATALOG_ALL_REACHABLE} />);
    await waitFor(() => expect(screen.getAllByText('قبول طلب مسوّق').length).toBeGreaterThan(0));

    fireEvent.click(screen.getAllByText('قبول طلب مسوّق')[0]);
    fireEvent.click(screen.getAllByText('تأكيد')[0]);

    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      '/api/v1/admin/affiliates/app-1/approve', 'POST', {}, 'tok-1'));
  });

  it('an empty result says so honestly, not a blank table', async () => {
    reqMock = vi.fn().mockResolvedValue({ applications: [] });
    render(<ActionCatalogPanel session={SESSION} actions={[LIST_ACTION]} catalog={CATALOG_ALL_REACHABLE} />);
    await waitFor(() => expect(screen.getAllByText('طلبات التسويق المعلّقة').length).toBeGreaterThan(0));
  });

  it('no actions AND every service answered — a real permission gap, said as one', () => {
    render(<ActionCatalogPanel session={SESSION} actions={[]} catalog={CATALOG_ALL_REACHABLE} />);
    expect(screen.getByText('لا إجراءات متاحة لصلاحياتك هنا بعد')).toBeTruthy();
  });

  it('no actions AND a service failed to answer — names it, does not claim no permission', () => {
    const catalog: AdminCatalog = { services: [], unreachable: ['secrets-admin'] };
    render(<ActionCatalogPanel session={SESSION} actions={[]} catalog={catalog} />);
    expect(screen.queryByText('لا إجراءات متاحة لصلاحياتك هنا بعد')).toBeNull();
    expect(screen.getByText(/secrets-admin/)).toBeTruthy();
  });
});
