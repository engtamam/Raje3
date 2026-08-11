import { useOutletContext } from 'react-router-dom';
import { TeamScreen } from './Team';
import type { Catalog } from '../catalog';
import type { Session } from '../session';

export function Team() {
  const { session, catalog } = useOutletContext<{ session: Session; catalog: Catalog }>();
  return <TeamScreen session={session} catalog={catalog} />;
}
