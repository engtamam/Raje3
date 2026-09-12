import type { ShellContext } from '../shell-context';
import { useOutletContext } from 'react-router-dom';
import { RatingScreen } from './Rating';
import { AppGate } from './Locked';

/**
 * «التقييم» — the whole section is the app here, same as «نقاطي»/«الحجوزات»: a shop that has not
 * bought the rating app sees only its own locked card, upgrade-flow and all (see subscribeFlow.ts).
 */
export function Rating() {
  const { session, catalog, owned, branch } = useOutletContext<ShellContext>();
  return (
    <AppGate appId="rating" owned={owned} session={session} catalog={catalog}>
      <RatingScreen session={session} catalog={catalog} branch={branch} />
    </AppGate>
  );
}
