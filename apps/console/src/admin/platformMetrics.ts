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

/** Which services answered the catalog build and which didn't (11.9) — free, no new backend: the
 *  gateway's own `admin_catalog.py::build_catalog` already tried every declared service and
 *  reports the ones that failed to answer, right in the response this whole panel already reads
 *  on every load. A service missing here means it did not answer AT catalog time, not "is down
 *  right now" — the honest freshness bound is stated by the caller, not invented here. */
export function unreachableServices(catalog: AdminCatalog): string[] {
  return catalog.unreachable;
}

interface AuditEvent {
  id: string; ts: string; actor: string; tenant: string;
}

/** Repeated failed sign-ins in the last `hours` (default 24) — a real audited action
 *  (`auth.login_failed`, identity-service) read through the already-declared `audit.query`, never
 *  a new backend surface. Grouped by actor because ONE failure is a typo; a burst from the SAME
 *  actor is the brute-force signal `auth.login_failed`'s own docstring names it as. */
export async function suspiciousLogins(
  session: AdminSession, catalog: AdminCatalog, hours = 24, threshold = 5,
): Promise<{ ok: true; actors: { actor: string; count: number }[] } | { ok: false; reason: string }> {
  const action = findAction(catalog, 'audit.query');
  if (!action) return { ok: false, reason: 'لا صلاحية لقراءة سجل التدقيق.' };

  const since = new Date(Date.now() - hours * 3600_000).toISOString();
  const qs = new URLSearchParams({ action: 'auth.login_failed', since, limit: '1000' });
  const body: { events: AuditEvent[] } = await req(`${action.path}?${qs}`, 'GET', undefined, session.access_token);
  const counts = new Map<string, number>();
  for (const e of body.events) {
    counts.set(e.actor, (counts.get(e.actor) ?? 0) + 1);
  }
  const actors = Array.from(counts.entries())
    .filter(([, count]) => count >= threshold)
    .map(([actor, count]) => ({ actor, count }))
    .sort((a, b) => b.count - a.count);
  return { ok: true, actors };
}

/** Affiliate applications waiting for a decision (11.7) — same action `AdminCustomers.tsx`
 *  already renders as a list; this is only the count for the dashboard tile. */
export async function pendingAffiliateApplications(
  session: AdminSession, catalog: AdminCatalog,
): Promise<{ ok: true; count: number } | { ok: false; reason: string }> {
  const action = findAction(catalog, 'affiliates.list_pending');
  if (!action) return { ok: false, reason: 'لا صلاحية لقراءة طلبات المسوّقين.' };
  const body: { applications: unknown[] } = await req(action.path, 'GET', undefined, session.access_token);
  return { ok: true, count: body.applications.length };
}

interface TicketRow { status: string }

/** Open tickets right now (11.8, half of it) — `tickets.inbox` has no aggregate count route, only
 *  a raw paginated list (`limit` capped at 200 server-side), so this reads ONE page and reports
 *  honestly: `atLeast: true` when a `cursor` came back, meaning the true count is higher, never a
 *  number presented as final when it isn't. Average response time is NOT computed here — the raw
 *  ticket row's own field names for first-response/created timestamps were not confirmed against
 *  real code, and a guessed field name would silently compute nonsense instead of failing loudly. */
export async function openTicketsCount(
  session: AdminSession, catalog: AdminCatalog,
): Promise<{ ok: true; count: number; atLeast: boolean } | { ok: false; reason: string }> {
  const action = findAction(catalog, 'tickets.inbox');
  if (!action) return { ok: false, reason: 'لا صلاحية لقراءة التذاكر.' };
  const body: { tickets: TicketRow[]; cursor: string | null } = await req(
    `${action.path}?status=open&limit=200`, 'GET', undefined, session.access_token,
  );
  return { ok: true, count: body.tickets.length, atLeast: Boolean(body.cursor) };
}

interface BackupAlert { service: string; severity: 'degraded' | 'critical'; reason: string }
interface BackupHealthBody {
  status: 'healthy' | 'degraded' | 'critical';
  alerts: BackupAlert[];
  summary: { total: number; healthy: number; degraded: number; critical: number };
}

/** Backup health across every registered target (11.12) — `backup.health`'s own summary/alerts,
 *  never recomputed here. */
export async function backupHealth(
  session: AdminSession, catalog: AdminCatalog,
): Promise<{ ok: true; body: BackupHealthBody } | { ok: false; reason: string }> {
  const action = findAction(catalog, 'backup.health');
  if (!action) return { ok: false, reason: 'لا صلاحية لقراءة صحة النسخ الاحتياطي.' };
  const body: BackupHealthBody = await req(action.path, 'GET', undefined, session.access_token);
  return { ok: true, body };
}

interface MemberRow { status: 'active' | 'suspended' }

/** Active admin team members right now (9.5) — `identity.list_members`, tenant read straight off
 *  the caller's own token claim (no `?tenant=`, confirmed against the route's own code — there is
 *  no way to target a tenant other than the caller's from this route), one bounded page (200, the
 *  service's own max page size) — honest `atLeast` flag if a bigger team ever exists than that. */
export async function activeTeamCount(
  session: AdminSession, catalog: AdminCatalog,
): Promise<{ ok: true; count: number; atLeast: boolean } | { ok: false; reason: string }> {
  const action = findAction(catalog, 'identity.list_members');
  if (!action) return { ok: false, reason: 'لا صلاحية لقراءة فريق الإدارة.' };
  const body: { members: MemberRow[]; next: string | null } = await req(
    `${action.path}?limit=200`, 'GET', undefined, session.access_token,
  );
  return {
    ok: true,
    count: body.members.filter((m) => m.status === 'active').length,
    atLeast: Boolean(body.next),
  };
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
