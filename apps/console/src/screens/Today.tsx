/**
 * WHAT «اليوم» LEFT BEHIND — two pieces, and no longer a page of its own.
 *
 * IT WAS A SCREEN, AND IT HELD HALF A SCREEN'S WORTH OF CONTENT. Three tiles and a short list, on
 * its own row in the rail, one press away from «محلّي» — which the owner opened straight after,
 * every time, to read the number he actually pays us for. Two rows, two loads, one glance's worth
 * of information between them.
 *
 * So it folds into «محلّي» (Shop.tsx), split by URGENCY rather than by subject:
 *
 *   TodayStrip    what is running RIGHT NOW, and what stops when it is not. Near the top, because
 *                 a shop whose messages are dead must learn that before it reads any rate.
 *   RecentVisits  reassurance rather than a decision — «we are still recording». It goes LAST, by
 *                 Tamam's own reading of the page: it is what he looks at least.
 *
 * The question these answer is still «is everything running», and neither of them invites study.
 */
import { hasFailed, isLoading } from '../loading';
import { useEffect, useState } from 'react';
// The icons the shell already depends on — no second icon set, and no bespoke SVG for a card.
import { Clock, Send, Signal } from 'lucide-react';
import { KpiCard } from '@base-ui/design-system/KpiCard';
import { EmptyState } from '@base-ui/design-system/EmptyState';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';
import { asLocal } from '../phone';

interface Today {
  /** Whether anything can go out at all. False is a stop, not a warning. */
  can_send?: boolean;
  /** The service's own sentence for why nothing can go out — shown whole, never re-worded. */
  blocked?: string;
  messages: {
    sent_today: number;
    /** CALMLY WAITING ONLY. The service tells this apart from a message that keeps failing, and
     *  the two used to arrive added together — so a shop whose every message was failing read a
     *  perfectly ordinary «12 بانتظار الإرسال». */
    waiting: number;
    /** HOW MANY ARE TRYING AND NOT SUCCEEDING. Optional because a console can be newer than the
     *  service it talks to, and `undefined` must not render as «0 متعثّرة» — that is the same
     *  lie as the one this field exists to end, pointed the other way. */
    retrying?: number;
    /** The service's own sentence for what that means. Shown whole, never re-worded. */
    retrying_reason?: string;
  };
  ceiling: {
    known: boolean;
    unlimited: boolean;
    limit: number;
    reached_today: number;
    remaining: number;
    quality: string;
  };
}

interface CustomerRow { id: string; phone: string; name?: string }

/**
 * WHAT IS RUNNING TODAY — the stop, the warning, and three numbers.
 *
 * THREE STATES, NOT TWO — and collapsing them is the bug this screen shipped with.
 *
 * `undefined` is loading, `null` is a read that FAILED, and a value is a value. It was written
 * with `null` for both, and `if (!today)` painted the loading skeleton: so a failed read looked
 * exactly like a slow one, for ever. Grey boxes that never resolve, nothing in the console,
 * nothing on the screen — and the owner concludes the product is broken, which is nearly right
 * and completely unactionable.
 */
export function TodayStrip({ session, catalog }: { session: Session; catalog: Catalog }) {
  const [today, setToday] = useState<Today | null | undefined>(undefined);
  const [connected, setConnected] = useState<{ state: string; message: string; can_send?: boolean } | null | undefined>(undefined);

  useEffect(() => {
    const a = action(catalog, 'reminders.today');
    // AN ABSENT ACTION IS A FAILURE HERE, not a wait. The nav only offers this section when the
    // action exists, so arriving without it means the catalogue changed under us — and spinning
    // for ever is the one response that tells him nothing.
    if (a) {
      call<Today>(session, a).then(setToday).catch(() => setToday(null));
    } else {
      setToday(null);
    }

    const w = action(catalog, 'whatsapp.connect_status');
    if (w) {
      call<{ state: string; message: string; can_send?: boolean }>(session, w)
        .then(setConnected).catch(() => {});
    }
  }, [session, catalog]);

  /**
   * THE WARNING LINE, AND ITS ONE RULE: it appears when there is something the OWNER can do.
   *
   * A failure of ours is not announced here. He can do nothing about it, and saying so makes the
   * screen look broken every time he opens it — which teaches him to stop reading the one line
   * that will matter on the day it is his to fix.
   */
  const warning = (() => {
    if (connected && connected.state !== 'connected' && connected.state !== '') {
      return connected.message;
    }
    if (connected && connected.state === '') {
      return 'واتساب غير مربوط — اربطه لتبدأ الرسائل. دقائق.';
    }
    // CONNECTED AND MUTE, WITH SOMETHING HE CAN DO — which is exactly why it belongs on this line
    // now and did not before. The number is not registered with Meta until his own two-step PIN is
    // entered (error 133010), and until then not one message is attempted. This screen stayed
    // silent through it: its check was «state !== connected», and the state IS connected.
    if (connected && connected.can_send === false) {
      return 'واتساب مربوط ولم يبدأ الإرسال — أدخل رمز التحقق بخطوتين في «حسابي» لتفعيله.';
    }
    if (today?.ceiling.known && !today.ceiling.unlimited && today.ceiling.remaining <= 0) {
      return 'بلغت سقف واتساب اليوم. الرسائل المتبقية ستُرسل غداً تلقائياً.';
    }
    return '';
  })();

  // A FAILED READ IS A LINE, NOT A PAGE. It used to replace the whole screen with «تعذّر تحميل
  // شاشة اليوم» — which, now that the indicators live on the same page, would have thrown away a
  // working retention rate because a different service was briefly unreachable.
  if (today === null) {
    return (
      <p className="rounded-card bg-surface-1 px-4 py-3 text-sm text-text-secondary shadow-sm">
        تعذّرت قراءة حالة اليوم — حسابك سليم، والأرقام أدناه صحيحة.
      </p>
    );
  }

  if (today === undefined) {
    return (
      <div className="grid gap-3 sm:grid-cols-3">
        <Skeleton height={88} /><Skeleton height={88} /><Skeleton height={88} />
      </div>
    );
  }

  return (
    <>
      {/* ── THE STOP, ABOVE EVERYTHING ────────────────────────────────────────────────────
          NOT AMBER. Amber is «something needs attention soon»; this is «nothing you record today
          reaches anybody», which the screen used to render as a perfectly calm «0 خرجت · 3
          بانتظار» — three tiles that describe a working shop. A day of real visits went past on
          that screen and the owner concluded the product was fine.

          IT NAMES THE REPAIR, NOT THE FAULT. He does not care which field a peer omits; he cares
          that his name is missing and that one screen fixes it. */}
      {today.blocked ? (
        <div className="flex flex-col gap-2 rounded-card border border-danger bg-danger/10 px-4 py-3">
          <span className="font-semibold text-danger">رسائلك متوقّفة</span>
          <span className="text-sm">{today.blocked}</span>
          <a href="/app/account" className="text-sm font-medium text-accent-on-soft underline">
            افتح «حسابي»
          </a>
        </div>
      ) : null}

      {/* ── TRYING AND NOT SUCCEEDING ────────────────────────────────────────────────────
          THE NUMBER THE SERVICE LEARNED AND THE SCREEN DID NOT SAY. `pending` holds two states:
          a reminder booked for next Tuesday, and a message that has thrown eleven times and is
          being retried hourly until it is given up on. They used to arrive added together under
          «بانتظار الإرسال», so a shop whose every message was failing read a calm queue.

          AMBER, NOT RED. Red is «nothing you record today reaches anybody» — the stop above. This
          is «some messages are struggling and we are still trying», which resolves itself when a
          peer comes back and does not when the content is wrong. The service's own sentence says
          which, and where he will find them if it does not.

          `> 0` RATHER THAN TRUTHINESS, and the count is optional: a console newer than its
          service reads `undefined`, and «0 متعثّرة» about a shop with none is the same kind of
          invented certainty the rest of this screen refuses. */}
      {/* ── TRYING AND NOT SUCCEEDING ────────────────────────────────────────────────────
          THE NUMBER THE SERVICE LEARNED AND THE SCREEN DID NOT SAY. `pending` holds two states:
          a reminder booked for next Tuesday, and a message that has thrown eleven times and is
          being retried hourly until it is given up on. They used to arrive added together under
          «بانتظار الإرسال», so a shop whose every message was failing read a calm queue.

          AMBER, NOT RED. Red is «nothing you record today reaches anybody» — the stop above. This
          is «some messages are struggling and we are still trying», which resolves itself when a
          peer comes back and does not when the content is wrong. The service's own sentence says
          which, and where he will find them if it does not.

          `> 0` RATHER THAN TRUTHINESS, and the count is optional: a console newer than its
          service reads `undefined`, and «0 متعثّرة» about a shop with none is the same kind of
          invented certainty the rest of this screen refuses. */}
      {(today.messages.retrying ?? 0) > 0 ? (
        <div className="flex flex-col gap-1 rounded-card border border-warning bg-warning-soft px-4 py-3 text-warning-on-soft">
          <span className="font-semibold">{today.messages.retrying} رسالة تحاول الخروج</span>
          {today.messages.retrying_reason ? (
            <span className="text-sm">{today.messages.retrying_reason}</span>
          ) : null}
        </div>
      ) : null}

      {warning ? (
        // Amber, and only amber, because the palette reserves it for "something needs attention
        // soon" — the kit's own comment forbids using it for anything else.
        <div className="rounded-card border border-warning bg-warning-soft px-4 py-3 text-warning-on-soft">
          {warning}
        </div>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-3">
        <KpiCard icon={<Send size={18} />} label="رسائل خرجت اليوم" value={String(today.messages.sent_today)} />
        <KpiCard icon={<Clock size={18} />} label="بانتظار الإرسال" value={String(today.messages.waiting)} />
        <KpiCard
          icon={<Signal size={18} />}
          label="سقفك المتبقي اليوم"
          // UNKNOWN IS NOT ZERO, AND ZERO IS NOT UNKNOWN. A ceiling we could not read rendered as
          // "0" tells the owner he may message nobody, which is the opposite of what an unreadable
          // answer means — and he would stop sending on our mistake.
          value={
            !today.ceiling.known ? '—'
              : today.ceiling.unlimited ? 'بلا حدّ'
                : String(today.ceiling.remaining)
          }
          tone={
            !today.ceiling.known || today.ceiling.unlimited ? 'neutral'
              : today.ceiling.remaining <= 0 ? 'warning' : 'accent'
          }
        />
      </div>
    </>
  );
}

/** «آخر الزيارات» — the last thing on the page, because it is the last thing he looks at. */
export function RecentVisits({ session, catalog }: { session: Session; catalog: Catalog }) {
  const [recent, setRecent] = useState<CustomerRow[] | null | undefined>(undefined);

  useEffect(() => {
    const r = action(catalog, 'operations.recent');
    if (!r) { setRecent(null); return; }
    call<{ customers: CustomerRow[] }>(session, r, { limit: 5 })
      .then((x) => setRecent(x.customers))
      .catch(() => setRecent(null));
  }, [session, catalog]);

  return (
    <section className="rounded-card bg-surface-1 p-4 shadow-sm">
      <h2 className="mb-3 text-sm text-text-secondary">آخر الزيارات</h2>
      {isLoading(recent) ? (
        <Skeleton height={64} />
      ) : hasFailed(recent) ? (
        // «لم تُسجَّل زيارة بعد» TO A SHOP THAT HAS BEEN BUSY ALL MORNING reads as «the system
        // stopped recording» — which is the one fear this section exists to answer.
        <EmptyState
          title="تعذّرت قراءة آخر الزيارات"
          description="والخلل عندنا — الزيارات محفوظة. أعد المحاولة بعد قليل."
        />
      ) : recent.length === 0 ? (
        // "لم تُسجَّل زيارة بعد" AND NEVER A ZERO. A zero in this place reads as a fault — the
        // shop wonders whether the system stopped recording rather than whether anyone came in.
        <EmptyState
          title="لم تُسجَّل زيارة بعد"
          description="سجّل أول زيارة من «تسجيل زيارة»."
        />
      ) : (
        <ul className="flex flex-col gap-2">
          {recent.map((c) => (
            <li key={c.id} className="flex items-center justify-between text-sm">
              <span dir="ltr" className="tabular-nums">{asLocal(c.phone)}</span>
              <span className="text-text-secondary">{c.name || '—'}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
