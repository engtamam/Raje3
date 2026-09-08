/**
 * One line above every screen when the month is running out, or has run out.
 *
 * WHY A BAR AND NOT A REFUSAL. operations and reminders now answer 402 on every write once the
 * base lapses, and 402 arrives when he PRESSES — after he has typed a customer's name, chosen a
 * service and reached for save. Learning that the month ended at the moment the work is thrown
 * away is the worst possible order, and it is the order we shipped the backend in. This says it
 * before the first press.
 *
 * IT SAYS WHAT STILL WORKS. «انتهى» alone leaves an owner wondering whether his customers went
 * with it; they did not, and the sentence has to carry that or he calls us instead of renewing.
 *
 * AND IT IS SILENT WHEN THE ANSWER IS UNKNOWN. While billing has not replied, or could not be
 * asked, no bar: telling a paying shop its subscription ended is worse than telling it nothing.
 * The same three-answer rule the locks and the app store already obey.
 */
import { Link } from 'react-router-dom';

import { baseState, daysLeft, relevantSubscription, type Owned } from './apps';
import type { Loading } from './loading';
import { STORE_PATH } from './nav';

/** Below this the trial is a countdown worth showing; above it, it is just «مشترك». */
const SOON_DAYS = 7;

export function SubscriptionBar({ owned, now }: { owned: Loading<Owned>; now: number }) {
  const state = baseState(owned);
  const left = daysLeft(owned, now);

  // `unknown` STAYS SILENT — billing unread. `none` USED TO MEAN THE SAME («nothing to say» —
  // no base, so nothing running out) but a shop with no base at all can still hold a STANDALONE
  // app bought on its own (تسجيل زيارة), and ITS renewal is what is actually ending for him —
  // handled just below rather than assumed away. جهات الاتصال never surfaces here: it is free
  // and subscribed `interval='once'`, so it never carries a `renews_at` and never wins the search
  // in `relevantSubscription` — no special case needed for it.
  if (state === 'unknown') return null;
  if (state === 'none') {
    const sub = relevantSubscription(owned);
    if (!sub) return null;                                    // nothing bought stand-alone either
    const secondsLeft = sub.renewsAt - Math.floor(now / 1000);
    const appLeft = secondsLeft > 0 ? Math.ceil(secondsLeft / 86400) : null;
    // NO «انتهى» BANNER HERE — unlike the base, a standalone app's row in `Owned` carries no
    // status, so a date in the past could mean lapsed or simply unread; claiming it ended on a
    // guess would be the exact wrong-sentence failure this file exists to avoid. Silence is safe.
    if (appLeft === null || appLeft > SOON_DAYS) return null;
    return (
      <div role="status"
           className="flex flex-wrap items-center justify-between gap-2 rounded-card px-4 py-2 text-sm bg-surface-2 text-text-secondary">
        <span>{`اشتراكك في ${sub.name} يتجدّد بعد ${appLeft} ${appLeft === 1 ? 'يوم' : 'أيام'}.`}</span>
        <Link to={STORE_PATH} className="font-medium underline underline-offset-4">متجر التطبيقات</Link>
      </div>
    );
  }
  if (state === 'active' && (left === null || left > SOON_DAYS)) return null;
  if (state === 'trial' && left !== null && left > SOON_DAYS) return null;

  // NAMED FROM THE DATA, NOT SPELLED HERE — `relevantSubscription` answers الأساس's own name
  // whenever `owned.base` exists, which it does in every branch reached below; a renamed or
  // second base tier tomorrow needs no edit to this file.
  const subName = relevantSubscription(owned)?.name ?? 'الأساس';
  const lapsed = state === 'lapsed';
  const text = lapsed
    ? 'انتهى اشتراكك — بياناتك محفوظة وتقدر تتصفّحها، وتسجيل الزيارات يرجع فور التجديد.'
    : state === 'trial'
      ? `تجربتك المجانية تنتهي بعد ${left} ${left === 1 ? 'يوم' : 'أيام'} — فعّل ${subName} ويكمل شغلك بلا انقطاع.`
      : `اشتراكك يتجدّد بعد ${left} ${left === 1 ? 'يوم' : 'أيام'}.`;

  return (
    <div
      role="status"
      className={`flex flex-wrap items-center justify-between gap-2 rounded-card px-4 py-2 text-sm ${
        lapsed ? 'bg-danger/10 text-danger' : 'bg-surface-2 text-text-secondary'
      }`}
    >
      <span>{text}</span>
      {/* THE ACTION IS THE SAME ONE, ALWAYS: نفس الزر فعّل الأساس أو أضِف — كلها نفسها
          للاشتراك الفعلي أو فترة التجربة. So this points at the store rather than growing a
          second activation path that would have to be kept in step with the first. */}
      {/* THE ADDRESS IS NAMED, NEVER SPELLED. `STORE_PATH` is where «متجر التطبيقات» lives, and
          #368 settled that name after the product carried two of them — a tab called «اشتراكي»
          and four screens pointing at «متجر التطبيقات», one of which existed. A literal here
          would be the third. */}
      <Link to={STORE_PATH} className="font-medium underline underline-offset-4">
        {lapsed ? 'جدّد الآن' : 'متجر التطبيقات'}
      </Link>
    </div>
  );
}
