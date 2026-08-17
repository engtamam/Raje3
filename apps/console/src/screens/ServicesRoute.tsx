import type { ShellContext } from '../shell-context';
import { useOutletContext } from 'react-router-dom';
import { ServicesScreen } from './Services';
import type { Catalog } from '../catalog';
import type { Session } from '../session';

export function Services() {
  const { session, catalog } = useOutletContext<ShellContext>();
  return <ServicesScreen session={session} catalog={catalog} />;
}
