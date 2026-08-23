/**
 * «فريقي» — مدير التسويق فقط (2026-08-23).
 *
 * Tamam's own framing: a manager IS a marketer — everything a promoter has, he has too (his own
 * KPIs live on «أرباحي»'s own WafaCard, `PerformanceStats`, same component both places read). This
 * screen is the ADDITIONAL thing a manager gets on top: tracking and running his team, moved out
 * of «أرباحي» entirely into its own place — money stays about HIS OWN money, this is about them.
 *
 * WHY ITS OWN TAB, NOT A SIXTH BOTTOM-NAV SLOT FOR EVERYONE. AffiliateNav.tsx's own header note
 * fixed the bar at five slots for the approved design; this earns a sixth ONLY for managers
 * (`tabsFor(isManager)`) rather than reopening that decision for the promoter majority who would
 * never use it.
 */
import { useEffect, useState, type FormEvent } from 'react';
import { Users, CheckCircle2, XCircle, UserPlus } from 'lucide-react';
import { Button } from '@base-ui/design-system/Button';
import { Badge } from '@base-ui/design-system/Badge';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import { EmptyState } from '@base-ui/design-system/EmptyState';
import { Field, Input } from '@base-ui/design-system/Field';
import { riyalsLabel } from '../money';
import { western } from '../digits';
import { PerformanceStats } from './AffiliateEarnings';
import {
  team, teamWafaRequests, decideTeamWafaRequest, invite, AffiliateRefused,
  type AffiliateSession, type Team, type WafaRequest,
} from './api';

export function AffiliateTeam({ session }: { session: AffiliateSession }) {
  return (
    <div className="flex flex-col gap-5 p-6">
      <h1 className="text-2xl leading-tight tracking-tight">فريقي</h1>
      <AddMemberSection session={session} />
      <TeamWafaQueue session={session} />
      <TeamRoster session={session} />
    </div>
  );
}

/** زر يفتح نموذج الدعوة — لا نموذج دائم الظهور. الدعوة نفسها فعل نادر (عكس مراجعة الفريق اليومية)،
 *  فلا تستحق أول ما يفتح المدير الصفحة. */
function AddMemberSection({ session }: { session: AffiliateSession }) {
  const [open, setOpen] = useState(false);

  if (!open) {
    return (
      <Button type="button" onClick={() => setOpen(true)}
             className="flex items-center justify-center gap-2 self-start">
        <UserPlus size={16} /> إضافة عضو لفريقك
      </Button>
    );
  }

  return <InviteForm session={session} onDone={() => setOpen(false)} />;
}

function InviteForm({ session, onDone }: { session: AffiliateSession; onDone: () => void }) {
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
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="text-lg">ادعُ مسوّقاً لفريقك</h2>
          <p className="mt-1 text-sm text-text-secondary">
            يمر طلبه على مراجعة فريقنا قبل التفعيل — نفس الخطوة لأي طلب جديد.
          </p>
        </div>
        <Button type="button" variant="ghost" onClick={onDone}>إغلاق</Button>
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

function TeamRoster({ session }: { session: AffiliateSession }) {
  const [data, setData] = useState<Team | 'loading' | 'failed'>('loading');
  const [openId, setOpenId] = useState<string | null>(null);

  useEffect(() => {
    team(session).then(setData).catch(() => setData('failed'));
  }, [session]);

  if (data === 'loading') return <Skeleton height={220} />;
  if (data === 'failed') return <EmptyState title="تعذّرت قراءة الفريق" />;

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
          {data.members.map((m) => {
            const expanded = openId === m.id;
            const hasPerf = m.retention_rate != null && m.refund_rate != null && m.support_kpis;
            return (
              <li key={m.id} className="rounded-md bg-surface-0">
                <button type="button"
                       onClick={() => setOpenId(expanded ? null : m.id)}
                       disabled={!hasPerf}
                       className="flex w-full items-center justify-between px-2.5 py-2 text-sm text-start disabled:cursor-default">
                  <div className="flex items-center gap-2">
                    <span>{m.name}</span>
                    {m.status !== 'active' ? <Badge tone="neutral">{m.status}</Badge> : null}
                  </div>
                  <span className="tabular-nums text-text-secondary">
                    {riyalsLabel(m.confirmed_halalas)} — {m.shops} محل
                  </span>
                </button>
                {expanded && hasPerf ? (
                  <div className="border-t border-border-subtle p-2.5 pt-2">
                    <PerformanceStats retentionRate={m.retention_rate!} refundRate={m.refund_rate!}
                                     supportKpis={m.support_kpis!}
                                     totalReferrals={m.total_referrals ?? 0}
                                     totalCommissions={m.total_commissions ?? 0} />
                  </div>
                ) : null}
              </li>
            );
          })}
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
