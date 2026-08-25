/**
 * لوحة الإدارة's own door — sign-in ONLY. No signup, no "forgot password" self-service, no OTP
 * self-onboarding — a platform-operator account is minted exclusively by
 * `deploy/seed/seed-admin.sh` (or later, a `platform-owner` granting one through this same
 * panel's own team screen — §٩.٤ of the plan), never a public form. That absence IS the security
 * control, not an oversight: this door has no "become an operator" path to lock down in the
 * first place.
 *
 * Reuses `DoorLayout` (product-agnostic canvas) and `rj-ui`'s own Field/Input/Button — never
 * `@base-ui/design-system` (a standing decision: those components are not developed enough
 * — see the plan's own note).
 */
import { useState, type FormEvent } from 'react';
import { Button } from '../rj-ui/Button';
import { Field, Input } from '../rj-ui/Field';
import { DoorLayout } from '../screens/DoorLayout';
import { AdminRefused, signIn, type AdminSession } from './api';

export function AdminDoor({ onSignedIn }: { onSignedIn: (session: AdminSession) => void }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [needsCode, setNeedsCode] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!email.trim() || !password) {
      setError('أدخل البريد وكلمة المرور.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const session = await signIn(email.trim(), password, code);
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
          <p className="mt-2 text-sm text-text-secondary">بريدك الإداري وكلمة المرور.</p>
        </div>

        <Field label="البريد الإلكتروني" required htmlFor="admin-email">
          <Input id="admin-email" value={email} type="email" dir="ltr" autoComplete="username"
                 onChange={(e) => { setEmail(e.target.value); setError(''); }} />
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

        <Button type="submit" disabled={busy} className={email && password ? undefined : 'opacity-50'}>
          {busy ? 'جارٍ الدخول…' : 'تسجيل الدخول'}
        </Button>
      </form>
    </DoorLayout>
  );
}
