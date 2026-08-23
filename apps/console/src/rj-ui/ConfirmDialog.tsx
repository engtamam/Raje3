/**
 * Our own ConfirmDialog — component #12, and the admin panel's own reason for existing now:
 * §٣ of the admin plan requires a destructive action to be confirmed BY THE TARGET'S OWN NAME
 * ("سيُغلق حساب بنشري الملك ويتوقف إرسال رسائله", never a bare "هل أنت متأكد؟").
 *
 * SAME API SURFACE AS `@base-ui/design-system/ConfirmDialog` on purpose — same "swap the import"
 * rule every other rj-ui component follows (see Button.tsx/Field.tsx's own header notes) — built
 * on OUR OWN Modal/Button/Field instead of the kit's.
 */
import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { Modal } from './Modal';
import { Button } from './Button';
import { Input } from './Field';

export interface ConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: ReactNode;
  /** Supporting line under the title. */
  body?: ReactNode;
  /** Extra content between the body and the actions (a warning list, a preview). */
  children?: ReactNode;
  confirmLabel?: ReactNode;
  cancelLabel?: ReactNode;
  /** Tints the primary button as destructive (danger) rather than solid accent. Defaults to true. */
  danger?: boolean;
  /** Disables the actions while the confirmed operation is in flight. */
  busy?: boolean;
  /** ARM MODE — when set, the operator must type this exact string to enable Confirm. */
  confirmText?: string;
  /** Label above the arm input (e.g. "اكتب اسم المحل للتأكيد"). */
  armLabel?: ReactNode;
}

export function ConfirmDialog({
  open, onClose, onConfirm, title, body, children,
  confirmLabel = 'تأكيد', cancelLabel = 'إلغاء', danger = true, busy = false,
  confirmText, armLabel,
}: ConfirmDialogProps) {
  const [typed, setTyped] = useState('');

  // A previous target's typed answer must never leak into the next confirm.
  useEffect(() => { if (!open) setTyped(''); }, [open]);
  useEffect(() => { setTyped(''); }, [confirmText]);

  const armed = confirmText != null && confirmText !== '';
  const typedOk = !armed || typed.trim() === confirmText.trim();
  const ready = typedOk && !busy;

  return (
    <Modal open={open} onClose={onClose} title={title} subtitle={body}>
      <div className="flex flex-col gap-4">
        {children}

        {armed ? (
          <label className="flex flex-col gap-1.5">
            <span className="text-label font-medium text-text-secondary">
              {armLabel ?? (
                <>اكتب <span className="font-semibold text-text-primary">{confirmText}</span> للتأكيد</>
              )}
            </span>
            <Input
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              autoComplete="off"
              autoCapitalize="off"
              spellCheck={false}
            />
          </label>
        ) : null}

        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose} disabled={busy}>{cancelLabel}</Button>
          <Button variant={danger ? 'danger' : 'solid'} onClick={onConfirm} disabled={!ready}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
