/**
 * The launcher's hero banner — an auto-sliding carousel, the one deliberately "movie-site" gesture
 * in the whole redesign (the owner's own reference point). Real app copy only: each slide's
 * sentence is the SAME `what` text `apps.ts::APP_ROWS` already carries (Locked.tsx/Plans.tsx read
 * the identical string) — never marketing copy invented for this one screen, which would be the
 * exact "no placeholder drift" failure this product keeps refusing elsewhere.
 *
 * A NEW COMPONENT, NOT A REUSE OF <Card> — a full-bleed gradient slide with its own arrows/dots has
 * nothing in common with a bordered white panel; forcing it through the card primitive would only
 * mean immediately overriding half of what that primitive sets.
 */
import { useEffect, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';
import { useOperatorI18n, tf } from '../operator-i18n';
import './launcher-i18n';

export interface HeroSlide {
  id: string;
  eyebrow: string;
  title: string;
  desc: string;
  gradient: string;
  cta: string;
  onOpen: () => void;
}

const AUTOPLAY_MS = 4500;

// ONE VARIANT SET, KEYED BY A PLAIN +1/-1 SIGN — never by the flex box's own physical order.
// This is the exact class of bug the previous CSS-transform version had: `translateX(index*100%)`
// assumed DOM order ran left-to-right, and the page's own `dir="rtl"` silently reverses how
// `flex-direction: row` lays its children out, so the active slide could end up shifted entirely
// outside the clipped viewport (blank hero, only visible once autoplay advanced past slide 0).
// `AnimatePresence` renders exactly ONE slide at a time and animates it purely by `x` motion values
// it owns itself — nothing here depends on flex order, so the direction the page's language reads
// in can never again point the shift the wrong way.
const slideVariants = {
  enter: (dir: number) => ({ x: `${dir * 100}%`, opacity: 0 }),
  center: { x: 0, opacity: 1 },
  exit: (dir: number) => ({ x: `${-dir * 100}%`, opacity: 0 }),
};

export function HeroBanner({ slides }: { slides: HeroSlide[] }) {
  const { t } = useOperatorI18n();
  const [[index, direction], setIndexed] = useState<[number, number]>([0, 1]);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const go = (next: number, dir: number) => setIndexed([(next + slides.length) % slides.length, dir]);

  useEffect(() => {
    if (slides.length <= 1) return;
    timer.current = setInterval(() => setIndexed(([i]) => [(i + 1) % slides.length, 1]), AUTOPLAY_MS);
    return () => { if (timer.current) clearInterval(timer.current); };
  }, [slides.length]);

  function pause() { if (timer.current) clearInterval(timer.current); }
  function resume() {
    pause();
    if (slides.length > 1) {
      timer.current = setInterval(() => setIndexed(([i]) => [(i + 1) % slides.length, 1]), AUTOPLAY_MS);
    }
  }

  if (slides.length === 0) return null;
  const s = slides[index];

  return (
    <div
      // `maxHeight` HERE, ON PURPOSE — an aspect-ratio box with no ceiling grows with the
      // viewport's own WIDTH forever, and on a genuinely wide/4K monitor (found live: 5120px
      // wide) 16:6 computes a banner ~1900px tall — most of the screen, reading as "the page
      // stopped responding" since everything else sat scrolled far below the fold. `minHeight`
      // already existed for the opposite (too-narrow) case; a real product needs both ends
      // bounded, not just one.
      // `width: '100%'` HERE, ON PURPOSE — without a pinned width, this box's width was `auto`
      // (fill-available), and CSS treats that as the "auto" side of `aspect-ratio` too: the moment
      // `maxHeight` actually clamps the box (any container wider than 380*16/6≈1013px — true on
      // almost any real monitor), the browser re-derives WIDTH from the clamped height to keep the
      // ratio, instead of keeping width at the container's full size. That silently shrank the
      // banner to ~1013px with blank space beside it — the exact "banner doesn't take the full
      // width" bug, and almost certainly also the earlier "everything collapsed to a small
      // floating square" reports (same shrink, just at a container width where it read as
      // catastrophic rather than merely narrow). Pinning width makes height the only ratio-derived
      // side, so `maxHeight`/`minHeight` clamp height alone and width always fills the row.
      className="group relative overflow-hidden rounded-[26px] shadow-lg"
      style={{ width: '100%', aspectRatio: '16 / 6', minHeight: 180, maxHeight: 380 }}
      onMouseEnter={pause}
      onMouseLeave={resume}
    >
      <AnimatePresence initial={false} custom={direction} mode="popLayout">
        <motion.div
          key={s.id}
          custom={direction}
          variants={slideVariants}
          initial="enter"
          animate="center"
          exit="exit"
          transition={{ x: { type: 'spring', stiffness: 300, damping: 32 }, opacity: { duration: 0.2 } }}
          className="absolute inset-0 flex h-full items-end p-7 text-white"
        >
          <div className="absolute inset-0" style={{ background: s.gradient }} />
          <div className="absolute inset-0 bg-gradient-to-t from-black/55 to-transparent" />
          <div className="relative z-[1] flex max-w-lg flex-col gap-2">
            <span className="text-[.72rem] font-bold uppercase tracking-wider opacity-85">{s.eyebrow}</span>
            <h2 className="text-2xl font-extrabold">{s.title}</h2>
            <p className="text-sm leading-relaxed opacity-90">{s.desc}</p>
            <button
              type="button"
              onClick={s.onOpen}
              className="mt-1.5 w-fit rounded-full bg-white px-5 py-2 text-sm font-extrabold text-[#1c1240] shadow-md transition hover:scale-[1.03]"
            >
              {s.cta}
            </button>
          </div>
        </motion.div>
      </AnimatePresence>

      {slides.length > 1 ? (
        <>
          <button
            type="button"
            aria-label={t('launcher.hero.prev')}
            onClick={() => { go(index - 1, -1); resume(); }}
            className="absolute top-1/2 start-3.5 z-[2] grid h-9 w-9 -translate-y-1/2 place-items-center rounded-full border border-white/30 bg-white/15 text-white opacity-0 backdrop-blur transition group-hover:opacity-100"
          >
            <ChevronLeft size={18} className="rtl:hidden" />
            <ChevronRight size={18} className="hidden rtl:block" />
          </button>
          <button
            type="button"
            aria-label={t('launcher.hero.next')}
            onClick={() => { go(index + 1, 1); resume(); }}
            className="absolute top-1/2 end-3.5 z-[2] grid h-9 w-9 -translate-y-1/2 place-items-center rounded-full border border-white/30 bg-white/15 text-white opacity-0 backdrop-blur transition group-hover:opacity-100"
          >
            <ChevronRight size={18} className="rtl:hidden" />
            <ChevronLeft size={18} className="hidden rtl:block" />
          </button>
          <div className="absolute bottom-3.5 end-5 z-[2] flex gap-1.5">
            {slides.map((s, i) => (
              <button
                key={s.id}
                type="button"
                aria-label={tf(t, 'launcher.hero.slide', { n: i + 1 })}
                onClick={() => { go(i, i > index ? 1 : -1); resume(); }}
                className={`h-[7px] rounded-full bg-white transition-all ${i === index ? 'w-5 opacity-100' : 'w-[7px] opacity-45'}`}
              />
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}
