/**
 * نجاح العملاء — يجيب المستأجرين (`tenant.list`) ثم يطلب فحصهم (`operations.customer_success_scan`)،
 * يعرض بطاقات ملخّص ملوّنة وجدول المحلات المتعثّرة، وتغيير مدّة التعثّر يعيد الفحص فوراً.
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
    { service: 'operations', actions: [
      { id: 'operations.customer_success_scan', label: 'x', method: 'POST' as const,
       path: '/api/v1/platform/customers/success-scan', capability: 'platform.operations' },
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

function goToSuccessTab() {
  fireEvent.click(screen.getByText('نجاح العملاء'));
}

describe('CustomerSuccess tab', () => {
  it('scans the real tenant list and shows stalling shops, colour-coded by reason', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockImplementation((path: string) => {
      if (path === '/api/v1/tenants') {
        return Promise.resolve({ tenants: [
          { id: 't1', name: 'محل بلا خدمات', slug: 's1', status: 'active',
           created_at: '2020-01-01T00:00:00Z', updated_at: '2020-01-01T00:00:00Z' },
        ] });
      }
      if (path === '/api/v1/platform/customers/success-scan') {
        return Promise.resolve({
          stalling: [{ tenant: 't1', name: 'محل بلا خدمات',
                      no_services_after_stall: true, has_services_no_visits: false }],
          scanned: 1,
        });
      }
      return Promise.resolve({});
    });

    render(<AdminCustomers session={SESSION} />);
    await waitFor(() => expect(screen.getByText('نجاح العملاء')).toBeTruthy());
    goToSuccessTab();

    await waitFor(() => expect(screen.getAllByText('محل بلا خدمات').length).toBeGreaterThan(0));
    expect(screen.getAllByText('بلا خدمات منذ التسجيل').length).toBeGreaterThan(0);

    // The scan call carried the real tenant it fetched, not a hardcoded/empty body.
    const scanCall = reqMock.mock.calls.find((c) => c[0] === '/api/v1/platform/customers/success-scan');
    expect(scanCall).toBeTruthy();
    const scanBody = scanCall![2] as { tenants: { id: string }[]; stall_days: number };
    expect(scanBody.tenants).toEqual([{ id: 't1', name: 'محل بلا خدمات', created_at: '2020-01-01T00:00:00Z' }]);
    expect(scanBody.stall_days).toBe(3);
  });

  it('changing the stall-days select re-scans immediately with the new value', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockImplementation((path: string) => {
      if (path === '/api/v1/tenants') return Promise.resolve({ tenants: [] });
      if (path === '/api/v1/platform/customers/success-scan') {
        return Promise.resolve({ stalling: [], scanned: 0 });
      }
      return Promise.resolve({});
    });

    render(<AdminCustomers session={SESSION} />);
    await waitFor(() => expect(screen.getByText('نجاح العملاء')).toBeTruthy());
    goToSuccessTab();
    await waitFor(() => expect(reqMock.mock.calls.some(
      (c) => c[0] === '/api/v1/platform/customers/success-scan')).toBe(true));
    const callsBefore = reqMock.mock.calls.length;

    fireEvent.change(screen.getByDisplayValue('3 أيام'), { target: { value: '7' } });
    await waitFor(() => expect(reqMock.mock.calls.length).toBeGreaterThan(callsBefore));
    const scanCalls = reqMock.mock.calls.filter((c) => c[0] === '/api/v1/platform/customers/success-scan');
    const last = scanCalls[scanCalls.length - 1];
    expect((last[2] as { stall_days: number }).stall_days).toBe(7);
  });

  it('no stalling shops reads as the platform being healthy, not a blank screen', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockImplementation((path: string) => {
      if (path === '/api/v1/tenants') return Promise.resolve({ tenants: [] });
      if (path === '/api/v1/platform/customers/success-scan') {
        return Promise.resolve({ stalling: [], scanned: 0 });
      }
      return Promise.resolve({});
    });

    render(<AdminCustomers session={SESSION} />);
    await waitFor(() => expect(screen.getByText('نجاح العملاء')).toBeTruthy());
    goToSuccessTab();

    await waitFor(() => expect(screen.getByText('لا محلات متعثّرة بهذي المدّة — الوضع سليم')).toBeTruthy());
  });
});
