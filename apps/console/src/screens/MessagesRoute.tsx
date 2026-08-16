import { useOutletContext } from 'react-router-dom';
import { MessagesScreen } from './Messages';
import { type Loading } from '../loading';
import type { Owned } from '../apps';
import type { Catalog } from '../catalog';
import type { Session } from '../session';

export function Messages() {
  // `owned` ALONGSIDE THE CATALOGUE, never instead of it: the catalogue says what this PERSON may
  // do and `owned` says what the SHOP bought. «رسائلي» needs both — the reasons table is the base
  // and belongs to every subscriber, and only the campaigns tab is an app he buys.
  const { session, catalog, owned } =
    useOutletContext<{ session: Session; catalog: Catalog; owned: Loading<Owned> }>();
  return <MessagesScreen session={session} catalog={catalog} owned={owned} />;
}
