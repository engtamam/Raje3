/**
 * The customer-profile half of the repeated-issue pattern: a step this customer has flagged on
 * MORE THAN ONE visit gets a callout, and each visit row shows the steps flagged on it. The
 * server-side resolution/counting is covered on the backend side
 * (services/operations/tests/unit/test_operations.py).
 */
import { describe, expect, it, vi } from 'vitest';
import { render as rtlRender, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { ReactElement } from 'react';
import { OperatorI18nProvider } from '../operator-i18n';
import { CustomerScreen } from './Customer';

const SESSION = { tenant: 't1', operator: '', operatorName: '', token: 'tok' } as never;
const catalog = { services: [], unreachable: [] } as never;

const RECORD = {
  customer: { id: 'cus_1', phone: '+966500000001', name: 'ريم الحربي', visits: 2 },
  visits: [
    {
      id: 'vis1', services: 'صيانة دورية', occurred_at: Math.floor(Date.now() / 1000),
      rating_issue_steps: [{ id: 'step_a', text: 'اربط الصمولة بعزم صحيح', severity: 'critical' as const }],
    },
    {
      id: 'vis2', services: 'صيانة دورية', occurred_at: Math.floor(Date.now() / 1000) - 86400 * 30,
      rating_issue_steps: [{ id: 'step_a', text: 'اربط الصمولة بعزم صحيح', severity: 'critical' as const }],
    },
  ],
  repeated_issues: [{ id: 'step_a', text: 'اربط الصمولة بعزم صحيح', severity: 'critical' as const, count: 2 }],
};

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }) => {
      if (a.id === 'operations.customer') return RECORD;
      return {};
    },
  };
});

function render(ui: ReactElement) {
  return rtlRender(
    <OperatorI18nProvider session={SESSION}>
      <MemoryRouter initialEntries={['/customers/cus_1']}>
        <Routes>
          <Route path="/customers/:id" element={ui} />
        </Routes>
      </MemoryRouter>
    </OperatorI18nProvider>,
  );
}

describe('صفحة العميل — نمط متكرر', () => {
  it('shows the repeated-issue callout when a step was flagged on more than one visit', async () => {
    render(<CustomerScreen session={SESSION} catalog={catalog} />);
    await waitFor(() => expect(screen.getByText('نمط متكرر عند هذا العميل')).toBeTruthy());
    expect(screen.getByText('2×')).toBeTruthy();
  });

  it('shows the flagged step on each visit row that named it', async () => {
    render(<CustomerScreen session={SESSION} catalog={catalog} />);
    await waitFor(() => expect(
      screen.getAllByText('اربط الصمولة بعزم صحيح').length,
    ).toBeGreaterThan(0));
  });
});
