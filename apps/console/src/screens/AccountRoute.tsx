import { useOutletContext } from 'react-router-dom';
import { AccountScreen } from './Account';
import type { Catalog } from '../catalog';
import type { Session } from '../session';

export function Account() {
  const { session, catalog } = useOutletContext<{ session: Session; catalog: Catalog }>();
  return <AccountScreen session={session} catalog={catalog} />;
}
