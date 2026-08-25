import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AdminAuditLog } from './AdminAuditLog';
import type { AdminSession } from './api';

const SESSION: AdminSession = { access_token: 'tok-1' };

const CATALOG = {
  services: [{ service: 'audit-service', actions: [
    { id: 'audit.query', label: 'x', method: 'GET' as const, path: '/api/v1/audit', capability: 'platform.audit' },
    { id: 'audit.verify', label: 'x', method: 'GET' as const, path: '/api/v1/audit/verify', capability: 'platform.audit' },
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

describe('AdminAuditLog', () => {
  it('loads events on first render with no filters', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({
      events: [{ id: 'e1', seq: 1, ts: '2026-08-01T00:00:00Z', service: 'billing-service',
                action: 'billing.platform_invoices_viewed', actor: 'op-1', resource: 'invoices', tenant: '_platform', ip: '' }],
      count: 1,
    });

    render(<AdminAuditLog session={SESSION} />);
    await waitFor(() => expect(screen.getAllByText('billing.platform_invoices_viewed').length).toBeGreaterThan(0));
  });

  it('searching with a filter calls audit.query with that query string', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({ events: [], count: 0 });

    render(<AdminAuditLog session={SESSION} />);
    await waitFor(() => expect(reqMock).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByLabelText('الفاعل'), { target: { value: 'op-1' } });
    fireEvent.click(screen.getByText('بحث'));

    await waitFor(() => expect(reqMock).toHaveBeenLastCalledWith(
      '/api/v1/audit?actor=op-1', 'GET', undefined, 'tok-1',
    ));
  });

  it('verify shows the ok badge on a healthy chain', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn()
      .mockResolvedValueOnce({ events: [], count: 0 })
      .mockResolvedValueOnce({ ok: true, checked: 42, first_bad_seq: null });

    render(<AdminAuditLog session={SESSION} />);
    fireEvent.click(await screen.findByText('تحقّق الآن'));
    await waitFor(() => expect(screen.getByText(/سليمة/)).toBeTruthy());
  });

  it('verify shows the broken badge with the reason and seq', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn()
      .mockResolvedValueOnce({ events: [], count: 0 })
      .mockResolvedValueOnce({ ok: false, checked: 10, first_bad_seq: 7, reason: 'content tampered (hash mismatch)' });

    render(<AdminAuditLog session={SESSION} />);
    fireEvent.click(await screen.findByText('تحقّق الآن'));
    await waitFor(() => expect(screen.getByText(/مكسورة/)).toBeTruthy());
    expect(screen.getByText(/content tampered/)).toBeTruthy();
  });
});
