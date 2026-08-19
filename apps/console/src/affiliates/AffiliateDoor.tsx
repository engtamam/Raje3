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
 *   THREE DOORS, NOT TWO. «تسجيل الدخول» and «تقديم طلب» are Door.tsx's own «in»/«new» split; the
 *   third, «قبول دعوة», exists only here — a manager-sent invite (spec: a manager can invite a
 *   promoter directly) has no shop-door equivalent at all. It opens automatically on a link
 *   carrying `?invite=`, so nobody has to find a segmented control to use a link they were sent.
 *
 * NO OTP HERE, unlike Door.tsx's own SignInPane/NewShopPane. The shop's number-proof step exists
 * because operations binds WhatsApp sending to that exact number (core/signup.py's own «أكّد
 * رقمك»); affiliate-service has no such binding yet, so there is nothing here to prove. Revisit
 * this the day the portal sends anything on a marketer's behalf.
 */
import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Button } from '@base-ui/design-system/Button';
import { Field, Input } from '@base-ui/design-system/Field';
import { Segmented } from '@base-ui/design-system/Segmented';
import { DoorLayout } from '../screens/DoorLayout';
import { western } from '../digits';
import { acceptInvite, AffiliateRefused, apply, signIn, type AffiliateSession } from './api';

type Mode = 'in' | 'new' | 'invite';

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
  const inviteToken = params.get('invite') ?? '';
  // A `?ref=` LINK IS A REFERRAL, NOT A LOGIN — a manager sharing AffiliateHome's own "لدعوة
  // مسوّق تحتك" link means "apply", and landing whoever clicks it on the sign-in pane (which
  // has nowhere to even show the referral code) would bury the one thing the link was for.
  const [mode, setMode] = useState<Mode>(
    inviteToken ? 'invite' : params.get('ref') ? 'new' : 'in');

  return (
    <DoorLayout
      title="عمولتك تكبر وأنت نائم."
      subtitle="راجِع يدفع لك عن كل منشأة تحضرها للمنصة — عمولة مستمرة، من أول يوم توقّعه، بلا سقف."
    >
      <div className="flex flex-col gap-6">
        {inviteToken ? null : (
          <Segmented
            className="flex w-full [&>button]:flex-1 [&>button]:whitespace-nowrap"
            options={[
              { value: 'in', label: 'تسجيل الدخول' },
              { value: 'new', label: 'تقديم طلب' },
            ]}
            value={mode === 'invite' ? 'in' : mode}
            onChange={(v) => setMode(v as Mode)}
          />
        )}
        {mode === 'in' && <SignInPane onSignedIn={onSignedIn} />}
        {mode === 'new' && <ApplyPane />}
        {mode === 'invite' && <AcceptInvitePane token={inviteToken} onActivated={() => setMode('in')} />}
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
  const [agree, setAgree] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [submitted, setSubmitted] = useState(false);

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
      await apply({ phone: v.phone, name: v.name, password: v.password, referralCode, agreed });
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
          when a promoter's own link carried one. */}
      <Field label="كود الإحالة (اختياري)" htmlFor="aff-ref">
        <Input id="aff-ref" name="referral" value={referralCode}
               onChange={(e) => setReferralCode(e.target.value.trim())} dir="ltr" />
      </Field>

      <AffiliateTerms agree={agree} onChange={setAgree} />

      {error ? <p role="alert" className="text-danger">{error}</p> : null}

      <Button type="submit" disabled={busy || !looksComplete}>
        {busy ? 'جارٍ الإرسال…' : 'إرسال الطلب'}
      </Button>
    </form>
  );
}

function AcceptInvitePane({ token, onActivated }: { token: string; onActivated: () => void }) {
  const [password, setPassword] = useState('');
  const [touched, setTouched] = useState(false);
  const [agree, setAgree] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [activated, setActivated] = useState(false);

  const err = errorFor('password', password);

  useEffect(() => {
    if (!token) setError('رابط الدعوة غير صالح.');
  }, [token]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (err) return;
    if (!agree) { setError('وافق على الشروط وسياسة الخصوصية للمتابعة.'); return; }
    setBusy(true);
    setError('');
    try {
      await acceptInvite(token, password, agree);
      // NO TOKEN COMES BACK FROM ACCEPTING — identity's own claim step returns the PERSON, not a
      // session (see identity-service's own /person/claim). Same shape as openShop in Door.tsx:
      // the account exists now, and the ordinary sign-in pane this hands him to is one call away
      // — with the phone he already knows, which this screen never even asked for.
      setActivated(true);
    } catch (e2) {
      setError(e2 instanceof AffiliateRefused ? e2.message : 'تعذّر قبول الدعوة.');
    } finally {
      setBusy(false);
    }
  }

  if (activated) {
    return (
      <div className="flex flex-col gap-4">
        <div>
          <h2 className="text-2xl leading-tight tracking-tight">تم تفعيل حسابك</h2>
          <p className="mt-1 text-sm text-text-secondary">سجّل الدخول برقم جوالك وكلمة المرور اللي اخترتها.</p>
        </div>
        <Button type="button" onClick={onActivated}>تسجيل الدخول</Button>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
      <div>
        <h2 className="text-2xl leading-tight tracking-tight">دُعيت للانضمام</h2>
        <p className="mt-1 text-sm text-text-secondary">اختر كلمة مرورك لتفعيل حسابك.</p>
      </div>

      <Field label="كلمة المرور" required htmlFor="aff-invite-password"
            error={touched ? err : ''}>
        <Input id="aff-invite-password" name="password" value={password}
               onChange={(e) => { setPassword(e.target.value); setError(''); }}
               onBlur={() => setTouched(true)} type="password" autoComplete="new-password" />
      </Field>

      {/* spec §2 — HIS agreement, not the manager who invited him. A manager's own consent when
          HE applied cannot stand in for the person he invited; see onboarding.py::accept_invite
          for the server-side half of this same rule. */}
      <AffiliateTerms agree={agree} onChange={setAgree} />

      {error ? <p role="alert" className="text-danger">{error}</p> : null}

      <Button type="submit" disabled={busy || !token}>
        {busy ? 'جارٍ التفعيل…' : 'تفعيل الحساب'}
      </Button>
    </form>
  );
}

/** The consent line — shared by ApplyPane and AcceptInvitePane, since both are moments a NEW
 *  person is agreeing for the first time (Door.tsx's own Terms component is the shop's
 *  equivalent, and points at a different set of documents entirely — see this module's own
 *  header note on why this is not that component reused). */
function AffiliateTerms({ agree, onChange }: { agree: boolean; onChange: (v: boolean) => void }) {
  const base = (import.meta.env.VITE_AFFILIATE_LEGAL_BASE ?? 'https://raje3.sa/legal/affiliates')
    .replace(/\/$/, '');
  return (
    <label className="flex items-start gap-2 text-sm text-text-secondary">
      <input type="checkbox" className="mt-1" checked={agree}
             onChange={(e) => onChange(e.target.checked)} />
      <span>
        أوافق على{' '}
        <a href={`${base}/terms`} target="_blank" rel="noreferrer" className="text-accent underline">
          شروط برنامج المسوّقين
        </a>{' '}
        و{' '}
        <a href={`${base}/privacy`} target="_blank" rel="noreferrer" className="text-accent underline">
          سياسة الخصوصية
        </a>
        .
      </span>
    </label>
  );
}
