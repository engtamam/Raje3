/**
 * The affiliate portal's door — «بوابة المسوّق» (spec §2/§9).
 *
 * BUILT FROM THE SAME PRIMITIVES AS Door.tsx, on purpose — `Field`, `Input`, `Button`,
 * `Segmented`, and the shop door's own `DoorLayout` canvas (now parametrised, see that file) —
 * but this is its OWN component, not Door.tsx branched. Three real differences earn that:
 *
 *   THE WORDS ARE FOR A MARKETER, NOT A SHOP OWNER. «افتح محلك» means nothing to someone who has
 *   no shop; every label, every sentence and the hero copy on the canvas are this audience's own.
 *
 *   THE LINKS ARE THIS PRODUCT'S OWN POLICIES. `VITE_AFFILIATE_LEGAL_BASE`, never `VITE_LEGAL_BASE`
 *   — an affiliate's agreement is about referrals and commission, not about a shop's PDPL
 *   obligations to ITS customers, and a person agreeing to the wrong document agreed to nothing.
 *
 *   TWO DOORS, NOT THREE ANY LONGER: «قبول دعوة» is gone — a manager no longer
 *   invites through us at all ("رابط للمدير مافي اي ارسال المدير راح يرسل له الرابط").
 *   He shares his own referral link himself, and whoever uses it lands right here, on «تقديم
 *   طلب», with `?ref=` pre-filling the same field a self-applicant fills by hand.
 *
 * THE OTP STEP IS OPTIONAL TODAY AND WILL BECOME MANDATORY THE MOMENT IT CAN BE. `apply()`'s own
 * `code` is empty unless the applicant pressed «أرسل رمز التحقق» — the server accepts that as
 * long as AFFILIATE_REQUIRE_OTP is off (every deployment today, since no WhatsApp/SMS channel is
 * wired yet — see onboarding.py's own note), and will start refusing an empty one the day it is
 * turned on, with no change needed here.
 */
import { useMemo, useState, type FormEvent } from 'react';
import { Button } from '../rj-ui/Button';
import { Field, Input } from '../rj-ui/Field';
import { Segmented } from '../rj-ui/Segmented';
import { DoorLayout } from '../screens/DoorLayout';
import { western } from '../digits';
import { legalUrl } from '../legal/url';
import { AffiliateRefused, apply, requestApplyOtp, signIn, type AffiliateSession } from './api';

type Mode = 'in' | 'new';

function normalizePhone(raw: string): string | null {
  const digits = (raw || '').replace(/[\s\-()]/g, '').replace(/^00/, '+');
  const national = digits.startsWith('+966') ? digits.slice(4)
    : digits.startsWith('966') ? digits.slice(3)
    : digits.startsWith('0') ? digits.slice(1)
    : digits;
  return /^5\d{8}$/.test(national) ? `+966${national}` : null;
}

/** A soft hint, not the rule — identity-service's own PASSWORD_MIN_LENGTH is the authority
 *  (config, not this file), and a mismatch must fail OPEN into a server refusal with a real
 *  sentence rather than a client rule blocking a password the server would have accepted. */
const PW_MIN_HINT = 8;

export function AffiliateDoor(
  { onSignedIn }: { onSignedIn: (session: AffiliateSession) => void },
) {
  const params = useMemo(() => new URLSearchParams(window.location.search), []);
  // A `?ref=` LINK IS A REFERRAL, NOT A LOGIN — a manager sharing AffiliateHome's own referral
  // link means "apply", and landing whoever clicks it on the sign-in pane (which has nowhere to
  // even show the referral code) would bury the one thing the link was for.
  const [mode, setMode] = useState<Mode>(params.get('ref') ? 'new' : 'in');

  return (
    <DoorLayout
      title="عمولتك تكبر وأنت نائم."
      subtitle="راجِع يدفع لك عن كل منشأة تحضرها للمنصة — عمولة مستمرة، من أول يوم توقّعه، بلا سقف."
    >
      <div className="flex flex-col gap-6">
        <Segmented
          className="flex w-full [&>button]:flex-1 [&>button]:whitespace-nowrap"
          options={[
            { value: 'in', label: 'تسجيل الدخول' },
            { value: 'new', label: 'تقديم طلب' },
          ]}
          value={mode}
          onChange={(v) => setMode(v as Mode)}
        />
        {mode === 'in' && <SignInPane onSignedIn={onSignedIn} />}
        {mode === 'new' && <ApplyPane />}
      </div>
    </DoorLayout>
  );
}

function SignInPane({ onSignedIn }: { onSignedIn: (session: AffiliateSession) => void }) {
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const data = new FormData(e.currentTarget as HTMLFormElement);
    const typedPhone = String(data.get('phone') ?? '').trim() || phone;
    const typedPassword = String(data.get('password') ?? '') || password;
    if (!typedPhone || !typedPassword) {
      setError('أدخل رقم الجوال وكلمة المرور.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const session = await signIn(typedPhone, typedPassword);
      onSignedIn(session);
    } catch (err) {
      setError(err instanceof AffiliateRefused ? err.message : 'تعذّر تسجيل الدخول.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
      <div>
        <h2 className="text-3xl leading-tight tracking-tight">أهلاً بك</h2>
        <p className="mt-2 text-sm text-text-secondary">رقم جوالك وكلمة المرور.</p>
      </div>

      <Field label="رقم الجوال" required htmlFor="aff-in-phone">
        <Input
          id="aff-in-phone" name="phone" value={phone}
          onChange={(e) => { setPhone(western(e.target.value)); setError(''); }}
          type="tel" inputMode="tel" dir="ltr" autoComplete="username" placeholder="05XXXXXXXX"
        />
      </Field>

      <Field label="كلمة المرور" required htmlFor="aff-in-password">
        <Input
          id="aff-in-password" name="password" value={password}
          onChange={(e) => { setPassword(e.target.value); setError(''); }}
          type="password" autoComplete="current-password"
        />
      </Field>

      {error ? <p role="alert" className="text-danger">{error}</p> : null}

      {/* Dimmed, never disabled — same autofill-trap reasoning as Door.tsx's own SignInPane. */}
      <Button type="submit" disabled={busy} className={phone && password ? undefined : 'opacity-50'}>
        {busy ? 'جارٍ الدخول…' : 'تسجيل الدخول'}
      </Button>
    </form>
  );
}

type FieldName = 'phone' | 'password' | 'name';

function errorFor(f: FieldName, v: string): string {
  switch (f) {
    case 'phone':
      return normalizePhone(v) ? '' : 'أدخل رقم جوال سعودي — مثل 0501234567';
    case 'password':
      return v.length >= PW_MIN_HINT ? '' : `${PW_MIN_HINT} أحرف على الأقل`;
    case 'name':
      return v.trim().length >= 2 ? '' : 'أدخل اسمك';
  }
}

function ApplyPane() {
  const [v, setV] = useState<Record<FieldName, string>>({ phone: '', password: '', name: '' });
  const [touched, setTouched] = useState<Partial<Record<FieldName, boolean>>>({});
  const [referralCode, setReferralCode] = useState(
    () => new URLSearchParams(window.location.search).get('ref') ?? '');
  const [cvUrl, setCvUrl] = useState('');
  const [code, setCode] = useState('');
  const [otpSent, setOtpSent] = useState(false);
  const [otpBusy, setOtpBusy] = useState(false);
  const [otpError, setOtpError] = useState('');
  const [agree, setAgree] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  async function sendOtp() {
    if (errorFor('phone', v.phone)) { setTouched((p) => ({ ...p, phone: true })); return; }
    setOtpBusy(true);
    setOtpError('');
    try {
      await requestApplyOtp(v.phone);
      setOtpSent(true);
    } catch (err) {
      // «غير مُفعّل بعد» IS THE HONEST ANSWER ON EVERY DEPLOYMENT TODAY (AFFILIATE_OTP_DELIVERABLE
      // is off — no WhatsApp/SMS channel wired yet) — shown, not swallowed, so nobody stares at a
      // code screen waiting for a message nothing ever tried to send.
      setOtpError(err instanceof AffiliateRefused ? err.message : 'تعذّر إرسال الرمز.');
    } finally {
      setOtpBusy(false);
    }
  }

  const errs = useMemo(() => ({
    phone: errorFor('phone', v.phone), password: errorFor('password', v.password),
    name: errorFor('name', v.name),
  }), [v]);
  const looksComplete = !errs.phone && !errs.password && !errs.name && agree;

  const set = (k: FieldName) => (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value;
    setV((p) => ({ ...p, [k]: k === 'phone' ? western(raw) : raw }));
    setError('');
  };
  const blur = (k: FieldName) => () => setTouched((p) => ({ ...p, [k]: true }));
  const shown = (k: FieldName) => (touched[k] ? errs[k] : '');

  async function submit(e: FormEvent) {
    e.preventDefault();
    setTouched({ phone: true, password: true, name: true });
    const bad = (Object.keys(v) as FieldName[]).find((k) => errorFor(k, v[k]));
    if (bad) return;
    if (!agree) { setError('وافق على الشروط وسياسة الخصوصية للمتابعة.'); return; }
    setBusy(true);
    setError('');
    try {
      await apply({
        phone: v.phone, name: v.name, password: v.password, referralCode, agreed: agree,
        cvUrl, code,
      });
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof AffiliateRefused ? err.message : 'تعذّر إرسال الطلب.');
    } finally {
      setBusy(false);
    }
  }

  if (submitted) {
    return (
      <div className="flex flex-col gap-3">
        <h2 className="text-2xl leading-tight tracking-tight">وصلنا طلبك</h2>
        <p className="text-sm text-text-secondary">
          سيراجع فريقنا طلبك ويتواصل معك على واتساب بمجرد الموافقة — عادة خلال يوم عمل.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
      <div>
        <h2 className="text-2xl leading-tight tracking-tight">انضم كمسوّق</h2>
        <p className="mt-1 text-sm text-text-secondary">
          طلبك يُراجَع من فريقنا قبل التفعيل — هذا لحماية حسابك وحساباتنا معاً.
        </p>
      </div>

      <Field label="اسمك" required htmlFor="aff-name" error={shown('name')}>
        <Input id="aff-name" name="name" value={v.name} onChange={set('name')}
               onBlur={blur('name')} autoComplete="name" />
      </Field>

      <Field label="رقم الجوال" required htmlFor="aff-phone" error={shown('phone')}>
        <Input id="aff-phone" name="phone" value={v.phone} onChange={set('phone')}
               onBlur={blur('phone')} type="tel" inputMode="tel" dir="ltr"
               autoComplete="tel" placeholder="05XXXXXXXX" />
      </Field>

      <Field label="كلمة المرور" required htmlFor="aff-password" error={shown('password')}>
        <Input id="aff-password" name="password" value={v.password} onChange={set('password')}
               onBlur={blur('password')} type="password" autoComplete="new-password" />
      </Field>

      {/* Present but never required — a self-apply with no referrer becomes a manager
          (services/affiliate-service/app/core/onboarding.py::apply). Pre-filled from `?ref=`
          when a manager's own link carried one. */}
      <Field label="كود الإحالة (اختياري)" htmlFor="aff-ref">
        <Input id="aff-ref" name="referral" value={referralCode}
               onChange={(e) => setReferralCode(e.target.value.trim())} dir="ltr" />
      </Field>

      {/* Optional, never required — a pasted résumé/portfolio link. */}
      <Field label="رابط سيرتك الذاتية (اختياري)" htmlFor="aff-cv">
        <Input id="aff-cv" name="cv_url" value={cvUrl}
               onChange={(e) => setCvUrl(e.target.value.trim())} dir="ltr"
               placeholder="https://..." />
      </Field>

      {/* Sends nothing on most deployments today (AFFILIATE_OTP_DELIVERABLE off, no WhatsApp/SMS
          channel wired) — `requestApplyOtp` says so honestly rather than pretending a code went
          out. Once it can deliver, this becomes the applicant's real proof he owns the number. */}
      <div className="flex flex-col gap-2 rounded-md bg-surface-0 p-3">
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm text-text-secondary">تأكيد رقم جوالك (إن طُلب)</span>
          <Button type="button" variant="ghost" onClick={sendOtp} disabled={otpBusy || otpSent}>
            {otpBusy ? 'جارٍ الإرسال…' : otpSent ? 'أُرسل الرمز' : 'أرسل رمز التحقق'}
          </Button>
        </div>
        {otpSent ? (
          <Input id="aff-otp" name="code" value={code}
                 onChange={(e) => setCode(western(e.target.value))} dir="ltr"
                 inputMode="numeric" placeholder="رمز التحقق" />
        ) : null}
        {otpError ? <p role="alert" className="text-danger text-sm">{otpError}</p> : null}
      </div>

      <AffiliateTerms agree={agree} onChange={setAgree} />

      {error ? <p role="alert" className="text-danger">{error}</p> : null}

      <Button type="submit" disabled={busy || !looksComplete}>
        {busy ? 'جارٍ الإرسال…' : 'إرسال الطلب'}
      </Button>
    </form>
  );
}

/** The consent line — Door.tsx's own Terms component is the shop's equivalent, and points at a
 *  different set of documents entirely, which is why this is its own small component.
 *
 *  SAME FIX AS Door.tsx's OWN `Terms` — this used to point at `raje3.sa/legal/affiliates`, a
 *  domain that does not exist, so nobody could actually read what they were agreeing to. Now
 *  `legalUrl` builds a same-origin link into the console's own public `/legal/:slug` route
 *  (Legal.tsx), which reads `deploy/seed/legal/affiliate-agreement.yaml` and
 *  `affiliate-privacy-policy.yaml` directly — the real published documents, not a summary. */
function AffiliateTerms({ agree, onChange }: { agree: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-start gap-2 text-sm text-text-secondary">
      <input type="checkbox" className="mt-1" checked={agree}
             onChange={(e) => onChange(e.target.checked)} />
      <span>
        أوافق على{' '}
        <a href={legalUrl('affiliate-agreement')} target="_blank" rel="noreferrer" className="text-accent underline">
          شروط برنامج المسوّقين
        </a>{' '}
        و{' '}
        <a href={legalUrl('affiliate-privacy-policy')} target="_blank" rel="noreferrer" className="text-accent underline">
          سياسة الخصوصية
        </a>
        .
      </span>
    </label>
  );
}
