/**
 * «حسابي» — the identity line every screenshot of a field operator's own account page was
 * missing: his name, and where he works, shown without depending on any tab
 * («منشأتي» is gated on capabilities a field operator never holds).
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => {
      // A FIELD OPERATOR'S OWN CATALOGUE — only the bookings-side id resolves, never the
      // owner/manager one, same shape staff.py's `_READ_BRANCHES` actually produces for him.
      if (id === 'operations.list_branches') return undefined;
      return { id, label: id, method: 'GET', path: `/${id}` };
    },
    call: async (_s: unknown, a: { id: string }) => {
      if (a.id === 'operations.list_branches_for_bookings') {
        return { branches: [{ id: 'brn-main', name: 'الفرع الرئيسي' }] };
      }
      if (a.id === 'billing.my_subscriptions') return { subscriptions: [] };
      return {};
    },
  };
});

const { AccountScreen } = await import('./Account');

afterEach(() => { cleanup(); });

const catalog = { services: [], unreachable: [] } as never;

describe('«حسابي» — who he is, and where he works', () => {
  it('shows his own name, always, regardless of which tabs his role can reach', async () => {
    const session = { operatorName: 'سالم العتيبي', operator: 'op_1' } as never;
    render(<AccountScreen session={session} catalog={catalog} />);
    await screen.findByText('سالم العتيبي');
  });

  it('falls back to the bare operator id when no display name was set', async () => {
    const session = { operatorName: '', operator: 'op_2' } as never;
    render(<AccountScreen session={session} catalog={catalog} />);
    await screen.findByText('op_2');
  });

  it('resolves his own branch via the bookings-side id a field operator actually holds', async () => {
    const session = { operatorName: 'سالم العتيبي', operator: 'op_1' } as never;
    render(<AccountScreen session={session} catalog={catalog} />);
    await screen.findByText('الفرع الرئيسي');
  });
});
