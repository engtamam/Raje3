/**
 * راجِع's look — which is the kit's palette, deliberately, plus two rules of our own.
 *
 * WE KEPT THEIR COLOURS AFTER READING THEM RATHER THAN BY PREFERENCE. The palette carries
 * decisions that were earned: the ground is warm ivory because "air, not grey" — their comment
 * explains that an earlier grey-blue made everything that was not white read as grey and drained
 * the life out; the ink is deep navy; and AMBER IS RESERVED for "expiring soon", so nothing else
 * in the product may use it for anything. That kind of discipline takes months to acquire and
 * cannot be copied by taste.
 *
 * AND KEEPING IT KEEPS THE ALIAS CLEAN. Replacing the palette would fork us from platform/ui in
 * the one file that touches every screen — the opposite of the decision that lets their four new
 * auth screens arrive for free.
 *
 * Their brand gold also passes the only test this product actually imposes, which comes from the
 * field rather than from a brand deck: it holds its contrast on a white button grid on a tablet in
 * an open workshop at noon, and it is neither the red nor the amber that screen must keep free for
 * failure. Nothing about it needed changing, so nothing was changed.
 */
import { applyTheme } from '@base-ui/theme';
import { applyDir } from '@base-ui/i18n';

/**
 * LIGHT, AND THAT IS NOT A DEFAULT. A dark theme is unreadable on a tablet in an open workshop at
 * noon, which is where the field screen lives — and the owner's sections are on the same app, so
 * one appearance is one fewer thing to be wrong about. The owner's console may offer the toggle
 * later; the field screen must not.
 */
/**
 * The derived colours, corrected after the fact — because the kit computes them wrong.
 *
 * `theme.config.ts` mixes two hex colours with:
 *
 *     const h = (c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16));
 *     const [r, g, b] = h(from.replace('#', ''));
 *
 * It strips the `#` and then indexes as though it were still there. `h('ffffff')` therefore reads
 * ("ff", "ff", "f") — white's blue channel comes out 15 instead of 255 — and every colour derived
 * from the brand gold is wrong. `--accent-soft`, which should be a pale sand (#f6f0e6), lands on
 * #f1ec0f: a highlighter yellow. That is the colour the owner photographed filling the active item
 * in the sidebar, and it is why «النشط بلونٍ لا يصرخ» could not be satisfied by changing anything
 * we own — the token itself was broken.
 *
 * AND IT CANNOT BE FIXED THROUGH `applyTheme`'s OVERRIDES. That function reads only `brand.accent`,
 * then RE-DERIVES soft and on-soft from it with the same broken mix — so passing our own values
 * has them computed over. We therefore set the two variables directly, immediately after, using
 * the same mechanism applyTheme itself uses (inline custom properties on the root).
 *
 * NOT A FORK, AND DELETABLE IN ONE EDIT. platform/ui is untouched; the upstream bug is escalated;
 * this block disappears the day the fix lands upstream. The base gold is left alone — it was never
 * wrong, only what was derived from it.
 */
const GOLD = '#B8862B';

/** The mix the kit meant to write: `#` stripped, then indexed from zero. */
function mix(from: string, to: string, amount: number): string {
  const channels = (c: string) => {
    const hex = c.replace('#', '');
    return [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16));
  };
  const [r1, g1, b1] = channels(from);
  const [r2, g2, b2] = channels(to);
  const one = (a: number, b: number) =>
    Math.round(a + (b - a) * amount).toString(16).padStart(2, '0');
  return `#${one(r1, r2)}${one(g1, g2)}${one(b1, b2)}`;
}

/** The pale sand the active nav item wears. Exported so it can be asserted, not only applied. */
export function softTint(): string {
  return mix(GOLD, '#ffffff', 0.88);
}

/** The ink that sits on it. */
export function onSoftInk(): string {
  return mix(GOLD, '#000000', 0.55);
}

export function applyRaje3(): void {
  // THE ACCENT IS PASSED NOW, AND THE DERIVED TINTS ARE NOT.
  //
  // Until v0.16.4 the kit's `mix()` stripped the '#' and then indexed as though it were still
  // there, so white's blue channel read 15 instead of 255 and every derived colour skewed yellow:
  // `--accent-soft` rendered #f1ec0f, a highlighter, across the active nav row. We set the two
  // variables by hand afterwards, because passing the accent re-derived them with the same broken
  // mixer and overwrote anything we set first.
  //
  // It is fixed upstream for every consumer, so this is where our correction is DELETED rather
  // than left behind. `softTint()` and `onSoftInk()` stay exported: the test still asserts those
  // exact values, so if this ever regresses we learn it from a failing assertion instead of from
  // a photograph of a yellow sidebar.
  applyTheme('light', { accent: GOLD });
  applyDir('ar');
}

/**
 * WESTERN DIGITS, AND TABULAR.
 *
 * The digits are 0-9 everywhere including inside Arabic prose — a rule this product enforces in CI
 * over its whole source tree, because Saudi numbers are written and read in Western digits and a
 * mixed set produces values that look right and match nothing.
 *
 * TABULAR IS THE PART THAT GETS FORGOTTEN. In a proportional face, 1 is narrower than 8 — so a
 * counter that ticks from 18 to 19 to 20 changes width as it changes value, and a dashboard meant
 * to be glanced at reads as flickering. Every number on a screen that updates carries this.
 */
export const NUMERIC = 'tabular-nums';
