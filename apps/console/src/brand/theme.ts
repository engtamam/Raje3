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
export function applyRaje3(): void {
  applyTheme('light', {});
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
