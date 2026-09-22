/**
 * Our own Confetti — a handful of coloured rectangles that fall and spin once, then vanish. No
 * canvas, no animation library beyond `framer-motion` (already a real dependency this app uses
 * for `AppDetailsModal`'s own showcase), same hand-rolled discipline every other `rj-ui`
 * component already follows (`BarCompare`'s own "no chart library" note).
 *
 * FIRES ONCE, CLEANS ITSELF UP — mounted only while its caller wants it shown (no internal
 * re-trigger), and calls `onDone` once every particle has finished so the caller can unmount it
 * rather than leaving a dead, invisible layer in the tree.
 */
import { useMemo } from 'react';
import { motion } from 'framer-motion';

const COLOURS = ['#F08C00', '#2F9E44', '#1971C2', '#E64980', '#7048E8', '#099268'];
const COUNT = 42;

interface Particle {
  id: number;
  x: number;        // vw offset from centre
  delay: number;
  duration: number;
  rotate: number;
  colour: string;
  size: number;
}

export function Confetti({ onDone }: { onDone?: () => void }) {
  const particles = useMemo<Particle[]>(() => Array.from({ length: COUNT }, (_, i) => ({
    id: i,
    x: (Math.random() - 0.5) * 90,
    delay: Math.random() * 0.3,
    duration: 1.6 + Math.random() * 0.9,
    rotate: (Math.random() - 0.5) * 720,
    colour: COLOURS[i % COLOURS.length],
    size: 6 + Math.random() * 6,
  })), []);

  return (
    <div className="pointer-events-none fixed inset-0 z-[60] overflow-hidden" aria-hidden="true">
      {particles.map((p, i) => (
        <motion.span
          key={p.id}
          initial={{ y: '-10vh', x: `${p.x}vw`, opacity: 1, rotate: 0 }}
          animate={{ y: '110vh', rotate: p.rotate, opacity: [1, 1, 0] }}
          transition={{ duration: p.duration, delay: p.delay, ease: 'easeIn' }}
          onAnimationComplete={i === particles.length - 1 ? onDone : undefined}
          className="absolute top-0 start-1/2 rounded-sm"
          style={{ width: p.size, height: p.size * 0.4, backgroundColor: p.colour }}
        />
      ))}
    </div>
  );
}
