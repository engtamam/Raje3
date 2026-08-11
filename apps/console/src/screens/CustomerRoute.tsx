import { useOutletContext } from 'react-router-dom';
import { CustomerScreen } from './Customer';
import type { Catalog } from '../catalog';
import type { Session } from '../session';

export function Customer() {
  const { session, catalog } = useOutletContext<{ session: Session; catalog: Catalog }>();
  return <CustomerScreen session={session} catalog={catalog} />;
}
