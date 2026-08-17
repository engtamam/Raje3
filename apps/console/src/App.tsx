/**
 * The one application — owner, manager and operator, behind one login.
 *
 * WHY ONE AND NOT TWO. The MANAGER needs both surfaces: the field screen when he stands at the
 * till and the sections when he sits (spec 10.8). Two applications means two sign-ins for him, and
 * that alone settles it. The operator is not given a smaller app; he is given the same app, which
 * shows him one section because that is all his capabilities reach.
 *
 * THE CHROME IS platform/ui's AppShell, BY ALIAS. Sidebar rail, persisted collapse, brand slot,
 * user block, theme and language toggles, and a Toaster — all of it already built and all of it
 * arriving with their next release. We supply the nav items and the brand; nothing else here is
 * ours to design.
 */
import { useEffect, useState } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { AppShell } from '@base-ui/shell';
import { EmptyState } from '@base-ui/design-system/EmptyState';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import { DENIED, isReady, type Loading } from './loading';
import { Mark, NAME_AR } from './brand/Mark';
import { Door } from './screens/Door';
import { LegalGate } from './screens/LegalGate';
import { action, call, fetchCatalog, SessionExpired, type Catalog } from './catalog';
import { ACCOUNT_PATH, isOutage, visibleSections } from './nav';
import { BranchSwitch } from './BranchSwitch';
import { currentBranch, loadBranch, saveBranch, type ScopeBranch } from './branch-scope';
import type { Owned } from './apps';
import { isSignedIn, useSession } from './session';

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
    const a = action(catalog, 'operations.list_branches');
    // NOT HIS TO SEE IS ITS OWN ANSWER (م · النمط 2). An operator's catalogue carries no such
    // action, and writing `[]` here would say «this shop has no branches» about a chain of five.
    // Both states happen to render the same nothing today — but they are different facts, and the
    // day one of them wants a sentence, the code already knows which one it is holding.
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
  if (!isSignedIn(session)) return <Door onSignedIn={signedIn} />;

  if (failed) {
    // THE DISTINCTION THAT MATTERS TO A PAYING OWNER: "we cannot reach the platform" and "you have
    // access to nothing" look identical on an empty screen, and only one of them is about him.
    return (
      <main className="grid min-h-dvh place-items-center bg-surface-0 p-6">
        <EmptyState
          title="تعذّر الوصول إلى المنصة"
          description="حسابك سليم — أعد المحاولة بعد قليل."
        />
      </main>
    );
  }

  if (!catalog) {
    return (
      <main className="min-h-dvh bg-surface-0 p-6">
        <Skeleton width={192} height={40} />
      </main>
    );
  }

  if (isOutage(catalog)) {
    return (
      <main className="grid min-h-dvh place-items-center bg-surface-0 p-6">
        <EmptyState
          title="الخدمات غير متاحة الآن"
          description="لا علاقة لهذا بحسابك. نعمل على إعادتها."
        />
      </main>
    );
  }

  const sections = visibleSections(catalog);

  return (
    <AppShell
      // OUR OWN MARK, AND IT IS THE ONE LINE THIS WAITED FOR.
      //
      // The shell drew its own BrandMark unconditionally — امتثالك's notary seal, a ring holding a
      // checkmark, meaning "sealed · verified". Right for a compliance product and wrong for ours:
      // راجِع is a journey that closes. We escalated rather than forking the shell, and
      // `brand.mark?: ReactNode` arrived in v0.16.4, defaulted to BrandMark so no consumer changed.
      //
      // The wait was not caution: an extra property is a COMPILE ERROR in TypeScript, never a
      // silently ignored one, so writing this line before the version that supports it would have
      // broken the build rather than sat quietly. One tag, one line.
      brand={{ name: NAME_AR, mark: <Mark size={26} className="shrink-0" /> }}
      // DERIVED, NOT WRITTEN — see nav.ts. An operator's list has one entry and a manager's is
      // missing what the owner keeps, with no role check anywhere in this file.
      // A SECTION WHOSE SERVICE IS DOWN IS NAMED, NOT DELETED (م · النمط 3). The row stays where
      // his hand expects it and the label says why it will not answer — «رسائلي · متعذّر الآن»
      // rather than a rail that quietly grew shorter and left him counting his own permissions.
      // AND THE ICON, WHICH IS THE ROW'S ONLY FACE WHEN THE RAIL IS COLLAPSED. We passed labels
      // alone, and the shell PERSISTS the collapsed choice per browser — so an owner who once
      // folded the rail was left with seven blank rows: sized, clickable, and mute. He had lost
      // his navigation with nothing on screen to say what had happened or how to undo it.
      navItems={sections.map((s) => ({
        to: s.path,
        label: s.unavailable ? `${s.label} · متعذّر الآن` : s.label,
        icon: s.icon,
      }))}
      user={{ name: session.operatorName || session.operator }}
      labels={{ collapse: 'طيّ القائمة', expand: 'فتح القائمة', signOut: 'تسجيل الخروج',
                account: 'حسابي' }}
      // «حسابي» AS AN ICON BESIDE SIGN-OUT, not as a ninth row in the rail. Both controls are
      // about the PERSON rather than about the shop, and the shell already groups them in one
      // block — so this costs no rail height and reads where a person already looks for himself.
      // THE SCOPE ABOVE THE NAV, which is where a scope belongs: everything below this line is
      // about what it says. The shell keeps this slot for exactly that and hides it on the
      // collapsed rail, where there is no room for a control with a label.
      projectSwitcher={
        <BranchSwitch branches={allowed} branch={scoped} onChange={setBranch} />
      }
      onAccount={() => navigate(ACCOUNT_PATH)}
      onSignOut={() => { signOut(); navigate('/'); }}
    >
      {/* THE SHELL RENDERS CHILDREN INSTEAD OF THE ROUTER OUTLET when given them — its two modes.
          We pass the Outlet explicitly so the screens receive the session and the catalogue we
          already loaded, rather than each fetching the catalogue again on every navigation. */}
      {/* THE LEGAL GATE SITS INSIDE THE SHELL, not in front of it. An owner who must accept a
          re-issued privacy notice is not locked out of a product he pays for — he is stopped at
          the content until he answers, with his own nav still around him. Nothing outstanding
          renders nothing at all. */}
      <LegalGate session={session} catalog={catalog}>
        <Outlet context={{ session, catalog, owned, branch: scoped, branches: allowed, setBranch }} />
      </LegalGate>
    </AppShell>
  );
}
