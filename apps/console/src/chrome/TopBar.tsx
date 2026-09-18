/**
 * «الشريط العلوي» — phase 4 of the app-store redesign (2026-09-16). A FRESH, purpose-built bar,
 * not a re-skin of the old sidebar footer — the owner's own instruction on this whole redesign
 * ([[app-store-redesign-new-components-not-reused]]) names "the top bar" explicitly as one of the
 * pieces that must be newly built, not restyled.
 *
 * FOUR CONTROLS, PERSISTENT, ABOVE EVERY SCREEN — not just the launcher: language, notifications,
 * account, and the branch switch. The branch switch is deliberately global here rather than
 * per-app (see [[app-store-branch-switch-global]]) — a scope choice belongs to the whole session,
 * not to whichever screen happens to be open when it is made.
 *
 * REUSES THE UNDERLYING WIDGETS' OWN DATA/LOGIC (`BranchSwitch`, `NotificationBell`,
 * `OperatorLocaleSwitcher`) — their fetch/read/permission logic is real product logic, not chrome,
 * and re-deriving it here would be the exact kind of drift [[no-placeholder-drift]] warns about.
 * What is fresh is the BAR ITSELF: the glossy full-bleed strip, the pill grouping, the dividers —
 * the actual "chrome" this phase is about.
 *
 * STILL SITS ABOVE THE OLD SIDEBAR'S OWN COPIES OF THESE SAME THREE CONTROLS (railSlot/
 * projectSwitcher in `@base-ui/shell`'s `AppShell`) FOR NOW — `App.tsx` stops PASSING them there
 * (no more duplicate controls on screen), but the shell itself is not touched: editing that file
 * would mean restyling the old nav, which this same redesign rule forbids just as much as it
 * forbids restyling the old cards. The sidebar becomes fully dead code only at the end of the
 * 7-phase plan (per [[task-app-store-redesign-7-phases]]), not mid-way through it.
 */
import { Home, MessageCircleQuestion } from 'lucide-react';
import { Link } from 'react-router-dom';
import { BranchSwitch } from '../BranchSwitch';
import { NotificationBell } from '../NotificationBell';
import { OperatorLocaleSwitcher } from '../OperatorLocaleSwitcher';
import { AiUnitsGauge } from './AiUnitsGauge';
import { AccountMenu } from './AccountMenu';
import { useOperatorI18n } from '../operator-i18n';
import { action, type Catalog } from '../catalog';
import type { Loading } from '../loading';
import type { ScopeBranch } from '../branch-scope';
import type { Session } from '../session';
import type { Owned } from '../apps';
import './top-bar-i18n';

export interface TopBarProps {
  session: Session;
  catalog: Catalog;
  /** Whether this shop holds the WhatsApp assistant — `AiUnitsGauge` gates its own visibility on
   *  this, not on `total > 0`, so a subscribed shop still sees the gauge at a real zero balance. */
  owned: Loading<Owned>;
  branch: string;
  branches: Loading<ScopeBranch[]>;
  onChangeBranch: (id: string) => void;
  onAddBranch: () => void;
  onAccount: () => void;
  /** Found live (owner's own report): the account icon used to navigate straight to «حسابي»
   *  with no way to sign out from this bar at all. Now opens `AccountMenu` (حسابي/تسجيل الخروج)
   *  instead of calling `onAccount` directly. */
  onSignOut: () => void;
  /** «الدعم الفني» — one of the "الشاشات الاستثنائية" (phase 5, [[task-app-store-redesign-7-phases]]):
   *  a real screen that is not an app (no plan, no feature, no launcher tile) and so gets an icon
   *  here instead, same treatment `onAccount` already has. `undefined` when this role holds no
   *  `tickets.open` — the icon then simply does not render, same rule the old sidebar's own
   *  `onSupport` already followed. */
  onSupport?: () => void;
}

export function TopBar({
  session, catalog, owned, branch, branches, onChangeBranch, onAddBranch, onAccount, onSignOut, onSupport,
}: TopBarProps) {
  const { t } = useOperatorI18n();
  return (
    // NEVER STICKY, ON PURPOSE (the owner's own direct instruction) — scrolls away with the page
    // on every screen size, same as any other row, rather than permanently pinning itself above
    // the work.
    <div className="relative z-20 flex items-center gap-3 border-b border-border-subtle bg-surface-1/85 px-4 py-2.5 backdrop-blur-md sm:px-6 md:px-8">
      {/* THE ONE WAY BACK TO «متجر التطبيقات» — the owner's own direct instruction: replacing the
          old sidebar's index route with the launcher left no link back to it from inside any
          other screen (the sidebar's own brand mark was never a link either). This is that link,
          global like the rest of this bar. */}
      <Link
        to="/"
        aria-label={t('topBar.home')}
        title={t('topBar.home')}
        className="grid size-9 shrink-0 place-items-center rounded-full text-text-secondary transition hover:bg-surface-2 hover:text-text-primary focus-ring"
      >
        <Home size={18} />
      </Link>

      <div className="min-w-0 flex-1">
        <BranchSwitch
          branches={branches}
          branch={branch}
          onChange={onChangeBranch}
          catalog={catalog}
          onAdd={action(catalog, 'operations.create_branch') ? onAddBranch : undefined}
        />
      </div>

      {/* THE AI-UNITS GAUGE, FREE-STANDING TOO, RIGHT BESIDE SUPPORT (2026-09-19, owner's own
          instruction) — same reasoning as the support button's own note just below: buried in the
          muted neutral pill it read as one more dull utility icon, not "how much AI is left". Its
          own black-and-gold chip (`AiUnitsGauge.tsx`'s own note) gives it the same distinct visual
          weight, right next to the other "this one matters" icon. */}
      <AiUnitsGauge session={session} catalog={catalog} owned={owned} />

      {/* «الدعم الفني» FREE-STANDING, NOT IN THE MUTED PILL — found live (owner's own report):
          folded into the same faded neutral pill as notifications/language/account, it read as
          just another dull utility icon, not the "talk to us" moment it actually is. Its own
          accent-tinted chip (a real chat glyph, not the old life-ring) gives it the one distinct
          visual weight in the bar, the way a real support entry point earns. */}
      {onSupport ? (
        <button
          type="button"
          onClick={onSupport}
          aria-label={t('topBar.support')}
          title={t('topBar.support')}
          className="grid size-9 shrink-0 place-items-center rounded-full bg-gradient-to-br from-emerald-400 to-teal-600 text-white shadow-[0_2px_10px_-2px_rgba(16,185,129,0.65)] transition hover:brightness-105 focus-ring"
        >
          <MessageCircleQuestion size={18} />
        </button>
      ) : null}

      {/* ONE GLOSSY PILL, THE REST — the bar's own "chrome" moment: a single bounded, tinted
          surface instead of icons floating loose against the page, so the group reads as one
          deliberate object rather than leftovers pulled out of the old rail. */}
      <div className="flex shrink-0 items-center gap-1 rounded-full border border-border-subtle bg-surface-2/60 p-1 shadow-sm">
        <NotificationBell session={session} />
        <OperatorLocaleSwitcher />
        <AccountMenu onAccount={onAccount} onSignOut={onSignOut} />
      </div>
    </div>
  );
}
