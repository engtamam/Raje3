import type { ShellContext } from '../shell-context';
import { useOutletContext } from 'react-router-dom';
import { ReferralPartnershipScreen } from './ReferralPartnership';
import { AppGate } from './Locked';

/** «شراكة استراتيجية» — the whole section is the app here, same posture as «تحالف استراتيجي». */
export function ReferralPartnership() {
  const { session, catalog, owned } = useOutletContext<ShellContext>();
  return (
    <AppGate appId="referral-partnership" owned={owned} session={session} catalog={catalog}>
      <ReferralPartnershipScreen session={session} catalog={catalog} />
    </AppGate>
  );
}
