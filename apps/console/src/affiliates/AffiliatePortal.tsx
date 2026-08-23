/**
 * The affiliate portal's own shell — Door, or a tabbed set of screens once signed in.
 *
 * ONE `useAffiliateSession()` INSTANCE, HELD HERE AND PASSED DOWN — never called a second time
 * inside AffiliateDoor/SignInPane. A hook's state lives in the COMPONENT INSTANCE that calls it,
 * so two separate calls (one here, one in a child) would be two independent copies of "am I
 * signed in": the sign-in pane's copy would update on submit, and this one — the one actually
 * deciding whether to render the door or the home screen — would never hear about it until a full
 * reload re-read localStorage. Passing `signIn`/`session` down instead of re-deriving them is
 * what keeps that decision and that mutation in the same place.
 *
 * THE TAB ITSELF IS NOT PERSISTED — a fresh sign-in (or a reload) always opens on «الرئيسية»,
 * the one screen every role needs first, rather than resuming wherever he last tapped away from.
 *
 * TWO LAYOUTS, ONE MARKUP, PICKED BY CSS (2026-08-22): below `md` this column is content-then-
 * bottom-bar (`flex-col`); at `md` and up it becomes sidebar-then-content (`md:flex-row`), and the
 * RTL document flips a row's visual order on its own — so the sidebar, placed FIRST here, lands on
 * the start (right) edge exactly where the shop console's own `AppShell` puts its rail. See
 * `AffiliateNav.tsx`'s own header on why a phone gets a bottom bar rather than that shell's
 * off-canvas drawer.
 */
import { useState } from 'react';
import type { HomeTicket } from './api';
import { AffiliateAccount } from './AffiliateAccount';
import { AffiliateDoor } from './AffiliateDoor';
import { AffiliateEarnings } from './AffiliateEarnings';
import { AffiliateHome } from './AffiliateHome';
import { AffiliateLeads } from './AffiliateLeads';
import { AffiliateSidebar, AffiliateBottomNav, ComingSoon, type Tab } from './AffiliateNav';
import { AffiliateTools } from './AffiliateTools';
import { useAffiliateSession } from './session';

export function AffiliatePortal() {
  const { session, signedIn, signIn, signOut } = useAffiliateSession();
  const [tab, setTab] = useState<Tab>('home');
  // Home's own TicketCarousel jumps straight into a ticket's own thread inside «أدواتي» — this is
  // the one piece of state that crosses tabs, so it lives here rather than in either screen.
  const [deepLinkTicket, setDeepLinkTicket] = useState<HomeTicket | null>(null);

  if (!signedIn) {
    return <AffiliateDoor onSignedIn={signIn} />;
  }

  return (
    <div className="flex min-h-dvh flex-col md:flex-row">
      <AffiliateSidebar active={tab} onChange={setTab} />
      <div className="mx-auto flex w-full max-w-lg flex-1 flex-col md:max-w-2xl">
        <div className="flex-1">
          {tab === 'home' ? (
            <AffiliateHome session={session}
                          onOpenTicket={(t) => { setDeepLinkTicket(t); setTab('tools'); }} />
          ) : null}
          {tab === 'leads' ? <AffiliateLeads session={session} /> : null}
          {tab === 'tools' ? (
            <AffiliateTools session={session} deepLinkTicket={deepLinkTicket}
                           onConsumeDeepLinkTicket={() => setDeepLinkTicket(null)} />
          ) : null}
          {tab === 'earnings' ? <AffiliateEarnings session={session} /> : null}
          {tab === 'account' ? <AffiliateAccount session={session} onSignOut={signOut} /> : null}
        </div>
        <AffiliateBottomNav active={tab} onChange={setTab} />
      </div>
    </div>
  );
}
