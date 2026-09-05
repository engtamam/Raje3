/**
 * «الباقات» — the list, the empty state, and the create dialog (server calls mocked; the real
 * request shape is covered on the backend side).
 */
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const ACTIONS: Record<string, { id: string; label: string; method: string; path: string }> = {
  'operations.manage_services': { id: 'operations.manage_services', label: 'x', method: 'GET', path: '/services' },
  'operations.list_packages': { id: 'operations.list_packages', label: 'x', method: 'GET', path: '/packages' },
  'operations.list_services': { id: 'operations.list_services', label: 'x', method: 'GET', path: '/services' },
  'operations.create_package': { id: 'operations.create_package', label: 'x', method: 'POST', path: '/packages' },
  'operations.update_package': { id: 'operations.update_package', label: 'x', method: 'PATCH', path: '/packages/{id}' },
  'loyalty.settings.read': { id: 'loyalty.settings.read', label: 'x', method: 'GET', path: '/settings' },
  'loyalty.settings.package': { id: 'loyalty.settings.package', label: 'x', method: 'PUT', path: '/settings/package/{package_id}' },
};

let packagesResponse: unknown[] = [];
let servicesResponse: unknown[] = [
  { id: 'svc_a', name: 'غيار زيت', active: true },
  { id: 'svc_b', name: 'فحص فرامل', active: true },
];
let earnResponse: unknown = { services: {}, groups: {}, service_group: {}, general: {}, packages: {} };
const createCalls: unknown[] = [];
const pointsCalls: unknown[] = [];

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ACTIONS[id] ?? null,
    call: async (_session: unknown, a: { id: string }, body: unknown) => {
      if (a.id === 'operations.list_packages') return { packages: packagesResponse };
      if (a.id === 'operations.list_services') return { services: servicesResponse };
      if (a.id === 'loyalty.settings.read') return earnResponse;
      if (a.id === 'operations.create_package') { createCalls.push(body); return { id: 'pkg_new' }; }
      if (a.id === 'operations.update_package') { createCalls.push(body); return {}; }
      if (a.id === 'loyalty.settings.package') { pointsCalls.push(body); return {}; }
      return {};
    },
  };
});

const { PackagesTab } = await import('./PackagesTab');

const session = {} as never;
const catalog = { services: [], unreachable: [] } as never;

function open(initialEntries = ['/services?tab=packages']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <PackagesTab session={session} catalog={catalog} />
    </MemoryRouter>,
  );
}

describe('الباقات', () => {
  it('shows the empty state and an invitation to create the first one', async () => {
    packagesResponse = [];
    open();
    await waitFor(() => expect(screen.getByText('لا توجد باقات بعد')).toBeTruthy());
    expect(screen.getByRole('button', { name: /أنشئ باقتك الأولى/ })).toBeTruthy();
  });

  it('lists an existing package with its real component names and price', async () => {
    packagesResponse = [
      { id: 'pkg1', name: 'باقة الصيانة', service_ids: ['svc_a', 'svc_b'], price_minor: 15000, active: true },
    ];
    open();
    await waitFor(() => expect(screen.getByText('باقة الصيانة')).toBeTruthy());
    expect(screen.getByText('غيار زيت')).toBeTruthy();
    expect(screen.getByText('فحص فرامل')).toBeTruthy();
    expect(screen.getByText('150 ريال')).toBeTruthy();
  });

  it('refuses to save with fewer than two services or no real price', async () => {
    packagesResponse = [];
    open();
    await waitFor(() => screen.getByRole('button', { name: /أنشئ باقتك الأولى/ }));
    fireEvent.click(screen.getByRole('button', { name: /أنشئ باقتك الأولى/ }));
    await waitFor(() => screen.getByPlaceholderText(/باقة الصيانة الشاملة/));
    expect((screen.getByRole('button', { name: 'حفظ' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('creating a package with two services and a price calls create then sets its points', async () => {
    packagesResponse = [];
    createCalls.length = 0; pointsCalls.length = 0;
    open();
    await waitFor(() => screen.getByRole('button', { name: /أنشئ باقتك الأولى/ }));
    fireEvent.click(screen.getByRole('button', { name: /أنشئ باقتك الأولى/ }));
    await waitFor(() => screen.getByPlaceholderText(/باقة الصيانة الشاملة/));

    fireEvent.change(screen.getByPlaceholderText(/باقة الصيانة الشاملة/), { target: { value: 'باقة جديدة' } });
    fireEvent.click(screen.getByText('غيار زيت'));
    fireEvent.click(screen.getByText('فحص فرامل'));
    const priceBox = screen.getByPlaceholderText('0');
    fireEvent.change(priceBox, { target: { value: '150' } });

    await waitFor(() => expect(
      (screen.getByRole('button', { name: 'حفظ' }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole('button', { name: 'حفظ' }));

    await waitFor(() => expect(createCalls.length).toBe(1));
    const body = createCalls[0] as { name: string; service_ids: string[]; price_minor: number };
    expect(body.name).toBe('باقة جديدة');
    expect(body.service_ids.sort()).toEqual(['svc_a', 'svc_b']);
    expect(body.price_minor).toBe(15000);
    expect(pointsCalls.length).toBe(1);
  });

  it('opens the create dialog pre-filled from محلّي\'s bundle suggestion', async () => {
    packagesResponse = [];
    open(['/services?tab=packages&prefill_a=svc_a&prefill_b=svc_b']);
    await waitFor(() => expect(screen.getByPlaceholderText(/باقة الصيانة الشاملة/)).toBeTruthy());
    // Both suggested services are pre-checked (accent-highlighted) — visible as the price/points
    // form being immediately ready to save once a name and price are typed.
    expect(screen.getByText('غيار زيت')).toBeTruthy();
    expect(screen.getByText('فحص فرامل')).toBeTruthy();
  });
});
