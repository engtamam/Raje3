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
  tenant: string;
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

// A CAPABILITY-GATED CALL CAN FAIL FOR REASONS OTHER THAN "not in the catalog" — a 403 the
// catalog itself didn't predict (a scope mismatch), a 500, a dropped connection. Every function
// below used to let that exception fall straight out of its own `req()` call, through
// `Promise.all` in AdminHome/AdminAnalytics, past the effect's own try/catch (which only guards
// `fetchCatalog`) — an unhandled rejection that left the WHOLE dashboard on "جارٍ التحميل…"
// forever, with every OTHER metric that would have succeeded never rendered either. One flaky
// call taking down every tile it shares a Promise.all with is not an acceptable failure mode on
// a screen a real operator depends on. Wrapping the call here turns that into this ONE tile
// reporting `ok: false`, same as "you don't hold this capability" already does.
async function safely<T>(fn: () => Promise<T>): Promise<{ ok: true; value: T } | { ok: false; reason: string }> {
  try {
    return { ok: true, value: await fn() };
  } catch {
    return { ok: false, reason: 'تعذّرت قراءة هذا الرقم الآن.' };
  }
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
  const result = await safely(async () => {
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
    return halalas;
  });
  return result.ok ? { ok: true, halalas: result.value } : result;
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
  const result = await safely(async () => {
    const qs = new URLSearchParams({ action: 'auth.login_failed', since, limit: '1000' });
    const body: { events: AuditEvent[] } = await req(`${action.path}?${qs}`, 'GET', undefined, session.access_token);
    const counts = new Map<string, number>();
    for (const e of body.events) {
      counts.set(e.actor, (counts.get(e.actor) ?? 0) + 1);
    }
    return Array.from(counts.entries())
      .filter(([, count]) => count >= threshold)
      .map(([actor, count]) => ({ actor, count }))
      .sort((a, b) => b.count - a.count);
  });
  return result.ok ? { ok: true, actors: result.value } : result;
}

/** Affiliate applications waiting for a decision (11.7) — same action `AdminCustomers.tsx`
 *  already renders as a list; this is only the count for the dashboard tile. */
export async function pendingAffiliateApplications(
  session: AdminSession, catalog: AdminCatalog,
): Promise<{ ok: true; count: number } | { ok: false; reason: string }> {
  const action = findAction(catalog, 'affiliates.list_pending');
  if (!action) return { ok: false, reason: 'لا صلاحية لقراءة طلبات المسوّقين.' };
  const result = await safely(async () => {
    const body: { applications: unknown[] } = await req(action.path, 'GET', undefined, session.access_token);
    return body.applications.length;
  });
  return result.ok ? { ok: true, count: result.value } : result;
}

interface TicketKpis {
  first_response_seconds: number | null;
  resolution_seconds: number | null;
}
interface TicketRow { status: string; created: string; kpis?: TicketKpis }

/** Open tickets right now (11.8, half of it) — `tickets.inbox` has no aggregate count route, only
 *  a raw paginated list (`limit` capped at 200 server-side), so this reads ONE page and reports
 *  honestly: `atLeast: true` when a `cursor` came back, meaning the true count is higher, never a
 *  number presented as final when it isn't. */
export async function openTicketsCount(
  session: AdminSession, catalog: AdminCatalog,
): Promise<{ ok: true; count: number; atLeast: boolean } | { ok: false; reason: string }> {
  const action = findAction(catalog, 'tickets.inbox');
  if (!action) return { ok: false, reason: 'لا صلاحية لقراءة التذاكر.' };
  const result = await safely(async () => {
    const body: { tickets: TicketRow[]; cursor: string | null } = await req(
      `${action.path}?status=open&limit=200`, 'GET', undefined, session.access_token,
    );
    return { count: body.tickets.length, atLeast: Boolean(body.cursor) };
  });
  return result.ok ? { ok: true, ...result.value } : result;
}

/** متوسط وقت أول رد (11.8، النصف الثاني) — `tickets.inbox` يُضمِّن الآن `kpis.first_response_seconds`
 *  لكل صفّ (تصعيد أجابه `base-services-72`، `ticket_kpis` نفس الدالة النقيّة المستخدَمة بالقراءة
 *  الداخلية للتذكرة الواحدة — لا حساب جديد، فقط تُضمَّن بالقائمة الآن). **لم يُنشَر بعد** — يحتاج
 *  إصدار `ticket-service` جديد لم يُثبَّت رقمه بعد بـ`platform/`؛ الدالة صحيحة اليوم لكنها تُرجع
 *  `sampleSize: 0` حتى يصل الإصدار (كل الصفوف بلا `kpis` تُستبعَد من المتوسط بصمت، لا تُحسَب
 *  كصفر). تذكرة بلا ردّ عامل بعد = `null`، تُستبعَد من المقام لا تُحسَب كرد فوري. */
export async function avgFirstResponseSeconds(
  session: AdminSession, catalog: AdminCatalog,
): Promise<{ ok: true; avgSeconds: number | null; sampleSize: number; atLeast: boolean } | { ok: false; reason: string }> {
  const action = findAction(catalog, 'tickets.inbox');
  if (!action) return { ok: false, reason: 'لا صلاحية لقراءة التذاكر.' };
  const result = await safely(async () => {
    const body: { tickets: TicketRow[]; cursor: string | null } = await req(
      `${action.path}?limit=200`, 'GET', undefined, session.access_token,
    );
    const values = body.tickets
      .map((t) => t.kpis?.first_response_seconds)
      .filter((v): v is number => typeof v === 'number');
    return {
      avgSeconds: values.length ? Math.round(values.reduce((a, b) => a + b, 0) / values.length) : null,
      sampleSize: values.length,
      atLeast: Boolean(body.cursor),
    };
  });
  return result.ok ? { ok: true, ...result.value } : result;
}

/** (33) تذاكر غير محلولة منذ أكثر من 48 ساعة — نفس التضمين الجديد (`kpis.resolution_seconds`).
 *  **لم يُنشَر بعد**، نفس ملاحظة الدالة أعلاه. غير محصورة بنوع "شكوى" تحديداً — قيم أنواع
 *  التذاكر الحقيقية لم تُؤكَّد بالكود، وتخمين قيمة `type` قد يُرجع صفراً صامتاً بدل رفض واضح؛
 *  تُعرَض كـ"تذاكر غير محلولة" عموماً حتى تتأكد قيمة النوع. */
export async function unresolvedTicketsOver48h(
  session: AdminSession, catalog: AdminCatalog,
): Promise<{ ok: true; count: number; atLeast: boolean } | { ok: false; reason: string }> {
  const action = findAction(catalog, 'tickets.inbox');
  if (!action) return { ok: false, reason: 'لا صلاحية لقراءة التذاكر.' };
  const result = await safely(async () => {
    const body: { tickets: TicketRow[]; cursor: string | null } = await req(
      `${action.path}?limit=200`, 'GET', undefined, session.access_token,
    );
    const cutoffMs = Date.now() - 48 * 3600_000;
    const count = body.tickets.filter((t) => {
      if (!t.kpis || t.kpis.resolution_seconds !== null) return false;
      const createdMs = Date.parse(t.created);
      return Number.isFinite(createdMs) && createdMs < cutoffMs;
    }).length;
    return { count, atLeast: Boolean(body.cursor) };
  });
  return result.ok ? { ok: true, ...result.value } : result;
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
  const result = await safely(() => req<BackupHealthBody>(action.path, 'GET', undefined, session.access_token));
  return result.ok ? { ok: true, body: result.value } : result;
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
  const result = await safely(async () => {
    const body: { members: MemberRow[]; next: string | null } = await req(
      `${action.path}?limit=200`, 'GET', undefined, session.access_token,
    );
    return { count: body.members.filter((m) => m.status === 'active').length, atLeast: Boolean(body.next) };
  });
  return result.ok ? { ok: true, ...result.value } : result;
}

interface RetentionPoint { at: number | null; value: number | null }
export interface PlatformInsights {
  returnRate: number | null;
  peakGrid: { day: string; hour: string; value: number }[];
  atRiskTenantCount: number | null;
  retentionSeries: RetentionPoint[] | null;   // null = learning (too little data platform-wide)
  tenantsWithSnapshot: number;
}

const DAY_LABELS = ['الأحد', 'الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت'];

/** The platform-wide rollup (11.1-11.4) — `insights.platform_summary` reads a PRECOMPUTED row
 *  (`services/insights`'s own scheduled pass, never computed on this request) — never re-derived
 *  here, only reshaped for the chart components. */
export async function platformInsights(
  session: AdminSession, catalog: AdminCatalog,
): Promise<{ ok: true; computing: true } | { ok: true; computing: false; data: PlatformInsights }
         | { ok: false; reason: string }> {
  const action = findAction(catalog, 'insights.platform_summary');
  if (!action) return { ok: false, reason: 'لا صلاحية لقراءة ملخص المنصّة.' };
  const result = await safely(async () => {
    const body: {
      computing: boolean;
      values: {
        return_rate?: number | null;
        peak_map?: { grid: Record<string, number>; busiest: string };
        at_risk_tenant_count?: number;
        retention_series?: { points?: RetentionPoint[]; learning: boolean };
      };
      tenants_with_snapshot?: number;
    } = await req(action.path, 'GET', undefined, session.access_token);
    if (body.computing) return { computing: true as const };
    const v = body.values || {};
    const peakGrid = Object.entries(v.peak_map?.grid ?? {}).map(([slot, value]) => {
      const [day, hour] = slot.split(':');
      return { day: DAY_LABELS[Number(day)] ?? day, hour: `${hour}:00`, value };
    });
    return {
      computing: false as const,
      data: {
        returnRate: v.return_rate ?? null,
        peakGrid,
        atRiskTenantCount: v.at_risk_tenant_count ?? null,
        retentionSeries: v.retention_series && !v.retention_series.learning
          ? (v.retention_series.points ?? []) : null,
        tenantsWithSnapshot: body.tenants_with_snapshot ?? 0,
      },
    };
  });
  return result.ok ? { ok: true, ...result.value } : result;
}

export interface AffiliateStats {
  activeAffiliates: number; totalAffiliates: number;
  totalNetRevenueMinor: number; revenuePartial: boolean;
}

/** (16)(17) active affiliates + platform-wide referred revenue — `affiliates.platform_stats`. */
export async function affiliateStats(
  session: AdminSession, catalog: AdminCatalog,
): Promise<{ ok: true; data: AffiliateStats } | { ok: false; reason: string }> {
  const action = findAction(catalog, 'affiliates.platform_stats');
  if (!action) return { ok: false, reason: 'لا صلاحية لقراءة إحصائيات المسوّقين.' };
  const result = await safely(async () => {
    const body: {
      active_affiliates: number; total_affiliates: number;
      total_net_revenue_minor: number; revenue_partial: boolean;
    } = await req(action.path, 'GET', undefined, session.access_token);
    return { activeAffiliates: body.active_affiliates, totalAffiliates: body.total_affiliates,
             totalNetRevenueMinor: body.total_net_revenue_minor, revenuePartial: body.revenue_partial };
  });
  return result.ok ? { ok: true, data: result.value } : result;
}

export interface LeaderboardRow {
  affiliateId: string; name: string; activeShops: number;
  retentionRate: number; totalReferrals: number; totalCommissions: number;
}

/** (19) أفضل المسوّقين أداءً — `affiliates.leaderboard`. */
export async function affiliateLeaderboard(
  session: AdminSession, catalog: AdminCatalog, limit = 10,
): Promise<{ ok: true; rows: LeaderboardRow[] } | { ok: false; reason: string }> {
  const action = findAction(catalog, 'affiliates.leaderboard');
  if (!action) return { ok: false, reason: 'لا صلاحية لقراءة أفضل المسوّقين.' };
  const result = await safely(async () => {
    const body: { leaderboard: Array<{
      affiliate_id: string; name: string; active_shops: number;
      retention_rate: number; total_referrals: number; total_commissions: number;
    }> } = await req(`${action.path}?limit=${limit}`, 'GET', undefined, session.access_token);
    return body.leaderboard.map((r) => ({
      affiliateId: r.affiliate_id, name: r.name, activeShops: r.active_shops,
      retentionRate: r.retention_rate, totalReferrals: r.total_referrals,
      totalCommissions: r.total_commissions,
    }));
  });
  return result.ok ? { ok: true, rows: result.value } : result;
}

export interface GeoPointOut { id: string; lat: number; lng: number; label: string; group?: string }

/** (18) خريطة العملاء المحتملين — `leads.geo_map`، بلا أي بيانات تواصل (id/lat/lng/city/sector
 *  فقط، مؤكَّد بالخلفية). */
export async function leadsGeoPoints(
  session: AdminSession, catalog: AdminCatalog,
): Promise<{ ok: true; points: GeoPointOut[] } | { ok: false; reason: string }> {
  const action = findAction(catalog, 'leads.geo_map');
  if (!action) return { ok: false, reason: 'لا صلاحية لقراءة خريطة العملاء المحتملين.' };
  const result = await safely(async () => {
    const body: { points: Array<{ id: string; lat: number; lng: number; city: string; sector_code: string }> } =
      await req(action.path, 'GET', undefined, session.access_token);
    return body.points.map((p) => ({ id: p.id, lat: p.lat, lng: p.lng, label: p.city, group: p.sector_code || undefined }));
  });
  return result.ok ? { ok: true, points: result.value } : result;
}

/** خريطة المحلات الفعلية عبر كل تينانت — `operations.branch_locations` (مبنية بالمرحلة 5،
 *  تُستهلَك أخيراً هنا). */
export async function branchGeoPoints(
  session: AdminSession, catalog: AdminCatalog,
): Promise<{ ok: true; points: GeoPointOut[] } | { ok: false; reason: string }> {
  const action = findAction(catalog, 'operations.branch_locations');
  if (!action) return { ok: false, reason: 'لا صلاحية لقراءة خريطة المحلات.' };
  const result = await safely(async () => {
    const body: { branches: Array<{ id: string; name: string; lat: number; lng: number; city: string }> } =
      await req(`${action.path}?limit=200`, 'GET', undefined, session.access_token);
    return body.branches.map((b) => ({ id: b.id, lat: b.lat, lng: b.lng, label: b.name, group: b.city || undefined }));
  });
  return result.ok ? { ok: true, points: result.value } : result;
}

/** (32) محلات دفعها فشل — بلوحة القيادة (10.5). فواتير `status=open` — النموذج التجاري مسبوق
 *  الدفع بالكامل (لا حالة "متأخرة")، فأي فاتورة `open` تعني توقّف خدمة المحل فعلياً الآن، لا
 *  مجرّد تذكير. صفحة واحدة محدودة (1000)، بعلم `atLeast` صادق لو تجاوز الحد — لا رقم نهائي
 *  مزيَّف. عدّ محلات فريدة، لا فواتير — محل بفاتورتين مفتوحتين يظهر مرّة واحدة. */
export async function failedPaymentTenants(
  session: AdminSession, catalog: AdminCatalog,
): Promise<{ ok: true; count: number; atLeast: boolean } | { ok: false; reason: string }> {
  const action = findAction(catalog, 'billing.platform_invoices');
  if (!action) return { ok: false, reason: 'لا صلاحية لقراءة الفواتير عبر المنصّة.' };
  const result = await safely(async () => {
    const body: InvoicesPage = await req(
      `${action.path}?status=open&limit=1000`, 'GET', undefined, session.access_token,
    );
    const tenants = new Set(body.invoices.map((inv) => inv.tenant).filter(Boolean));
    return { count: tenants.size, atLeast: Boolean(body.next_cursor) };
  });
  return result.ok ? { ok: true, ...result.value } : result;
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

  const result = await safely(async () => {
    const body: { tenants: TenantRow[] } = await req(action.path, 'GET', undefined, session.access_token);
    const monthStart = isoMonthStart(0);
    return body.tenants.reduce<TenantCounts>((acc, t) => {
      acc.total += 1;
      if (t.status === 'active') acc.active += 1;
      if (t.created_at >= monthStart) acc.newThisMonth += 1;
      return acc;
    }, { total: 0, active: 0, newThisMonth: 0 });
  });
  return result.ok ? { ok: true, counts: result.value } : result;
}
