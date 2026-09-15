import type { ShellContext } from '../shell-context';
import { useOutletContext } from 'react-router-dom';
import { MobileRequestsScreen } from './MobileRequests';

/** «خدمات متنقلة» — operational, capability-gated only (same shape as «الفريق»), not an AppGate
 *  section: not a sold app yet (see [[task-mobile-service-requests-phases]] — phase 4, listing it
 *  in the app store, has not started), reachable to whichever role holds
 *  operations.mobile_requests_manage the moment the nav row (nav.ts) offers it. */
export function MobileRequests() {
  const { session, catalog } = useOutletContext<ShellContext>();
  return <MobileRequestsScreen session={session} catalog={catalog} />;
}
