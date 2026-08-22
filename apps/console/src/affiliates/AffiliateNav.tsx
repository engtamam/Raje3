/**
 * The bottom nav — the FIRST shared shell the portal has had (2026-08-22). Home and Leads were
 * both built as if they were the only screen; a second real screen means somewhere has to hold
 * "which one am I on" instead of `AffiliatePortal` hard-rendering one component.
 *
 * FIVE SLOTS NOW, TWO OF THEM REAL. The approved 8-screen design (manager) / 6-screen (promoter)
 * names all five bottom-nav destinations up front — الرئيسية, عملائي, أدواتي, أرباحي, حسابي — and
 * showing only the two that exist yet would mean relabelling this bar on every future slice, which
 * is its own kind of instability. A stub tab says «قريبًا» rather than pretending to be a working
 * screen — the same honesty rule Home's own empty states follow, applied to navigation instead of
 * data.
 */
import type { ReactNode } from 'react';
import { Home as HomeIcon, Users, Wrench, Wallet, CircleUserRound } from 'lucide-react';

export type Tab = 'home' | 'leads' | 'tools' | 'earnings' | 'account';

const TABS: { id: Tab; label: string; icon: ReactNode; ready: boolean }[] = [
  { id: 'home', label: 'الرئيسية', icon: <HomeIcon size={20} />, ready: true },
  { id: 'leads', label: 'عملائي', icon: <Users size={20} />, ready: true },
  { id: 'tools', label: 'أدواتي', icon: <Wrench size={20} />, ready: false },
  { id: 'earnings', label: 'أرباحي', icon: <Wallet size={20} />, ready: false },
  { id: 'account', label: 'حسابي', icon: <CircleUserRound size={20} />, ready: false },
];

export function AffiliateNav({ active, onChange }: { active: Tab; onChange: (t: Tab) => void }) {
  return (
    <nav
      aria-label="أقسام بوابة المسوّق"
      className="sticky bottom-0 flex border-t border-border-subtle bg-surface-1/95 backdrop-blur"
    >
      {TABS.map((t) => (
        <button
          key={t.id}
          type="button"
          onClick={() => onChange(t.id)}
          aria-current={active === t.id ? 'page' : undefined}
          className={`flex flex-1 flex-col items-center gap-0.5 py-2 text-xs ${
            active === t.id ? 'text-accent' : 'text-text-secondary'
          }`}
        >
          {t.icon}
          <span>{t.label}</span>
        </button>
      ))}
    </nav>
  );
}

/** What a stub tab shows — never a blank screen, never a fake "coming soon" illustration doing
 *  the work an honest sentence already does. */
export function ComingSoon({ label }: { label: string }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 p-6 text-center">
      <p className="text-lg">{label}</p>
      <p className="text-sm text-text-secondary">هذا القسم قيد البناء — قريبًا.</p>
    </div>
  );
}
