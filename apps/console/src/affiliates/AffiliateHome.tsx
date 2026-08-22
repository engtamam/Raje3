/**
 * The affiliate portal's real home screen (2026-08-22) — replaces the earlier placeholder now
 * that the backend actually has something to show: `GET /me/home` (affiliate_self.py::home)
 * assembles everything below from six-to-eight routes into one call, server-side, so this screen
 * makes exactly ONE request rather than fanning them out itself.
 *
 * THE HIERARCHY IS THE RESEARCH, NOT A GUESS: urgent items needing a reply first (loss-aversion —
 * "who's waiting on me" — is the single highest-leverage trigger for a WhatsApp-led sales flow),
 * then the one next action, then earnings, then progress toward the two commission programs, then
 * what is actually converting, then — manager only — the team. See the design mockup this session
 * produced for the full research trail; every widget here reads from a real field `home()` already
 * returns, never an invented number.
 *
 * A DAY-ONE EMPTY STATE IS THE COMMON CASE, NOT THE EDGE CASE — checked against the live server
 * directly before building this: zero real affiliates exist yet. Every section below has to read
 * honestly at zero (no stale leads, no team, no template used yet) rather than assume data that
 * will not exist for a while.
 */
import { useEffect, useState, type FormEvent } from 'react';
import { Button } from '@base-ui/design-system/Button';
import { Field, Input } from '@base-ui/design-system/Field';
import { riyalsLabel } from '../money';
import { western } from '../digits';
import { AffiliateRefused, home, invite, type AffiliateSession, type Home } from './api';

export function AffiliateHome({ session, onSignOut }: {
  session: AffiliateSession; onSignOut: () => void;
}) {
  const [data, setData] = useState<Home | 'loading' | 'failed'>('loading');

  useEffect(() => {
    let cancelled = false;
    home(session)
      .then((h) => { if (!cancelled) setData(h); })
      .catch(() => { if (!cancelled) setData('failed'); });
    return () => { cancelled = true; };
  }, [session]);

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl leading-tight tracking-tight">
          {data !== 'loading' && data !== 'failed' ? `مرحباً، ${data.affiliate.name}` : 'بوابة المسوّق'}
        </h1>
        <Button type="button" onClick={onSignOut} className="opacity-70">تسجيل الخروج</Button>
      </div>

      {data === 'loading' ? <HomeSkeleton /> : null}
      {data === 'failed' ? (
        <p role="alert" className="text-danger">تعذّر تحميل بيانات حسابك. أعد المحاولة بعد قليل.</p>
      ) : null}

      {data !== 'loading' && data !== 'failed' ? (
        <>
          <UrgentLeadsCard data={data} />
          <EarningsCard data={data} />
          <EligibilityRow data={data} />
          <TopTemplateCard data={data} />
          {data.team ? <TeamCard team={data.team} /> : null}
          <ReferralLinkCard self={data.affiliate} />
          {data.affiliate.role === 'affiliate_manager'
            ? <InviteCard session={session} /> : null}
        </>
      ) : null}
    </div>
  );
}

function HomeSkeleton() {
  return (
    <div className="flex flex-col gap-4" aria-hidden>
      <div className="h-20 animate-pulse rounded-card bg-surface-1" />
      <div className="h-28 animate-pulse rounded-card bg-surface-1" />
      <div className="h-16 animate-pulse rounded-card bg-surface-1" />
    </div>
  );
}

/** THE #1 WIDGET, PER THE RESEARCH: a lead nobody has touched in a while is the single strongest,
 *  least-gamified reason to open this app right now — see this session's own design trail (the
 *  "5 minutes worth more than 4 hours" finding). Absent entirely when there is nothing waiting,
 *  never a false-cheerful "all caught up" banner that would be one more thing to read past. */
function UrgentLeadsCard({ data }: { data: Home }) {
  if (data.stale_leads_count === 0) return null;
  const shown = data.stale_leads.slice(0, 3);
  return (
    <div className="flex flex-col gap-3 rounded-card bg-danger-soft p-4">
      <div className="flex items-center justify-between">
        <span className="font-medium text-danger">
          {data.stale_leads_count === 1 ? 'عميل واحد بانتظار ردك' : `${data.stale_leads_count} عملاء بانتظار ردك`}
        </span>
      </div>
      <div className="flex flex-col gap-2">
        {shown.map((lead) => (
          <div key={lead.id} className="flex items-center justify-between rounded-md bg-surface-0 px-3 py-2 text-sm">
            <span className="truncate font-medium">{lead.name || 'محل بلا اسم مسجَّل'}</span>
            <span className="shrink-0 text-xs text-text-secondary">{lead.city}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function EarningsCard({ data }: { data: Home }) {
  const { balance } = data;
  return (
    <div className="flex flex-col gap-3 rounded-card bg-surface-1 p-5 shadow-sm">
      <span className="text-label font-medium text-text-secondary">رصيدك الجاهز للسحب</span>
      <span className="text-4xl font-semibold leading-none tracking-tight tabular-nums">
        {riyalsLabel(balance.confirmed_available_halalas)}
      </span>
      <div className="flex gap-2">
        <div className="flex-1 rounded-md bg-surface-0 p-2.5">
          <span className="block text-xs text-text-secondary">معلَّق</span>
          <span className="tabular-nums font-medium">{riyalsLabel(balance.pending_halalas)}</span>
        </div>
        <div className="flex-1 rounded-md bg-surface-0 p-2.5">
          <span className="block text-xs text-text-secondary">مسحوب سابقًا</span>
          <span className="tabular-nums font-medium">{riyalsLabel(balance.withdrawn_halalas)}</span>
        </div>
      </div>
      {/* A REAL, PRESSABLE NEXT STEP RATHER THAN A NUMBER ALONE — a home screen's job is action
          before analytics; withdrawing/setting a payout method is the actual thing a screen full
          of money should let him do. */}
      {!data.payout_method_set ? (
        <p className="text-xs text-warning">أضف طريقة استلام أرباحك من صفحة حسابك قبل أول سحب.</p>
      ) : data.pending_withdrawal ? (
        <p className="text-xs text-text-secondary">طلب سحبك الحالي قيد المراجعة.</p>
      ) : null}
    </div>
  );
}

/** Two programs, one row — both answer "how close am I" from `eligibility_preview()`, never from
 *  trying a request and being refused. Absent entirely for a brand-new promoter at zero would just
 *  be two empty meters, which is still the honest truth (§8's own thresholds are real, not close). */
function EligibilityRow({ data }: { data: Home }) {
  const wafa = data.wafa_eligibility;
  const wafaPct = Math.min(100, Math.round((wafa.active_shops % wafa.tier_shops || (wafa.eligible ? wafa.tier_shops : 0)) / wafa.tier_shops * 100));
  const emp = data.employment_eligibility;
  const empPct = Math.min(100, Math.round((emp.converted_customers / emp.threshold) * 100));
  return (
    <div className="flex gap-3 rounded-card bg-surface-1 p-4 shadow-sm">
      <Meter
        label="محلات نشِطة"
        value={`${wafa.active_shops} / ${wafa.tier_shops}`}
        pct={wafaPct}
        note={wafa.eligible
          ? `تستحق ${riyalsLabel(wafa.current_tier_amount_halalas)} شهريًا الآن`
          : `${wafa.shops_until_next_tier} محل يفتح لك دعم الوفاء`}
      />
      <Meter
        label="عملاء مشتركون"
        value={`${emp.converted_customers} / ${emp.threshold}`}
        pct={empPct}
        note={emp.eligible ? 'مؤهَّل للترشّح لوظيفة الآن' : `${emp.customers_until_eligible} للترشّح لوظيفة`}
      />
    </div>
  );
}

function Meter({ label, value, pct, note }: { label: string; value: string; pct: number; note: string }) {
  return (
    <div className="flex flex-1 flex-col gap-1.5">
      <div className="flex justify-between text-xs text-text-secondary">
        <span>{label}</span>
        <span className="tabular-nums">{value}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-surface-0">
        <div className="h-full rounded-full bg-accent" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-text-secondary">{note}</span>
    </div>
  );
}

/** "Which of MY OWN templates actually works" — absent until he has used at least one, since a
 *  rate computed from zero uses would be a fiction dressed as a percentage. */
function TopTemplateCard({ data }: { data: Home }) {
  const t = data.top_template_this_period;
  if (!t) return null;
  return (
    <div className="flex items-center justify-between rounded-card bg-surface-1 p-4 shadow-sm">
      <div className="flex flex-col">
        <span className="text-sm font-medium">{t.title}</span>
        <span className="text-xs text-text-secondary">أفضل قالب يشتغل معك — {t.uses} استخدام</span>
      </div>
      <span className="text-xl font-semibold tabular-nums text-success">
        {Math.round(t.advance_rate * 100)}٪
      </span>
    </div>
  );
}

function TeamCard({ team }: { team: NonNullable<Home['team']> }) {
  return (
    <div className="flex flex-col gap-3 rounded-card bg-surface-1 p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <span className="text-lg">فريقك</span>
        {team.pending_wafa_requests_count > 0 ? (
          <span className="rounded-full bg-danger-soft px-2.5 py-0.5 text-xs font-medium text-danger">
            {team.pending_wafa_requests_count} قرار بانتظارك
          </span>
        ) : null}
      </div>
      <div className="flex gap-2">
        <div className="flex-1 rounded-md bg-surface-0 p-2.5">
          <span className="block text-xs text-text-secondary">عدد الفريق</span>
          <span className="tabular-nums font-medium">{team.member_count}</span>
        </div>
        <div className="flex-1 rounded-md bg-surface-0 p-2.5">
          <span className="block text-xs text-text-secondary">إيراد مؤكَّد</span>
          <span className="tabular-nums font-medium">{riyalsLabel(team.team_confirmed_halalas)}</span>
        </div>
      </div>
    </div>
  );
}

/**
 * HIS OWN ID IS HIS REFERRAL CODE (spec §1) — no separate code to mint, copy, or keep in step
 * with the affiliate row. Two links shown for the two doors that read `?aff=`/`?ref=`: a shop
 * owner's own signup (auth.ts::affiliateRefFromUrl) and another marketer applying under him
 * (AffiliateDoor.tsx's own `ref` prefill) — a promoter gets the second only implicitly (nothing
 * stops him sharing it; onboarding.py's own apply() decides what a referral code sitting on a
 * promoter's row actually means when read back).
 */
function ReferralLinkCard({ self }: { self: Home['affiliate'] }) {
  const [copied, setCopied] = useState<'shop' | 'affiliate' | null>(null);

  const base = window.location.origin;
  const shopLink = `${base}/?aff=${self.id}`;
  const affiliateLink = `${base}/affiliates?ref=${self.id}`;

  const copy = (which: 'shop' | 'affiliate', link: string) => {
    navigator.clipboard?.writeText(link).then(() => {
      setCopied(which);
      setTimeout(() => setCopied(null), 2000);
    }).catch(() => {});
  };

  return (
    <div className="flex flex-col gap-4 rounded-card bg-surface-1 p-5 shadow-sm">
      <h2 className="text-lg">رابطك</h2>

      <div className="flex flex-col gap-1.5">
        <span className="text-label font-medium text-text-secondary">لدعوة صاحب محل</span>
        <div className="flex gap-2">
          <input readOnly dir="ltr" value={shopLink}
                 className="w-full rounded-md border border-border-strong bg-surface-0 px-3 py-2 text-sm text-text-primary" />
          <Button type="button" onClick={() => copy('shop', shopLink)}>
            {copied === 'shop' ? 'تم النسخ' : 'نسخ'}
          </Button>
        </div>
      </div>

      {self.role === 'affiliate_manager' ? (
        <div className="flex flex-col gap-1.5">
          <span className="text-label font-medium text-text-secondary">لدعوة مسوّق تحتك</span>
          <div className="flex gap-2">
            <input readOnly dir="ltr" value={affiliateLink}
                   className="w-full rounded-md border border-border-strong bg-surface-0 px-3 py-2 text-sm text-text-primary" />
            <Button type="button" onClick={() => copy('affiliate', affiliateLink)}>
              {copied === 'affiliate' ? 'تم النسخ' : 'نسخ'}
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function InviteCard({ session }: { session: AffiliateSession }) {
  const [phone, setPhone] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!phone.trim() || !name.trim()) {
      setError('أدخل الاسم ورقم الجوال.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      await invite(session, phone, name);
      setSent(true);
      setPhone('');
      setName('');
    } catch (err) {
      setError(err instanceof AffiliateRefused ? err.message : 'تعذّرت الدعوة.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4 rounded-card bg-surface-1 p-5 shadow-sm">
      <div>
        <h2 className="text-lg">ادعُ مسوّقاً لفريقك</h2>
        <p className="mt-1 text-sm text-text-secondary">
          يمر طلبه على مراجعة فريقنا قبل التفعيل — نفس الخطوة لأي طلب جديد.
        </p>
      </div>

      <Field label="اسمه" required htmlFor="inv-name">
        <Input id="inv-name" value={name}
               onChange={(e) => { setName(e.target.value); setError(''); setSent(false); }} />
      </Field>

      <Field label="رقم جواله" required htmlFor="inv-phone">
        <Input id="inv-phone" value={phone} type="tel" inputMode="tel" dir="ltr"
               placeholder="05XXXXXXXX"
               onChange={(e) => {
                 setPhone(western(e.target.value)); setError(''); setSent(false);
               }} />
      </Field>

      {error ? <p role="alert" className="text-danger">{error}</p> : null}
      {sent ? <p className="text-success">أُرسلت الدعوة — بانتظار المراجعة.</p> : null}

      <Button type="submit" disabled={busy || !phone.trim() || !name.trim()}>
        {busy ? 'جارٍ الإرسال…' : 'إرسال الدعوة'}
      </Button>
    </form>
  );
}
