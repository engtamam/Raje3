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
import { useOperatorI18n } from './operator-i18n';
import './hint-i18n';

export function Hint({ children, label, wide = false }:
    { children: ReactNode; label?: string; wide?: boolean }) {
  const { t } = useOperatorI18n();
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        aria-label={label ?? t('hint.label')}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        // 44px OF TOUCH, 24px OF INK. The comment above this line claimed the floor and the class
        // below it was `size-6` — 24 pixels, which the mobile suite caught on seven «؟» at once.
        //
        // A «؟» drawn at 44px is a button that shouts on a card whose whole point is to be quiet,
        // so the SHAPE stays small and the TARGET grows around it: a 44px box with no background,
        // holding a 24px circle. The finger gets its floor and the eye gets the footnote.
        className="grid size-11 shrink-0 place-items-center rounded-full"
      >
        <span aria-hidden className="grid size-6 place-items-center rounded-full bg-surface-2 text-xs text-text-secondary">
          {t('hint.questionMark')}
        </span>
      </button>
      {open ? (
        // FULL WIDTH IN WHATEVER LAYOUT IT LANDS IN. `basis-full` is a flex instruction and a
        // grid ignores it entirely — so inside a two-column row the sentence was squeezed into
        // the label column and rendered one word per line, a column of text taller than the form
        // it was explaining. `wide` adds the grid equivalent, and the two do not conflict.
        <p className={`basis-full text-xs leading-relaxed text-text-secondary ${
          wide ? 'col-span-full' : ''}`}>{children}</p>
      ) : null}
    </>
  );
}
