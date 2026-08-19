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
import { useState, type FormEvent } from 'react';
import { Button } from '@base-ui/design-system/Button';
import { Field, Input } from '@base-ui/design-system/Field';
import { western } from '../digits';
import { AffiliateRefused, invite, type AffiliateSession } from './api';

export function AffiliateHome({ session, onSignOut }: {
  session: AffiliateSession; onSignOut: () => void;
}) {
  return (
    <div className="mx-auto flex min-h-dvh max-w-lg flex-col gap-8 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl leading-tight tracking-tight">بوابة المسوّق</h1>
        <Button type="button" onClick={onSignOut} className="opacity-70">تسجيل الخروج</Button>
      </div>

      <InviteCard session={session} />
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
