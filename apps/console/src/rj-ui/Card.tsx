/**
 * Our own Card — component #30, and the app-store/premium redesign's own primitive (2026-09-16):
 * every screen's hand-rolled `<div className="rounded-card border border-border-subtle bg-surface-1
 * ...">` copy is migrated to THIS, so a future change to how a card looks or feels reaches every
 * screen from one edit — the exact promise a hand-rolled copy breaks the moment it is written.
 *
 * THE GLOSS IS ON BY DEFAULT, NOT AN OPT-IN — the owner's own instruction: nothing may read as
 * dull. `card-sheen` (tailwind-preset.cjs, shared across every app that extends the preset) is an
 * accent-tinted diagonal light sweep layered ON TOP of whatever surface colour is already there,
 * never a token override — set `sheen={false}` for the rare surface that must stay still (a dense
 * table row, say).
 *
 * NO `@base-ui` IMPORT, DELIBERATELY — this app's own components read Raje3's own kit only, not
 * the platform-originated one; merges its own classes via our own `../cn` (tailwind-merge + clsx,
 * both already real dependencies of this app), not the shared kit's copy.
 */
import type { HTMLAttributes } from 'react';
import { cn } from '../cn';

export interface RjCardProps extends HTMLAttributes<HTMLDivElement> {
  /** Lifts on hover with the accent-tinted glow — for a card that is itself a tap target. */
  interactive?: boolean;
  /** The default sheen sweep. Off only for a surface that must stay visually still. */
  sheen?: boolean;
}

export function Card({ className, interactive, sheen = true, ...props }: RjCardProps) {
  return (
    <div
      className={cn(
        'rounded-card border border-border-subtle bg-surface-1 p-5 shadow-sm',
        sheen && 'card-sheen',
        interactive &&
          'cursor-pointer transition-all duration-base ease-smooth hover:-translate-y-0.5 ' +
            'hover:border-accent/50 hover:shadow-glow focus-ring',
        className,
      )}
      {...props}
    />
  );
}

export function CardTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h2 className={cn('text-lg font-semibold tracking-tight text-text-primary', className)} {...props} />
  );
}

export function CardSubtitle({ className, ...props }: HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn('mt-1 text-sm text-text-muted', className)} {...props} />;
}
