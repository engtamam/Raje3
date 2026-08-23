/**
 * The welcome dialog — shown exactly once, the moment a brand-new shop first lands inside.
 *
 * WHY THIS EXISTS AT ALL. A fresh signup used to walk straight into the ordinary app with nothing
 * marking the moment — no confirmation his shop was real, no word that the free trial billing
 * quietly opened behind the scenes (see `services/operations/app/core/signup.py`'s own
 * `_start_base_trial`) had actually started. Tamam, on seeing a brand-new account: «وهو عنده
 * فترة تجربة ايضا شهر كامل … ابغ كمان ترحيب فيه بعد التسجيل … خليها فخمة كذا وراقية الترحيب».
 *
 * A DIALOG OVER THE APP, NOT A SECOND PAGE. The first version replaced App's whole render tree —
 * Tamam's own report: nothing right after signup (App had already mounted with nothing in
 * sessionStorage yet, before `onWelcome` existed — see App.tsx), then a screen that COVERED
 * EVERYTHING after a refresh remounted it. Fixing the timing bug alone would still have left a
 * full-bleed page; he asked for it as «نافذة منبثقة … نافذة وسط الشاشة» — a dialog, portalled over
 * the shop he is about to see, not a page that replaces it.
 *
 * THE SAME DARK/GOLD HERO `DoorLayout.tsx` COMMITS TO, not a fork of it — that file's own note
 * already states the rule this dialog follows: a moment read once, before anyone owns anything,
 * earns one deliberate look regardless of theme, unlike the field screen a shop stares at all day.
 * Kept as its own card rather than the generic `rj-ui/Modal` for that reason — this is a moment,
 * not a form, and the kit's modal chrome (title bar, muted surface, a close-X) is built for those.
 *
 * NO DAY COUNT IS EVER PRINTED HERE. How long a trial runs is billing's own decision (a plan's
 * `trial_days`, editable without a deploy) — the marketing page's own rule
 * (marketing/index.html's "NO TRIAL, NO PRICE, NO DURATION") is that no duration is ever promised
 * in text that outlives the setting behind it. The real end date travels from the signup response
 * instead (`trial_end`, unix seconds) and is shown as a date, never a promise about how many days
 * that date is away.
 */
import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Mark, Wordmark } from '../brand/Mark';
import { Button } from '../rj-ui/Button';
import { Sparkles } from 'lucide-react';

const CARD: React.CSSProperties = {
  background:
    'radial-gradient(130% 110% at 18% 6%, rgba(184,134,43,0.30), transparent 58%),'
    + 'radial-gradient(120% 120% at 90% 96%, rgba(184,134,43,0.12), transparent 55%),'
    + 'linear-gradient(160deg, #101828, #151d33)',
};

const WEEKDAYS_AR = ['الأحد', 'الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت'];
const MONTHS_AR = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
                   'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'];

function humanDate(epochSeconds: number): string {
  const d = new Date(epochSeconds * 1000);
  return `${WEEKDAYS_AR[d.getDay()]} ${d.getDate()} ${MONTHS_AR[d.getMonth()]} ${d.getFullYear()}`;
}

export function WelcomeTrial({ trialEnd, onDone }: { trialEnd: number; onDone: () => void }) {
  // SAME SCROLL-LOCK + ESCAPE-TO-CLOSE `rj-ui/Modal` ALREADY ESTABLISHES for a dialog over the
  // app — this one has no separate close affordance (the whole point is one deliberate button),
  // so Escape maps to the same "لنبدأ" action rather than leaving him stuck with no way out.
  useEffect(() => {
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onDone(); };
    document.addEventListener('keydown', onKey);
    return () => {
      document.body.style.overflow = prevOverflow;
      document.removeEventListener('keydown', onKey);
    };
  }, [onDone]);

  return createPortal(
    <div className="fixed inset-0 z-50 grid place-items-center p-4" role="dialog" aria-modal="true" aria-label="أهلاً بك في راجِع">
      {/* NO CLICK-OUTSIDE-TO-CLOSE — unlike the generic modal, dismissing this by accident loses
          the one place the trial's real end date is stated; «لنبدأ» is the one deliberate way out. */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" aria-hidden />
      <div
        className="animate-in relative z-10 flex w-full max-w-sm flex-col items-center gap-6 rounded-3xl p-8 text-center shadow-2xl"
        style={CARD}
      >
        <div className="flex items-center gap-3 text-[#f4efe2]">
          <Mark size={36} />
          <Wordmark className="text-base" />
        </div>

        <div
          className="grid size-14 place-items-center rounded-full"
          style={{ background: 'rgba(184,134,43,0.18)', boxShadow: '0 0 0 1px rgba(184,134,43,0.35)' }}
        >
          <Sparkles size={24} className="text-[#e3b957]" aria-hidden />
        </div>

        <div>
          <h1 className="text-2xl leading-tight tracking-tight text-[#f4efe2]">
            أهلاً بك في راجِع
          </h1>
          <p className="mt-2.5 text-[14px] leading-relaxed text-[#c9c2b3]">
            محلّك جاهز، وتجربتك المجانية بدأت الآن — كل شيء مفتوح أمامك بلا أي إعداد.
          </p>
          {trialEnd > 0 ? (
            <p className="mt-3.5 rounded-card px-3.5 py-2 text-[13px] text-[#e3b957]"
              style={{ background: 'rgba(184,134,43,0.12)', border: '1px solid rgba(184,134,43,0.3)' }}>
              تجربتك سارية حتى {humanDate(trialEnd)}
            </p>
          ) : null}
        </div>

        <Button
          onClick={onDone}
          className="w-full bg-[#e3b957] text-[#151d33] hover:bg-[#d4a944]"
        >
          لنبدأ
        </Button>

        <p className="text-xs text-[#8d8778]">راجِع · السعودية</p>
      </div>
    </div>,
    document.body,
  );
}
