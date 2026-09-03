/**
 * One customer, as his shop sees him.
 *
 * THE SCREEN «عملائي» COULD NOT OPEN. The list found him and stopped there: the owner tapped a row
 * and nothing happened, so the only question this section could answer was "does he exist". His
 * visits, his points and — the reason this file was written — WHICH OFFERS HE IS HOLDING were all
 * in the product and reachable from nowhere.
 *
 * THE OFFERS COME FIRST, and expired ones are shown here and nowhere else.
 *
 * The customer's own page and the field screen must never render a dead offer: it contradicts the
 * shop in front of the customer. The owner is asking a different question. "Did he get last
 * month's offer?" is as common as "what is he holding now", and an answer that hides everything
 * that ran out makes his own history unreadable — so they are here, dimmed and labelled, never
 * removed.
 *
 * AND THE JOIN IS THE PSEUDONYM. reminders holds no names at all — deliberately — so the offers
 * are fetched by the `subject_ref` that arrives with this one record and with no list.
 */
import { asLocal } from '../phone';
import { CustomerBookingHistory } from '../CustomerBookingHistory';
import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Badge } from '../rj-ui/Badge';
import { Segmented } from '../rj-ui/Segmented';
import { Drawer } from '../rj-ui/Drawer';
import { Hint } from '../Hint';
import { Button } from '../rj-ui/Button';
import { EmptyState } from '../rj-ui/EmptyState';
import { isDenied, isReady, DENIED, hasFailed, isLoading, type Loading } from '../loading';
import { Skeleton } from '../rj-ui/Skeleton';
import { Waiting } from '../Waiting';
import { action, call, type Catalog } from '../catalog';
import { partitionOffers, remaining, type Offer } from '../offers';
import type { Session } from '../session';
import { western } from '../digits';

interface Record {
  customer: { id: string; phone: string; name?: string; subject_ref?: string; visits?: number };
  /** `services` is the NAME the server joins for this row (ب-3), not the identifiers `public()`
   *  carries: reading `service_ids` here would print «svc_9f2a…» to the owner, and reading a key
   *  the server never sent printed «زيارة» on twenty identical lines.
   *
   *  `meter` and `note` are typed by the operator on the field screen and were read by nothing
   *  at all (أ-9): both doors accept them, the visit row stores them, and no screen in the
   *  product showed them back. Daily effort on a screen whose whole budget is five seconds. */
  visits: { id: string; services?: string; occurred_at?: number; meter?: number; note?: string }[];
  /** His vehicles, when this shop works on cars. The record has always carried them. */
  assets?: { id: string; plate?: string; make?: string; model?: string }[];
}

interface Balance { balance: number; rewards?: { id: string; name: string; cost: number }[] }
interface Move { at?: number; delta?: number; reason?: string; kind?: string }
interface Send { at?: number; template_type?: string; outcome?: string; reason?: string }


/**
 * How long ago, in words a person uses. «قبل 0 يوماً» is not a sentence anyone says, and it was
 * the first thing on the page for every customer who came in today — which is exactly the customer
 * an owner is most likely to be looking at.
 */
export function ago(days: number, seen: boolean): string {
  if (!seen) return '—';
  if (days <= 0) return 'اليوم';
  if (days === 1) return 'أمس';
  if (days === 2) return 'قبل يومين';
  if (days <= 10) return `قبل ${days} أيام`;
  return `قبل ${days} يوماً`;
}

/** A date an owner reads. Western digits, and the shop's own timezone rather than the browser's. */
function when(epoch: number): string {
  if (!epoch) return '';
  return new Date(epoch * 1000).toLocaleDateString('ar-SA-u-nu-latn', {
    timeZone: 'Asia/Riyadh', year: 'numeric', month: 'short', day: 'numeric',
  });
}

/**
 * Why a balance was moved by hand — the reasons a shop actually has.
 *
 * TYPING IS THE ENEMY HERE. The reason is required because the entry outlives the memory of it,
 * but requiring it as free text on a workshop tablet produces «تعويض» and «خطا» and «..» — three
 * words that answer nothing six months later, which is exactly when the customer asks. A short
 * list of the real cases costs one tap and produces a record somebody can read.
 *
 * «أخرى» KEEPS THE DOOR OPEN, because a fixed list always meets the case nobody predicted — and a
 * screen that refuses the unusual reason teaches the operator to pick the nearest lie.
 */
const ADJUST_REASONS = [
  'تعويض عن خطأ في تسجيل الزيارة',
  'تعويض عن خدمة لم تُنفَّذ كما يجب',
  'نقاط ترحيبية',
  'تصحيح رصيد بعد جرد',
  'استبدال تمّ يدوياً في المحل',
  'إلغاء استبدال',
] as const;

/**
 * One learned interval — HIS, for one service.
 *
 * `learned` is separate from the number on purpose: an owner told «تعلّمنا: 90 يوماً» from zero
 * observations stops trusting every number on the screen, so an estimate that is still the
 * service's own default has to say it is one.
 */
interface Rule {
  id?: string;
  service_id?: string;
  service_name?: string;
  interval_days?: number;
  observations?: number;
  learned?: boolean;
  pinned?: boolean;
}

export function CustomerScreen({ session, catalog }: { session: Session; catalog: Catalog }) {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const [record, setRecord] = useState<Record | null | undefined>(undefined);
  const [offers, setOffers] = useState<Loading<Offer[]>>(undefined);
  const [balance, setBalance] = useState<Balance | null | undefined>(undefined);
  const [moves, setMoves] = useState<Move[] | null | undefined>(undefined);
  const [sends, setSends] = useState<Send[] | null | undefined>(undefined);
  const [tab, setTab] = useState<'overview' | 'points' | 'messages' | 'manage'>('overview');
  const [adjustBy, setAdjustBy] = useState('');
  const [adjustNote, setAdjustNote] = useState<string>(ADJUST_REASONS[0]);
  const [adjusting, setAdjusting] = useState(false);
  const [adjustMsg, setAdjustMsg] = useState('');
  const [nameDraft, setNameDraft] = useState('');
  const [namingMsg, setNamingMsg] = useState('');
  /** His own rhythm, per service, as the engine learned it (§5.2). */
  const [cycles, setCycles] = useState<Rule[]>([]);
  const [pinMsg, setPinMsg] = useState('');
  const [pickingReason, setPickingReason] = useState(false);
  const [erasing, setErasing] = useState(false);
  const [eraseAsked, setEraseAsked] = useState(false);
  const [eraseMsg, setEraseMsg] = useState('');

  useEffect(() => {
    const a = action(catalog, 'operations.customer');
    if (!a || !id) { setRecord(null); return; }
    let stale = false;
    call<Record>(session, a, { id })
      .then((r) => {
        if (stale) return;
        setRecord(r);
        // THE SECOND CALL DEPENDS ON THE FIRST, and it cannot be avoided: the pseudonym is what
        // reminders knows him by, and only this record carries it.
        const o = action(catalog, 'reminders.customer_offers');
        const ref = r.customer?.subject_ref;
        if (!ref) { setOffers([]); return; }
        if (!o) { setOffers(DENIED); return; }
        call<{ offers: Offer[] }>(session, o, { subject_ref: ref, include_expired: true })
          .then((x) => { if (!stale) setOffers(x.offers ?? []); })
          // An offers read that fails must not empty the record: his visits are still true.
          .catch(() => { if (!stale) setOffers(null); });

        // EACH SECTION FAILS ALONE. They are four services, and one of them being slow or absent
        // is not a reason to show an empty customer — a shop without the loyalty feature has no
        // balance to read, and that says nothing about his messages.
        const bal = action(catalog, 'loyalty.balance');
        if (bal) {
          call<Balance>(session, bal, { subject_ref: ref })
            .then((x) => { if (!stale) setBalance(x); }).catch(() => undefined);
        }
        const hist = action(catalog, 'loyalty.history');
        if (hist) {
          call<{ history?: Move[]; moves?: Move[] }>(session, hist, { subject_ref: ref })
            .then((x) => { if (!stale) setMoves(x.history ?? x.moves ?? []); })
            .catch(() => undefined);
        }
        // WHAT THE SYSTEM LEARNED ABOUT HIM — §5.2 and §5.3, invisible until now. The rules were
        // computed per (customer, service) from his own rhythm, and the only screen that could
        // read them filtered by service, so nobody could ever ask «كل كم يعود هذا؟».
        const rules = action(catalog, 'reminders.list_rules');
        if (rules) {
          call<{ rules: Rule[] }>(session, rules, { subject_ref: ref })
            .then((x) => { if (!stale) setCycles(x.rules ?? []); })
            .catch(() => undefined);
        }
        const log = action(catalog, 'reminders.log');
        if (log) {
          call<{ entries?: Send[]; log?: Send[] }>(session, log, { subject_ref: ref, limit: 20 })
            .then((x) => { if (!stale) setSends(x.entries ?? x.log ?? []); })
            .catch(() => undefined);
        }
      })
      .catch(() => { if (!stale) setRecord(null); });
    return () => { stale = true; };
  }, [id, session, catalog]);

  // A PAGE WITH NO KNOWN SHAPE YET WAITS IN OUR OWN MARK, not as one grey rectangle —
  // see Waiting.tsx. The skeletons inside the page stay: there the shape IS known.
  if (record === undefined) return <Waiting what="نفتح صفحة عميلك" />;

  if (record === null) {
    return (
      <div className="p-4">
        <EmptyState
          title="تعذّر فتح سجل العميل"
          description="قد يكون العميل غير موجود، أو تعذّر الوصول إلى الخدمة. حاول بعد قليل."
        />
        <Button variant="ghost" onClick={() => navigate('/customers')}>رجوع إلى عملائي</Button>
      </div>
    );
  }

  const c = record.customer;
  // FROM THE TESTED MODULE, NOT FROM A COPY HERE. A rule that lives inside a component is a rule
  // only a rendered page can check — and the rendered page is the thing most likely to be rewritten.
  const [live, past] = partitionOffers(isReady(offers) ? offers : []);
  // NOT OFFERED AT ALL WHERE IT IS NOT PERMITTED. The gateway has already filtered
  // the catalogue by capability, so a supervisor sees a shorter tab rather than a
  // button that refuses him — and `operations.manage` is deliberately not the
  // capability the man at the counter carries.
  const eraseAction = action(catalog, 'operations.erase_customer');

  /**
   * WHAT HIS OWN VISITS SAY ABOUT HIM — computed here, from what we already have.
   *
   * These are not the shop's indicators (§10, gated): they are three facts about ONE customer that
   * the record in hand already contains. An owner opening a customer asks them in this order —
   * when was he last here, how often does he come, and is he late — and answering with a number he
   * can check beats any sentence we could write.
   *
   * «كل كم يوماً» IS A MEAN OF GAPS, not visits-per-period: a customer with two visits three years
   * apart and one who came twice last week must not read the same, and the gap says so.
   */
  const times = (record.visits ?? [])
    .map((v) => Number(v.occurred_at) || 0).filter(Boolean).sort((a, b) => b - a);
  const lastSeen = times[0] ?? 0;
  const gaps = times.slice(0, -1).map((t, i) => t - times[i + 1]).filter((g) => g > 0);
  const everyDays = gaps.length
    ? Math.round(gaps.reduce((a, b) => a + b, 0) / gaps.length / 86400)
    : 0;
  const sinceDays = lastSeen ? Math.floor((Date.now() / 1000 - lastSeen) / 86400) : 0;
  // LATE ONLY AGAINST HIS OWN RHYTHM, never against a number we chose. A customer who comes twice
  // a year is not overdue in month three, and telling his shop otherwise invents a problem.
  const overdue = everyDays > 0 && sinceDays > everyDays * 1.5;

  return (
    <div className="flex flex-col gap-4 p-4">
      <header className="flex items-center justify-between gap-3">
        {/* TWO LINES, ALWAYS, AND THE SMALLER ONE UNDERNEATH. The name leads when there is one;
            the number leads when there is not, and «بلا اسم» sits under it as a quiet fact rather
            than a heading. §4.3: the name arrives after five visits and never blocks a save, so an
            unnamed customer is ordinary — a layout that changes shape between the two makes the
            common case look like the broken one. */}
        <span className="flex flex-col">
          <span className={c.name ? 'text-lg font-semibold' : 'text-lg font-semibold tabular-nums'}
                dir={c.name ? undefined : 'ltr'}>
            {c.name || asLocal(c.phone)}
          </span>
          <span
            dir={c.name ? 'ltr' : undefined}
            className="text-sm text-text-secondary tabular-nums"
          >
            {c.name ? asLocal(c.phone) : 'بلا اسم'}
          </span>
        </span>
        <Button variant="ghost" onClick={() => navigate('/customers')}>رجوع</Button>
      </header>

      {/* HIS THREE NUMBERS, ABOVE EVERYTHING. They are what the owner opened this page to learn,
          and each is checkable against the visits listed below it — nothing here is inferred from
          data he cannot see. */}
      <section className="grid grid-cols-3 gap-2">
        {[
          { k: 'زياراته', v: String(c.visits ?? times.length) },
          { k: 'آخر زيارة', v: ago(sinceDays, Boolean(lastSeen)) },
          { k: 'كل كم يوماً', v: everyDays ? String(everyDays) : '—' },
        ].map((x) => (
          // EQUAL HEIGHT AND ONE LINE EACH. Three cards that size themselves to their own text
          // read as three unrelated boxes; the label sits under the value at a fixed height so the
          // row scans as one row.
          <div
            key={x.k}
            className="flex h-20 flex-col items-center justify-center gap-0.5 rounded-card bg-surface-1 px-2 shadow-sm"
          >
            <div className="truncate text-lg font-semibold tabular-nums">{x.v}</div>
            <div className="text-xs text-text-secondary">{x.k}</div>
          </div>
        ))}
      </section>

      {overdue ? (
        <p className="rounded-xl bg-accent-soft px-3 py-2 text-sm text-accent-on-soft">
          تأخّر عن دورته المعتادة — يزور كل {everyDays} يوماً، وآخر زيارة قبل {sinceDays}.
        </p>
      ) : null}

      {(record.assets ?? []).length > 0 ? (
        <section className="rounded-card bg-surface-1 p-4 shadow-sm">
          <h2 className="mb-2 text-sm text-text-secondary">سياراته</h2>
          <ul className="flex flex-wrap gap-2">
            {(record.assets ?? []).map((a) => (
              <li key={a.id} className="rounded-lg bg-surface-2 px-3 py-1.5 text-sm">
                <span dir="ltr" className="tabular-nums">{a.plate || '—'}</span>
                {a.make ? <span className="ms-2 text-text-secondary">{a.make} {a.model}</span> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {/* TABS, LIKE EVERY OTHER SECTION. The page answers three different errands — who he is,
          what he is owed, and what we said to him — and stacking all three made the first one
          scroll away. Same shape as «حسابي» and «خدماتي»: a person who learned one has learned
          this. */}
      <Segmented
        // FOUR SHORT WORDS SPLIT EVENLY, and never a strip that slides. A tab hanging half off
        // the edge is a tab nobody presses: it does not look like a control, it looks like the
        // page is broken. «حسابي» has five tabs and needs the sliding row; four fit, so they get
        // the width instead — the same component, sized to what it holds.
        className="flex w-full flex-nowrap [&>button]:min-w-0 [&>button]:flex-1 [&>button]:truncate [&>button]:px-1 [&>button]:text-xs sm:[&>button]:px-3 sm:[&>button]:text-sm"
        ariaLabel="أقسام العميل"
        value={tab}
        onChange={(v: string) => setTab(v as typeof tab)}
        options={[
          { value: 'overview', label: 'نظرة عامة' },
          { value: 'points', label: 'نقاطه' },
          { value: 'messages', label: 'رسائله' },
          // EVERYTHING THAT CHANGES HIM, IN ONE PLACE. Reading and editing are different errands
          // with different risks: a manager scanning a balance should not have a points field
          // under his thumb, and an owner correcting a name should not have to hunt through three
          // read-only panes to find where the product lets him write.
          { value: 'manage', label: 'تعديل' },
        ]}
      />

      {tab === 'overview' ? (
        <>
      {record?.customer?.id ? (
        <CustomerBookingHistory session={session} customerId={record.customer.id} />
      ) : null}
      <section className="rounded-card bg-surface-1 p-4 shadow-sm">
        <h2 className="mb-3 text-sm text-text-secondary">عروضه</h2>
        {isLoading(offers) ? (
          <Skeleton height={90} />
        ) : isDenied(offers) ? (
          <p className="text-sm text-text-secondary">لا يشمل دورك عروض العملاء.</p>
        ) : hasFailed(offers) ? (
          // «لم يصله أي عرض» IS A FACT ABOUT HIM. Said after a failed read it tells the owner his
          // customer was never invited to anything, which he may then act on.
          <p className="text-sm text-text-secondary">
            تعذّرت قراءة عروضه الآن — والخلل عندنا. أعد المحاولة بعد قليل.
          </p>
        ) : offers.length === 0 ? (
          // NOT A FAULT, unlike an empty service catalogue. Nobody seeds a customer an offer — he
          // gets one when the shop runs one, and saying so plainly beats an apology.
          <p className="text-sm text-text-secondary">لم يصله أي عرض بعد.</p>
        ) : (
          <ul className="flex flex-col gap-3">
            {live.map((o) => (
              <li key={`${o.sent_at}-${o.text}`} className="rounded-xl bg-surface-2 p-3">
                <p className="font-medium">{o.text}</p>
                <p className="mt-1 text-sm text-text-secondary">
                  {o.services.length > 0 ? `على: ${o.services.join('، ')}` : 'على كل الخدمات'}
                </p>
                <p className="mt-2 flex flex-wrap items-center gap-2 text-sm">
                  <Badge tone="accent">ساري</Badge>
                  <span className="text-text-secondary">{remaining(o.expires_at)}</span>
                  <span className="text-text-secondary">· وصله {when(o.sent_at)}</span>
                  {/* THE SAME STRING HE IS HOLDING. The owner is often the one who answers when a
                      customer calls to ask about an offer, and «الرمز اللي عندك؟» only works if
                      this screen shows what was sent. */}
                  {o.code ? (
                    <span dir="ltr" className="font-mono tracking-wider text-text-secondary">
                      {o.code}
                    </span>
                  ) : null}
                </p>
              </li>
            ))}
            {/* DIMMED AND LABELLED, NEVER REMOVED. «هل وصله عرض الشهر الماضي؟» is a question the
                owner asks as often as «ماذا يحمل الآن؟», and an answer that hides what ran out
                makes his own history unreadable. */}
            {past.map((o) => (
              <li key={`${o.sent_at}-${o.text}`} className="rounded-xl bg-surface-2 p-3 opacity-60">
                <p className="font-medium">{o.text}</p>
                <p className="mt-2 flex items-center gap-2 text-sm">
                  <Badge tone="neutral">انتهى</Badge>
                  <span className="text-text-secondary">
                    {when(o.sent_at)} — {when(o.expires_at)}
                  </span>
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-card bg-surface-1 p-4 shadow-sm">
        <h2 className="mb-3 text-sm text-text-secondary">زياراته</h2>
        {record.visits.length === 0 ? (
          <p className="text-sm text-text-secondary">لا زيارات مسجّلة بعد.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {record.visits.slice(0, 20).map((v) => (
              <li key={v.id} className="flex items-start justify-between gap-3">
                <span className="min-w-0">
                  {v.services || 'زيارة'}
                  {/* WHAT THE TECHNICIAN TYPED, SHOWN TO THE PERSON WHO ASKED FOR IT. The reading
                      is how a vehicle shop knows whether a service is due by distance rather than
                      by date, and the note is the sentence that explains a visit months later. */}
                  {v.meter ? (
                    <span className="block text-sm tabular-nums text-text-secondary">
                      العدّاد: {v.meter.toLocaleString('en-US')}
                    </span>
                  ) : null}
                  {v.note ? (
                    <span className="block truncate text-sm text-text-secondary">{v.note}</span>
                  ) : null}
                </span>
                <span className="shrink-0 text-sm text-text-secondary">{when(v.occurred_at ?? 0)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
        </>
      ) : null}

      {tab === 'points' ? (
        <section className="rounded-card bg-surface-1 p-4 shadow-sm">
          {/* HIS BALANCE, AND WHERE IT WENT. «أين ذهبت نقاطي؟» is asked at the counter, by the
              person whose points they are, and an owner who cannot answer it in front of him has
              a loyalty programme that costs trust instead of earning it. */}
          <h2 className="mb-3 text-sm text-text-secondary">نقاطه</h2>
          {/* ONE SENTENCE FOR TWO CONTRADICTORY STATES, until the states themselves were told
              apart. «برنامج النقاط غير مفعّل، أو تعذّرت قراءة رصيده» asks the owner to work
              out which of two entirely different things happened — one he fixes by buying, one he
              fixes by waiting. The lock for «not in your enabled apps» is drawn elsewhere on this screen;
              here `undefined` waits and `null` says the read failed. */}
          {isLoading(balance) ? (
            <Skeleton height={70} />
          ) : hasFailed(balance) ? (
            <p className="text-sm text-text-secondary">
              تعذّرت قراءة رصيده الآن — والخلل عندنا. أعد المحاولة بعد قليل.
            </p>
          ) : (
            <>
              <div className="mb-3 flex items-baseline gap-2">
                <span className="text-3xl font-semibold tabular-nums">{balance.balance}</span>
                <span className="text-sm text-text-secondary">نقطة</span>
              </div>
              {(balance.rewards ?? []).length > 0 ? (
                <ul className="mb-3 flex flex-col gap-1 text-sm">
                  {(balance.rewards ?? []).map((r) => (
                    <li key={r.id} className="flex justify-between">
                      <span>{r.name}</span>
                      <span className="tabular-nums text-text-secondary">{r.cost} نقطة</span>
                    </li>
                  ))}
                </ul>
              ) : null}
              <h3 className="mb-1 text-sm text-text-secondary">حركة النقاط</h3>
              {isLoading(moves) ? <Skeleton height={60} /> : hasFailed(moves) ? (
                <p className="text-sm text-text-secondary">
                  تعذّرت قراءة حركة نقاطه الآن — أعد المحاولة بعد قليل.
                </p>
              ) : moves.length === 0 ? (
                <p className="text-sm text-text-secondary">لا حركة بعد.</p>
              ) : (
                <ul className="flex flex-col gap-1 text-sm">
                  {moves.slice(0, 12).map((m, i) => (
                    <li key={i} className="flex justify-between">
                      <span className="text-text-secondary">{when(m.at ?? 0)}</span>
                      <span className={`tabular-nums ${(m.delta ?? 0) < 0 ? 'text-danger' : ''}`}>
                        {(m.delta ?? 0) > 0 ? `+${m.delta}` : m.delta}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </section>
      ) : null}


      {tab === 'manage' ? (
        <section className="flex flex-col gap-4 rounded-card bg-surface-1 p-4 shadow-sm">
          {/* HIS NAME, WHICH ARRIVES LATE BY DESIGN (§4.3). It is hard to ask a stranger his name
              while taking his key, and after five visits the operator simply knows it — so the
              field never blocks a save and most customers are created without one. Until this
              existed there was no way to add it afterwards: the owner recognising a regular sat
              watching a row that said «بلا اسم» for ever. */}
          <div className="flex flex-col gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium">اسمه</span>
              {/* THE RULE, ONE TAP AWAY. It is true for ever and read once; left on the card it
                  becomes furniture that takes the width the fields need and gets skipped by the
                  eye — so the one time somebody needs it, he has already learned to look past it. */}
              <Hint label="لماذا لا يُعدَّل الرقم">
                الرقم هوية العميل عند كل أقسام النظام، ومنه يُشتقّ معرّفه — فتغييره يترك نقاطه
                وعروضه وتاريخه خلف الرقم القديم. رقمٌ خاطئ يعني عميلاً جديداً ودمجاً، لا تعديلاً.
              </Hint>
            </div>
            <div className="flex gap-2">
              <input
                value={nameDraft || c.name || ''}
                onChange={(e) => setNameDraft(e.target.value)}
                placeholder="اكتب اسمه"
                aria-label="اسم العميل"
                className="h-11 min-w-0 flex-1 rounded-xl bg-surface-2 px-3 shadow-sm"
              />
              <Button
                onClick={async () => {
                  const a2 = action(catalog, 'operations.rename_customer');
                  if (!a2) return;
                  setNamingMsg('');
                  try {
                    const saved = nameDraft.trim();
                    await call(session, a2, { customer_id: c.id, name: saved });
                    // THE PAGE AGREES WITH THE SERVER NOW. Without this the header still showed
                    // «بلا اسم» beside a field that had just been saved — two truths on one
                    // screen, and the one he can see is the wrong one.
                    c.name = saved;
                    setNamingMsg('✓ تم حفظ الاسم');
                    // IT CLEARS ITSELF. A confirmation that stays becomes furniture — after a
                    // minute he cannot tell whether it belongs to the edit he just made or the
                    // one before it, which is worse than no confirmation at all.
                    window.setTimeout(() => setNamingMsg(''), 3000);
                  } catch (e) {
                    setNamingMsg(e instanceof Error ? e.message : 'تعذّر الحفظ');
                  }
                }}
              >
                حفظ
              </Button>
            </div>
            {/* THE NUMBER IS NOT EDITABLE, and the sentence says why rather than leaving him to
                wonder. It is the identity every peer resolves him by — his points, his offers and
                his history all hang off the pseudonym derived from it. */}
            {namingMsg ? (
              <p className={`text-sm ${namingMsg.startsWith('✓') ? 'text-success' : 'text-danger'}`}>
                {namingMsg}
              </p>
            ) : null}
          </div>

              {/* THE APOLOGY, WHERE THE BALANCE IS. A machine ate a card, an operator picked the
              wrong service, a customer was shorted — and until this existed the only repair
              the owner had was to invent a visit that never happened, which corrupts the data
              his own indicators are built on.
              THE REASON IS REQUIRED because the entry outlives the memory of it: the customer
              may ask in six months, and «+50» with nothing beside it is unanswerable. */}
          {action(catalog, 'loyalty.adjust') ? (
            <div className="mb-4 flex flex-col gap-2 rounded-xl bg-surface-2 p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium">تعديل رصيده</span>
                <Hint label="شرح المنح والخصم">
                  اكتب <span dir="ltr" className="tabular-nums">50</span> لمنحه نقاطاً،
                  و<span dir="ltr" className="tabular-nums">-50</span> لخصمها منه.
                </Hint>
              </div>
              {/* TWO ROWS, NOT ONE. Everything about this control was correct three attempts
                  ago except WHERE it stood: sharing a flex row with the number field left it the
                  narrow strip beside it, so one long sentence folded into a six-line tower. The
                  amount is short and the reason is a sentence — they do not belong side by side.
                  The lesson is the one worth keeping: I kept replacing the component when the
                  layout was what the owner was photographing. */}
              <div className="flex items-center gap-2">
                <input
                  value={adjustBy}
                  // FOLD FIRST. The class keeps `-` deliberately (this box takes a deduction
                  // too), but an Arabic keyboard's digits are not in it — so the owner
                  // adjusting a balance watched the field stay empty as he typed.
                  onChange={(e) => setAdjustBy(western(e.target.value).replace(/[^0-9-]/g, ''))}
                  inputMode="numeric"
                  dir="ltr"
                  placeholder="50"
                  aria-label="عدد النقاط"
                  className="h-11 w-full rounded-xl bg-surface-1 px-3 text-center text-lg tabular-nums shadow-sm"
                />
              </div>

                {/* UNDER THE FIELD, ON ONE LINE. Beside it the sentence folded into three ragged
                    lines next to a small box — the same mistake as the reason, one row up. A hint
                    is an aside: it belongs under the thing it explains, not in competition with it.
                    AND BY EXAMPLE, NOT BY GRAMMAR. «موجب/سالب» is the vocabulary of a form, and an
                    owner compensating a customer should not have to work out that the same box
                    also takes points away. He reads «-50» and knows. */}

                {/* THE REASON IS A CHOICE, NOT AN ESSAY. It stays required — the entry outlives
                    the memory of it and the customer asks six months later — but demanding free
                    text on a workshop tablet produces «تعويض», «خطا» and «..»: words written by
                    somebody who wanted the keyboard gone, answering nothing.
                    «أخرى» KEEPS THE DOOR OPEN, because a closed list always meets the case nobody
                    predicted, and a screen that refuses the unusual reason teaches the operator to
                    pick the nearest lie — worse than free text, because it looks like data. */}
                {/* A SHEET, NOT A DROPDOWN, and the third attempt at this control.
                    A native <select> renders its list outside the page — we cannot give it a
                    height, a scroll, or a readable line width, and on the owner's screen it opened
                    into something he could not move through. Six full sentences were never going
                    to fit a control designed for «نعم / لا».
                    THE DRAWER IS THE KIT'S OWN. It owns the whole width, scrolls inside itself,
                    closes on the backdrop, and each reason is a 44px row a thumb can hit — which
                    is the same answer the field screen reached for its keypad. */}
                <button
                  type="button"
                  onClick={() => setPickingReason(true)}
                  className="flex min-h-11 w-full items-center justify-between rounded-xl bg-surface-1 px-3 text-start text-sm shadow-sm"
                >
                  <span className={adjustNote ? '' : 'text-text-secondary'}>
                    {adjustNote || 'اختر السبب'}
                  </span>
                  <span className="text-text-secondary">▾</span>
                </button>

                <Drawer
                  open={pickingReason}
                  onClose={() => setPickingReason(false)}
                  title="سبب التعديل"
                  subtitle="يُحفَظ مع الحركة، ويُقرأ بعد أشهر"
                >
                  <ul className="flex flex-col gap-1">
                    {ADJUST_REASONS.map((r) => (
                      <li key={r}>
                        <button
                          type="button"
                          onClick={() => { setAdjustNote(r); setPickingReason(false); }}
                          className={`min-h-11 w-full rounded-xl px-3 text-start text-sm ${
                            adjustNote === r ? 'bg-accent text-white' : 'bg-surface-2'
                          }`}
                        >
                          {r}
                        </button>
                      </li>
                    ))}
                    <li>
                      {/* «أخرى» STAYS: a closed list always meets the case nobody predicted, and
                          forcing the nearest wrong reason corrupts the record while making it look
                          clean — worse than free text, because it reads as data. */}
                      <button
                        type="button"
                        onClick={() => { setAdjustNote(''); setPickingReason(false); }}
                        className="min-h-11 w-full rounded-xl bg-surface-2 px-3 text-start text-sm"
                      >
                        أخرى…
                      </button>
                    </li>
                  </ul>
                </Drawer>

              {/* THE FREE FIELD ONLY FOR «أخرى» — the common case is two taps, and the case
                  nobody predicted is still possible. */}
              {!(ADJUST_REASONS as readonly string[]).includes(adjustNote) ? (
                <input
                  value={adjustNote}
                  onChange={(e) => setAdjustNote(e.target.value)}
                  placeholder="اكتب السبب"
                  aria-label="سبب آخر"
                  className="h-11 rounded-xl bg-surface-1 px-3 text-sm shadow-sm"
                />
              ) : null}

              <Button
                disabled={adjusting || !adjustBy || adjustNote.trim().length < 3}
                onClick={async () => {
                  const a = action(catalog, 'loyalty.adjust');
                  const ref = c.subject_ref;
                  if (!a || !ref) return;
                  setAdjusting(true);
                  setAdjustMsg('');
                  try {
                    const r = await call<{ ok?: boolean; balance?: number; reason?: string }>(
                      session, a,
                      {
                        subject_ref: ref,
                        delta: Number(adjustBy),
                        note: adjustNote.trim(),
                        // ONE PRESS IS ONE INTENTION even when the network is slow: without a
                        // key a retried 50-point apology becomes a hundred, and neither side
                        // can tell which press was real.
                        idempotency_key: `adj-${ref}-${adjustBy}-${adjustNote.trim()}`,
                      },
                    );
                    if (r.ok === false) { setAdjustMsg(r.reason || 'تعذّر التعديل'); }
                    else {
                      setBalance((b) => (b ? { ...b, balance: r.balance ?? b.balance } : b));
                      setAdjustBy('');
                      setAdjustNote('');
                      setAdjustMsg('تم — وسُجّل السبب مع الحركة.');
                    }
                  } catch (e) {
                    setAdjustMsg(e instanceof Error ? e.message : 'تعذّر التعديل');
                  } finally {
                    setAdjusting(false);
                  }
                }}
              >
                حفظ التعديل
              </Button>
              {adjustMsg ? <p className="text-sm text-text-secondary">{adjustMsg}</p> : null}
            </div>
          ) : null}

          {/* ── «امسح بياناتي» — the request his customer makes to HIM ────────────────────────
              THE ESTABLISHMENT IS THE CONTROLLER under the PDPL and we are its processor: the
              customer asks the workshop, and the workshop owes him the erasure. The engine that
              performs it has been complete for months and the person who receives the request had
              no way to start it — the obligation was his and the button was nobody's.

              LAST ON THE TAB, AND ALONE. It is separated from the name and the points by a rule
              and by distance, because every other control here is a correction and this one is
              not: nothing on this screen, and nothing we hold, brings him back. */}
          {eraseAction ? (
            <div className="mt-6 flex flex-col gap-2 border-t border-border-subtle pt-4">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">حذف بيانات هذا العميل</span>
                <Hint>
                  حقّ نظامي لعميلك: إذا طلب حذف بياناته فالحذف عليك أنت لا علينا، ونحن ننفّذه
                  بأمرك. يُحذف اسمه ورقمه وزياراته ونقاطه ورسائله من كل مكان في المنصة — ولا يمكن
                  التراجع. ويبقى ما يلزمنا القانون بحفظه: الفواتير والسجلّ المحاسبي، لأن حذفها
                  مخالفة أخرى.
                </Hint>
              </div>

              {!eraseAsked ? (
                <div>
                  <Button variant="outline" onClick={() => { setEraseAsked(true); setEraseMsg(''); }}>
                    حذف بياناته
                  </Button>
                </div>
              ) : (
                /* TWO STEPS, AND THE SECOND ONE NAMES HIM. A confirmation that says «متأكد؟» is a
                   reflex; one that repeats whose data is about to go is a decision. */
                <div className="flex flex-col gap-2 rounded-card bg-surface-2 p-3">
                  <p className="text-sm">
                    سيُحذف نهائياً كل ما لدينا عن {record?.customer?.name || 'هذا العميل'} — بلا رجعة.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="danger"
                      disabled={erasing}
                      onClick={async () => {
                        setErasing(true); setEraseMsg('');
                        try {
                          const r = await call<{ ok?: boolean; reason?: string }>(
                            session, eraseAction, { customer_id: id ?? '' });
                          if (r?.ok === false) { setEraseMsg(r.reason || 'تعذّر الحذف'); return; }
                          // AND WE LEAVE THE PAGE. Staying on the record of a person we just
                          // erased would render his name off a copy in the browser's memory —
                          // which is the one place the fan-out cannot reach.
                          navigate('/customers', { replace: true });
                        } catch (e) {
                          setEraseMsg(e instanceof Error ? e.message : 'تعذّر الحذف');
                        } finally {
                          setErasing(false);
                        }
                      }}
                    >
                      نعم، احذف نهائياً
                    </Button>
                    <Button variant="outline" disabled={erasing}
                            onClick={() => setEraseAsked(false)}>
                      تراجع
                    </Button>
                  </div>
                  {eraseMsg ? <p className="text-sm text-danger">{eraseMsg}</p> : null}
                </div>
              )}
            </div>
          ) : null}
        </section>
      ) : null}

      {/* ── his rhythm, and the one number an owner sometimes knows better ───────────────
          THE ADAPTIVE ENGINE WAS INVISIBLE. It watches how often each customer comes back and
          moves his reminder toward it (§5.2) — the feature the whole product's timing rests on —
          and no screen ever showed a single learned number. An owner could not see it, could not
          check it, and could not correct it on the one customer he knows by name.

          AND CORRECTING IT STOPS THE LEARNING for that pair, which the route says in its own
          words. Silently resuming adaptation would walk his number back toward the observed
          rhythm over the next few visits, and he would conclude the setting does not work. */}
      {tab === 'overview' && cycles.length ? (
        <section className="flex flex-col gap-2 rounded-card bg-surface-1 p-4 shadow-sm">
          <div className="flex items-center gap-2">
            <h2 className="text-sm text-text-secondary">دورته عندك</h2>
            <Hint>
              كم يوماً يمرّ عادةً قبل أن يعود لكل خدمة — نتعلّمها من زياراته هو، لا من متوسط عام.
              وإن كنت تعرف رقمه أفضل منّا فاكتبه، ونتوقّف عن التعديل لهذه الخدمة.
            </Hint>
          </div>
          {cycles.slice(0, 6).map((r) => (
            <div key={r.id || r.service_id} className="flex flex-wrap items-center justify-between gap-2 border-t border-border-subtle pt-2 first:border-0 first:pt-0">
              <span className="flex min-w-0 flex-col">
                <span className="text-sm">{r.service_name || r.service_id}</span>
                <span className="text-xs text-text-secondary">
                  {/* STILL AN ESTIMATE, AND IT SAYS SO. `learned` false means the number is the
                      service's default wearing his name. */}
                  {r.learned
                    ? `تعلّمناها من ${r.observations ?? 0} زيارة`
                    : 'تقدير مبدئي — لم نتعلّمها بعد'}
                  {r.pinned ? ' · مثبّتة بيدك' : ''}
                </span>
              </span>
              <span className="flex items-center gap-2">
                <input
                  type="number"
                  min={1}
                  dir="ltr"
                  defaultValue={String(Math.round(r.interval_days ?? 0))}
                  aria-label={`دورة ${r.service_name || r.service_id}`}
                  onBlur={async (e) => {
                    const raw = e.target.value.trim();
                    const n = Number(raw);
                    if (!raw || !n || n === Math.round(r.interval_days ?? 0)) return;
                    const a = action(catalog, 'reminders.set_rule');
                    if (!a) return;
                    setPinMsg('');
                    try {
                      await call(session, a, { service_id: r.id || r.service_id || '',
                                               interval_days: n });
                      setPinMsg('ثبّتنا رقمك — ولن نعدّله تلقائياً لهذه الخدمة.');
                    } catch {
                      setPinMsg('تعذّر الحفظ.');
                    }
                  }}
                  className="h-10 w-20 rounded-lg bg-surface-2 px-2 text-center tabular-nums"
                />
                <span className="text-xs text-text-secondary">يوماً</span>
              </span>
            </div>
          ))}
          {pinMsg ? <p className="text-xs text-text-secondary">{pinMsg}</p> : null}
        </section>
      ) : null}

      {tab === 'messages' ? (
        <section className="rounded-card bg-surface-1 p-4 shadow-sm">
          {/* WHAT WENT TO HIM, AND WHAT DID NOT — WITH ITS REASON. «لماذا لم تصل رسالة عميلي؟» is
              the only question this engine generates, and every correct refusal (quiet hours, the
              ceiling, consent, an unapproved template) reads as a fault until it is named. */}
          <h2 className="mb-3 text-sm text-text-secondary">رسائله</h2>
          {isLoading(sends) ? <Skeleton height={80} /> : hasFailed(sends) ? (
            // «لم يخرج له شيء» ANSWERS THE ONE QUESTION THIS SCREEN EXISTS FOR. Said after a
            // failed read, the owner concludes the engine never wrote to his customer at all.
            <p className="text-sm text-text-secondary">
              تعذّرت قراءة رسائله الآن — والخلل عندنا. أعد المحاولة بعد قليل.
            </p>
          ) : sends.length === 0 ? (
            <p className="text-sm text-text-secondary">لم يخرج له شيء بعد.</p>
          ) : (
            <ul className="flex flex-col gap-2 text-sm">
              {sends.slice(0, 20).map((x, i) => (
                <li key={i} className="flex items-center justify-between gap-2">
                  <span className="flex flex-col">
                    <span>{x.template_type || 'رسالة'}</span>
                    {x.reason ? (
                      <span className="text-xs text-text-secondary">{x.reason}</span>
                    ) : null}
                  </span>
                  <span className="flex items-center gap-2">
                    <span className="text-xs text-text-secondary">{when(x.at ?? 0)}</span>
                    {x.outcome === 'sent'
                      ? <Badge tone="success">خرجت</Badge>
                      : <Badge tone="neutral">لم تخرج</Badge>}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}

    </div>
  );
}
