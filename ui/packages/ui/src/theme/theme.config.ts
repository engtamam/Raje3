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
  /** THE GOLD COMPANION — added 2026-09-07 alongside the Lumera rebrand (config/product.json's own
   *  `brand.secondaryAccent`: personal-care-company/hair-analysis-platform's "Lumera — Majestic
   *  Design System", adopted as Raje3's own reference for a premium feel). Same five-token ramp
   *  shape as `accent`, deliberately: a component that already knows how to render an accent-toned
   *  surface (soft bg + on-soft text + a solid fill with real contrast ink) renders a gold one with
   *  zero new logic, just a different token family. NEVER the default emphasis colour — gold is for
   *  a component that explicitly asks for the premium/gift treatment; the everyday primary action
   *  stays `accent`. */
  secondary: string;
  'secondary-hover': string;
  'secondary-contrast': string;
  'secondary-soft': string;
  'secondary-on-soft': string;
  /** REAL GRADIENT STRINGS, not derived at the call site — the other half of the Lumera rebrand: a
   *  flat single-hue fill was the single biggest visual gap next to محلّي's own hero cards
   *  (Shop.tsx's RetentionHero) and the sister mobile app's gradient-everywhere surfaces.
   *  Appearance-aware (dark needs different stops than light, not just darker ones), so a component
   *  reaches for ONE token instead of hand-rolling colour stops that drift from the palette.
   *  `gradient-hero` mirrors RetentionHero's own background exactly. */
  'gradient-accent': string;
  'gradient-gold': string;
  'gradient-hero': string;
  'gradient-ground': string;
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
  /** Elevation shadows (control-room: soft, low-spread). `glow` is accent-tinted; `glow-gold` is the
   *  same treatment tinted by `--secondary` instead — for a component that wants the premium-gold
   *  hover lift specifically (a gift/upgrade card, never the everyday interactive one). */
  shadow: { sm: string; md: string; lg: string; pop: string; glow: string; 'glow-gold': string };
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

// THE GOLD COMPANION, injected the SAME way — config/product.json's own `brand.secondaryAccent`, via
// vite.config.ts's __PRODUCT_SECONDARY_ACCENT__ define (mirrors __PRODUCT_ACCENT__'s own wiring).
// Fallback matches Lumera's own metallic-gold secondary, for a context with no define.
declare const __PRODUCT_SECONDARY_ACCENT__: { light: string; dark: string };
const BRAND_SECONDARY = typeof __PRODUCT_SECONDARY_ACCENT__ !== 'undefined'
  ? __PRODUCT_SECONDARY_ACCENT__
  : { light: '#D4AF37', dark: '#E8C547' };

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

// GOLD ramp, same shape — gold is a mid-tone either way, so BOTH light and dark take dark ink on
// the solid fill (mirrors Lumera's own accent-contrast choice for its gold secondary).
const SECONDARY_LIGHT = {
  base: BRAND_SECONDARY.light,
  hover: mix(BRAND_SECONDARY.light, '#000000', 0.18),
  soft: mix(BRAND_SECONDARY.light, '#ffffff', 0.85),
  onSoft: mix(BRAND_SECONDARY.light, '#000000', 0.45),
};
const SECONDARY_DARK = {
  base: BRAND_SECONDARY.dark,
  hover: mix(BRAND_SECONDARY.dark, '#ffffff', 0.22),
  soft: mix(BRAND_SECONDARY.dark, '#0a0e1a', 0.78),
  onSoft: mix(BRAND_SECONDARY.dark, '#ffffff', 0.35),
};

const light: Palette = {
  // REBRANDED 2026-09-07 — "Lumera — Majestic Design System", the sister mobile app's own theme
  // (personal-care-company/hair-analysis-platform), adopted as Raje3's own PRIMARY design reference
  // ("مصدرنا الأساسي تطبيق الجوال"). Replaces the violet/teal/coral identity built for محلّي, itself
  // a rebrand of an earlier gold/ivory theme — this is a return to gold, now paired with a deeper
  // Royal Amethyst rather than standing alone against a cool-white ground. Every hex below is taken
  // directly from Lumera's own `AppColors`, not re-derived or approximated.
  'surface-0': '#fdf8ff',
  'surface-1': '#ffffff',
  'surface-2': '#f3eafa',
  'surface-3': '#e5d3f5',
  'text-primary': '#1a0a2e',
  'text-secondary': '#6b5880',
  'text-muted': '#a993bb',
  'border-subtle': '#e5d3f5',
  'border-strong': '#d3a9ef',
  accent: ACCENT_LIGHT.base,
  'accent-hover': ACCENT_LIGHT.hover,
  // Royal Amethyst is dark enough that WHITE ink reads clearly on a filled button.
  'accent-contrast': '#ffffff',
  'accent-soft': ACCENT_LIGHT.soft,
  'accent-on-soft': ACCENT_LIGHT.onSoft,
  secondary: SECONDARY_LIGHT.base,
  'secondary-hover': SECONDARY_LIGHT.hover,
  // Gold is a mid-tone: dark ink reads far higher contrast on it than white does.
  'secondary-contrast': '#1a0a2e',
  'secondary-soft': SECONDARY_LIGHT.soft,
  'secondary-on-soft': SECONDARY_LIGHT.onSoft,
  'gradient-accent': 'linear-gradient(135deg, #5c1b7a 0%, #9348cc 100%)',
  'gradient-gold': 'linear-gradient(90deg, #d4af37 0%, #f5ce3f 100%)',
  // Mirrors Shop.tsx's RetentionHero background exactly — a violet-to-teal-ish radial pair over a
  // deep royal linear base, the one hero treatment already built, shipped, and approved.
  'gradient-hero': 'radial-gradient(120% 90% at 15% 0%, #8f6bff 0%, transparent 55%),'
    + 'radial-gradient(110% 100% at 100% 100%, #0fb897 0%, transparent 50%),'
    + 'linear-gradient(160deg,#4c34c4,#2a1f7a)',
  'gradient-ground': 'linear-gradient(180deg, #fdf8ff 0%, #f3eafa 100%)',
  success: '#2e9b58',
  'success-soft': '#d4f5e3',
  'success-on-soft': '#1f7a44',
  warning: '#d97706',
  'warning-soft': '#fef3c7',
  'warning-on-soft': '#92400e',
  danger: '#dc2626',
  'danger-soft': '#ffe4e6',
  'danger-on-soft': '#b91c1c',
  'danger-contrast': '#ffffff',
  info: '#1d6fa4',
  'info-soft': '#dbeafa',
  'info-on-soft': '#155d8a',
  // The gift accent (a free standard) stays distinct from BOTH brand hues — Lumera's own
  // `mintFresh`, never the violet accent (means "act on this") or the gold secondary (means
  // "premium/gift" in a DIFFERENT, more deliberate sense — an upgrade CTA, not a free perk).
  gift: '#4caf50',
  'gift-soft': '#e3f4e4',
  'gift-on-soft': '#2e7d32',
  'gift-contrast': '#ffffff',
  'focus-ring': ACCENT_LIGHT.base,
  overlay: 'rgb(26 10 46 / 0.45)',
};

const dark: Palette = {
  // Lumera's own `AppDarkColors` — a rich near-black with a violet undertone ("night control
  // room"), not flat charcoal. Same rebrand as `light` above.
  'surface-0': '#080412',
  'surface-1': '#180b30',
  'surface-2': '#221240',
  'surface-3': '#2c1850',
  // Measured to stay ≥ 4.5:1 on surface-0/1 (Lumera's own bar, carried over).
  'text-primary': '#f0e6ff',
  'text-secondary': '#c4a8e0',
  'text-muted': '#8b6fa8',
  'border-subtle': '#3d2260',
  'border-strong': '#3d2260',
  accent: ACCENT_DARK.base,
  'accent-hover': ACCENT_DARK.hover,
  'accent-contrast': '#1a0a2e',
  'accent-soft': ACCENT_DARK.soft,
  'accent-on-soft': ACCENT_DARK.onSoft,
  secondary: SECONDARY_DARK.base,
  'secondary-hover': SECONDARY_DARK.hover,
  'secondary-contrast': '#1a0a2e',
  'secondary-soft': SECONDARY_DARK.soft,
  'secondary-on-soft': SECONDARY_DARK.onSoft,
  'gradient-accent': 'linear-gradient(135deg, #9348cc 0%, #bf7fe0 100%)',
  'gradient-gold': 'linear-gradient(180deg, #e8c547 0%, #d4af37 50%, #b8960f 100%)',
  'gradient-hero': 'radial-gradient(120% 90% at 15% 0%, #9348cc 0%, transparent 55%),'
    + 'radial-gradient(110% 100% at 100% 100%, #4fd9bd 0%, transparent 50%),'
    + 'linear-gradient(160deg,#221240,#080412)',
  'gradient-ground': 'linear-gradient(180deg, #080412 0%, #0f0820 100%)',
  success: '#34d399',
  'success-soft': '#0c2f26',
  'success-on-soft': '#6ee7b7',
  warning: '#e8c469',
  'warning-soft': '#3a2d0e',
  'warning-on-soft': '#f5d98d',
  danger: '#f0836a',
  'danger-soft': '#3a1a12',
  'danger-on-soft': '#f7b3a1',
  'danger-contrast': '#080412',
  info: '#5eccc0',
  'info-soft': '#0c322e',
  'info-on-soft': '#9be3d9',
  gift: '#6ee7b7',
  'gift-soft': '#0c2f26',
  'gift-on-soft': '#a7f3d0',
  'gift-contrast': '#080412',
  'focus-ring': ACCENT_DARK.hover,
  overlay: 'rgb(5 2 9 / 0.62)',
};

const scale: Scale = {
  // 100% (=16px). 112.5% read oversized — the whole UI at ~90% browser zoom was the comfortable size,
  // i.e. 112.5%×0.9≈101%. Sizing the root here means every rem-based token shrinks together, so the
  // sidebar fits without a scroll and reading is easier, with no per-component change.
  rootFontPct: 100,
  // A touch more generous — a larger card radius reads as premium, not utilitarian.
  radius: { sm: '0.5rem', md: '0.625rem', lg: '0.875rem', card: '1.25rem', pill: '9999px' },
  // BRAND-TINTED, LAYERED, "DEEPER / MORE DRAMATIC FOR A MAJESTIC FEEL" — Lumera's own AppShadows
  // docstring, adopted verbatim as the goal here. Each step pairs a tight contact shadow with a
  // large diffuse one, BOTH tinted by the accent colour itself (`color-mix` against `--accent`)
  // rather than neutral ink — this is what makes a white card lift off the ground looking like it
  // belongs to a coloured, considered surface instead of a generic grey elevation system. Alpha
  // rises with each step, mirroring Lumera's own escalating 0.14 → 0.50 ramp.
  shadow: {
    sm: '0 1px 3px -1px color-mix(in srgb, var(--accent) 14%, transparent), '
      + '0 1px 2px color-mix(in srgb, var(--accent) 6%, transparent)',
    md: '0 4px 10px -3px color-mix(in srgb, var(--accent) 16%, transparent), '
      + '0 2px 6px -2px color-mix(in srgb, var(--accent) 8%, transparent)',
    lg: '0 10px 22px -8px color-mix(in srgb, var(--accent) 22%, transparent), '
      + '0 4px 12px -4px color-mix(in srgb, var(--accent) 10%, transparent)',
    pop: '0 18px 38px -12px color-mix(in srgb, var(--accent) 30%, transparent), '
      + '0 8px 20px -6px color-mix(in srgb, var(--accent) 12%, transparent)',
    glow: '0 10px 34px -8px color-mix(in srgb, var(--accent) 42%, transparent)',
    // GOLD GLOW — same shape, tinted by `--secondary` instead, for a component that wants the
    // premium-gold hover lift specifically (mirrors Lumera's own AppShadows.gold).
    'glow-gold': '0 10px 34px -8px color-mix(in srgb, var(--secondary) 45%, transparent), '
      + '0 3px 10px -2px color-mix(in srgb, var(--secondary) 15%, transparent)',
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
