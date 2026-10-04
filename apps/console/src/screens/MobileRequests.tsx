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
 * "تحتاج قرار" READS THE REAL APPOINTMENT CLOCK — `requested_time` is a real, validated epoch
 * instant (revised 2026-09-15, the owner's own correction: "الوقت ماهو نص حر الوقت من اوقات عمل
 * المنشاه" — chosen by the customer from the shop's REAL working hours, never free text; see
 * core/mobile_requests.py::validate_requested_time). So «تحتاج قرار» means exactly what it says:
 * an accepted request whose own real moment has passed and still carries no «تم»/«لم يتم» —
 * `NEEDS_DECISION_GRACE_MINUTES` below is only a small buffer so a request due two minutes ago is
 * not nagged before the shop even had a chance to act.
 *
 * «إضافة طلب» (Phase 4, 2026-09-15) IS WHAT MAKES THIS APP STANDALONE — the owner's own decision:
 * a shop with no WhatsApp bot at all can still take a request (a customer called in, or is
 * standing at the counter asking about a mobile visit) by having staff type it in through the
 * same modal, no different in shape from what the bot itself would have sent — same real service
 * catalogue, same real working-hours-validated time, same pasted-Google-Maps-link location
 * (`../googleMapsLink.ts`, already built for a branch's own address — reused here verbatim, not
 * a second parser), and the SAME review queue afterward: a manually-typed request still starts
 * PENDING, never pre-approved just because a human at the shop typed it.
 */
import { useEffect, useMemo, useState } from 'react';
import {
  Truck, MapPin, Clock, AlertTriangle, CheckCircle2, XCircle, Search, CalendarCheck2,
  MessageCircle, Copy, Check, Plus,
} from 'lucide-react';
import { PageHeader } from '../rj-ui/PageHeader';
import { Card } from '../rj-ui/Card';
import { KpiCard } from '../rj-ui/KpiCard';
import { Segmented } from '../rj-ui/Segmented';
import { Badge } from '../rj-ui/Badge';
import { Button } from '../rj-ui/Button';
import { EmptyState } from '../rj-ui/EmptyState';
import { Modal } from '../rj-ui/Modal';
import { Field, Input, Select } from '../rj-ui/Field';
import { FilterMenu } from '../rj-ui/FilterMenu';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';
import { useOperatorI18n, tf } from '../operator-i18n';
import { parseGoogleMapsLink, isShortGoogleMapsLink } from '../googleMapsLink';
import './mobile-requests-i18n';

interface MobileServiceRequest {
  id: string;
  tenant: string;
  phone: string;
  customer_name: string;
  service_ids: string[];
  requested_time: number;
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
  assigned_to: string;
}

interface StaffMember { id: string; name: string; active?: boolean }

interface NoShowRisk {
  considered: number;
  no_shows: number;
  risky: boolean;
  threshold_percent: number;
}

interface ServiceRow { id: string; name: string }

type Filter = 'all' | 'pending' | 'accepted' | 'needs_decision' | 'completed' | 'closed';

// See this file's own module docstring — `requested_time` is now the real appointment moment, so
// this reads the real clock. A short grace window (not zero) so a request due two minutes ago is
// not immediately flagged before the shop had a real chance to act on it.
const NEEDS_DECISION_GRACE_MINUTES = 30;
const NEEDS_DECISION_GRACE_SECONDS = NEEDS_DECISION_GRACE_MINUTES * 60;

function isNeedsDecision(r: MobileServiceRequest, nowSeconds: number): boolean {
  return r.status === 'accepted' && nowSeconds - r.requested_time > NEEDS_DECISION_GRACE_SECONDS;
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

// `r.phone` is always canonical_phone's own "+<digits>" shape (services/operations/app/core/
// signup.py) — wa.me wants the digits alone, no leading "+".
function whatsappLink(phone: string): string {
  return `https://wa.me/${phone.replace(/[^\d]/g, '')}`;
}

/** Same «نسخ بضغطة» pattern as src/affiliates/AffiliateTools.tsx's own CopyButton — a plain icon
 *  button that flips to a checkmark for two seconds, no separate library. */
function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button type="button" aria-label={label} title={label}
           className="rounded-md p-1 text-text-tertiary transition-colors hover:bg-surface-2 hover:text-text-primary"
           onClick={() => {
             navigator.clipboard?.writeText(text).then(() => {
               setCopied(true);
               setTimeout(() => setCopied(false), 2000);
             }).catch(() => {});
           }}>
      {copied ? <Check size={13} className="text-success" /> : <Copy size={13} />}
    </button>
  );
}

/**
 * ONE SENTENCE FOR EVERY ACTION FAILURE ON THIS SCREEN — same "the server's own real reason,
 * never a blank failure" convention Customer.tsx's own save/offer handlers already hold to.
 *
 * A 403 HERE IS ALMOST ALWAYS `OUTSIDE_YOUR_BRANCH` (services/operations/app/api/v1/
 * mobile_requests.py's own `_require_branch_access`/branch checks in `assign_mobile_request` and
 * `create_mobile_request`) — but the SERVER'S OWN SENTENCE never reaches here: `api/errors.py`
 * strips every `HTTPException` detail on the way out (CWE-209), so `call()`'s own `err.message`
 * falls back to a bare `METHOD path → 403`. Rather than show that, this screen names the one real
 * reason a manager reading it actually needs — the request moved (or the operator he tried to
 * assign works) outside the branch he can see. Any OTHER status keeps the server's own sentence
 * when one arrived (`err.message`), same as every other screen in this console.
 */
function actionErrorMessage(e: unknown, t: (k: string) => string): string {
  const status = e instanceof Error ? (e as Error & { status?: number }).status : undefined;
  if (status === 403) return t('mobileRequests.action.outsideBranch');
  return e instanceof Error && e.message ? e.message : t('mobileRequests.action.genericError');
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
  const createAction = action(catalog, 'operations.mobile_request_create');
  const acceptAction = action(catalog, 'operations.mobile_request_accept');
  const rejectAction = action(catalog, 'operations.mobile_request_reject');
  const completeAction = action(catalog, 'operations.mobile_request_complete');
  const noShowAction = action(catalog, 'operations.mobile_request_no_show');
  const riskAction = action(catalog, 'operations.mobile_request_risk');
  const assignAction = action(catalog, 'operations.mobile_request_assign');
  const servicesAction = action(catalog, 'operations.manage_services') ?? action(catalog, 'operations.list_services');
  const operatorsAction = action(catalog, 'operations.list_operators');

  const [rows, setRows] = useState<MobileServiceRequest[] | 'loading' | 'failed'>('loading');
  const [services, setServices] = useState<Map<string, string>>(new Map());
  const [operators, setOperators] = useState<StaffMember[]>([]);
  const [risks, setRisks] = useState<Map<string, NoShowRisk>>(new Map());
  const [filter, setFilter] = useState<Filter>('all');
  const [search, setSearch] = useState('');
  const [busyId, setBusyId] = useState<string | null>(null);
  const [now, setNow] = useState(() => Math.floor(Date.now() / 1000));
  const [addOpen, setAddOpen] = useState(false);
  // A REAL SENTENCE FOR A REFUSED ACTION — see `actionErrorMessage`'s own docstring. Cleared on
  // the next attempt and self-clearing after a few seconds, same "confirmation that clears itself"
  // pattern Customer.tsx's own `namingMsg` already uses, so a stale refusal never lingers over a
  // screen that keeps changing under it.
  const [actionError, setActionError] = useState('');

  function reportActionError(e: unknown) {
    setActionError(actionErrorMessage(e, t));
    window.setTimeout(() => setActionError(''), 5000);
  }

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

  // OPERATORS, ONLY FOR WHOEVER CAN ASSIGN — absent entirely for a plain field operator's own
  // scoped view (operatorsAction/assignAction are both null for them, so this simply never
  // fires; see RequestCard's own `canAssign` gate below).
  useEffect(() => {
    if (!operatorsAction || !assignAction) return;
    call<{ operators: StaffMember[] }>(session, operatorsAction)
      .then((x) => setOperators(x.operators.filter((o) => o.active !== false)))
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

  // HOW MANY OPEN REQUESTS EACH OPERATOR CURRENTLY CARRIES — pending + accepted only (a closed
  // request is no longer "load" on anyone), computed here from the same list already on screen
  // rather than a second read, so the count the manager sees while choosing who to assign next
  // is never stale relative to the cards themselves.
  const assignedCounts = useMemo(() => {
    const m = new Map<string, number>();
    for (const r of list) {
      if (!r.assigned_to) continue;
      if (r.status !== 'pending' && r.status !== 'accepted') continue;
      m.set(r.assigned_to, (m.get(r.assigned_to) ?? 0) + 1);
    }
    return m;
  }, [list]);

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
    setActionError('');
    try {
      await call(session, acceptAction, { request_id: r.id });
      load();
    } catch (e) {
      reportActionError(e);
    } finally { setBusyId(null); }
  }

  async function onReject(r: MobileServiceRequest) {
    if (!rejectAction || busyId) return;
    // eslint-disable-next-line no-alert -- same lightweight prompt Coupons.tsx's own disconnect
    // confirm uses; a full modal is more weight than an optional one-line reason needs.
    const reason = window.prompt(t('mobileRequests.reject.reasonPrompt')) ?? '';
    setBusyId(r.id);
    setActionError('');
    try {
      await call(session, rejectAction, { request_id: r.id, reason: reason.trim() });
      load();
    } catch (e) {
      reportActionError(e);
    } finally { setBusyId(null); }
  }

  async function onComplete(r: MobileServiceRequest) {
    if (!completeAction || busyId) return;
    setBusyId(r.id);
    setActionError('');
    try {
      await call(session, completeAction, { request_id: r.id });
      load();
    } catch (e) {
      reportActionError(e);
    } finally { setBusyId(null); }
  }

  async function onNoShow(r: MobileServiceRequest) {
    if (!noShowAction || busyId) return;
    setBusyId(r.id);
    setActionError('');
    try {
      await call(session, noShowAction, { request_id: r.id });
      load();
    } catch (e) {
      reportActionError(e);
    } finally { setBusyId(null); }
  }

  async function onAssign(r: MobileServiceRequest, operatorId: string) {
    if (!assignAction || busyId) return;
    setBusyId(r.id);
    setActionError('');
    try {
      await call(session, assignAction, { request_id: r.id, operator_id: operatorId });
      load();
    } catch (e) {
      reportActionError(e);
    } finally { setBusyId(null); }
  }

  async function onCreate(payload: {
    phone: string; customer_name: string; service_ids: string[]; requested_time: number;
    lat: number; lng: number; operator_id: string;
  }) {
    if (!createAction) throw new Error('no create action');
    await call(session, createAction, payload);
    load();
  }

  return (
    <div className="flex flex-col gap-4 p-4">
      <PageHeader icon={Truck} title={t('mobileRequests.title')}
                 action={createAction ? (
                   <Button size="sm" onClick={() => setAddOpen(true)} data-testid="mobile-request-add-open">
                     <Plus size={15} /> {t('mobileRequests.add.open')}
                   </Button>
                 ) : undefined} />
      <p className="-mt-2 text-sm text-text-secondary">{t('mobileRequests.subtitle')}</p>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <KpiCard icon={<Clock size={18} />} label={t('mobileRequests.kpi.pending')}
                value={pendingCount} tone="info" testId="mobile-requests-kpi-pending" />
        <KpiCard icon={<AlertTriangle size={18} />} label={t('mobileRequests.kpi.needsDecision')}
                value={needsDecisionRows.length} tone="warning" testId="mobile-requests-kpi-needs-decision" />
        <KpiCard icon={<CalendarCheck2 size={18} />} label={t('mobileRequests.kpi.completedThisMonth')}
                value={completedThisMonth} tone="success" testId="mobile-requests-kpi-completed" />
      </div>

      {actionError ? (
        <p role="alert" className="rounded-card border border-danger/30 bg-danger-soft px-4 py-2 text-sm font-semibold text-danger">
          {actionError}
        </p>
      ) : null}

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
              canAssign={!!assignAction} operators={operators} assignedCounts={assignedCounts}
              onAccept={() => onAccept(r)} onReject={() => onReject(r)}
              onComplete={() => onComplete(r)} onNoShow={() => onNoShow(r)}
              onAssign={(operatorId) => onAssign(r, operatorId)}
            />
          ))}
        </div>
      )}

      {addOpen ? (
        <AddRequestModal
          onClose={() => setAddOpen(false)}
          services={Array.from(services.entries()).map(([id, name]) => ({ id, name }))}
          operators={operators} assignedCounts={assignedCounts}
          t={t} onSubmit={onCreate}
        />
      ) : null}
    </div>
  );
}

// A REAL RIYADH-LOCAL INSTANT, REGARDLESS OF THE BROWSER'S OWN TIMEZONE — the fixed +03:00
// offset services/operations/app/core/riyadh.py already uses (Saudi Arabia observes no DST, so a
// literal offset is the whole truth, never an approximation). `day`/`time` are the raw
// <input type="date">/<input type="time"> values (YYYY-MM-DD / HH:MM).
function riyadhEpoch(day: string, time: string): number | null {
  if (!day || !time) return null;
  const ms = new Date(`${day}T${time}:00+03:00`).getTime();
  return Number.isFinite(ms) ? Math.floor(ms / 1000) : null;
}

function AddRequestModal({
  onClose, services, operators, assignedCounts, t, onSubmit,
}: {
  onClose: () => void;
  services: ServiceRow[]; operators: StaffMember[]; assignedCounts: Map<string, number>;
  t: (k: string) => string;
  onSubmit: (payload: {
    phone: string; customer_name: string; service_ids: string[]; requested_time: number;
    lat: number; lng: number; operator_id: string;
  }) => Promise<void>;
}) {
  const [phone, setPhone] = useState('');
  const [customerName, setCustomerName] = useState('');
  const [serviceIds, setServiceIds] = useState<string[]>([]);
  const [day, setDay] = useState('');
  const [time, setTime] = useState('');
  const [mapsLink, setMapsLink] = useState('');
  const [operatorId, setOperatorId] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const location = mapsLink.trim() ? parseGoogleMapsLink(mapsLink) : null;
  const mapsError = mapsLink.trim() && !location
    ? (isShortGoogleMapsLink(mapsLink) ? t('mobileRequests.add.mapsLinkShort') : t('mobileRequests.add.mapsLinkInvalid'))
    : '';
  const requestedTime = riyadhEpoch(day, time);

  const canSubmit = !!phone.trim() && serviceIds.length > 0 && !!requestedTime && !!location && !submitting;

  async function submit() {
    if (!canSubmit || !location || !requestedTime) return;
    setSubmitting(true);
    setError('');
    try {
      await onSubmit({
        phone: phone.trim(), customer_name: customerName.trim(), service_ids: serviceIds,
        requested_time: requestedTime, lat: location.lat, lng: location.lng,
        operator_id: operatorId,
      });
      onClose();
    } catch (e) {
      // SAME REAL-SENTENCE RULE AS EVERY ACTION ON THIS SCREEN — a manager assigning outside
      // their own branch at creation time (`create_mobile_request`'s own check) gets the same
      // clear sentence `onAssign` shows, not a bare `POST ... → 403`.
      const status = e instanceof Error ? (e as Error & { status?: number }).status : undefined;
      setError(status === 403 ? t('mobileRequests.action.outsideBranch')
              : (e instanceof Error && e.message ? e.message : t('mobileRequests.add.error')));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal open onClose={onClose} title={t('mobileRequests.add.title')}
          footer={(
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={onClose}>{t('mobileRequests.add.cancel')}</Button>
              <Button onClick={submit} disabled={!canSubmit} data-testid="mobile-request-add-submit">
                {submitting ? t('mobileRequests.add.submitting') : t('mobileRequests.add.submit')}
              </Button>
            </div>
          )}>
      <div className="flex flex-col gap-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label={t('mobileRequests.add.phoneLabel')} required htmlFor="mreq-add-phone">
            <Input id="mreq-add-phone" type="tel" dir="ltr" value={phone}
                  onChange={(e) => setPhone(e.target.value)} placeholder="05xxxxxxxx" />
          </Field>
          <Field label={t('mobileRequests.add.nameLabel')} htmlFor="mreq-add-name">
            <Input id="mreq-add-name" value={customerName}
                  onChange={(e) => setCustomerName(e.target.value)} />
          </Field>
        </div>

        <Field label={t('mobileRequests.add.servicesLabel')} required>
          <FilterMenu label={t('mobileRequests.add.servicesLabel')}
                     options={services.map((s) => ({ value: s.id, label: s.name }))}
                     selected={serviceIds} onChange={setServiceIds} />
        </Field>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label={t('mobileRequests.add.dayLabel')} required htmlFor="mreq-add-day">
            <Input id="mreq-add-day" type="date" dir="ltr" value={day}
                  onChange={(e) => setDay(e.target.value)} />
          </Field>
          <Field label={t('mobileRequests.add.timeLabel')} required htmlFor="mreq-add-time">
            <Input id="mreq-add-time" type="time" dir="ltr" value={time}
                  onChange={(e) => setTime(e.target.value)} />
          </Field>
        </div>

        <Field label={t('mobileRequests.add.mapsLinkLabel')} required htmlFor="mreq-add-maps"
              error={mapsError || undefined} hint={!mapsError ? t('mobileRequests.add.mapsLinkHint') : undefined}>
          <Input id="mreq-add-maps" dir="ltr" value={mapsLink}
                onChange={(e) => setMapsLink(e.target.value)}
                placeholder="https://maps.google.com/..." />
        </Field>

        {operators.length > 0 ? (
          <Field label={t('mobileRequests.add.assignLabel')} htmlFor="mreq-add-assign">
            <Select id="mreq-add-assign" value={operatorId} onChange={(e) => setOperatorId(e.target.value)}>
              <option value="">{t('mobileRequests.card.assignUnassigned')}</option>
              {operators.map((op) => (
                <option key={op.id} value={op.id}>
                  {op.name}{assignedCounts.has(op.id) ? ` (${assignedCounts.get(op.id)})` : ''}
                </option>
              ))}
            </Select>
          </Field>
        ) : null}

        {error ? <p className="text-sm font-semibold text-danger" role="alert">{error}</p> : null}
      </div>
    </Modal>
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
  canAssign, operators, assignedCounts,
  onAccept, onReject, onComplete, onNoShow, onAssign,
}: {
  r: MobileServiceRequest; now: number; t: (k: string) => string; locale: string;
  serviceNames: string[]; risk: NoShowRisk | undefined; busy: boolean;
  canAccept: boolean; canReject: boolean; canComplete: boolean; canNoShow: boolean;
  canAssign: boolean; operators: StaffMember[]; assignedCounts: Map<string, number>;
  onAccept: () => void; onReject: () => void; onComplete: () => void; onNoShow: () => void;
  onAssign: (operatorId: string) => void;
}) {
  const needsDecision = isNeedsDecision(r, now);
  const initial = (r.customer_name || r.phone).trim().charAt(0) || t('mobileRequests.unknownInitial');

  return (
    <Card
      data-testid="mobile-request-card"
      className={[
        'flex flex-wrap items-start gap-4 p-4',
        needsDecision ? 'border-warning/40 bg-warning-soft/40' : '',
      ].join(' ')}
    >
      <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-info-soft text-base font-bold text-info-on-soft">
        {initial}
      </div>

      <div className="min-w-60 flex-1">
        <div className="mb-1 flex flex-wrap items-center gap-2">
          <span className="text-sm font-bold">{r.customer_name || t('mobileRequests.card.unnamed')}</span>
          <span className="flex items-center gap-1 text-xs tabular-nums text-text-tertiary">
            <a href={whatsappLink(r.phone)} target="_blank" rel="noreferrer" dir="ltr"
              title={t('mobileRequests.card.openWhatsapp')}
              className="flex items-center gap-1 text-info-on-soft hover:underline">
              <MessageCircle size={12} />
              {r.phone}
            </a>
            <CopyButton text={r.phone} label={t('mobileRequests.card.copyPhone')} />
          </span>
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
            {tf(t, 'mobileRequests.card.requestedTime', { time: formatDate(r.requested_time, locale) })}
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

        {canAssign && (r.status === 'pending' || r.status === 'accepted') ? (
          <div className="mt-2 flex items-center gap-2">
            <span className="text-xs font-semibold text-text-secondary">{t('mobileRequests.card.assignLabel')}</span>
            <Select value={r.assigned_to} disabled={busy} className="!w-auto py-1 text-xs"
                   aria-label={t('mobileRequests.card.assignLabel')}
                   data-testid={`mobile-request-assign-${r.id}`}
                   onChange={(e) => onAssign(e.target.value)}>
              <option value="">{t('mobileRequests.card.assignUnassigned')}</option>
              {operators.map((op) => (
                <option key={op.id} value={op.id}>
                  {op.name}{assignedCounts.has(op.id) ? ` (${assignedCounts.get(op.id)})` : ''}
                </option>
              ))}
            </Select>
          </div>
        ) : null}
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
    </Card>
  );
}
