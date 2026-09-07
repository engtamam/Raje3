/**
 * The canvas the door sits on — ours, and this is the one place a fork is worth it.
 *
 * THE KIT'S `AuthLayout` IS DELIBERATELY PLAIN: a split, with `bg-accent-soft/40` on the brand half
 * and nothing in it. That is correct for a component shipped to every product built on the platform
 * — it cannot know anyone's brand — and it is why our door looked like a form on a beige page while
 * the same palette, in another product, reads as premium.
 *
 * THE PALETTE IS NOT THE DIFFERENCE. It is byte-for-byte the same file: the same ivory ground
 * (#f6f4ef), the same navy ink (#151d33), the same gold. What was missing is COMPOSITION — a
 * committed dark hero, depth from layered light rather than from borders, and one large statement
 * instead of a label.
 *
 * SO THE HERO COMMITS TO ONE LOOK REGARDLESS OF THEME, exactly as the rest of the product refuses
 * to: the field screen must stay light because it is read on a tablet in an open workshop at noon,
 * and this screen is read once, indoors, before anyone owns anything. Different job, different
 * rule — and stating it here stops someone "fixing" the inconsistency later.
 *
 * IT IS HIDDEN ENTIRELY UNDER lg. On a phone the hero would be a screen of decoration between the
 * owner and the form he came for, and he would scroll past it every single time.
 */
import type { ReactNode } from 'react';
import { Mark, Wordmark } from '../brand/Mark';
import { legalUrl } from '../legal/url';

/**
 * Depth from LIGHT, not from boxes. Two soft pools of the brand gold over deep navy — the near one
 * warm and high, the far one cool and low — so the panel has a direction to it rather than being a
 * flat rectangle of colour. The values are the theme's, written out here because a gradient cannot
 * take a Tailwind token.
 */
const HERO: React.CSSProperties = {
  background:
    'radial-gradient(130% 110% at 18% 6%, rgba(184,134,43,0.30), transparent 58%),'
    + 'radial-gradient(120% 120% at 90% 96%, rgba(184,134,43,0.12), transparent 55%),'
    + 'linear-gradient(160deg, #101828, #151d33)',
};

export function DoorLayout({ children, title, subtitle }: {
  children: ReactNode;
  /** Overridable so a SECOND product on this canvas (the affiliate portal — a different
      audience, same visual language) is not stuck advertising «عملاؤك يرجعون» to a marketer
      who has no shop. Defaults to the shop's own copy so Door.tsx needs no change. */
  title?: ReactNode;
  subtitle?: ReactNode;
}) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-2">
      <aside
        className="relative hidden overflow-hidden p-12 lg:flex lg:flex-col lg:justify-between"
        style={HERO}
      >
        {/* THE MARK IS THE WAY OUT. This screen has no navigation at all — a person who opens it
            and changes his mind, or wants to read the page once more before committing, has
            nothing to press but the browser's back button, and on a link opened from WhatsApp
            there is no page behind it. So the mark leaves, which is where every site on earth
            puts that door. It is a plain <a> to '/' and not a router link: the landing page is
            served outside this bundle. */}
        <a href="/" className="flex items-center gap-3 text-[#f4efe2]" aria-label="العودة إلى الصفحة الرئيسية">
          <Mark size={40} />
          <Wordmark className="text-lg" />
        </a>

        <div className="max-w-md">
          {/* ONE SENTENCE, AND IT IS THE PRODUCT. Not a feature list — a person deciding whether to
              sign up is deciding whether the idea is worth ten minutes, not comparing specs. */}
          <h1 className="text-4xl leading-tight tracking-tight text-[#f4efe2]">
            {title ?? 'عملاؤك يرجعون، من نفسهم.'}
          </h1>
          <p className="mt-4 text-[15px] leading-relaxed text-[#c9c2b3]">
            {subtitle ?? (
              'راجِع يتذكّر متى يحتاج كل عميل خدمته القادمة، ويذكّره على واتساب باسم محلك — بلا أن '
              + 'تفتح التطبيق.'
            )}
          </p>
        </div>

        <p className="text-xs text-[#8d8778]">راجِع · السعودية</p>
      </aside>

      <main className="flex items-center justify-center bg-surface-0 p-6">
        <div className="w-full max-w-sm">
          {/* The mark again, for the phone — where the hero does not exist and the page would
              otherwise open on a segmented control with no idea what product it belongs to. */}
          {/* And on the phone, where the hero panel does not exist, this is the ONLY mark on the
              screen — so it carries the whole burden of saying both what this is and how to leave.
              A dead logo on a page with no other exit is a page people abandon. */}
          <a href="/" className="mb-8 flex items-center gap-2 lg:hidden" aria-label="العودة إلى الصفحة الرئيسية">
            <Mark size={32} />
            <Wordmark className="text-base" />
          </a>
          {children}

          {/* MARKETING'S FOOTER, MINIATURE — this screen is the one place a signed-out visitor may
              land with NO landing page behind it at all (a direct link, or a future "skip the
              landing page" mode). The legal links must be reachable from here on their own, not
              only from marketing/index.html's footer. */}
          <p className="mt-10 flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-xs text-text-muted">
            <span>© راجِع — جميع الحقوق محفوظة</span>
            <a href={legalUrl('terms')} target="_blank" rel="noreferrer" className="hover:text-text-secondary">
              الشروط
            </a>
            <a href={legalUrl('privacy-policy')} target="_blank" rel="noreferrer" className="hover:text-text-secondary">
              الخصوصية
            </a>
          </p>
        </div>
      </main>
    </div>
  );
}
