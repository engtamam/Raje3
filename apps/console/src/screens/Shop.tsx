/**
 * «محلّي» — ONE PAGE, where there were two.
 *
 * «اليوم» AND «محلّي» WERE THE SAME VISIT, SPLIT IN HALF. He opened «اليوم», read three tiles,
 * and pressed «محلّي» to see the number he pays us for — every time. Two rows in the rail, two
 * loads, and a duplicated freshness caption between them. Tamam's own words: «افكر ادمج صفحة
 * اليوم مع محلي في صفحة وحده وخلاص، نقلل من التكرارات».
 *
 * THE ORDER IS THE ARGUMENT, and it is not the order we built things in:
 *
 *   1. what STOPS the shop — «رسائلك متوقّفة». Rare, and above everything when it is true.
 *   2. نسبة العودة, large. The one number this product is about, and the first thing he sees.
 *   3. the numbers around it — his three indicators, then what our messages moved and cost.
 *   4. what he might DO — a heading drawn only when there is something under it.
 *   5. detail, folded. Pairs, branches, and what is still too thin to show honestly.
 *   6. آخر الزيارات, LAST — «خليها اخر شي»: reassurance, not a decision.
 *
 * WHY THE PAGE IS ASSEMBLED HERE RATHER THAN MERGED INTO ONE COMPONENT: the two halves fail
 * independently. `reminders` can be unreachable while `insights` answers perfectly — and the
 * merged version of that is a page that throws away a working retention rate because a different
 * service is down. Each piece keeps its own three states, and each says its own sentence.
 */
import type { ShellContext } from '../shell-context';
import { useOutletContext } from 'react-router-dom';
import { LocalScreen } from './Local';
import { RecentVisits, TodayStrip } from './Today';

export function ShopScreen() {
  // THE BRANCH COMES FROM THE SHELL, which is where the control now lives. A screen that read the
  // stored value itself would be a second reader of the same choice — and the day the two got out
  // of step, the rail would say «الرياض» over numbers about the whole chain.
  const { session, catalog, branch, setBranch } = useOutletContext<ShellContext>();
  return (
    <div className="flex flex-col gap-4 p-4">
      <TodayStrip session={session} catalog={catalog} />
      <LocalScreen session={session} catalog={catalog} branch={branch} onBranch={setBranch} />
      <RecentVisits session={session} catalog={catalog} />
    </div>
  );
}
