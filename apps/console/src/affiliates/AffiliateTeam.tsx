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
import { useEffect, useState } from 'react';
import { Users, CheckCircle2, XCircle, QrCode } from 'lucide-react';
import QRCode from 'qrcode';
import { Button } from '@base-ui/design-system/Button';
import { Badge } from '@base-ui/design-system/Badge';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import { EmptyState } from '@base-ui/design-system/EmptyState';
import { riyalsLabel } from '../money';
import { PerformanceStats } from './AffiliateEarnings';
import {
  me, team, teamWafaRequests, decideTeamWafaRequest,
  type AffiliateSession, type Team, type WafaRequest,
} from './api';

export function AffiliateTeam({ session }: { session: AffiliateSession }) {
  return (
    <div className="flex flex-col gap-5 p-6">
      <h1 className="text-2xl leading-tight tracking-tight">فريقي</h1>
      <ReferralLinkSection session={session} />
      <TeamWafaQueue session={session} />
      <TeamRoster session={session} />
    </div>
  );
}

/** لا دعوة تُرسَل من عندنا بعد الآن (تمام، 2026-08-23: "رابط للمدير مافي اي ارسال المدير راح
 *  يرسل له الرابط") — المدير يشارك رابطه الخاص بنفسه (واتساب، شخصيًا)، ومن يستخدمه يقدّم طلبه
 *  العادي ويُربَط تحت المدير تلقائيًا عبر كود الإحالة، بعد تأكيد رقم جواله. */
function ReferralLinkSection({ session }: { session: AffiliateSession }) {
  const [selfId, setSelfId] = useState<string | 'loading' | 'failed'>('loading');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    me(session).then((m) => { if (!cancelled) setSelfId(m.id); })
      .catch(() => { if (!cancelled) setSelfId('failed'); });
    return () => { cancelled = true; };
  }, [session]);

  if (selfId === 'loading') return <Skeleton height={100} />;
  if (selfId === 'failed') return null;

  const link = `${window.location.origin}/affiliates?ref=${selfId}`;
  const copy = () => {
    navigator.clipboard?.writeText(link).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }).catch(() => {});
  };

  return (
    <div className="flex flex-col gap-3 rounded-card bg-surface-1 p-5 shadow-sm">
      <div>
        <h2 className="text-lg">أضف عضواً لفريقك</h2>
        <p className="mt-1 text-sm text-text-secondary">
          شارك رابطك مع المسوّق — طلبه يمر بالمراجعة ثم يُربَط تحتك تلقائيًا.
        </p>
      </div>
      <div className="flex gap-2">
        <input readOnly dir="ltr" value={link}
               className="w-full rounded-md border border-border-strong bg-surface-0 px-3 py-2 text-sm text-text-primary" />
        <Button type="button" onClick={copy}>{copied ? 'تم النسخ' : 'نسخ'}</Button>
        <QrDownloadButton link={link} />
      </div>
    </div>
  );
}

function QrDownloadButton({ link }: { link: string }) {
  const [busy, setBusy] = useState(false);

  async function download() {
    setBusy(true);
    try {
      const dataUrl = await QRCode.toDataURL(link, { width: 512, margin: 2 });
      const a = document.createElement('a');
      a.href = dataUrl;
      a.download = 'رابط-دعوة-مسوّق.png';
      a.click();
    } catch {
      // الرابط نفسه لسا قابل للنسخ عادي، الباركود مجرد تسهيل إضافي.
    } finally {
      setBusy(false);
    }
  }

  return (
    <Button type="button" variant="ghost" size="icon" aria-label="تنزيل كباركود"
           disabled={busy} onClick={download}>
      <QrCode size={16} />
    </Button>
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
