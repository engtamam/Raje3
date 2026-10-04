import type { ShellContext } from '../shell-context';
import { useOutletContext } from 'react-router-dom';
import { ReferralsScreen } from './Referrals';

/**
 * «الإحالة والمسوّقين» — no AppGate here on purpose. Unlike «نقاطي»/«ولاء الشركاء», this program
 * has no entry in apps.ts at all: it is not a purchasable app tier, just a capability
 * (`referrals.manage`/`operations.read`/`operations.affiliates_read`) every section inside the
 * screen already checks with `action()`, same posture as Services.tsx/Customers.tsx.
 */
export function Referrals() {
  const { session, catalog } = useOutletContext<ShellContext>();
  return <ReferralsScreen session={session} catalog={catalog} />;
}
