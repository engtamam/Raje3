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

import { baseState, daysLeft, type Owned } from './apps';
import type { Loading } from './loading';
import { STORE_PATH } from './nav';

/** Below this the trial is a countdown worth showing; above it, it is just «مشترك». */
const SOON_DAYS = 7;

export function SubscriptionBar({ owned, now }: { owned: Loading<Owned>; now: number }) {
  const state = baseState(owned);
  const left = daysLeft(owned, now);

  // NOTHING TO SAY, AND SAYING NOTHING IS THE ANSWER. `unknown` is billing unread; `none` is a
  // shop that never activated — the app store already puts «فعّل الأساس» in front of him and a
  // second banner over it would be nagging; `active` with time left is the ordinary case.
  if (state === 'unknown' || state === 'none') return null;
  if (state === 'active' && (left === null || left > SOON_DAYS)) return null;
  if (state === 'trial' && left !== null && left > SOON_DAYS) return null;

  const lapsed = state === 'lapsed';
  const text = lapsed
    ? 'انتهى اشتراكك — بياناتك محفوظة وتقدر تتصفّحها، وتسجيل الزيارات يرجع فور التجديد.'
    : state === 'trial'
      ? `تجربتك المجانية تنتهي بعد ${left} ${left === 1 ? 'يوم' : 'أيام'} — فعّل الأساس ويكمل شغلك بلا انقطاع.`
      : `اشتراكك يتجدّد بعد ${left} ${left === 1 ? 'يوم' : 'أيام'}.`;

  return (
    <div
      role="status"
      className={`flex flex-wrap items-center justify-between gap-2 rounded-card px-4 py-2 text-sm ${
        lapsed ? 'bg-danger/10 text-danger' : 'bg-surface-2 text-text-secondary'
      }`}
    >
      <span>{text}</span>
      {/* THE ACTION IS THE SAME ONE, ALWAYS. Tamam: «نفس الزر فعّل الأساس أو أضِف — كلها نفسها
          للاشتراك الفعلي أو فترة التجربة». So this points at the store rather than growing a
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
