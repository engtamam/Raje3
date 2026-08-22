/**
 * Our own EmptyState — component #4. Same API as @base-ui/design-system/EmptyState (icon, title,
 * description, action), so a call site needs only the import changed.
 *
 * Centred, theme-token only, RTL-safe by construction (text-center + logical spacing carries the
 * same regardless of direction) — for a zero-result list, a "not started yet" section, or a read
 * that failed and has nothing else on screen to say so.
 */
import type { ReactNode } from 'react';

export interface RjEmptyStateProps {
  icon?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ icon, title, description, action, className }: RjEmptyStateProps) {
  return (
    <div className={['flex flex-col items-center justify-center gap-3 px-6 py-12 text-center', className ?? ''].filter(Boolean).join(' ')}>
      {icon ? (
        <div className="grid h-12 w-12 place-items-center rounded-full bg-surface-2 text-text-muted">
          {icon}
        </div>
      ) : null}
      <div className="flex flex-col gap-1">
        <p className="text-title font-semibold text-text-primary">{title}</p>
        {description != null ? (
          <p className="mx-auto max-w-sm text-body text-text-muted">{description}</p>
        ) : null}
      </div>
      {action ? <div className="mt-1 flex items-center gap-2">{action}</div> : null}
    </div>
  );
}
