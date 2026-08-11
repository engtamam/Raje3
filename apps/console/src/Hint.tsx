/**
 * A rule the screen states once, then keeps out of the way.
 *
 * WHY THIS EXISTS. Two sentences on the customer card explain things that are true for ever — the
 * phone is the identity and cannot be edited, and a minus deducts. An owner reads each of them
 * once. After that they are furniture: they take the width a control needs, push the real fields
 * down, and get skipped by the eye anyway — which means the ONE time somebody needed to read them,
 * they had already learned to look past them.
 *
 * SO THE TEXT IS STILL THERE, one tap away, and the card stays a card. It is not hidden and it is
 * not shouting: «؟» is the shape everyone already knows for "explain this".
 *
 * OPEN ON THE PAGE, NOT IN A TOOLTIP. A hover tooltip is a control that does not exist on a
 * workshop tablet, and a title attribute is unreadable to a thumb.
 */
import { useState, type ReactNode } from 'react';

export function Hint({ children, label = 'شرح' }: { children: ReactNode; label?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        aria-label={label}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        // 44px, because it is a control on a screen used with a thumb — the same floor every
        // other tappable thing in this app answers to.
        className="grid size-6 shrink-0 place-items-center rounded-full bg-surface-2 text-xs text-text-secondary"
      >
        ؟
      </button>
      {open ? (
        <p className="basis-full text-xs leading-relaxed text-text-secondary">{children}</p>
      ) : null}
    </>
  );
}
