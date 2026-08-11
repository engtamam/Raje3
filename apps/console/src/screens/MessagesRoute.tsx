import { useOutletContext } from 'react-router-dom';
import { MessagesScreen } from './Messages';
import type { Catalog } from '../catalog';
import type { Session } from '../session';

export function Messages() {
  const { session, catalog } = useOutletContext<{ session: Session; catalog: Catalog }>();
  return <MessagesScreen session={session} catalog={catalog} />;
}
