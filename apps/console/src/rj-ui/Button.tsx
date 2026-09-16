/**
 * Our own Button — component #2 in the platform-by-platform replacement (FilterMenu was #1).
 *
 * SAME API SURFACE AS `@base-ui/design-system/Button` on purpose: `variant`/`size` plus every
 * native button prop, so swapping the import is the only change a call site needs. What differs is
 * the press itself — the kit's button only changes colour on press; a workshop tablet is tapped
 * fast and the finger is already moving to the next thing before the eye confirms the tap landed,
 * so touch needs to feel it register. `active:scale` gives that in one frame, at a duration short
 * enough (100ms) that it never reads as a delay on a screen built around a five-second visit.
 */
import { forwardRef } from 'react';
import type { ButtonHTMLAttributes } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '../cn';

export const rjButtonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl font-semibold ' +
    'outline-none focus-ring transition-transform duration-100 active:scale-[0.97] ' +
    'disabled:pointer-events-none disabled:opacity-40 disabled:active:scale-100',
  {
    variants: {
      variant: {
        solid: 'bg-accent text-accent-contrast shadow-sm hover:bg-accent-hover',
        soft: 'bg-accent-soft text-accent-on-soft hover:opacity-90',
        outline: 'border border-border-strong bg-transparent text-text-primary hover:bg-surface-2',
        // GHOST HAD NO RESTING SHAPE — `bg-transparent` plus coloured text alone, indistinguishable
        // from a plain label until the pointer already found it by accident. Reported directly
        // (screenshot: «اجعلها نبرتي» read as inert text, not a control). A permanent light fill
        // gives it the same "this is a chip you can press" cue `outline` gets from its border,
        // without competing visually with `outline`'s own bordered look.
        ghost: 'bg-surface-2 text-text-secondary hover:bg-surface-3 hover:text-text-primary',
        danger: 'bg-danger text-danger-contrast hover:opacity-90',
      },
      size: {
        sm: 'h-8 px-3 text-sm',
        md: 'h-10 px-4 text-sm',
        // 44px — the touch-target floor a glove or a wet thumb still hits, same reasoning
        // platform/ui's AppShell nav rows already settled on.
        lg: 'h-11 px-6 text-base',
        icon: 'h-11 w-11 p-0',
      },
    },
    defaultVariants: { variant: 'solid', size: 'md' },
  },
);

export interface RjButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof rjButtonVariants> {}

export const Button = forwardRef<HTMLButtonElement, RjButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button ref={ref} className={cn(rjButtonVariants({ variant, size }), className)} {...props} />
  ),
);
Button.displayName = 'RjButton';
