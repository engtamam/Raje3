import type { ShellContext } from '../shell-context';
import { useOutletContext } from 'react-router-dom';
import { FreelancersScreen } from './Freelancers';
import { AppGate } from './Locked';

/** «خدمات ما بعد البيع» — the whole section is the app here, same posture as «تبادل منافع». */
export function Freelancers() {
  const { session, catalog, owned } = useOutletContext<ShellContext>();
  return (
    <AppGate appId="freelancers" owned={owned} session={session} catalog={catalog}>
      <FreelancersScreen session={session} catalog={catalog} />
    </AppGate>
  );
}
