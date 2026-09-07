/**
 * Our own KpiCard — component #10. Same API as @base-ui/design-system/KpiCard for the slots Points.tsx
 * actually uses (icon/label/value/hint/tone/testId) — a call site needs only the import changed. The
 * kit's own `spark`/`delta`/`onClick` trend machinery is left out: nothing under `apps/console/src`
 * passes them (checked before porting — the same discipline as every other rj-ui component), and a
 * slot nobody calls is a slot nobody has verified. Add it back here, ported the same way, the day a
 * screen actually needs a trend pill.
 */
import type { ReactNode } from 'react';
import { cn } from '@base-ui/lib/cn';

export type RjKpiTone = 'neutral' | 'accent' | 'success' | 'warning' | 'danger';

const TONE_TEXT: Record<RjKpiTone, string> = {
  neutral: 'text-text-primary',
  accent: 'text-accent-on-soft',
  success: 'text-success-on-soft',
  warning: 'text-warning-on-soft',
  danger: 'text-danger-on-soft',
};
const TONE_ICON_BG: Record<RjKpiTone, string> = {
  neutral: 'bg-surface-2 text-text-secondary',
  accent: 'bg-accent-soft text-accent-on-soft',
  success: 'bg-success-soft text-success-on-soft',
  warning: 'bg-warning-soft text-warning-on-soft',
  danger: 'bg-danger-soft text-danger-on-soft',
};
// THE WHOLE CARD TINTED BY TONE, NOT JUST THE ICON CHIP — added 2026-09-07, a design audit's own
// top recommendation: a flat `bg-surface-1` card with colour confined to a 32px icon read as
// "the same card everywhere" regardless of what it meant. `neutral` keeps the plain surface (nothing
// to signal); every other tone now carries its own soft background across the whole shape, same
// idea Shop.tsx's own `Tile` already proved.
const TONE_CARD_BG: Record<RjKpiTone, string> = {
  neutral: 'bg-surface-1 border border-border-subtle',
  accent: 'bg-accent-soft',
  success: 'bg-success-soft',
  warning: 'bg-warning-soft',
  danger: 'bg-danger-soft',
};

export interface RjKpiCardProps {
  icon: ReactNode;
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: RjKpiTone;
  testId?: string;
}

export function KpiCard({ icon, label, value, hint, tone = 'neutral', testId }: RjKpiCardProps) {
  return (
    <div
      className={cn('flex flex-col gap-3 rounded-card p-5 shadow-sm', TONE_CARD_BG[tone])}
      data-testid={testId}
    >
      {/* ON A TINTED CARD, the icon chip is a translucent white overlay rather than the SAME soft
          tone the card itself now carries — two identical fills stacked would erase the chip
          entirely. Neutral cards keep their own distinct chip background, unchanged. */}
      <span className={cn(
        'inline-flex w-fit rounded-lg p-2',
        tone === 'neutral' ? TONE_ICON_BG.neutral : cn('bg-white/55', TONE_TEXT[tone]),
      )}>{icon}</span>
      <div>
        <div className={cn('text-3xl font-semibold tabular-nums tracking-tight', TONE_TEXT[tone])}>
          {value}
        </div>
        <div className="mt-1 text-sm font-medium text-text-secondary">{label}</div>
        {hint != null ? <div className="mt-0.5 text-xs text-text-muted">{hint}</div> : null}
      </div>
    </div>
  );
}
