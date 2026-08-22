/**
 * The welcome screen — shown exactly once, the moment a brand-new shop first lands inside.
 *
 * WHY THIS EXISTS AT ALL. A fresh signup used to walk straight into the ordinary app with nothing
 * marking the moment — no confirmation his shop was real, no word that the free trial billing
 * quietly opened behind the scenes (see `services/operations/app/core/signup.py`'s own
 * `_start_base_trial`) had actually started. Tamam, on seeing a brand-new account: «وهو عنده
 * فترة تجربة ايضا شهر كامل … ابغ كمان ترحيب فيه بعد التسجيل … خليها فخمة كذا وراقية الترحيب».
 *
 * THE SAME DARK/GOLD HERO `DoorLayout.tsx` COMMITS TO, not a fork of it — that file's own note
 * already states the rule this screen follows: a screen read once, before anyone owns anything,
 * earns one deliberate look regardless of theme, unlike the field screen a shop stares at all day.
 *
 * NO DAY COUNT IS EVER PRINTED HERE. How long a trial runs is billing's own decision (a plan's
 * `trial_days`, editable without a deploy) — the marketing page's own rule
 * (marketing/index.html's "NO TRIAL, NO PRICE, NO DURATION") is that no duration is ever promised
 * in text that outlives the setting behind it. The real end date travels from the signup response
 * instead (`trial_end`, unix seconds) and is shown as a date, never a promise about how many days
 * that date is away.
 */
import { Mark, Wordmark } from '../brand/Mark';
import { Button } from '../rj-ui/Button';
import { Sparkles } from 'lucide-react';

const HERO: React.CSSProperties = {
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
  return (
    <div className="grid min-h-dvh place-items-center p-6" style={HERO}>
      <div className="flex w-full max-w-md flex-col items-center gap-8 text-center">
        <div className="flex items-center gap-3 text-[#f4efe2]">
          <Mark size={40} />
          <Wordmark className="text-lg" />
        </div>

        <div
          className="grid size-16 place-items-center rounded-full"
          style={{ background: 'rgba(184,134,43,0.18)', boxShadow: '0 0 0 1px rgba(184,134,43,0.35)' }}
        >
          <Sparkles size={28} className="text-[#e3b957]" aria-hidden />
        </div>

        <div>
          <h1 className="text-3xl leading-tight tracking-tight text-[#f4efe2]">
            أهلاً بك في راجِع
          </h1>
          <p className="mt-3 text-[15px] leading-relaxed text-[#c9c2b3]">
            محلّك جاهز، وتجربتك المجانية بدأت الآن — كل شيء مفتوح أمامك بلا أي إعداد.
          </p>
          {trialEnd > 0 ? (
            <p className="mt-4 rounded-card px-4 py-2.5 text-sm text-[#e3b957]"
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

        <p className="text-xs text-[#8d8778]">راجِع · الرياض</p>
      </div>
    </div>
  );
}
