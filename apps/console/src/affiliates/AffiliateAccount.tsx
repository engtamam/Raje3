/**
 * «حسابي» (2026-08-22) — built out from the sign-out-only stub, on this session's own research
 * into gig/field-sales account screens (Uber Driver, DoorDash Dasher) plus a full backend
 * inventory of what affiliate-service actually supports.
 *
 * SCOPED TO WHAT IS REAL. The research's full recommended list also names per-category
 * notification toggles and a support/legal section — neither exists anywhere in affiliate-service
 * (confirmed by direct inventory). Building UI for them would be exactly the failure
 * `AccountPanes.tsx`'s own convention warns against — a screen that "says so plainly" when a
 * section has nothing behind it, never a control that quietly does nothing. Password-change WAS
 * missing at first inventory time; it now has a real backend (see `change-password`'s own commit)
 * and gets its own section here.
 *
 * PAYOUT GOT ITS OWN READ ROUTE THIS SESSION (`GET /me/payout-method`) — it did not exist before,
 * so this screen is also what closed that gap: showing a masked account on file needs somewhere
 * to read it FROM.
 */
import { useEffect, useState } from 'react';
import { CircleUserRound, LogOut, Wallet, KeyRound } from 'lucide-react';
import { Button } from '@base-ui/design-system/Button';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import {
  AffiliateRefused, me, payoutMethod, setPayoutMethod, changePassword, PAYOUT_CHANNELS,
  type AffiliateSession, type Me, type PayoutMethod,
} from './api';

const ROLE_LABEL: Record<string, string> = {
  affiliate_manager: 'مدير تسويق', affiliate_promoter: 'مسوّق',
};
const CHANNEL_LABEL: Record<string, string> = {
  bank_iban: 'حساب بنكي (آيبان)', intermediary: 'منصة وسيطة',
};

export function AffiliateAccount({ session, onSignOut }: {
  session: AffiliateSession; onSignOut: () => void;
}) {
  const [who, setWho] = useState<Me | 'loading' | 'failed'>('loading');

  useEffect(() => {
    let cancelled = false;
    me(session).then((m) => { if (!cancelled) setWho(m); })
      .catch(() => { if (!cancelled) setWho('failed'); });
    return () => { cancelled = true; };
  }, [session]);

  return (
    <div className="flex flex-col gap-6 p-6">
      <h1 className="text-2xl leading-tight tracking-tight">حسابي</h1>

      {who === 'loading' ? (
        <Skeleton height={90} />
      ) : (
        <div className="flex items-center gap-3 rounded-card bg-surface-1 p-4 shadow-sm">
          <div className="grid size-12 shrink-0 place-items-center rounded-full bg-surface-2 text-text-muted">
            <CircleUserRound size={24} />
          </div>
          <div className="flex flex-col">
            <span className="font-medium">
              {who === 'failed' ? 'تعذّرت قراءة بيانات حسابك' : who.name}
            </span>
            {who !== 'failed' ? (
              <span className="text-sm text-text-secondary">{ROLE_LABEL[who.role] ?? who.role}</span>
            ) : null}
          </div>
        </div>
      )}

      <PayoutMethodCard session={session} />

      <ChangePasswordCard session={session} />

      <Button type="button" variant="outline" onClick={onSignOut}
             className="flex items-center justify-center gap-2 text-danger">
        <LogOut size={16} /> تسجيل الخروج
      </Button>
    </div>
  );
}

/** View mode shows only what `GET /payout-method` ever returns — a channel name and the last
 *  four characters of the account. Edit mode is a fresh form every time, never pre-filled with a
 *  full account number the server itself no longer gives back. */
function PayoutMethodCard({ session }: { session: AffiliateSession }) {
  const [data, setData] = useState<PayoutMethod | 'loading' | 'failed'>('loading');
  const [editing, setEditing] = useState(false);

  const load = () => {
    setData('loading');
    payoutMethod(session).then(setData).catch(() => setData('failed'));
  };
  useEffect(load, [session]);

  if (editing) {
    return (
      <PayoutMethodForm
        session={session}
        current={data !== 'loading' && data !== 'failed' && data.set ? data : null}
        onDone={() => { setEditing(false); load(); }}
        onCancel={() => setEditing(false)}
      />
    );
  }

  return (
    <div className="flex flex-col gap-3 rounded-card bg-surface-1 p-4 shadow-sm">
      <div className="flex items-center gap-2 text-sm font-medium text-text-secondary">
        <Wallet size={16} /> طريقة استلام أرباحك
      </div>

      {data === 'loading' ? (
        <Skeleton height={40} />
      ) : data === 'failed' ? (
        <p className="text-sm text-danger">تعذّرت قراءة طريقة الاستلام الآن.</p>
      ) : data.set ? (
        <div className="flex items-center justify-between">
          <div className="flex flex-col">
            <span className="text-sm">{CHANNEL_LABEL[data.channel] ?? data.channel}</span>
            <span dir="ltr" className="text-sm tabular-nums text-text-secondary">
              {data.channel_name ? `${data.channel_name} — ` : ''}{data.masked_account_ref}
            </span>
          </div>
          <Button type="button" variant="ghost" onClick={() => setEditing(true)}>تغيير</Button>
        </div>
      ) : (
        <div className="flex items-center justify-between">
          <p className="text-sm text-warning">لم تُضِف طريقة استلام بعد — لن تقدر تسحب أرباحك بدونها.</p>
          <Button type="button" onClick={() => setEditing(true)}>إضافة</Button>
        </div>
      )}
    </div>
  );
}

function PayoutMethodForm({ session, current, onDone, onCancel }: {
  session: AffiliateSession; current: Extract<PayoutMethod, { set: true }> | null;
  onDone: () => void; onCancel: () => void;
}) {
  const [channel, setChannel] = useState(current?.channel || PAYOUT_CHANNELS[0]);
  const [channelName, setChannelName] = useState(current?.channel_name || '');
  const [accountRef, setAccountRef] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function save() {
    setBusy(true); setError('');
    try {
      await setPayoutMethod(session, { channel, channelName, accountRef });
      onDone();
    } catch (err) {
      setError(err instanceof AffiliateRefused ? err.message : 'تعذّر حفظ طريقة الاستلام.');
    } finally { setBusy(false); }
  }

  return (
    <div className="flex flex-col gap-3 rounded-card bg-surface-1 p-4 shadow-sm">
      <div className="flex items-center gap-2 text-sm font-medium text-text-secondary">
        <Wallet size={16} /> {current ? 'تغيير طريقة الاستلام' : 'إضافة طريقة استلام'}
      </div>

      {current ? (
        <p className="text-xs text-text-secondary">
          تغيير الطريقة قد يؤخّر دفعتك القادمة إلى حين مراجعتها.
        </p>
      ) : null}

      <div className="flex gap-2">
        {PAYOUT_CHANNELS.map((c) => (
          <Button key={c} type="button" variant={channel === c ? 'solid' : 'ghost'}
                 onClick={() => setChannel(c)}>
            {CHANNEL_LABEL[c]}
          </Button>
        ))}
      </div>

      {channel === 'intermediary' ? (
        <input value={channelName} onChange={(e) => setChannelName(e.target.value)}
               placeholder="اسم المنصة الوسيطة"
               className="h-11 rounded-md border border-border-strong bg-surface-0 px-3 text-sm" />
      ) : null}

      <input value={accountRef} onChange={(e) => setAccountRef(e.target.value)} dir="ltr"
             placeholder={channel === 'bank_iban' ? 'رقم الآيبان' : 'رقم حسابك على المنصة'}
             className="h-11 rounded-md border border-border-strong bg-surface-0 px-3 text-sm" />

      {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}

      <div className="flex gap-2">
        <Button type="button" disabled={busy || !accountRef.trim()} onClick={save}>حفظ</Button>
        <Button type="button" variant="ghost" disabled={busy} onClick={onCancel}>إلغاء</Button>
      </div>
    </div>
  );
}

/** Collapsed by default — a control this sensitive earns the extra tap, per the research's own
 *  "critical action must be reachable, never prominent" balance. The three-field pattern (current +
 *  new + confirm) rather than a "forgot password" reset: this is an AUTHENTICATED change, made
 *  while he already holds a session, which is a different flow from the unauthenticated one on the
 *  sign-in screen — see this session's own research note on why the two must never be conflated. */
function ChangePasswordCard({ session }: { session: AffiliateSession }) {
  const [open, setOpen] = useState(false);
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)}
             className="flex items-center gap-2 rounded-card bg-surface-1 p-4 text-sm shadow-sm">
        <KeyRound size={16} className="text-text-secondary" /> تغيير كلمة المرور
      </button>
    );
  }

  async function submit() {
    if (newPassword !== confirm) { setError('كلمتا المرور الجديدتان غير متطابقتين.'); return; }
    setBusy(true); setError(''); setDone(false);
    try {
      await changePassword(session, oldPassword, newPassword);
      setDone(true);
      setOldPassword(''); setNewPassword(''); setConfirm('');
    } catch (err) {
      setError(err instanceof AffiliateRefused ? err.message : 'تعذّر تغيير كلمة المرور.');
    } finally { setBusy(false); }
  }

  return (
    <div className="flex flex-col gap-3 rounded-card bg-surface-1 p-4 shadow-sm">
      <div className="flex items-center gap-2 text-sm font-medium text-text-secondary">
        <KeyRound size={16} /> تغيير كلمة المرور
      </div>

      <input type="password" value={oldPassword}
             onChange={(e) => { setOldPassword(e.target.value); setDone(false); }}
             placeholder="كلمة المرور الحالية"
             className="h-11 rounded-md border border-border-strong bg-surface-0 px-3 text-sm" />
      <input type="password" value={newPassword}
             onChange={(e) => { setNewPassword(e.target.value); setDone(false); }}
             placeholder="كلمة المرور الجديدة"
             className="h-11 rounded-md border border-border-strong bg-surface-0 px-3 text-sm" />
      <input type="password" value={confirm}
             onChange={(e) => { setConfirm(e.target.value); setDone(false); }}
             placeholder="تأكيد كلمة المرور الجديدة"
             className="h-11 rounded-md border border-border-strong bg-surface-0 px-3 text-sm" />

      {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
      {done ? <p className="text-sm text-success">تم تغيير كلمة المرور.</p> : null}

      <div className="flex gap-2">
        <Button type="button" disabled={busy || !oldPassword || !newPassword || !confirm}
               onClick={submit}>
          حفظ
        </Button>
        <Button type="button" variant="ghost" disabled={busy}
               onClick={() => { setOpen(false); setError(''); setDone(false); }}>
          إلغاء
        </Button>
      </div>
    </div>
  );
}
