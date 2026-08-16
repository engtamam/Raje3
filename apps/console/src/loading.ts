/**
 * Three states for a value a screen has to fetch — because two were never enough.
 *
 * WHAT WENT WRONG (م · النمط 1). Every screen in this app held `useState<Rows | null>(null)`,
 * rendered a skeleton while the value was `null`, and handled failure with
 * `.catch(() => setRows(null))`. A failed read therefore put the state back exactly where it
 * started: the skeleton rendered for ever, and the Arabic sentence somebody had already written
 * for the failure was unreachable code.
 *
 * The owner saw «نقرأ نقاطك وجوائزك» that never finished. The payments screen — the one that
 * sells — was two grey rectangles. «نوع النشاط» on the very first screen of the product was a
 * permanent skeleton above a dead «ابدأ» button. Nobody was told anything, so nobody retried.
 *
 * THE VOCABULARY:
 *
 *   undefined — not yet. The request is in flight. Render the skeleton.
 *   null      — it failed. Render the sentence, and offer the retry.
 *   DENIED    — this section is not his to see. Never asked for, so never failed and never empty.
 *   a value   — it arrived. An EMPTY value is an answer: «he has no customers» is a fact about
 *               the shop, and must never be rendered as an outage.
 *
 * WHY THE FOURTH (م · النمط 2 — eleven places). Where an action was missing from the catalogue the
 * screens wrote `setRows([])` and moved on, so a PERMISSION answer came out wearing an EMPTINESS
 * sentence: «لا يوجد عملاء بعد» to a shop with three thousand, «لا أحد متأخر» — a congratulation —
 * at the moment somebody should have been chasing people, and «تعذّر قراءة رسائلك · حسابك سليم.
 * حاول بعد قليل» whose only path was a missing capability, so he tried again every day on
 * something waiting would never open.
 *
 * `Messages.tsx` had the right shape from the start with its own `logFailed` flag; this is the
 * same idea with no second variable to forget to set.
 */

/**
 * Not this person's to see. A unique object rather than a boolean beside the value: a second
 * variable is a second thing to forget to set, and every one of the eleven sites forgot.
 */
export const DENIED = { denied: true } as const;
export type Denied = typeof DENIED;

/** A value that is fetched: `undefined` while it is on its way, `null` if the read failed. */
export type Loading<T> = T | null | undefined | Denied;

/** Still on its way. */
export function isLoading<T>(v: Loading<T>): v is undefined {
  return v === undefined;
}

/** The read failed — say so, and let him try again. */
export function hasFailed<T>(v: Loading<T>): v is null {
  return v === null;
}

/** Not his to see — a fact about his role, and never about our availability. */
export function isDenied<T>(v: Loading<T>): v is Denied {
  return v === DENIED;
}

/** It arrived. Empty is still arrived, and that distinction is the whole point. */
export function isReady<T>(v: Loading<T>): v is T {
  return v !== undefined && v !== null && v !== DENIED;
}
