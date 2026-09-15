/**
 * «خدمات متنقلة» — the shop's own review queue for a service that travels TO the customer (a
 * mobile car wash, say), built the real screen the artifact mockup only sketched:
 * services/operations/app/core/mobile_requests.py's own state machine (pending -> accepted/
 * rejected, then accepted -> completed/no_show), reviewed here one request at a time.
 *
 * NO STAFF DISTRIBUTION, ON PURPOSE — the owner's own words: "لا لا خلاص طلبات تترص وانتهينا".
 * This screen is the whole workflow: a request lands, the shop accepts or rejects it, and after
 * the shop actually did the work it marks «تم» (a real visit — loyalty/insights pick it up like
 * any other) or «لم يتم» (never a visit, just a heads-up for next time).
 *
 * "تحتاج قرار" IS A HONEST PROXY, NOT A PARSED APPOINTMENT TIME. `requested_time_text` is the
 * customer's own free words from WhatsApp ("بكرا العصر", "أقرب وقت") — never a real timestamp the
 * backend could compare against "now" (see core/mobile_requests.py's own dataclass: there is no
 * `scheduled_at` field, deliberately, because a WhatsApp-collected time like that cannot be
 * parsed reliably). So "needs a decision" here means what it can honestly mean: accepted a while
 * ago and still sitting with no «تم»/«لم يتم» — `NEEDS_DECISION_AFTER_HOURS` below, not a claim
 * about the appointment's own clock.
 */
import { useEffect, useMemo, useState } from 'react';
import {
  Truck, MapPin, Clock, AlertTriangle, CheckCircle2, XCircle, Search, CalendarCheck2,
} from 'lucide-react';
import { PageHeader } from '../rj-ui/PageHeader';
import { KpiCard } from '../rj-ui/KpiCard';
import { Segmented } from '../rj-ui/Segmented';
import { Badge } from '../rj-ui/Badge';
import { Button } from '../rj-ui/Button';
import { EmptyState } from '../rj-ui/EmptyState';
import { Input } from '../rj-ui/Field';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';
import { useOperatorI18n, tf } from '../operator-i18n';
import './mobile-requests-i18n';

interface MobileServiceRequest {
  id: string;
  tenant: string;
  phone: string;
  customer_name: string;
  service_ids: string[];
  requested_time_text: string;
  lat: number;
  lng: number;
  status: 'pending' | 'accepted' | 'rejected' | 'completed' | 'no_show';
  created: number;
  decided_at: number;
  decided_by: string;
  reject_reason: string;
  visit_id: string;
  note: string;
  maps_url: string;
}

interface NoShowRisk {
  considered: number;
  no_shows: number;
  risky: boolean;
  threshold_percent: number;
}

interface ServiceRow { id: string; name: string }

type Filter = 'all' | 'pending' | 'accepted' | 'needs_decision' | 'completed' | 'closed';

// See this file's own module docstring — an honest proxy for "the appointment has clearly come
// and gone", not a parsed time. 3 hours: most requested_time_text windows are same-day ("العصر",
// "بعد الظهر"), so an accepted request still open three hours later is already worth surfacing,
// without flagging one accepted five minutes ago that simply has not happened yet.
const NEEDS_DECISION_AFTER_HOURS = 3;
const NEEDS_DECISION_AFTER_SECONDS = NEEDS_DECISION_AFTER_HOURS * 3600;

function isNeedsDecision(r: MobileServiceRequest, nowSeconds: number): boolean {
  return r.status === 'accepted' && nowSeconds - r.decided_at > NEEDS_DECISION_AFTER_SECONDS;
}

function relativeTime(ts: number, nowSeconds: number, t: (k: string) => string): string {
  const diff = Math.max(0, nowSeconds - ts);
  const mins = Math.floor(diff / 60);
  if (mins < 1) return t('mobileRequests.time.justNow');
  if (mins < 60) return tf(t, 'mobileRequests.time.minutesAgo', { n: mins });
  const hours = Math.floor(mins / 60);
  if (hours < 24) return tf(t, 'mobileRequests.time.hoursAgo', { n: hours });
  const days = Math.floor(hours / 24);
  return tf(t, 'mobileRequests.time.daysAgo', { n: days });
}

function formatDate(ts: number, locale: string): string {
  if (!ts) return '';
  return new Date(ts * 1000).toLocaleDateString(locale === 'ar' ? 'ar-SA' : locale, {
    day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit',
  });
}

export function MobileRequestsScreen({ session, catalog }: { session: Session; catalog: Catalog }) {
  const { t, locale } = useOperatorI18n();

  const listAction = action(catalog, 'operations.mobile_requests_list');
  const acceptAction = action(catalog, 'operations.mobile_request_accept');
  const rejectAction = action(catalog, 'operations.mobile_request_reject');
  const completeAction = action(catalog, 'operations.mobile_request_complete');
  const noShowAction = action(catalog, 'operations.mobile_request_no_show');
  const riskAction = action(catalog, 'operations.mobile_request_risk');
  const servicesAction = action(catalog, 'operations.manage_services') ?? action(catalog, 'operations.list_services');

  const [rows, setRows] = useState<MobileServiceRequest[] | 'loading' | 'failed'>('loading');
  const [services, setServices] = useState<Map<string, string>>(new Map());
  const [risks, setRisks] = useState<Map<string, NoShowRisk>>(new Map());
  const [filter, setFilter] = useState<Filter>('all');
  const [search, setSearch] = useState('');
  const [busyId, setBusyId] = useState<string | null>(null);
  const [now, setNow] = useState(() => Math.floor(Date.now() / 1000));

  // TICKS THE "منذ كذا"/"تحتاج قرار" READ FORWARD without a refetch — a card that was fine when
  // the list loaded must still flip into the needs-decision bucket while the owner is looking at
  // the screen, not only on the next reload.
  useEffect(() => {
    const id = setInterval(() => setNow(Math.floor(Date.now() / 1000)), 60_000);
    return () => clearInterval(id);
  }, []);

  const load = () => {
    if (!listAction) { setRows('failed'); return; }
    setRows('loading');
    call<{ requests: MobileServiceRequest[] }>(session, listAction)
      .then((x) => setRows(x.requests))
      .catch(() => setRows('failed'));
  };

  useEffect(load, [session, catalog]);

  useEffect(() => {
    if (!servicesAction) return;
    call<{ services: ServiceRow[] }>(session, servicesAction, { include_retired: true })
      .then((x) => setServices(new Map(x.services.map((s) => [s.id, s.name]))))
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session, catalog]);

  // RISK, ONLY FOR REQUESTS STILL PENDING A DECISION — the owner's own instruction: a heads-up at
  // accept time, never an enforced deposit. Fetched once per id the moment it shows up here, not
  // re-fetched on every tick.
  useEffect(() => {
    if (!riskAction || !Array.isArray(rows)) return;
    const pending = rows.filter((r) => r.status === 'pending' && !risks.has(r.id));
    if (pending.length === 0) return;
    let cancelled = false;
    Promise.all(pending.map((r) =>
      call<NoShowRisk>(session, riskAction, { request_id: r.id })
        .then((risk) => [r.id, risk] as const)
        .catch(() => null),
    )).then((results) => {
      if (cancelled) return;
      setRisks((prev) => {
        const next = new Map(prev);
        for (const entry of results) if (entry) next.set(entry[0], entry[1]);
        return next;
      });
    });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, riskAction]);

  const list = Array.isArray(rows) ? rows : [];
  const needsDecisionRows = useMemo(
    () => list.filter((r) => isNeedsDecision(r, now)),
    [list, now],
  );
  const pendingCount = list.filter((r) => r.status === 'pending').length;
  const completedThisMonth = useMemo(() => {
    const monthStart = new Date();
    monthStart.setDate(1); monthStart.setHours(0, 0, 0, 0);
    const cutoff = monthStart.getTime() / 1000;
    return list.filter((r) => r.status === 'completed' && r.created >= cutoff).length;
  }, [list]);

  const filtered = useMemo(() => {
    let out = list;
    if (filter === 'pending') out = out.filter((r) => r.status === 'pending');
    else if (filter === 'accepted') out = out.filter((r) => r.status === 'accepted');
    else if (filter === 'needs_decision') out = out.filter((r) => isNeedsDecision(r, now));
    else if (filter === 'completed') out = out.filter((r) => r.status === 'completed');
    else if (filter === 'closed') out = out.filter((r) => r.status === 'rejected' || r.status === 'no_show');
    if (search.trim()) {
      const q = search.trim();
      out = out.filter((r) => r.customer_name.includes(q) || r.phone.includes(q));
    }
    return [...out].sort((a, b) => b.created - a.created);
  }, [list, filter, search, now]);

  async function onAccept(r: MobileServiceRequest) {
    if (!acceptAction || busyId) return;
    setBusyId(r.id);
    try {
      await call(session, acceptAction, { request_id: r.id });
      load();
    } finally { setBusyId(null); }
  }

  async function onReject(r: MobileServiceRequest) {
    if (!rejectAction || busyId) return;
    // eslint-disable-next-line no-alert -- same lightweight prompt Coupons.tsx's own disconnect
    // confirm uses; a full modal is more weight than an optional one-line reason needs.
    const reason = window.prompt(t('mobileRequests.reject.reasonPrompt')) ?? '';
    setBusyId(r.id);
    try {
      await call(session, rejectAction, { request_id: r.id, reason: reason.trim() });
      load();
    } finally { setBusyId(null); }
  }

  async function onComplete(r: MobileServiceRequest) {
    if (!completeAction || busyId) return;
    setBusyId(r.id);
    try {
      await call(session, completeAction, { request_id: r.id });
      load();
    } finally { setBusyId(null); }
  }

  async function onNoShow(r: MobileServiceRequest) {
    if (!noShowAction || busyId) return;
    setBusyId(r.id);
    try {
      await call(session, noShowAction, { request_id: r.id });
      load();
    } finally { setBusyId(null); }
  }

  return (
    <div className="flex flex-col gap-4 p-4">
      <PageHeader icon={Truck} title={t('mobileRequests.title')} />
      <p className="-mt-2 text-sm text-text-secondary">{t('mobileRequests.subtitle')}</p>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <KpiCard icon={<Clock size={18} />} label={t('mobileRequests.kpi.pending')}
                value={pendingCount} tone="info" testId="mobile-requests-kpi-pending" />
        <KpiCard icon={<AlertTriangle size={18} />} label={t('mobileRequests.kpi.needsDecision')}
                value={needsDecisionRows.length} tone="warning" testId="mobile-requests-kpi-needs-decision" />
        <KpiCard icon={<CalendarCheck2 size={18} />} label={t('mobileRequests.kpi.completedThisMonth')}
                value={completedThisMonth} tone="success" testId="mobile-requests-kpi-completed" />
      </div>

      {needsDecisionRows.length > 0 ? (
        <div className="flex flex-wrap items-center gap-3 rounded-card border border-warning/30 bg-warning-soft px-4 py-3 text-sm font-semibold text-warning-on-soft">
          <AlertTriangle size={18} className="shrink-0" />
          <span>{tf(t, 'mobileRequests.banner.text', { n: needsDecisionRows.length })}</span>
          <Button size="sm" variant="outline" className="ms-auto"
                 onClick={() => setFilter('needs_decision')} data-testid="mobile-requests-banner-go">
            {t('mobileRequests.banner.go')}
          </Button>
        </div>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <Segmented
          ariaLabel={t('mobileRequests.title')} value={filter} onChange={setFilter}
          testId="mobile-requests-filter"
          options={[
            { value: 'all', label: t('mobileRequests.filter.all'), badge: String(list.length) },
            { value: 'pending', label: t('mobileRequests.filter.pending'), badge: String(pendingCount) },
            { value: 'accepted', label: t('mobileRequests.filter.accepted'),
             badge: String(list.filter((r) => r.status === 'accepted').length) },
            { value: 'needs_decision', label: t('mobileRequests.filter.needsDecision'),
             badge: String(needsDecisionRows.length), badgeTone: needsDecisionRows.length ? 'partial' : 'empty' },
            { value: 'completed', label: t('mobileRequests.filter.completed'),
             badge: String(list.filter((r) => r.status === 'completed').length) },
            { value: 'closed', label: t('mobileRequests.filter.closed'),
             badge: String(list.filter((r) => r.status === 'rejected' || r.status === 'no_show').length) },
          ]}
        />
        <div className="relative w-52">
          <Search size={15} className="pointer-events-none absolute inset-y-0 start-3 my-auto text-text-muted" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)}
                placeholder={t('mobileRequests.searchPlaceholder')}
                aria-label={t('mobileRequests.searchPlaceholder')} className="ps-9" />
        </div>
      </div>

      {rows === 'loading' ? (
        <EmptyState title={t('mobileRequests.loading')} />
      ) : rows === 'failed' ? (
        <EmptyState title={t('mobileRequests.readFailed.title')} description={t('mobileRequests.readFailed.desc')} />
      ) : filtered.length === 0 ? (
        <EmptyState icon={<Truck size={22} />} title={t('mobileRequests.empty.title')}
                   description={t('mobileRequests.empty.desc')} />
      ) : (
        <div className="flex flex-col gap-2.5">
          {filtered.map((r) => (
            <RequestCard
              key={r.id} r={r} now={now} t={t} locale={locale}
              serviceNames={r.service_ids.map((id) => services.get(id) ?? id)}
              risk={risks.get(r.id)} busy={busyId === r.id}
              canAccept={!!acceptAction} canReject={!!rejectAction}
              canComplete={!!completeAction} canNoShow={!!noShowAction}
              onAccept={() => onAccept(r)} onReject={() => onReject(r)}
              onComplete={() => onComplete(r)} onNoShow={() => onNoShow(r)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function statusBadge(r: MobileServiceRequest, needsDecision: boolean, t: (k: string) => string) {
  if (r.status === 'pending') return <Badge tone="info">{t('mobileRequests.status.pending')}</Badge>;
  if (r.status === 'accepted' && needsDecision) {
    return (
      <Badge tone="warning" className="border border-warning/40">
        <AlertTriangle size={11} /> {t('mobileRequests.status.needsDecision')}
      </Badge>
    );
  }
  if (r.status === 'accepted') return <Badge tone="accent">{t('mobileRequests.status.accepted')}</Badge>;
  if (r.status === 'completed') {
    return <Badge tone="success"><CheckCircle2 size={11} /> {t('mobileRequests.status.completed')}</Badge>;
  }
  if (r.status === 'no_show') {
    return <Badge tone="danger"><XCircle size={11} /> {t('mobileRequests.status.noShow')}</Badge>;
  }
  return <Badge tone="neutral">{t('mobileRequests.status.rejected')}</Badge>;
}

function RequestCard({
  r, now, t, locale, serviceNames, risk, busy,
  canAccept, canReject, canComplete, canNoShow,
  onAccept, onReject, onComplete, onNoShow,
}: {
  r: MobileServiceRequest; now: number; t: (k: string) => string; locale: string;
  serviceNames: string[]; risk: NoShowRisk | undefined; busy: boolean;
  canAccept: boolean; canReject: boolean; canComplete: boolean; canNoShow: boolean;
  onAccept: () => void; onReject: () => void; onComplete: () => void; onNoShow: () => void;
}) {
  const needsDecision = isNeedsDecision(r, now);
  const initial = (r.customer_name || r.phone).trim().charAt(0) || '؟';

  return (
    <div
      data-testid="mobile-request-card"
      className={[
        'flex flex-wrap items-start gap-4 rounded-card border bg-surface-1 p-4 shadow-sm',
        needsDecision ? 'border-warning/40 bg-warning-soft/40' : 'border-border-subtle',
      ].join(' ')}
    >
      <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-info-soft text-base font-bold text-info-on-soft">
        {initial}
      </div>

      <div className="min-w-60 flex-1">
        <div className="mb-1 flex flex-wrap items-center gap-2">
          <span className="text-sm font-bold">{r.customer_name || t('mobileRequests.card.unnamed')}</span>
          <span className="text-xs tabular-nums text-text-tertiary" dir="ltr">{r.phone}</span>
          {statusBadge(r, needsDecision, t)}
        </div>

        <div className="mb-2 flex flex-wrap gap-1.5">
          {serviceNames.map((name, i) => (
            <span key={i} className="rounded-md bg-surface-2 px-2 py-0.5 text-xs font-semibold text-text-secondary">
              {name}
            </span>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 text-xs text-text-secondary">
          <span className="flex items-center gap-1.5">
            <Clock size={13} className="text-text-tertiary" />
            {r.status === 'pending'
              ? tf(t, 'mobileRequests.card.requestedTime', { text: r.requested_time_text || t('mobileRequests.card.noTimeGiven') })
              : formatDate(r.decided_at || r.created, locale)}
          </span>
          <a href={r.maps_url} target="_blank" rel="noreferrer"
            className="flex items-center gap-1.5 font-semibold text-info-on-soft hover:underline">
            <MapPin size={13} />
            {t('mobileRequests.card.openMap')}
          </a>
          {risk?.risky ? (
            <span className="flex items-center gap-1.5 font-semibold text-danger">
              <AlertTriangle size={13} />
              {t('mobileRequests.card.riskyCustomer')}
            </span>
          ) : null}
          {r.reject_reason ? (
            <span className="text-text-tertiary">{tf(t, 'mobileRequests.card.rejectReason', { reason: r.reject_reason })}</span>
          ) : null}
        </div>
      </div>

      <div className="flex min-w-40 flex-col items-stretch gap-1.5">
        {r.status === 'pending' && (canAccept || canReject) ? (
          <div className="flex gap-1.5">
            {canAccept ? (
              <Button size="sm" className="flex-1" disabled={busy} onClick={onAccept}
                     data-testid={`mobile-request-accept-${r.id}`}>
                {t('mobileRequests.action.accept')}
              </Button>
            ) : null}
            {canReject ? (
              <Button size="sm" variant="danger" className="flex-1" disabled={busy} onClick={onReject}
                     data-testid={`mobile-request-reject-${r.id}`}>
                {t('mobileRequests.action.reject')}
              </Button>
            ) : null}
          </div>
        ) : null}

        {r.status === 'accepted' && (canComplete || canNoShow) ? (
          <div className="flex gap-1.5">
            {canComplete ? (
              <Button size="sm" className="flex-1" disabled={busy} onClick={onComplete}
                     data-testid={`mobile-request-complete-${r.id}`}>
                {t('mobileRequests.action.complete')}
              </Button>
            ) : null}
            {canNoShow ? (
              <Button size="sm" variant="ghost" className="flex-1 !bg-danger-soft !text-danger" disabled={busy} onClick={onNoShow}
                     data-testid={`mobile-request-noshow-${r.id}`}>
                {t('mobileRequests.action.noShow')}
              </Button>
            ) : null}
          </div>
        ) : null}

        <span className="text-center text-[11px] text-text-tertiary">
          {relativeTime(r.status === 'pending' ? r.created : (r.decided_at || r.created), now, t)}
        </span>
      </div>
    </div>
  );
}
