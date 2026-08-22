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
      className="flex flex-col gap-3 rounded-card border border-border-subtle bg-surface-1 p-5 shadow-sm"
      data-testid={testId}
    >
      <span className={cn('inline-flex w-fit rounded-lg p-2', TONE_ICON_BG[tone])}>{icon}</span>
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
