/**
 * The affiliate portal, after the door — a placeholder home, deliberately small.
 *
 * THE DASHBOARD, COMMISSION AND LEADS SCREENS ARE LATER SLICES (spec §14's own table). What
 * exists on the backend TODAY is sign-in, apply, accept-invite, and a manager's own invite() —
 * so this screen is exactly that much and no more, rather than a home page promising sections
 * that would 404 the moment somebody pressed them.
 *
 * WHY THE INVITE FORM IS SHOWN TO EVERYONE SIGNED IN, NOT JUST MANAGERS: this screen has no way
 * to know the caller's role — affiliate-service exposes no "who am I, which role" read yet (only
 * GET /api/v1/whoami, which carries `caps`, and this tenant's roles have no capability seeding
 * done yet either — a pending item from Slice 2). The SERVER already refuses a promoter's attempt
 * correctly (`managers_only`, `403`) and this screen shows exactly that refusal — the same
 * "server decides, client displays" discipline Door.tsx's own sign-in pane already follows for
 * `unverified`. A capability-driven show/hide is a real improvement for later, not a gate this
 * screen may invent on its own guess.
 */
import { useEffect, useState, type FormEvent } from 'react';
import { Button } from '@base-ui/design-system/Button';
import { Field, Input } from '@base-ui/design-system/Field';
import { western } from '../digits';
import { AffiliateRefused, invite, me, type AffiliateSession, type Me } from './api';

export function AffiliateHome({ session, onSignOut }: {
  session: AffiliateSession; onSignOut: () => void;
}) {
  const [self, setSelf] = useState<Me | 'loading' | 'failed'>('loading');

  useEffect(() => {
    let cancelled = false;
    me(session)
      .then((m) => { if (!cancelled) setSelf(m); })
      .catch(() => { if (!cancelled) setSelf('failed'); });
    return () => { cancelled = true; };
  }, [session]);

  return (
    <div className="mx-auto flex min-h-dvh max-w-lg flex-col gap-8 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl leading-tight tracking-tight">بوابة المسوّق</h1>
        <Button type="button" onClick={onSignOut} className="opacity-70">تسجيل الخروج</Button>
      </div>

      <ReferralLinkCard self={self} />

      {/* ONLY A MANAGER CAN INVITE (services/affiliate-service's own onboarding.invite() enforces
          this — see InviteCard's own note on why this screen shows the form anyway rather than
          hiding it by a role guess of its own), so this waits for `self` to know that. */}
      {self !== 'loading' && self !== 'failed' && self.role === 'affiliate_manager'
        ? <InviteCard session={session} /> : null}
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
function ReferralLinkCard({ self }: { self: Me | 'loading' | 'failed' }) {
  const [copied, setCopied] = useState<'shop' | 'affiliate' | null>(null);

  if (self === 'loading') {
    return <div className="h-24 animate-pulse rounded-card bg-surface-1" />;
  }
  if (self === 'failed') {
    return <p role="alert" className="text-danger">تعذّر تحميل بيانات حسابك.</p>;
  }

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
