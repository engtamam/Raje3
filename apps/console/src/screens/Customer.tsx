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
import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Badge } from '@base-ui/design-system/Badge';
import { Segmented } from '@base-ui/design-system/Segmented';
import { Button } from '@base-ui/design-system/Button';
import { EmptyState } from '@base-ui/design-system/EmptyState';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import { action, call, type Catalog } from '../catalog';
import { partitionOffers, remaining, type Offer } from '../offers';
import type { Session } from '../session';

interface Record {
  customer: { id: string; phone: string; name?: string; subject_ref?: string; visits?: number };
  visits: { id: string; services?: string; occurred_at?: number }[];
  /** His vehicles, when the sector has any. The record has always carried them. */
  assets?: { id: string; plate?: string; make?: string; model?: string }[];
}

interface Balance { balance: number; rewards?: { id: string; name: string; cost: number }[] }
interface Move { at?: number; delta?: number; reason?: string; kind?: string }
interface Send { at?: number; template_type?: string; outcome?: string; reason?: string }

/**
 * The number as HE knows it. Storage keeps E.164 — «966573579663» — because that is what the
 * network needs, and showing it raw asks an owner to translate his own customer's phone in his
 * head. He reads 05XXXXXXXX, so that is what the screen prints.
 */
export function local(phone: string): string {
  const d = (phone || '').replace(/\D/g, '');
  if (d.startsWith('966')) return `0${d.slice(3)}`;
  if (d.startsWith('05')) return d;
  return phone;
}

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

export function CustomerScreen({ session, catalog }: { session: Session; catalog: Catalog }) {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const [record, setRecord] = useState<Record | null | undefined>(undefined);
  const [offers, setOffers] = useState<Offer[] | null>(null);
  const [balance, setBalance] = useState<Balance | null>(null);
  const [moves, setMoves] = useState<Move[] | null>(null);
  const [sends, setSends] = useState<Send[] | null>(null);
  const [tab, setTab] = useState<'overview' | 'points' | 'messages' | 'manage'>('overview');
  const [adjustBy, setAdjustBy] = useState('');
  const [adjustNote, setAdjustNote] = useState('');
  const [adjusting, setAdjusting] = useState(false);
  const [adjustMsg, setAdjustMsg] = useState('');
  const [nameDraft, setNameDraft] = useState('');
  const [namingMsg, setNamingMsg] = useState('');

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
        if (!o || !ref) { setOffers([]); return; }
        call<{ offers: Offer[] }>(session, o, { subject_ref: ref, include_expired: true })
          .then((x) => { if (!stale) setOffers(x.offers ?? []); })
          // An offers read that fails must not empty the record: his visits are still true.
          .catch(() => { if (!stale) setOffers([]); });

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

  if (record === undefined) return <div className="p-4"><Skeleton height={240} /></div>;

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
  const [live, past] = partitionOffers(offers ?? []);

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
            {c.name || local(c.phone)}
          </span>
          <span
            dir={c.name ? 'ltr' : undefined}
            className="text-sm text-text-secondary tabular-nums"
          >
            {c.name ? local(c.phone) : 'بلا اسم'}
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
        className="flex w-full flex-nowrap overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden [&>button]:shrink-0 [&>button]:whitespace-nowrap sm:[&>button]:flex-1"
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
      <section className="rounded-card bg-surface-1 p-4 shadow-sm">
        <h2 className="mb-3 text-sm text-text-secondary">عروضه</h2>
        {offers === null ? (
          <Skeleton height={90} />
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
                <p className="mt-2 flex items-center gap-2 text-sm">
                  <Badge tone="accent">ساري</Badge>
                  <span className="text-text-secondary">{remaining(o.expires_at)}</span>
                  <span className="text-text-secondary">· وصله {when(o.sent_at)}</span>
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
              <li key={v.id} className="flex items-center justify-between gap-3">
                <span>{v.services || 'زيارة'}</span>
                <span className="text-sm text-text-secondary">{when(v.occurred_at ?? 0)}</span>
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
          {balance === null ? (
            <p className="text-sm text-text-secondary">
              لا يوجد برنامج نقاط في باقتك، أو تعذّرت قراءة رصيده.
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
              {moves === null ? <Skeleton height={60} /> : moves.length === 0 ? (
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
            <span className="text-sm font-medium">اسمه</span>
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
            <p className="text-xs text-text-secondary">
              الرقم لا يُعدَّل — هو هوية العميل عند كل أقسام النظام. رقمٌ خاطئ يعني عميلاً جديداً.
            </p>
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
              <span className="text-sm font-medium">تعديل رصيده</span>
              <div className="flex gap-2">
                <input
                  value={adjustBy}
                  onChange={(e) => setAdjustBy(e.target.value.replace(/[^0-9-]/g, ''))}
                  inputMode="numeric"
                  dir="ltr"
                  placeholder="+50"
                  aria-label="عدد النقاط"
                  className="h-11 w-24 rounded-xl bg-surface-1 px-3 text-center tabular-nums shadow-sm"
                />
                <input
                  value={adjustNote}
                  onChange={(e) => setAdjustNote(e.target.value)}
                  placeholder="السبب — مثال: تعويض عن خطأ في التسجيل"
                  aria-label="سبب التعديل"
                  className="h-11 min-w-0 flex-1 rounded-xl bg-surface-1 px-3 text-sm shadow-sm"
                />
              </div>
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


        </section>
      ) : null}

      {tab === 'messages' ? (
        <section className="rounded-card bg-surface-1 p-4 shadow-sm">
          {/* WHAT WENT TO HIM, AND WHAT DID NOT — WITH ITS REASON. «لماذا لم تصل رسالة عميلي؟» is
              the only question this engine generates, and every correct refusal (quiet hours, the
              ceiling, consent, an unapproved template) reads as a fault until it is named. */}
          <h2 className="mb-3 text-sm text-text-secondary">رسائله</h2>
          {sends === null ? <Skeleton height={80} /> : sends.length === 0 ? (
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
