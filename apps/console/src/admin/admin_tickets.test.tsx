/**
 * صفحة "تذاكر" — صندوق وارد موحّد عبر كل المستأجرين مباشرة (v0.18.21)، فلتر status=open
 * افتراضي (لا قراءة بلا فلتر أصلاً)، بلا اختيار عميل أولاً.
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

describe('AdminTickets (unified cross-tenant inbox)', () => {
  it('loads status=open across all tenants by default — no tenant picked first', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockImplementation((path: string) => {
      if (path === '/api/v1/tenants') {
        return Promise.resolve({
          tenants: [{ id: 't1', slug: 'shop-one', name: 'محل الأول', status: 'active',
                     created_at: '', updated_at: '' }],
        });
      }
      if (path.includes('/tickets/admin/tickets?')) {
        return Promise.resolve({
          tickets: [{ id: 'tk1', tenant: 't1', type: 'support', status: 'open', priority: 'normal',
                     created: '2026-09-01T00:00:00Z', updated: '2026-09-01T01:00:00Z',
                     assignee: '', tags: [], raiser_ref: '' }],
        });
      }
      return Promise.resolve({});
    });

    render(<AdminTickets session={SESSION} />);
    // no tenant picker, no click needed — the inbox itself is the default view
    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/tickets/admin/tickets?status=open'), 'GET', undefined, 'tok-1'));
    // never called the list route with NO filter at all
    expect(reqMock).not.toHaveBeenCalledWith('/api/v1/tickets/admin/tickets?limit=50', 'GET', undefined, 'tok-1');
    await waitFor(() => expect(screen.getByText('tk1')).toBeTruthy());
    expect(screen.getByText('محل الأول')).toBeTruthy();
  });

  it('opening a row fetches that ticket\'s full detail using ITS OWN tenant field', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockImplementation((path: string) => {
      if (path === '/api/v1/tenants') {
        return Promise.resolve({
          tenants: [{ id: 't2', slug: 'shop-two', name: 'محل الثاني', status: 'active',
                     created_at: '', updated_at: '' }],
        });
      }
      if (path.includes('/tickets/admin/tickets/tk9')) {
        return Promise.resolve({
          ticket: { id: 'tk9', tenant: 't2', type: 'support', status: 'open', priority: 'normal',
                   created: '', updated: '', assignee: '', tags: [], raiser_ref: '',
                   subject: 'مشكلة بالدفع', body: 'الدفع ما اكتمل' },
          events: [],
        });
      }
      if (path.includes('/tickets/admin/tickets?')) {
        return Promise.resolve({
          tickets: [{ id: 'tk9', tenant: 't2', type: 'support', status: 'open', priority: 'normal',
                     created: '', updated: '', assignee: '', tags: [], raiser_ref: '' }],
        });
      }
      return Promise.resolve({});
    });

    render(<AdminTickets session={SESSION} />);
    await waitFor(() => expect(screen.getByText('tk9')).toBeTruthy());
    fireEvent.click(screen.getByText('tk9'));
    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/tickets/admin/tickets/tk9?tenant=t2'), 'GET', undefined, 'tok-1'));
    await waitFor(() => expect(screen.getByText('مشكلة بالدفع')).toBeTruthy());
  });
});
