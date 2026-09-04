/**
 * لوحة الإدارة's own door — sign-in, plus a real "forgot password?" now (see AdminSecrets' own
 * neighbour, resetPassword/requestPasswordResetOtp in api.ts). Still no signup, no OTP
 * self-onboarding — a platform-operator account is minted exclusively by
 * `deploy/seed/seed-admin.sh` (or later, a `platform-owner` granting one through this same
 * panel's own team screen — §9.4 of the plan), never a public form. That absence IS the security
 * control, not an oversight: this door has no "become an operator" path to lock down in the
 * first place — recovering an EXISTING account's password is a different concern from minting a
 * new one, and does not reopen it.
 *
 * Reuses `DoorLayout` (product-agnostic canvas) and `rj-ui`'s own Field/Input/Button — never
 * `@base-ui/design-system` (a standing decision: those components are not developed enough
 * — see the plan's own note).
 */
import { useState, type FormEvent } from 'react';
import { Button } from '../rj-ui/Button';
import { Field, Input } from '../rj-ui/Field';
import { DoorLayout } from '../screens/DoorLayout';
import { AdminRefused, requestPasswordResetOtp, resetPassword, signIn, type AdminSession } from './api';

export function AdminDoor({ onSignedIn }: { onSignedIn: (session: AdminSession) => void }) {
  const [forgot, setForgot] = useState(false);
  return forgot
    ? <ForgotPassword onDone={() => setForgot(false)} />
    : <SignIn onSignedIn={onSignedIn} onForgot={() => setForgot(true)} />;
}

function SignIn({ onSignedIn, onForgot }: {
  onSignedIn: (session: AdminSession) => void; onForgot: () => void;
}) {
  // ONE IDENTIFIER FIELD, LABELLED FOR WHAT THIS DEPLOYMENT ACTUALLY USES — this product's own
  // login field is the phone (deploy/services/identity-service.values.yaml pins
  // IDENTITY_LOGIN_FIELD=phone; seed-admin.sh asks for ADMIN_PHONE, never an email), but the
  // field below was still labelled "البريد الإلكتروني" with type="email" — a mismatch nobody
  // hit until someone actually typed a phone number into a field asking for an email. `signIn`
  // itself always sent it as a generic `username`, so nothing server-side needed to change.
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [needsCode, setNeedsCode] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!identifier.trim() || !password) {
      setError('أدخل رقم الجوال وكلمة المرور.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const session = await signIn(identifier.trim(), password, code);
      onSignedIn(session);
    } catch (err) {
      if (err instanceof AdminRefused && err.reason === 'MFA_REQUIRED') {
        setNeedsCode(true);
        setError('أدخل رمز التحقق.');
      } else {
        setError(err instanceof AdminRefused ? err.message : 'تعذّر تسجيل الدخول.');
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <DoorLayout title="لوحة تحكم راجِع" subtitle="دخول فريق الإدارة فقط.">
      <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
        <div>
          <h2 className="text-3xl leading-tight tracking-tight">أهلاً بك</h2>
          <p className="mt-2 text-sm text-text-secondary">رقم جوالك الإداري وكلمة المرور.</p>
        </div>

        <Field label="رقم الجوال" required htmlFor="admin-identifier">
          <Input id="admin-identifier" value={identifier} type="tel" dir="ltr" autoComplete="username"
                 onChange={(e) => { setIdentifier(e.target.value); setError(''); }} />
        </Field>

        <Field label="كلمة المرور" required htmlFor="admin-password">
          <Input id="admin-password" value={password} type="password" autoComplete="current-password"
                 onChange={(e) => { setPassword(e.target.value); setError(''); }} />
        </Field>

        {needsCode ? (
          <Field label="رمز التحقق" required htmlFor="admin-code">
            <Input id="admin-code" value={code} inputMode="numeric" dir="ltr"
                   onChange={(e) => { setCode(e.target.value); setError(''); }} />
          </Field>
        ) : null}

        {error ? <p role="alert" className="text-danger">{error}</p> : null}

        <Button type="submit" disabled={busy} className={identifier && password ? undefined : 'opacity-50'}>
          {busy ? 'جارٍ الدخول…' : 'تسجيل الدخول'}
        </Button>

        <button type="button" onClick={onForgot}
                className="self-center text-sm text-text-secondary underline underline-offset-2 hover:text-text-primary">
          نسيت كلمة المرور؟
        </button>
      </form>
    </DoorLayout>
  );
}

/** ONE SCREEN, code and new password together — matches identity-service's own
 *  `/api/v1/auth/reset-password` shape exactly: a single {identifier, code, new_password} call
 *  that verifies and sets in one step, never a separate "verify" call first (that would consume
 *  the code and leave nothing for the actual reset — see resetPassword's own note in api.ts). */
function ForgotPassword({ onDone }: { onDone: () => void }) {
  const [identifier, setIdentifier] = useState('');
  const [sent, setSent] = useState(false);
  const [code, setCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);

  async function sendCode(e: FormEvent) {
    e.preventDefault();
    if (!identifier.trim()) { setError('أدخل رقم الجوال أولاً.'); return; }
    setBusy(true);
    setError('');
    try {
      await requestPasswordResetOtp(identifier.trim());
      // NO ORACLE — this message shows whether or not the number is a real admin account, on
      // purpose (same reasoning as sign-in's own single refusal sentence).
      setNotice('لو الرقم يخص حساب إدارة، وصله رمز عبر واتساب الآن.');
      setSent(true);
    } catch {
      setError('تعذّر إرسال الطلب. حاول مرة أخرى.');
    } finally {
      setBusy(false);
    }
  }

  async function submitReset(e: FormEvent) {
    e.preventDefault();
    if (!code.trim() || newPassword.length < 12) {
      setError('أدخل الرمز، وكلمة مرور 12 حرفاً فأكثر.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      await resetPassword(identifier.trim(), code.trim(), newPassword);
      setNotice('تم تعيين كلمة المرور. سجّل دخولك بها الآن.');
      setTimeout(onDone, 1500);
    } catch (err) {
      setError(err instanceof AdminRefused ? err.message : 'تعذّرت إعادة التعيين.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <DoorLayout title="لوحة تحكم راجِع" subtitle="استعادة كلمة مرور الإدارة.">
      <form onSubmit={sent ? submitReset : sendCode} className="flex flex-col gap-4" noValidate>
        <div>
          <h2 className="text-3xl leading-tight tracking-tight">نسيت كلمة المرور؟</h2>
          <p className="mt-2 text-sm text-text-secondary">
            {sent ? 'أدخل الرمز اللي وصلك عبر واتساب، وكلمة مرور جديدة.'
                  : 'أدخل رقم جوال حساب الإدارة — يوصلك رمز عبر واتساب.'}
          </p>
        </div>

        <Field label="رقم الجوال" required htmlFor="reset-identifier">
          <Input id="reset-identifier" value={identifier} type="tel" dir="ltr" disabled={sent}
                 onChange={(e) => { setIdentifier(e.target.value); setError(''); }} />
        </Field>

        {sent ? (
          <>
            <Field label="رمز التحقق" required htmlFor="reset-code">
              <Input id="reset-code" value={code} inputMode="numeric" dir="ltr"
                     onChange={(e) => { setCode(e.target.value); setError(''); }} />
            </Field>
            <Field label="كلمة المرور الجديدة" required htmlFor="reset-new-password">
              <Input id="reset-new-password" value={newPassword} type="password" autoComplete="new-password"
                     onChange={(e) => { setNewPassword(e.target.value); setError(''); }} />
            </Field>
          </>
        ) : null}

        {notice ? <p className="text-sm text-text-secondary">{notice}</p> : null}
        {error ? <p role="alert" className="text-danger">{error}</p> : null}

        <Button type="submit" disabled={busy}>
          {busy ? 'جارٍ التنفيذ…' : sent ? 'تعيين كلمة المرور' : 'إرسال رمز التحقق'}
        </Button>

        <button type="button" onClick={onDone}
                className="self-center text-sm text-text-secondary underline underline-offset-2 hover:text-text-primary">
          رجوع لتسجيل الدخول
        </button>
      </form>
    </DoorLayout>
  );
}
