/**
 * «ConnectByBranch» — the one screen that used to have no way to connect a second WhatsApp
 * number at all, no matter how a chain configured `shop_mode` (core/shop_mode.py). A `central`
 * shop — the overwhelming default — must see exactly the one card this screen has always shown;
 * a `per_branch` shop must see one card per branch, each reading and writing its OWN status.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

const calls: { id: string; params: unknown }[] = [];

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }, params: unknown = {}) => {
      calls.push({ id: a.id, params });
      if (a.id === 'operations.shop_mode') return (globalThis as any).__mode;
      if (a.id === 'operations.list_branches') return { branches: (globalThis as any).__branches ?? [] };
      if (a.id === 'whatsapp.connect_status') {
        return { state: '', message: 'لم تبدأ الربط بعد.', can_send: false };
      }
      return {};
    },
  };
});

const { ConnectByBranch } = await import('./Connect');

afterEach(() => { cleanup(); calls.length = 0; });

const catalog = { services: [], unreachable: [] } as never;
const session = {} as never;

describe('ConnectByBranch', () => {
  it('renders the single establishment-wide card for a shop still in central mode', async () => {
    (globalThis as any).__mode = { mode: 'central', available: true };
    render(<ConnectByBranch session={session} catalog={catalog} />);
    await screen.findByText('واتساب أعمالك');
    expect(screen.queryByText(/فرع/)).toBeNull();
  });

  it('renders one card per branch once the shop has moved to per_branch, each labelled by name', async () => {
    (globalThis as any).__mode = { mode: 'per_branch', available: true };
    (globalThis as any).__branches = [
      { id: 'brn_riy', name: 'فرع الرياض' },
      { id: 'brn_jed', name: 'فرع جدة' },
    ];
    render(<ConnectByBranch session={session} catalog={catalog} />);
    await screen.findByText('واتساب فرع الرياض');
    await screen.findByText('واتساب فرع جدة');
  });

  it('asks the status of each branch by its own branch_id, not the establishment as a whole', async () => {
    (globalThis as any).__mode = { mode: 'per_branch', available: true };
    (globalThis as any).__branches = [{ id: 'brn_riy', name: 'فرع الرياض' }];
    render(<ConnectByBranch session={session} catalog={catalog} />);
    await screen.findByText('واتساب فرع الرياض');
    const statusCalls = calls.filter((c) => c.id === 'whatsapp.connect_status');
    expect(statusCalls.some((c) => (c.params as { branch_id?: string })?.branch_id === 'brn_riy')).toBe(true);
  });

  it('tells him plainly when a per_branch shop has no branches yet to connect', async () => {
    (globalThis as any).__mode = { mode: 'per_branch', available: true };
    (globalThis as any).__branches = [];
    render(<ConnectByBranch session={session} catalog={catalog} />);
    await screen.findByText(/بلا فروع بعد/);
  });
});
