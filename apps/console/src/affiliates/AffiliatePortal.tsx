/**
 * The affiliate portal's own tiny shell — Door, or Home. No AppShell, no nav, no catalogue: the
 * dashboard, commission and lead screens are later slices (spec §14's own table); today this is
 * just enough surface to sign in, apply, accept an invite, and — if signed in as a manager —
 * invite one more person onto the team.
 *
 * ONE `useAffiliateSession()` INSTANCE, HELD HERE AND PASSED DOWN — never called a second time
 * inside AffiliateDoor/SignInPane. A hook's state lives in the COMPONENT INSTANCE that calls it,
 * so two separate calls (one here, one in a child) would be two independent copies of "am I
 * signed in": the sign-in pane's copy would update on submit, and this one — the one actually
 * deciding whether to render the door or the home screen — would never hear about it until a full
 * reload re-read localStorage. Passing `signIn`/`session` down instead of re-deriving them is
 * what keeps that decision and that mutation in the same place.
 */
import { AffiliateDoor } from './AffiliateDoor';
import { AffiliateHome } from './AffiliateHome';
import { useAffiliateSession } from './session';

export function AffiliatePortal() {
  const { session, signedIn, signIn, signOut } = useAffiliateSession();

  if (!signedIn) {
    return <AffiliateDoor onSignedIn={signIn} />;
  }
  return <AffiliateHome session={session} onSignOut={signOut} />;
}
