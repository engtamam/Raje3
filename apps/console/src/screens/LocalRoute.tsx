import { useOutletContext } from 'react-router-dom';
import { LocalScreen } from './Local';
import type { Catalog } from '../catalog';
import type { Session } from '../session';

export function Local() {
  const { session, catalog } = useOutletContext<{ session: Session; catalog: Catalog }>();
  return <LocalScreen session={session} catalog={catalog} />;
}
