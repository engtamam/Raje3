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
 *   a value   — it arrived. An EMPTY value is an answer: «he has no customers» is a fact about
 *               the shop, and must never be rendered as an outage.
 *
 * `Messages.tsx` had the right shape from the start with its own `logFailed` flag; this is the
 * same idea with no second variable to forget to set.
 */

/** A value that is fetched: `undefined` while it is on its way, `null` if the read failed. */
export type Loading<T> = T | null | undefined;

/** Still on its way. */
export function isLoading<T>(v: Loading<T>): v is undefined {
  return v === undefined;
}

/** The read failed — say so, and let him try again. */
export function hasFailed<T>(v: Loading<T>): v is null {
  return v === null;
}

/** It arrived. Empty is still arrived, and that distinction is the whole point. */
export function isReady<T>(v: Loading<T>): v is T {
  return v !== undefined && v !== null;
}
