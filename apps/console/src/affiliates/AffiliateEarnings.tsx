/**
 * «أرباحي» (2026-08-22) — the fifth and final screen, built on this session's own research into
 * gig-app earnings screens (Uber Driver/DoorDash/Instacart: one hero number, a reconciling
 * breakdown, a docked cash-out CTA, a terse transaction list with detail-on-tap) plus a full
 * backend inventory of `core/payouts.py` + `core/wafa.py`'s self-service routes.
 *
 * THE ONE NUMBER THAT MATTERS FIRST, ALWAYS VISIBLE, NEVER AMBIGUOUS — the research's own anti-
 * pattern warning: DoorDash's withheld tip/base split was rated a trust problem specifically
 * because the number a worker cares about was hidden. `confirmed_available_halalas` is the hero;
 * pending/withdrawn are a breakdown UNDER it, never competing with it for attention.
 *
 * A DIFFERENT KIND OF MONEY GETS ITS OWN CARD — «دعم الوفاء» is a stipend-eligibility PROGRAM, not
 * a commission, so it never merges into the ledger (research's own point 5): its own module, own
 * accent, "now and next" framing (current tier, progress, benefit).
 *
 * EMPTY-STATE-FIRST, CHECKED AGAINST THE LIVE SERVER: zero commissions, zero withdrawals exist in
 * production today — the hero must render an honest "٠ ر.س" plus a path forward, never a screen
 * that looks broken because nothing has happened yet.
 */
import { useEffect, useState } from 'react';
import { Wallet, TrendingUp, FileText, Users, CheckCircle2, XCircle } from 'lucide-react';
import { Button } from '@base-ui/design-system/Button';
import { Badge } from '@base-ui/design-system/Badge';
import { EmptyState } from '@base-ui/design-system/EmptyState';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import { riyalsLabel } from '../money';
import {
  AffiliateRefused, me, balance, commissions, requestWithdrawal, myWithdrawals,
  withdrawalReceiptUrl, team, wafaEligibility, requestWafa, myWafaRequests, teamWafaRequests,
  decideTeamWafaRequest,
  type AffiliateSession, type Me, type Balance, type Commission, type WithdrawalRequest,
  type Team, type WafaRequest,
} from './api';

const COMMISSION_STATUS_LABEL: Record<string, string> = {
  pending: 'قيد المراجعة', confirmed: 'مؤكَّدة', voided: 'مُلغاة',
};
const WITHDRAWAL_STATUS_LABEL: Record<string, string> = {
  requested: 'قيد المعالجة', completed: 'تم الدفع', rejected: 'مرفوض',
};
const WAFA_STATUS_LABEL: Record<string, string> = {
  requested: 'قيد المراجعة', granted: 'مُستحَق', rejected: 'مرفوض',
};

export function AffiliateEarnings({ session }: { session: AffiliateSession }) {
  const [who, setWho] = useState<Me | 'loading'>('loading');

  useEffect(() => {
    let cancelled = false;
    me(session).then((m) => { if (!cancelled) setWho(m); }).catch(() => {});
    return () => { cancelled = true; };
  }, [session]);

  if (who === 'loading') {
    return <div className="flex flex-col gap-4 p-6"><h1 className="text-2xl">أرباحي</h1><Skeleton height={400} /></div>;
  }
  const isManager = who.role === 'affiliate_manager';

  return (
    <div className="flex flex-col gap-5 p-6">
      <h1 className="text-2xl leading-tight tracking-tight">أرباحي</h1>
      <BalanceSection session={session} />
      <WafaCard session={session} />
      {isManager ? <TeamEarningsCard session={session} /> : null}
      {isManager ? <TeamWafaQueue session={session} /> : null}
      <CommissionHistory session={session} />
      <WithdrawalHistory session={session} />
    </div>
  );
}

/* ── الرصيد وطلب السحب ─────────────────────────────────────────────────────────────────────────── */
function BalanceSection({ session }: { session: AffiliateSession }) {
  const [data, setData] = useState<Balance | 'loading' | 'failed'>('loading');
  const [openRequest, setOpenRequest] = useState<WithdrawalRequest | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const load = () => {
    setData('loading');
    balance(session).then(setData).catch(() => setData('failed'));
    myWithdrawals(session).then((r) => {
      setOpenRequest(r.withdrawals.find((w) => w.status === 'requested') ?? null);
    }).catch(() => {});
  };
  useEffect(load, [session]);

  async function withdraw() {
    setBusy(true); setError('');
    try { await requestWithdrawal(session); load(); }
    catch (err) { setError(err instanceof AffiliateRefused ? err.message : 'تعذّر إرسال طلب السحب.'); }
    finally { setBusy(false); }
  }

  if (data === 'loading') return <Skeleton height={180} />;
  if (data === 'failed') return <EmptyState title="تعذّرت قراءة رصيدك" />;

  return (
    <div className="flex flex-col gap-4 rounded-card bg-surface-1 p-5 shadow-sm">
      <span className="text-label font-medium text-text-secondary">رصيدك الجاهز للسحب</span>
      <span className="text-4xl font-semibold leading-none tracking-tight tabular-nums">
        {riyalsLabel(data.confirmed_available_halalas)}
      </span>

      <div className="flex gap-2">
        <div className="flex-1 rounded-md bg-surface-0 p-2.5">
          <span className="block text-xs text-text-secondary">قيد المراجعة</span>
          <span className="tabular-nums font-medium">{riyalsLabel(data.pending_halalas)}</span>
        </div>
        <div className="flex-1 rounded-md bg-surface-0 p-2.5">
          <span className="block text-xs text-text-secondary">تم سحبه سابقًا</span>
          <span className="tabular-nums font-medium">{riyalsLabel(data.withdrawn_halalas)}</span>
        </div>
      </div>

      {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}

      {openRequest ? (
        <div className="flex items-center justify-between rounded-md bg-accent-soft px-3 py-2.5 text-sm text-accent-on-soft">
          <span>طلب سحبك بقيمة {riyalsLabel(openRequest.amount_halalas)} قيد المعالجة</span>
        </div>
      ) : (
        <Button type="button" disabled={busy || data.confirmed_available_halalas <= 0}
               onClick={withdraw} className="flex items-center justify-center gap-2">
          <Wallet size={16} /> اسحب أرباحك
        </Button>
      )}
    </div>
  );
}

/* ── دعم الوفاء — بطاقة منفصلة تمامًا عن سجل العمولات ────────────────────────────────────────────── */
function WafaCard({ session }: { session: AffiliateSession }) {
  const [elig, setElig] = useState<Awaited<ReturnType<typeof wafaEligibility>> | 'loading'>('loading');
  const [requests, setRequests] = useState<WafaRequest[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const load = () => {
    wafaEligibility(session).then(setElig).catch(() => {});
    myWafaRequests(session).then((r) => setRequests(r.wafa_requests)).catch(() => {});
  };
  useEffect(load, [session]);

  if (elig === 'loading') return <Skeleton height={90} />;

  const hasOpenRequest = requests.some((r) => r.status === 'requested');
  const pct = Math.min(100, Math.round((elig.active_shops % elig.tier_shops
    || (elig.eligible ? elig.tier_shops : 0)) / elig.tier_shops * 100));

  async function request() {
    setBusy(true); setError('');
    try { await requestWafa(session); load(); }
    catch (err) { setError(err instanceof AffiliateRefused ? err.message : 'تعذّر إرسال الطلب.'); }
    finally { setBusy(false); }
  }

  return (
    <div className="flex flex-col gap-3 rounded-card border border-accent/30 bg-accent-soft/40 p-4 shadow-sm">
      <div className="flex items-center gap-2 text-sm font-medium text-accent-on-soft">
        <TrendingUp size={16} /> برنامج دعم الوفاء
      </div>
      <div className="flex justify-between text-xs text-text-secondary">
        <span>محلات نشِطة</span>
        <span className="tabular-nums">{elig.active_shops} / {elig.tier_shops}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-surface-0">
        <div className="h-full rounded-full bg-accent" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-sm">
        {elig.eligible ? `تستحق ${riyalsLabel(elig.current_tier_amount_halalas)} شهريًا الآن`
                       : `${elig.shops_until_next_tier} محل يفتح لك الاستحقاق`}
      </span>
      {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
      {elig.eligible && !hasOpenRequest ? (
        <Button type="button" disabled={busy} onClick={request}>اطلب الاستحقاق</Button>
      ) : hasOpenRequest ? (
        <span className="text-xs text-text-secondary">طلبك الحالي قيد المراجعة.</span>
      ) : null}
    </div>
  );
}

/* ── ملخص أرباح الفريق — مدير فقط ─────────────────────────────────────────────────────────────── */
function TeamEarningsCard({ session }: { session: AffiliateSession }) {
  const [data, setData] = useState<Team | 'loading' | 'failed'>('loading');

  useEffect(() => {
    team(session).then(setData).catch(() => setData('failed'));
  }, [session]);

  if (data === 'loading') return <Skeleton height={140} />;
  if (data === 'failed') return null;

  return (
    <div className="flex flex-col gap-3 rounded-card bg-surface-1 p-4 shadow-sm">
      <div className="flex items-center gap-2 text-sm font-medium text-text-secondary">
        <Users size={16} /> أرباح فريقك
      </div>
      <div className="flex gap-2">
        <div className="flex-1 rounded-md bg-surface-0 p-2.5">
          <span className="block text-xs text-text-secondary">مؤكَّد</span>
          <span className="tabular-nums font-medium">{riyalsLabel(data.team_confirmed_halalas)}</span>
        </div>
        <div className="flex-1 rounded-md bg-surface-0 p-2.5">
          <span className="block text-xs text-text-secondary">قيد المراجعة</span>
          <span className="tabular-nums font-medium">{riyalsLabel(data.team_pending_halalas)}</span>
        </div>
      </div>
      {data.members.length === 0 ? (
        <p className="text-sm text-text-secondary">لا أعضاء بفريقك بعد.</p>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {data.members.map((m) => (
            <li key={m.id} className="flex items-center justify-between text-sm">
              <span>{m.name}</span>
              <span className="tabular-nums text-text-secondary">
                {riyalsLabel(m.confirmed_halalas)} — {m.shops} محل
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function TeamWafaQueue({ session }: { session: AffiliateSession }) {
  const [rows, setRows] = useState<WafaRequest[] | 'loading'>('loading');
  const [busy, setBusy] = useState<string | null>(null);

  const load = () => { teamWafaRequests(session).then((r) => setRows(r.wafa_requests)).catch(() => setRows([])); };
  useEffect(load, [session]);

  if (rows === 'loading') return <Skeleton height={60} />;
  if (rows.length === 0) return null;

  async function decide(id: string, decision: 'approve' | 'reject') {
    setBusy(id);
    try { await decideTeamWafaRequest(session, id, decision); } catch { /* row stays as-is */ }
    finally { setBusy(null); load(); }
  }

  return (
    <div className="flex flex-col gap-3 rounded-card bg-surface-1 p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-text-secondary">طلبات دعم الوفاء بانتظارك</span>
        <Badge tone="warning">{rows.length}</Badge>
      </div>
      <ul className="flex flex-col gap-2">
        {rows.map((r) => (
          <li key={r.id} className="flex items-center justify-between gap-2 rounded-md bg-surface-0 px-3 py-2 text-sm">
            <span>{r.active_shops} محل — {riyalsLabel(r.tier_amount_halalas)}</span>
            <div className="flex gap-1">
              <Button type="button" variant="ghost" size="icon" aria-label="موافقة" disabled={busy === r.id}
                     onClick={() => decide(r.id, 'approve')}>
                <CheckCircle2 size={16} className="text-success" />
              </Button>
              <Button type="button" variant="ghost" size="icon" aria-label="رفض" disabled={busy === r.id}
                     onClick={() => decide(r.id, 'reject')}>
                <XCircle size={16} className="text-danger" />
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* ── سجل العمولات ─────────────────────────────────────────────────────────────────────────────── */
function CommissionHistory({ session }: { session: AffiliateSession }) {
  const [rows, setRows] = useState<Commission[] | 'loading' | 'failed'>('loading');

  useEffect(() => {
    commissions(session).then((r) => setRows(r.commissions)).catch(() => setRows('failed'));
  }, [session]);

  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-sm font-medium text-text-secondary">سجل العمولات</h2>
      {rows === 'loading' ? <Skeleton height={120} /> : rows === 'failed' ? (
        <EmptyState title="تعذّرت القراءة" />
      ) : rows.length === 0 ? (
        <EmptyState title="لا عمولات بعد" description="أول عمولة على بعد خطوة — شارك رابطك أو تابع عملاءك المحتملين." />
      ) : (
        <ul className="flex flex-col gap-2">
          {rows
            .slice()
            .sort((a, b) => b.created_at - a.created_at)
            .map((c) => (
              <li key={c.id} className="flex items-center justify-between rounded-card bg-surface-1 px-4 py-3 text-sm shadow-sm">
                <span className="tabular-nums font-medium">{riyalsLabel(c.amount_halalas)}</span>
                <Badge tone={c.status === 'confirmed' ? 'success' : c.status === 'voided' ? 'danger' : 'neutral'}>
                  {COMMISSION_STATUS_LABEL[c.status] ?? c.status}
                </Badge>
              </li>
            ))}
        </ul>
      )}
    </div>
  );
}

/* ── سجل السحوبات + الإيصالات ─────────────────────────────────────────────────────────────────── */
function WithdrawalHistory({ session }: { session: AffiliateSession }) {
  const [rows, setRows] = useState<WithdrawalRequest[] | 'loading' | 'failed'>('loading');

  useEffect(() => {
    myWithdrawals(session).then((r) => setRows(r.withdrawals)).catch(() => setRows('failed'));
  }, [session]);

  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-sm font-medium text-text-secondary">سجل السحوبات</h2>
      {rows === 'loading' ? <Skeleton height={100} /> : rows === 'failed' ? (
        <EmptyState title="تعذّرت القراءة" />
      ) : rows.length === 0 ? (
        <EmptyState title="لا طلبات سحب بعد" />
      ) : (
        <ul className="flex flex-col gap-2">
          {rows.map((w) => <WithdrawalRow key={w.id} session={session} withdrawal={w} />)}
        </ul>
      )}
    </div>
  );
}

function WithdrawalRow({ session, withdrawal }: { session: AffiliateSession; withdrawal: WithdrawalRequest }) {
  const [opening, setOpening] = useState(false);

  async function openReceipt() {
    setOpening(true);
    try { window.open(await withdrawalReceiptUrl(session, withdrawal.id), '_blank', 'noreferrer'); }
    catch { /* no receipt uploaded yet */ }
    finally { setOpening(false); }
  }

  return (
    <li className="flex items-center justify-between rounded-card bg-surface-1 px-4 py-3 text-sm shadow-sm">
      <span className="tabular-nums font-medium">{riyalsLabel(withdrawal.amount_halalas)}</span>
      <div className="flex items-center gap-2">
        <Badge tone={withdrawal.status === 'completed' ? 'success'
                    : withdrawal.status === 'rejected' ? 'danger' : 'neutral'}>
          {WITHDRAWAL_STATUS_LABEL[withdrawal.status] ?? withdrawal.status}
        </Badge>
        {withdrawal.status === 'completed' ? (
          <Button type="button" variant="ghost" size="icon" aria-label="عرض الإيصال"
                 disabled={opening} onClick={openReceipt}>
            <FileText size={16} />
          </Button>
        ) : null}
      </div>
    </li>
  );
}
