// @imtithalak-ui — the ONE shared app shell (sidebar rail + top-less main + theme/lang/account controls),
// consumed by every channel SPA. It is PURELY PRESENTATIONAL and fully parameterized: the reference is
// the on-prem client shell, moved here byte-for-byte so both channels render an identical chrome and a
// future shell change edits THIS file only. Everything channel-specific — the nav items, brand,
// authenticated user, sign-out/account/theme/language handlers, an optional command-palette slot — is
// supplied by props. Page content renders through <Outlet/>; the collapse state persists per-browser.
import { useEffect, useState, type CSSProperties, type ReactNode } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import {
  Command,
  Languages,
  LifeBuoy,
  LogOut,
  Menu,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Sun,
  UserCog,
  X,
  type LucideIcon,
} from 'lucide-react';
import { Badge } from '../design-system/Badge';
import { BrandMark } from '../design-system/BrandMark';
import { Button } from '../design-system/Button';
import { Toaster } from '../design-system/Toast';
import { cn } from '../lib/cn';

/** A single sidebar entry. `label` is already translated by the channel (it doubles as the collapsed
 *  hover title), so the shell stays i18n-agnostic.
 *
 *  TWO MODES, ONE CHROME. The client is ROUTER-driven: an item has `to` and the shell renders a
 *  <NavLink>. The admin is STATE-driven (a single-page action console, no routes): an item has `key`,
 *  the shell renders a <button> and reports clicks through `onSelect`. Everything else — the rail, the
 *  brand, the user block, the toggles — is identical, which is the whole point of sharing this file.
 *  `icon` is optional so a grouped nav (whose heading carries the icon) can list plain text items. */
export interface AppShellNavItem {
  to?: string;
  key?: string;
  label: string;
  icon?: LucideIcon;
  /** Optional group id (matches an AppShellNavGroup). Ungrouped items render before any heading. */
  group?: string;
  /** THIS ITEM'S OWN ACTIVE-STATE COLOUR (2026-09-13, the owner's own instruction: "كل أيقونة
   *  لازم لون يميّزها"). A hex string from a categorical set (theme/navAccents.ts) — one hue per
   *  section, never cycled, so a rail with more sections than colours gets a real new hue added
   *  there rather than a repeat. Falls back to the rail's own default amber when absent, so an app
   *  that has not adopted per-item colour yet (admin, affiliate) renders exactly as before. */
  accent?: string;
}

/** A heading that groups nav items (admin's Customers / Revenue / Catalog / System). Client passes none
 *  and stays flat. */
export interface AppShellNavGroup {
  id: string;
  label: string;
  icon?: LucideIcon;
}

/** The authenticated user shown in the sidebar footer. `roleLabel` is the pre-translated role badge; omit
 *  it to hide the badge. */
export interface AppShellUser {
  name: string;
  roleLabel?: string;
}

/** Chrome strings the channel supplies from its own i18n so the shell hard-codes no copy. */
export interface AppShellLabels {
  collapse: string;
  expand: string;
  signOut: string;
  /** Text/aria for the theme toggle (only rendered when `onToggleTheme` is given). */
  toggleTheme?: string;
  /** Text/aria for the language toggle (only rendered when `onToggleLang` is given). */
  toggleLang?: string;
  /** Aria/title for the account link (only rendered when `onAccount` is given). */
  account?: string;
  /** Aria/title for the support link (only rendered when `onSupport` is given). */
  support?: string;
}

export interface AppShellProps {
  /** Pre-filtered, role-aware nav items (the channel does its own RBAC filtering). */
  navItems: AppShellNavItem[];
  /** Optional group headings; when given, items are grouped by their `group` id in this order. */
  navGroups?: AppShellNavGroup[];
  /** STATE-DRIVEN mode (admin): the selected item key, and a click handler. When `onSelect` is set the
   *  shell renders <button>s (keyed by `key ?? to`) instead of router <NavLink>s. */
  activeKey?: string;
  onSelect?: (key: string) => void;
  /** Content rendered in the main column INSTEAD of the router <Outlet/> — for a channel without routes. */
  children?: ReactNode;
  /** `mark` is the brand glyph shown beside the name; it DEFAULTS to the platform's BrandMark, so a
   *  consuming product supplies its own (e.g. its logo) without forking the shell. */
  brand: { name: string; tagline?: string; mark?: ReactNode };
  /** The signed-in user, or null (footer collapses to controls only). */
  user: AppShellUser | null;
  labels: AppShellLabels;
  onSignOut: () => void;
  /** Theme control — the button renders only when `onToggleTheme` is provided. */
  theme?: 'dark' | 'light';
  onToggleTheme?: () => void;
  /** Language control — the button renders only when `onToggleLang` is provided (optional per channel). */
  onToggleLang?: () => void;
  /** Account link — renders only when provided (e.g. on-prem has an /account page; cloud does not). */
  onAccount?: () => void;
  /** Support link, in the same user-block icon row as `onAccount` — a channel with its own support
   *  section (e.g. a ticket route) passes this instead of giving it a full rail row of its own, the
   *  same "about the person, not about the shop's own work" grouping `onAccount` already earned. */
  onSupport?: () => void;
  /** Show the "⌘K" command-palette hint in the footer (channels with a palette). */
  showPaletteHint?: boolean;
  /** App-only extras mounted once alongside the shell (e.g. the command palette). */
  slots?: ReactNode;
  /** Optional app-wide footer rendered at the bottom of the main content column (channels with a footer). */
  footer?: ReactNode;
  /** Optional widget injected into the sidebar rail above the user block (e.g. cloud's smart wallet chip). */
  railSlot?: ReactNode;
  /** Optional global project switcher, rendered at the TOP of the sidebar above the nav (the workspace
   *  pivot — cloud's per-client Project selector). Channel-optional, so on-prem is unaffected. */
  projectSwitcher?: ReactNode;
}

// One nav entry, in either mode. Router mode (NavLink, active from the route) or state mode (a button
// that reports its key). The classes are identical so both channels render the same rail.
function renderNavItem(
  item: AppShellNavItem,
  { collapsed, activeKey, onSelect, onNavigate }: { collapsed: boolean; activeKey?: string; onSelect?: (key: string) => void; onNavigate?: () => void },
) {
  const Icon = item.icon;
  // min-h-11 (44px) is the accessible touch-target floor; py-1.5 alone rendered ~32px and failed the
  // mobile spec. The row still hugs its content width; only its HEIGHT is floored.
  const base = 'group relative flex min-h-11 items-center rounded-lg py-1.5 text-sm font-medium transition-all focus-ring';
  const layout = collapsed ? 'justify-center px-0' : 'gap-3 px-3';
  // ACTIVE = A DISTINCT ICON CHIP PLUS A LEADING ACCENT BAR, NOT A TINTED ROW ALONE. The bar (a thin
  // absolutely-positioned pseudo-element at the row's leading edge) is what a premium admin rail
  // actually carries — the chip alone read as "a slightly darker button", the bar is what makes the
  // whole row read as "this is where you are". It survives collapse unchanged since it never depends
  // on the label being visible.
  // ACTIVE'S OWN COLOUR IS DELIBERATELY NOT THE BRAND ACCENT — a nav rail that paints "you are
  // here" in the same purple as every primary button/link in the product reads as one more
  // instance of the brand colour, not as its own distinct signal. AND, PER SECTION NOW
  // (2026-09-13, the owner's own instruction: "كل أيقونة لازم لون يميّزها") — a single flat amber
  // for every item read as no different from one plain colour everywhere, which was the whole
  // complaint. `item.accent` (theme/navAccents.ts's categorical set, one hue per section, never
  // cycled) rides in as a CSS custom property so the SAME Tailwind arbitrary-value classes work
  // for every item — no per-hex class ever needs to exist at build time. Falls back to the
  // original amber for an app that has not adopted per-item colour yet.
  // COLLAPSED DROPS THE ROW'S OWN `bg-surface-2` ENTIRELY — kept, it was a gray rounded-lg pill
  // sitting behind the icon chip's own (smaller, tinted, `rounded-md`) fill, and the two shapes'
  // corners never lined up: a visible seam of grey peeking around the chip, reading as two
  // composited layers rather than one native shape. Expanded, the row's own fill is real (it is
  // what makes the WHOLE row read as active, not just the icon); collapsed, the icon chip alone
  // already fills the visible space, so the row needs no fill of its own to repeat it.
  const NAV_STYLE = (accent?: string) => ({ '--nav-item-accent': accent || '#f0a020' } as CSSProperties);
  const active = (isCollapsed: boolean) => cn(
    'text-text-primary font-semibold',
    !isCollapsed && 'bg-surface-2',
    "before:absolute before:inset-y-2 before:start-0 before:w-[3px] before:rounded-full before:bg-[var(--nav-item-accent)] before:content-['']",
  );
  // A TRUE NEUTRAL HOVER, NOT `surface-2` — `surface-2` carries a faint lavender cast (it is a
  // step off the accent hue, by design, elsewhere in the theme), so a plain "you're hovering
  // this row" state read as a second brand-purple tint rather than a neutral highlight. A flat
  // black/white overlay never carries any hue at all.
  const inactive = 'text-text-secondary hover:bg-black/[0.04] hover:text-text-primary dark:hover:bg-white/[0.06]';
  // EVERY ICON GETS A CHIP, ACTIVE OR NOT — a plain glyph floating with no background read as an
  // afterthought next to the active row's filled square, so the list looked "half-finished" rather
  // than one consistent design. AT REST the chip is a tinted surface with a hairline ring (depth
  // without weight); ON HOVER it darkens neutrally instead of tinting toward the accent, same
  // reasoning as `inactive` above; ACTIVE is this item's OWN colour (see NAV_STYLE above), not the
  // brand accent — still fully legible, and now distinct section to section.
  const iconWrap = (isActive: boolean) => cn(
    'grid size-7 shrink-0 place-items-center rounded-md transition-all duration-150',
    'group-hover:scale-105',
    isActive
      ? "bg-gradient-to-br from-[var(--nav-item-accent)] to-[color-mix(in_oklab,var(--nav-item-accent)_85%,transparent)] text-white shadow-sm ring-1 ring-[color-mix(in_oklab,var(--nav-item-accent)_40%,transparent)]"
      : 'bg-surface-2 text-text-muted ring-1 ring-border-subtle/60 group-hover:bg-black/[0.06] group-hover:text-text-primary group-hover:ring-border-strong/40 dark:group-hover:bg-white/10',
  );
  // COLLAPSED ACCESSIBLE NAME WAS `title=` ALONE — a hover tooltip, invisible to a screen reader that
  // never receives a synthetic hover. `aria-label` (paired with `aria-hidden` on the visual glyphs
  // below) is what actually announces "رسائلي" etc. when the rail is icon-only.
  if (onSelect) {
    const k = item.key ?? item.to ?? item.label;
    const isActive = activeKey === k;
    return (
      <button
        key={k}
        type="button"
        onClick={() => { onSelect(k); onNavigate?.(); }}
        title={collapsed ? item.label : undefined}
        aria-label={collapsed ? item.label : undefined}
        aria-current={isActive ? 'page' : undefined}
        style={NAV_STYLE(item.accent)}
        className={cn(base, layout, 'w-full text-start', isActive ? active(collapsed) : inactive)}
      >
        {Icon && <span className={iconWrap(isActive)} aria-hidden><Icon size={16} /></span>}
        {!collapsed && <span className="truncate">{item.label}</span>}
      </button>
    );
  }
  return (
    <NavLink
      key={item.to}
      to={item.to ?? '#'}
      onClick={onNavigate}
      title={collapsed ? item.label : undefined}
      aria-label={collapsed ? item.label : undefined}
      style={NAV_STYLE(item.accent)}
      className={({ isActive }) => cn(base, layout, isActive ? active(collapsed) : inactive)}
    >
      {({ isActive }) => (
        <>
          {Icon && <span className={iconWrap(isActive)} aria-hidden><Icon size={16} /></span>}
          {!collapsed && <span className="truncate">{item.label}</span>}
        </>
      )}
    </NavLink>
  );
}

export function AppShell({
  navItems,
  navGroups,
  activeKey,
  onSelect,
  children,
  brand,
  user,
  labels,
  onSignOut,
  theme,
  onToggleTheme,
  onToggleLang,
  onAccount,
  onSupport,
  showPaletteHint,
  slots,
  footer,
  railSlot,
  projectSwitcher,
}: AppShellProps) {
  // Collapsible sidebar: shrink to an icon-only rail for more workspace. The choice persists per browser
  // (localStorage) so it survives reloads. Collapsed → labels hidden, native hover tooltips (title=) name
  // each item; the rail keeps every control reachable as an icon.
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem('imtithalak-nav-collapsed') === '1'; } catch { return false; }
  });
  useEffect(() => {
    try { localStorage.setItem('imtithalak-nav-collapsed', collapsed ? '1' : '0'); } catch { /* ignore */ }
  }, [collapsed]);

  // #831 — on phones the fixed rail would eat the screen, so below `md` the sidebar becomes an off-canvas
  // DRAWER: a hamburger in the mobile header opens it, an overlay (or a nav tap) closes it. At `md+` it is
  // the normal static, collapsible rail — desktop is byte-for-byte unchanged.
  const [mobileOpen, setMobileOpen] = useState(false);
  const closeMobile = () => setMobileOpen(false);

  // ESCAPE CLOSES THE DRAWER — a scrim tap and an X button worked, but the keyboard had no way out
  // at all, and a drawer with `role="dialog"` below promises exactly this. Only bound while it is
  // actually open, so it never intercepts Escape anywhere else in the app.
  useEffect(() => {
    if (!mobileOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') closeMobile(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [mobileOpen]);

  return (
    <div className="flex h-screen overflow-hidden bg-surface-0 text-text-primary">
      {/* Mobile scrim behind the drawer (below md only). */}
      {mobileOpen && (
        <button
          type="button"
          aria-label={labels.collapse}
          onClick={closeMobile}
          className="fixed inset-0 z-40 bg-overlay md:hidden"
        />
      )}
      {/* ── sidebar: role-aware grouped nav. Desktop: collapsible rail. Mobile: off-canvas drawer. ── */}
      <aside
        data-testid="sidebar"
        data-collapsed={collapsed}
        role={mobileOpen ? 'dialog' : undefined}
        aria-modal={mobileOpen ? true : undefined}
        aria-label={mobileOpen ? brand.name : undefined}
        className={cn(
          'flex flex-col border-e border-border-subtle bg-surface-1',
          // mobile drawer: fixed, slides in from the start edge (works in RTL + LTR)
          'fixed inset-y-0 start-0 z-50 w-72 max-w-[82vw] -translate-x-full rtl:translate-x-full transition-transform duration-200',
          mobileOpen && '!translate-x-0 shadow-xl',
          // desktop: static in-flow rail with a collapsible width (relative = positioning ctx for the toggle)
          'md:relative md:z-auto md:w-60 md:max-w-none md:!translate-x-0 md:shrink-0 md:shadow-none md:transition-[width]',
          collapsed ? 'md:w-16' : 'md:w-60',
        )}
      >
        {/* Mobile-only: close the drawer (desktop uses the collapse handle instead). */}
        <button
          type="button"
          onClick={closeMobile}
          aria-label={labels.collapse}
          className="absolute end-3 top-3 z-10 grid size-11 place-items-center rounded-lg text-text-secondary transition hover:bg-surface-2 hover:text-text-primary md:hidden"
        >
          <X size={18} />
        </button>

        {/* Collapse toggle — pinned to the sidebar's TRAILING edge (the "back", against the divider) at a
            fixed vertical offset, so it never jumps between the expanded and collapsed layouts. It floats
            on the border, half-overhanging into the main area, the way a rail handle should. */}
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setCollapsed((c) => !c)}
          aria-label={collapsed ? labels.expand : labels.collapse}
          title={collapsed ? labels.expand : labels.collapse}
          data-testid="nav-collapse"
          className="absolute top-6 z-10 hidden h-6 w-6 -translate-y-1/2 rounded-full border border-border-subtle bg-surface-1 shadow-sm end-0 translate-x-1/2 rtl:-translate-x-1/2 md:flex"
        >
          {collapsed ? (
            <PanelLeftOpen size={14} className="rtl:rotate-180" />
          ) : (
            <PanelLeftClose size={14} className="rtl:rotate-180" />
          )}
        </Button>

        {/* brand */}
        <div className={cn('flex items-center border-b border-border-subtle px-3 py-3.5', collapsed ? 'justify-center' : 'justify-start')}>
          {collapsed ? (
            brand.mark ?? <BrandMark size={26} className="shrink-0" />
          ) : (
            <div className="flex min-w-0 items-center gap-2.5 ps-2">
              {brand.mark ?? <BrandMark size={26} className="shrink-0" />}
              <div className="min-w-0">
                <div data-testid="brand-name" className="truncate text-base font-semibold">
                  {brand.name}
                </div>
                {brand.tagline && (
                  <div className="truncate text-xs text-text-muted">{brand.tagline}</div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* optional global project switcher (the workspace pivot), pinned above the nav — expanded only
            (the collapsed icon rail has no room for it) */}
        {projectSwitcher && !collapsed && (
          <div className="px-3 pb-1" data-testid="project-switcher-slot">{projectSwitcher}</div>
        )}

        <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 pt-3">
          {(navGroups && navGroups.length > 0
            ? navGroups
                .map((g) => ({ group: g, items: navItems.filter((it) => it.group === g.id) }))
                .filter((s) => s.items.length > 0)
            : [{ group: null as AppShellNavGroup | null, items: navItems }]
          ).map(({ group, items }) => (
            <div key={group?.id ?? '_flat'} className={cn('space-y-0.5', group && 'pt-2 first:pt-1')}>
              {group && !collapsed && (
                <span className="flex items-center gap-1.5 px-3 pb-1 text-[0.7rem] font-semibold uppercase tracking-[0.12em] text-text-muted">
                  {group.icon && <group.icon size={12} aria-hidden />}
                  {group.label}
                </span>
              )}
              {items.map((item) => renderNavItem(item, { collapsed, activeKey, onSelect, onNavigate: closeMobile }))}
            </div>
          ))}
        </nav>

        {/* logged-in user + role. REDESIGNED — the account/sign-out pair used to be two bare
            ghost buttons floating in empty space (no visible boundary of their own), and both
            shared the exact same neutral hover, so "leaving the account" and "opening it" read
            as the same kind of action. Now: one bounded pill-row (a real edge, not an implied
            one), a divider between the two actions, and sign-out gets its own DANGER-tinted
            hover — a real semantic colour for "you are about to leave", never the brand accent —
            while account keeps a plain neutral hover. Also drops `Badge tone="accent"` on the
            role chip for `neutral`: one more brand-purple instance this rail did not need. */}
        <div className="border-t border-border-subtle px-3 py-2.5" data-testid="current-user">
          {collapsed ? (
            <div className="flex flex-col overflow-hidden rounded-xl border border-border-subtle bg-surface-2/50">
              {onSupport && (
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={onSupport}
                  aria-label={labels.support}
                  title={labels.support}
                  data-testid="support-link"
                  className="rounded-none hover:bg-black/[0.06] dark:hover:bg-white/10"
                >
                  <LifeBuoy size={18} />
                </Button>
              )}
              {onAccount && (
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={onAccount}
                  aria-label={user?.name || labels.account}
                  title={user?.name || labels.account}
                  data-testid="account-link"
                  className={cn(
                    'rounded-none hover:bg-black/[0.06] dark:hover:bg-white/10',
                    onSupport && 'border-t border-border-subtle',
                  )}
                >
                  <UserCog size={18} />
                </Button>
              )}
              <Button
                variant="ghost"
                size="icon"
                onClick={onSignOut}
                aria-label={labels.signOut}
                title={labels.signOut}
                data-testid="logout"
                className={cn(
                  'rounded-none text-text-secondary hover:bg-danger-soft hover:text-danger-on-soft',
                  (onAccount || onSupport) && 'border-t border-border-subtle',
                )}
              >
                <LogOut size={18} />
              </Button>
            </div>
          ) : (
            <div className="flex flex-col overflow-hidden rounded-xl border border-border-subtle bg-surface-2/50">
              <div className="flex items-center justify-between gap-2 px-3 py-2">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium" data-testid="current-username">
                    {user?.name}
                  </div>
                  {user?.roleLabel && (
                    <Badge tone="neutral" className="mt-1" data-testid="current-role">
                      {user.roleLabel}
                    </Badge>
                  )}
                </div>
                {/* ONE GROUP, NOT LOOSE SIBLINGS — both icons live in their own flex row,
                    separate from the username's own flex slot above. A future third icon
                    (or a fourth) joins THIS group and the two just cluster together at the
                    row's own end; nothing about it has to renegotiate space with the name/
                    badge column the way two direct `justify-between` siblings would. */}
                <div className="flex shrink-0 items-center gap-1">
                  {onSupport && (
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={onSupport}
                      aria-label={labels.support}
                      title={labels.support}
                      data-testid="support-link"
                      className="shrink-0 hover:bg-black/[0.06] dark:hover:bg-white/10"
                    >
                      <LifeBuoy size={18} />
                    </Button>
                  )}
                  {onAccount && (
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={onAccount}
                      aria-label={labels.account}
                      data-testid="account-link"
                      className="shrink-0 hover:bg-black/[0.06] dark:hover:bg-white/10"
                    >
                      <UserCog size={18} />
                    </Button>
                  )}
                </div>
              </div>
              <Button
                variant="ghost"
                onClick={onSignOut}
                aria-label={labels.signOut}
                data-testid="logout"
                className="justify-start gap-2 rounded-none border-t border-border-subtle px-3 text-sm text-text-secondary hover:bg-danger-soft hover:text-danger-on-soft"
              >
                <LogOut size={16} /> {labels.signOut}
              </Button>
            </div>
          )}
        </div>

        {/* optional channel-injected rail widget (e.g. cloud's wallet chip). MOVED BELOW the
            user block, right beside the theme/language/palette icon row rather than above it —
            it used to sit as its own full-width band between the nav and the account/sign-out
            icons, reading as a stray control floating apart from the rest of the settings-style
            row it belongs with. Still expanded-only: a collapsed rail has no room for a widget
            with a label (console's own language `<select>`, for instance). */}
        {railSlot && !collapsed && (
          <div className="border-t border-border-subtle px-3 py-3" data-testid="rail-slot">{railSlot}</div>
        )}

        {/* theme + language + palette hint */}
        <div
          className={cn(
            'flex items-center gap-2 border-t border-border-subtle px-3 py-2',
            collapsed && 'flex-col',
          )}
        >
          {onToggleTheme && (
            <Button
              variant="ghost"
              size="icon"
              onClick={onToggleTheme}
              aria-label={labels.toggleTheme}
              title={labels.toggleTheme}
              data-testid="theme-toggle"
            >
              {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
            </Button>
          )}
          {onToggleLang && (
            <Button
              variant="ghost"
              size={collapsed ? 'icon' : 'sm'}
              onClick={onToggleLang}
              className={collapsed ? undefined : 'gap-2'}
              aria-label={labels.toggleLang}
              title={labels.toggleLang}
              data-testid="lang-toggle"
            >
              <Languages size={16} />
              {!collapsed && labels.toggleLang}
            </Button>
          )}
          {showPaletteHint && !collapsed && (
            <span className="ms-auto flex items-center gap-1 text-[10px] text-text-muted">
              <Command size={12} />K
            </span>
          )}
        </div>
      </aside>

      {/* flex column so the footer (when present) is pinned to the BOTTOM: the content wrapper grows to fill
          the viewport, so on a short page the footer sits at the bottom edge — never floating mid-screen —
          and on a long page it flows after the content. */}
      {/* `overscroll-contain` — WITHOUT IT, a fast wheel/touchpad scroll that outruns this
          element's own content does not stop at the true bottom; the browser's own rubber-band
          glide carries the page past it into blank space before snapping back, which reads as
          "the scroll goes further than the page actually has" (reported directly on a long
          table). This is the scroll CONTAINER — the one place that bounce can happen — so it is
          the one place that needs to say the bounce stops here rather than propagating to
          whatever sits behind it. */}
      <main className="flex min-w-0 flex-1 flex-col overflow-x-hidden overflow-y-auto overscroll-contain">
        {/* Mobile header (below md only): a hamburger opens the drawer, with the brand beside it. On desktop
            there is no global header bar — each page owns its own filters next to its content. */}
        <div className="sticky top-0 z-30 flex items-center gap-2.5 border-b border-border-subtle bg-surface-0/90 px-4 py-2.5 backdrop-blur-md md:hidden">
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            aria-label={labels.expand}
            className="grid size-9 place-items-center rounded-lg text-text-secondary transition hover:bg-surface-2 hover:text-text-primary"
          >
            <Menu size={20} />
          </button>
          <div className="flex items-center gap-2">
            {brand.mark ?? <BrandMark size={22} className="shrink-0" />}
            <span className="text-sm font-semibold">{brand.name}</span>
          </div>
        </div>
        {/* max-w-5xl READ AS A MOBILE LAYOUT STRETCHED THIN across a desktop window — every screen
            kept stacking single-column cards inside a fixed 1024px column no matter how wide the
            browser actually was, leaving two dead margins on anything bigger than a laptop. A
            screen is free to lay its own content out in columns past `lg`; this only stops
            reserving the width for it. */}
        <div className="mx-auto w-full max-w-5xl flex-1 p-4 sm:p-6 md:p-8 lg:max-w-7xl xl:max-w-[88rem]">
          {children ?? <Outlet />}
        </div>
        {footer}
      </main>

      {/* app-only extras (e.g. the command palette + shortcuts), mounted once */}
      {slots}
      {/* transient feedback host (copy confirmations, etc.) */}
      <Toaster />
    </div>
  );
}
