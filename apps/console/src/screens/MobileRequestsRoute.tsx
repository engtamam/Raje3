import type { ShellContext } from '../shell-context';
import { useOutletContext } from 'react-router-dom';
import { MobileRequestsScreen } from './MobileRequests';
import { AppGate } from './Locked';

/** «خدمات متنقلة» — Phase 4 (2026-09-15): now a real sold app (feature.mobile_requests,
 *  deploy/seed/plans.json), the same shape as «كوبونات»/«التقييم» — a shop that has not bought it
 *  sees only its own locked card, upgrade-flow and all. */
export function MobileRequests() {
  const { session, catalog, owned } = useOutletContext<ShellContext>();
  return (
    <AppGate appId="mobile-requests" owned={owned} session={session} catalog={catalog}>
      <MobileRequestsScreen session={session} catalog={catalog} />
    </AppGate>
  );
}
