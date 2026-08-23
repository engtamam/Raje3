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
 *
 * MOBILE GETS A BOTTOM BAR, NOT THE SHOP CONSOLE'S SIDEBAR (2026-08-22): a marketer works this app
 * one-handed, walking between shops, and the thumb reaches the bottom edge of a phone — not a
 * hamburger in a corner. `platform/ui`'s shared `AppShell` collapses to an off-canvas DRAWER on
 * mobile (a hidden rail behind a hamburger), which is right for a shop owner sitting at a counter
 * and wrong here on purpose. So this is its own component, not that one reused — same reasoning
 * `api.ts`'s own header comment gives for not reusing the shop's `auth.ts`: a different audience,
 * bent to fit, is the failure this avoids.
 *
 * ONE TAB LIST, TWO RENDERINGS, PICKED BY CSS NOT JS. `md:hidden` / `hidden md:flex` — no
 * `matchMedia` listener, no layout flash while JS decides; the breakpoint the shop console itself
 * already uses for the same rail-vs-drawer split (`AppShell.tsx`'s own `md:` classes).
 */
import type { ReactNode } from 'react';
import { Home as HomeIcon, Users, Wrench, Wallet, CircleUserRound, UsersRound } from 'lucide-react';

export type Tab = 'home' | 'leads' | 'tools' | 'earnings' | 'team' | 'account';

/** SIX SLOTS FOR A MANAGER, STILL FIVE FOR A PROMOTER. «فريقي» is the one ADDITIONAL thing a
 *  manager gets on top of everything a promoter already has (Tamam, 2026-08-23) — not a sixth
 *  slot reopened for everybody, which is exactly what this file's own header note fixed the bar
 *  against. Inserted after «أرباحي»: team management is a business concern, closest to money. */
function tabsFor(isManager: boolean): { id: Tab; label: string; icon: ReactNode; ready: boolean }[] {
  const base: { id: Tab; label: string; icon: ReactNode; ready: boolean }[] = [
    { id: 'home', label: 'الرئيسية', icon: <HomeIcon size={20} />, ready: true },
    { id: 'leads', label: 'عملائي', icon: <Users size={20} />, ready: true },
    { id: 'tools', label: 'أدواتي', icon: <Wrench size={20} />, ready: true },
    { id: 'earnings', label: 'أرباحي', icon: <Wallet size={20} />, ready: true },
  ];
  if (isManager) base.push({ id: 'team', label: 'فريقي', icon: <UsersRound size={20} />, ready: true });
  base.push({ id: 'account', label: 'حسابي', icon: <CircleUserRound size={20} />, ready: true });
  return base;
}

interface NavProps { active: Tab; onChange: (t: Tab) => void; isManager: boolean }

/** DESKTOP/TABLET (md and up) — a side rail, rendered FIRST in `AffiliatePortal`'s markup so the
 *  browser's own RTL row-reversal puts it on the start (right) edge, exactly where `AppShell`'s
 *  own `<aside>` sits in the shop console — same convention, not reinvented. */
export function AffiliateSidebar({ active, onChange, isManager }: NavProps) {
  return (
    <aside
      aria-label="أقسام بوابة المسوّق"
      className="sticky top-0 hidden h-dvh w-56 shrink-0 flex-col gap-0.5 border-e border-border-subtle bg-surface-1 p-3 md:flex"
    >
      {tabsFor(isManager).map((t) => (
        <button
          key={t.id}
          type="button"
          onClick={() => onChange(t.id)}
          aria-current={active === t.id ? 'page' : undefined}
          className={`flex min-h-11 items-center gap-3 rounded-lg px-3 text-sm font-medium transition-colors ${
            active === t.id
              ? 'bg-accent-soft text-accent-on-soft'
              : 'text-text-secondary hover:bg-surface-2 hover:text-text-primary'
          }`}
        >
          {t.icon}
          {t.label}
        </button>
      ))}
    </aside>
  );
}

/** PHONE (below md) — a bottom bar, rendered LAST after the content column so it sits at the foot
 *  of the mobile column layout, sticky to the viewport's bottom edge, thumb-reachable. */
export function AffiliateBottomNav({ active, onChange, isManager }: NavProps) {
  return (
    <nav
      aria-label="أقسام بوابة المسوّق"
      className="sticky bottom-0 z-20 flex border-t border-border-subtle bg-surface-1/95 backdrop-blur md:hidden"
    >
      {tabsFor(isManager).map((t) => (
        <button
          key={t.id}
          type="button"
          onClick={() => onChange(t.id)}
          aria-current={active === t.id ? 'page' : undefined}
          className={`flex min-h-11 flex-1 flex-col items-center gap-0.5 py-2 text-xs ${
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
