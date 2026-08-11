import { useOutletContext } from 'react-router-dom';
import { PointsScreen } from './Points';
import type { Catalog } from '../catalog';
import type { Session } from '../session';

export function Points() {
  const { session, catalog } = useOutletContext<{ session: Session; catalog: Catalog }>();
  return <PointsScreen session={session} catalog={catalog} />;
}
