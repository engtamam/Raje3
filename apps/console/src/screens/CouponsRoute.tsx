import type { ShellContext } from '../shell-context';
import { useOutletContext } from 'react-router-dom';
import { CouponsScreen } from './Coupons';
import { AppGate } from './Locked';

/** «كوبونات» — the whole section is the app here, same posture as «التقييم»/«نقاطي». */
export function Coupons() {
  const { session, catalog, owned } = useOutletContext<ShellContext>();
  return (
    <AppGate appId="coupons" owned={owned} session={session} catalog={catalog}>
      <CouponsScreen session={session} catalog={catalog} />
    </AppGate>
  );
}
