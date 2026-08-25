import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { AdminAnalytics } from './AdminAnalytics';
import type { AdminSession } from './api';

const SESSION: AdminSession = { access_token: 'tok-1' };

const CATALOG = {
  services: [
    { service: 'insights', actions: [
      { id: 'insights.platform_summary', label: 'x', method: 'GET' as const,
       path: '/api/v1/insights/platform/summary', capability: 'platform.insights' },
    ] },
    { service: 'affiliate-service', actions: [
      { id: 'affiliates.platform_stats', label: 'x', method: 'GET' as const,
       path: '/api/v1/admin/affiliates/stats', capability: 'platform.affiliates' },
      { id: 'affiliates.leaderboard', label: 'x', method: 'GET' as const,
       path: '/api/v1/admin/affiliates/leaderboard', capability: 'platform.affiliates' },
      { id: 'leads.geo_map', label: 'x', method: 'GET' as const,
       path: '/api/v1/admin/leads/geo', capability: 'platform.affiliates' },
    ] },
    { service: 'operations', actions: [
      { id: 'operations.branch_locations', label: 'x', method: 'GET' as const,
       path: '/api/v1/platform/branches/locations', capability: 'platform.operations' },
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

function mockAllFive(overrides: {
  insights?: Record<string, unknown>;
  stats?: Record<string, unknown>;
  leaderboard?: { leaderboard: Record<string, unknown>[] };
  leads?: { points: Record<string, unknown>[] };
  branches?: { branches: Record<string, unknown>[]; next_cursor: null };
} = {}) {
  const {
    insights = { computing: true, values: {}, tenants_with_snapshot: 0 },
    stats = { active_affiliates: 0, total_affiliates: 0, total_net_revenue_minor: 0, revenue_partial: false },
    leaderboard = { leaderboard: [] },
    leads = { points: [] },
    branches = { branches: [], next_cursor: null },
  } = overrides;
  reqMock = vi.fn((path: string) => {
    if (path.includes('platform/summary')) return Promise.resolve(insights);
    if (path.includes('affiliates/stats')) return Promise.resolve(stats);
    if (path.includes('leaderboard')) return Promise.resolve(leaderboard);
    if (path.includes('leads/geo')) return Promise.resolve(leads);
    if (path.includes('branches/locations')) return Promise.resolve(branches);
    return Promise.reject(new Error(`unexpected path ${path}`));
  });
}

describe('AdminAnalytics', () => {
  it('renders nothing when every source is unavailable', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue({ services: [], unreachable: [] });
    const { container } = render(<AdminAnalytics session={SESSION} />);
    await waitFor(() => expect(container.textContent).not.toContain('جارٍ التحميل'));
    expect(container.querySelector('h2')).toBeFalsy();
  });

  it('says the rollup has not computed yet, honestly', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    mockAllFive();
    render(<AdminAnalytics session={SESSION} />);
    await waitFor(() => expect(screen.getByText(/لم يُحسب بعد/)).toBeTruthy());
  });

  it('renders real retention/at-risk KPIs once the rollup has a row', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    mockAllFive({
      insights: {
        computing: false,
        values: {
          return_rate: 0.55, at_risk_tenant_count: 4,
          peak_map: { grid: { '0:9': 3 }, busiest: '0:9' },
          retention_series: {
            learning: false,
            points: [
              { at: 1, value: 0.3 }, { at: 2, value: 0.4 }, { at: 3, value: 0.5 },
              { at: 4, value: 0.5 }, { at: 5, value: 0.6 }, { at: 6, value: 0.6 },
            ],
          },
        },
        tenants_with_snapshot: 20,
      },
    });
    render(<AdminAnalytics session={SESSION} />);
    await waitFor(() => expect(screen.getByText('55٪')).toBeTruthy());
    expect(screen.getByText('4')).toBeTruthy();
    expect(screen.getByText(/عبر 20 محلاً/)).toBeTruthy();
  });

  it('renders affiliate stats and the leaderboard', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    mockAllFive({
      stats: { active_affiliates: 3, total_affiliates: 5, total_net_revenue_minor: 500000, revenue_partial: false },
      leaderboard: { leaderboard: [
        { affiliate_id: 'a1', name: 'سارة', active_shops: 4, retention_rate: 0.75, refund_rate: 0.05, total_referrals: 10, total_commissions: 8 },
      ] },
    });
    render(<AdminAnalytics session={SESSION} />);
    await waitFor(() => expect(screen.getByText('3')).toBeTruthy());
    expect(screen.getByText(/سارة/)).toBeTruthy();
    expect(screen.getByText(/10 إحالة/)).toBeTruthy();
  });

  it('renders leads and branch geo maps when points exist', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    mockAllFive({
      leads: { points: [{ id: 'l1', lat: 24.7, lng: 46.6, city: 'الرياض', sector_code: 'salon' }] },
      branches: { branches: [{ id: 'b1', name: 'فرع الروضة', lat: 24.71, lng: 46.68, city: 'الرياض' }], next_cursor: null },
    });
    render(<AdminAnalytics session={SESSION} />);
    await waitFor(() => expect(screen.getByText('خريطة العملاء المحتملين')).toBeTruthy());
    expect(screen.getByText('خريطة المحلات الفعلية')).toBeTruthy();
  });
});
