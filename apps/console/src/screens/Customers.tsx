/**
 * «عملائي» — who I have, and who has not come back.
 *
 * THREE REASONS TO OPEN IT AND NO FOURTH: how many do I have, find this one, who is overdue.
 * Anything that does not serve one of those is analysis, and analysis is «محلّي».
 *
 * THE SEARCH IS THE FIRST THING BECAUSE IT IS THE FIRST REASON — and it is the one control on this
 * screen with a failure mode that costs a customer. Filtering the rows already on screen looks
 * identical in development and fails exactly as the spec warns: he types five correct digits, sees
 * nothing because that customer was not here today, and concludes the man is not registered.
 *
 * AND THE THIRD REASON WAS MISSING FOR WEEKS. This file named «من تأخّر» in its own first
 * paragraph and never built it: the screen listed recent customers and searched them, and the
 * question an owner opens this section to ask — who has not come back — had no answer anywhere in
 * the product. It could not be built until operations could turn a pseudonym into a customer,
 * because the overdue list comes from reminders and reminders holds no names at all, deliberately.
 */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronLeft, Search } from 'lucide-react';
import { EmptyState } from '@base-ui/design-system/EmptyState';
import { Segmented } from '@base-ui/design-system/Segmented';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import { Badge } from '@base-ui/design-system/Badge';
import { action, call, type Catalog } from '../catalog';
import { suggestByPrefix, type CustomerHit } from '../api';
import type { Session } from '../session';

const MIN_PREFIX = 3;

/** One pending reminder, as the scheduler stores it. The pseudonym, never a name. */
interface Due { subject_ref?: string; due_at?: number }

export function CustomersScreen({ session, catalog }: { session: Session; catalog: Catalog }) {
  const navigate = useNavigate();
  const [tab, setTab] = useState<'all' | 'overdue'>('all');
  const [query, setQuery] = useState('');
  const [matches, setMatches] = useState<CustomerHit[]>([]);
  const [recent, setRecent] = useState<CustomerHit[] | null>(null);
  const [overdue, setOverdue] = useState<CustomerHit[] | null>(null);

  useEffect(() => {
    const a = action(catalog, 'operations.recent');
    if (!a) { setRecent([]); return; }
    call<{ customers: CustomerHit[] }>(session, a, { limit: 50 })
      .then((x) => setRecent(x.customers))
      .catch(() => setRecent([]));
  }, [session, catalog]);

  /**
   * WHO IS OVERDUE — two calls, and neither of them decides what "overdue" means.
   *
   * THE ENGINE OWNS THE DEFINITION. A due date is the settings tree resolved against a service's
   * cycle and the customer's last visit, and re-deriving any of that here would be a second
   * opinion — one that disagrees the first time somebody changes a cycle, with the wrong answer
   * being the one on the owner's screen. So the schedule is read as it stands, and this screen
   * only asks WHOSE it is.
   *
   * LOADED ONLY WHEN THE TAB IS OPENED. It costs two round trips, and most visits to this section
   * are somebody looking up one customer at the counter.
   */
  useEffect(() => {
    if (tab !== 'overdue' || overdue !== null) return;
    const schedule = action(catalog, 'reminders.list_schedule');
    const resolve = action(catalog, 'operations.customers_by_refs');
    if (!schedule || !resolve) { setOverdue([]); return; }

    let stale = false;
    call<{ schedule: Due[] }>(session, schedule, { state: 'pending', limit: 200 })
      .then((s) => {
        // PAST, NOT PENDING. Everything scheduled is pending; only what was due before now is
        // late, and showing a customer whose reminder goes out tomorrow as "overdue" would send
        // the owner chasing people the engine is already handling.
        const now = Math.floor(Date.now() / 1000);
        const refs = (s.schedule ?? [])
          .filter((r) => (r.due_at ?? 0) > 0 && (r.due_at ?? 0) <= now)
          .map((r) => r.subject_ref)
          .filter((r): r is string => Boolean(r));
        if (refs.length === 0) return { customers: [] as CustomerHit[] };
        return call<{ customers: CustomerHit[] }>(session, resolve, { refs });
      })
      .then((x) => { if (!stale) setOverdue(x.customers ?? []); })
      .catch(() => { if (!stale) setOverdue([]); });
    return () => { stale = true; };
  }, [tab, overdue, session, catalog]);

  /**
   * DEBOUNCED, AND GUARDED AGAINST ITS OWN HISTORY. This fires on every key of a ten-digit number
   * typed fast; without the `stale` flag the answer to three digits can land after the answer to
   * six and overwrite it, so the list would show matches for a prefix he has already moved past.
   */
  useEffect(() => {
    if (query.length < MIN_PREFIX) { setMatches([]); return; }
    let stale = false;
    const id = window.setTimeout(() => {
      suggestByPrefix(session, query)
        .then((rows) => { if (!stale) setMatches(rows); })
        // A failed search must never block the screen: the list below still stands, and he can
        // still reach a customer through it.
        .catch(() => { if (!stale) setMatches([]); });
    }, 180);
    return () => { stale = true; window.clearTimeout(id); };
  }, [query, session]);

  const searching = query.length >= MIN_PREFIX;
  const showing = tab === 'overdue'
    ? (overdue ?? [])
    : searching ? matches : (recent ?? []);
  const loading = tab === 'overdue' ? overdue === null : recent === null;

  return (
    <div className="flex flex-col gap-4 p-4">
      <Segmented
        ariaLabel="أقسام العملاء"
        value={tab}
        onChange={setTab}
        options={[
          { value: 'all', label: 'عملائي' },
          { value: 'overdue', label: 'من تأخّر' },
        ]}
      />

      {/* THE SEARCH BELONGS TO THE LIST, NOT TO THE SCREEN. Typing a number while «من تأخّر» is
          open would search everybody and quietly leave the tab he is looking at. */}
      {tab === 'all' ? (
      <label className="relative block">
        <Search size={18} className="absolute top-1/2 -translate-y-1/2 start-3 text-text-muted" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="ابحث برقم الجوال أو الاسم"
          className="h-12 w-full rounded-xl bg-surface-1 ps-10 pe-4 shadow-sm placeholder:text-text-muted"
        />
      </label>
      ) : null}

      {loading ? (
        <Skeleton height={200} />
      ) : showing.length === 0 ? (
        // THREE DIFFERENT EMPTIES, AND THEY MUST NOT SHARE A SENTENCE. "No customer matched" is a
        // search result; "you have no customers yet" is the state of the shop; and an empty
        // overdue list is GOOD NEWS — the one empty state in this product that is a compliment.
        tab === 'overdue' ? (
          <EmptyState
            title="لا أحد متأخر"
            description="كل عميل إما زار في وقته أو تذكيره لم يحن بعد."
          />
        ) : searching ? (
          <EmptyState
            title="لا نتائج"
            description="تأكد من الرقم، أو سجّل زيارة جديدة لهذا العميل."
          />
        ) : (
          <EmptyState
            title="لا يوجد عملاء بعد"
            description="سجّل أول زيارة من «تسجيل زيارة» — العميل يُنشأ بزيارته."
          />
        )
      ) : (
        <ul className="flex flex-col gap-2">
          {showing.map((c) => (
            // THE ROW OPENS HIM. It used to be inert: the owner tapped a customer and nothing
            // happened, so this whole section could answer only "does he exist".
            <li key={c.id}>
            <button
              type="button"
              onClick={() => navigate(`/customers/${c.id}`)}
              className="flex w-full items-center justify-between rounded-card bg-surface-1 px-4 py-3 text-start shadow-sm active:scale-[0.99]"
            >
              <div className="flex flex-col">
                <span dir="ltr" className="tabular-nums">{c.phone}</span>
                <span className="text-sm text-text-secondary">{c.name || 'بلا اسم'}</span>
              </div>
              {/* THE CONSENT STATE IS SHOWN BECAUSE IT CHANGES WHAT HE MAY DO, not as decoration:
                  a customer who withdrew still earns points and still gets service messages, and
                  the one thing that stops is marketing. An owner who cannot see it will assume an
                  offer reached everyone. */}
              <span className="flex items-center gap-2">
                {c.marketing === false ? (
                  <Badge tone="neutral">أوقف التسويق</Badge>
                ) : null}
                {/* RTL: the chevron points the way the page will move, which is leftwards. */}
                <ChevronLeft size={18} className="shrink-0 text-text-muted" aria-hidden />
              </span>
            </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
