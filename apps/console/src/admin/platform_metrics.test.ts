import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  activeTeamCount, affiliateLeaderboard, affiliateStats, backupHealth, branchGeoPoints,
  leadsGeoPoints, monthRevenueHalalas, openTicketsCount, pendingAffiliateApplications,
  platformInsights, suspiciousLogins, tenantCounts, unreachableServices,
} from './platformMetrics';
import type { AdminCatalog } from './catalog';
import type { AdminSession } from './api';

const SESSION: AdminSession = { access_token: 'tok-1' };

const EMPTY_CATALOG: AdminCatalog = { services: [], unreachable: [] };

const AUDIT_CATALOG: AdminCatalog = {
  services: [{ service: 'audit-service', actions: [
    { id: 'audit.query', label: 'x', method: 'GET', path: '/api/v1/audit', capability: 'platform.audit' },
  ] }],
  unreachable: ['notification-service'],
};

// REAL SHAPE — grouped by service, per admin_catalog.py::build_catalog. Two different services
// on purpose, matching production: billing.platform_invoices comes from billing-service,
// tenant.list from tenant-service.
const CATALOG: AdminCatalog = {
  services: [
    { service: 'billing-service', actions: [
      { id: 'billing.platform_invoices', label: 'x', method: 'GET',
       path: '/api/v1/billing/admin/invoices', capability: 'platform.billing' },
    ] },
    { service: 'tenant-service', actions: [
      { id: 'tenant.list', label: 'x', method: 'GET', path: '/api/v1/tenants', capability: 'platform.tenants' },
    ] },
  ],
  unreachable: [],
};

let reqMock: ReturnType<typeof vi.fn>;

vi.mock('./api', async (importOriginal) => {
  const real = await importOriginal<typeof import('./api')>();
  return { ...real, req: (...args: unknown[]) => reqMock(...args) };
});

afterEach(() => vi.clearAllMocks());

describe('monthRevenueHalalas', () => {
  it('sums total_minor minus refunded_minor across every paid invoice', async () => {
    reqMock = vi.fn().mockResolvedValue({
      invoices: [
        { total_minor: 10000, refunded_minor: 0, created: '2026-08-05T00:00:00Z' },
        { total_minor: 5000, refunded_minor: 1000, created: '2026-08-10T00:00:00Z' },
      ],
      next_cursor: null,
    });
    const out = await monthRevenueHalalas(SESSION, CATALOG, 0);
    expect(out).toEqual({ ok: true, halalas: 14000 });
  });

  it('pages through cursors until next_cursor is null', async () => {
    reqMock = vi.fn()
      .mockResolvedValueOnce({ invoices: [{ total_minor: 100, refunded_minor: 0, created: 'x' }], next_cursor: 'c1' })
      .mockResolvedValueOnce({ invoices: [{ total_minor: 200, refunded_minor: 0, created: 'x' }], next_cursor: null });
    const out = await monthRevenueHalalas(SESSION, CATALOG, 0);
    expect(out).toEqual({ ok: true, halalas: 300 });
    expect(reqMock).toHaveBeenCalledTimes(2);
  });

  it('refuses honestly when the caller has no billing action in their catalog', async () => {
    reqMock = vi.fn();
    const out = await monthRevenueHalalas(SESSION, EMPTY_CATALOG, 0);
    expect(out.ok).toBe(false);
    expect(reqMock).not.toHaveBeenCalled();
  });
});

describe('tenantCounts', () => {
  it('counts total, active, and created-this-month from one flat call', async () => {
    const thisMonthStart = new Date();
    thisMonthStart.setUTCDate(1);
    thisMonthStart.setUTCHours(0, 0, 0, 0);
    const inThisMonth = new Date(thisMonthStart.getTime() + 86400000).toISOString();
    const lastMonth = new Date(thisMonthStart.getTime() - 86400000).toISOString();

    reqMock = vi.fn().mockResolvedValue({
      tenants: [
        { id: 't1', status: 'active', created_at: inThisMonth },
        { id: 't2', status: 'active', created_at: lastMonth },
        { id: 't3', status: 'suspended', created_at: lastMonth },
      ],
    });
    const out = await tenantCounts(SESSION, CATALOG);
    expect(out).toEqual({ ok: true, counts: { total: 3, active: 2, newThisMonth: 1 } });
  });

  it('refuses honestly when the caller has no tenant action in their catalog', async () => {
    reqMock = vi.fn();
    const out = await tenantCounts(SESSION, EMPTY_CATALOG);
    expect(out.ok).toBe(false);
    expect(reqMock).not.toHaveBeenCalled();
  });
});

describe('unreachableServices', () => {
  it('reads straight off the catalog\'s own unreachable list — no request at all', () => {
    expect(unreachableServices(AUDIT_CATALOG)).toEqual(['notification-service']);
    expect(unreachableServices(EMPTY_CATALOG)).toEqual([]);
  });
});

describe('suspiciousLogins', () => {
  it('groups auth.login_failed events by actor and keeps only bursts at or above the threshold', async () => {
    reqMock = vi.fn().mockResolvedValue({
      events: [
        { id: '1', ts: 'x', actor: 'atk@evil.com', tenant: '' },
        { id: '2', ts: 'x', actor: 'atk@evil.com', tenant: '' },
        { id: '3', ts: 'x', actor: 'atk@evil.com', tenant: '' },
        { id: '4', ts: 'x', actor: 'atk@evil.com', tenant: '' },
        { id: '5', ts: 'x', actor: 'atk@evil.com', tenant: '' },
        { id: '6', ts: 'x', actor: 'typo@user.com', tenant: '' },
      ],
    });
    const out = await suspiciousLogins(SESSION, AUDIT_CATALOG, 24, 5);
    expect(out).toEqual({ ok: true, actors: [{ actor: 'atk@evil.com', count: 5 }] });
  });

  it('refuses honestly when the caller has no audit action in their catalog', async () => {
    reqMock = vi.fn();
    const out = await suspiciousLogins(SESSION, EMPTY_CATALOG);
    expect(out.ok).toBe(false);
    expect(reqMock).not.toHaveBeenCalled();
  });
});

const AFFILIATES_CATALOG: AdminCatalog = {
  services: [{ service: 'affiliate-service', actions: [
    { id: 'affiliates.list_pending', label: 'x', method: 'GET', path: '/api/v1/admin/affiliates', capability: 'platform.affiliates' },
  ] }],
  unreachable: [],
};

describe('pendingAffiliateApplications', () => {
  it('counts the applications array', async () => {
    reqMock = vi.fn().mockResolvedValue({ applications: [{ id: 'a1' }, { id: 'a2' }] });
    const out = await pendingAffiliateApplications(SESSION, AFFILIATES_CATALOG);
    expect(out).toEqual({ ok: true, count: 2 });
  });

  it('refuses honestly with no capability', async () => {
    reqMock = vi.fn();
    const out = await pendingAffiliateApplications(SESSION, EMPTY_CATALOG);
    expect(out.ok).toBe(false);
    expect(reqMock).not.toHaveBeenCalled();
  });
});

const TICKETS_CATALOG: AdminCatalog = {
  services: [{ service: 'ticket-service', actions: [
    { id: 'tickets.inbox', label: 'x', method: 'GET', path: '/api/v1/operator/tickets', capability: 'tickets.manage' },
  ] }],
  unreachable: [],
};

describe('openTicketsCount', () => {
  it('counts one page and flags atLeast when a cursor came back', async () => {
    reqMock = vi.fn().mockResolvedValue({
      tickets: Array.from({ length: 200 }, (_, i) => ({ status: 'open', id: String(i) })),
      cursor: 'more',
    });
    const out = await openTicketsCount(SESSION, TICKETS_CATALOG);
    expect(out).toEqual({ ok: true, count: 200, atLeast: true });
  });

  it('a null cursor means the count is exact', async () => {
    reqMock = vi.fn().mockResolvedValue({ tickets: [{ status: 'open' }], cursor: null });
    const out = await openTicketsCount(SESSION, TICKETS_CATALOG);
    expect(out).toEqual({ ok: true, count: 1, atLeast: false });
  });

  it('refuses honestly with no capability', async () => {
    reqMock = vi.fn();
    const out = await openTicketsCount(SESSION, EMPTY_CATALOG);
    expect(out.ok).toBe(false);
    expect(reqMock).not.toHaveBeenCalled();
  });
});

const BACKUP_CATALOG: AdminCatalog = {
  services: [{ service: 'backup-service', actions: [
    { id: 'backup.health', label: 'x', method: 'GET', path: '/api/v1/operator/backup/health', capability: 'platform.restore' },
  ] }],
  unreachable: [],
};

const IDENTITY_CATALOG: AdminCatalog = {
  services: [{ service: 'identity-service', actions: [
    { id: 'identity.list_members', label: 'x', method: 'GET', path: '/api/v1/tenancy/members', capability: 'members:read' },
  ] }],
  unreachable: [],
};

describe('activeTeamCount', () => {
  it('counts only active members, ignoring suspended ones', async () => {
    reqMock = vi.fn().mockResolvedValue({
      tenant: '_platform', next: null,
      members: [{ status: 'active' }, { status: 'active' }, { status: 'suspended' }],
    });
    const out = await activeTeamCount(SESSION, IDENTITY_CATALOG);
    expect(out).toEqual({ ok: true, count: 2, atLeast: false });
  });

  it('flags atLeast when a next cursor came back', async () => {
    reqMock = vi.fn().mockResolvedValue({ tenant: '_platform', next: 'cursor2', members: [{ status: 'active' }] });
    const out = await activeTeamCount(SESSION, IDENTITY_CATALOG);
    expect(out).toEqual({ ok: true, count: 1, atLeast: true });
  });

  it('refuses honestly with no capability', async () => {
    reqMock = vi.fn();
    const out = await activeTeamCount(SESSION, EMPTY_CATALOG);
    expect(out.ok).toBe(false);
    expect(reqMock).not.toHaveBeenCalled();
  });
});

describe('backupHealth', () => {
  it('passes the peer\'s own summary/alerts through untouched', async () => {
    const body = {
      status: 'critical' as const,
      alerts: [{ service: 'billing-service', severity: 'critical' as const, reason: 'missed run' }],
      summary: { total: 5, healthy: 4, degraded: 0, critical: 1 },
    };
    reqMock = vi.fn().mockResolvedValue(body);
    const out = await backupHealth(SESSION, BACKUP_CATALOG);
    expect(out).toEqual({ ok: true, body });
  });

  it('refuses honestly with no capability', async () => {
    reqMock = vi.fn();
    const out = await backupHealth(SESSION, EMPTY_CATALOG);
    expect(out.ok).toBe(false);
    expect(reqMock).not.toHaveBeenCalled();
  });
});

const INSIGHTS_CATALOG: AdminCatalog = {
  services: [{ service: 'insights', actions: [
    { id: 'insights.platform_summary', label: 'x', method: 'GET', path: '/api/v1/insights/platform/summary', capability: 'platform.insights' },
  ] }],
  unreachable: [],
};

describe('platformInsights', () => {
  it('reports computing:true honestly before the first rollup pass', async () => {
    reqMock = vi.fn().mockResolvedValue({ computing: true, values: {}, tenants_with_snapshot: 0 });
    const out = await platformInsights(SESSION, INSIGHTS_CATALOG);
    expect(out).toEqual({ ok: true, computing: true });
  });

  it('reshapes the peak_map grid into day/hour rows and drops a learning retention series', async () => {
    reqMock = vi.fn().mockResolvedValue({
      computing: false,
      values: {
        return_rate: 0.42,
        peak_map: { grid: { '0:9': 5 }, busiest: '0:9' },
        at_risk_tenant_count: 3,
        retention_series: { learning: true, points: [] },
      },
      tenants_with_snapshot: 12,
    });
    const out = await platformInsights(SESSION, INSIGHTS_CATALOG);
    expect(out.ok).toBe(true);
    if (out.ok && !out.computing) {
      expect(out.data.returnRate).toBe(0.42);
      expect(out.data.peakGrid).toEqual([{ day: 'الأحد', hour: '9:00', value: 5 }]);
      expect(out.data.atRiskTenantCount).toBe(3);
      expect(out.data.retentionSeries).toBeNull();
      expect(out.data.tenantsWithSnapshot).toBe(12);
    }
  });

  it('refuses honestly with no capability', async () => {
    reqMock = vi.fn();
    const out = await platformInsights(SESSION, EMPTY_CATALOG);
    expect(out.ok).toBe(false);
    expect(reqMock).not.toHaveBeenCalled();
  });
});

const AFFILIATES_PLATFORM_CATALOG: AdminCatalog = {
  services: [{ service: 'affiliate-service', actions: [
    { id: 'affiliates.platform_stats', label: 'x', method: 'GET', path: '/api/v1/admin/affiliates/stats', capability: 'platform.affiliates' },
    { id: 'affiliates.leaderboard', label: 'x', method: 'GET', path: '/api/v1/admin/affiliates/leaderboard', capability: 'platform.affiliates' },
    { id: 'leads.geo_map', label: 'x', method: 'GET', path: '/api/v1/admin/leads/geo', capability: 'platform.affiliates' },
  ] }],
  unreachable: [],
};

describe('affiliateStats', () => {
  it('maps the snake_case body to camelCase', async () => {
    reqMock = vi.fn().mockResolvedValue({
      active_affiliates: 4, total_affiliates: 6, total_net_revenue_minor: 900000, revenue_partial: false,
    });
    const out = await affiliateStats(SESSION, AFFILIATES_PLATFORM_CATALOG);
    expect(out).toEqual({ ok: true, data: {
      activeAffiliates: 4, totalAffiliates: 6, totalNetRevenueMinor: 900000, revenuePartial: false,
    } });
  });

  it('refuses honestly with no capability', async () => {
    reqMock = vi.fn();
    const out = await affiliateStats(SESSION, EMPTY_CATALOG);
    expect(out.ok).toBe(false);
  });
});

describe('affiliateLeaderboard', () => {
  it('maps rows and passes the limit through', async () => {
    reqMock = vi.fn().mockResolvedValue({
      leaderboard: [{ affiliate_id: 'a1', name: 'سارة', active_shops: 5, retention_rate: 0.8,
                      refund_rate: 0.1, total_referrals: 7, total_commissions: 6 }],
    });
    const out = await affiliateLeaderboard(SESSION, AFFILIATES_PLATFORM_CATALOG, 5);
    expect(out).toEqual({ ok: true, rows: [{
      affiliateId: 'a1', name: 'سارة', activeShops: 5, retentionRate: 0.8,
      totalReferrals: 7, totalCommissions: 6,
    }] });
    expect(reqMock).toHaveBeenCalledWith(
      '/api/v1/admin/affiliates/leaderboard?limit=5', 'GET', undefined, 'tok-1',
    );
  });
});

describe('leadsGeoPoints', () => {
  it('maps city to label and sector_code to group', async () => {
    reqMock = vi.fn().mockResolvedValue({
      points: [{ id: 'l1', lat: 24.7, lng: 46.6, city: 'الرياض', sector_code: 'salon' }],
    });
    const out = await leadsGeoPoints(SESSION, AFFILIATES_PLATFORM_CATALOG);
    expect(out).toEqual({ ok: true, points: [
      { id: 'l1', lat: 24.7, lng: 46.6, label: 'الرياض', group: 'salon' },
    ] });
  });
});

const OPERATIONS_CATALOG: AdminCatalog = {
  services: [{ service: 'operations', actions: [
    { id: 'operations.branch_locations', label: 'x', method: 'GET', path: '/api/v1/platform/branches/locations', capability: 'platform.operations' },
  ] }],
  unreachable: [],
};

describe('branchGeoPoints', () => {
  it('maps branch name to label and city to group', async () => {
    reqMock = vi.fn().mockResolvedValue({
      branches: [{ id: 'brn-1', name: 'فرع الروضة', lat: 24.71, lng: 46.68, city: 'الرياض' }],
      next_cursor: null,
    });
    const out = await branchGeoPoints(SESSION, OPERATIONS_CATALOG);
    expect(out).toEqual({ ok: true, points: [
      { id: 'brn-1', lat: 24.71, lng: 46.68, label: 'فرع الروضة', group: 'الرياض' },
    ] });
  });

  it('refuses honestly with no capability', async () => {
    reqMock = vi.fn();
    const out = await branchGeoPoints(SESSION, EMPTY_CATALOG);
    expect(out.ok).toBe(false);
  });
});
