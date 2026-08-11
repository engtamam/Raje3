/**
 * What an offer means on a screen — the two rules that are worth testing without a browser.
 *
 * Extracted from the customer record precisely so they CAN be tested: a rule living inside a
 * component is a rule that only a rendered page can check, and the rendered page is the thing most
 * likely to be rewritten.
 */

export interface Offer {
  text: string;
  expires_at: number;
  sent_at: number;
  services: string[];
  /** THE SERVER'S VERDICT, and the screen does not second-guess it. Two clocks disagreeing about
   *  whether an offer is live is a support call nobody can settle, and the browser's is the one
   *  that can be wrong on purpose. */
  live: boolean;
}

/**
 * How long is left, in the largest unit that is still true.
 *
 * The owner is SCANNING a record, not timing a countdown — that belongs on the customer's own
 * page, where the seconds matter because he is deciding whether to come now. Here "3 days" is the
 * whole answer, and "0 days" would read as expired when it is not.
 */
export function remaining(expires: number, now: number = Math.floor(Date.now() / 1000)): string {
  const left = expires - now;
  if (left <= 0) return '';
  const days = Math.floor(left / 86400);
  if (days >= 1) return `يبقى ${days} يوماً`;
  const hours = Math.floor(left / 3600);
  if (hours >= 1) return `تبقّى ${hours} ساعات`;
  return 'ينتهي خلال ساعة';
}

/** Live first, then what ran out — kept, dimmed and labelled, never removed. */
export function partitionOffers(offers: Offer[]): [Offer[], Offer[]] {
  return [offers.filter((o) => o.live), offers.filter((o) => !o.live)];
}
