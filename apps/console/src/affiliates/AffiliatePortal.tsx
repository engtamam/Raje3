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
 */
import { useState } from 'react';
import { AffiliateDoor } from './AffiliateDoor';
import { AffiliateHome } from './AffiliateHome';
import { AffiliateLeads } from './AffiliateLeads';
import { AffiliateNav, ComingSoon, type Tab } from './AffiliateNav';
import { useAffiliateSession } from './session';

export function AffiliatePortal() {
  const { session, signedIn, signIn, signOut } = useAffiliateSession();
  const [tab, setTab] = useState<Tab>('home');

  if (!signedIn) {
    return <AffiliateDoor onSignedIn={signIn} />;
  }

  return (
    <div className="mx-auto flex min-h-dvh max-w-lg flex-col">
      <div className="flex-1">
        {tab === 'home' ? <AffiliateHome session={session} onSignOut={signOut} /> : null}
        {tab === 'leads' ? <AffiliateLeads session={session} /> : null}
        {tab === 'tools' ? <ComingSoon label="أدواتي" /> : null}
        {tab === 'earnings' ? <ComingSoon label="أرباحي" /> : null}
        {tab === 'account' ? <ComingSoon label="حسابي" /> : null}
      </div>
      <AffiliateNav active={tab} onChange={setTab} />
    </div>
  );
}
