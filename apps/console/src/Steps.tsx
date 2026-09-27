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
 * NOTHING IS GATED, AND THAT IS DELIBERATE. A step never blocks the next one: the operator can
 * take the services first and ask for the number afterwards, which is exactly how it goes when
 * the car is already on the lift and the owner has wandered off. A journey that insists on its
 * own order is a journey that argues with a workshop, and the workshop wins.
 *
 * ARROWS AS WELL AS SWIPES. Touch can be off, gloved, or on a screen with a broken digitiser, and
 * a journey reachable only by swiping is a journey some shops simply cannot use. The dots are
 * buttons too, so any step is one tap from any other.
 *
 * A SKIPPED STEP IS NOT A HIDDEN STEP. Steps carry `when`, and a step whose condition is false is
 * absent from the sequence entirely — no empty page, no dot in the progress row that never lights.
 * What the operator would have seen there is the caller's job to say on the following step; see
 * «تسجيل زيارة», which reports «لا عروض ولا نقاط» rather than silently skipping.
 */
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useOperatorI18n } from './operator-i18n';
import './steps-i18n';

export interface Step {
  id: string;
  /** Shown above the pane. One line, and it is what this step ASKS — not a section name. */
  title: string;
  /** False = this step does not exist for this visit. Not "rendered empty". */
  when?: boolean;
  /** A hint under the arrows — never a block. See the note on free movement below. */
  hint?: string;
  body: ReactNode;
}

/** How far a drag must travel to count as a swipe rather than a tap that wandered. */
const THRESHOLD = 60;

/**
 * The height left between the top of this element and the bottom of the window — MEASURED.
 *
 * The first version subtracted a guessed 3.5rem for the shell's header. It was wrong on the very
 * first phone it met: the real chrome differs by shell, by whether a banner is showing, and by
 * every browser's own toolbars — so the journey ran taller than the screen and the arrows sat
 * below the fold, reachable only by scrolling. The one thing this component exists to avoid.
 *
 * Asking the DOM removes the guess entirely, and it re-asks on resize and on rotation, which is a
 * tablet being picked up off a bench.
 */
function useFittedHeight() {
  const ref = useRef<HTMLDivElement | null>(null);
  const [h, setH] = useState<number | null>(null);

  useEffect(() => {
    const fit = () => {
      const el = ref.current;
      if (!el) return;
      setH(Math.max(320, Math.floor(window.innerHeight - el.getBoundingClientRect().top)));
    };
    fit();
    // MEASURED AGAIN AFTER THE LAYOUT SETTLES, not once on mount. Fonts load, an offer line
    // appears, a hint wraps to two lines — each moves our top edge, and a height computed before
    // any of that is a height that was true for one frame. Observing the document catches all of
    // them without knowing which one happened.
    const ro = new ResizeObserver(fit);
    ro.observe(document.documentElement);
    window.addEventListener('resize', fit);
    // The visual viewport is the one that shrinks when a keyboard opens — the moment this screen
    // most needs to refit, and the one `resize` does not always report on mobile.
    window.visualViewport?.addEventListener('resize', fit);
    return () => {
      ro.disconnect();
      window.removeEventListener('resize', fit);
      window.visualViewport?.removeEventListener('resize', fit);
    };
  }, []);

  return { ref, h };
}

export function Steps({ steps, done }: { steps: Step[]; done: ReactNode }) {
  const { t } = useOperatorI18n();
  const live = steps.filter((s) => s.when !== false);
  const [at, setAt] = useState(0);
  const start = useRef<number | null>(null);
  const { ref, h } = useFittedHeight();

  // A STEP CAN DISAPPEAR UNDER HIM. Type a plate, the offers step appears; clear it and it is gone
  // — and if he was standing on it, the index now points past the end and the screen goes blank.
  useEffect(() => {
    if (at > live.length - 1) setAt(Math.max(0, live.length - 1));
  }, [at, live.length]);

  const step = live[Math.min(at, live.length - 1)];
  if (!step) return null;

  const last = at >= live.length - 1;
  const go = (delta: number) =>
    setAt((i) => Math.min(live.length - 1, Math.max(0, i + delta)));

  return (
    <div
      ref={ref}
      style={{ height: h ?? undefined }}
      className="flex flex-col overflow-hidden"
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
          enough that "am I nearly done?" is a real question with a customer standing there.
          PAST DOTS STAY TINTED, not just "not current" — a dot he already answered and a dot he
          has not reached yet used to look identical, so the row said only "here", never "this
          far in". A filled small dot behind him costs nothing extra to read and answers the
          actual question faster. Still pure CSS — no timer, no extra frame, nothing this screen's
          five-second budget would ever notice. */}
      <div className="flex items-center justify-center gap-1.5 py-2">
        {live.map((s, i) => (
          <button
            key={s.id}
            type="button"
            aria-label={s.title}
            onClick={() => setAt(i)}
            className="grid h-11 w-6 place-items-center"
          >
            <span
              className={`h-1.5 rounded-full transition-all duration-150 ${
                i === at ? 'w-6 bg-accent' : i < at ? 'w-1.5 bg-accent-soft' : 'w-1.5 bg-border-subtle'
              }`}
            />
          </button>
        ))}
      </div>

      <h2 className="px-4 pb-2 text-center text-base font-semibold">{step.title}</h2>

      {/* THE PANE OWNS THE REST OF THE SCREEN. `min-h-0` is what actually lets it shrink inside a
          flex column — without it the pane grows to its content and the footer is pushed off. */}
      {/* CONSTRAINED AND CENTRED ON A WIDE SCREEN. This journey is designed for a phone held in
          one hand, and a phone layout stretched across a desktop is not generous — it is a form
          whose fields run a foot wide with a field of empty page under them. The width is capped
          at the size the design was drawn for; the extra room becomes margin, which is what a
          reader's eye expects. */}
      <div data-pane className="min-h-0 flex-1 overflow-y-auto px-4 pb-2">
        <div className="mx-auto w-full max-w-3xl">{step.body}</div>
      </div>

      {step.hint ? (
        <p className="px-4 pb-1 text-center text-xs text-text-secondary">{step.hint}</p>
      ) : null}

      {/* ARROWS POINT THE WAY THE PAGE READS. In Arabic «السابق» is on the right and «التالي» on
          the left, so the flex order alone puts each where it belongs.
          
          THE GLYPHS ARE TRIANGLES, NOT CHEVRONS. `‹` and `›` are quotation marks, and the bidi
          algorithm MIRRORS them in a right-to-left run — so the arrow rendered pointing the
          opposite way to the one written in the source, and «السابق» wore the forward arrow. Seen
          in a screenshot, not in a review. `◂` and `▸` are geometric shapes and are not mirrored,
          so what is written is what is drawn. */}
      <div className="mx-auto flex w-full max-w-3xl items-center gap-2 border-t border-border-subtle bg-surface-0 p-3">
        {/* active:scale, NOT a hover state — this is a touch screen, and the only feedback that
            matters is the one his thumb feels the instant it lands. 100ms so it reads as the tap
            itself, never as a delay before the step actually turns. */}
        <button
          type="button"
          onClick={() => go(-1)}
          disabled={at === 0}
          aria-label={t('steps.previous')}
          className="grid size-11 shrink-0 place-items-center rounded-xl border border-border-subtle bg-surface-1 text-lg transition-transform duration-100 active:scale-90 disabled:opacity-30 disabled:active:scale-100"
        >
          ▸
        </button>

        <div className="min-w-0 flex-1">{last ? done : null}</div>

        <button
          type="button"
          onClick={() => go(1)}
          disabled={last}
          aria-label={t('steps.next')}
          className="grid size-11 shrink-0 place-items-center rounded-xl bg-accent text-lg text-white transition-transform duration-100 active:scale-90 disabled:opacity-30 disabled:active:scale-100"
        >
          ◂
        </button>
      </div>
    </div>
  );
}
