/**
 * One reader for config.ts, shared by every recorder — the ad's (record.mjs) and the live
 * tours' (record-tour.mjs) alike.
 *
 * WHY A TEXT PARSE AND NOT A TYPESCRIPT IMPORT. Neither recorder script is compiled — they run
 * as plain Node ESM so a contributor can `node media/record.mjs …` with nothing to build first.
 * config.ts stays a `.ts` file anyway (it's imported for real, with real types, from anywhere
 * inside apps/console that wants brand constants) — so this reads it as text instead of asking
 * every recorder to carry its own TypeScript toolchain just to learn a handful of numbers.
 *
 * WHY GENERIC, NOT ONE REGEX PER FIELD THAT record.mjs USED TO HAVE. That version knew exactly
 * four keys (fps, width, height, deviceWidth/Height) by name — anyone adding a fifth constant to
 * config.ts had to remember a second place to teach it to. This one walks every top-level
 * `export const NAME = { … } as const` block and returns its keys generically: a new constant in
 * config.ts is available here the moment it's written, with nothing to keep in sync by hand.
 *
 * Values it understands: numbers, quoted strings (single or double), and `true`/`false`. A
 * comment on its own line inside a block is skipped. Anything else in a block (a nested object,
 * a computed expression) is left out rather than guessed at — callers get what config.ts states
 * plainly, and a caller needing more should be the one to widen the parser, not silently trust
 * a wrong guess.
 */
import { readFileSync, existsSync } from 'node:fs';

let cached = null;

export function readConfig(configPath) {
  if (cached) return cached;
  if (!existsSync(configPath)) return (cached = {});

  const src = readFileSync(configPath, 'utf8');
  const out = {};

  // One block per `export const NAME = { ... } as const;` — non-greedy so two blocks in the same
  // file don't merge into one giant match.
  const blockRe = /export const (\w+)\s*=\s*\{([\s\S]*?)\}\s*as const/g;
  let block;
  while ((block = blockRe.exec(src))) {
    const [, name, body] = block;
    const values = {};
    for (const rawLine of body.split('\n')) {
      const line = rawLine.trim();
      if (!line || line.startsWith('/*') || line.startsWith('*') || line.startsWith('//')) continue;
      const m = line.match(/^(\w+):\s*(.+?),?\s*$/);
      if (!m) continue;
      const [, key, rawValue] = m;
      values[key] = parseScalar(rawValue.replace(/,\s*$/, ''));
    }
    out[name] = values;
  }
  return (cached = out);
}

function parseScalar(raw) {
  if (raw === 'true') return true;
  if (raw === 'false') return false;
  if (/^-?\d+(\.\d+)?$/.test(raw)) return Number(raw);
  const str = raw.match(/^['"](.*)['"]$/);
  if (str) return str[1];
  return undefined; // a nested object, template literal, or expression — not this parser's job.
}
