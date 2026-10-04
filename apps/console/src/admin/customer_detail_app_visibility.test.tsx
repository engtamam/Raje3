/**
 * «التطبيقات والفوترة» tab's new "تطبيقات مخفية عن الجميع" panel (core/app_visibility.py) — lists
 * only the platform's currently UNLISTED plans, reads/writes this one tenant's own overrides, and
 * hides entirely when the caller holds no `operations.app_visibility_*` capability.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { AdminAction, AdminCatalog } from './catalog';
import type { Tenant } from './CustomerList';

const calls: { path: string; method: string; body?: unknown }[] = [];
let responder: (path: string, method: string, body?: unknown) => unknown = () => ({});

vi.mock('./api', async (importOriginal) => {
  const real = await importOriginal<typeof import('./api')>();
  return {
    ...real,
    req: vi.fn(async (path: string, method: string, body?: unknown) => {
      calls.push({ path, method, body });
      const out = responder(path, method, body);
      if (out instanceof Error) throw out;
      return out;
    }),
  };
});

const { CustomerDetail } = await import('./CustomerDetail');

const session = { access_token: 'tok' } as never;
const tenant: Tenant = {
  id: 't1', name: 'محل تجريبي', slug: 't1-slug', status: 'active',
  created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
} as never;

function action(id: string, method: AdminAction['method'], path: string): AdminAction {
  return { id, label: id, method, path, capability: 'platform.operations' };
}

const PLAN_LISTED = { id: 'plan_visit', name: 'تسجيل زيارة', listed: true,
  limits: { 'feature.visit': { kind: 'boolean', limit: 1 } } };
const PLAN_UNLISTED = { id: 'plan_partner_loyalty', name: 'ولاء الشركاء', listed: false,
  limits: { 'feature.partner_loyalty': { kind: 'boolean', limit: 1 } } };
const PLAN_UNLISTED_NO_KEY = { id: 'plan_capacity', name: 'مقاعد إضافية', listed: false,
  limits: { 'plan.standalone': { kind: 'boolean', limit: 1 } } };

const ALL_ACTIONS = [
  action('billing.list_plans', 'GET', '/api/v1/billing/plans'),
  action('billing.platform_subscriptions', 'GET', '/api/v1/platform/subscriptions'),
  action('billing.platform_invoices', 'GET', '/api/v1/platform/invoices'),
  action('operations.app_visibility_list', 'GET', '/api/v1/platform/app-visibility'),
  action('operations.app_visibility_set', 'PUT', '/api/v1/platform/app-visibility'),
];

function catalogWith(ids: string[]): AdminCatalog {
  return { services: [{ service: 'x', actions: ALL_ACTIONS.filter((a) => ids.includes(a.id)) }],
          unreachable: [] };
}

const FULL_CATALOG = catalogWith(ALL_ACTIONS.map((a) => a.id));

function defaultResponder(path: string) {
  if (path.includes('/billing/plans')) return { plans: [PLAN_LISTED, PLAN_UNLISTED, PLAN_UNLISTED_NO_KEY] };
  if (path.includes('/app-visibility')) return { tenant: 't1', overrides: [] };
  if (path.includes('/platform/subscriptions')) return { subscriptions: [] };
  if (path.includes('/platform/invoices')) return { invoices: [] };
  return {};
}

function openBillingTab(catalog: AdminCatalog) {
  render(<CustomerDetail session={session} tenant={tenant} subscription={null}
                        planNames={new Map()} catalog={catalog} onClose={() => {}} />);
  fireEvent.click(screen.getByText('التطبيقات والفوترة'));
}

afterEach(() => { cleanup(); calls.length = 0; responder = defaultResponder; });
responder = defaultResponder;

describe('app visibility panel', () => {
  it('shows only unlisted plans that carry a real feature key', async () => {
    openBillingTab(FULL_CATALOG);
    await screen.findByText('ولاء الشركاء');
    expect(screen.queryByText('مقاعد إضافية')).toBeNull();
  });

  it('reflects an already-granted override as checked', async () => {
    responder = (path) => {
      if (path.includes('/app-visibility')) {
        return { tenant: 't1', overrides: [{ feature_key: 'feature.partner_loyalty', visible: true }] };
      }
      return defaultResponder(path);
    };
    openBillingTab(FULL_CATALOG);
    const toggle = await screen.findByRole('switch', { name: 'أظهر ولاء الشركاء لهذا المحل' });
    expect(toggle.getAttribute('aria-checked')).toBe('true');
  });

  it('toggling on sends the right PUT body and reloads', async () => {
    openBillingTab(FULL_CATALOG);
    const toggle = await screen.findByRole('switch', { name: 'أظهر ولاء الشركاء لهذا المحل' });
    expect(toggle.getAttribute('aria-checked')).toBe('false');
    fireEvent.click(toggle);
    await waitFor(() => {
      const putCall = calls.find((c) => c.method === 'PUT');
      expect(putCall).toBeTruthy();
      expect(putCall!.body).toEqual({ tenant: 't1', feature_key: 'feature.partner_loyalty', visible: true });
    });
  });

  it('toggling off sends visible: false', async () => {
    responder = (path) => {
      if (path.includes('/app-visibility')) {
        return { tenant: 't1', overrides: [{ feature_key: 'feature.partner_loyalty', visible: true }] };
      }
      return defaultResponder(path);
    };
    openBillingTab(FULL_CATALOG);
    const toggle = await screen.findByRole('switch', { name: 'أظهر ولاء الشركاء لهذا المحل' });
    fireEvent.click(toggle);
    await waitFor(() => {
      const putCall = calls.find((c) => c.method === 'PUT');
      expect(putCall!.body).toEqual({ tenant: 't1', feature_key: 'feature.partner_loyalty', visible: false });
    });
  });

  it('shows a refusal message and never crashes on a failed save', async () => {
    responder = (path, method) => {
      if (method === 'PUT') return new Error('تعذّر الحفظ');
      return defaultResponder(path);
    };
    openBillingTab(FULL_CATALOG);
    const toggle = await screen.findByRole('switch', { name: 'أظهر ولاء الشركاء لهذا المحل' });
    fireEvent.click(toggle);
    await screen.findByRole('alert');
  });

  it('is entirely absent with no operations.app_visibility_* capability', async () => {
    openBillingTab(catalogWith(['billing.list_plans', 'billing.platform_subscriptions',
      'billing.platform_invoices']));
    // give the tab a moment to settle, then assert the panel never appears
    await screen.findByText('التطبيقات المفعّلة');
    expect(screen.queryByText('تطبيقات مخفية عن الجميع', { exact: false })).toBeNull();
  });

  it('is absent when the platform sells no unlisted plans at all', async () => {
    responder = (path) => {
      if (path.includes('/billing/plans')) return { plans: [PLAN_LISTED] };
      return defaultResponder(path);
    };
    openBillingTab(FULL_CATALOG);
    await screen.findByText('التطبيقات المفعّلة');
    expect(screen.queryByText('تطبيقات مخفية عن الجميع', { exact: false })).toBeNull();
  });
});
