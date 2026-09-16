/**
 * Halalas on the wire, riyals on the screen — and the crossing happens here, once.
 *
 * WHAT THIS COST, IN THREE PLACES THAT EACH LOOKED FINE ALONE (ح-9، ح-10).
 *
 *  · `Plans.tsx` advertised a price with `Math.round(minor / 100)`. A plan at 9950 halalas was
 *    shown as «100 ريال» — fifty halalas more than we charge, on the screen whose entire job is
 *    to state the price before he agrees to it.
 *
 *  · `AccountPanes.tsx` rounded an ISSUED INVOICE the same way. A bill of 26950 read «270 ريال»
 *    while 269.50 was taken from his card. An owner reconciling our screen against his statement
 *    finds a number that is not on either side of the transaction.
 *
 *  · `Points.tsx` converted the other way with `Number(riyals) * 100`, directly beneath a comment
 *    reading «no float ever touches money». `2.3 * 100` is `229.99999999999997` in IEEE-754, so a
 *    reward the owner priced at 2.30 was stored as 229 halalas after truncation — a discount
 *    silently one halala short, forever, on every redemption.
 *
 * SO THE RULE IS NOT «ROUND BETTER». Rounding to whole riyals is lossy in the one direction that
 * matters — upward, past what was actually paid — and multiplying by 100 in floating point is
 * lossy in the other. Money crosses this boundary as INTEGERS and as DECIMAL TEXT, never as a
 * float, and never through arithmetic written at the call site.
 *
 * WESTERN DIGITS, ALWAYS. The product's numbers are read against bank statements and card
 * receipts, which are Western everywhere in the Kingdom.
 */
import { translate } from './operator-i18n';
import './money-i18n';

/** Halalas → the exact riyals to show. `26950` → `269.50`; `700` → `7`. */
export function riyals(minor: number): string {
  if (!Number.isFinite(minor)) return '0';
  // TRUNCATION IS NOT AN OPTION HERE AND NEITHER IS ROUNDING: both change the amount. The integer
  // and the remainder are taken separately so nothing is lost, and a negative amount (a refund,
  // a credit note) keeps its sign in front rather than inside the fraction.
  const n = Math.trunc(minor);
  const sign = n < 0 ? '-' : '';
  const abs = Math.abs(n);
  const whole = Math.floor(abs / 100);
  const cents = abs % 100;
  // A trailing «.00» on a round price is noise on a pricing card; a non-zero fraction is the whole
  // point of this function and is always shown, both digits.
  return cents === 0 ? `${sign}${whole}` : `${sign}${whole}.${String(cents).padStart(2, '0')}`;
}

/** Halalas → riyals with the currency word, or an em dash when there is nothing to show.
 *  `t` defaults to an ar-only translator (same pattern as Wallet.tsx's own `unitsLabel`) because
 *  this function is called from many places that do not carry a live `t` in scope (admin/
 *  affiliate cards, tests); a real render site that has `useOperatorI18n()` should pass its own. */
export function riyalsLabel(
  minor: number | null | undefined, t: (key: string) => string = (k) => translate('ar', k),
): string {
  if (minor === null || minor === undefined || Number.isNaN(Number(minor))) return '—';
  return `${riyals(Number(minor))} ${t('money.riyal')}`;
}

/**
 * What a person typed → halalas, by integer arithmetic on the TEXT.
 *
 * `parseFloat` then `* 100` is the whole of ح-10: the float is already wrong before the multiply.
 * Splitting the string keeps every digit the person actually typed, and a third decimal place is
 * refused rather than silently dropped — «2.305 ريال» is not a price this product can charge, and
 * quietly making it 2.30 spends his money on our convenience.
 *
 * Returns null for anything that is not a price, so the caller shows him a reason.
 */
export function halalas(text: string): number | null {
  const raw = String(text ?? '').trim().replace(/٫/g, '.');   // Arabic decimal separator
  if (!raw) return null;
  const m = /^(-?)(\d+)(?:\.(\d{1,2}))?$/.exec(raw);
  if (!m) return null;
  const [, sign, whole, frac = ''] = m;
  const cents = Number(frac.padEnd(2, '0'));
  const value = Number(whole) * 100 + cents;
  return sign === '-' ? -value : value;
}
