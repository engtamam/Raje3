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
  /** Font families (Arabic-aware face swapped at dir=rtl in index.css).
   *  `display` — REBRANDED 2026-09-12, alongside the paper/violet palette below: the mockup this
   *  rebrand is drawn from pairs a heavier display face (Cairo, headings/numbers) with a lighter
   *  body face (Tajawal) — two jobs one `sans` token cannot do at once. `display` is new and
   *  consumed so far only by `PageHeader` (see that file), the one shared component nearly every
   *  screen's own title already renders through — the cheapest single point that reaches the
   *  whole product without a per-screen change. */
  font: { sans: string; display: string; mono: string };
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
  // REBRANDED AGAIN 2026-09-14, THE OWNER'S OWN DIRECT INSTRUCTION: "أبغى أغيّر لون البراند
  // للأبيض... كله بيجي يصير أبيض وبنفسجي" — the warm cream/paper identity (2026-09-12) is
  // retired in favour of a clean neutral white/grey ground, SAME violet accent (unchanged —
  // never was part of the complaint), same semantic colours (success/warning/danger/info/gift
  // were never tied to the cream hue family either). The page itself is a hair off pure white
  // (`surface-0`) so a white CARD (`surface-1`) still visibly lifts off it — true page-white AND
  // card-white at once would erase that lift entirely, the one thing a "white" redesign must not
  // also flatten.
  'surface-0': '#f7f8fa',
  'surface-1': '#ffffff',
  // THE SAME "REAL STEP, NOT A HAIRLINE" SEPARATION THE 2026-09-13 WIDENING ESTABLISHED — carried
  // over verbatim in spirit, just re-based on a neutral grey family instead of warm cream: a
  // chip's OFF state, a toggle's OFF track, an unselected tab must all still read as a visibly
  // different surface from the page under them.
  'surface-2': '#e7e9ee',
  'surface-3': '#d7dae2',
  'text-primary': '#14161c',
  'text-secondary': '#5b6270',
  'text-muted': '#868c99',
  'border-subtle': '#dde0e7',
  'border-strong': '#c5cad4',
  accent: ACCENT_LIGHT.base,
  'accent-hover': ACCENT_LIGHT.hover,
  // Violet is dark enough at this saturation that WHITE ink reads clearly on a filled button —
  // unlike the old gold, which needed dark ink to clear contrast.
  'accent-contrast': '#ffffff',
  'accent-soft': ACCENT_LIGHT.soft,
  'accent-on-soft': ACCENT_LIGHT.onSoft,
  success: '#1e9e82',
  'success-soft': '#dcf3ec',
  'success-on-soft': '#146b58',
  warning: '#c99a2c',
  'warning-soft': '#f7ecd2',
  'warning-on-soft': '#8a6a1e',
  // DANGER = coral, the same hue محلّي already uses for churn/at-risk attention — so a red flag
  // reads as the same colour language everywhere, not a leftover brick-red from the old theme.
  danger: '#d9584a',
  'danger-soft': '#fbe1dd',
  'danger-on-soft': '#b7412f',
  'danger-contrast': '#ffffff',
  // ITS OWN BLUE NOW, DISTINCT FROM `gift` BELOW — the two shared one teal hex before this pass,
  // meaning an informational note and a free-standard ribbon looked identical by accident.
  info: '#5a96dc',
  'info-soft': '#e3edfa',
  'info-on-soft': '#2f5f8f',
  // The gift accent (a free standard) must stay DISTINCT from the violet accent AND from `info`
  // above — so it keeps the calm teal that used to be shared, never a hue that means something
  // else on the same screen.
  gift: '#0a8871',
  'gift-soft': '#dcf7f1',
  'gift-on-soft': '#086e5c',
  'gift-contrast': '#ffffff',
  'focus-ring': ACCENT_LIGHT.base,
  overlay: 'rgb(20 22 28 / 0.45)',
};

const dark: Palette = {
  // REBRANDED AGAIN 2026-09-12, alongside `light` above — not a fresh guess: this is the exact
  // deep-plum look already shipped and approved on TWO real surfaces before this pass existed
  // (Rating.tsx's own `.rating-podium-card.rank-1`, and the campaigns mockup's own phone-preview
  // card) — `#241640 → #120a24`, cream ink. Promoted from those two one-off scoped treatments to
  // the platform's own dark theme, so the whole product's dark mode now IS what those two cards
  // already were, instead of a third, unrelated dark identity sitting beside them.
  'surface-0': '#120a24',
  'surface-1': '#1c1440',
  'surface-2': '#241c4d',
  'surface-3': '#2d235c',
  // Measured to stay ≥ 4.5:1 on surface-0/1, same bar as before.
  'text-primary': '#f6efdd',
  'text-secondary': '#cfc6e8',
  'text-muted': '#9c93b8',
  'border-subtle': '#322a58',
  'border-strong': '#443a72',
  accent: ACCENT_DARK.base,
  'accent-hover': ACCENT_DARK.hover,
  'accent-contrast': '#1c1440',
  'accent-soft': ACCENT_DARK.soft,
  'accent-on-soft': ACCENT_DARK.onSoft,
  success: '#3ddba8',
  'success-soft': '#0e3229',
  'success-on-soft': '#8fe9cd',
  warning: '#e8c469',
  'warning-soft': '#3a2d0e',
  'warning-on-soft': '#f5d98d',
  danger: '#ff9585',
  'danger-soft': '#3a1f16',
  'danger-on-soft': '#ffb49f',
  'danger-contrast': '#1c1440',
  // ITS OWN BLUE, matching `light`'s own split of what used to be one shared teal into a
  // distinct info/gift pair (see that palette's own note).
  info: '#6fa8ea',
  'info-soft': '#1c2f4a',
  'info-on-soft': '#a9cdf2',
  // Gift stays teal (distinct from the violet brand accent and now from `info` too) on the dark
  // ground.
  gift: '#4fd9bd',
  'gift-soft': '#123a32',
  'gift-on-soft': '#9be9da',
  'gift-contrast': '#120a24',
  'focus-ring': ACCENT_DARK.hover,
  overlay: 'rgb(10 6 20 / 0.62)',
};

const scale: Scale = {
  // 80% (=12.8px), RAISED BACK UP A STEP — the owner's own direct request, one step back from the
  // 70% pass just before it. Since browser zoom and this token scale the exact same rem-based
  // sizing, this reproduces "browser zoomed to 80%" at the page's own 100% zoom.
  //
  // WHAT THIS DOES NOT REACH, AND WHY THINGS MAY STILL LOOK SLIGHTLY LARGE IN ONE SPOT: an icon
  // drawn via `<Icon size={16} />` (lucide-react's own `size` prop) renders a literal PIXEL
  // width/height, not a rem value — real browser zoom shrinks it like everything else on the
  // page, but this token cannot, since nothing here touches how a component calls that prop. If a
  // particular icon still reads oversized after this change, that call site's own `size={N}` is
  // the thing to lower, not this token — it is a real, separate, per-component number, the same
  // way `radius`/`shadow` below are real per-token numbers rather than one dial.
  rootFontPct: 80,
  // A touch more generous — a larger card radius reads as premium, not utilitarian.
  radius: { sm: '0.5rem', md: '0.625rem', lg: '0.875rem', card: '1.25rem', pill: '9999px' },
  // Layered elevation, SOFTENED. A tight contact shadow plus a large diffuse one at low opacity, so a
  // panel lifts off the ground without a heavy grey halo — the airy premium feel comes from big blur at
  // low opacity, not from a darker shadow. `glow` is the accent-tinted hover lift, the gift-card glow
  // generalised: any interactive card can wear it on hover and it picks up whatever the accent is.
  // TINTED TOWARD THE NEW WARM INK (#1b1712, "27 23 18" below), REBRANDED 2026-09-12 alongside
  // the palette above — the previous tint (a cool navy-ink rgb) was left over from before the
  // paper/violet identity existed; white cards now lift off the warm cream canvas with a soft
  // premium halo that actually matches the ground they sit on.
  shadow: {
    sm: '0 1px 2px -1px rgb(20 22 28 / 0.10), 0 1px 1px rgb(20 22 28 / 0.05)',
    md: '0 2px 8px -3px rgb(20 22 28 / 0.12), 0 10px 26px -8px rgb(20 22 28 / 0.14)',
    lg: '0 8px 18px -8px rgb(20 22 28 / 0.14), 0 24px 52px -16px rgb(20 22 28 / 0.20)',
    pop: '0 12px 26px -12px rgb(20 22 28 / 0.18), 0 34px 72px -20px rgb(20 22 28 / 0.28)',
    glow: '0 10px 34px -8px color-mix(in srgb, var(--accent) 42%, transparent)',
  },
  motion: { fast: '120ms', base: '200ms', slow: '360ms', ease: 'cubic-bezier(0.22, 1, 0.36, 1)' },
  font: {
    // BODY FACE — Tajawal, the mockup's own choice for running text (buttons, labels, table
    // cells): lighter and more legible at small sizes than a heavier display face would be.
    // REBRANDED 2026-09-12 — IBM Plex Sans Arabic/Inter were declared here since the previous
    // rebrand but NEVER ACTUALLY LOADED by any app in this repo (no webfont link existed
    // anywhere), so the whole product has always rendered in the browser's own default
    // sans-serif regardless of what this token said. Fixed alongside this change —
    // apps/console/index.html now actually links Cairo + Tajawal, and index.css now actually
    // applies `--font-sans` to `body` — both previously missing, not just re-pointed.
    sans: "'Tajawal', 'Cairo', ui-sans-serif, system-ui, 'Segoe UI', Tahoma, Arial, sans-serif",
    // DISPLAY FACE — Cairo, heavier weights (600-900) for headings and big numbers — the
    // mockup's own pairing. See this interface's own docstring for where it is actually consumed.
    display: "'Cairo', 'Tajawal', ui-sans-serif, system-ui, 'Segoe UI', Tahoma, Arial, sans-serif",
    mono: "'JetBrains Mono', ui-monospace, 'SFMono-Regular', Menlo, Consolas, monospace",
  },
};

/**
 * NAV_ACCENTS — one hue per sidebar section (2026-09-13, the owner's own instruction: "كل أيقونة
 * لازم لون يميّزها", every icon needs its own distinguishing colour — a single flat amber for
 * every active item read as "everything is one colour", exactly the complaint). A CATEGORICAL
 * SET, never cycled: consumed positionally by apps/console/src/nav.ts's own SECTIONS, one entry
 * per section, in the SAME fixed order every time — a future 11th section gets its own new hue
 * appended here, never a repeat of an earlier one. Deliberately clear of the four semantic
 * colours (danger/warning/success/gift) and the brand accent above, so a nav icon's colour is
 * never mistaken for a status or for "act on this" — these mean nothing but "this is where you
 * are", the same role the single amber used to carry alone. Same ten hexes in both appearances:
 * picked at a lightness/saturation that reads clearly on both the light cream ground and the
 * dark plum one, so one set serves both rather than needing a second table to keep in sync.
 */
export const NAV_ACCENTS = [
  '#1971C2', // 0 — blue
  '#2F9E44', // 1 — green
  '#F08C00', // 2 — orange
  '#E64980', // 3 — pink
  '#862E9C', // 4 — purple
  '#0C8599', // 5 — dark cyan
  '#5C7CFA', // 6 — indigo
  '#099268', // 7 — teal
  '#495057', // 8 — slate
  '#C2255C', // 9 — rose
] as const;

export const themeConfig = {
  defaultAppearance: 'light' as Appearance,
  palettes: { light, dark } as Record<Appearance, Palette>,
  scale,
};

export type ThemeConfig = typeof themeConfig;
