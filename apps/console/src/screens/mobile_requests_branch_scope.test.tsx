/**
 * «خدمات متنقلة» — branch-scoping UX (step 5 of the branch-domains project).
 *
 * THE ASSIGN DROPDOWN ALREADY LISTS ONLY WHAT THE SERVER SENDS. `operatorsAction` reads
 * `operations.list_operators` (services/operations/app/api/v1/staff.py::list_operators), which
 * already narrows its own answer to the caller's branch scope server-side
 * (`SCOPE.visible([o.public() for o in rows], scope)`, confirmed in this screen's own step-3
 * audit) — so this test proves the screen renders EXACTLY the operators the mocked call returns,
 * with no separate client-side broadening or re-filtering of its own, rather than re-testing the
 * server's own scoping logic (already covered in services/operations's own test suite).
 *
 * A 403 SHOWS A REAL SENTENCE, NEVER A BLANK FAILURE. `services/operations/app/api/errors.py`
 * strips every `HTTPException` detail on the way out (CWE-209), so the server's own
 * `OUTSIDE_YOUR_BRANCH` string never reaches the console — these tests prove the screen names the
 * one real reason itself instead of showing nothing, or the bare `POST ... → 403` `call()` would
 * otherwise fall back to.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render as rtlRender, screen, waitFor } from '@testing-library/react';
import type { ReactElement } from 'react';
import { OperatorI18nProvider } from '../operator-i18n';

const SESSION_FOR_I18N = { tenant: 't1', operator: '', operatorName: '', token: 'tok' } as never;
function render(ui: ReactElement) {
  return rtlRender(<OperatorI18nProvider session={SESSION_FOR_I18N}>{ui}</OperatorI18nProvider>);
}

const REQUEST = {
  id: 'mreq_1', tenant: 't1', phone: '+966500000001', customer_name: 'أحمد',
  service_ids: [], requested_time: 1_900_000_000, lat: 24.7, lng: 46.6,
  status: 'pending', created: 1_899_990_000, decided_at: 0, decided_by: '',
  reject_reason: '', visit_id: '', note: '', maps_url: 'https://maps.google.com/?q=24.7,46.6',
  assigned_to: '',
};

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string; method?: string }, params: unknown = {}) => {
      if (a.id === 'operations.mobile_requests_list') return { requests: [{ ...REQUEST }] };
      if (a.id === 'operations.manage_services') return { services: [] };
      if (a.id === 'operations.list_operators') {
        // THE SERVER'S OWN NARROWED ANSWER — a manager scoped to Jeddah would only ever receive
        // Jeddah's own operators here; this mock simply returns whatever the test set, and the
        // screen's own job is to offer exactly this list, nothing more.
        return { operators: (globalThis as any).__operators ?? [] };
      }
      if (a.id === 'operations.mobile_request_assign') {
        if ((globalThis as any).__assignFails) {
          const err = new Error('FORBIDDEN') as Error & { status?: number };
          err.status = 403;
          throw err;
        }
        return { ...REQUEST, assigned_to: (params as { operator_id: string }).operator_id };
      }
      if (a.id === 'operations.mobile_request_accept') {
        if ((globalThis as any).__acceptFails) {
          const err = new Error('FORBIDDEN') as Error & { status?: number };
          err.status = 403;
          throw err;
        }
        return { ...REQUEST, status: 'accepted' };
      }
      if (a.id === 'operations.mobile_request_risk') return { considered: 0, no_shows: 0, risky: false, threshold_percent: 40 };
      return {};
    },
  };
});

const { MobileRequestsScreen } = await import('./MobileRequests');

afterEach(() => {
  cleanup();
  (globalThis as any).__operators = undefined;
  (globalThis as any).__assignFails = undefined;
  (globalThis as any).__acceptFails = undefined;
});

const catalog = { services: [], unreachable: [] } as never;
const session = {} as never;

describe('MobileRequests — branch scoping', () => {
  it('offers only the operators the server actually returned in the assign dropdown', async () => {
    (globalThis as any).__operators = [
      { id: 'op_jeddah', name: 'محمد', active: true },
      // Riyadh's own operator is deliberately NOT in this list — the server (list_operators)
      // already narrowed it away for a Jeddah-scoped manager. This screen must not add it back.
    ];
    render(<MobileRequestsScreen session={session} catalog={catalog} />);
    const select = await screen.findByTestId(`mobile-request-assign-${REQUEST.id}`);
    const options = Array.from(select.querySelectorAll('option')).map((o) => o.textContent);
    expect(options).toContain('محمد');
    expect(options.some((o) => o?.includes('Riyadh') || o?.includes('رياض'))).toBe(false);
    expect(options.length).toBe(2); // "بلا إسناد" + the one operator the server sent
  });

  it('shows a real sentence, not a blank failure, when assigning is refused as outside the branch', async () => {
    (globalThis as any).__operators = [{ id: 'op_other_branch', name: 'خالد', active: true }];
    (globalThis as any).__assignFails = true;
    render(<MobileRequestsScreen session={session} catalog={catalog} />);
    const select = await screen.findByTestId(`mobile-request-assign-${REQUEST.id}`);
    fireEvent.change(select, { target: { value: 'op_other_branch' } });
    await screen.findByText(/خارج نطاق فرعك/);
  });

  it('shows a real sentence on accept refused as outside the branch too', async () => {
    (globalThis as any).__acceptFails = true;
    render(<MobileRequestsScreen session={session} catalog={catalog} />);
    const button = await screen.findByTestId(`mobile-request-accept-${REQUEST.id}`);
    fireEvent.click(button);
    await screen.findByText(/خارج نطاق فرعك/);
  });

  it('clears a stale action error once a new attempt is made', async () => {
    (globalThis as any).__acceptFails = true;
    render(<MobileRequestsScreen session={session} catalog={catalog} />);
    const button = await screen.findByTestId(`mobile-request-accept-${REQUEST.id}`);
    fireEvent.click(button);
    await screen.findByText(/خارج نطاق فرعك/);
    (globalThis as any).__acceptFails = false;
    fireEvent.click(button);
    await waitFor(() => expect(screen.queryByText(/خارج نطاق فرعك/)).toBeNull());
  });
});
