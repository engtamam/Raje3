/**
 * The language switch — rebuilt from scratch (2026-09-16, the owner's own direct instruction: "كل
 * المنصة يتغير معاها تصميمه لانه بيسك جدا" — a plain native `<select>` read as too basic for a
 * product redesigning its whole chrome around it). ONE COMPONENT, MOUNTED ONCE (`TopBar.tsx`), so
 * this single file's own design reaches every screen in the product — there is no second copy to
 * keep in sync.
 *
 * A REAL MENU, NOT A NATIVE `<select>` — a floating panel that opens with a spring, shows every
 * language in its OWN script (never translated into the current one — a Bengali reader hunting
 * for his own language should not have to recognise it spelled in Arabic), and marks the active
 * one with a check rather than relying on a native widget's own unstyleable chrome.
 *
 * THE DATA/LOGIC IS UNCHANGED — `useOperatorI18n()`'s `locale`/`setLocale`/`ready`/`saveError` are
 * real product state (the platform-wide `/api/v1/account/me/locale` preference), not chrome; only
 * the presentation is new here.
 */
import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Check, ChevronDown, Languages } from 'lucide-react';
import { OPERATOR_LOCALES, useOperatorI18n } from './operator-i18n';
import './operator-locale-switcher-i18n';

export function OperatorLocaleSwitcher() {
  const { locale, setLocale, ready, saveError, t } = useOperatorI18n();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDocClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDocClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  if (!ready) return null;
  const current = OPERATOR_LOCALES.find((l) => l.value === locale) ?? OPERATOR_LOCALES[0];

  return (
    <div ref={rootRef} className="relative flex items-center gap-2">
      {saveError ? (
        <span role="alert" className="text-xs text-danger">{t('localeSwitcher.saveFailed')}</span>
      ) : null}

      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={t('localeSwitcher.ariaLabel')}
        className="flex h-9 shrink-0 items-center gap-1.5 rounded-full border border-border-subtle bg-surface-1 px-3 text-sm font-semibold transition hover:border-accent/50 focus-ring"
      >
        <Languages size={14} className="shrink-0 text-text-muted" />
        <span dir="ltr">{current.label}</span>
        <ChevronDown size={14} className={`shrink-0 text-text-muted transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      <AnimatePresence>
        {open ? (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.97 }}
            transition={{ type: 'spring', stiffness: 420, damping: 32 }}
            role="listbox"
            className="absolute top-full z-30 mt-2 w-40 overflow-hidden rounded-2xl border border-border-subtle bg-surface-1 p-1 shadow-pop end-0"
          >
            {OPERATOR_LOCALES.map((l) => {
              const active = l.value === locale;
              return (
                <button
                  key={l.value}
                  type="button"
                  role="option"
                  aria-selected={active}
                  dir="ltr"
                  onClick={() => { setLocale(l.value); setOpen(false); }}
                  className={`flex w-full items-center justify-between gap-2 rounded-xl px-3 py-2 text-start text-sm font-medium transition ${
                    active ? 'bg-accent-soft text-accent-on-soft' : 'text-text-primary hover:bg-surface-2'
                  }`}
                >
                  {l.label}
                  {active ? <Check size={14} /> : null}
                </button>
              );
            })}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
