import { useOutletContext, useSearchParams } from 'react-router-dom';
import { AccountScreen, type Pane } from './Account';
import type { Catalog } from '../catalog';
import type { Session } from '../session';

const PANES = ['billing', 'invoices', 'whatsapp', 'shop', 'keys', 'login', 'data'] as const;

export function Account() {
  const { session, catalog } = useOutletContext<{ session: Session; catalog: Catalog }>();
  const [params] = useSearchParams();
  // VALIDATED AGAINST THE LIST, never passed through. `?tab=` comes from a URL anybody can type,
  // and an unknown value would leave the screen on a tab that does not exist — a blank page
  // reached from a button that promised a purchase.
  const asked = params.get('tab') ?? '';
  const openOn = (PANES as readonly string[]).includes(asked) ? (asked as Pane) : undefined;
  return <AccountScreen session={session} catalog={catalog} openOn={openOn} />;
}
