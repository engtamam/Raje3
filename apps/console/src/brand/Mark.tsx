/**
 * راجِع — the mark.
 *
 * COPIED FROM platform/ui's BrandMark AND REPLACED, which is the one case our alias rule allows:
 * we consume the kit by reference and fork only a component we must change. Theirs is a notary
 * seal — a ring holding a checkmark, saying "sealed · verified". That is a compliance product's
 * mark, and it is not ours.
 *
 * WHAT OURS HAS TO SAY: a customer went away and came back. That is the entire product, and it is
 * also the word — راجِع, the one who returns.
 *
 * SO THE MARK IS A JOURNEY THAT CLOSES. A dot at the centre is the shop. An arc leaves it, opens,
 * and an arrowhead turns back toward it. Not a refresh glyph, which means "do it again"; this one
 * has a destination and returns TO it.
 *
 * FOUR PLACES IT MUST SURVIVE, and they pull against each other:
 *
 *   24px in the collapsed sidebar rail   → no detail finer than the stroke itself
 *   a WhatsApp profile, cropped round    → the whole mark sits inside a circle with margin
 *   monochrome, on an invoice            → it carries no colour information at all
 *   a favicon                            → the same, at 16px
 *
 * Which is why there is no gradient, no second colour, and nothing inside the arc. It takes
 * `--accent` from the theme like every other token, so an establishment's own colour overrides it
 * on the customer page without touching this file — and on that page the mark is not rendered at
 * all (spec 8.6.1): the customer sees his shop, not a product his shop bought.
 */
export function Mark({ size = 26, className }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      className={className}
      aria-hidden="true"
      focusable="false"
      style={{ color: 'var(--accent)' }}
    >
      {/* THE JOURNEY. An arc that opens at the top-right — the customer leaving — drawn thick
          enough to hold at 16px, and stopping short so the gap reads as absence rather than as a
          broken circle. */}
      <path
        d="M16 5.2a10.8 10.8 0 1 1-7.9 3.4"
        stroke="currentColor"
        strokeWidth="2.6"
        strokeLinecap="round"
        fill="none"
      />
      {/* THE RETURN. The arrowhead points back INTO the ring rather than along it — the difference
          between "going round again" and "coming back". */}
      <path
        d="M6.6 4.9 8.1 9.2 12.4 8.1"
        stroke="currentColor"
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
      {/* THE SHOP. Filled, because it is the one thing that does not move. */}
      <circle cx="16" cy="16" r="3.4" fill="currentColor" />
    </svg>
  );
}

/**
 * The wordmark.
 *
 * THE KASRA IS LOAD-BEARING, NOT DECORATION. راجَع and راجِع are different words: the first is
 * "he reviewed / went over the accounts", the second is the one about bringing someone back. A
 * product whose whole premise is the returning customer cannot be ambiguous about which word its
 * own name is, and Arabic readers resolve an unvowelled راجع by context — of which a logo has
 * none. So the vowel is written, here and everywhere the name appears.
 */
export const NAME_AR = 'راجِع';
export const NAME_EN = 'Raje3';

export function Wordmark({ locale = 'ar', className }: { locale?: 'ar' | 'en'; className?: string }) {
  return (
    <span className={className} style={{ fontWeight: 700, letterSpacing: locale === 'en' ? '-0.01em' : 0 }}>
      {locale === 'ar' ? NAME_AR : NAME_EN}
    </span>
  );
}
