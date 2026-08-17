import type { ShellContext } from '../shell-context';
import { useOutletContext } from 'react-router-dom';
import { LocalScreen } from './Local';

export function Local() {
  // THE BRANCH COMES FROM THE SHELL, which is where the control now lives. A screen that read the
  // stored value itself would be a second reader of the same choice — and the day the two got out
  // of step, the rail would say «الرياض» over numbers about the whole chain.
  const { session, catalog, branch, setBranch } = useOutletContext<ShellContext>();
  return <LocalScreen session={session} catalog={catalog} branch={branch}
                      onBranch={setBranch} />;
}
