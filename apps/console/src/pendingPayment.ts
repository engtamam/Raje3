/**
 * What we were doing when the browser left for 3-D Secure — the one thing `tokenizeCard`'s
 * `redirect` result cannot carry itself, because a full page navigation clears everything in
 * memory. Without this, the owner comes back from his bank's verification page having proven his
 * card is his and the console has no idea what that was FOR.
 *
 * sessionStorage, not memory: the redirect is a real navigation away from this tab and back, so
 * anything held only in a JS variable is already gone by the time `resolve()` would read it.
 * Not localStorage — a card-purchase intent has no business surviving past this one attempt.
 */
const KEY = 'raje3.pending_payment.v1';

export type PendingPayment =
  | { kind: 'subscribe'; planId: string }
  | { kind: 'update_payment_method'; subscriptionId: string };

export function remember(p: PendingPayment): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(p));
  } catch {
    // Quota, or a private-mode tab. If this fails, `resolve()` on return finds nothing and the
    // owner sees the plain "couldn't tell what this was for" sentence rather than a silent no-op.
  }
}

/** Read once, and gone — a second callback landing here (a refreshed tab, a bookmarked URL) must
 *  not replay the same subscribe/update against whatever token happens to still resolve. */
export function takePending(): PendingPayment | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    sessionStorage.removeItem(KEY);
    if (!raw) return null;
    const row = JSON.parse(raw) as PendingPayment;
    if (row.kind === 'subscribe' && typeof row.planId === 'string') return row;
    if (row.kind === 'update_payment_method' && typeof row.subscriptionId === 'string') return row;
    return null;
  } catch {
    return null;
  }
}
