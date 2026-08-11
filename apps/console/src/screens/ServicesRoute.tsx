import { useOutletContext } from 'react-router-dom';
import { ServicesScreen } from './Services';
import type { Catalog } from '../catalog';
import type { Session } from '../session';

export function Services() {
  const { session, catalog } = useOutletContext<{ session: Session; catalog: Catalog }>();
  return <ServicesScreen session={session} catalog={catalog} />;
}
