/**
 * The card form itself — Moyasar's own fields, tokenised straight from this component to their
 * API (see `payment.ts` for why it can never go through our backend).
 *
 * ONE FORM, TWO CALLERS. Subscribing to a paid plan and updating the card on an existing
 * subscription both end at the same place — a `payment_token` handed to a different backend
 * action — so this component only knows how to produce a token; `pending` tells it (and
 * `pendingPayment.ts`, across the possible 3DS redirect) what that token is FOR.
 */
import { useState, type FormEvent } from 'react';
import { Button } from '../rj-ui/Button';
import { Field, Input } from '../rj-ui/Field';
import { digitsOnly } from '../digits';
import { tokenizeCard } from '../payment';
import { remember, type PendingPayment } from '../pendingPayment';

/** Groups of 4, the way he reads it off the card itself — display only; `number` sent to Moyasar
 *  is stripped back to plain digits first. */
function formatCardNumber(raw: string): string {
  return digitsOnly(raw).slice(0, 19).replace(/(.{4})/g, '$1 ').trim();
}

export function CardForm({ pending, onToken, onCancel }: {
  pending: PendingPayment;
  /** Called ONLY for the rare card that skips 3DS — the ordinary path never returns, because the
   *  browser has navigated away to the issuer's verification page and back through the callback
   *  route instead. */
  onToken: (token: string) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState('');
  const [number, setNumber] = useState('');
  const [month, setMonth] = useState('');
  const [year, setYear] = useState('');
  const [cvc, setCvc] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const thisYear = new Date().getFullYear();

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError('');
    const digits = digitsOnly(number);
    if (digits.length < 12) { setError('رقم البطاقة غير مكتمل.'); return; }
    const m = digitsOnly(month).padStart(2, '0');
    const y = digitsOnly(year);
    const yyyy = y.length === 2 ? `20${y}` : y;
    if (!m || Number(m) < 1 || Number(m) > 12) { setError('شهر الانتهاء غير صحيح.'); return; }
    if (!yyyy || Number(yyyy) < thisYear) { setError('سنة الانتهاء غير صحيحة.'); return; }
    const c = digitsOnly(cvc);
    if (c.length < 3) { setError('رمز الأمان (CVC) غير مكتمل.'); return; }
    if (!name.trim()) { setError('اكتب الاسم كما هو مطبوع على البطاقة.'); return; }

    setBusy(true);
    try {
      // THE SAME PAGE, QUERY STRING AND ALL — a redirect that lands anywhere else strips the
      // context (which tab, which billing pane) the owner was actually looking at.
      const returnTo = window.location.href;
      const result = await tokenizeCard(
        { name: name.trim(), number: digits, month: m, year: yyyy, cvc: c }, returnTo);
      if (result.kind === 'error') { setError(result.message); return; }
      if (result.kind === 'redirect') {
        // REMEMBERED BEFORE THE NAVIGATION, never after — the page is about to unload, and code
        // after `window.location.href =` may simply never run.
        remember(pending);
        window.location.href = result.url;
        return;
      }
      onToken(result.token);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-3 rounded-card border border-border-subtle bg-surface-1 p-4">
      <Field label="الاسم كما على البطاقة" htmlFor="cf-name">
        <Input id="cf-name" value={name} onChange={(e) => setName(e.target.value)}
               autoComplete="cc-name" required />
      </Field>
      <Field label="رقم البطاقة" htmlFor="cf-number">
        <Input id="cf-number" inputMode="numeric" dir="ltr" autoComplete="cc-number"
               value={formatCardNumber(number)}
               onChange={(e) => setNumber(digitsOnly(e.target.value))} required />
      </Field>
      <div className="grid grid-cols-3 gap-3">
        <Field label="الشهر" htmlFor="cf-month">
          <Input id="cf-month" inputMode="numeric" dir="ltr" placeholder="MM" maxLength={2}
                 autoComplete="cc-exp-month" value={month}
                 onChange={(e) => setMonth(digitsOnly(e.target.value))} required />
        </Field>
        <Field label="السنة" htmlFor="cf-year">
          <Input id="cf-year" inputMode="numeric" dir="ltr" placeholder="YYYY" maxLength={4}
                 autoComplete="cc-exp-year" value={year}
                 onChange={(e) => setYear(digitsOnly(e.target.value))} required />
        </Field>
        <Field label="CVC" htmlFor="cf-cvc">
          <Input id="cf-cvc" inputMode="numeric" dir="ltr" maxLength={4} autoComplete="cc-csc"
                 value={cvc} onChange={(e) => setCvc(digitsOnly(e.target.value))} required />
        </Field>
      </div>
      {error ? <p className="text-sm text-danger">{error}</p> : null}
      <p className="text-xs text-text-secondary">
        بياناتك تُرسَل مباشرة لبوابة الدفع ولا تمر على خوادمنا إطلاقاً — قد يُطلب منك تأكيد العملية
        من تطبيق بنكك.
      </p>
      <div className="flex gap-2">
        <Button type="submit" disabled={busy}>{busy ? 'يتحقق…' : 'تأكيد البطاقة'}</Button>
        <Button type="button" variant="ghost" disabled={busy} onClick={onCancel}>إلغاء</Button>
      </div>
    </form>
  );
}
