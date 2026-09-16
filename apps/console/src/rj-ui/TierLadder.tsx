/**
 * TierLadder — a shop's own place on a rising set of automatic percent tiers, drawn as connected
 * rungs rather than a bare number. Built for «كوبونات»'s own stats tab: the backend's
 * `CouponService.stats()` already resolves which tier a shop's LAST month of activity earns
 * (core/coupons.py), and a plain "your cap is 20%" sentence hides the thing that actually
 * motivates a shop — where it sits among the steps, and how far the next one is.
 *
 * DONE RUNGS, THE CURRENT ONE, AND WHAT IS STILL AHEAD are three different visual states
 * (filled/ringed/empty), never one colour repeated — the same "a shelf must read as distinct
 * states, not a shade of the same thing" rule `KpiCard`'s own tone system already holds.
 */
import { cn } from '../cn';

export interface TierLadderRung {
  /** The percent this rung represents — rendered as-is (`%` appended by the caller's own
   *  `formatPercent`, so this stays a plain locale-agnostic label if a screen ever needs one). */
  label: string;
  /** `true` once the shop's current cap has reached or passed this rung. */
  done: boolean;
  /** At most ONE rung should carry this — the shop's own cap today. */
  current?: boolean;
}

export function TierLadder({ rungs, testId }: { rungs: TierLadderRung[]; testId?: string }) {
  if (rungs.length === 0) return null;
  return (
    <div className="flex items-center" data-testid={testId} role="list" aria-label="سلّم الشرائح">
      {rungs.map((r, i) => (
        <div key={i} role="listitem" className="relative flex flex-1 flex-col items-center gap-1.5">
          {i > 0 ? (
            <span
              aria-hidden
              className={cn(
                'absolute right-1/2 top-[7px] h-0.5 w-full',
                r.done || r.current ? 'bg-accent' : 'bg-border-subtle',
              )}
            />
          ) : null}
          <span
            aria-hidden
            className={cn(
              'z-10 h-3.5 w-3.5 rounded-full border-2',
              r.current
                ? 'border-accent bg-surface-1 shadow-[0_0_0_4px_var(--color-accent-soft)]'
                : r.done
                  ? 'border-accent bg-accent'
                  : 'border-border-subtle bg-surface-2',
            )}
          />
          <span className={cn(
            'text-xs font-bold tabular-nums',
            r.current ? 'text-accent-on-soft' : 'text-text-secondary',
          )}>
            {r.label}
          </span>
        </div>
      ))}
    </div>
  );
}
