/**
 * «تبادل منافع» — cross-tenant customer referral (core/mutual_benefit.py's own module
 * docstring; deploy/seed/plans.json's own note beside this row). NOT «تحالف استراتيجي»/Coupons.tsx:
 * that app discounts OUR OWN subscription price between two shops; this one moves real customers
 * between two real shops, backed by both shops' own catalogues, mutual-consent only.
 *
 * REDESIGNED (owner's own direction, in full): a PARTNER-CENTRIC view, not a flat contract list —
 * every partnership this shop ever had with the SAME other shop groups under one partner card,
 * because the owner's own real question is never "what does row 14 say" but "how is this
 * RELATIONSHIP doing". Grounded in 2026 partner-relationship-management (PRM) practice — a
 * scorecard limited to a few leading/lagging indicators, a merged activity feed, progressive
 * disclosure (collapsed by default, real numbers computed only once opened) — not invented from
 * nothing. Language throughout is «شراكة»/«تعاون», never «عقد» — the owner's own explicit call:
 * this is a strategic relationship, not a legal instrument, and must never read like one.
 *
 * NO FREE TEXT ANYWHERE for what a grant is — a gift is always a real service picked from the
 * granting shop's own catalogue, and a discount is one of three catalogue-driven scopes (a real
 * service, a blanket "whole visit", or a real package/group). Every grant's own text is DERIVED
 * server-side (core/entitlements.py) from whichever real catalogue fact backs it.
 *
 * TERMS ARE IMMUTABLE ONCE PROPOSED — no edit action anywhere in this file, on purpose: a
 * different grant is a NEW partnership, never a change to an existing one.
 *
 * THE SCORECARD IS COMPUTED, NEVER GUESSED. `kpis()` only answers in aggregate (as referrer / as
 * beneficiary, across every partner at once) — nothing server-side breaks it down per partner. So
 * a partner's own scorecard is computed client-side, ON DEMAND when that card is opened (never for
 * every partner up front — that would be one audit-log call per agreement, for partners nobody is
 * even looking at), by fetching that partner's own agreements' audit logs and counting real
 * `grant_created`/`grant_redeemed` events. Same posture as everywhere else in this product: an
 * unreadable read shows a real "تعذّر" message, never a silent zero.
 */
import { useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  ArrowDownLeft, ArrowUpRight, ChevronDown, Gift, HandHeart, Percent, Plus, Search, X,
} from 'lucide-react';
import { PageHeader } from '../rj-ui/PageHeader';
import { Card } from '../rj-ui/Card';
import { KpiCard } from '../rj-ui/KpiCard';
import { TabBar } from '../rj-ui/TabBar';
import { Badge } from '../rj-ui/Badge';
import { Button } from '../rj-ui/Button';
import { EmptyState } from '../rj-ui/EmptyState';
import { BarCompare } from '../rj-ui/BarCompare';
import { Field, Input } from '../rj-ui/Field';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';
import { useOperatorI18n, tf } from '../operator-i18n';
import { halalas } from '../money';
import './mutual-benefit-i18n';

const GRANT_DISCOUNT = 'discount';
const GRANT_GIFT = 'gift';
const SCOPE_ITEM = 'item';
const SCOPE_BLANKET = 'blanket';
const SCOPE_GROUP = 'group';

const STATUS_TONE: Record<string, 'neutral' | 'accent' | 'success' | 'warning' | 'danger'> = {
  proposed: 'accent',
  active: 'success',
  paused: 'warning',
  cancel_requested: 'warning',
  ended: 'neutral',
  rejected: 'danger',
  expired_unanswered: 'neutral',
};

// THE DOT'S OWN COLOUR — Badge already carries a tone, but the partner card's own activity pill
// needs a plain hex for a live CSS dot (a pulsing one for "active"), which Badge does not expose.
const ACTIVITY_DOT: Record<'active' | 'paused' | 'pending' | 'inactive', string> = {
  active: 'bg-success', paused: 'bg-warning', pending: 'bg-accent', inactive: 'bg-text-tertiary',
};

interface Agreement {
  id: string;
  shop_a: string;
  shop_b: string;
  status: string;
  condition_type: string;
  condition_value: string;
  grant_validity_days: number;
  agreement_duration_days: number;
  started_at: number;
  ends_at: number;
  cancel_requested_by: string;
  grant_type: string;
  gift_service_id: string;
  gift_service_name: string;
  discount_scope: string;
  discount_group_id: string;
  discount_group_name: string;
}

interface RoleKpis {
  referrals_sent: number;
  redeemed: number;
  expired_unused: number;
  redemption_rate: number;
  by_month: Record<string, number>;
  gift_redemptions_by_service: Record<string, { service_name: string; granted: number; redeemed: number }>;
  discount_redemptions_by_group: Record<string, { group_name: string; granted: number; redeemed: number }>;
}
interface Kpis { as_referrer: RoleKpis; as_beneficiary: RoleKpis }

interface CatalogueItem { id: string; name: string; active?: boolean }

interface AuditEntry { id: string; event: string; actor_tenant: string; created: number }

function grantLine(a: Agreement, t: (k: string) => string): string {
  if (a.grant_type === GRANT_GIFT) return tf(t, 'mb.grant.gift', { name: a.gift_service_name });
  if (a.discount_scope === SCOPE_ITEM) return tf(t, 'mb.grant.discountItem', { name: a.gift_service_name });
  if (a.discount_scope === SCOPE_GROUP) return tf(t, 'mb.grant.discountGroup', { name: a.discount_group_name });
  return t('mb.grant.discountBlanket');
}

function formatDate(ts: number, locale: string): string {
  if (!ts) return '—';
  return new Date(ts * 1000).toLocaleDateString(locale === 'ar' ? 'ar-SA' : locale, {
    day: 'numeric', month: 'short', year: 'numeric',
  });
}

function formatDateTime(ts: number, locale: string): string {
  return new Date(ts * 1000).toLocaleString(locale === 'ar' ? 'ar-SA' : locale, {
    day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit',
  });
}

/** «هذا الطرف» يُعرَّف بهويته الحقيقية (المستأجر) — لا اسم ولا هاتف مخزَّن على أي اتفاق بعد
 *  إنشائه، فهذا كل ما هو متاح فعلاً للعرض دون بناء بحث جديد بالخادم. */
function otherParty(a: Agreement, myTenant: string): string {
  return a.shop_a === myTenant ? a.shop_b : a.shop_a;
}

function myRole(a: Agreement, myTenant: string): 'referrer' | 'beneficiary' {
  return a.shop_a === myTenant ? 'referrer' : 'beneficiary';
}

function partnerActivity(rows: Agreement[]): 'active' | 'paused' | 'pending' | 'inactive' {
  if (rows.some((r) => r.status === 'active')) return 'active';
  if (rows.some((r) => r.status === 'paused' || r.status === 'cancel_requested')) return 'paused';
  if (rows.some((r) => r.status === 'proposed')) return 'pending';
  return 'inactive';
}

const ACTIVITY_RANK: Record<string, number> = { active: 0, paused: 1, pending: 2, inactive: 3 };

export function MutualBenefitScreen({ session, catalog }: { session: Session; catalog: Catalog }) {
  const { t, locale } = useOperatorI18n();

  const listAction = action(catalog, 'operations.mutual_benefit_list');
  const kpisAction = action(catalog, 'operations.mutual_benefit_kpis');
  const proposeAction = action(catalog, 'operations.mutual_benefit_propose');
  const acceptAction = action(catalog, 'operations.mutual_benefit_accept');
  const rejectAction = action(catalog, 'operations.mutual_benefit_reject');
  const cancelRequestAction = action(catalog, 'operations.mutual_benefit_cancel_request');
  const cancelConfirmAction = action(catalog, 'operations.mutual_benefit_cancel_confirm');
  const auditLogAction = action(catalog, 'operations.mutual_benefit_audit_log');
  const servicesAction = action(catalog, 'operations.list_services');
  const packagesAction = action(catalog, 'operations.list_packages');

  const [rows, setRows] = useState<Agreement[] | 'loading' | 'failed'>('loading');
  const [kpis, setKpis] = useState<Kpis | null | undefined>(undefined);
  const [kpiTab, setKpiTab] = useState<'referrer' | 'beneficiary'>('referrer');
  const [services, setServices] = useState<CatalogueItem[]>([]);
  const [packages, setPackages] = useState<CatalogueItem[]>([]);
  const [showPropose, setShowPropose] = useState(false);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [roleFilter, setRoleFilter] = useState<'all' | 'referrer' | 'beneficiary'>('all');
  const [expanded, setExpanded] = useState<string | null>(null);

  const reload = () => {
    if (!listAction) { setRows('failed'); return; }
    setRows('loading');
    call<{ agreements: Agreement[] }>(session, listAction)
      .then((x) => setRows(x.agreements))
      .catch(() => setRows('failed'));
  };

  useEffect(reload, [session, catalog]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!kpisAction) { setKpis(null); return; }
    call<Kpis>(session, kpisAction).then(setKpis).catch(() => setKpis(null));
  }, [session, catalog, kpisAction]);

  useEffect(() => {
    if (!servicesAction) return;
    call<{ services: CatalogueItem[] }>(session, servicesAction)
      .then((x) => setServices(x.services)).catch(() => setServices([]));
  }, [session, catalog, servicesAction]);

  useEffect(() => {
    if (!packagesAction) return;
    call<{ packages: CatalogueItem[] }>(session, packagesAction)
      .then((x) => setPackages(x.packages)).catch(() => setPackages([]));
  }, [session, catalog, packagesAction]);

  const partners = useMemo(() => {
    if (!Array.isArray(rows)) return [];
    const byPartner = new Map<string, Agreement[]>();
    for (const r of rows) {
      const key = otherParty(r, session.tenant);
      const list = byPartner.get(key) ?? [];
      list.push(r);
      byPartner.set(key, list);
    }
    let groups = Array.from(byPartner.entries()).map(([partnerId, agreements]) => ({
      partnerId, agreements: agreements.sort((a, b) => b.started_at - a.started_at),
      activity: partnerActivity(agreements),
    }));
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      groups = groups.filter((g) => g.partnerId.toLowerCase().includes(q));
    }
    if (statusFilter !== 'all') {
      groups = groups
        .map((g) => ({ ...g, agreements: g.agreements.filter((a) => a.status === statusFilter) }))
        .filter((g) => g.agreements.length > 0);
    }
    if (roleFilter !== 'all') {
      groups = groups
        .map((g) => ({ ...g, agreements: g.agreements.filter((a) => myRole(a, session.tenant) === roleFilter) }))
        .filter((g) => g.agreements.length > 0);
    }
    groups.sort((a, b) => ACTIVITY_RANK[a.activity] - ACTIVITY_RANK[b.activity]
      || b.agreements.length - a.agreements.length);
    return groups;
  }, [rows, session.tenant, search, statusFilter, roleFilter]);

  if (!listAction) return null;

  const kpiData = kpis ? kpis[kpiTab === 'referrer' ? 'as_referrer' : 'as_beneficiary'] : null;
  const monthlyItems = kpiData
    ? Object.entries(kpiData.by_month).slice(-6).map(([m, n]) => ({ label: m.slice(5), value: n }))
    : [];
  const breakdownItems = kpiData
    ? [
        ...Object.values(kpiData.gift_redemptions_by_service).map((v) => ({ label: v.service_name, value: v.redeemed })),
        ...Object.values(kpiData.discount_redemptions_by_group).map((v) => ({ label: v.group_name, value: v.redeemed })),
      ].filter((v) => v.value > 0).sort((a, b) => b.value - a.value).slice(0, 6)
    : [];

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <PageHeader icon={HandHeart} title={t('mb.title')} />
          <p className="mt-1 text-sm text-text-secondary">{t('mb.subtitle')}</p>
        </div>
        {proposeAction ? (
          <Button onClick={() => setShowPropose((v) => !v)}>
            {showPropose ? <X size={16} /> : <Plus size={16} />}
            {showPropose ? t('mb.new.close') : t('mb.new.button')}
          </Button>
        ) : null}
      </div>

      <AnimatePresence initial={false}>
        {showPropose && proposeAction ? (
          <motion.div
            initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }} transition={{ duration: 0.22, ease: 'easeOut' }}
            className="overflow-hidden"
          >
            <ProposeCard
              session={session} proposeAction={proposeAction} services={services} packages={packages}
              onDone={() => { reload(); setShowPropose(false); }} t={t}
            />
          </motion.div>
        ) : null}
      </AnimatePresence>

      {kpis !== null ? (
        <Card className="flex flex-col gap-4 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm font-bold">{t('mb.overview.title')}</p>
            <TabBar
              value={kpiTab} onChange={setKpiTab} ariaLabel={t('mb.overview.title')}
              options={[
                { value: 'referrer', label: t('mb.overview.tab.referrer') },
                { value: 'beneficiary', label: t('mb.overview.tab.beneficiary') },
              ]}
            />
          </div>

          {kpiData ? (
            <>
              <motion.div
                key={kpiTab}
                initial="hidden" animate="show"
                variants={{ show: { transition: { staggerChildren: 0.06 } } }}
                className="grid grid-cols-2 gap-3 sm:grid-cols-4"
              >
                {[
                  { icon: <ArrowUpRight size={18} />, label: t('mb.kpi.sent'), value: kpiData.referrals_sent, tone: 'accent' as const },
                  { icon: <HandHeart size={18} />, label: t('mb.kpi.redeemed'), value: kpiData.redeemed, tone: 'success' as const },
                  { icon: <ArrowDownLeft size={18} />, label: t('mb.kpi.expired'), value: kpiData.expired_unused, tone: 'warning' as const },
                  { icon: <Percent size={18} />, label: t('mb.kpi.rate'), value: `${Math.round(kpiData.redemption_rate * 100)}%`, tone: 'neutral' as const },
                ].map((k) => (
                  <motion.div key={k.label}
                             variants={{ hidden: { opacity: 0, y: 8 }, show: { opacity: 1, y: 0 } }}>
                    <KpiCard icon={k.icon} label={k.label} value={k.value} tone={k.tone} />
                  </motion.div>
                ))}
              </motion.div>

              {monthlyItems.length || breakdownItems.length ? (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  {monthlyItems.length ? (
                    <div>
                      <p className="mb-2 text-xs font-bold text-text-secondary">{t('mb.chart.trend.title')}</p>
                      <BarCompare items={monthlyItems} />
                    </div>
                  ) : null}
                  {breakdownItems.length ? (
                    <div>
                      <p className="mb-2 text-xs font-bold text-text-secondary">
                        {t(kpiTab === 'referrer' ? 'mb.chart.breakdown.title.referrer' : 'mb.chart.breakdown.title.beneficiary')}
                      </p>
                      <BarCompare items={breakdownItems} />
                    </div>
                  ) : null}
                </div>
              ) : null}
            </>
          ) : null}
        </Card>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-48 flex-1">
          <Search size={16} className="pointer-events-none absolute start-3 top-1/2 -translate-y-1/2 text-text-tertiary" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)}
                placeholder={t('mb.toolbar.searchPlaceholder')} className="ps-9" />
        </div>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
               className="rounded-lg border border-border-subtle bg-surface-1 px-3 py-2 text-sm">
          <option value="all">{t('mb.toolbar.statusAll')}</option>
          {Object.keys(STATUS_TONE).map((s) => <option key={s} value={s}>{t(`mb.status.${s}`)}</option>)}
        </select>
        <select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value as typeof roleFilter)}
               className="rounded-lg border border-border-subtle bg-surface-1 px-3 py-2 text-sm">
          <option value="all">{t('mb.toolbar.roleAll')}</option>
          <option value="referrer">{t('mb.toolbar.role.referrer')}</option>
          <option value="beneficiary">{t('mb.toolbar.role.beneficiary')}</option>
        </select>
        <p className="text-xs text-text-tertiary">{t('mb.propose.note.cap')}</p>
      </div>

      {rows === 'failed' ? (
        <EmptyState title={t('mb.readFailed.title')} description={t('mb.readFailed.desc')} />
      ) : rows === 'loading' ? null : partners.length === 0 ? (
        rows.length === 0 ? (
          <EmptyState title={t('mb.empty.title')} description={t('mb.empty.desc')} />
        ) : (
          <EmptyState title={t('mb.empty.filtered')} />
        )
      ) : (
        <motion.div
          initial="hidden" animate="show"
          variants={{ show: { transition: { staggerChildren: 0.05 } } }}
          className="flex flex-col gap-3"
        >
          {partners.map((g) => (
            <motion.div key={g.partnerId}
                       variants={{ hidden: { opacity: 0, y: 10 }, show: { opacity: 1, y: 0 } }}>
              <PartnerCard
                session={session} group={g} expanded={expanded === g.partnerId}
                onToggle={() => setExpanded((cur) => (cur === g.partnerId ? null : g.partnerId))}
                auditLogAction={auditLogAction}
                acceptAction={acceptAction} rejectAction={rejectAction}
                cancelRequestAction={cancelRequestAction} cancelConfirmAction={cancelConfirmAction}
                onActed={reload} t={t} locale={locale}
              />
            </motion.div>
          ))}
        </motion.div>
      )}
    </div>
  );
}

function PartnerCard({
  session, group, expanded, onToggle, auditLogAction,
  acceptAction, rejectAction, cancelRequestAction, cancelConfirmAction, onActed, t, locale,
}: {
  session: Session; group: { partnerId: string; agreements: Agreement[]; activity: 'active' | 'paused' | 'pending' | 'inactive' };
  expanded: boolean; onToggle: () => void;
  auditLogAction: ReturnType<typeof action>;
  acceptAction: ReturnType<typeof action>; rejectAction: ReturnType<typeof action>;
  cancelRequestAction: ReturnType<typeof action>; cancelConfirmAction: ReturnType<typeof action>;
  onActed: () => void; t: (k: string) => string; locale: string;
}) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [entriesByAgreement, setEntriesByAgreement] = useState<Record<string, AuditEntry[]> | null | undefined>(undefined);

  useEffect(() => {
    if (!expanded) return;
    if (entriesByAgreement !== undefined) return;
    if (!auditLogAction) { setEntriesByAgreement(null); return; }
    Promise.all(group.agreements.map((a) =>
      call<{ entries: AuditEntry[] }>(session, auditLogAction, { id: a.id })
        .then((x) => [a.id, x.entries] as const)
        .catch(() => [a.id, null] as const)))
      .then((pairs) => {
        if (pairs.some(([, e]) => e === null)) { setEntriesByAgreement(null); return; }
        const map: Record<string, AuditEntry[]> = {};
        for (const [id, e] of pairs) map[id] = e as AuditEntry[];
        setEntriesByAgreement(map);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expanded]);

  async function act(a: ReturnType<typeof action>, id: string, confirmMsg?: string) {
    if (!a || busyId) return;
    // eslint-disable-next-line no-alert -- same window.confirm pattern the rest of the console uses
    if (confirmMsg && !window.confirm(confirmMsg)) return;
    setBusyId(id);
    try {
      await call(session, a, { id });
      setEntriesByAgreement(undefined);
      onActed();
    } finally {
      setBusyId(null);
    }
  }

  const scorecard = useMemo(() => {
    if (!entriesByAgreement) return entriesByAgreement;
    let granted = 0, redeemed = 0;
    for (const list of Object.values(entriesByAgreement)) {
      for (const e of list) {
        if (e.event === 'grant_created') granted += 1;
        if (e.event === 'grant_redeemed') redeemed += 1;
      }
    }
    return { granted, redeemed, rate: granted > 0 ? redeemed / granted : 0 };
  }, [entriesByAgreement]);

  const timeline = useMemo(() => {
    if (!entriesByAgreement) return null;
    return Object.values(entriesByAgreement).flat().sort((a, b) => b.created - a.created).slice(0, 12);
  }, [entriesByAgreement]);

  return (
    <Card interactive={false} className="flex flex-col gap-0 p-0 overflow-hidden">
      <button type="button" onClick={onToggle}
             className="flex w-full items-center justify-between gap-3 p-4 text-start transition-colors hover:bg-surface-2">
        <div className="flex items-center gap-3">
          <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${ACTIVITY_DOT[group.activity]} ${group.activity === 'active' ? 'animate-pulse' : ''}`} />
          <div>
            <p className="text-sm font-bold">{group.partnerId}</p>
            <p className="text-xs text-text-secondary">
              {t(`mb.partner.activity.${group.activity}`)} · {tf(t, 'mb.partner.count', { n: group.agreements.length })}
            </p>
          </div>
        </div>
        <motion.span animate={{ rotate: expanded ? 180 : 0 }} transition={{ duration: 0.18 }}>
          <ChevronDown size={18} className="text-text-tertiary" />
        </motion.span>
      </button>

      <AnimatePresence initial={false}>
        {expanded ? (
          <motion.div
            initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.22, ease: 'easeOut' }}
            className="overflow-hidden border-t border-border-subtle"
          >
            <div className="flex flex-col gap-4 p-4">
              <div>
                <p className="mb-2 text-xs font-bold text-text-secondary">{t('mb.scorecard.title')}</p>
                {scorecard === undefined ? (
                  <p className="text-xs text-text-tertiary">{t('mb.scorecard.loading')}</p>
                ) : scorecard === null ? (
                  <p className="text-xs text-danger">{t('mb.scorecard.failed')}</p>
                ) : (
                  <div className="grid grid-cols-3 gap-2">
                    <KpiCard icon={<ArrowUpRight size={16} />} label={t('mb.kpi.sent')} value={scorecard.granted} tone="accent" />
                    <KpiCard icon={<HandHeart size={16} />} label={t('mb.kpi.redeemed')} value={scorecard.redeemed} tone="success" />
                    <KpiCard icon={<Percent size={16} />} label={t('mb.kpi.rate')} value={`${Math.round(scorecard.rate * 100)}%`} tone="neutral" />
                  </div>
                )}
              </div>

              <div>
                <p className="mb-2 text-xs font-bold text-text-secondary">{t('mb.activity.title')}</p>
                {timeline === undefined ? null : timeline === null ? (
                  <p className="text-xs text-danger">{t('mb.scorecard.failed')}</p>
                ) : timeline.length === 0 ? (
                  <p className="text-xs text-text-tertiary">{t('mb.activity.empty')}</p>
                ) : (
                  <ol className="relative flex flex-col gap-3 ps-4">
                    <span className="absolute bottom-1 start-[3px] top-1 w-px bg-border-subtle" />
                    {timeline.map((e) => (
                      <li key={e.id} className="relative flex items-baseline justify-between gap-3 text-xs">
                        <span className="absolute -start-4 top-1 h-1.5 w-1.5 rounded-full bg-accent" />
                        <span className="font-medium">{t(`mb.event.${e.event}`)}</span>
                        <span className="shrink-0 tabular-nums text-text-tertiary">{formatDateTime(e.created, locale)}</span>
                      </li>
                    ))}
                  </ol>
                )}
              </div>

              <div>
                <p className="mb-2 text-xs font-bold text-text-secondary">{t('mb.agreements.title')}</p>
                <div className="flex flex-col gap-2">
                  {group.agreements.map((r) => {
                    const role = myRole(r, session.tenant);
                    const busy = busyId === r.id;
                    return (
                      <div key={r.id}
                           className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border-subtle p-3">
                        <div className="flex flex-wrap items-center gap-2">
                          {role === 'referrer'
                            ? <ArrowUpRight size={14} className="text-accent" />
                            : <ArrowDownLeft size={14} className="text-success" />}
                          {r.grant_type === GRANT_GIFT
                            ? <Gift size={14} className="text-text-tertiary" />
                            : <Percent size={14} className="text-text-tertiary" />}
                          <Badge tone={STATUS_TONE[r.status] ?? 'neutral'}>{t(`mb.status.${r.status}`)}</Badge>
                          <span className="text-xs">{grantLine(r, t)}</span>
                          <span className="text-xs text-text-tertiary">
                            {r.started_at ? tf(t, 'mb.since', { date: formatDate(r.started_at, locale) })
                                          : tf(t, 'mb.until', { date: formatDate(r.ends_at, locale) })}
                          </span>
                        </div>

                        <div className="flex gap-1.5">
                          {r.status === 'proposed' && r.shop_b === session.tenant ? (
                            <>
                              {acceptAction ? (
                                <Button size="sm" disabled={busy}
                                       onClick={() => act(acceptAction, r.id, t('mb.action.confirm.accept'))}>
                                  {t('mb.action.accept')}
                                </Button>
                              ) : null}
                              {rejectAction ? (
                                <Button size="sm" variant="ghost" disabled={busy}
                                       onClick={() => act(rejectAction, r.id)}>
                                  {t('mb.action.reject')}
                                </Button>
                              ) : null}
                            </>
                          ) : r.status === 'proposed' ? (
                            <span className="text-xs text-text-tertiary">{t('mb.action.waitingThem')}</span>
                          ) : r.status === 'active' && cancelRequestAction ? (
                            <Button size="sm" variant="ghost" disabled={busy}
                                   onClick={() => act(cancelRequestAction, r.id)}>
                              {t('mb.action.cancelRequest')}
                            </Button>
                          ) : r.status === 'cancel_requested' ? (
                            r.cancel_requested_by === session.tenant ? (
                              <span className="text-xs text-text-tertiary">{t('mb.action.waitingThem')}</span>
                            ) : cancelConfirmAction ? (
                              <Button size="sm" variant="danger" disabled={busy}
                                     onClick={() => act(cancelConfirmAction, r.id, t('mb.action.confirm.cancelConfirm'))}>
                                {t('mb.action.cancelConfirm')}
                              </Button>
                            ) : null
                          ) : null}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </Card>
  );
}

function ProposeCard({ session, proposeAction, services, packages, onDone, t }: {
  session: Session; proposeAction: NonNullable<ReturnType<typeof action>>;
  services: CatalogueItem[]; packages: CatalogueItem[]; onDone: () => void;
  t: (k: string) => string;
}) {
  const [phone, setPhone] = useState('');
  const [conditionType, setConditionType] = useState<'min_total_minor' | 'service_id'>('min_total_minor');
  const [conditionRiyals, setConditionRiyals] = useState(50);
  const [conditionServiceId, setConditionServiceId] = useState('');
  const [grantValidityDays, setGrantValidityDays] = useState(30);
  const [agreementDurationDays, setAgreementDurationDays] = useState(90);
  const [perPeriodCap, setPerPeriodCap] = useState(0);
  const [grantType, setGrantType] = useState<typeof GRANT_DISCOUNT | typeof GRANT_GIFT>(GRANT_DISCOUNT);
  const [discountScope, setDiscountScope] = useState<typeof SCOPE_ITEM | typeof SCOPE_BLANKET | typeof SCOPE_GROUP>(SCOPE_BLANKET);
  const [giftServiceId, setGiftServiceId] = useState('');
  const [discountGroupId, setDiscountGroupId] = useState('');
  const [discountKind, setDiscountKind] = useState<'percent' | 'fixed_halalas'>('percent');
  const [discountAmountText, setDiscountAmountText] = useState('10');
  const [submitting, setSubmitting] = useState(false);
  // MANDATORY, NEVER A FLOAT — same halalas()-on-text discipline `Launch.tsx`'s own campaign
  // discount uses (money.ts), so a fixed SAR amount never goes through a `* 100` float multiply.
  const discountAmount = discountKind === 'fixed_halalas'
    ? (halalas(discountAmountText) ?? 0)
    : Math.round(Number(discountAmountText) || 0);
  const [result, setResult] = useState<{ ok: boolean } | null>(null);

  const activeServices = services.filter((s) => s.active !== false);
  const activePackages = packages.filter((p) => p.active !== false);

  const needsService = grantType === GRANT_GIFT || (grantType === GRANT_DISCOUNT && discountScope === SCOPE_ITEM);
  const needsGroup = grantType === GRANT_DISCOUNT && discountScope === SCOPE_GROUP;

  const valid = phone.trim().length >= 9
    && (conditionType === 'min_total_minor' ? conditionRiyals > 0 : conditionServiceId !== '')
    && (!needsService || giftServiceId !== '')
    && (!needsGroup || discountGroupId !== '')
    // MANDATORY FOR A DISCOUNT GRANT ONLY — a gift's value is the named service itself.
    && (grantType !== GRANT_DISCOUNT || (discountAmount > 0 && (discountKind !== 'percent' || discountAmount <= 100)));

  async function onSubmit() {
    if (!valid || submitting) return;
    setSubmitting(true);
    setResult(null);
    try {
      await call(session, proposeAction, {
        shop_b_phone: phone.trim(),
        condition_type: conditionType,
        condition_value: conditionType === 'min_total_minor' ? String(Math.round(conditionRiyals * 100)) : conditionServiceId,
        grant_validity_days: grantValidityDays,
        agreement_duration_days: agreementDurationDays,
        per_period_cap: perPeriodCap,
        grant_type: grantType,
        gift_service_id: needsService ? giftServiceId : '',
        discount_scope: grantType === GRANT_DISCOUNT ? discountScope : '',
        discount_group_id: needsGroup ? discountGroupId : '',
        discount_kind: grantType === GRANT_DISCOUNT ? discountKind : '',
        discount_amount: grantType === GRANT_DISCOUNT ? discountAmount : 0,
      });
      setResult({ ok: true });
      setPhone('');
      onDone();
    } catch {
      setResult({ ok: false });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card className="flex flex-col gap-4 p-5">
      <p className="text-sm font-bold">{t('mb.propose.title')}</p>

      <div className="flex flex-wrap items-end gap-4">
        <Field label={t('mb.propose.phoneLabel')}>
          <Input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)}
                placeholder={t('mb.propose.phonePlaceholder')} className="w-40" />
        </Field>

        <Field label={t('mb.propose.conditionLabel')}>
          <select value={conditionType}
                 onChange={(e) => setConditionType(e.target.value as typeof conditionType)}
                 className="rounded-lg border border-border-subtle bg-surface-1 px-3 py-2 text-sm">
            <option value="min_total_minor">{t('mb.propose.condition.minTotal')}</option>
            <option value="service_id">{t('mb.propose.condition.serviceId')}</option>
          </select>
        </Field>

        {conditionType === 'min_total_minor' ? (
          <Field label={t('mb.propose.conditionValueRiyals')}>
            <Input type="number" min={1} value={conditionRiyals}
                  onChange={(e) => setConditionRiyals(Math.max(0, Number(e.target.value) || 0))}
                  className="w-28 tabular-nums" />
          </Field>
        ) : (
          <Field label={t('mb.propose.conditionValueService')}>
            <select value={conditionServiceId} onChange={(e) => setConditionServiceId(e.target.value)}
                   className="min-w-40 rounded-lg border border-border-subtle bg-surface-1 px-3 py-2 text-sm">
              <option value="">{t('mb.propose.selectPlaceholder')}</option>
              {activeServices.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </Field>
        )}

        <Field label={t('mb.propose.grantValidityLabel')}>
          <Input type="number" min={1} value={grantValidityDays}
                onChange={(e) => setGrantValidityDays(Math.max(1, Number(e.target.value) || 1))}
                className="w-24 tabular-nums" />
        </Field>

        <Field label={t('mb.propose.durationLabel')}>
          <Input type="number" min={1} value={agreementDurationDays}
                onChange={(e) => setAgreementDurationDays(Math.max(1, Number(e.target.value) || 1))}
                className="w-24 tabular-nums" />
        </Field>

        <Field label={t('mb.propose.perPeriodCapLabel')}>
          <Input type="number" min={0} value={perPeriodCap}
                onChange={(e) => setPerPeriodCap(Math.max(0, Number(e.target.value) || 0))}
                className="w-24 tabular-nums" />
        </Field>
      </div>

      <div className="flex flex-wrap items-end gap-4">
        <Field label={t('mb.propose.grantTypeLabel')}>
          <select value={grantType} onChange={(e) => setGrantType(e.target.value as typeof grantType)}
                 className="rounded-lg border border-border-subtle bg-surface-1 px-3 py-2 text-sm">
            <option value={GRANT_DISCOUNT}>{t('mb.propose.grantType.discount')}</option>
            <option value={GRANT_GIFT}>{t('mb.propose.grantType.gift')}</option>
          </select>
        </Field>

        {grantType === GRANT_DISCOUNT ? (
          <Field label={t('mb.propose.discountScopeLabel')}>
            <select value={discountScope}
                   onChange={(e) => setDiscountScope(e.target.value as typeof discountScope)}
                   className="rounded-lg border border-border-subtle bg-surface-1 px-3 py-2 text-sm">
              <option value={SCOPE_BLANKET}>{t('mb.propose.discountScope.blanket')}</option>
              <option value={SCOPE_ITEM}>{t('mb.propose.discountScope.item')}</option>
              {packages.length ? <option value={SCOPE_GROUP}>{t('mb.propose.discountScope.group')}</option> : null}
            </select>
          </Field>
        ) : null}

        {grantType === GRANT_DISCOUNT ? (
          <Field label={t('mb.propose.discountAmountLabel')}>
            <div className="flex items-center gap-2">
              <Input type="number" min={1} value={discountAmountText}
                    onChange={(e) => setDiscountAmountText(e.target.value)}
                    className="w-24 tabular-nums" />
              <select value={discountKind}
                     onChange={(e) => setDiscountKind(e.target.value as typeof discountKind)}
                     className="rounded-lg border border-border-subtle bg-surface-1 px-3 py-2 text-sm">
                <option value="percent">{t('mb.propose.discountKind.percent')}</option>
                <option value="fixed_halalas">{t('mb.propose.discountKind.sar')}</option>
              </select>
            </div>
          </Field>
        ) : null}

        {needsService ? (
          <Field label={t('mb.propose.serviceLabel')}>
            <select value={giftServiceId} onChange={(e) => setGiftServiceId(e.target.value)}
                   className="min-w-40 rounded-lg border border-border-subtle bg-surface-1 px-3 py-2 text-sm">
              <option value="">{t('mb.propose.selectPlaceholder')}</option>
              {activeServices.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </Field>
        ) : null}

        {needsGroup ? (
          <Field label={t('mb.propose.groupLabel')}>
            <select value={discountGroupId} onChange={(e) => setDiscountGroupId(e.target.value)}
                   className="min-w-40 rounded-lg border border-border-subtle bg-surface-1 px-3 py-2 text-sm">
              <option value="">{t('mb.propose.selectPlaceholder')}</option>
              {activePackages.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </Field>
        ) : null}

        <Button onClick={onSubmit} disabled={!valid || submitting}>
          {submitting ? t('mb.propose.submitting') : t('mb.propose.submit')}
        </Button>
      </div>

      <p className="text-xs text-text-tertiary">{t('mb.propose.note.immutable')}</p>

      {result ? (
        <div className={`rounded-lg px-3 py-2 text-sm font-semibold ${
          result.ok ? 'bg-success-soft text-success' : 'bg-danger-soft text-danger'
        }`}>
          {t(result.ok ? 'mb.propose.result.success' : 'mb.propose.result.fail')}
        </div>
      ) : null}
    </Card>
  );
}
