/**
 * The one application — owner, manager and operator, behind one login.
 *
 * WHY ONE AND NOT TWO. The MANAGER needs both surfaces: the field screen when he stands at the
 * till and the sections when he sits (spec 10.8). Two applications means two sign-ins for him, and
 * that alone settles it. The operator is not given a smaller app; he is given the same app, which
 * shows him one section because that is all his capabilities reach.
 *
 * THE CHROME IS ui/'s AppShell, BY ALIAS. Sidebar rail, persisted collapse, brand slot, user
 * block, theme and language toggles, and a Toaster — all of it already built. `ui/` is our own
 * copy (taken from base-services' platform/ui at their v0.16.29, 2026-08-22, so we could edit it
 * ourselves) — we supply the nav items and the brand, and can now change the shell itself too,
 * rather than waiting on someone else's release.
 */
import { useEffect, useState } from 'react';
import { Outlet, useNavigate, type NavigateFunction } from 'react-router-dom';

import { SubscriptionBar } from './SubscriptionBar';
import { AppShell } from '@base-ui/shell';
import { EmptyState } from '@base-ui/design-system/EmptyState';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import { DENIED, isReady, type Loading } from './loading';
import { NAME_AR, Wordmark } from './brand/Mark';
import { Door } from './screens/Door';
import { LegalGate } from './screens/LegalGate';
import { WelcomeTrial } from './screens/WelcomeTrial';
import { action, call, fetchCatalog, SessionExpired, type Catalog } from './catalog';
import { ACCOUNT_PATH, isOutage, SUPPORT_PATH, visibleSections, type SectionState } from './nav';
import { BranchSwitch } from './BranchSwitch';
import { currentBranch, loadBranch, saveBranch, type ScopeBranch } from './branch-scope';
import type { Owned } from './apps';
import { isSignedIn, useSession, type Session } from './session';
import { WELCOME_TRIAL_KEY } from './auth';
import { OperatorI18nProvider, tf, useOperatorI18n } from './operator-i18n';
import { OperatorLocaleSwitcher } from './OperatorLocaleSwitcher';
import { NotificationBell } from './NotificationBell';
import './nav-i18n';

/**
 * THE SHELL ITSELF, AS ITS OWN COMPONENT — split out of `App()` for exactly one reason:
 * `useOperatorI18n()` throws outside `<OperatorI18nProvider>`, and `App()` is the component that
 * RENDERS the provider, not a descendant of it. Its own body runs before the provider exists, so
 * `navItems`/`labels` built there could never call `t()` — which is exactly how the rail ended up
 * permanently Arabic while every screen inside it correctly switched languages (found live
 * 2026-09-14). This component is a CHILD of the provider instead, where the hook is legal.
 */
function ConsoleShell({
  sections, session, catalog, owned, scoped, allowed, scopeBranches, setBranch, navigate, signOut,
}: {
  sections: SectionState[];
  session: Session;
  catalog: Catalog;
  owned: Loading<Owned>;
  scoped: string;
  allowed: ScopeBranch[];
  scopeBranches: Loading<ScopeBranch[]>;
  setBranch: (id: string) => void;
  navigate: NavigateFunction;
  signOut: () => void;
}) {
  const { t } = useOperatorI18n();
  return (
    <AppShell
      // OUR OWN MARK IS THE NAME ITSELF (2026-09-16 rebrand) — no separate icon, drawn or
      // otherwise. `markOnly` tells the shell not to also print `brand.name` beside it (this IS
      // the name, compact); see ui/'s own AppShell.tsx for why that flag exists at all.
      brand={{ name: NAME_AR, mark: <Wordmark compact className="shrink-0" />, markOnly: true }}
      // DERIVED, NOT WRITTEN — see nav.ts. An operator's list has one entry and a manager's is
      // missing what the owner keeps, with no role check anywhere in this file.
      // A SECTION WHOSE SERVICE IS DOWN IS NAMED, NOT DELETED (م · النمط 3). The row stays where
      // his hand expects it and the label says why it will not answer — «الحملات · متعذّر الآن»
      // rather than a rail that quietly grew shorter and left him counting his own permissions.
      // AND THE ICON, WHICH IS THE ROW'S ONLY FACE WHEN THE RAIL IS COLLAPSED. We passed labels
      // alone, and the shell PERSISTS the collapsed choice per browser — so an owner who once
      // folded the rail was left with seven blank rows: sized, clickable, and mute. He had lost
      // his navigation with nothing on screen to say what had happened or how to undo it.
      // «الدعم الفني» IS FILTERED OUT HERE, not deleted from `SECTIONS` — see nav.ts's own note
      // beside that entry. It still gates on `tickets.open` exactly as before; this only decides
      // where it renders (the icon row below, beside «حسابي», rather than a ninth rail row).
      // TRANSLATED HERE, BY `nav.<id>` — see nav-i18n.ts's own header for why the key is the
      // section's stable id rather than its (Arabic) `label` field, which stays as the ar/fallback
      // text `translate()` reaches for when a locale has not shipped this key yet.
      navItems={sections.filter((s) => s.id !== 'support').map((s) => {
        const label = t(`nav.${s.id}`);
        return {
          to: s.path,
          label: s.unavailable ? tf(t, 'nav.unavailableSuffix', { label }) : label,
          icon: s.icon,
          accent: s.accent,
        };
      })}
      user={{ name: session.operatorName || session.operator }}
      labels={{ collapse: t('shell.collapse'), expand: t('shell.expand'), signOut: t('shell.signOut'),
                account: t('shell.account'), support: t('nav.support') }}
      // «حسابي» AS AN ICON BESIDE SIGN-OUT, not as a ninth row in the rail. Both controls are
      // about the PERSON rather than about the shop, and the shell already groups them in one
      // block — so this costs no rail height and reads where a person already looks for himself.
      // «الدعم الفني» JOINS IT for the same reason, right beside it — moved out of the rail's
      // eight shop-work rows.
      // THE SCOPE ABOVE THE NAV, which is where a scope belongs: everything below this line is
      // about what it says. The shell keeps this slot for exactly that and hides it on the
      // collapsed rail, where there is no room for a control with a label.
      // AND THE STATE TRAVELS WHOLE INTO IT. `allowed` is the collapsed list every OTHER reader
      // wants — «is there a scope to apply» — but the control itself must tell a shop with ONE
      // branch from a shop whose branches we could not READ, and only the raw state can.
      projectSwitcher={
        <BranchSwitch
          branches={scopeBranches}
          branch={scoped}
          onChange={setBranch}
          catalog={catalog}
          // AND THE DOOR IT OPENS IS THE SHOP'S OWN, not a second form built beside the rail.
          // «منشأتي» already creates a branch, counts it against the subscription, names it and can close
          // it; a quick field here would be a second way in that drifts from the first the day
          // either changes. What this saves him is the search — not the screen.
          onAdd={() => navigate(`${ACCOUNT_PATH}?tab=shop`)}
        />
      }
      onAccount={() => navigate(ACCOUNT_PATH)}
      // UNDEFINED, NOT A HANDLER THAT REFUSES — `sections` is already `visibleSections(catalog)`,
      // so an operator without `tickets.open` never gets the entry in the first place; the icon
      // simply does not render for him, same as every other role-gated control in this shell.
      onSupport={sections.some((s) => s.id === 'support') ? () => navigate(SUPPORT_PATH) : undefined}
      onSignOut={() => { signOut(); navigate('/'); }}
      // THE LANGUAGE SWITCH ITSELF, IN THE RAIL — not per-screen any more, and now visible to the
      // owner too (2026-09-11 — the preference moved off Operator rows onto a platform-wide
      // one). It used to live inside Visit.tsx alone, when Visit was the only screen that read
      // useOperatorI18n(); Bookings, Points, Services and «الاشتراك» all read it now too, so a
      // control duplicated onto each of them (or missing from the rest) was the wrong shape.
      // `railSlot` is the shell's own extension point for exactly this — a widget above the user
      // block, alongside `projectSwitcher` above. The bell sits beside the language switch rather
      // than replacing it — two independent controls, one slot, same shape the shell already
      // gives `projectSwitcher` when both a scope and an add-branch action share it.
      railSlot={<div className="flex items-center gap-2"><NotificationBell session={session} /><OperatorLocaleSwitcher /></div>}
    >
      {/* THE SHELL RENDERS CHILDREN INSTEAD OF THE ROUTER OUTLET when given them — its two modes.
          We pass the Outlet explicitly so the screens receive the session and the catalogue we
          already loaded, rather than each fetching the catalogue again on every navigation. */}
      {/* THE LEGAL GATE SITS INSIDE THE SHELL, not in front of it. An owner who must accept a
          re-issued privacy notice is not locked out of a product he pays for — he is stopped at
          the content until he answers, with his own nav still around him. Nothing outstanding
          renders nothing at all. */}
      <LegalGate session={session} catalog={catalog}>
        {/* THE SUBSCRIPTION STATE, ABOVE THE WORK AND NOT INSIDE IT. operations and reminders
            answer 402 on every write once the base lapses, and a 402 arrives after he has typed a
            customer's name and reached for save — the worst possible moment to learn the month
            ended. One line here says it before the first press, and says what still works.
            It renders nothing at all while the answer is unknown or the month has time left. */}
        <SubscriptionBar owned={owned} now={Date.now()} />
        <Outlet context={{ session, catalog, owned, branch: scoped, branches: allowed, setBranch }} />
      </LegalGate>
    </AppShell>
  );
}

export function App() {
  const { session, signedIn, signOut } = useSession();
  const navigate = useNavigate();
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [failed, setFailed] = useState(false);
  // WHAT THE SHOP BOUGHT — READ ONCE, HERE, FOR EVERY SCREEN.
  //
  // Five keys asked from five screens is five round trips on every navigation and five different
  // answers during a deploy. Held beside the catalogue because it answers the same kind of
  // question: the catalogue says what this PERSON may do, this says what the SHOP owns, and a
  // screen needs both to decide between a control, a lock, and neither.
  //
  // It stays null when the action is absent — an operator's catalogue does not carry it, and his
  // screens do not draw locks anyway.
  const [owned, setOwned] = useState<Loading<Owned>>(undefined);
  /**
   * THE BRANCHES THIS PERSON MAY READ, and the one he is currently looking at.
   *
   * READ HERE FOR THE SAME REASON `owned` IS: the choice scopes every screen, so every screen
   * would otherwise ask for the list — five round trips on every navigation, and five chances to
   * disagree about what the scope is.
   *
   * NEVER ASSEMBLED IN THE BROWSER. This is the server's answer, already narrowed to what he may
   * see (§12.4). A switcher built from anything else could offer him a branch the reads then
   * refuse, and «يُضيِّق ولا يوسّع أبداً» is the one rule this control cannot bend.
   */
  const [scopeBranches, setScopeBranches] = useState<Loading<ScopeBranch[]>>(undefined);
  const [branch, setBranchState] = useState<string>(() => loadBranch());
  // THE FLAG DOOR.TSX SET THE MOMENT A FRESH SIGNUP'S TRIAL OPENED — read once, at mount, so a
  // page reload mid-onboarding still shows the welcome exactly once rather than never or forever.
  // `null` = nothing to show; `0` or a real epoch = show it (0 simply omits the date line).
  const [welcomeTrialEnd, setWelcomeTrialEnd] = useState<number | null>(() => {
    try {
      const raw = sessionStorage.getItem(WELCOME_TRIAL_KEY);
      return raw === null ? null : Number(raw) || 0;
    } catch {
      return null;
    }
  });

  useEffect(() => {
    if (!isSignedIn(session)) return;
    fetchCatalog(session)
      .then(setCatalog)
      .catch((err) => {
        // AN EXPIRED SESSION IS SHOWN THE DOOR, not an outage screen. Signing out puts him one tap
        // from the only action that helps — and leaving him on «تعذّر الوصول إلى المنصة» tells
        // him to wait for something that is not broken.
        if (err instanceof SessionExpired) signOut();
        else setFailed(true);
      });
  }, [session, signOut]);

  useEffect(() => {
    if (!catalog) return;
    const a = action(catalog, 'subscription.apps');
    // NOT AN ERROR WHEN ABSENT — but not silence either. Only the owner's catalogue carries this
    // action; for anybody else the state used to stay at its initial value for ever, and the gate
    // reads that as «still loading» and draws a skeleton. A manager holding `loyalty.manage` and
    // not `billing.self` therefore met a grey rectangle on «نقاطي» that never resolved: no
    // programme, no lock, no reason (م · قاطع).
    if (!a) { setOwned(DENIED); return; }
    call<Owned>(session, a)
      // A FAILED READ IS THE OUTAGE ANSWER, not silence: the route reports `checked: false` when
      // billing could not be asked, and a network failure here is the same fact.
      .then(setOwned)
      .catch(() => setOwned({ checked: false, message: 'تعذّر التحقق من اشتراكك الآن — حاول بعد قليل.',
                              keys: [], apps: [] }));
  }, [catalog, session]);

  useEffect(() => {
    if (!catalog) return;
    // TWO IDS, ONE ROUTE — an owner/manager/marketer reaches it via
    // `operations.list_branches` (operations.read); a field operator, who never holds that but
    // genuinely needs his own branch for Bookings, reaches the SAME read via
    // `operations.list_branches_for_bookings` (bookings.read). See services/operations/app/api/
    // v1/staff.py::_READ_BRANCHES for the full reasoning — this used to read a plain operator as
    // «no branches exist», which was false; he simply held neither id.
    const a = action(catalog, 'operations.list_branches')
      || action(catalog, 'operations.list_branches_for_bookings');
    // NOT HIS TO SEE IS ITS OWN ANSWER (م · النمط 2). Neither id in his catalogue and writing
    // `[]` here would say «this shop has no branches» about a chain of five. Both states happen
    // to render the same nothing today — but they are different facts, and the day one of them
    // wants a sentence, the code already knows which one it is holding.
    if (!a) { setScopeBranches(DENIED); return; }
    call<{ branches?: ScopeBranch[] }>(session, a)
      .then((x) => setScopeBranches(x.branches ?? []))
      // AND A FAILED READ IS NOT AN EMPTY ONE EITHER. `null`, so «we could not ask» is never
      // stored as «he has one branch» — the screens stay unnarrowed, which is exactly where they
      // were before this control existed, and no stale option is offered.
      .catch(() => setScopeBranches(null));
  }, [catalog, session]);

  // THE STORED CHOICE IS ONLY HONOURED WHILE IT IS STILL HIS. A branch closed since Tuesday, or a
  // scope the owner has since changed, would otherwise leave him staring at empty screens with no
  // hint that a filter he set last week is the cause.
  // ONE SHAPE FOR THE SWITCHER, whatever the reason there is nothing to offer. `isReady` keeps
  // the three not-a-value states apart in the state itself and collapses them here, at the one
  // place that only cares «is there a list».
  const allowed = isReady(scopeBranches) ? scopeBranches : [];
  const scoped = currentBranch(allowed, branch || null);
  const setBranch = (id: string) => { saveBranch(id); setBranchState(id); };

  // THE DOOR IS NOT A ROUTE, and that is deliberate. A `/login` path is a page the app can be
  // navigated to WHILE signed in and, worse, a page a signed-out person can navigate AWAY from
  // into a screen that then renders half-loaded and 401s. Signed out, there is one thing on the
  // screen and no way past it but through.
  // `onWelcome` FIRES THE SCREEN IMMEDIATELY, in the same render pass `onSignedIn` moves him past
  // this branch — the sessionStorage flag Door.tsx also writes is read-once, at App's own mount,
  // which already happened before he had typed a single character. Without this direct call the
  // welcome only ever showed after a manual refresh remounted App and re-ran that initializer.
  // WRAPPED HERE TOO — a real, live bug (2026-09-12): Door.tsx/DoorLayout.tsx were migrated to
  // operator-i18n (useOperatorI18n() calls, no fallback) without ever being wrapped in the
  // provider that migration assumes every screen sits inside. `useOperatorI18n()` THROWS with no
  // ancestor provider (see its own header note — a deliberate loud failure, not a silent
  // identity fallback), so every signed-out visitor hit a hard crash on the sign-in page itself.
  // `session` here is always a real (if empty-token) `Session`, safe to hand the provider exactly
  // as-is: `getMyLocale` simply fails and falls back to Arabic + `ready` for anyone not signed in
  // yet, the same graceful path it already takes for any other read failure.
  if (!isSignedIn(session)) {
    return (
      <OperatorI18nProvider session={session}>
        <Door onSignedIn={signedIn} onWelcome={setWelcomeTrialEnd} />
      </OperatorI18nProvider>
    );
  }

  // THE WELCOME, SHOWN EXACTLY ONCE — the flag Door.tsx set the moment his shop (and its trial)
  // opened, cleared the instant he presses through. session-scoped, so it cannot survive past this
  // tab or replay on an ordinary sign-in from another device.
  //
  // A DIALOG OVER WHATEVER RENDERS BELOW, NOT A REPLACEMENT FOR IT — «نافذة
  // منبثقة مو صفحة كامله». `WelcomeTrial` portals itself to `document.body`, so it is appended as
  // a sibling to every branch below (loading skeleton, outage screen, the real shell) rather than
  // being one more early return that discards whichever of them was about to render.
  const welcomeOverlay = welcomeTrialEnd !== null ? (
    <WelcomeTrial
      trialEnd={welcomeTrialEnd}
      onDone={() => {
        try { sessionStorage.removeItem(WELCOME_TRIAL_KEY); } catch { /* private mode */ }
        setWelcomeTrialEnd(null);
      }}
    />
  ) : null;

  if (failed) {
    // THE DISTINCTION THAT MATTERS TO A PAYING OWNER: "we cannot reach the platform" and "you have
    // access to nothing" look identical on an empty screen, and only one of them is about him.
    return (
      <>
        <main className="grid min-h-dvh place-items-center bg-surface-0 p-6">
          <EmptyState
            title="تعذّر الوصول إلى المنصة"
            description="حسابك سليم — أعد المحاولة بعد قليل."
          />
        </main>
        {welcomeOverlay}
      </>
    );
  }

  if (!catalog) {
    return (
      <>
        <main className="min-h-dvh bg-surface-0 p-6">
          <Skeleton width={192} height={40} />
        </main>
        {welcomeOverlay}
      </>
    );
  }

  if (isOutage(catalog)) {
    return (
      <>
        <main className="grid min-h-dvh place-items-center bg-surface-0 p-6">
          <EmptyState
            title="الخدمات غير متاحة الآن"
            description="لا علاقة لهذا بحسابك. نعمل على إعادتها."
          />
        </main>
        {welcomeOverlay}
      </>
    );
  }

  const sections = visibleSections(catalog);

  return (
    <>
    {/* THE OPERATOR'S OWN LANGUAGE, ABOVE THE WHOLE SHELL rather than only the routed screens —
        moved here from around the bare <Outlet/> once a SECOND screen (then a third, a fourth)
        started reading useOperatorI18n(): the switch itself lives in the rail now
        (`railSlot` below), which renders alongside the shell's own nav, not inside it, so the
        provider has to cover the shell too. The preference is still read once per account (not
        the device — see operator-i18n.tsx's own header), one provider for every screen and the
        rail control together instead of racing separate fetches for the same row.

        `ConsoleShell` IS THE CHILD THAT ACTUALLY READS IT — see that component's own header for
        why the shell's nav labels moved into a separate component rather than being built here,
        in `App()`'s own body, which runs OUTSIDE this provider. */}
    <OperatorI18nProvider session={session}>
      <ConsoleShell
        sections={sections} session={session} catalog={catalog} owned={owned} scoped={scoped}
        allowed={allowed} scopeBranches={scopeBranches} setBranch={setBranch} navigate={navigate}
        signOut={signOut}
      />
    </OperatorI18nProvider>
    {welcomeOverlay}
    </>
  );
}
