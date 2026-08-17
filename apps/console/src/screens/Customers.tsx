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
import { hasFailed, isDenied, isLoading, isReady, DENIED, type Loading } from '../loading';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronLeft, Search } from 'lucide-react';
import { EmptyState } from '@base-ui/design-system/EmptyState';
import { Button } from '@base-ui/design-system/Button';
import { Segmented } from '@base-ui/design-system/Segmented';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import { Badge } from '@base-ui/design-system/Badge';
import { action, call, type Catalog } from '../catalog';
import { suggestByPrefix, type CustomerHit } from '../api';
import type { Session } from '../session';
import { asLocal } from '../phone';

const MIN_PREFIX = 3;

/** One pending reminder, as the scheduler stores it. The pseudonym, never a name. */
interface Due { subject_ref?: string; due_at?: number }

/** One request a customer made from his own page. It carries a pseudonym and never a name. */
interface PrivacyAsk { id: string; type: string; at: number; subject_ref?: string }

/** How long ago, in the words an owner uses — the clock started then, and that is the point. */
function ago(at: number): string {
  const days = Math.floor((Date.now() / 1000 - at) / 86_400);
  if (days <= 0) return 'اليوم';
  if (days === 1) return 'أمس';
  if (days === 2) return 'قبل يومين';
  return `قبل ${days} أيام`;
}

export function CustomersScreen({ session, catalog }: { session: Session; catalog: Catalog }) {
  const navigate = useNavigate();
  const [tab, setTab] = useState<'all' | 'overdue'>('all');
  const [query, setQuery] = useState('');
  const [matches, setMatches] = useState<CustomerHit[] | null>([]);
  const [recent, setRecent] = useState<Loading<CustomerHit[]>>(undefined);
  const [overdue, setOverdue] = useState<Loading<CustomerHit[]>>(undefined);
  /**
   * WHAT HIS CUSTOMERS ASKED HIM FOR, from their own pages — a copy of their data, or its erasure.
   *
   * IT SITS AT THE TOP OF «عملائي» AND NOWHERE ELSE. This is a legal obligation with a thirty-day
   * clock and it belongs where he already looks at customers, not in a settings page he opens
   * twice a year. Absent when there is nothing to answer: a permanent empty panel about a legal
   * duty is how a legal duty becomes wallpaper.
   */
  const [asks, setAsks] = useState<PrivacyAsk[] | null>([]);

  useEffect(() => {
    const a = action(catalog, 'operations.recent');
    if (!a) { setRecent(DENIED); return; }
    call<{ customers: CustomerHit[] }>(session, a, { limit: 50 })
      .then((x) => setRecent(x.customers))
      .catch(() => setRecent(null));
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
    // NOT YET IS `undefined`, AND THIS LINE ONCE SAID `null`. It was written when a fetched value
    // had two states and `null` meant «not asked for yet»; `loading.ts` gave every screen four, and
    // this lazy guard kept the old vocabulary. So the tab opened at `undefined`, the guard read it
    // as «already handled», nothing was ever requested, and «من تأخّر» was a grey rectangle for
    // ever — the exact defect the four states were introduced to end. It would also have RETRIED A
    // FAILURE ENDLESSLY, since `null` now means «it failed» and would re-enter on every render.
    if (tab !== 'overdue' || overdue !== undefined) return;
    const schedule = action(catalog, 'reminders.list_schedule');
    const resolve = action(catalog, 'operations.customers_by_refs');
    if (!schedule || !resolve) { setOverdue(DENIED); return; }

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
      .catch(() => { if (!stale) setOverdue(null); });
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
        .catch(() => { if (!stale) setMatches(null); });
    }, 180);
    return () => { stale = true; window.clearTimeout(id); };
  }, [query, session]);

  const asksAction = action(catalog, 'operations.privacy_requests');
  const closeAsk = action(catalog, 'operations.close_privacy_request');
  /**
   * WHO EACH REQUEST IS, resolved from its pseudonym — the same join the overdue tab makes.
   *
   * THE PANEL COULD NOT ACT WITHOUT IT. A request arrives as a `subject_ref` and nothing else, so
   * the row said «طلب حذف بياناته» about nobody in particular and the only button closed it. An
   * owner meeting a PDPL deadline had no way from this panel to find the man, and no way to
   * honour the request — «تم الرد» marked it answered while every byte of the customer's data
   * stayed exactly where it was.
   *
   * `undefined` while the join is out, `null` when it failed: a name we could not look up must
   * not render as «عميل غير معروف», which is a claim about his records.
   */
  const [askWho, setAskWho] = useState<Loading<Record<string, CustomerHit>>>(undefined);

  useEffect(() => {
    if (!asksAction) return;
    call<{ requests: PrivacyAsk[] }>(session, asksAction)
      .then((r) => setAsks(r.requests ?? []))
      // SILENT ON FAILURE, because this panel is absent when there is nothing to show and an
      // error box about a feature he has never used is noise on the screen he opens most.
      .catch(() => setAsks(null));
  }, [session, catalog, asksAction]);

  useEffect(() => {
    const resolve = action(catalog, 'operations.customers_by_refs');
    if (!isReady(asks) || asks.length === 0) return;
    if (!resolve) { setAskWho(DENIED); return; }
    const refs = asks.map((a) => a.subject_ref).filter((r): r is string => Boolean(r));
    if (refs.length === 0) { setAskWho({}); return; }
    let stale = false;
    call<{ customers: (CustomerHit & { subject_ref?: string })[] }>(session, resolve, { refs })
      .then((x) => {
        if (stale) return;
        const by: Record<string, CustomerHit> = {};
        for (const c of x.customers ?? []) if (c.subject_ref) by[c.subject_ref] = c;
        setAskWho(by);
      })
      .catch(() => { if (!stale) setAskWho(null); });
    return () => { stale = true; };
  }, [asks, session, catalog]);

  const searching = query.length >= MIN_PREFIX;
  // THE TAB'S OWN VALUE, WITH ITS OWN STATE. Each of the four — loading, failed, denied, arrived —
  // gets its own sentence below, and «لا أحد متأخر» is the one empty state in this product that
  // is a compliment: saying it to somebody whose role never asked the question, or after a read
  // that failed, congratulates a shop at the moment it should be chasing people (م · النمط 2).
  const source = tab === 'overdue' ? overdue : searching ? matches : recent;
  const showing = isReady(source) ? source : [];
  const loading = isLoading(source);
  const denied = isDenied(source);

  return (
    <div className="flex flex-col gap-4 p-4">
      {/* ── what his customers asked him for ────────────────────────────────────────────────
          FIRST, AND ONLY WHEN THERE IS ONE. A customer tapped «اطلب حذف بياناتي» on his own page;
          under the PDPL the establishment is the controller and owes him an answer within thirty
          days. Before this the only way the shop could learn of it was a phone call — which is
          exactly what his page was built to replace. */}
      {asks?.length ? (
        <section className="flex flex-col gap-2 rounded-card border border-warning/40 bg-surface-1 p-4 shadow-sm">
          <h2 className="text-sm font-medium">
            طلبات على البيانات ({asks.length})
          </h2>
          <p className="text-sm text-text-secondary">
            عملاء طلبوا نسخة من بياناتهم أو حذفها من صفحاتهم. الرد عليهم مسؤوليتك نظاماً، خلال
            ثلاثين يوماً من تاريخ الطلب.
          </p>
          {asks.map((a) => (
            <PrivacyAskRow
              key={a.id}
              session={session}
              ask={a}
              who={isReady(askWho) ? askWho[a.subject_ref ?? ''] ?? null : undefined}
              whoFailed={hasFailed(askWho) || isDenied(askWho)}
              close={closeAsk}
              onDone={() => setAsks((cur) => (cur ?? []).filter((x) => x.id !== a.id))}
              onOpen={(id) => navigate(`/customers/${id}`)}
            />
          ))}
        </section>
      ) : null}

      <Segmented
        // FULL WIDTH, SPLIT EVENLY, NEVER WRAPPED. The kit's Segmented is
        // `inline-flex flex-wrap`, which on a phone stacks two long Arabic labels into a
        // ragged block half the screen wide. It takes a className and merges with
        // tailwind-merge, so this is a fix at the call site rather than a fork of the kit.
        className="flex w-full [&>button]:flex-1 [&>button]:whitespace-nowrap"
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
      ) : showing === null ? (
        // THE FOURTH STATE, AND THE ONE THAT WAS MISSING. A failed read used to become an empty
        // list, so this screen told a shop with three thousand customers «لا يوجد عملاء بعد» —
        // and, on the overdue tab, CONGRATULATED him with «لا أحد متأخر» at the exact moment he
        // should have been chasing someone. An empty state is a claim about his shop; we may only
        // make it when we actually read.
        <EmptyState
          title="تعذّرت القراءة"
          description="لم نستطع جلب القائمة الآن — والخلل عندنا لا في محلك. أعد المحاولة بعد قليل."
        />
      ) : denied ? (
        <EmptyState
          title={tab === 'overdue' ? 'لا يشمل دورك متابعة المتأخرين' : 'لا يشمل دورك قائمة العملاء'}
          description="راجع صاحب المحل إن كنت تحتاج هذا القسم."
        />
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
                <span dir="ltr" className="tabular-nums">{asLocal(c.phone)}</span>
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

/**
 * One request, with the person it is about and a way to finish it.
 *
 * THE ROW USED TO BE A TYPE, A DATE AND ONE BUTTON. The request arrives as a pseudonym, so the
 * panel said «طلب حذف بياناته» about nobody in particular — and «تم الرد» closed it while every
 * byte of that customer's data stayed exactly where it was. An owner on a thirty-day legal clock
 * was given a screen that could mark the duty done and could not perform it.
 *
 * SO IT NAMES HIM AND IT OPENS HIM. The erasure itself lives on the customer's own page, behind a
 * confirmation that repeats his name — an irreversible act belongs in one place, and a second
 * copy of it inside a summary panel is the copy that drifts. This row is the route to it.
 *
 * AND CLOSING IS NEVER DRESSED AS DELETING. «تم الرد» records that HE answered — kept with his
 * name and the hour, and audited — and on an erasure request the row says in words that closing
 * deletes nothing, because that is precisely the belief the old panel encouraged.
 */
function PrivacyAskRow({ session, ask, who, whoFailed, close, onDone, onOpen }: {
  session: Session;
  ask: PrivacyAsk;
  /** The customer, `null` when this establishment holds no such ref, `undefined` while resolving. */
  who: CustomerHit | null | undefined;
  /** The join failed or was never permitted — which is not «we hold nobody by that name». */
  whoFailed: boolean;
  close: ReturnType<typeof action>;
  onDone: () => void;
  onOpen: (customerId: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const erasure = ask.type === 'erase';

  return (
    <div className="flex flex-col gap-2 border-t border-border-subtle pt-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex flex-col">
          <span className="text-sm">
            {erasure ? 'طلب حذف بياناته' : 'طلب نسخة من بياناته'}
          </span>
          {/* WHO ASKED. Three different answers, and none of them may borrow another's words: a
              name we have, a lookup that failed, and a shop that genuinely holds no such customer
              — the last of which usually means his data is already gone. */}
          <span className="text-xs text-text-secondary" dir={who?.name ? undefined : 'ltr'}>
            {who ? (who.name || asLocal(who.phone))
              : whoFailed ? 'تعذّر التعرّف على صاحب الطلب'
              : who === null ? 'لا يوجد عميل بهذا المرجع في سجلاتك'
              : '…'}
          </span>
          {/* THE DATE IS THE POINT: the clock started on it, and «قبل يومين» is what tells him
              whether this is urgent without arithmetic. */}
          <span className="text-xs text-text-secondary">{ago(ask.at)}</span>
        </span>
        <span className="flex flex-wrap gap-2">
          {who ? (
            <Button onClick={() => onOpen(who.id)}>
              {erasure ? 'افتح سجله لتنفيذ الحذف' : 'افتح سجله'}
            </Button>
          ) : null}
          {close ? (
            <Button
              variant="ghost"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                await call(session, close, { request_id: ask.id }).catch(() => null);
                onDone();
              }}
            >
              تم الرد
            </Button>
          ) : null}
        </span>
      </div>
      {erasure ? (
        <p className="text-xs text-text-secondary">
          «تم الرد» يسجّل أنك أجبته، ولا يحذف شيئاً. الحذف من صفحة العميل نفسه.
        </p>
      ) : null}
    </div>
  );
}
