/**
 * راجِع — the wordmark, and the ONLY mark (2026-09-16).
 *
 * THE DRAWN ICON IS GONE, ON PURPOSE. The product had a graphic "journey that closes" mark — an
 * arc leaving a dot and an arrowhead turning back into it — and the owner's own instruction was
 * direct: the design was not working, and the name itself, set in type, is the better logo. So
 * there is no separate glyph any more, anywhere: the sidebar, the sign-in screens, the welcome
 * dialog and the browser tab (public/favicon.svg) all show the same thing — راجِع, spelled out,
 * with its kasra.
 *
 * THE KASRA IS LOAD-BEARING, NOT DECORATION. راجَع and راجِع are different words: the first is
 * "he reviewed / went over the accounts", the second is the one about bringing someone back. A
 * product whose whole premise is the returning customer cannot be ambiguous about which word its
 * own name is, and Arabic readers resolve an unvowelled راجع by context — of which a logo has
 * none. So the vowel is written, here and everywhere the name appears — INCLUDING the tightest
 * spots (a 26px collapsed sidebar rail, a 16px favicon): the owner's own call, once shown the
 * alternative (an initial letter alone) and asked which he preferred.
 */
export const NAME_AR = 'راجِع';
export const NAME_EN = 'Raje3';

export function Wordmark({
  locale = 'ar',
  compact = false,
  className,
}: {
  locale?: 'ar' | 'en';
  /** For the tightest slots — the collapsed sidebar rail, a mobile header icon — where the full
   *  word still has to read as itself rather than truncate or overflow its box. Fixed, small type
   *  rather than inheriting the surrounding context's font-size, which is exactly what those slots
   *  do not control (a 26px square gives an ambient `font-size` no say at all). */
  compact?: boolean;
  className?: string;
}) {
  return (
    <span
      className={className}
      style={{
        fontFamily: 'var(--font-display, "Cairo", "Tajawal", system-ui, sans-serif)',
        fontWeight: 800,
        color: 'var(--accent)',
        display: 'inline-block',
        lineHeight: 1,
        ...(compact ? { fontSize: '13px', letterSpacing: 0 } : {}),
        // ARABIC KEEPS ITS NATURAL SPACING outside the compact slots. Negative tracking is a Latin
        // habit: it tightens letters that stand apart, and in a connected script it pulls joined
        // letterforms into each other — «راجِع» loses the seat its kasra sits on before anyone can
        // say why the logo looks wrong.
        ...(!compact ? { letterSpacing: locale === 'en' ? '-0.01em' : 0 } : {}),
      }}
    >
      {locale === 'ar' ? NAME_AR : NAME_EN}
    </span>
  );
}
