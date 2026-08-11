/**
 * A journey made of full screens, moved by a thumb — not one long page scrolled with a wet hand.
 *
 * WHY THIS EXISTS. «تسجيل زيارة» had every field on one page, and on a phone that meant the
 * operator scrolled past sixteen service tiles to reach the customer. A workshop screen is used
 * standing up, one-handed, often with a customer waiting: each step should ask ONE thing, fill the
 * screen with it, and get out of the way.
 *
 * RIGHT IS FORWARD, because the page is Arabic. In RTL a swipe from right to left moves the
 * content the way reading moves, so «التالي» sits on the left and a leftward drag advances. Wiring
 * this to physical direction rather than to `dir` is the classic way a right-to-left app ends up
 * feeling backwards to everyone who uses it.
 *
 * A SKIPPED STEP IS NOT A HIDDEN STEP. Steps carry `when`, and a step whose condition is false is
 * absent from the sequence entirely — no empty page, no dot in the progress row that never lights.
 * What the operator would have seen there is the caller's job to say on the following step; see
 * «تسجيل زيارة», which reports «لا عروض ولا نقاط» rather than silently skipping.
 */
import { useEffect, useRef, useState, type ReactNode } from 'react';

export interface Step {
  id: string;
  /** Shown above the pane. One line, and it is what this step ASKS — not a section name. */
  title: string;
  /** False = this step does not exist for this visit. Not "rendered empty". */
  when?: boolean;
  /** False blocks «التالي» and says why, so a dead button never has to be guessed at. */
  ready?: boolean;
  readyHint?: string;
  body: ReactNode;
}

/** How far a drag must travel to count as a swipe rather than a tap that wandered. */
const THRESHOLD = 60;

export function Steps({ steps, done }: { steps: Step[]; done: ReactNode }) {
  const live = steps.filter((s) => s.when !== false);
  const [at, setAt] = useState(0);
  const start = useRef<number | null>(null);

  // A STEP CAN DISAPPEAR UNDER HIM. Type a plate, the offers step appears; clear it and it is gone
  // — and if he was standing on it, the index now points past the end and the screen goes blank.
  useEffect(() => {
    if (at > live.length - 1) setAt(Math.max(0, live.length - 1));
  }, [at, live.length]);

  const step = live[Math.min(at, live.length - 1)];
  if (!step) return null;

  const last = at >= live.length - 1;
  const blocked = step.ready === false;

  const go = (delta: number) => {
    if (delta > 0 && (blocked || last)) return;
    setAt((i) => Math.min(live.length - 1, Math.max(0, i + delta)));
  };

  return (
    <div
      className="flex h-[calc(100dvh-var(--shell-top,3.5rem))] flex-col overflow-hidden"
      onTouchStart={(e) => { start.current = e.touches[0]?.clientX ?? null; }}
      onTouchEnd={(e) => {
        const from = start.current;
        start.current = null;
        if (from === null) return;
        const moved = (e.changedTouches[0]?.clientX ?? from) - from;
        if (Math.abs(moved) < THRESHOLD) return;
        // Leftward drag (negative) = forward, in a page that reads right to left.
        go(moved < 0 ? 1 : -1);
      }}
    >
      {/* WHERE HE IS, IN DOTS. Three steps is short enough that a number would be noise, and long
          enough that "am I nearly done?" is a real question with a customer standing there. */}
      <div className="flex items-center justify-center gap-1.5 py-2">
        {live.map((s, i) => (
          <span
            key={s.id}
            className={`h-1.5 rounded-full transition-all ${
              i === at ? 'w-6 bg-accent' : 'w-1.5 bg-border-subtle'
            }`}
          />
        ))}
      </div>

      <h2 className="px-4 pb-2 text-center text-base font-semibold">{step.title}</h2>

      {/* THE PANE OWNS THE REST OF THE SCREEN. `min-h-0` is what actually lets it shrink inside a
          flex column — without it the pane grows to its content and the footer is pushed off. */}
      <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-2">{step.body}</div>

      <div className="flex items-center gap-2 border-t border-border-subtle bg-surface-0 p-3">
        {at > 0 ? (
          <button
            type="button"
            onClick={() => go(-1)}
            className="min-h-[44px] rounded-xl px-4 text-sm text-text-secondary"
          >
            رجوع
          </button>
        ) : null}

        {last ? (
          <div className="flex-1">{done}</div>
        ) : (
          <button
            type="button"
            onClick={() => go(1)}
            disabled={blocked}
            className="min-h-[44px] flex-1 rounded-xl bg-accent text-base font-semibold text-white disabled:opacity-40"
          >
            {blocked && step.readyHint ? step.readyHint : 'التالي'}
          </button>
        )}
      </div>
    </div>
  );
}
