import type { HTMLAttributes } from 'react';
import { cn } from '../lib/cn';

/**
 * Card — the signature panel, redesigned 2026-09-16 for the app-store/premium redesign: the
 * gloss (`card-sheen`, tailwind-preset.cjs) is ON by default now, not something a page opts into —
 * the owner's own instruction was "nothing may read as dull", so a card that quietly renders flat
 * is the regression this default exists to prevent. `sheen={false}` opts back out for the rare
 * surface that genuinely needs to stay still (a dense data table row, say). Radius from
 * --radius-card, soft elevation, and an optional `interactive` hover that lifts on the
 * accent-tinted glow (shadow-glow) with an accent-tinted border — paired with
 * <CardTitle>/<CardSubtitle>.
 */
export function Card({
  className,
  interactive,
  sheen = true,
  ...props
}: HTMLAttributes<HTMLDivElement> & { interactive?: boolean; sheen?: boolean }) {
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
