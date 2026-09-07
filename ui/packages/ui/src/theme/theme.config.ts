/**
 * theme.config.ts — THE SINGLE SOURCE OF TRUTH for the whole client UI's look.
 *
 * Edit ONE value here and the entire app changes: colours, surfaces, the accent, radii, shadows,
 * typography scale, motion. Nothing is hard-coded in components — every component resolves Tailwind
 * utilities (bg-surface-2, text-accent, rounded-card …) to the CSS variables this file emits
 * (see applyTheme.ts + tailwind.config.js). The runtime can ALSO override any token from the store
 * (white-label brand colour, density) — see applyTheme(overrides).
 *
 * Light-first: `defaultAppearance` is 'light'; the user can still toggle to dark.
 */

export type Appearance = 'light' | 'dark';

/** A flat colour palette — keys become CSS custom properties (--surface-0, --accent, …). */
export interface Palette {
  'surface-0': string;
  'surface-1': string;
  'surface-2': string;
  'surface-3': string;
  'text-primary': string;
  'text-secondary': string;
  'text-muted': string;
  'border-subtle': string;
  'border-strong': string;
  accent: string;
  'accent-hover': string;
  'accent-contrast': string;
  'accent-soft': string;
  'accent-on-soft': string;
  success: string;
  'success-soft': string;
  'success-on-soft': string;
  warning: string;
  'warning-soft': string;
  'warning-on-soft': string;
  danger: string;
  'danger-soft': string;
  'danger-on-soft': string;
  'danger-contrast': string;
  info: string;
  'info-soft': string;
  'info-on-soft': string;
  /** GOLD — reserved for a gift: a standard someone may use free for a while. It is deliberately NOT
   *  `warning` (amber already means "expiring soon" on these same cards) and NOT `accent` (which means
   *  "act on this"). A colour that means one thing keeps meaning it. */
  gift: string;
  'gift-soft': string;
  'gift-on-soft': string;
  'gift-contrast': string;
  'focus-ring': string;
  /** Scrim behind modals/drawers/popovers. A pre-composited translucent ink so every overlay across the
   *  three apps uses ONE backdrop, theme-aware, instead of a hand-rolled `bg-black/50`. */
  overlay: string;
}

/** Non-colour design tokens — shared across appearances (also emitted as CSS vars). */
export interface Scale {
  /** Root font-size as a percentage of 16px; scales the WHOLE UI (rem-based). */
  rootFontPct: number;
  /** Corner radii. `card` is the signature large radius for panels. */
  radius: { sm: string; md: string; lg: string; card: string; pill: string };
  /** Elevation shadows (control-room: soft, low-spread). */
  shadow: { sm: string; md: string; lg: string; pop: string; glow: string };
  /** Motion durations + easing for the consistent, calm feel. */
  motion: { fast: string; base: string; slow: string; ease: string };
  /** Font families (Arabic-aware face swapped at dir=rtl in index.css). */
  font: { sans: string; mono: string };
}

// ── the accent: ONE source of truth ───────────────────────────────────────────────────
// The brand accent lives in config/product.json (brand.accent) and is injected here at build time as
// __PRODUCT_ACCENT__. To rebrand the whole product — every button, link, focus ring, glow, and the logo
// shield — you change ONE value in product.json. Nothing else. The full ramp (hover, soft tint, on-soft
// text) is DERIVED from that base below, so there is no second place to keep in sync.
//
// The fallback (royal blue) is only for a context where the define is absent — a test runner, Storybook.
declare const __PRODUCT_ACCENT__: { light: string; dark: string };
const BRAND = typeof __PRODUCT_ACCENT__ !== 'undefined'
  ? __PRODUCT_ACCENT__
  : { light: '#B8862B', dark: '#D8B876' };

/** Mix two hex colours by `amount` (0..1 toward `to`). Lets us derive a hover, a soft tint and on-soft
 *  text from a single brand hex, so the ramp is computed rather than hand-picked in a second place. */
function mix(from: string, to: string, amount: number): string {
  // The `#` is stripped first, so the channels start at 0/2/4 — NOT 1/3/5. With 1/3/5 (a leftover
  // from indexing WITH the '#'), h('ffffff') read ['ff','ff','f'] → blue=15 not 255, so every derived
  // tint skewed hard toward yellow (accent-soft rendered #f1ec0f, a highlighter, on the active nav row).
  const h = (c: string) => [0, 2, 4].map((i) => parseInt(c.slice(i, i + 2), 16));
  const [r1, g1, b1] = h(from.replace('#', ''));
  const [r2, g2, b2] = h(to.replace('#', ''));
  const m = (a: number, b: number) => Math.round(a + (b - a) * amount).toString(16).padStart(2, '0');
  return `#${m(r1, r2)}${m(g1, g2)}${m(b1, b2)}`;
}

// LIGHT: hover darkens toward ink; soft is a pale tint of the accent; on-soft reuses the hover for text.
const ACCENT_LIGHT = {
  base: BRAND.light,
  hover: mix(BRAND.light, '#000000', 0.22),
  soft: mix(BRAND.light, '#ffffff', 0.88),
  onSoft: mix(BRAND.light, '#000000', 0.22),
};
// DARK: the base is already lifted for the near-black ground; hover lightens, soft is a deep tint.
const ACCENT_DARK = {
  base: BRAND.dark,
  hover: mix(BRAND.dark, '#ffffff', 0.28),
  soft: mix(BRAND.dark, '#0a0e1a', 0.80),
  onSoft: mix(BRAND.dark, '#ffffff', 0.40),
};

const light: Palette = {
  // REBRANDED, FROM THE SHOP CONSOLE'S OWN "محلّي" SCREEN, NOT INVENTED HERE. The old
  // warm-cream/gold "sealed document" identity was rejected outright, and a
  // violet/teal/coral direction built for محلّي was approved; this is that same
  // palette promoted from one screen's local `--sh-*` tokens to the platform's own theme, so
  // every screen gets it rather than one screen carrying a different identity than its shell.
  // A near-white cool violet ground (not warm cream), white cards, violet accent, teal
  // secondary, coral for danger/attention.
  'surface-0': '#f4f5fa',
  'surface-1': '#ffffff',
  'surface-2': '#eceefa',
  'surface-3': '#dfe1f2',
  'text-primary': '#131226',
  'text-secondary': '#47466a',
  'text-muted': '#8d8ca8',
  'border-subtle': '#e5e6f2',
  'border-strong': '#cfd1e8',
  accent: ACCENT_LIGHT.base,
  'accent-hover': ACCENT_LIGHT.hover,
  // Violet is dark enough at this saturation that WHITE ink reads clearly on a filled button —
  // unlike the old gold, which needed dark ink to clear contrast.
  'accent-contrast': '#ffffff',
  'accent-soft': ACCENT_LIGHT.soft,
  'accent-on-soft': ACCENT_LIGHT.onSoft,
  success: '#0f7a54',
  'success-soft': '#dcefe4',
  'success-on-soft': '#0a5c3f',
  warning: '#b7791f',
  'warning-soft': '#f7ecd2',
  'warning-on-soft': '#8a5a12',
  // DANGER = coral, the same hue محلّي already uses for churn/at-risk attention — so a red flag
  // reads as the same colour language everywhere, not a leftover brick-red from the old theme.
  danger: '#d9472f',
  'danger-soft': '#ffe4dd',
  'danger-on-soft': '#b23a24',
  'danger-contrast': '#ffffff',
  // SECONDARY = teal. Also used for the info role.
  info: '#0a8871',
  'info-soft': '#dcf7f1',
  'info-on-soft': '#086e5c',
  // The gift accent (a free standard) must stay DISTINCT from the violet accent — so it is teal
  // here, the calm secondary, never the hue that now carries the brand.
  gift: '#0a8871',
  'gift-soft': '#dcf7f1',
  'gift-on-soft': '#086e5c',
  'gift-contrast': '#ffffff',
  'focus-ring': ACCENT_LIGHT.base,
  overlay: 'rgb(19 18 38 / 0.45)',
};

const dark: Palette = {
  // REBRANDED 2026-08-22, alongside `light` above — the same violet/teal/coral identity, re-hued
  // for a deep violet-black ground instead of the old navy. Structure (how far each step lifts,
  // where contrast is measured) carries over from the previous dark theme; only the hue changed.
  'surface-0': '#100f24',
  'surface-1': '#17162f',
  'surface-2': '#201f3d',
  'surface-3': '#2b2a4d',
  // Measured to stay ≥ 4.5:1 on surface-0/1, same bar as before.
  'text-primary': '#f1f0fb',
  'text-secondary': '#cfcee6',
  'text-muted': '#9c9bbe',
  'border-subtle': '#2c2b4c',
  'border-strong': '#423f6b',
  accent: ACCENT_DARK.base,
  'accent-hover': ACCENT_DARK.hover,
  'accent-contrast': '#17162f',
  'accent-soft': ACCENT_DARK.soft,
  'accent-on-soft': ACCENT_DARK.onSoft,
  success: '#34d399',
  'success-soft': '#0c2f26',
  'success-on-soft': '#6ee7b7',
  warning: '#e8c469',
  'warning-soft': '#3a2d0e',
  'warning-on-soft': '#f5d98d',
  danger: '#ff8a70',
  'danger-soft': '#3a1f16',
  'danger-on-soft': '#ffb49f',
  'danger-contrast': '#17162f',
  info: '#4fd9bd',
  'info-soft': '#123a32',
  'info-on-soft': '#9be9da',
  // Gift stays teal (distinct from the violet brand accent) on the dark ground.
  gift: '#4fd9bd',
  'gift-soft': '#123a32',
  'gift-on-soft': '#9be9da',
  'gift-contrast': '#0f0f24',
  'focus-ring': ACCENT_DARK.hover,
  overlay: 'rgb(8 7 20 / 0.62)',
};

const scale: Scale = {
  // 100% (=16px). 112.5% read oversized — the whole UI at ~90% browser zoom was the comfortable size,
  // i.e. 112.5%×0.9≈101%. Sizing the root here means every rem-based token shrinks together, so the
  // sidebar fits without a scroll and reading is easier, with no per-component change.
  rootFontPct: 100,
  // A touch more generous — a larger card radius reads as premium, not utilitarian.
  radius: { sm: '0.5rem', md: '0.625rem', lg: '0.875rem', card: '1.25rem', pill: '9999px' },
  // Layered elevation, SOFTENED. A tight contact shadow plus a large diffuse one at low opacity, so a
  // panel lifts off the ground without a heavy grey halo — the airy premium feel comes from big blur at
  // low opacity, not from a darker shadow. `glow` is the accent-tinted hover lift, the gift-card glow
  // generalised: any interactive card can wear it on hover and it picks up whatever the accent is.
  // Softly tinted toward the brand (royal-blue ink, not neutral black) so white cards lift off the airy
  // near-white canvas without a heavy grey halo — the premium feel comes from big blur at low opacity.
  // Tinted toward the NAVY ink (not neutral black) so white cards lift off the warm cream canvas with a
  // soft, premium halo — big blur at low opacity, never a heavy grey shadow.
  shadow: {
    sm: '0 1px 2px -1px rgb(21 29 51 / 0.10), 0 1px 1px rgb(21 29 51 / 0.05)',
    md: '0 2px 8px -3px rgb(21 29 51 / 0.12), 0 10px 26px -8px rgb(21 29 51 / 0.14)',
    lg: '0 8px 18px -8px rgb(21 29 51 / 0.14), 0 24px 52px -16px rgb(21 29 51 / 0.20)',
    pop: '0 12px 26px -12px rgb(21 29 51 / 0.18), 0 34px 72px -20px rgb(21 29 51 / 0.28)',
    glow: '0 10px 34px -8px color-mix(in srgb, var(--accent) 42%, transparent)',
  },
  motion: { fast: '120ms', base: '200ms', slow: '360ms', ease: 'cubic-bezier(0.22, 1, 0.36, 1)' },
  font: {
    // ONE central stack for the whole product — the premium identity face. IBM Plex Sans Arabic carries
    // BOTH Arabic and Latin with a formal, engineered feel (the "sealed document" voice); Inter is the
    // Latin fallback. To change it everywhere, swap the first family here AND the webfont @import in each
    // app's index.css — nothing else.
    sans: "'IBM Plex Sans Arabic', 'Inter', ui-sans-serif, system-ui, 'Segoe UI', Tahoma, Arial, sans-serif",
    mono: "'JetBrains Mono', ui-monospace, 'SFMono-Regular', Menlo, Consolas, monospace",
  },
};

export const themeConfig = {
  defaultAppearance: 'light' as Appearance,
  palettes: { light, dark } as Record<Appearance, Palette>,
  scale,
};

export type ThemeConfig = typeof themeConfig;
