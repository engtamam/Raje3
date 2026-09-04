/**
 * صفحة "تذاكر" المستقلة بالشريط الجانبي — تختار مستأجراً من tenant.list أولاً (لا مسار
 * "كل التذاكر" — tenant مطلوب على مسارات ticket-service الإدارية، انظر AdminTickets.tsx's own
 * header)، ثم تعرض نفس TicketsTab المستخدمة داخل ملف عميل واحد.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AdminTickets } from './AdminTickets';
import type { AdminSession } from './api';

const SESSION: AdminSession = { access_token: 'tok-1' };

const CATALOG = {
  services: [
    { service: 'tenant-service', actions: [
      { id: 'tenant.list', label: 'x', method: 'GET' as const,
       path: '/api/v1/tenants', capability: 'platform.tenants' },
    ] },
    { service: 'ticket-service', actions: [
      { id: 'tickets.platform_inbox', label: 'x', method: 'GET' as const,
       path: '/api/v1/tickets/admin/tickets', capability: 'platform.tickets' },
      { id: 'tickets.platform_detail', label: 'x', method: 'GET' as const,
       path: '/api/v1/tickets/admin/tickets/{ticket_id}', capability: 'platform.tickets' },
    ] },
  ],
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

describe('AdminTickets (standalone sidebar page)', () => {
  it('picks a tenant first, then shows that tenant\'s tickets — no all-tenants call ever made', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockImplementation((path: string) => {
      if (path === '/api/v1/tenants') {
        return Promise.resolve({
          tenants: [{ id: 't1', slug: 'shop-one', name: 'محل الأول', status: 'active',
                     created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-02T00:00:00Z' }],
        });
      }
      if (path.includes('/tickets/admin/tickets?tenant=t1')) {
        return Promise.resolve({
          tenant: 't1',
          tickets: [{ id: 'tk1', type: 'support', status: 'open', priority: 'normal',
                     created: '2026-09-01T00:00:00Z', updated: '2026-09-01T01:00:00Z',
                     assignee: '', tags: [], raiser_ref: 'ref-1' }],
        });
      }
      return Promise.resolve({});
    });

    render(<AdminTickets session={SESSION} />);
    await waitFor(() => expect(screen.getByText('محل الأول')).toBeTruthy());

    // never called the list route without a tenant filter — the route requires one (422 without)
    expect(reqMock).not.toHaveBeenCalledWith('/api/v1/tickets/admin/tickets', 'GET', undefined, 'tok-1');

    fireEvent.click(screen.getByText('محل الأول'));
    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/tickets/admin/tickets?tenant=t1'), 'GET', undefined, 'tok-1'));
    await waitFor(() => expect(screen.getByText('tk1')).toBeTruthy());
  });

  it('search filters the tenant list locally by name or slug', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockImplementation((path: string) => {
      if (path === '/api/v1/tenants') {
        return Promise.resolve({
          tenants: [
            { id: 't1', slug: 'shop-one', name: 'محل الأول', status: 'active',
             created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-02T00:00:00Z' },
            { id: 't2', slug: 'shop-two', name: 'محل الثاني', status: 'active',
             created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-02T00:00:00Z' },
          ],
        });
      }
      return Promise.resolve({});
    });

    render(<AdminTickets session={SESSION} />);
    await waitFor(() => expect(screen.getByText('محل الأول')).toBeTruthy());
    expect(screen.getByText('محل الثاني')).toBeTruthy();

    fireEvent.change(screen.getByPlaceholderText('ابحث باسم العميل…'), { target: { value: 'الثاني' } });
    await waitFor(() => expect(screen.queryByText('محل الأول')).toBeNull());
    expect(screen.getByText('محل الثاني')).toBeTruthy();
  });
});
