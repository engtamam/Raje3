import type { ShellContext } from '../shell-context';
import { useOutletContext } from 'react-router-dom';
import { CustomersScreen } from './Customers';
import type { Catalog } from '../catalog';
import type { Session } from '../session';

export function Customers() {
  const { session, catalog, branch } = useOutletContext<ShellContext>();
  return <CustomersScreen session={session} catalog={catalog} branch={branch} />;
}
