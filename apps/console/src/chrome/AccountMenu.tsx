/**
 * «حسابي» AS A REAL MENU, NOT A DIRECT LINK — found live (owner's own report): the account icon
 * used to navigate straight to «حسابي» with no way to sign out from the top bar at all. Two
 * items, both real actions the app already had (`onAccount`/`onSignOut`) — this only gives them a
 * shared door, the same floating-panel pattern `OperatorLocaleSwitcher.tsx` already established
 * for this bar (spring open, click-outside/Escape to close).
 */
import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { LogOut, UserCog } from 'lucide-react';
import { useOperatorI18n } from '../operator-i18n';
import './top-bar-i18n';

export function AccountMenu({ onAccount, onSignOut }: { onAccount: () => void; onSignOut: () => void }) {
  const { t } = useOperatorI18n();
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

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={t('topBar.account')}
        title={t('topBar.account')}
        className="grid size-9 shrink-0 place-items-center rounded-full text-text-secondary transition hover:bg-surface-1 hover:text-text-primary focus-ring"
      >
        <UserCog size={18} />
      </button>

      <AnimatePresence>
        {open ? (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.97 }}
            transition={{ type: 'spring', stiffness: 420, damping: 32 }}
            role="menu"
            className="absolute top-full z-30 mt-2 w-44 overflow-hidden rounded-2xl border border-border-subtle bg-surface-1 p-1 shadow-pop end-0"
          >
            <button
              type="button"
              role="menuitem"
              onClick={() => { setOpen(false); onAccount(); }}
              className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-start text-sm font-medium text-text-primary transition hover:bg-surface-2"
            >
              <UserCog size={15} className="shrink-0 text-text-muted" /> {t('topBar.account')}
            </button>
            <button
              type="button"
              role="menuitem"
              onClick={() => { setOpen(false); onSignOut(); }}
              className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-start text-sm font-medium text-danger transition hover:bg-danger-soft"
            >
              <LogOut size={15} className="shrink-0" /> {t('topBar.signOut')}
            </button>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
