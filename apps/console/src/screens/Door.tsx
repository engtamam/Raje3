/**
 * The door — sign in, or open a shop.
 *
 * BUILT FROM THE KIT'S PRIMITIVES — `Field`, `Input`, `Button`, `Segmented`, `OtpVerify` — and
 * NOT from its two assembled auth forms, for one reason each:
 *
 *   `LoginForm` hardcodes `type="email"` on the identifier, so a browser refuses a phone number
 *   before any of our code runs (see SignInPane).
 *
 *   `SignupForm` asks a person's name and an email and offers a company/individual toggle — five
 *   values where we ask three, one of them an address an owner may not have.
 *
 * The canvas is ours too (DoorLayout), and that file says why.
 *
 * ────────────────────────────────────────────────────────────────────────────────────────────
 * FOUR THINGS THIS FORM DOES THAT A PLAIN ONE DOES NOT, and each is a real failure it prevents:
 *
 *   PER-FIELD ERRORS. One message under a form of four inputs makes the person guess which one is
 *   wrong. The rules mirror the server's exactly — a client rule the server does not have is a
 *   refusal for no reason, and a server rule the client does not have is a round trip to learn it.
 *
 *   THE PASSWORD RULES ARE SHOWN AND TICK OFF AS HE TYPES. Twelve characters is a long password;
 *   telling him so AFTER he presses the button is how a signup is abandoned.
 *
 *   THE CONSENT BOX, WITH LINKS. Not decoration: PDPL Art. 6 wants a consent that is informed and
 *   demonstrable, and a person who could not read the document before agreeing did neither. It
 *   gates the button, and the version-pinned RECORD is written by the legal gate the moment he is
 *   inside — see LegalGate.tsx for why the recording lives there and not here.
 *
 *   THE NUMBER IS PROVEN. His phone is his identity in this product AND the channel we message
 *   him on; an unproven identifier is not an identity. The code arrives on WhatsApp, which is the
 *   channel he is about to connect anyway — no SMS contract, no second vendor.
 */
import { useEffect, useMemo, useState, type ChangeEvent, type FormEvent } from 'react';
import { OtpVerify } from '@base-ui/auth/OtpVerify';
import { Button } from '@base-ui/design-system/Button';
import { Field, Input } from '@base-ui/design-system/Field';
import { Segmented } from '@base-ui/design-system/Segmented';
import { hasFailed, isLoading } from '../loading';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import { Check, Eye, EyeOff } from 'lucide-react';
import { DoorLayout } from './DoorLayout';
import {
  openShop, requestCode, signIn, verifyCode, affiliateRefFromUrl, AGREED_KEY, WELCOME_TRIAL_KEY, Refused,
} from '../auth';
import { sentenceFor } from '../api';
import type { Session } from '../session';
import { western } from '../digits';

/**
 * A password field with a real show/hide toggle — reported directly: neither pane offered any
 * way to check what he had actually typed, on a form whose whole point (§ the twelve-character
 * rule above) is that a wrong keystroke is easy to make and easy to miss while the field masks
 * it. One eye icon inside the box, never a second control competing for the label's own space.
 */
function PasswordInput({ id, name, value, onChange, onBlur, autoComplete }: {
  id: string;
  name: string;
  value: string;
  onChange: (e: ChangeEvent<HTMLInputElement>) => void;
  onBlur?: () => void;
  autoComplete: string;
}) {
  const [shown, setShown] = useState(false);
  return (
    <div className="relative">
      <Input
        id={id} name={name} value={value} onChange={onChange} onBlur={onBlur}
        type={shown ? 'text' : 'password'} autoComplete={autoComplete}
        className="pe-10"
      />
      <button
        type="button"
        onClick={() => setShown((v) => !v)}
        aria-label={shown ? 'إخفاء كلمة المرور' : 'إظهار كلمة المرور'}
        className="absolute inset-y-0 end-0 grid w-10 place-items-center text-text-secondary"
      >
        {shown ? <EyeOff size={18} aria-hidden /> : <Eye size={18} aria-hidden />}
      </button>
    </div>
  );
}

export function Door({ onSignedIn }: { onSignedIn: (s: Session) => void }) {
  const [mode, setMode] = useState<'in' | 'new'>('in');

  return (
    <DoorLayout>
      <div className="flex flex-col gap-6">
        <Segmented
          // FULL WIDTH, SPLIT EVENLY, NEVER WRAPPED. The kit's Segmented is
          // `inline-flex flex-wrap`, which on a phone stacks two long Arabic labels into a
          // ragged block half the screen wide. It takes a className and merges with
          // tailwind-merge, so this is a fix at the call site rather than a fork of the kit.
          className="flex w-full [&>button]:flex-1 [&>button]:whitespace-nowrap"
          options={[
            { value: 'in', label: 'تسجيل الدخول' },
            { value: 'new', label: 'تسجيل جديد' },
          ]}
          value={mode}
          onChange={setMode}
        />
        {mode === 'in'
          ? <SignInPane onSignedIn={onSignedIn} />
          : <NewShopPane onSignedIn={onSignedIn} />}
      </div>
    </DoorLayout>
  );
}

type Proving = { phone: string; password: string; problem: string };

/**
 * «أكّد رقمك» — the one refusal that is a STEP rather than an error, shared by both doors.
 *
 * IT LIVED IN THE SIGN-IN PANE ALONE (م · قاطع). Opening a shop ends by signing in, and when the
 * server answers `unverified` the new-shop pane simply printed the sentence on a form with no code
 * field anywhere on it. The account exists, his number is spoken for, and there is no way forward
 * from that screen — while the pane beside it has handled exactly this correctly all along.
 */
async function proveStep(phone: string, password: string): Promise<Proving> {
  let problem = '';
  try {
    await requestCode(phone);
  } catch (sendErr) {
    problem = sentenceFor(sendErr, 'تعذّر إرسال الرمز.');
  }
  return { phone, password, problem };
}

function needsProof(err: unknown): boolean {
  return err instanceof Refused && err.reason === 'unverified';
}

function ProveNumber(
  { proving, setProving, onSignedIn }:
  { proving: Proving; setProving: (p: Proving) => void; onSignedIn: (s: Session) => void },
) {
  return (
    <>
      {proving.problem ? (
        <p role="alert" className="mb-4 rounded-card bg-surface-1 p-4 text-danger shadow-sm">
          {proving.problem}
        </p>
      ) : null}
      <OtpVerify
        title="أكّد رقمك"
        sentTo={proving.phone}
        onVerify={async (code) => {
          await verifyCode(proving.phone, code);
          onSignedIn(await signIn(proving.phone, proving.password));
        }}
        // ONE PLACE FOR ONE MESSAGE. The banner exists for a send that failed BEFORE this screen
        // rendered — there is no other surface for that. A RESEND has one: the component's own
        // error, under the input where the person is looking. Setting both showed the sentence
        // twice, which reads as two separate faults.
        onResend={async () => {
          setProving({ ...proving, problem: '' });
          await requestCode(proving.phone);
        }}
        mapError={otpError}
      />
    </>
  );
}


function SignInPane({ onSignedIn }: { onSignedIn: (s: Session) => void }) {
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  /** Set when the server says this number was never proven — see the catch below. */
  const [proving, setProving] = useState<{ phone: string; password: string; problem: string } | null | undefined>(undefined);

  /**
   * OUR OWN FIELDS, AND THE KIT'S `LoginForm` DELIBERATELY UNUSED.
   *
   * It hardcodes `type="email"` on the identifier — reasonable for a kit whose default login field
   * is an address, and wrong the moment a deployment sets IDENTITY_LOGIN_FIELD=phone. The browser
   * then refuses the form itself, in English, on an Arabic screen: "Please include an '@' in the
   * email address. '0505536720' is missing an '@'." Nothing in our code runs; the validation is the
   * browser's, so no `mapError` can reach it.
   *
   * platform/ is read-only, so this is composed from the same primitives instead — the loss is one
   * screen's worth of markup, and the gain is a field that is what it says it is.
   */
  /**
   * READ FROM THE FORM, NOT FROM STATE — and this is the autofill trap, which had this screen
   * showing a filled form under a dead button.
   *
   * A password manager writes into the input directly. The DOM has the value, the user can see it,
   * and React's `onChange` never fires — so `phone` and `password` are still empty strings. Any
   * button gated on them stays disabled over a form that looks complete, and the person has no
   * move: he did fill it in.
   *
   * So the values are taken from the submitted form, which is where they actually are, and the
   * button is disabled only while a request is in flight.
   */
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
      onSignedIn(await signIn(typedPhone, typedPassword));
    } catch (err) {
      // THE ONE REFUSAL THAT IS A STEP. He signed up, closed the tab on the code screen, and came
      // back. Sending a fresh code and showing it to him is the whole remedy — leaving him on a
      // login form holding a sentence about a code nobody sent is not.
      if (needsProof(err)) {
        setProving(await proveStep(typedPhone, typedPassword));
        return;
      }
      setError(sentenceFor(err, 'تعذّر تسجيل الدخول.'));
    } finally {
      setBusy(false);
    }
  }

  if (proving) {
    return <ProveNumber proving={proving} setProving={setProving} onSignedIn={onSignedIn} />;
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
      <div>
        <h2 className="text-3xl leading-tight tracking-tight">أهلاً بك</h2>
        <p className="mt-2 text-sm text-text-secondary">رقم جوالك وكلمة المرور.</p>
      </div>

      <Field label="رقم الجوال" required htmlFor="in-phone">
        <Input
          id="in-phone" name="phone" value={phone}
          onChange={(e) => { setPhone(western(e.target.value)); setError(''); }}
          type="tel" inputMode="tel" dir="ltr" autoComplete="username" placeholder="05XXXXXXXX"
        />
      </Field>

      <Field label="كلمة المرور" required htmlFor="in-password">
        <PasswordInput
          id="in-password" name="password" value={password}
          onChange={(e) => { setPassword(e.target.value); setError(''); }}
          autoComplete="current-password"
        />
      </Field>

      {error ? <p role="alert" className="text-danger">{error}</p> : null}

      {/* DIMMED BUT NEVER DISABLED, and this pane is the one place that distinction earns its
          keep: a password manager fills both fields without firing React's onChange, so the state
          reads empty over a form that plainly is not (see `submit`). Disabling here would leave a
          returning owner staring at a dead button above his own saved credentials.
          The dimming is the kit's own `disabled:opacity-50`, applied by hand — the same "not yet"
          the rest of the product uses, without the dead end. */}
      <Button
        type="submit"
        disabled={busy}
        className={phone && password ? undefined : 'opacity-50'}
      >
        {busy ? 'جارٍ الدخول…' : 'تسجيل الدخول'}
      </Button>
    </form>
  );
}

/**
 * What went wrong on the code screen — READ, never assumed.
 *
 * `OtpVerify` runs BOTH its buttons through one `mapError`, and this was a fixed sentence: so
 * pressing «إرسال الرمز مرة أخرى» inside the one-minute cooldown answered «الرمز غير صحيح أو
 * انتهت صلاحيته» about a code the person had not typed yet. He is told his code is wrong while
 * being refused a new one — a dead end built out of two correct behaviours.
 *
 * The server writes a sentence for every refusal it makes (the cooldown says to wait), so the
 * honest thing is to show what it said and keep a default only for the case where nothing spoke.
 */
function otpError(e: unknown): string {
  return e instanceof Error && e.message
    ? e.message
    : 'تعذّر إكمال الطلب. حاول مرة أخرى.';
}

// ── the rules, mirrored from the server ────────────────────────────────────────────────────────

type FieldName = 'phone' | 'password' | 'shopName';

/**
 * `0501234567`, `+966501234567` and `966501234567` are ONE human, folded the same way identity and
 * our own phone index fold them. Returns null when it is not a Saudi mobile at all.
 */
function normalizePhone(raw: string): string | null {
  const digits = (raw || '').replace(/[\s\-()]/g, '').replace(/^00/, '+');
  const national = digits.startsWith('+966') ? digits.slice(4)
    : digits.startsWith('966') ? digits.slice(3)
    : digits.startsWith('0') ? digits.slice(1)
    : digits;
  return /^5\d{8}$/.test(national) ? `+966${national}` : null;
}

/**
 * TWELVE, BECAUSE THE SERVER SAYS TWELVE (identity's PASSWORD_MIN_LENGTH). This account can
 * connect a WhatsApp number and message thousands of people in a shop's name, which is the reason
 * the deployment raised it above the platform's default — so the form must not offer a shorter one
 * and then be refused.
 */
const PW_RULES: { label: string; ok: (v: string) => boolean }[] = [
  { label: '12 حرفاً على الأقل', ok: (v) => v.length >= 12 },
  { label: 'حرف كبير', ok: (v) => /[A-Z]/.test(v) },
  { label: 'رقم', ok: (v) => /\d/.test(v) },
  { label: 'رمز', ok: (v) => /[^A-Za-z0-9]/.test(v) },
];

function errorFor(f: FieldName, v: string): string {
  switch (f) {
    case 'phone':
      return normalizePhone(v) ? '' : 'أدخل رقم جوال سعودي — مثل 0501234567';
    case 'password':
      return PW_RULES.every((r) => r.ok(v)) ? '' : 'كلمة المرور لا تحقق الشروط أدناه';
    case 'shopName':
      return v.trim().length >= 2 ? '' : 'أدخل اسم المحل';
  }
}

function NewShopPane({ onSignedIn }: { onSignedIn: (s: Session) => void }) {
  const [proving, setProving] = useState<Proving | null>(null);
  const [v, setV] = useState<Record<FieldName, string>>({ phone: '', password: '', shopName: '' });
  const [touched, setTouched] = useState<Partial<Record<FieldName, boolean>>>({});
  const [agree, setAgree] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  // CARRIED FROM THE FIRST CALL THROUGH A POSSIBLE «أكّد رقمك» DETOUR — see auth.ts's own note
  // on `openShop`: the shop and its trial already exist the moment sign-in itself refuses.
  const [trialEnd, setTrialEnd] = useState(0);

  function markWelcome(end: number) {
    if (!end) return;
    try { sessionStorage.setItem(WELCOME_TRIAL_KEY, String(end)); } catch { /* private mode */ }
  }

  const errs = useMemo(() => ({
    phone: errorFor('phone', v.phone),
    password: errorFor('password', v.password),
    shopName: errorFor('shopName', v.shopName),
  }), [v]);

  /** What the state can see. Never a gate — only the button's appearance; see the button. */
  /**
   * THE SHOP NAME IS NOT THE PASSWORD, and this is a cross-field check because no single field
   * can see it. A manager that fills the name with the generated password produces a form where
   * every field is individually valid — and the result is printed in large type on the page the
   * shop's customers open, and sent inside every WhatsApp message it signs.
   */
  const nameIsPassword = v.shopName.length > 0 && v.shopName === v.password;

  const looksComplete = !nameIsPassword && !errs.phone && !errs.password && !errs.shopName
    && agree;

  const set = (k: FieldName) => (e: React.ChangeEvent<HTMLInputElement>) => {
    // FOLD THE PHONE, AND ONLY FOLD IT. `western` changes the script of a digit and removes
    // nothing, which is the right strength at a boundary whose accepted format is not ours:
    // identity-service owns it, and a leading `+` is legitimate there. Stripping would be us
    // deciding what a valid number looks like on somebody else's behalf.
    //
    // WITHOUT THIS HE CANNOT GET IN AT ALL. A number typed on an Arabic keyboard is not the
    // number we hold, so the sign-in is refused — and the message he reads blames his phone or
    // his password. He is locked out of his own product by a keyboard setting, with our text
    // telling him he got his own number wrong.
    const raw = e.target.value;
    setV((p) => ({ ...p, [k]: k === 'phone' ? western(raw) : raw }));
    setError('');
  };
  const blur = (k: FieldName) => () => setTouched((p) => ({ ...p, [k]: true }));
  const shown = (k: FieldName) => (touched[k] ? errs[k] : '');

  async function submit(e: FormEvent) {
    e.preventDefault();
    setTouched({ phone: true, password: true, shopName: true });
    // SAME AUTOFILL TRAP AS THE SIGN-IN PANE — a password manager fills the inputs without firing
    // React's onChange, so the state these rules read is empty while the form on screen is not.
    // Whatever the browser put in the fields is adopted before anything is judged.
    const data = new FormData(e.currentTarget as HTMLFormElement);
    const filled: Record<FieldName, string> = {
      phone: String(data.get('phone') ?? '') || v.phone,
      password: String(data.get('password') ?? '') || v.password,
      shopName: String(data.get('shopName') ?? '') || v.shopName,
    };
    if (filled.phone !== v.phone || filled.password !== v.password
        || filled.shopName !== v.shopName) {
      setV(filled);
    }
    const bad = (Object.keys(filled) as FieldName[]).find((k) => errorFor(k, filled[k]));
    if (bad) return;
    if (!agree) { setError('وافق على الشروط وسياسة الخصوصية للمتابعة.'); return; }
    setBusy(true);
    setError('');
    try {
      // NO TRADE IS ASKED FOR. Sign-up used to open on «نوع النشاط», and that one answer seeded a
      // service catalogue and a rewards table guessed from a business we had never seen — wrong on
      // its first day for any shop that did two things. A shop now starts empty and its owner
      // writes what he actually sells; whether he works on cars is a checkbox in «منشأتي» that he
      // can change the day his work changes.
      // ONE SIGN-IN, NOT TWO — `openShop` already walks him through the door itself (auth.ts's
      // own doc comment says so); this pane used to discard that session and ask again.
      const opened = await openShop({
        phone: filled.phone, password: filled.password, shopName: filled.shopName,
        // WHICH MARKETER'S LINK HE ARRIVED ON, IF ANY — read once, silently, from `?aff=`; see
        // auth.ts's own note on why this is never a field he fills in himself.
        affiliateRef: affiliateRefFromUrl(),
      });
      // HE AGREED HERE, against links to the documents. The legal gate records the version-pinned
      // acceptance the moment he is inside; this marker is what stops it asking the same question
      // twice in thirty seconds. Keyed by the number so a shared phone cannot carry one person's
      // consent into another person's account.
      try {
        localStorage.setItem(AGREED_KEY, normalizePhone(filled.phone) ?? '');
      } catch { /* private mode — the gate simply asks, which is the safe direction */ }

      markWelcome(opened.trialEnd);
      onSignedIn(opened.session);
    } catch (err) {
      // THE SAME REFUSAL, THE SAME STEP — and this pane used to answer it with a sentence on a
      // form that has no code field anywhere on it (م · قاطع). The account exists by then, his
      // number is spoken for, and «أكّد رقمك» with nowhere to type it is a locked door he built
      // himself. The pane beside this one has handled it correctly since it was written.
      if (needsProof(err)) {
        // THE TRIAL ALREADY OPENED — carried on the thrown error itself (auth.ts's own note),
        // since the shop and its trial exist by the time sign-in alone is what refused.
        setTrialEnd(Number((err as { trialEnd?: number }).trialEnd) || 0);
        setProving(await proveStep(filled.phone, filled.password));
        return;
      }
      setError(sentenceFor(err, 'تعذّر إنشاء الحساب.'));
    } finally {
      setBusy(false);
    }
  }

  if (proving) {
    return <ProveNumber proving={proving} setProving={setProving}
                        onSignedIn={(s) => { markWelcome(trialEnd); onSignedIn(s); }} />;
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
      <h2 className="text-xl">افتح محلك</h2>

      <Field label="رقم الجوال" required htmlFor="phone" error={shown('phone')}>
        <Input
          id="phone" name="phone" value={v.phone} onChange={set('phone')} onBlur={blur('phone')}
          type="tel" inputMode="tel" dir="ltr" autoComplete="tel" placeholder="05XXXXXXXX"
        />
      </Field>

      <Field label="كلمة المرور" required htmlFor="password" error={shown('password')}>
        <PasswordInput
          id="password" name="password" value={v.password} onChange={set('password')}
          onBlur={blur('password')}
          autoComplete="new-password"
        />
      </Field>

      {/* THE RULES, TICKING OFF AS HE TYPES — and only once he has started, so an untouched form is
          not a list of complaints. Twelve characters announced after the button is a signup lost. */}
      {v.password.length > 0 || touched.password ? (
        <ul className="-mt-2 grid grid-cols-2 gap-1">
          {PW_RULES.map((r) => {
            const ok = r.ok(v.password);
            return (
              <li key={r.label}
                  className={`flex items-center gap-1.5 text-xs ${ok ? 'text-success' : 'text-text-secondary'}`}>
                <span aria-hidden>{ok ? '✓' : '○'}</span> {r.label}
              </li>
            );
          })}
        </ul>
      ) : null}

      <Field label="اسم المحل" required htmlFor="shop" error={shown('shopName')}>
        {/* `organization` IS THE FIX FOR A REAL ACCIDENT. With no autocomplete hint a password
            manager sees a bare text input sitting after a new-password field and fills it with
            the password it just generated — the owner in the screenshot found «Cacad$453453»
            printed as his shop name on the page his customers see. Naming the field tells every
            manager what belongs in it. */}
        <Input id="shop" name="shopName" value={v.shopName} onChange={set('shopName')}
               autoComplete="organization" onBlur={blur('shopName')} />
        {nameIsPassword ? (
          <p className="text-sm text-danger">
            هذا اسم محلّك كما يراه عملاؤك — ويبدو أنه كلمة مرورك. اكتب اسم المحل.
          </p>
        ) : null}
      </Field>

      {/* THREE VALUES, ALL ABOUT HIM. There used to be a fourth — «نوع النشاط» — and it was the
          only one that was not: it existed so we could seed a catalogue guessed from his trade.
          A guess is wrong on its first day for any shop that does two things, and correcting it
          means deleting our guesses one by one, so the shop starts empty and he writes what he
          sells. Whether he works on cars is a checkbox in «منشأتي», where he can change it. */}

      <Terms agree={agree} onChange={setAgree} />

      {error ? <p role="alert" className="text-danger">{error}</p> : null}

      {/* GENUINELY DISABLED UNTIL THE FORM IS COMPLETE, and here that is safe — which it is not on
          the sign-in pane.
          The autofill trap needs the browser to fill EVERY gate silently. It cannot here: the
          consent box is a click nobody's password manager makes. So `looksComplete` is false only
          when the form really is incomplete.
          The `soft` variant was tried and is wrong for this — it is `bg-accent-soft`, a bright
          wash meant for a secondary ACTION, so it read as a second, louder button. Disabled uses
          the kit's own dimming (`disabled:opacity-50` on solid), which is what "not yet" looks
          like everywhere else in the product. */}
      <Button type="submit" disabled={busy || !looksComplete}>
        {busy ? 'جارٍ الإنشاء…' : 'ابدأ'}
      </Button>
    </form>
  );
}


/**
 * The consent line.
 *
 * THE LINKS OPEN IN A NEW TAB so a half-filled form is never lost, and they point at the PUBLISHED
 * documents rather than at a summary — a person who agreed to a paraphrase agreed to nothing.
 *
 * THE TARGET IS CONFIGURATION because a pre-session reader cannot fetch them from us:
 * compliance-service serves every legal read behind a capability, which is right for the in-app
 * viewer and leaves nothing for the one reader who most needs it — the one deciding whether to
 * sign up at all. Raised upstream; until then this points at the published pages.
 */
function Terms({ agree, onChange }: { agree: boolean; onChange: (v: boolean) => void }) {
  const base = (import.meta.env.VITE_LEGAL_BASE ?? 'https://raje3.sa/legal').replace(/\/$/, '');
  return (
    <label className="flex items-start gap-2 text-sm text-text-secondary">
      <input
        type="checkbox" className="mt-1" checked={agree}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span>
        أوافق على{' '}
        <a href={`${base}/terms`} target="_blank" rel="noreferrer" className="text-accent underline">
          شروط الاستخدام
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
