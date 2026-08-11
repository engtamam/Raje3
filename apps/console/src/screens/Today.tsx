/**
 * «اليوم» — the screen the product opens on, every day.
 *
 * THE QUESTION IT ANSWERS IS NOT "how much did I sell" BUT "is everything running". That single
 * choice decides everything below: a number that cannot be acted on today does not belong here,
 * and every indicator that invites study belongs in «محلّي», which is read once a week.
 *
 * AND IT IS WHY THE PRODUCT OPENS HERE RATHER THAN ON THE INDICATORS, even though the indicators
 * are what the top plan is bought for. A shop in its first week has nothing to show there —
 * opening a paid product onto "not enough data yet" is the worst first impression available, while
 * this screen works from the first visit.
 */
import { useEffect, useState } from 'react';
// The icons the shell already depends on — no second icon set, and no bespoke SVG for a card.
import { Clock, Send, Signal } from 'lucide-react';
import { KpiCard } from '@base-ui/design-system/KpiCard';
import { EmptyState } from '@base-ui/design-system/EmptyState';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';

interface Today {
  messages: { sent_today: number; waiting: number };
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

export function TodayScreen({ session, catalog }: { session: Session; catalog: Catalog }) {
  /**
   * THREE STATES, NOT TWO — and collapsing them is the bug this screen shipped with.
   *
   * `undefined` is loading, `null` is a read that FAILED, and a value is a value. It was written
   * with `null` for both, and `if (!today)` painted the loading skeleton: so a failed read looked
   * exactly like a slow one, for ever. Grey boxes that never resolve, nothing in the console,
   * nothing on the screen — and the owner concludes the product is broken, which is nearly right
   * and completely unactionable.
   */
  const [today, setToday] = useState<Today | null | undefined>(undefined);
  const [recent, setRecent] = useState<CustomerRow[] | null>(null);
  const [connected, setConnected] = useState<{ state: string; message: string } | null>(null);

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

    const r = action(catalog, 'operations.recent');
    if (r) {
      call<{ customers: CustomerRow[] }>(session, r, { limit: 5 })
        .then((x) => setRecent(x.customers))
        .catch(() => setRecent([]));
    }

    const w = action(catalog, 'whatsapp.connect_status');
    if (w) call<{ state: string; message: string }>(session, w).then(setConnected).catch(() => {});
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
    if (today?.ceiling.known && !today.ceiling.unlimited && today.ceiling.remaining <= 0) {
      return 'بلغت سقف واتساب اليوم. الرسائل المتبقية ستُرسل غداً تلقائياً.';
    }
    return '';
  })();

  if (today === null) {
    // SAID, NOT SPUN. He can act on this — wait, or tell us — and neither is possible while a
    // skeleton implies the answer is still coming.
    return (
      <div className="p-4">
        <EmptyState
          title="تعذّر تحميل شاشة اليوم"
          description="حسابك سليم. حاول بعد قليل."
        />
      </div>
    );
  }

  if (today === undefined) {
    return (
      <div className="grid gap-4 p-4 sm:grid-cols-3">
        <Skeleton height={96} /><Skeleton height={96} /><Skeleton height={96} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-4">
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

      <section className="rounded-card bg-surface-1 p-4 shadow-sm">
        <h2 className="mb-3 text-sm text-text-secondary">آخر الزيارات</h2>
        {recent === null ? (
          <Skeleton height={64} />
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
                <span dir="ltr" className="tabular-nums">{c.phone}</span>
                <span className="text-text-secondary">{c.name || '—'}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
