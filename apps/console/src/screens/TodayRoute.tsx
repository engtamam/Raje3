// The route wrapper: takes what the shell already loaded and hands it to the screen.
//
// SEPARATE FROM THE SCREEN so the screen stays a pure function of (session, catalogue) and can be
// tested without a router — the same reason every screen here takes its data as props.
import { useOutletContext } from 'react-router-dom';
import { TodayScreen } from './Today';
import type { Catalog } from '../catalog';
import type { Session } from '../session';

export function Today() {
  const { session, catalog } = useOutletContext<{ session: Session; catalog: Catalog }>();
  return <TodayScreen session={session} catalog={catalog} />;
}
