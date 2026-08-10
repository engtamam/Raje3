import { useOutletContext } from 'react-router-dom';
import { CustomersScreen } from './Customers';
import type { Catalog } from '../catalog';
import type { Session } from '../session';

export function Customers() {
  const { session, catalog } = useOutletContext<{ session: Session; catalog: Catalog }>();
  return <CustomersScreen session={session} catalog={catalog} />;
}
