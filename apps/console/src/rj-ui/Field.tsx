/**
 * Our own Field/Input/Textarea/Select — component #11. Same API as
 * @base-ui/design-system/Field's exports, so a call site needs only the import changed. Bundled as one
 * file because the kit does the same: a labelled row wrapper plus the three styled native controls it
 * wraps, sharing one skin (`CONTROL`) so a form reads as one system rather than four.
 *
 * NATIVE ELEMENTS UNDER THE PAINT, DELIBERATELY — same choice the kit made. A custom listbox re-fights
 * keyboard nav, screen-reader semantics and the mobile OS picker that a real <select> gets for free;
 * only the chrome is ours (`appearance-none` + our own chevron at the logical `end`, so it still flips
 * side in RTL).
 */
import { forwardRef, useId } from 'react';
import type {
  InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes, ReactNode,
} from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from '../cn';

const CONTROL =
  'w-full rounded-md border border-border-strong bg-surface-1 px-3 py-2 text-sm text-text-primary ' +
  'placeholder:text-text-muted transition-colors outline-none focus-ring ' +
  'disabled:cursor-not-allowed disabled:opacity-50 ' +
  'aria-[invalid=true]:border-danger aria-[invalid=true]:focus-visible:outline-danger';

export type RjInputProps = InputHTMLAttributes<HTMLInputElement>;
export const Input = forwardRef<HTMLInputElement, RjInputProps>(
  ({ className, ...props }, ref) => <input ref={ref} className={cn(CONTROL, className)} {...props} />,
);
Input.displayName = 'RjInput';

export type RjTextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement>;
export const Textarea = forwardRef<HTMLTextAreaElement, RjTextareaProps>(
  ({ className, rows = 4, ...props }, ref) => (
    <textarea ref={ref} rows={rows} className={cn(CONTROL, 'resize-y leading-relaxed', className)} {...props} />
  ),
);
Textarea.displayName = 'RjTextarea';

export type RjSelectProps = SelectHTMLAttributes<HTMLSelectElement>;
export const Select = forwardRef<HTMLSelectElement, RjSelectProps>(
  ({ className, children, ...props }, ref) => (
    <div className="relative">
      <select ref={ref} className={cn(CONTROL, 'appearance-none pe-9', className)} {...props}>
        {children}
      </select>
      <ChevronDown
        size={16}
        aria-hidden
        className="pointer-events-none absolute inset-y-0 end-3 my-auto text-text-muted"
      />
    </div>
  ),
);
Select.displayName = 'RjSelect';

export interface RjFieldProps {
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  required?: boolean;
  htmlFor?: string;
  className?: string;
  children: ReactNode;
}

export function Field({ label, hint, error, required, htmlFor, className, children }: RjFieldProps) {
  const auto = useId();
  const id = htmlFor ?? auto;
  const hintId = hint ? `${id}-hint` : undefined;
  const errId = error ? `${id}-err` : undefined;

  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      {label != null ? (
        <label htmlFor={id} className="text-label font-medium text-text-secondary">
          {label}
          {required ? <span className="ms-1 text-danger" aria-hidden>*</span> : null}
        </label>
      ) : null}
      {children}
      {error != null ? (
        <p id={errId} className="text-caption text-danger-on-soft" role="alert">{error}</p>
      ) : hint != null ? (
        <p id={hintId} className="text-caption text-text-muted">{hint}</p>
      ) : null}
    </div>
  );
}
