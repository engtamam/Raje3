import type { ShellContext } from '../shell-context';
import { useOutletContext } from 'react-router-dom';
import { SupportScreen } from './Support';

export function Support() {
  const { session, catalog } = useOutletContext<ShellContext>();
  return <SupportScreen session={session} catalog={catalog} />;
}
