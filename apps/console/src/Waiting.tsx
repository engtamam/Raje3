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
 * SO THIS SAYS IT, WITH A SPINNER — a plain turning ring, not the drawn logo the product used to
 * have (retired 2026-09-16: the mark is now the wordmark itself, and a word does not read as
 * "loading" when it spins). It takes `--accent` like everything else, which means on a shop's own
 * screen it is the shop's colour and not ours.
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
import { useOperatorI18n } from './operator-i18n';
import './waiting-i18n';

/** Below this, a wait is not a wait — it is a repaint, and announcing it makes it look worse. */
const APPEAR_AFTER_MS = 300;

export function Waiting({ what = '', delayMs = APPEAR_AFTER_MS }: { what?: string; delayMs?: number }) {
  const { t } = useOperatorI18n();
  const [show, setShow] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setShow(true), delayMs);
    return () => clearTimeout(timer);
  }, [delayMs]);

  if (!show) return null;

  return (
    <div
      className="flex min-h-48 flex-col items-center justify-center gap-3 py-10"
      // ANNOUNCED, NOT ONLY DRAWN. A screen reader user gets nothing from a turning ring, and
      // `polite` means it is read when there is a gap rather than cutting across something else.
      role="status"
      aria-live="polite"
    >
      <span className="raje-waiting" aria-hidden="true">
        <svg width={40} height={40} viewBox="0 0 40 40" fill="none" style={{ color: 'var(--accent)' }}>
          <circle cx="20" cy="20" r="16" stroke="currentColor" strokeOpacity="0.2" strokeWidth="4" />
          <path
            d="M20 4a16 16 0 0 1 16 16"
            stroke="currentColor"
            strokeWidth="4"
            strokeLinecap="round"
          />
        </svg>
      </span>
      {/* WHAT WE ARE FETCHING, when the caller knows. «جاري التحميل» is what every product says
          and tells him nothing; «نجمع عملاءك» tells him which screen he is waiting on. */}
      <span className="text-sm text-text-secondary">{what || t('waiting.default')}</span>
    </div>
  );
}
