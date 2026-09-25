/**
 * The one application — owner, manager and operator, behind one login.
 *
 * WHY ONE AND NOT TWO. The MANAGER needs both surfaces: the field screen when he stands at the
 * till and the sections when he sits (spec 10.8). Two applications means two sign-ins for him, and
 * that alone settles it. The operator is not given a smaller app; he is given the same app, which
 * shows him one section because that is all his capabilities reach.
 *
 * NO SIDEBAR RAIL (2026-09-16, the last step of the 7-phase app-store redesign,
 * [[task-app-store-redesign-7-phases]]) — the chrome used to be `ui/`'s `@base-ui` `AppShell`
 * (a shared copy taken from base-services' platform/ui); it is gone entirely now, replaced by
 * `chrome/ConsoleLayout.tsx` + `chrome/TopBar.tsx`, this product's own fresh components
 * (`rj-ui/`), once every rail row had a real equivalent path through the launcher/top bar.
 */
import { useEffect, useState } from 'react';
import { Outlet, useNavigate, type NavigateFunction } from 'react-router-dom';

import { SubscriptionBar } from './SubscriptionBar';
import { EmptyState } from './rj-ui/EmptyState';
import { Skeleton } from './rj-ui/Skeleton';
import { Button } from './rj-ui/Button';
import { DENIED, isReady, type Loading } from './loading';
import { Door } from './screens/Door';
import { LegalGate } from './screens/LegalGate';
import { WelcomeTrial } from './screens/WelcomeTrial';
import { action, call, fetchCatalog, SessionExpired, type Catalog } from './catalog';
import { ACCOUNT_PATH, isOutage, SUPPORT_WHATSAPP_URL, visibleSections, type SectionState } from './nav';
import { currentBranch, loadBranch, saveBranch, type ScopeBranch } from './branch-scope';
import type { Owned } from './apps';
import { isSignedIn, useSession, type Session } from './session';
import { WELCOME_TRIAL_KEY } from './auth';
import { OperatorI18nProvider } from './operator-i18n';
import { TopBar } from './chrome/TopBar';
import { ConsoleLayout } from './chrome/ConsoleLayout';
import './nav-i18n';
import './api-i18n';

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
  return (
    <ConsoleLayout>
      <TopBar
        session={session}
        catalog={catalog}
        owned={owned}
        branch={scoped}
        branches={scopeBranches}
        onChangeBranch={setBranch}
        onAddBranch={() => navigate(`${ACCOUNT_PATH}?tab=shop`)}
        onAccount={() => navigate(ACCOUNT_PATH)}
        onSignOut={() => { signOut(); navigate('/'); }}
        // UNDEFINED, NOT A HANDLER THAT REFUSES — `sections` is already `visibleSections(catalog)`,
        // so an operator without `tickets.open` never gets the entry in the first place; the icon
        // simply does not render for him, same as every other role-gated control in this bar.
        //
        // OPENS WHATSAPP DIRECTLY, NOT `SUPPORT_PATH` (owner's own instruction, 2026-09-16) — the
        // in-app support screen/route is untouched underneath, just unlinked from this icon; see
        // `SUPPORT_WHATSAPP_URL`'s own note in `nav.ts` for how to relink it later.
        onSupport={sections.some((s) => s.id === 'support')
          ? () => window.open(SUPPORT_WHATSAPP_URL, '_blank', 'noopener,noreferrer')
          : undefined}
      />
      {/* THE LEGAL GATE SITS INSIDE THE LAYOUT, not in front of it. An owner who must accept a
          re-issued privacy notice is not locked out of a product he pays for — he is stopped at
          the content until he answers, with the top bar still around him. Nothing outstanding
          renders nothing at all. */}
      <LegalGate session={session} catalog={catalog}>
        <div className="p-4 sm:p-6 md:p-8">
          {/* THE SUBSCRIPTION STATE, ABOVE THE WORK AND NOT INSIDE IT. operations and reminders
              answer 402 on every write once the base lapses, and a 402 arrives after he has typed
              a customer's name and reached for save — the worst possible moment to learn the
              month ended. One line here says it before the first press, and says what still
              works. It renders nothing at all while the answer is unknown or the month has time
              left. */}
          <SubscriptionBar owned={owned} now={Date.now()} />
          <Outlet context={{ session, catalog, owned, branch: scoped, branches: allowed, setBranch }} />
        </div>
      </LegalGate>
    </ConsoleLayout>
  );
}

export function App() {
  const { session, signedIn, signOut } = useSession();
  const navigate = useNavigate();
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [failed, setFailed] = useState(false);
  // BUMPED TO RE-RUN THE CATALOGUE FETCH BELOW — a plain boolean `failed` gave the owner no way
  // back except a manual page reload, on a screen whose own caption promises "أعد المحاولة بعد
  // قليل" (try again shortly) with nothing on it that tries again. Found live (2026-09-16): a
  // session left idle — tab backgrounded, then the OS/browser's own network briefly drops during
  // resume — throws a plain fetch error, never `SessionExpired`, so it landed here and stayed
  // here forever, on a platform that came right back a second later.
  const [retryTick, setRetryTick] = useState(0);
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
    let live = true;
    setFailed(false);
    fetchCatalog(session)
      .then((c) => { if (live) setCatalog(c); })
      .catch((err) => {
        if (!live) return;
        // AN EXPIRED SESSION IS SHOWN THE DOOR, not an outage screen. Signing out puts him one tap
        // from the only action that helps — and leaving him on «تعذّر الوصول إلى المنصة» tells
        // him to wait for something that is not broken.
        if (err instanceof SessionExpired) signOut();
        else setFailed(true);
      });
    return () => { live = false; };
  }, [session, signOut, retryTick]);

  // AUTO-RETRY THE MOMENT HE ACTUALLY COMES BACK — the exact trigger reported live: leave the tab
  // idle a while, come back, platform unreachable. A tab that was backgrounded long enough for the
  // OS to freeze its network, or one whose connection simply dropped and came back, resumes with
  // no signal of its own that anything happened; `visibilitychange`/`online` are the two real
  // signals a browser gives for "the person is looking again" and "the network is back", so retry
  // on either rather than making him find and press a button for something that fixes itself.
  useEffect(() => {
    if (!failed) return;
    const retry = () => setRetryTick((n) => n + 1);
    const onVisible = () => { if (document.visibilityState === 'visible') retry(); };
    document.addEventListener('visibilitychange', onVisible);
    window.addEventListener('online', retry);
    return () => {
      document.removeEventListener('visibilitychange', onVisible);
      window.removeEventListener('online', retry);
    };
  }, [failed]);

  useEffect(() => {
    if (!catalog) return;
    const a = action(catalog, 'subscription.apps');
    // NOT AN ERROR WHEN ABSENT — but not silence either. Only the owner's catalogue carries this
    // action; for anybody else the state used to stay at its initial value for ever, and the gate
    // reads that as «still loading» and draws a skeleton. A manager holding `loyalty.manage` and
    // not `billing.self` therefore met a grey rectangle on «نقاط الولاء» that never resolved: no
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
            action={<Button onClick={() => setRetryTick((n) => n + 1)}>إعادة المحاولة</Button>}
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
