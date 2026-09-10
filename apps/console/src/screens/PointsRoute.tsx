import type { ShellContext } from '../shell-context';
import { useOutletContext } from 'react-router-dom';
import { PointsScreen } from './Points';
import { AppGate } from './Locked';
import { type Loading } from '../loading';
import type { Owned } from '../apps';
import type { Catalog } from '../catalog';
import type { Session } from '../session';

/**
 * THE WHOLE SECTION IS THE APP HERE, unlike «رسائلي» where only one tab is.
 *
 * «نقاطي» is the programme itself — the rewards he sells and the rules that earn them — so a shop
 * without the app has nothing on this screen but the offer to buy it.
 *
 * AND IT HIDES NOTHING HE EARNED. Customer balances are not here; they are on the customer's page
 * and on his own, and both keep showing them when the app lapses. The services enforce the same
 * split: earning and editing stop, reading and redeeming never do.
 */
export function Points() {
  const { session, catalog, owned } =
    useOutletContext<ShellContext>();
  return (
    <AppGate appId="loyalty" owned={owned} session={session} catalog={catalog}>
      <PointsScreen session={session} catalog={catalog} />
    </AppGate>
  );
}
