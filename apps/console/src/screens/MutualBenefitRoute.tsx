import type { ShellContext } from '../shell-context';
import { useOutletContext } from 'react-router-dom';
import { MutualBenefitScreen } from './MutualBenefit';
import { AppGate } from './Locked';

/** «تبادل منافع» — the whole section is the app here, same posture as «تحالف استراتيجي». */
export function MutualBenefit() {
  const { session, catalog, owned } = useOutletContext<ShellContext>();
  return (
    <AppGate appId="mutual-benefit" owned={owned} session={session} catalog={catalog}>
      <MutualBenefitScreen session={session} catalog={catalog} />
    </AppGate>
  );
}
