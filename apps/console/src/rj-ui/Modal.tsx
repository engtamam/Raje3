/**
 * Our own Modal — component #5, and the one with a real scope note.
 *
 * @base-ui/design-system/Modal's actual job is coordinating MANY dialogs that can nest (a confirm
 * opened from inside a detail sheet) — a module-level stacking register so only the top one binds
 * Escape and only the top one is visible, with two previously-fixed bugs in its own history to prove
 * it was hard to get right. Reimplementing that registry here, disconnected from the one every other
 * screen still uses, would risk exactly the bug it was built to prevent the moment this modal ever had
 * to coexist with another one.
 *
 * IT DOES NOT NEED TO, YET. «من يحفظ؟» is the one dialog on تسجيل زيارة — a screen with no nav, no
 * settings sheet, nothing else that opens a modal beside it. So this covers the single-dialog case
 * only: portal to body, scrim, Escape-to-close, scroll lock. If a second modal is ever needed
 * anywhere near this one, reach for the shared Modal instead of teaching this one to stack.
 */
import { useEffect, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

const SIZE = {
  md: 'max-w-lg',
  lg: 'max-w-3xl',
} as const;

export function Modal({
  open, onClose, title, subtitle, size = 'md', children,
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  subtitle?: ReactNode;
  size?: keyof typeof SIZE;
  children: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => {
      document.body.style.overflow = prevOverflow;
      document.removeEventListener('keydown', onKey);
    };
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-md" onClick={onClose} aria-hidden />
      <div className={`animate-in relative z-10 flex max-h-[92vh] w-full ${SIZE[size]} flex-col overflow-hidden rounded-card border border-border-subtle bg-surface-1 shadow-pop`}>
        <div className="flex items-start justify-between gap-4 border-b border-border-subtle p-5">
          <div>
            <h2 className="text-lg font-semibold tracking-tight text-text-primary">{title}</h2>
            {subtitle ? <p className="mt-0.5 text-sm text-text-muted">{subtitle}</p> : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="shrink-0 rounded-md p-1.5 text-text-muted transition hover:bg-surface-2 hover:text-text-primary focus-ring"
            aria-label="إغلاق"
          >
            <X size={18} />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-5">{children}</div>
      </div>
    </div>,
    document.body,
  );
}
