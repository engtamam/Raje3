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
    // getAllByText — rj-ui's own Table renders a desktop table AND a mobile card list at once,
    // and "محل الأول" also appears once more as the tenant filter's own <option>.
    await waitFor(() => expect(screen.getAllByText('tk1').length).toBeGreaterThan(0));
    expect(screen.getAllByText('محل الأول').length).toBeGreaterThan(0);
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
    await waitFor(() => expect(screen.getAllByText('tk9').length).toBeGreaterThan(0));
    fireEvent.click(screen.getAllByText('tk9')[0]);
    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/tickets/admin/tickets/tk9?tenant=t2'), 'GET', undefined, 'tok-1'));
    await waitFor(() => expect(screen.getByText('مشكلة بالدفع')).toBeTruthy());
  });

  it('the tenant filter is a real, working query param — was missing entirely before', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockImplementation((path: string) => {
      if (path === '/api/v1/tenants') {
        return Promise.resolve({
          tenants: [{ id: 't1', slug: 'shop-one', name: 'محل الأول', status: 'active',
                     created_at: '', updated_at: '' }],
        });
      }
      return Promise.resolve({ tickets: [] });
    });

    render(<AdminTickets session={SESSION} />);
    // wait for the tenant LIST to actually resolve and populate the <option>s — the <select>
    // itself renders immediately, before that fetch lands, with only "كل المحلات".
    await waitFor(() => expect(screen.getByText('محل الأول')).toBeTruthy());

    fireEvent.change(screen.getByLabelText('فلترة بالمحل'), { target: { value: 't1' } });
    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      expect.stringContaining('tenant=t1'), 'GET', undefined, 'tok-1'));
  });

  it('clearing every filter never re-fetches — the server refuses an empty where, so this side must not even ask', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockImplementation((path: string) => {
      if (path === '/api/v1/tenants') return Promise.resolve({ tenants: [] });
      if (path.includes('/tickets/admin/tickets?')) {
        return Promise.resolve({ tickets: [
          { id: 'tk1', tenant: 't1', type: 'support', status: 'open', priority: 'normal',
           created: '', updated: '', assignee: '', tags: [], raiser_ref: '' },
        ] });
      }
      return Promise.resolve({});
    });

    render(<AdminTickets session={SESSION} />);
    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      expect.stringContaining('status=open'), 'GET', undefined, 'tok-1'));
    reqMock.mockClear();

    fireEvent.change(screen.getByLabelText('فلترة بالحالة'), { target: { value: '' } });
    // the warning shows...
    await waitFor(() => expect(screen.getByText(
      'لازم فلتر واحد على الأقل — لا قراءة عابرة لكل المستأجرين بلا حدود، نفس قاعدة الفواتير.',
    )).toBeTruthy());
    // ...and the calm placeholder, never the contradictory "تعذّرت القراءة" a wasted, refused
    // fetch would have produced.
    expect(screen.getByText('اختر فلتراً لعرض التذاكر')).toBeTruthy();
    expect(screen.queryByText('تعذّرت قراءة التذاكر')).toBeNull();
    // and, above all, no request was ever sent for the tickets list with no filter at all.
    expect(reqMock).not.toHaveBeenCalledWith(
      expect.stringContaining('/tickets/admin/tickets?'), 'GET', undefined, 'tok-1');
  });

  it('KPI cards count escalated/pending from the shown page, colour-coded', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockImplementation((path: string) => {
      if (path === '/api/v1/tenants') return Promise.resolve({ tenants: [] });
      if (path.includes('/tickets/admin/tickets?')) {
        return Promise.resolve({ tickets: [
          { id: 'tk1', tenant: 't1', type: 'support', status: 'escalated', priority: 'high', created: '', updated: '', assignee: '', tags: [], raiser_ref: '' },
          { id: 'tk2', tenant: 't1', type: 'support', status: 'pending', priority: 'normal', created: '', updated: '', assignee: '', tags: [], raiser_ref: '' },
        ] });
      }
      return Promise.resolve({});
    });

    render(<AdminTickets session={SESSION} />);
    await waitFor(() => expect(screen.getByText('المعروضة')).toBeTruthy());
    expect(screen.getAllByText('2').length).toBeGreaterThan(0);
    expect(screen.getByText('مصعَّدة')).toBeTruthy();
    expect(screen.getByText('بالانتظار')).toBeTruthy();
  });
});
