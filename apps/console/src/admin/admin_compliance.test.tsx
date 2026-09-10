/**
 * الامتثال — التبويبات الستة كانت مُعلَنة بالخلفية بلا شاشة. تحقّق أهم اثنين: حظر الحذف (يفتح
 * على أول تبويب) وطلبات DSAR (يحتوي قائمتين تجنّب المحرّك العام تصادمها).
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AdminCompliance } from './AdminCompliance';
import type { AdminSession } from './api';

const SESSION: AdminSession = { access_token: 'tok-1' };

const CATALOG = {
  services: [{ service: 'compliance-service', actions: [
    { id: 'compliance.list_legal_holds', label: 'x', method: 'GET' as const,
     path: '/api/v1/compliance/legal-holds', capability: 'platform.compliance' },
    { id: 'compliance.place_legal_hold', label: 'وضع حظر', method: 'POST' as const,
     path: '/api/v1/compliance/legal-holds', capability: 'platform.compliance' },
    { id: 'compliance.release_legal_hold', label: 'رفع الحظر', method: 'POST' as const,
     path: '/api/v1/compliance/legal-holds/{id}/release', capability: 'platform.compliance',
     params: [{ name: 'id', in: 'path' as const, type: 'string', required: true }] },
    { id: 'compliance.list_dsar', label: 'x', method: 'GET' as const,
     path: '/api/v1/compliance/dsar', capability: 'platform.compliance' },
    { id: 'compliance.list_data_targets', label: 'x', method: 'GET' as const,
     path: '/api/v1/compliance/data-targets', capability: 'platform.compliance' },
    { id: 'compliance.list_ropa', label: 'x', method: 'GET' as const,
     path: '/api/v1/compliance/ropa', capability: 'platform.compliance' },
  ] }, { service: 'operations', actions: [
    { id: 'operations.customer_by_phone', label: 'ابحث عن عميل برقم جواله', method: 'GET' as const,
     path: '/api/v1/platform/customers/by-phone', capability: 'platform.operations' },
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

describe('AdminCompliance', () => {
  it('opens on legal holds by default and lists them', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({
      holds: [{ id: 'h1', tenant: 'tnt_x', subject: 'sub_1', reason: 'نزاع قضائي' }],
    });
    render(<AdminCompliance session={SESSION} />);
    await waitFor(() => expect(screen.getAllByText('نزاع قضائي').length).toBeGreaterThan(0));
    expect(screen.getAllByText('وضع حظر').length).toBeGreaterThan(0);
    expect(screen.getAllByText('رفع الحظر').length).toBeGreaterThan(0);
  });

  it('switching to «جهات البيانات» does not also render the RoPA list (group collision avoided)', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn()
      .mockResolvedValueOnce({ holds: [] })                                   // legal holds initial
      .mockResolvedValueOnce({ targets: [{ id: 't1', service: 'operations', category: 'visits' }] });
    render(<AdminCompliance session={SESSION} />);
    await waitFor(() => expect(reqMock).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByText('جهات البيانات'));
    await waitFor(() => expect(screen.getAllByText('operations').length).toBeGreaterThan(0));
    // RoPA's own list action must NOT have been called — each tab owns its exact list action.
    expect(reqMock).not.toHaveBeenCalledWith('/api/v1/compliance/ropa', 'GET', undefined, 'tok-1');
  });

  it('searches a customer by tenant + phone and shows the found profile', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn()
      .mockResolvedValueOnce({ holds: [] })   // legal holds, initial tab load
      .mockResolvedValueOnce({
        customer: { id: 'cus_1', tenant: 'tnt_x', phone: '0501234567', name: 'أحمد',
                   visit_count: 3, last_visit: 1_700_000_000 },
      });
    render(<AdminCompliance session={SESSION} />);
    await waitFor(() => expect(reqMock).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByPlaceholderText('tnt_...'), { target: { value: 'tnt_x' } });
    fireEvent.change(screen.getByPlaceholderText('05xxxxxxxx'), { target: { value: '0501234567' } });
    fireEvent.click(screen.getByText('بحث'));

    await waitFor(() => expect(screen.getByText('أحمد')).toBeTruthy());
    expect(reqMock).toHaveBeenLastCalledWith(
      '/api/v1/platform/customers/by-phone?tenant=tnt_x&phone=0501234567',
      'GET', undefined, 'tok-1');
  });

  it('a search that finds nobody says so, not a blank card', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn()
      .mockResolvedValueOnce({ holds: [] })
      .mockResolvedValueOnce({ customer: null });
    render(<AdminCompliance session={SESSION} />);
    await waitFor(() => expect(reqMock).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByPlaceholderText('tnt_...'), { target: { value: 'tnt_x' } });
    fireEvent.change(screen.getByPlaceholderText('05xxxxxxxx'), { target: { value: '0500000000' } });
    fireEvent.click(screen.getByText('بحث'));

    await waitFor(() => expect(screen.getByText(/لا عميل بهذا الرقم/)).toBeTruthy());
  });

  it('a tab the caller cannot read at all is not offered', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue({
      services: [{ service: 'compliance-service', actions: [
        { id: 'compliance.list_legal_holds', label: 'x', method: 'GET' as const,
         path: '/api/v1/compliance/legal-holds', capability: 'platform.compliance' },
      ] }],
      unreachable: [],
    });
    reqMock = vi.fn().mockResolvedValue({ holds: [] });
    render(<AdminCompliance session={SESSION} />);
    await waitFor(() => expect(screen.getAllByText('حظر الحذف').length).toBeGreaterThan(0));
    expect(screen.queryByText('طلبات الحذف والاطّلاع')).toBeNull();
  });
});
