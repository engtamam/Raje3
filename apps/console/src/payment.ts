/**
 * The card form — minting a `payment_token` for real, against Moyasar.
 *
 * WHAT THIS REPLACES. `canMintToken` was hardcoded `false` and `mintPaymentToken()` always threw
 * `NO_CARD_FORM` — a deliberate, declared stub (see the module's own git history) for the day a
 * merchant account and a publishable key existed. That day is now; the key itself is supplied at
 * build time and stays empty until Ops sets it, so nothing here changes behaviour until it does.
 *
 * WHY MOYASAR, AND WHY THE TOKEN IS MINTED FROM THE BROWSER, NEVER OUR SERVER. Moyasar's own
 * security model requires it: card data must never transit our backend, so tokenisation is a
 * direct browser→Moyasar call authenticated with the PUBLISHABLE key (safe to ship in client code
 * — it can only create a single-use token, never charge anything). Our backend only ever sees the
 * resulting `token_...` id.
 *
 * THE GATEWAY IS SWAPPABLE, AND THIS FILE IS THE ONE PLACE THAT KNOWS WHICH ONE. billing-service
 * itself already supports several (`PAYMENT_GATEWAY_DRIVER`: moyasar/tap/hyperpay/paytabs/geidea/
 * aps/paypal/checkout — `platform/services/billing-service/app/container.py`'s `_PAYMENT`
 * registry) — this module is Moyasar's OWN browser-side tokenisation contract, which is specific
 * to Moyasar's API regardless of what other gateways the backend can charge through. The day this
 * shop's gateway changes, this file is what gets a sibling, not what gets rewritten.
 *
 * THE FLOW HAS TWO SHAPES, BECAUSE MOYASAR'S DOES. A save-only tokenisation (what this always is —
 * we are never charging in the same step) ALWAYS triggers 3-D Secure: the browser is redirected
 * away to the card issuer's own verification page and back. So minting a token is not one call —
 * it is "maybe a call, maybe a full navigation", and `pendingPayment.ts` is what survives that
 * navigation to finish the job on return.
 */

export const MOYASAR_PUBLISHABLE_KEY = import.meta.env.VITE_MOYASAR_PUBLISHABLE_KEY ?? '';

/** Whether this build can actually produce a `payment_token` at all. `false` until Ops sets the
 *  key — the screen reads this rather than inferring readiness from the server's `enabled` flag,
 *  which answers "is there a gateway key" and not "can this browser hand back a token". */
export const canMintToken = Boolean(MOYASAR_PUBLISHABLE_KEY);

/** Said in the owner's words: the till is not shut for a fault of his. */
export const NO_CARD_FORM =
  'الدفع بالبطاقة لم يُفعَّل بعد. تواصل معنا لتفعيل باقتك، ولن تُحسب عليك أي رسوم حتى ذلك الحين.';

const TOKENS_URL = 'https://api.moyasar.com/v1/tokens';

export interface Card {
  name: string;
  /** Digits only — the form strips spaces/Arabic-Indic digits before this is built. */
  number: string;
  /** MM, two digits. */
  month: string;
  /** YYYY, four digits — Moyasar's own field name and shape for `/v1/tokens`. */
  year: string;
  cvc: string;
}

/** Either the token is already usable, or the browser must navigate away to verify it — never
 *  both, and a caller that only handles one of the two has not handled tokenisation at all. */
export type TokenizeResult =
  | { kind: 'token'; token: string }
  | { kind: 'redirect'; url: string }
  | { kind: 'error'; message: string };

function basicAuthHeader(publishableKey: string): string {
  // Basic auth, publishable key as the username, empty password — Moyasar's own scheme
  // (docs.moyasar.com/api/authentication). `btoa` is fine here: both are always ASCII.
  return `Basic ${btoa(`${publishableKey}:`)}`;
}

/**
 * Tokenise a card — `save_only`, never a charge. Returns a usable token directly for the rare
 * card that skips 3DS, or a `redirect` URL that MUST be navigated to (a full `window.location`
 * change, not a fetch) to complete verification.
 *
 * `returnTo` is Moyasar's `callback_url` — where the issuer's page sends the browser back after
 * 3DS. It must be an absolute URL on this app; see `pendingPayment.ts` for what happens when it
 * lands.
 */
export async function tokenizeCard(card: Card, returnTo: string): Promise<TokenizeResult> {
  if (!canMintToken) return { kind: 'error', message: NO_CARD_FORM };
  let res: Response;
  try {
    res = await fetch(TOKENS_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: basicAuthHeader(MOYASAR_PUBLISHABLE_KEY),
      },
      body: JSON.stringify({
        name: card.name, number: card.number, month: card.month, year: card.year, cvc: card.cvc,
        save_only: true, callback_url: returnTo,
      }),
    });
  } catch {
    // NETWORK-LEVEL, NOT A REFUSAL. A dropped connection to Moyasar is not the same sentence as a
    // declined card — the owner should retry, not correct a number that was never wrong.
    return { kind: 'error', message: 'تعذّر الاتصال ببوابة الدفع. تحقق من اتصالك وحاول مرة أخرى.' };
  }
  const body = await res.json().catch(() => ({}) as Record<string, unknown>);
  if (!res.ok) {
    // MOYASAR'S OWN SENTENCE, the same rule every server refusal in this app follows — a card
    // number and a CVC failing validation is theirs to describe correctly, not ours to guess at.
    return { kind: 'error', message: typeof body.message === 'string' ? body.message : 'تعذّر قبول بطاقتك.' };
  }
  const verificationUrl = typeof body.verification_url === 'string' ? body.verification_url : '';
  if (verificationUrl) return { kind: 'redirect', url: verificationUrl };
  const id = typeof body.id === 'string' ? body.id : '';
  if (id && body.status !== 'inactive') return { kind: 'token', token: id };
  return { kind: 'error', message: 'تعذّر التحقق من بطاقتك.' };
}

/**
 * After the issuer's page sends the browser back: confirm the token actually verified, rather
 * than trusting the query string alone — the same discipline the Moyasar payment-callback flow
 * documents for a charge ("fetch it by id, verify status, amount, currency before accepting"),
 * applied to a token instead.
 */
export async function confirmToken(tokenId: string): Promise<TokenizeResult> {
  if (!canMintToken) return { kind: 'error', message: NO_CARD_FORM };
  let res: Response;
  try {
    res = await fetch(`${TOKENS_URL}/${encodeURIComponent(tokenId)}`, {
      headers: { Authorization: basicAuthHeader(MOYASAR_PUBLISHABLE_KEY) },
    });
  } catch {
    return { kind: 'error', message: 'تعذّر الاتصال ببوابة الدفع. تحقق من اتصالك وحاول مرة أخرى.' };
  }
  const body = await res.json().catch(() => ({}) as Record<string, unknown>);
  if (!res.ok) {
    return { kind: 'error', message: typeof body.message === 'string' ? body.message : 'تعذّر التحقق من بطاقتك.' };
  }
  if (body.status === 'active' || body.status === 'verified') {
    return { kind: 'token', token: String(body.id ?? tokenId) };
  }
  // A REFUSED VERIFICATION IS NOT A NETWORK FAILURE. «initiated» stuck this long means the bank
  // declined the 3DS challenge — a fact about the card, said as one, not retried silently.
  return { kind: 'error', message: 'رفض البنك التحقق من هذه البطاقة. جرّب بطاقة أخرى.' };
}
