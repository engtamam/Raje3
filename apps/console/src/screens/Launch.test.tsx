/**
 * Launch.tsx — the `package_offer` goal's own picker (packages feature). The service_offer path
 * is pre-existing and unchanged; this covers only the new branch: the "catalogue" blank fills
 * with a PACKAGE instead of a service, and the request carries package_id/package_name instead
 * of service_id/service_name.
 */
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

const ACTIONS: Record<string, { id: string; label: string; method: string; path: string }> = {
  'campaigns.goals': { id: 'campaigns.goals', label: 'x', method: 'GET', path: '/goals' },
  'campaigns.preview': { id: 'campaigns.preview', label: 'x', method: 'POST', path: '/preview' },
  'campaigns.create': { id: 'campaigns.create', label: 'x', method: 'POST', path: '' },
  'operations.list_services': { id: 'operations.list_services', label: 'x', method: 'GET', path: '/services' },
  'operations.list_packages': { id: 'operations.list_packages', label: 'x', method: 'GET', path: '/packages' },
  'operations.list_branches': { id: 'operations.list_branches', label: 'x', method: 'GET', path: '/branches' },
};

const previewCalls: unknown[] = [];
const createCalls: unknown[] = [];

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ACTIONS[id] ?? null,
    call: async (_session: unknown, a: { id: string }, body?: unknown) => {
      if (a.id === 'campaigns.goals') {
        return {
          goals: [{ goal: 'package_offer', title: 'عرض على باقة', line: 'روّج لباقة',
                   icon: 'tag', available: true, offers: true,
                   blanks: ['amount', 'catalogue', 'date'] }],
        };
      }
      if (a.id === 'operations.list_services') return { services: [] };
      if (a.id === 'operations.list_packages') {
        return { packages: [{ id: 'pkg1', name: 'باقة الصيانة', active: true }] };
      }
      if (a.id === 'operations.list_branches') return { branches: [] };
      if (a.id === 'campaigns.preview') { previewCalls.push(body); return { message: 'معاينة', reaches: 10 }; }
      if (a.id === 'campaigns.create') { createCalls.push(body); return { campaign: { id: 'cmp1' } }; }
      return {};
    },
  };
});

const { Launch } = await import('./Launch');

const session = {} as never;
const catalog = { services: [], unreachable: [] } as never;

describe('package_offer', () => {
  it('shows a package select, not a service select, for the package_offer goal', async () => {
    render(<Launch session={session} catalog={catalog} onDone={() => {}} initialGoalId="package_offer" />);
    await waitFor(() => expect(screen.getByText('على أي باقة؟')).toBeTruthy());
    expect(screen.queryByText('على أي خدمة؟')).toBeNull();
    expect(screen.getByText('باقة الصيانة')).toBeTruthy();
  });

  it('preview sends package_id, never service_id', async () => {
    previewCalls.length = 0;
    render(<Launch session={session} catalog={catalog} onDone={() => {}} initialGoalId="package_offer" />);
    await waitFor(() => screen.getByText('على أي باقة؟'));

    // Only ONE <select> renders for this goal (no service select, no branch select — no branches
    // in this mock) — the package picker.
    const packageSelect = document.querySelector('select') as HTMLSelectElement;
    fireEvent.change(packageSelect, { target: { value: 'pkg1' } });

    const amountBox = document.querySelector('input[type="number"]') as HTMLInputElement;
    fireEvent.change(amountBox, { target: { value: '20' } });
    const dateBox = document.querySelector('input[type="date"]') as HTMLInputElement;
    fireEvent.change(dateBox, { target: { value: '2030-01-01' } });

    fireEvent.click(screen.getByRole('button', { name: 'اعرض ما سيصل' }));
    await waitFor(() => expect(previewCalls.length).toBe(1));
    const body = previewCalls[0] as { package_id: string; service_id: string };
    expect(body.package_id).toBe('pkg1');
    expect(body.service_id).toBe('');
  });
});
