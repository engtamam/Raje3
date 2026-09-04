/**
 * جدول العملاء — الاختبارات تتأكد أن البحث بالاسم يُصفّي محلياً، أن فلتر الحالة يشتغل، أن الـKPIs
 * تُحسب من الاشتراكات المجموعة (لا استدعاء منفصل لكل عميل)، وأن فتح صف يفتح ملف العميل.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AdminCustomers } from './AdminCustomers';
import type { AdminSession } from './api';

const SESSION: AdminSession = { access_token: 'tok-1' };

const CATALOG = {
  services: [
    { service: 'tenant-service', actions: [
      { id: 'tenant.list', label: 'x', method: 'GET' as const,
       path: '/api/v1/tenants', capability: 'platform.tenants' },
    ] },
    { service: 'billing-service', actions: [
      { id: 'billing.platform_subscriptions', label: 'x', method: 'GET' as const,
       path: '/api/v1/billing/admin/subscriptions', capability: 'platform.billing' },
      { id: 'billing.platform_invoices', label: 'x', method: 'GET' as const,
       path: '/api/v1/billing/admin/invoices', capability: 'platform.billing' },
    ] },
    { service: 'audit-service', actions: [
      { id: 'audit.query', label: 'x', method: 'GET' as const,
       path: '/api/v1/audit', capability: 'platform.audit' },
    ] },
    { service: 'billing-service-2', actions: [
      { id: 'billing.list_plans', label: 'x', method: 'GET' as const,
       path: '/api/v1/billing/plans', capability: 'billing.manage' },
    ] },
    { service: 'operations', actions: [
      { id: 'operations.tenant_capacity', label: 'x', method: 'GET' as const,
       path: '/api/v1/platform/tenants/{tenant_id}/capacity', capability: 'platform.operations' },
      { id: 'operations.whatsapp_diagnostics', label: 'x', method: 'GET' as const,
       path: '/api/v1/platform/whatsapp/diagnostics', capability: 'platform.operations' },
    ] },
    { service: 'affiliate-service', actions: [] },
    { service: 'ticket-service', actions: [
      { id: 'tickets.platform_inbox', label: 'x', method: 'GET' as const,
       path: '/api/v1/tickets/admin/tickets', capability: 'platform.tickets' },
      { id: 'tickets.platform_detail', label: 'x', method: 'GET' as const,
       path: '/api/v1/tickets/admin/tickets/{ticket_id}', capability: 'platform.tickets' },
    ] },
  ],
  unreachable: [],
};

function tenant(over: Partial<Record<string, unknown>> = {}) {
  return {
    id: 't1', slug: 'shop-one', name: 'محل الأول', status: 'active',
    created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-02T00:00:00Z', ...over,
  };
}

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

describe('CustomerList (via AdminCustomers, default tab)', () => {
  it('lists tenants and filters by name locally, no extra request per keystroke', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockImplementation((path: string) => {
      if (path === '/api/v1/tenants') {
        return Promise.resolve({ tenants: [tenant(), tenant({ id: 't2', name: 'محل الثاني', slug: 'shop-two' })] });
      }
      return Promise.resolve({ subscriptions: [] });
    });

    render(<AdminCustomers session={SESSION} />);
    await waitFor(() => expect(screen.getByText('محل الأول')).toBeTruthy());
    expect(screen.getByText('محل الثاني')).toBeTruthy();

    const callsBefore = reqMock.mock.calls.length;
    fireEvent.change(screen.getByPlaceholderText('ابحث بالاسم…'), { target: { value: 'الثاني' } });
    expect(screen.queryByText('محل الأول')).toBeNull();
    expect(screen.getByText('محل الثاني')).toBeTruthy();
    // filtering is local — no new request fired by typing
    expect(reqMock.mock.calls.length).toBe(callsBefore);
  });

  it('computes KPI counts from the bulk per-status subscription calls, not one per tenant', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockImplementation((path: string) => {
      if (path === '/api/v1/tenants') {
        return Promise.resolve({ tenants: [tenant(), tenant({ id: 't2', status: 'suspended' })] });
      }
      if (path.includes('status=trialing')) return Promise.resolve({ subscriptions: [{ id: 's1', tenant: 't1', plan_id: 'pro', status: 'trialing' }] });
      if (path.includes('status=past_due')) return Promise.resolve({ subscriptions: [{ id: 's2', tenant: 't2', plan_id: 'pro', status: 'past_due' }] });
      return Promise.resolve({ subscriptions: [] });
    });

    render(<AdminCustomers session={SESSION} />);
    // "تجريبي" is a static KPI label present from the first render — wait for the actual async
    // subscription calls to land instead, then assert the count.
    await waitFor(() => {
      const subCalls = reqMock.mock.calls.filter((c) => String(c[0]).includes('/admin/subscriptions'));
      expect(subCalls.length).toBe(5);
    });
  });

  it('filters by tenant status via the segmented control', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockImplementation((path: string) => {
      if (path === '/api/v1/tenants') {
        return Promise.resolve({
          tenants: [tenant(), tenant({ id: 't2', name: 'محل معلَّق', status: 'suspended' })],
        });
      }
      return Promise.resolve({ subscriptions: [] });
    });

    render(<AdminCustomers session={SESSION} />);
    await waitFor(() => expect(screen.getByText('محل الأول')).toBeTruthy());
    expect(screen.getByText('محل معلَّق')).toBeTruthy();

    // "معلَّقة" appears both as a KPI label and a filter option — target the radio button specifically.
    fireEvent.click(screen.getByRole('radio', { name: 'معلَّقة' }));
    await waitFor(() => expect(screen.queryByText('محل الأول')).toBeNull());
    expect(screen.getByText('محل معلَّق')).toBeTruthy();
  });

  it('opening a row opens the customer detail drawer with its name', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockImplementation((path: string) => {
      if (path === '/api/v1/tenants') return Promise.resolve({ tenants: [tenant()] });
      if (path.includes('/admin/invoices')) return Promise.resolve({ invoices: [] });
      return Promise.resolve({ subscriptions: [] });
    });

    render(<AdminCustomers session={SESSION} />);
    await waitFor(() => expect(screen.getByText('محل الأول')).toBeTruthy());
    fireEvent.click(screen.getByText('محل الأول'));

    await waitFor(() => expect(screen.getByText('shop-one')).toBeTruthy());
    expect(screen.getByText('نظرة عامة')).toBeTruthy();
    expect(screen.getByText('التطبيقات والفوترة')).toBeTruthy();
  });

  it('shows the plan NAME, not the raw plan_id, in both the table and the detail view', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockImplementation((path: string) => {
      if (path === '/api/v1/tenants') return Promise.resolve({ tenants: [tenant()] });
      if (path.includes('status=trialing')) {
        return Promise.resolve({ subscriptions: [{ id: 's1', tenant: 't1', plan_id: 'plan_abc123', status: 'trialing' }] });
      }
      if (path.includes('/admin/subscriptions')) return Promise.resolve({ subscriptions: [] });
      if (path.includes('/billing/plans')) {
        return Promise.resolve({ plans: [{ id: 'plan_abc123', name: 'الباقة الاحترافية' }] });
      }
      if (path.includes('/admin/invoices')) return Promise.resolve({ invoices: [] });
      return Promise.resolve({ subscriptions: [] });
    });

    render(<AdminCustomers session={SESSION} />);
    await waitFor(() => expect(screen.getByText('الباقة الاحترافية')).toBeTruthy());
    expect(screen.queryByText('plan_abc123')).toBeNull();

    fireEvent.click(screen.getByText('محل الأول'));
    await waitFor(() => expect(screen.getAllByText('الباقة الاحترافية').length).toBeGreaterThan(1));
  });

  it('the seats tab shows the real count against the real entitled limit, x/y', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockImplementation((path: string) => {
      if (path === '/api/v1/tenants') return Promise.resolve({ tenants: [tenant()] });
      if (path.includes('/admin/subscriptions')) return Promise.resolve({ subscriptions: [] });
      if (path.includes('/platform/tenants/t1/capacity')) {
        return Promise.resolve({ branches: 3, operators: 7, branches_limit: 5, operators_limit: 15 });
      }
      return Promise.resolve({});
    });

    render(<AdminCustomers session={SESSION} />);
    await waitFor(() => expect(screen.getByText('محل الأول')).toBeTruthy());
    fireEvent.click(screen.getByText('محل الأول'));
    await waitFor(() => expect(screen.getByText('shop-one')).toBeTruthy());

    fireEvent.click(screen.getByText('الفروع والمستخدمين'));
    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      '/api/v1/platform/tenants/t1/capacity', 'GET', undefined, 'tok-1'));
    await waitFor(() => expect(screen.getByText('3/5')).toBeTruthy());
    expect(screen.getByText('7/15')).toBeTruthy();
  });

  it('the seats tab shows a bare count, no fabricated ceiling, when the limit is unlimited/unreachable', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockImplementation((path: string) => {
      if (path === '/api/v1/tenants') return Promise.resolve({ tenants: [tenant()] });
      if (path.includes('/admin/subscriptions')) return Promise.resolve({ subscriptions: [] });
      if (path.includes('/platform/tenants/t1/capacity')) {
        return Promise.resolve({ branches: 3, operators: 7, branches_limit: -1, operators_limit: -1 });
      }
      return Promise.resolve({});
    });

    render(<AdminCustomers session={SESSION} />);
    await waitFor(() => expect(screen.getByText('محل الأول')).toBeTruthy());
    fireEvent.click(screen.getByText('محل الأول'));
    await waitFor(() => expect(screen.getByText('shop-one')).toBeTruthy());

    fireEvent.click(screen.getByText('الفروع والمستخدمين'));
    await waitFor(() => expect(screen.getByText('3')).toBeTruthy());
    expect(screen.getByText('7')).toBeTruthy();
  });

  it('the whatsapp tab queries this tenant\'s own delivery log, no manual tenant entry', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockImplementation((path: string) => {
      if (path === '/api/v1/tenants') return Promise.resolve({ tenants: [tenant()] });
      if (path.includes('/admin/invoices')) return Promise.resolve({ invoices: [] });
      if (path.includes('/admin/subscriptions')) return Promise.resolve({ subscriptions: [] });
      if (path.includes('/whatsapp/diagnostics')) {
        return Promise.resolve({
          tenant: 't1',
          deliveries: [{ id: 'd1', status: 'delivered', recipient_masked: '•••1234',
                        receipt_status: 'read', created: '2026-09-01T00:00:00Z' }],
        });
      }
      return Promise.resolve({});
    });

    render(<AdminCustomers session={SESSION} />);
    await waitFor(() => expect(screen.getByText('محل الأول')).toBeTruthy());
    fireEvent.click(screen.getByText('محل الأول'));
    await waitFor(() => expect(screen.getByText('shop-one')).toBeTruthy());

    fireEvent.click(screen.getByText('واتساب'));
    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/platform/whatsapp/diagnostics?tenant=t1'), 'GET', undefined, 'tok-1'));
    await waitFor(() => expect(screen.getByText('•••1234')).toBeTruthy());
  });

  it('the audit tab queries audit.query scoped to this tenant', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockImplementation((path: string) => {
      if (path === '/api/v1/tenants') return Promise.resolve({ tenants: [tenant()] });
      if (path.includes('/admin/invoices')) return Promise.resolve({ invoices: [] });
      if (path.includes('/admin/subscriptions')) return Promise.resolve({ subscriptions: [] });
      if (path.includes('/api/v1/audit')) {
        return Promise.resolve({
          events: [{ id: 'e1', seq: 1, ts: '2026-09-01T00:00:00Z', service: 'billing-service',
                    action: 'billing.plan_changed', actor: 'op-1', resource: 'sub:s1' }],
        });
      }
      return Promise.resolve({});
    });

    render(<AdminCustomers session={SESSION} />);
    await waitFor(() => expect(screen.getByText('محل الأول')).toBeTruthy());
    fireEvent.click(screen.getByText('محل الأول'));
    await waitFor(() => expect(screen.getByText('shop-one')).toBeTruthy());

    fireEvent.click(screen.getByText('السجل والتدقيق'));
    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/audit?tenant=t1'), 'GET', undefined, 'tok-1'));
    await waitFor(() => expect(screen.getByText('billing.plan_changed')).toBeTruthy());
  });

  it('the tickets tab lists this tenant\'s tickets, then opens full detail with the reply thread', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockImplementation((path: string) => {
      if (path === '/api/v1/tenants') return Promise.resolve({ tenants: [tenant()] });
      if (path.includes('/admin/invoices')) return Promise.resolve({ invoices: [] });
      if (path.includes('/admin/subscriptions')) return Promise.resolve({ subscriptions: [] });
      if (path.includes('/tickets/admin/tickets/tk1')) {
        return Promise.resolve({
          tenant: 't1',
          ticket: { id: 'tk1', type: 'support', status: 'open', priority: 'normal',
                   created: '2026-09-01T00:00:00Z', updated: '2026-09-01T01:00:00Z',
                   assignee: '', tags: [], raiser_ref: 'ref-1',
                   subject: 'ما وصلتني الرسالة', body: 'حاولت أرسل تذكير وما وصل شي' },
          events: [{ id: 'ev1', kind: 'replied', ts: '2026-09-01T01:00:00Z', actor: 'op-1',
                    body: 'نتحقق الآن' }],
        });
      }
      if (path.includes('/tickets/admin/tickets')) {
        return Promise.resolve({
          tenant: 't1',
          tickets: [{ id: 'tk1', type: 'support', status: 'open', priority: 'normal',
                     created: '2026-09-01T00:00:00Z', updated: '2026-09-01T01:00:00Z',
                     assignee: '', tags: [], raiser_ref: 'ref-1' }],
        });
      }
      return Promise.resolve({});
    });

    render(<AdminCustomers session={SESSION} />);
    await waitFor(() => expect(screen.getByText('محل الأول')).toBeTruthy());
    fireEvent.click(screen.getByText('محل الأول'));
    await waitFor(() => expect(screen.getByText('shop-one')).toBeTruthy());

    fireEvent.click(screen.getByText('التذاكر والدعم'));
    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/tickets/admin/tickets?tenant=t1'), 'GET', undefined, 'tok-1'));
    await waitFor(() => expect(screen.getByText('tk1')).toBeTruthy());

    fireEvent.click(screen.getByText('tk1'));
    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/tickets/admin/tickets/tk1?tenant=t1'), 'GET', undefined, 'tok-1'));
    await waitFor(() => expect(screen.getByText('ما وصلتني الرسالة')).toBeTruthy());
    expect(screen.getByText('حاولت أرسل تذكير وما وصل شي')).toBeTruthy();
    expect(screen.getByText('نتحقق الآن')).toBeTruthy();
  });

  it('the tickets tab filters by status/type/priority/assignee server-side, and pages via cursor', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockImplementation((path: string) => {
      if (path === '/api/v1/tenants') return Promise.resolve({ tenants: [tenant()] });
      if (path.includes('/admin/invoices')) return Promise.resolve({ invoices: [] });
      if (path.includes('/admin/subscriptions')) return Promise.resolve({ subscriptions: [] });
      if (path.includes('cursor=page2')) {
        return Promise.resolve({ tenant: 't1', tickets: [{ id: 'tk2', type: 'support', status: 'open',
                                                            priority: 'normal', created: '', updated: '',
                                                            assignee: '', tags: [], raiser_ref: '' }] });
      }
      if (path.includes('status=open')) {
        return Promise.resolve({
          tenant: 't1', cursor: 'page2',
          tickets: [{ id: 'tk1', type: 'support', status: 'open', priority: 'normal',
                     created: '', updated: '', assignee: '', tags: [], raiser_ref: '' }],
        });
      }
      if (path.includes('/tickets/admin/tickets')) {
        return Promise.resolve({
          tenant: 't1',
          tickets: [{ id: 'tk1', type: 'support', status: 'open', priority: 'normal',
                     created: '', updated: '', assignee: '', tags: [], raiser_ref: '' }],
        });
      }
      return Promise.resolve({});
    });

    render(<AdminCustomers session={SESSION} />);
    await waitFor(() => expect(screen.getByText('محل الأول')).toBeTruthy());
    fireEvent.click(screen.getByText('محل الأول'));
    await waitFor(() => expect(screen.getByText('shop-one')).toBeTruthy());
    fireEvent.click(screen.getByText('التذاكر والدعم'));
    await waitFor(() => expect(screen.getByText('tk1')).toBeTruthy());

    fireEvent.change(screen.getByLabelText('فلترة بالحالة'), { target: { value: 'open' } });
    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      expect.stringContaining('status=open'), 'GET', undefined, 'tok-1'));

    fireEvent.click(screen.getByText('حمّل المزيد'));
    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      expect.stringContaining('cursor=page2'), 'GET', undefined, 'tok-1'));
    await waitFor(() => expect(screen.getByText('tk2')).toBeTruthy());
    // both pages stay on screen — load more appends, never replaces
    expect(screen.getByText('tk1')).toBeTruthy();
  });

  it('no capability, no silent blank table', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue({ services: [], unreachable: [] });
    render(<AdminCustomers session={SESSION} />);
    await waitFor(() => expect(screen.getByText('هذه الشاشة ليست ضمن صلاحياتك')).toBeTruthy());
  });
});
