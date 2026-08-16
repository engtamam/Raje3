/**
 * The card form — the one thing standing between a live plan button and a charged riyal (د-15).
 *
 * THE DEFECT THIS ANSWERS. `Plans.tsx` posted `{ plan_id }` and nothing else, while
 * `subscription.activate` decides `paid = bool(payment_token)` and answers 402 without one. So
 * every paid row on the price list was drawn as a live button and refused on press; only the base
 * got through, and only because its `trial_days: 14` skips the check entirely. Nothing was broken
 * in a way anybody could see — the button looked exactly like a button that works.
 *
 * WHY THE FORM IS NOT HERE. Minting the token is the gateway's own browser form (Moyasar), and it
 * needs the publishable key and a live merchant account — neither of which exists yet. Writing a
 * form against keys we do not have would be a second promise on top of the first.
 *
 * SO THE HONEST STATE IS DECLARED, NOT ASSUMED. `canMintToken` says whether this console can
 * actually produce a `payment_token`. It is false until the form lands, and the screen reads it
 * rather than inferring readiness from the server's `enabled` flag — that flag answers «is there a
 * gateway key», which is not the same question as «can this browser hand back a token».
 *
 * The day the form is built, this becomes the module that builds it and `canMintToken` becomes
 * true — one place, and every screen that sells follows.
 */

export const canMintToken = false;

/** Said in the owner's words: the till is not shut for a fault of his. */
export const NO_CARD_FORM =
  'الدفع بالبطاقة لم يُفعَّل بعد. تواصل معنا لتفعيل باقتك، ولن تُحسب عليك أي رسوم حتى ذلك الحين.';

/**
 * A single-use reference to a card we never see.
 *
 * Refuses rather than returning an empty string: an empty token travels perfectly well all the way
 * to the server, which reads it as «not paid» and answers 402 — the shape that produced this
 * finding. A caller that cannot mint must know it before it asks somebody to press anything.
 */
export async function mintPaymentToken(): Promise<string> {
  throw new Error(NO_CARD_FORM);
}
