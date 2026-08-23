/**
 * Phase 4 — the platform-wide "المال" and "النمو" numbers, computed on the client from actions
 * ALREADY declared and audited on the backend (`billing.platform_invoices`, `tenant.list`) —
 * no new backend work needed for either. Real cross-service aggregation (a service reporting its
 * own revenue share, insights' per-tenant metrics rolled up) is scoped separately; this file only
 * covers what two existing, already-catalog-visible actions can answer honestly today.
 *
 * WHY THIS ISN'T A NEW BACKEND ENDPOINT: `billing.platform_invoices` and `tenant.list` are both
 * user-tier, capability-gated (`platform.billing`/`platform.tenants`), audited write-ahead
 * routes — exactly the shape a new aggregator would have had to rebuild. Summing their own
 * output client-side is arithmetic, not a new privileged capability.
 */
import { req, type AdminSession } from './api';
import { allActions, type AdminCatalog } from './catalog';

interface InvoiceRow {
  total_minor: number;
  refunded_minor: number;
  created: string;
}

interface InvoicesPage {
  invoices: InvoiceRow[];
  next_cursor: string | null;
}

interface TenantRow {
  id: string;
  status: string;
  created_at: string;
}

/** ISO 8601, UTC midnight — the exact shape `billing.platform_invoices`'s own boot guard demands
 *  (verified in the route: a non-ISO bound fails loudly rather than silently matching nothing). */
function isoMonthStart(monthsAgo: number): string {
  const d = new Date();
  d.setUTCDate(1);
  d.setUTCHours(0, 0, 0, 0);
  d.setUTCMonth(d.getUTCMonth() - monthsAgo);
  return d.toISOString();
}

function findAction(catalog: AdminCatalog, id: string) {
  return allActions(catalog).find((a) => a.id === id);
}

/** Net revenue (halalas) for calendar month `monthsAgo` (0 = this month, 1 = last month) —
 *  `total_minor - refunded_minor` summed over every PAID invoice issued in the window, paged to
 *  the route's own cap (`platform_max_pages`) so this can never become an unbounded read. */
export async function monthRevenueHalalas(
  session: AdminSession, catalog: AdminCatalog, monthsAgo: number,
): Promise<{ ok: true; halalas: number } | { ok: false; reason: string }> {
  const action = findAction(catalog, 'billing.platform_invoices');
  if (!action) return { ok: false, reason: 'لا صلاحية لقراءة الفواتير عبر المنصّة.' };

  const since = isoMonthStart(monthsAgo);
  const until = isoMonthStart(monthsAgo - 1);
  let cursor: string | null = null;
  let halalas = 0;
  // A REAL PAGE CAP, MATCHING THE ROUTE'S OWN — the backend already stops after
  // `platform_max_pages`; mirroring a bound here means a runaway loop is impossible even if the
  // server-side cap ever changes shape, not just unlikely.
  for (let page = 0; page < 50; page++) {
    const qs = new URLSearchParams({ status: 'paid', since, until, limit: '1000' });
    if (cursor) qs.set('cursor', cursor);
    const body: InvoicesPage = await req(`${action.path}?${qs}`, 'GET', undefined, session.access_token);
    for (const inv of body.invoices) {
      halalas += (inv.total_minor || 0) - (inv.refunded_minor || 0);
    }
    if (!body.next_cursor) break;
    cursor = body.next_cursor;
  }
  return { ok: true, halalas };
}

export interface TenantCounts {
  total: number;
  active: number;
  newThisMonth: number;
}

/** `tenant.list` has no pagination (a flat, config-bounded `limit`) — one call, and the plan's
 *  own note applies here honestly: past that bound this undercounts rather than lies silently,
 *  and the fix is the same page-cursor upgrade the invoice route already has, not client work. */
export async function tenantCounts(
  session: AdminSession, catalog: AdminCatalog,
): Promise<{ ok: true; counts: TenantCounts } | { ok: false; reason: string }> {
  const action = findAction(catalog, 'tenant.list');
  if (!action) return { ok: false, reason: 'لا صلاحية لقراءة قائمة المستأجرين.' };

  const body: { tenants: TenantRow[] } = await req(action.path, 'GET', undefined, session.access_token);
  const monthStart = isoMonthStart(0);
  const counts = body.tenants.reduce<TenantCounts>((acc, t) => {
    acc.total += 1;
    if (t.status === 'active') acc.active += 1;
    if (t.created_at >= monthStart) acc.newThisMonth += 1;
    return acc;
  }, { total: 0, active: 0, newThisMonth: 0 });
  return { ok: true, counts };
}
