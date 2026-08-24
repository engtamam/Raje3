/**
 * Turns a tour script's caption text into how long it stays on screen — driven entirely by
 * config.ts's CAPTION constants, so tightening the reading-speed rule in one place changes the
 * timing of every caption in every tour without touching a tour script.
 *
 * LINE-WRAPPING ITSELF LIVES IN overlay.mjs, NOT HERE. A character-count guess (this file's own
 * former `wrapCaption`) can't know a caption bar's real rendered pixel width, and produced five
 * lines instead of two the first time a tour ran at its actual portrait frame width — see
 * overlay.mjs's `say()` for the real fix, which measures against the bar's own live width in the
 * browser instead of guessing from a character budget calibrated for a different frame entirely.
 */

/** How long a caption must stay up to be readable — never less than CAPTION.minMs. */
export function captionHoldMs(text, cfg) {
  const readMs = (text.length / cfg.charsPerSecond) * 1000;
  return Math.max(cfg.minMs, Math.round(readMs));
}
