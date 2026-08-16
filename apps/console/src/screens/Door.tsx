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
 *   values where we ask four, one of them an address an owner may not have, and none of them the
 *   sector his catalogue is seeded from.
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
import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { OtpVerify } from '@base-ui/auth/OtpVerify';
import { Button } from '@base-ui/design-system/Button';
import { Field, Input } from '@base-ui/design-system/Field';
import { Segmented } from '@base-ui/design-system/Segmented';
import { hasFailed, isLoading } from '../loading';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import { Check } from 'lucide-react';
import { DoorLayout } from './DoorLayout';
import { openShop, requestCode, signIn, verifyCode, AGREED_KEY, Refused } from '../auth';
import { listSectors, sentenceFor, type Sector } from '../api';
import type { Session } from '../session';

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
            { value: 'new', label: 'محل جديد' },
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
      if (err instanceof Refused && err.reason === 'unverified') {
        let problem = '';
        try {
          await requestCode(typedPhone);
        } catch (sendErr) {
          problem = sentenceFor(sendErr, 'تعذّر إرسال الرمز.');
        }
        setProving({ phone: typedPhone, password: typedPassword, problem });
        return;
      }
      setError(sentenceFor(err, 'تعذّر تسجيل الدخول.'));
    } finally {
      setBusy(false);
    }
  }

  if (proving) {
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

  return (
    <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
      <div>
        <h2 className="text-3xl leading-tight tracking-tight">أهلاً بك</h2>
        <p className="mt-2 text-sm text-text-secondary">رقم جوالك وكلمة المرور.</p>
      </div>

      <Field label="رقم الجوال" required htmlFor="in-phone">
        <Input
          id="in-phone" name="phone" value={phone}
          onChange={(e) => { setPhone(e.target.value); setError(''); }}
          type="tel" inputMode="tel" dir="ltr" autoComplete="username" placeholder="05XXXXXXXX"
        />
      </Field>

      <Field label="كلمة المرور" required htmlFor="in-password">
        <Input
          id="in-password" name="password" value={password}
          onChange={(e) => { setPassword(e.target.value); setError(''); }}
          type="password" autoComplete="current-password"
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
  const [v, setV] = useState<Record<FieldName, string>>({ phone: '', password: '', shopName: '' });
  const [touched, setTouched] = useState<Partial<Record<FieldName, boolean>>>({});
  const [sector, setSector] = useState('');
  /** null while the list is still being fetched — NOT an empty list. See the field below. */
  const [sectors, setSectors] = useState<Sector[] | null | undefined>(undefined);
  const [agree, setAgree] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const loadSectors = () => {
    listSectors()
      .then((list) => {
        setSectors(list);
        // Preselected when there is one, so nobody answers a question with one possible answer.
        if (list.length === 1) setSector(list[0].key);
      })
      .catch(() => setSectors(null));
  };

  useEffect(loadSectors, []);

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
    && Boolean(sector) && agree;

  const set = (k: FieldName) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setV((p) => ({ ...p, [k]: e.target.value }));
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
    if (!sector) { setError('اختر نوع النشاط.'); return; }
    if (!agree) { setError('وافق على الشروط وسياسة الخصوصية للمتابعة.'); return; }
    setBusy(true);
    setError('');
    try {
      await openShop({
        phone: filled.phone, password: filled.password, shopName: filled.shopName, sector,
      });
      // HE AGREED HERE, against links to the documents. The legal gate records the version-pinned
      // acceptance the moment he is inside; this marker is what stops it asking the same question
      // twice in thirty seconds. Keyed by the number so a shared phone cannot carry one person's
      // consent into another person's account.
      try {
        localStorage.setItem(AGREED_KEY, normalizePhone(filled.phone) ?? '');
      } catch { /* private mode — the gate simply asks, which is the safe direction */ }

      // STRAIGHT IN, AND THE SERVER DECIDES WHETHER THAT IS ALLOWED.
      //
      // The rule "an unproven number may not sign in" lives in operations, behind a setting — and
      // while sending is not wired to Meta it is off, because demanding a proof we cannot send is
      // a locked door with no key. So the console does not gate on its own: it signs in, and if
      // the server still wants the number proven it says so with `unverified`, which the sign-in
      // pane already knows how to turn into the code screen.
      //
      // ONE PLACE DECIDES, and it is the one that knows. A second rule here would be the copy that
      // goes stale the day the setting flips.
      onSignedIn(await signIn(filled.phone, filled.password));
    } catch (err) {
      setError(sentenceFor(err, 'تعذّر إنشاء الحساب.'));
    } finally {
      setBusy(false);
    }
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
        <Input
          id="password" name="password" value={v.password} onChange={set('password')}
          onBlur={blur('password')}
          type="password" autoComplete="new-password"
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

      {/* THE FOURTH VALUE, AND THE ONLY ONE NOT ABOUT HIM. His catalogue is seeded from it — without
          it his first screen is an empty «خدماتي», which costs him more than the question does.

          IT IS ALWAYS ON THE FORM NOW. It used to render only when more than one sector had
          ARRIVED — so a slow fetch or a failed one silently removed a required field, and the
          button stayed dim over a form with nothing visibly missing. "Sometimes it appears" is
          exactly what a race looks like from the outside.

          A single sector is preselected and shown rather than hidden: the person still needs to
          see what his shop was recorded as, and a question with one answer that answers itself is
          not the same as a question that was never asked. */}
      {/* A GROUP, NOT A CONTROL — so it carries no <label>. `Field`'s label is a `htmlFor`, and a
          card group has no single element to point at; the binding would resolve to nothing and a
          screen reader would announce the cards nameless. `role="group"` + `aria-label` names the
          set, which is what is actually being labelled here. */}
      <div role="group" aria-label="نوع النشاط" className="flex flex-col gap-1.5">
        <span className="text-label font-medium text-text-secondary">
          نوع النشاط<span className="ms-1 text-danger" aria-hidden>*</span>
        </span>
        {/* THREE STATES, NOT TWO (م · النمط 1). This read failed into the SAME value it started
            from, so a failed load rendered the skeleton for ever: a permanent grey rectangle above
            a dead «ابدأ», on the first screen of the product. `undefined` is «on its way»; `null`
            is «it failed», and only now can the sentence below ever be reached. */}
        {isLoading(sectors) ? (
          <Skeleton height={40} />
        ) : hasFailed(sectors) || sectors.length === 0 ? (
          // A FAULT, AND IT SAYS SO. Silence here is what produced the dead button — the sector is
          // required, so a missing list has to be visible and retryable rather than absent.
          <button
            type="button"
            onClick={() => { setSectors(undefined); loadSectors(); }}
            className="text-sm text-danger underline"
          >
            تعذّر تحميل أنواع النشاط — أعد المحاولة
          </button>
        ) : (
          <SectorCards options={sectors} value={sector} onChange={setSector} />
        )}
      </div>

      <Terms agree={agree} onChange={setAgree} />

      {error ? <p role="alert" className="text-danger">{error}</p> : null}

      {/* GENUINELY DISABLED UNTIL THE FORM IS COMPLETE, and here that is safe — which it is not on
          the sign-in pane.
          The autofill trap needs the browser to fill EVERY gate silently. It cannot here: the
          consent box is a click nobody's password manager makes, and the sector is a control it
          does not understand. So `looksComplete` is false only when the form really is incomplete.
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
 * Choosing the trade.
 *
 * `Segmented` WAS WRONG FOR THIS, AND IT SHOWED. It is a compact toggle — two or three short words
 * sharing one pill, sized for «الكل / المتأخرون». Four sector names of four words each wrapped
 * inside it into a beige block of run-together text, which is what "primitive" meant: not a
 * missing colour, a control being asked to do a job it was not shaped for.
 *
 * SO THEY ARE CARDS, one per choice, each with room to be read. The selected one is stated three
 * times over — a gold border, a tinted ground, and a tick — because on a phone in sunlight any one
 * of the three can be the one that survives, and this is the answer that decides which catalogue
 * his shop is born with.
 *
 * STILL RADIOS UNDERNEATH. A grid of `<button>`s looks identical and tells a screen reader
 * nothing: the group has no name, the options have no relationship, and nothing announces which is
 * chosen. Real inputs keep the keyboard arrows and the announcement for free.
 */
function SectorCards({
  options, value, onChange,
}: {
  options: Sector[];
  value: string;
  onChange: (key: string) => void;
}) {
  return (
    <div role="radiogroup" aria-label="نوع النشاط" className="grid gap-2 sm:grid-cols-2">
      {options.map((o) => {
        const picked = o.key === value;
        return (
          <label
            key={o.key}
            className={[
              'flex cursor-pointer items-center justify-between gap-3 rounded-card border px-4 py-3',
              'transition-colors',
              picked
                ? 'border-accent bg-accent-soft text-accent-on-soft'
                : 'border-border-subtle bg-surface-1 hover:border-border-strong',
            ].join(' ')}
          >
            {/* The input carries the semantics and the keyboard; the card carries the look. */}
            <input
              type="radio"
              name="sector"
              value={o.key}
              checked={picked}
              onChange={() => onChange(o.key)}
              className="sr-only"
            />
            <span className="text-sm leading-snug">{o.label}</span>
            {picked ? <Check size={16} aria-hidden className="shrink-0" /> : null}
          </label>
        );
      })}
    </div>
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
