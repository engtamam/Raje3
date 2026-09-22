/**
 * «تحالف استراتيجي» (renamed from «كوبونات» — file/route/key names below are unchanged on
 * purpose, only what a shop owner reads is different) — a shop grants ANOTHER registered shop a
 * discount on that shop's own subscription with us, applied automatically at its next renewal.
 * The real build of the approved mockup (docs/mockups/coupons-tab.html): a grant form up top,
 * «السجل»/«الإحصائيات» as real tabs below, and the tier ladder inside stats — no shortcut taken
 * on any of the three.
 *
 * WE ARE THE INTERMEDIARY, ALWAYS — see core/coupons.py's own module docstring. This screen never
 * learns the beneficiary's identity: the phone-check hint and the grant result both carry only
 * what the granter needs to decide what to do next.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Handshake, Store } from 'lucide-react';
import { PageHeader } from '../rj-ui/PageHeader';
import { Card } from '../rj-ui/Card';
import { KpiCard } from '../rj-ui/KpiCard';
import { TabBar } from '../rj-ui/TabBar';
import { Badge } from '../rj-ui/Badge';
import { Button } from '../rj-ui/Button';
import { EmptyState } from '../rj-ui/EmptyState';
import { Table, type TableColumn } from '../rj-ui/Table';
import { FilterMenu } from '../rj-ui/FilterMenu';
import { BarCompare } from '../rj-ui/BarCompare';
import { TierLadder, type TierLadderRung } from '../rj-ui/TierLadder';
import { RangeSlider } from '../rj-ui/RangeSlider';
import { Toggle } from '../rj-ui/Toggle';
import { Field, Input } from '../rj-ui/Field';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';
import { useOperatorI18n, tf } from '../operator-i18n';
import { APP_ROWS } from '../apps';
import './coupons-i18n';

interface CouponAttempt {
  id: string;
  beneficiary_phone_last4: string;
  percent_requested: number;
  scope: string;
  outcome: string;
  created: number;
  per_app: Record<string, string>;
}

interface SallaStatus {
  connected: boolean;
  merchant_id?: string;
  store_name?: string;
}

interface CouponStats {
  grants_this_month: number;
  current_cap_percent: number;
  ceiling_percent: number;
  next_tier_percent: number | null;
  next_tier_grants_needed: number | null;
  history: { month_key: string; grants: number }[];
}

const SCOPE_OPTIONS = APP_ROWS
  .filter((a) => a.key && a.key !== 'feature.partner_loyalty')
  .map((a) => ({ value: a.key as string, label: a.name }));

// A refusal reads as a warning, not a hard failure — the shop simply already got the better
// deal, and nothing was wasted trying. Every other outcome (including `granted`) keeps a plain
// binary read: success or a real, actionable refusal.
const SOFT_OUTCOMES = new Set(['already_has_better_coupon']);

function outcomeTone(outcome: string): 'success' | 'warning' | 'danger' {
  if (outcome === 'granted') return 'success';
  return SOFT_OUTCOMES.has(outcome) ? 'warning' : 'danger';
}

function formatDate(ts: number, locale: string): string {
  return new Date(ts * 1000).toLocaleDateString(locale === 'ar' ? 'ar-SA' : locale, {
    day: 'numeric', month: 'short',
  });
}

function monthLabel(monthKey: string, locale: string): string {
  const [y, m] = monthKey.split('-').map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString(locale === 'ar' ? 'ar-SA' : locale, { month: 'short' });
}

export function CouponsScreen({ session, catalog }: { session: Session; catalog: Catalog }) {
  const { t, locale } = useOperatorI18n();

  // Strong-only gate for the WHOLE PAGE (owner decision, 2026-09-19: two coupon tiers). nav.ts
  // already keeps a weak-tier holder from ever clicking here, but this screen also mounts on a
  // directly-typed URL — and `grantAction` below is no longer a safe proxy for "may see this page"
  // now that `operations.grant_coupon`'s own capability was loosened so the visit-screen shortcut
  // works for weak-tier roles too. `operations.coupons_page` has no route of its own; it exists
  // purely so this screen (and nav.ts) can still require the strong capability.
  const pageAction = action(catalog, 'operations.coupons_page');
  const grantAction = action(catalog, 'operations.grant_coupon');
  const checkAction = action(catalog, 'operations.coupon_check');
  const historyAction = action(catalog, 'operations.coupon_history');
  const statsAction = action(catalog, 'operations.coupon_stats');
  const prefsGetAction = action(catalog, 'operations.coupon_preferences_get');
  const prefsSetAction = action(catalog, 'operations.coupon_preferences_set');
  const sallaInstallAction = action(catalog, 'operations.salla_install');
  const sallaStatusAction = action(catalog, 'operations.salla_status');
  const sallaDisconnectAction = action(catalog, 'operations.salla_disconnect');

  const [tab, setTab] = useState<'log' | 'stats'>('log');

  // ── the grant form ────────────────────────────────────────────────────────────────────────
  const [phone, setPhone] = useState('');
  const [percent, setPercent] = useState(10);
  const [general, setGeneral] = useState(false);
  const [scope, setScope] = useState<string[]>([]);
  const [phoneCheck, setPhoneCheck] = useState<{ registered: boolean; already_granted_this_month: boolean } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null);
  const [stats, setStats] = useState<CouponStats | null | undefined>(undefined);
  const [visitGrantEnabled, setVisitGrantEnabled] = useState<boolean | null>(null);
  const [prefsSaving, setPrefsSaving] = useState(false);

  useEffect(() => {
    if (!statsAction) { setStats(null); return; }
    call<CouponStats>(session, statsAction).then(setStats).catch(() => setStats(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session, catalog, result]);

  useEffect(() => {
    if (!prefsGetAction) return;
    call<{ visit_grant_enabled: boolean }>(session, prefsGetAction)
      .then((x) => setVisitGrantEnabled(x.visit_grant_enabled))
      .catch(() => setVisitGrantEnabled(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session, catalog]);

  async function onTogglePrefs(next: boolean) {
    if (!prefsSetAction || prefsSaving) return;
    setPrefsSaving(true);
    const prev = visitGrantEnabled;
    setVisitGrantEnabled(next);                       // optimistic — a single boolean, cheap to revert
    try {
      await call(session, prefsSetAction, { visit_grant_enabled: next });
    } catch {
      setVisitGrantEnabled(prev);
    } finally {
      setPrefsSaving(false);
    }
  }

  // ── Salla — the connect popup ────────────────────────────────────────────────────────────
  const [sallaStatus, setSallaStatus] = useState<SallaStatus | null | undefined>(undefined);
  const [sallaConnecting, setSallaConnecting] = useState(false);
  const [sallaDisconnecting, setSallaDisconnecting] = useState(false);
  const [sallaError, setSallaError] = useState<string | null>(null);
  const sallaPopupRef = useRef<Window | null>(null);
  const sallaPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refreshSallaStatus = useCallback(() => {
    if (!sallaStatusAction) { setSallaStatus(null); return; }
    call<SallaStatus>(session, sallaStatusAction).then(setSallaStatus).catch(() => setSallaStatus(null));
  }, [session, sallaStatusAction]);

  useEffect(refreshSallaStatus, [refreshSallaStatus]);

  // THE POPUP HANDS ITS RESULT BACK VIA postMessage (api/v1/salla.py's own callback page) —
  // never a token, only {ok, message, store_name}: see that route's own docstring on why the
  // payload is safe to post to '*' (no secret ever leaves the server).
  useEffect(() => {
    function onMessage(e: MessageEvent) {
      const data = e.data as { source?: string; ok?: boolean; message?: string } | null;
      if (!data || data.source !== 'raje3:salla-connect') return;
      setSallaConnecting(false);
      if (sallaPollRef.current) { clearInterval(sallaPollRef.current); sallaPollRef.current = null; }
      if (data.ok) {
        setSallaError(null);
        refreshSallaStatus();
      } else {
        setSallaError(data.message || t('coupons.salla.connectError'));
      }
    }
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [refreshSallaStatus, t]);

  useEffect(() => () => { if (sallaPollRef.current) clearInterval(sallaPollRef.current); }, []);

  async function onConnectSalla() {
    if (!sallaInstallAction || sallaConnecting) return;
    setSallaConnecting(true);
    setSallaError(null);
    try {
      const { url } = await call<{ url: string }>(session, sallaInstallAction);
      const popup = window.open(url, 'salla-connect',
        'width=520,height=720,menubar=no,toolbar=no,status=no');
      if (!popup) {
        // Blocked by the browser — the full-page fallback the callback page itself already
        // supports (no window.opener there, so it just shows a plain readable result).
        window.location.href = url;
        return;
      }
      sallaPopupRef.current = popup;
      // A CLOSED-WITHOUT-FINISHING POPUP MUST NOT LEAVE THE BUTTON STUCK ON "يفتح…" FOR EVER —
      // the owner closing the window by hand (changed his mind, or finished and the auto-close
      // in the callback page raced this check) is the ordinary case, not a fault to report.
      sallaPollRef.current = setInterval(() => {
        if (popup.closed) {
          if (sallaPollRef.current) clearInterval(sallaPollRef.current);
          sallaPollRef.current = null;
          setSallaConnecting(false);
        }
      }, 500);
    } catch {
      setSallaError(t('coupons.salla.connectError'));
      setSallaConnecting(false);
    }
  }

  async function onDisconnectSalla() {
    if (!sallaDisconnectAction || sallaDisconnecting) return;
    // eslint-disable-next-line no-alert -- same window.confirm pattern Services.tsx already uses
    // for a reversible-but-not-trivial action; a full modal is more weight than this needs.
    if (!window.confirm(t('coupons.salla.disconnectConfirm'))) return;
    setSallaDisconnecting(true);
    setSallaError(null);
    try {
      await call(session, sallaDisconnectAction);
      setSallaStatus({ connected: false });
    } catch {
      setSallaError(t('coupons.salla.disconnectError'));
    } finally {
      setSallaDisconnecting(false);
    }
  }

  // THE LIVE HINT — debounced so every keystroke does not fire a request; a Saudi mobile number
  // is 10 digits, so anything shorter is not worth asking about yet.
  useEffect(() => {
    if (!checkAction || phone.trim().length < 9) { setPhoneCheck(null); return; }
    const id = setTimeout(() => {
      call<{ registered: boolean; already_granted_this_month: boolean }>(
        session, checkAction, { phone: phone.trim() },
      ).then(setPhoneCheck).catch(() => setPhoneCheck(null));
    }, 350);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phone, session, catalog]);

  const cap = stats?.current_cap_percent ?? 100;

  async function onGrant() {
    if (!grantAction || submitting || !phone.trim() || percent < 1) return;
    setSubmitting(true); setResult(null);
    try {
      const att = await call<CouponAttempt>(session, grantAction, {
        phone: phone.trim(), percent, general, app_keys: general ? [] : scope,
      });
      if (att.outcome === 'granted') {
        const failedSome = Object.values(att.per_app).some((v) => v !== 'attached' && v !== 'unchanged');
        setResult({ ok: true, text: failedSome ? t('coupons.grant.result.partial') : t('coupons.grant.result.success') });
      } else {
        setResult({ ok: false, text: t(`coupons.outcome.${att.outcome}`) });
      }
      setPhoneCheck(null);
    } catch {
      setResult({ ok: false, text: t('coupons.outcome.billing_unavailable') });
    } finally {
      setSubmitting(false);
    }
  }

  const phoneHint = useMemo(() => {
    if (!phoneCheck) return null;
    if (!phoneCheck.registered) return { tone: 'danger' as const, text: t('coupons.grant.phoneHint.unregistered') };
    if (phoneCheck.already_granted_this_month) return { tone: 'warning' as const, text: t('coupons.grant.phoneHint.already') };
    return { tone: 'success' as const, text: t('coupons.grant.phoneHint.ok') };
  }, [phoneCheck, t]);

  // A weak-tier holder reaching this route directly (nav.ts already never links him here) sees
  // nothing — never a form whose submit would just 403, which would look like a bug rather than
  // a boundary.
  if (!pageAction) return null;

  return (
    <div className="flex flex-col gap-4 p-4">
      <PageHeader
        icon={Handshake}
        title={t('coupons.title')}
        action={stats ? (
          <Badge tone="accent">
            {t('coupons.cap.label')} <b className="tabular-nums">{stats.current_cap_percent}%</b>
          </Badge>
        ) : undefined}
      />
      <p className="-mt-2 text-sm text-text-secondary">{t('coupons.subtitle')}</p>

      {sallaInstallAction ? (
        <Card className="flex flex-col gap-2 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Store size={18} className="text-text-secondary" />
              <div>
                <p className="text-sm font-bold">{t('coupons.salla.title')}</p>
                <p className="text-xs text-text-secondary">{t('coupons.salla.desc')}</p>
              </div>
            </div>
            {sallaStatus?.connected ? (
              <div className="flex items-center gap-2">
                <Badge tone="success" data-testid="salla-connected-badge">{t('coupons.salla.connected')}</Badge>
                {sallaDisconnectAction ? (
                  <Button onClick={onDisconnectSalla} disabled={sallaDisconnecting}
                         variant="ghost" size="sm" data-testid="salla-disconnect-button">
                    {sallaDisconnecting ? t('coupons.salla.disconnecting') : t('coupons.salla.disconnect')}
                  </Button>
                ) : null}
              </div>
            ) : (
              <Button onClick={onConnectSalla} disabled={sallaConnecting} variant="outline"
                     data-testid="salla-connect-button">
                {sallaConnecting ? t('coupons.salla.connecting') : t('coupons.salla.connect')}
              </Button>
            )}
          </div>
          {sallaStatus?.connected ? (
            <p className="text-xs text-text-tertiary">
              {tf(t, 'coupons.salla.connectedTo', {
                name: sallaStatus.store_name || sallaStatus.merchant_id || '',
              })}
            </p>
          ) : null}
          {sallaError ? (
            <p className="text-xs font-semibold text-danger" role="alert">{sallaError}</p>
          ) : null}
        </Card>
      ) : null}

      {prefsSetAction && visitGrantEnabled !== null ? (
        <Card className="flex items-center justify-between gap-3 p-4">
          <div>
            <p className="text-sm font-bold">{t('coupons.prefs.title')}</p>
            <p className="text-xs text-text-secondary">{t('coupons.prefs.desc')}</p>
          </div>
          <Toggle checked={visitGrantEnabled} onChange={onTogglePrefs} disabled={prefsSaving}
                 ariaLabel={t('coupons.prefs.title')} testId="coupon-prefs-toggle" />
        </Card>
      ) : null}

      {/* ── grant form ──────────────────────────────────────────────────────────────────── */}
      {grantAction ? (
        <Card className="flex flex-col gap-4 p-5">
          <p className="text-sm font-bold">{t('coupons.grant.title')}</p>
          <div className="flex flex-wrap items-end gap-4">
            <Field label={t('coupons.grant.phoneLabel')}>
              <Input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)}
                    placeholder={t('coupons.grant.phonePlaceholder')} className="w-44" />
              {phoneHint ? (
                <p className={`mt-1 text-xs font-medium ${
                  phoneHint.tone === 'success' ? 'text-success' :
                  phoneHint.tone === 'warning' ? 'text-warning' : 'text-danger'
                }`}>
                  {phoneHint.text}
                </p>
              ) : null}
            </Field>

            <div className="flex min-w-52 flex-col gap-1.5">
              <div className="flex items-center gap-2">
                <div className="flex-1">
                  <RangeSlider
                    label={t('coupons.grant.percentLabel')} value={percent} min={1} max={cap}
                    onChange={setPercent} valueLabel={`${percent}%`}
                  />
                </div>
                <Input
                  type="number" min={1} max={cap} value={percent}
                  onChange={(e) => {
                    const n = Number(e.target.value);
                    if (!Number.isNaN(n)) setPercent(Math.max(1, Math.min(cap, n)));
                  }}
                  className="w-16 text-center tabular-nums"
                />
              </div>
              <p className="text-xs text-text-tertiary">
                {tf(t, 'coupons.grant.capLine', { p: cap })}
              </p>
            </div>

            <div className="flex min-w-56 flex-col gap-1.5">
              <span className="text-sm text-text-secondary">{t('coupons.grant.scopeLabel')}</span>
              <div className="flex flex-wrap gap-1.5">
                <button type="button" onClick={() => setGeneral((g) => !g)}
                       className={`rounded-full border px-3 py-1 text-xs font-semibold transition-colors ${
                         general ? 'border-accent bg-accent text-white' : 'border-border-subtle bg-surface-2 text-text-secondary'
                       }`}>
                  {t('coupons.grant.scopeAll')}
                </button>
                {!general ? (
                  <FilterMenu label={t('coupons.grant.scopeLabel')} options={SCOPE_OPTIONS}
                             selected={scope} onChange={setScope} />
                ) : null}
              </div>
            </div>

            <Button onClick={onGrant} disabled={submitting || !phone.trim() || (!general && scope.length === 0)}>
              {submitting ? t('coupons.grant.submitting') : t('coupons.grant.submit')}
            </Button>
          </div>

          {result ? (
            <div className={`rounded-lg px-3 py-2 text-sm font-semibold ${
              result.ok ? 'bg-success-soft text-success' : 'bg-danger-soft text-danger'
            }`}>
              {result.text}
            </div>
          ) : null}
        </Card>
      ) : null}

      {/* ── tabs ────────────────────────────────────────────────────────────────────────── */}
      <TabBar
        value={tab} onChange={setTab} ariaLabel={t('coupons.title')}
        options={[
          { value: 'log', label: t('coupons.tab.log') },
          { value: 'stats', label: t('coupons.tab.stats') },
        ]}
      />

      {tab === 'log' ? (
        <LogTab session={session} catalog={catalog} historyAction={historyAction} t={t} locale={locale} />
      ) : (
        <StatsTab stats={stats} t={t} locale={locale} />
      )}
    </div>
  );
}

function LogTab({ session, catalog, historyAction, t, locale }: {
  session: Session; catalog: Catalog; historyAction: ReturnType<typeof action>;
  t: (k: string) => string; locale: string;
}) {
  const [rows, setRows] = useState<CouponAttempt[] | 'loading' | 'failed'>('loading');
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'ok' | 'fail'>('all');

  useEffect(() => {
    if (!historyAction) { setRows('failed'); return; }
    setRows('loading');
    call<{ attempts: CouponAttempt[] }>(session, historyAction, { limit: 200 })
      .then((x) => setRows(x.attempts))
      .catch(() => setRows('failed'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session, catalog]);

  const filtered = Array.isArray(rows)
    ? rows.filter((r) => {
        if (search && !r.beneficiary_phone_last4.includes(search.trim())) return false;
        if (statusFilter === 'ok' && r.outcome !== 'granted') return false;
        if (statusFilter === 'fail' && r.outcome === 'granted') return false;
        return true;
      })
    : rows;

  const columns: TableColumn<CouponAttempt>[] = [
    { key: 'date', header: t('coupons.log.col.date'), render: (r) => formatDate(r.created, locale) },
    { key: 'last4', header: t('coupons.log.col.last4'), render: (r) => `••${r.beneficiary_phone_last4}` },
    { key: 'scope', header: t('coupons.log.col.scope'), render: (r) => r.scope === 'all' ? t('coupons.grant.scopeAll') : r.scope },
    { key: 'percent', header: t('coupons.log.col.percent'), render: (r) => `${r.percent_requested}%`, hideOnCard: true },
    {
      key: 'status', header: t('coupons.log.col.status'),
      render: (r) => <Badge tone={outcomeTone(r.outcome)}>{t(`coupons.outcome.${r.outcome}`)}</Badge>,
    },
  ];

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-2">
        <Input value={search} onChange={(e) => setSearch(e.target.value)}
              placeholder={t('coupons.log.searchPlaceholder')} className="w-40" />
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as typeof statusFilter)}
               className="rounded-lg border border-border-subtle bg-surface-1 px-3 py-2 text-sm">
          <option value="all">{t('coupons.log.filterAll')}</option>
          <option value="ok">{t('coupons.log.filterOk')}</option>
          <option value="fail">{t('coupons.log.filterFail')}</option>
        </select>
      </div>
      <Table
        columns={columns} rows={filtered} getRowId={(r) => r.id}
        emptyTitle={t('coupons.log.empty.title')} emptyDescription={t('coupons.log.empty.desc')}
        failedTitle={t('coupons.log.readFailed')}
      />
    </div>
  );
}

function StatsTab({ stats, t, locale }: {
  stats: CouponStats | null | undefined; t: (k: string) => string; locale: string;
}) {
  if (stats === undefined) return <EmptyState title={t('coupons.readFailed.title')} />;
  if (stats === null) return <EmptyState title={t('coupons.readFailed.title')} description={t('coupons.readFailed.desc')} />;

  // THE LADDER'S OWN RUNGS — every tier percent up to and including the ceiling, `done` for
  // anything at or below the shop's current cap. Built from just `current_cap_percent`/
  // `ceiling_percent` since `stats()` does not (and should not) walk the platform's full tier
  // table for one shop's own screen — see core/coupons.py's own `effective_cap`.
  const rungs: TierLadderRung[] = stats.next_tier_percent
    ? [
        { label: `${stats.current_cap_percent}%`, done: true, current: true },
        { label: `${stats.next_tier_percent}%`, done: false },
        ...(stats.ceiling_percent > stats.next_tier_percent
          ? [{ label: `${stats.ceiling_percent}%`, done: false }] : []),
      ]
    : [{ label: `${stats.current_cap_percent}%`, done: true, current: true }];

  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <KpiCard icon={<Handshake size={18} />} label={t('coupons.stats.kpi.thisMonth')}
                value={stats.grants_this_month} tone="accent" testId="coupon-kpi-month" />
        <KpiCard icon={<Handshake size={18} />} label={t('coupons.stats.kpi.cap')}
                value={`${stats.current_cap_percent}%`} tone="success" testId="coupon-kpi-cap" />
        <KpiCard icon={<Handshake size={18} />} label={t('coupons.stats.kpi.ceiling')}
                value={`${stats.ceiling_percent}%`} tone="neutral" testId="coupon-kpi-ceiling" />
      </div>

      <Card className="p-5">
        <p className="mb-3 text-sm font-bold">{t('coupons.stats.ladder.title')}</p>
        <TierLadder rungs={rungs} testId="coupon-ladder" />
        <p className="mt-3 text-center text-xs text-text-secondary">
          {stats.next_tier_percent
            ? tf(t, 'coupons.stats.ladder.note', {
                n: stats.grants_this_month, left: stats.next_tier_grants_needed ?? 0, p: stats.next_tier_percent,
              })
            : tf(t, 'coupons.stats.ladder.atTop', { n: stats.grants_this_month })}
        </p>
        <p className="mt-2 border-t border-dashed border-border-subtle pt-2 text-center text-xs text-text-tertiary">
          {tf(t, 'coupons.stats.ceilingNote', { p: stats.ceiling_percent })}
        </p>
      </Card>

      <Card className="p-5">
        <p className="mb-3 text-sm font-bold">{t('coupons.stats.chart.title')}</p>
        <BarCompare
          items={stats.history.map((h) => ({ label: monthLabel(h.month_key, locale), value: h.grants }))}
        />
      </Card>
    </div>
  );
}
