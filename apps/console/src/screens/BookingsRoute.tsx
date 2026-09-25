import type { ShellContext } from '../shell-context';
import { useOutletContext } from 'react-router-dom';
import { BookingsScreen } from './Bookings';
import { AppGate } from './Locked';

/**
 * Bookings — a whole section gated by the app, same as "My Points". A shop that hasn't bought
 * the bookings system sees only the upgrade card here; nothing is lost on "Record Visit" or "My
 * Customers" — the same rule every app follows.
 */
export function Bookings() {
  const { session, catalog, owned, branch, branches, setBranch } = useOutletContext<ShellContext>();
  return (
    <AppGate appId="bookings" owned={owned} session={session} catalog={catalog}>
      <BookingsScreen session={session} catalog={catalog} branch={branch} branches={branches} onBranch={setBranch} />
    </AppGate>
  );
}
