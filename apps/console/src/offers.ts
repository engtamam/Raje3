/**
 * What an offer means on a screen — the two rules that are worth testing without a browser.
 *
 * Extracted from the customer record precisely so they CAN be tested: a rule living inside a
 * component is a rule that only a rendered page can check, and the rendered page is the thing most
 * likely to be rewritten.
 */
import { tf, translate } from './operator-i18n';
import './offers-i18n';

export interface Offer {
  text: string;
  expires_at: number;
  sent_at: number;
  services: string[];
  /** THE SERVER'S VERDICT, and the screen does not second-guess it. Two clocks disagreeing about
   *  whether an offer is live is a support call nobody can settle, and the browser's is the one
   *  that can be wrong on purpose. */
  live: boolean;
  /** The code the customer holds, when the offer carries one. Empty for the older ones. */
  code?: string;
}

/**
 * How long is left, in the largest unit that is still true.
 *
 * The owner is SCANNING a record, not timing a countdown — that belongs on the customer's own
 * page, where the seconds matter because he is deciding whether to come now. Here "3 days" is the
 * whole answer, and "0 days" would read as expired when it is not.
 *
 * `t` defaults to an ar-only translator (same pattern as Wallet.tsx's own `unitsLabel`) — the real
 * render site (Customer.tsx) passes its own live `t` from context.
 */
export function remaining(
  expires: number, now: number = Math.floor(Date.now() / 1000),
  t: (key: string) => string = (k) => translate('ar', k),
): string {
  const left = expires - now;
  if (left <= 0) return '';
  const days = Math.floor(left / 86400);
  if (days >= 1) return tf(t, 'offers.remaining.days', { days });
  const hours = Math.floor(left / 3600);
  if (hours >= 1) return tf(t, 'offers.remaining.hours', { hours });
  return t('offers.remaining.hour');
}

/** Live first, then what ran out — kept, dimmed and labelled, never removed. */
export function partitionOffers(offers: Offer[]): [Offer[], Offer[]] {
  return [offers.filter((o) => o.live), offers.filter((o) => !o.live)];
}
