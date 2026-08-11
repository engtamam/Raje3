/**
 * Waiting, in our own hand — for the screens whose shape we cannot honestly guess.
 *
 * WHY NOT A SKELETON EVERYWHERE. A skeleton is a promise about the layout that is coming: these
 * grey bars will become those rows. Where that promise is true it is the best waiting state there
 * is, and it stays — a list, a table, a card whose shape we already know. But a whole page rendered
 * as one grey rectangle promises nothing; it reads as a panel that failed to draw. The owner
 * photographed one and asked what was broken. Nothing was broken; the screen simply had no way to
 * say "I am working".
 *
 * SO THIS SAYS IT, WITH THE MARK. The journey in our logo — leave, turn, come back — is already a
 * loop, so it does not need a spinner drawn around it: it turns, slowly, and stops when the data
 * arrives. It takes `--accent` like everything else, which means on a shop's own screen it is the
 * shop's colour and not ours.
 *
 * IT DOES NOT APPEAR IMMEDIATELY. A fast connection answers in eighty milliseconds, and a spinner
 * that flashes for eighty milliseconds is worse than no spinner: the flicker reads as instability
 * in the product. Below the delay the screen simply stays as it was — which is what "instant" looks
 * like. Above it, the wait is real and deserves an answer.
 *
 * AND IT HOLDS STILL FOR ANYONE WHO ASKED IT TO. `prefers-reduced-motion` is set by people for
 * whom movement is not decoration but a symptom; the mark then fades rather than turns, and the
 * sentence carries the meaning on its own.
 */
import { useEffect, useState } from 'react';
import { Mark } from './brand/Mark';

/** Below this, a wait is not a wait — it is a repaint, and announcing it makes it look worse. */
const APPEAR_AFTER_MS = 300;

export function Waiting({ what = '', delayMs = APPEAR_AFTER_MS }: { what?: string; delayMs?: number }) {
  const [show, setShow] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setShow(true), delayMs);
    return () => clearTimeout(t);
  }, [delayMs]);

  if (!show) return null;

  return (
    <div
      className="flex min-h-48 flex-col items-center justify-center gap-3 py-10"
      // ANNOUNCED, NOT ONLY DRAWN. A screen reader user gets nothing from a turning logo, and
      // `polite` means it is read when there is a gap rather than cutting across something else.
      role="status"
      aria-live="polite"
    >
      <span className="raje-waiting">
        <Mark size={40} />
      </span>
      {/* WHAT WE ARE FETCHING, when the caller knows. «جاري التحميل» is what every product says
          and tells him nothing; «نجمع عملاءك» tells him which screen he is waiting on. */}
      <span className="text-sm text-text-secondary">{what || 'لحظة…'}</span>
    </div>
  );
}
