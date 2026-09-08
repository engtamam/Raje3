/**
 * «أرباحي» — the fifth and final screen, built on this session's own research into
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
 * production today — the hero must render an honest "0 ر.س" plus a path forward, never a screen
 * that looks broken because nothing has happened yet.
 */
import { useEffect, useState } from 'react';
import { Wallet, TrendingUp, FileText } from 'lucide-react';
import { Button } from '@base-ui/design-system/Button';
import { Badge } from '@base-ui/design-system/Badge';
import { EmptyState } from '@base-ui/design-system/EmptyState';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import { riyalsLabel } from '../money';
import {
  AffiliateRefused, me, balance, commissions, requestWithdrawal, myWithdrawals,
  withdrawalReceiptUrl, wafaEligibility, requestWafa, myWafaRequests,
  employmentEligibility, requestEmployment, myEmploymentRequests,
  type AffiliateSession, type Me, type Balance, type Commission, type WithdrawalRequest,
  type WafaRequest, type EmploymentRequest, type SupportKpis,
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
const EMPLOYMENT_STATUS_LABEL: Record<string, string> = {
  requested: 'قيد المراجعة', approved: 'مُستحَق', rejected: 'مرفوض',
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

  return (
    <div className="flex flex-col gap-5 p-6">
      <h1 className="text-2xl leading-tight tracking-tight">أرباحي</h1>
      <BalanceSection session={session} />
      <WafaCard session={session} />
      <EmploymentCard session={session} />
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

  // BELOW WHAT THE BUTTON WOULD ACTUALLY DO — payouts.py's own `request()` refuses with
  // `below_minimum` at this exact comparison; showing it here means he learns it from the
  // number, not from tapping the button and reading an error.
  const belowMinimum = data.confirmed_available_halalas < data.min_withdrawal_halalas;
  const remaining = data.min_withdrawal_halalas - data.confirmed_available_halalas;

  return (
    <div className="flex flex-col gap-4 rounded-card bg-surface-1 p-5 shadow-sm">
      <span className="text-label font-medium text-text-secondary">رصيدك الجاهز للسحب</span>
      <span className="text-4xl font-semibold leading-none tracking-tight tabular-nums">
        {riyalsLabel(data.confirmed_available_halalas)}
      </span>
      {data.min_withdrawal_halalas > 0 ? (
        <span className="text-xs text-text-secondary">
          الحد الأدنى للسحب {riyalsLabel(data.min_withdrawal_halalas)}
          {belowMinimum ? ` — يتبقى ${riyalsLabel(remaining)} لتقدر تسحب` : null}
        </span>
      ) : null}

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
        <div className="flex items-center justify-between rounded-md bg-info-soft px-3 py-2.5 text-sm text-info-on-soft">
          <span>طلب سحبك بقيمة {riyalsLabel(openRequest.amount_halalas)} قيد المعالجة</span>
        </div>
      ) : (
        <Button type="button" disabled={busy || data.confirmed_available_halalas <= 0 || belowMinimum}
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
        <div className="h-full rounded-full bg-info" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-sm">
        {elig.eligible
          ? `تستحق ${riyalsLabel(elig.current_tier_amount_halalas)} شهريًا الآن`
          // ENOUGH SHOPS BUT NOT ENOUGH RECENT CONVERSIONS — a different sentence, not the
          // shop-count one. "N محل يفتح لك الاستحقاق" would read as "0 يفتح لك الاستحقاق" here
          // (he already has enough shops), telling him the opposite of what's actually blocking
          // him. Singular/plural matches core/wafa.py's own request()-time message.
          : elig.active_shops >= elig.tier_shops && elig.recent_conversions < elig.min_recent_conversions
          ? `عندك ${elig.tier_shops} محل، بس تحتاج ${
              elig.min_recent_conversions === 1 ? 'عميلاً جديداً' : `${elig.min_recent_conversions} عملاء جدد`
            } تحوّلوا من تجربة مجانية لاشتراك خلال آخر ${elig.conversion_lookback_days} يوماً`
          : `${elig.shops_until_next_tier} محل يفتح لك الاستحقاق`}
      </span>
      {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
      {elig.eligible && !hasOpenRequest ? (
        <Button type="button" disabled={busy} onClick={request}>اطلب الاستحقاق</Button>
      ) : hasOpenRequest ? (
        <span className="text-xs text-text-secondary">طلبك الحالي {WAFA_STATUS_LABEL.requested}.</span>
      ) : null}

      {/* أدائك أنت — نفس الأرقام اللي القرار الملزم يُبنى عليها (retention/refund)، ونفس مؤشرات
          الدعم اللي مديرك يشوفها عنك من «فريقي». "مدير التسويق يعتبر مسوّي،
          عنده نفس المؤشرات لنفسه" — هذي البطاقة تصير صحيحة لأي مسوّق، لا المدير فقط. */}
      <div className="mt-1 border-t border-border-subtle pt-3">
        <PerformanceStats retentionRate={elig.retention_rate} refundRate={elig.refund_rate}
                         supportKpis={elig.support_kpis} totalReferrals={elig.total_referrals}
                         totalCommissions={elig.total_commissions} />
      </div>
    </div>
  );
}

/** أرقام أداء مسوّق واحد — تُستخدم هنا لنفسه («دعم الوفاء») وبـ«فريقي» لكل عضو، نفس الشكل بالضبط
 *  حتى يتعلّم عضو الفريق قراءتها مرة واحدة ويفهمها بالمكانين.
 *
 *  totalReferrals/totalCommissions هي حجم العيّنة وراء كل نسبة — بلا محلات محالة أو عمولات، الرقم
 *  اللي ترجعه المعادلة (100٪ احتفاظ، 0٪ استرجاع) قيمة افتراضية للحساب لا رقماً مُكتسَباً، وعرضه
 *  كنسبة حقيقية بلا أي بيانات وراءها هو بالضبط ما اعتُرض عليه ("كيف كذا وهو صفر
 *  اساس! في غلط في المعادلة"). المعادلة نفسها صحيحة لغرضها الأصلي (توصية الاستحقاق) — العرض هو
 *  اللي كان يكذب. */
export function PerformanceStats({ retentionRate, refundRate, supportKpis,
                                  totalReferrals, totalCommissions }: {
  retentionRate: number; refundRate: number; supportKpis: SupportKpis;
  totalReferrals: number; totalCommissions: number;
}) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-2">
        <div className="flex-1 rounded-md bg-surface-0 p-2">
          <span className="block text-xs text-text-secondary">معدّل الاحتفاظ</span>
          <span className="tabular-nums font-medium">
            {totalReferrals > 0 ? `${Math.round(retentionRate * 100)}٪` : '—'}
          </span>
        </div>
        <div className="flex-1 rounded-md bg-surface-0 p-2">
          <span className="block text-xs text-text-secondary">معدّل الاسترجاع</span>
          <span className="tabular-nums font-medium">
            {totalCommissions > 0 ? `${Math.round(refundRate * 100)}٪` : '—'}
          </span>
        </div>
      </div>
      {totalReferrals === 0 && totalCommissions === 0 ? (
        <p className="text-xs text-text-muted">لا بيانات كافية بعد — تظهر أول محل تحيله يستمر أو ينقطع.</p>
      ) : null}
      {supportKpis.available ? (
        <div className="flex gap-2">
          <div className="flex-1 rounded-md bg-surface-0 p-2">
            <span className="block text-xs text-text-secondary">سرعة أول ردّ</span>
            <span className="tabular-nums font-medium">
              {formatDuration(supportKpis.avg_first_response_seconds)}
            </span>
          </div>
          <div className="flex-1 rounded-md bg-surface-0 p-2">
            <span className="block text-xs text-text-secondary">سرعة الحل</span>
            <span className="tabular-nums font-medium">
              {formatDuration(supportKpis.avg_resolution_seconds)}
            </span>
          </div>
          <div className="flex-1 rounded-md bg-surface-0 p-2">
            <span className="block text-xs text-text-secondary">نسبة التصعيد</span>
            <span className="tabular-nums font-medium">
              {Math.round((supportKpis.escalation_rate ?? 0) * 100)}٪
            </span>
          </div>
        </div>
      ) : (
        <p className="text-xs text-text-muted">
          مؤشرات الدعم تظهر أول ما محل يشارك تذاكره معك.
        </p>
      )}
    </div>
  );
}

/** ثانية خام → «س دقيقة» أو «س ساعة» — نفس فكرة `timeAgo` بـ TicketCarousel.tsx، هنا لمدّة لا لتاريخ. */
function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return '—';
  if (seconds < 3600) return `${Math.max(1, Math.round(seconds / 60))} دقيقة`;
  return `${Math.round(seconds / 3600)} ساعة`;
}

/** «رشّح نفسك لوظيفة» — نفس الشكل بالضبط، بطاقة منفصلة لأنه برنامج مختلف بعتبة مختلفة (عملاء
 *  مشتركون لا محلات نشِطة)، لا تبويب فرعي داخل بطاقة دعم الوفاء. */
function EmploymentCard({ session }: { session: AffiliateSession }) {
  const [elig, setElig] = useState<Awaited<ReturnType<typeof employmentEligibility>> | 'loading'>('loading');
  const [requests, setRequests] = useState<EmploymentRequest[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const load = () => {
    employmentEligibility(session).then(setElig).catch(() => {});
    myEmploymentRequests(session).then((r) => setRequests(r.employment_requests)).catch(() => {});
  };
  useEffect(load, [session]);

  if (elig === 'loading') return <Skeleton height={90} />;

  const hasOpenRequest = requests.some((r) => r.status === 'requested');
  const pct = Math.min(100, Math.round((elig.converted_customers / elig.threshold) * 100));

  async function request() {
    setBusy(true); setError('');
    try { await requestEmployment(session); load(); }
    catch (err) { setError(err instanceof AffiliateRefused ? err.message : 'تعذّر إرسال الطلب.'); }
    finally { setBusy(false); }
  }

  return (
    <div className="flex flex-col gap-3 rounded-card border border-success/30 bg-success-soft/40 p-4 shadow-sm">
      <div className="flex items-center gap-2 text-sm font-medium text-success-on-soft">
        <TrendingUp size={16} /> رشّح نفسك لوظيفة
      </div>
      <div className="flex justify-between text-xs text-text-secondary">
        <span>عملاء مشتركون</span>
        <span className="tabular-nums">{elig.converted_customers} / {elig.threshold}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-surface-0">
        <div className="h-full rounded-full bg-success" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-sm">
        {elig.eligible ? 'مؤهَّل للترشّح لوظيفة الآن' : `${elig.customers_until_eligible} للترشّح لوظيفة`}
      </span>
      {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
      {elig.eligible && !hasOpenRequest ? (
        <Button type="button" disabled={busy} onClick={request}>رشّح نفسي</Button>
      ) : hasOpenRequest ? (
        <span className="text-xs text-text-secondary">طلبك الحالي {EMPLOYMENT_STATUS_LABEL.requested}.</span>
      ) : null}
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
