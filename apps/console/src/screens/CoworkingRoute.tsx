import type { ShellContext } from '../shell-context';
import { useOutletContext } from 'react-router-dom';
import { CoworkingScreen } from './Coworking';

export function Coworking() {
  const { session, catalog, branch } = useOutletContext<ShellContext>();
  return <CoworkingScreen session={session} catalog={catalog} branch={branch} />;
}
