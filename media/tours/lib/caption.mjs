/**
 * Turns a tour script's caption text into what actually gets shown and for how long — driven
 * entirely by config.ts's CAPTION constants, so tightening the reading-speed rule in one place
 * (config.ts) changes the timing of every caption in every tour without touching a tour script.
 */

/** Greedy word-wrap into at most `maxLines` lines of at most `maxCharsPerLine` each. */
export function wrapCaption(text, cfg) {
  const words = text.trim().split(/\s+/);
  const lines = [];
  let line = '';
  for (const word of words) {
    const next = line ? `${line} ${word}` : word;
    if (next.length > cfg.maxCharsPerLine && line) {
      lines.push(line);
      line = word;
    } else {
      line = next;
    }
  }
  if (line) lines.push(line);

  if (lines.length > cfg.maxLines) {
    throw new Error(
      `caption "${text}" needs ${lines.length} lines at ${cfg.maxCharsPerLine} chars/line — `
      + `CAPTION.maxLines is ${cfg.maxLines}. Shorten the sentence or split it into two captions.`,
    );
  }
  return lines.join('\n');
}

/** How long a caption must stay up to be readable — never less than CAPTION.minMs. */
export function captionHoldMs(text, cfg) {
  const readMs = (text.length / cfg.charsPerSecond) * 1000;
  return Math.max(cfg.minMs, Math.round(readMs));
}
