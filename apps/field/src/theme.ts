/**
 * Raje3's look, applied at RUNTIME onto platform/ui's tokens.
 *
 * This is the whole reason the library is themeable: the brand is one override call, never an edit
 * inside a component — and platform/ is read-only, so an edit there was never an option anyway.
 */
import { applyTheme } from '@base-ui/theme';
import { applyDir } from '@base-ui/i18n';

/** Deep green. Chosen for the field: it holds its contrast against a white button grid under
 *  daylight, and it is not the red or amber this screen needs to keep free for failure. */
export const BRAND = '#0F5F4E';

export function applyRaje3(): void {
  // LIGHT, DELIBERATELY. A dark theme is unreadable on a tablet in an open workshop at noon, and
  // that is where this screen lives. The owner's dashboard is a different app and may choose.
  applyTheme('light', { 'brand.accent': BRAND });
  applyDir('ar');
}
