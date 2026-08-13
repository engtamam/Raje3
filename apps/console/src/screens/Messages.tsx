/**
 * «رسائلي» — what goes out in my name.
 *
 * IT OPENS ON WHAT IS BEING SENT NOW, never on a setup screen. That is the rule for every section
 * (§10.8), and it matters most here because this is the one an owner opens when he is nervous:
 * something went out, or did not, and he wants to see it rather than configure it.
 *
 * AND THE WORDS «قالب» AND «فئة» AND «اعتماد» DO NOT APPEAR. They are ours — Meta's vocabulary and
 * our library's — and an owner who meets them concludes the product needs study. He picks a TONE
 * once and every wording follows; that is the whole of his involvement with sixty-six templates.
 *
 * TWO TABS, BECAUSE THE TWO LISTS ANSWER DIFFERENT QUESTIONS. Stacked in one scroll, an owner
 * hunting for "did my campaign go out" scrolls past four automatic occasions every time, and the
 * thing he came for is never the thing on screen.
 *
 * AND «حملاتي» IS SHOWN LOCKED WHEN HIS PLAN HAS NO CAMPAIGNS, never removed. It used to vanish —
 * `campaigns === null` rendered nothing at all — and a section that disappears reads as a fault,
 * while a capability nobody can see is one nobody can buy.
 */
import { useEffect, useRef, useState } from 'react';
import { Badge } from '@base-ui/design-system/Badge';
import { EmptyState } from '@base-ui/design-system/EmptyState';
import { Segmented } from '@base-ui/design-system/Segmented';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import { Lock } from 'lucide-react';
import { Button } from '@base-ui/design-system/Button';
import { Launch } from './Launch';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';

interface Campaign { id: string; name?: string; goal?: string; state?: string; sent?: number }

/** One line of the send log. `reason` is the service's own sentence — never re-worded here. */
interface LogRow {
  id: string;
  at?: number;
  outcome?: string;
  reason?: string;
  template_name?: string;
  cls?: string;
  subject_ref?: string;
}
/** When it happened, in the words an owner uses. Same shape as «عملائي» — one habit, not two. */
function when(at: number): string {
  if (!at) return '';
  const days = Math.floor((Date.now() / 1000 - at) / 86_400);
  if (days <= 0) return 'اليوم';
  if (days === 1) return 'أمس';
  return `قبل ${days} أيام`;
}

interface Run { at?: number; sent?: number; suppressed?: number; reason?: string }

interface Schedule {
  schedule: { id?: string; kind?: string; due_at?: number; subject_ref?: string }[];
  count: number;
}

/** A customer as operations answers with him — the only service on the platform that holds names. */
interface Who { id: string; name?: string; phone?: string; subject_ref?: string }

/**
 * The occasions, by their names rather than by their template ids.
 *
 * `kind` matches what the scheduler stores, which is how a count is attached to each without the
 * screen inventing a mapping. A kind the backend adds later and this list does not name simply
 * does not appear here — which is the safe direction: a missed row is a gap, an invented one is a
 * promise the engine does not keep.
 */
const OCCASION: Record<string, string> = {
  reminder: 'تذكير موعد',
  follow_up: 'اطمئنان بعد الزيارة',
  review_request: 'طلب تقييم',
  campaign: 'حملة',
};

/** How far off it is, in the words he would use — «بعد 3 أيام», not a date he has to subtract. */
function dueIn(at: number): string {
  const days = Math.round((at - Date.now() / 1000) / 86_400);
  if (days < 0) return 'تأخّرت';
  if (days === 0) return 'اليوم';
  if (days === 1) return 'بكرة';
  return `بعد ${days} أيام`;
}

/** 966xxxxxxxxx → 05xxxxxxxx. The form he reads on his own phone. */
function asLocal(phone: string): string {
  const d = (phone || '').replace(/\D/g, '');
  return d.startsWith('966') ? `0${d.slice(3)}` : d;
}

export function MessagesScreen({ session, catalog }: { session: Session; catalog: Catalog }) {
  const [tab, setTab] = useState<'auto' | 'campaigns' | 'log'>('auto');

  /**
   * WHAT WENT OUT AND WHAT DID NOT, WITH THE REASON.
   *
   * `reminders.log` describes itself as the most important route this service has, and no screen
   * called it. Every correct suppression we make — quiet hours, the daily ceiling, missing
   * consent, an unapproved template — therefore reads to the owner as a fault, and every refusal
   * we wrote in plain Arabic goes to a place nobody opens. That is not a missing feature; it
   * turns every rule in the engine into a suspected bug.
   */
  const [log, setLog] = useState<LogRow[] | null>(null);
  const [only, setOnly] = useState<'' | 'sent' | 'suppressed'>('');
  const [schedule, setSchedule] = useState<Schedule | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[] | null>(null);
  /** The composer, open only when he asks for it — this tab is a list first. */
  const [launching, setLaunching] = useState(false);
  /** One campaign's sends, open under its row. `null` is closed — it is not a screen of its own. */
  const [runs, setRuns] = useState<Run[] | null>(null);
  /**
   * PSEUDONYM → THE CUSTOMER, and this is what made the whole section useless without it.
   *
   * reminders holds no names by design (see operations' resolve route), so every row it answers
   * with is an opaque `subject_ref`. The screen therefore had nothing person-shaped to show and
   * fell back on counting message TYPES — «تذكير الموعد: 1 بانتظار الإرسال» — which answers a
   * question no shop owner has ever asked. He wants to know WHO is about to be messaged, and
   * whether he should stop it.
   *
   * ONE JOIN, WHERE THE NAMES ALREADY ARE. Same call «عملائي» uses for its overdue list; an
   * unknown ref is simply absent from the answer and its row falls back to «عميل».
   */
  const [who, setWho] = useState<Record<string, Who>>({});
  /**
   * WHAT WE HAVE ALREADY ASKED FOR — and it cannot be derived from `who`.
   *
   * THE LOOP THIS PREVENTS, WHICH RAN IN PRODUCTION. The effect below filtered its refs by "not in
   * `who`" and depended on `who`. A pseudonym operations does not return — an erased customer, or
   * one whose row moved — never lands in the map, so the filter kept selecting it, the effect kept
   * firing, and the console hammered `/customers/resolve` until the gateway answered 429.
   *
   * An unanswered ref is still an ASKED ref. A set of what we sent, in a ref rather than state, so
   * recording it cannot itself trigger the effect that reads it.
   */
  const asked = useRef<Set<string>>(new Set());

  // THE LOG IS FETCHED WHEN ITS TAB OPENS, not with the screen. It is the heaviest read here and
  // the least often wanted — an owner opens «رسائلي» to see what is coming, and pays for the log
  // only when he asks why something did not.
  useEffect(() => {
    if (tab !== 'log') return;
    const a = action(catalog, 'reminders.log');
    if (!a) { setLog([]); return; }
    setLog(null);
    call<{ log: LogRow[] }>(session, a, only ? { outcome: only, limit: 100 } : { limit: 100 })
      .then((x) => setLog(x.log ?? []))
      .catch(() => setLog([]));
  }, [tab, only, session, catalog]);

  useEffect(() => {
    const s = action(catalog, 'reminders.list_schedule');
    if (s) {
      call<Schedule>(session, s, { state: 'pending', limit: 200 })
        .then(setSchedule)
        .catch(() => setSchedule({ schedule: [], count: 0 }));
    } else {
      setSchedule({ schedule: [], count: 0 });
    }

    loadCampaigns();
    if (!action(catalog, 'campaigns.list')) {
      // NOT AN ERROR AND NOT AN EMPTY LIST: the plan does not include campaigns. `null` is the
      // LOCKED state — the tab is still there, and it says why.
      setCampaigns(null);
    }
  }, [session, catalog]);

  /**
   * THE JOIN, RUN WHENEVER EITHER LIST CHANGES.
   *
   * One call for both lists: the queue and the log draw from the same pool of customers, and two
   * separate resolutions would ask operations for the same person twice on every tab switch.
   * Refs already resolved are not asked for again — the map only grows.
   */
  useEffect(() => {
    const resolve = action(catalog, 'operations.customers_by_refs');
    if (!resolve) return;
    const refs = [
      ...(schedule?.schedule ?? []).map((r) => r.subject_ref),
      ...(log ?? []).map((r) => r.subject_ref),
    ].filter((r): r is string => Boolean(r) && !asked.current.has(r!));
    if (refs.length === 0) return;
    // MARKED BEFORE THE CALL, not after it. A failed request must not put the ref back in the
    // queue: the next render would ask again, and a service that is down would be asked on every
    // keystroke of the screen's life.
    for (const r of refs) asked.current.add(r);

    let stale = false;
    call<{ customers: Who[] }>(session, resolve, { refs: [...new Set(refs)].slice(0, 200) })
      .then((x) => {
        if (stale) return;
        setWho((prev) => {
          const next = { ...prev };
          for (const c of x.customers ?? []) if (c.subject_ref) next[c.subject_ref] = c;
          return next;
        });
      })
      // A FAILED JOIN IS NOT A FAILED SCREEN. The rows still say what goes out and when; they
      // fall back to «عميل» for the name, which is worse than a name and far better than nothing.
      .catch(() => null);
    return () => { stale = true; };
  }, [schedule, log, session, catalog]);

  /** Re-read what is queued — after a cancel, so the row he just stopped is gone. */
  const loadSchedule = () => {
    const a = action(catalog, 'reminders.list_schedule');
    if (!a) return;
    call<Schedule>(session, a).then(setSchedule)
      .catch(() => setSchedule({ schedule: [], count: 0 }));
  };

  const openRuns = async (id: string) => {
    const a = action(catalog, 'campaigns.runs');
    if (!a) return;
    // AN EMPTY LIST RATHER THAN A CLOSED PANEL ON FAILURE: he asked a question, and silence is
    // the one answer that sends him to support.
    setRuns(await call<{ runs: Run[] }>(session, a, { campaign_id: id })
      .then((r) => r.runs ?? []).catch(() => []));
  };

  /** Re-read the list — after a launch, so the campaign he just started is on screen. */
  const loadCampaigns = () => {
    const c = action(catalog, 'campaigns.list');
    if (!c) return;
    call<{ campaigns: Campaign[] }>(session, c)
      .then((x) => setCampaigns(x.campaigns ?? []))
      .catch(() => setCampaigns([]));
  };

  return (
    <div className="flex flex-col gap-4 p-4">
      <Segmented
        // FULL WIDTH, SPLIT EVENLY, NEVER WRAPPED. The kit's Segmented is
        // `inline-flex flex-wrap`, which on a phone stacks two long Arabic labels into a
        // ragged block half the screen wide. It takes a className and merges with
        // tailwind-merge, so this is a fix at the call site rather than a fork of the kit.
        className="flex w-full [&>button]:flex-1 [&>button]:whitespace-nowrap"
        ariaLabel="أقسام الرسائل"
        value={tab}
        onChange={setTab}
        options={[
          { value: 'auto', label: 'ما يُرسَل تلقائياً' },
          { value: 'campaigns', label: 'حملاتي' },
          { value: 'log', label: 'ما خرج ولم يخرج' },
        ]}
      />

      {tab === 'auto' ? (
      <section className="flex flex-col gap-3">
        {/* ── the queue, as PEOPLE ────────────────────────────────────────────────────────────
            «مين بيوصله إيش، ومتى» — and the one act that belongs here, which is stopping one of
            them. The old shape was four fixed rows, one per message TYPE, each carrying a count
            and three dashes: a shop with one queued reminder read «تذكير الموعد … 1» and «—» three
            times, and could not tell whose reminder it was without opening a nested panel. Nothing
            on the screen was about a customer, which is the only thing this section is about. */}
        {schedule === null ? (
          <Skeleton height={160} />
        ) : (schedule.schedule ?? []).length === 0 ? (
          <EmptyState
            title="ما في رسائل بانتظار الخروج"
            description="كل زيارة تُسجَّل تجدول تذكيرها واطمئنانها — وتظهر هنا قبل أن تخرج، فتوقف ما تريد."
          />
        ) : (
          <>
            <p className="px-1 text-sm text-text-secondary">
              {`${schedule.schedule.length} رسالة بانتظار الخروج — أوقف أياً منها قبل موعدها.`}
            </p>
            <ul className="flex flex-col gap-2">
              {[...schedule.schedule]
                .sort((a, b) => (a.due_at ?? 0) - (b.due_at ?? 0))
                .slice(0, 100)
                .map((r, i) => {
                  const person = r.subject_ref ? who[r.subject_ref] : undefined;
                  return (
                    <li key={r.id || i}
                        className="flex items-center justify-between gap-3 rounded-card bg-surface-1 p-3 shadow-sm">
                      <span className="flex min-w-0 flex-col">
                        {/* THE NAME IF HE WROTE ONE, THE NUMBER IF HE DID NOT — never a
                            pseudonym. Names are optional at the counter (§4.3), so the phone is
                            the fallback that always identifies somebody. */}
                        <span className="truncate font-medium">
                          {person?.name || (person?.phone ? asLocal(person.phone) : 'عميل')}
                        </span>
                        <span className="truncate text-sm text-text-secondary">
                          {OCCASION[r.kind ?? ''] ?? 'رسالة'}
                          {r.due_at ? ` · ${dueIn(r.due_at)}` : ''}
                        </span>
                      </span>
                      {/* CANCELS THE MESSAGE, NOT THE RULE — the route's own words, repeated here
                          so he is not surprised: the next visit schedules a new one. */}
                      {action(catalog, 'reminders.cancel') && r.id ? (
                        <Button
                          variant="ghost"
                          onClick={async () => {
                            const a2 = action(catalog, 'reminders.cancel');
                            if (!a2 || !r.id) return;
                            await call(session, a2, { id: r.id }).catch(() => null);
                            loadSchedule();
                          }}
                        >
                          أوقفها
                        </Button>
                      ) : null}
                    </li>
                  );
                })}
            </ul>
            <p className="px-1 text-xs text-text-secondary">
              الإيقاف يوقف هذه الرسالة وحدها — والزيارة القادمة تجدول واحدة جديدة.
            </p>
          </>
        )}
      </section>
      ) : tab === 'log' ? (
        <section className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <Segmented
              className="flex w-full [&>button]:flex-1 [&>button]:whitespace-nowrap"
              ariaLabel="تصفية السجل"
              value={only}
              onChange={(v) => setOnly(v as '' | 'sent' | 'suppressed')}
              options={[
                { value: '', label: 'الكل' },
                { value: 'sent', label: 'خرجت' },
                // THE ONE HE CAME FOR. Named by what happened to the message rather than by our
                // word for it: «مكبوحة» is a term from the engine, and he is asking why his
                // customer heard nothing.
                { value: 'suppressed', label: 'لم تخرج' },
              ]}
            />
            <p className="px-1 text-sm text-text-secondary">
              كل رسالة لم تخرج، ومعها سببها — لا شيء يُمنع بصمت.
            </p>
          </div>

          {log === null ? (
            <Skeleton height={120} />
          ) : log.length === 0 ? (
            // NOT AN APOLOGY AND NOT A FAULT. A shop whose engine has not had to refuse anything
            // yet is a shop working correctly, and the sentence says which.
            <EmptyState
              title="لا شيء في السجل بعد"
              description="حين تخرج رسالة أو تُمنع، تجدها هنا بسببها."
            />
          ) : (
            <ul className="flex flex-col gap-2">
              {log.map((r) => (
                <li key={r.id} className="rounded-card bg-surface-1 p-3 shadow-sm">
                  <div className="flex items-center justify-between gap-3">
                    {/* WHO IT WAS ABOUT, FIRST. A log line that says only «لم تخرج» and a reason
                        leaves the owner unable to act: he cannot call the customer, cannot check
                        the number, cannot tell whether it matters. */}
                    <span className="flex min-w-0 flex-col">
                      <span className="truncate font-medium">
                        {(() => {
                          const person = r.subject_ref ? who[r.subject_ref] : undefined;
                          return person?.name
                            || (person?.phone ? asLocal(person.phone) : 'عميل');
                        })()}
                      </span>
                      <span className="text-xs text-text-secondary tabular-nums">
                        {r.at ? `${when(r.at)} · ${OCCASION[r.cls ?? ''] ?? 'رسالة'}` : ''}
                      </span>
                    </span>
                    <Badge tone={r.outcome === 'sent' ? 'success' : 'warning'}>
                      {r.outcome === 'sent' ? 'خرجت' : 'لم تخرج'}
                    </Badge>
                  </div>
                  {/* THE SERVICE'S OWN SENTENCE, WORD FOR WORD. Every refusal in the engine
                      returns Arabic a shop owner can act on, and re-wording it here would give
                      one rule two vocabularies — which is how an owner comes to believe there
                      are two problems. */}
                  {r.reason ? <p className="mt-1">{r.reason}</p> : null}
                  {r.template_name ? (
                    <p className="mt-1 text-sm text-text-secondary" dir="ltr">{r.template_name}</p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : campaigns === null ? (
        // LOCKED, NOT HIDDEN — and it names the thing rather than the plan tier, because "campaigns
        // are in a higher plan" is a fact about our price list and "reach a group of your customers
        // with one offer" is a fact about his shop.
        <section className="rounded-card bg-surface-1 p-4 text-center shadow-sm">
          {/* The kit's EmptyState takes a rendered node, not a component — the same shape «فريقي»
              already uses for its locked branches tab. */}
          <Lock size={20} className="mx-auto mb-3 text-text-secondary" aria-hidden />
          <EmptyState
            title="الحملات ليست في باقتك"
            description="الحملة تصل بعرض واحد إلى شريحة من عملائك الموافقين — بدل رسالة رسالة."
          />
        </section>
      ) : (
        <section className="flex flex-col gap-3 rounded-card bg-surface-1 p-4 shadow-sm">
          {/* THE BUTTON THAT DID NOT EXIST. The engine — goals with their locks, the audience
              rules, the spread across days, the reserved share, the per-send log — was complete
              and unreachable; this tab listed campaigns and explained what a campaign is for,
              which is a brochure for a feature its owner cannot use. */}
          {launching ? (
            <Launch session={session} catalog={catalog}
                    onDone={() => { setLaunching(false); loadCampaigns(); }} />
          ) : action(catalog, 'campaigns.create') ? (
            <div><Button onClick={() => setLaunching(true)}>أطلق حملة</Button></div>
          ) : null}

          {campaigns.length === 0 ? (
            <EmptyState
              title="لم تُطلق حملة بعد"
              description="اختر شريحة من عملائك الموافقين وأرسل لهم عرضاً."
            />
          ) : (
            <ul className="flex flex-col gap-2">
              {campaigns.map((c) => (
                <li key={c.id} className="flex items-center justify-between">
                  <span>{c.name || c.goal || 'حملة'}</span>
                  <span className="flex items-center gap-2">
                    {typeof c.sent === 'number' ? (
                      <span className="tabular-nums text-text-secondary">{c.sent} أُرسلت</span>
                    ) : null}
                    {c.state ? <Badge tone={c.state === 'running' ? 'accent' : 'neutral'}>{c.state}</Badge> : null}
                    {/* «ماذا حدث» — THE MOST IMPORTANT ROUTE THIS SERVICE HAS, by its own note:
                        "it didn't arrive" is the only complaint this product generates, and every
                        correct refusal (consent, the ceiling, quiet hours) reads as a fault until
                        it is named. It was declared and called by nothing. */}
                    {action(catalog, 'campaigns.runs') ? (
                      <Button variant="ghost" onClick={() => void openRuns(c.id)}>ماذا حدث</Button>
                    ) : null}
                    {/* STOPPING A STANDING RULE, not deleting its history. Only while it runs —
                        a pause button on a finished campaign is a control that does nothing. */}
                    {c.state === 'running' && action(catalog, 'campaigns.pause') ? (
                      <Button
                        variant="ghost"
                        onClick={async () => {
                          const a2 = action(catalog, 'campaigns.pause');
                          if (!a2) return;
                          await call(session, a2, { campaign_id: c.id }).catch(() => null);
                          loadCampaigns();
                        }}
                      >
                        أوقفها
                      </Button>
                    ) : null}
                  </span>
                </li>
              ))}
            </ul>
          )}

          {/* WHAT ACTUALLY WENT OUT, PER SEND, WITH ITS REASON. Opened under the campaign it
              belongs to rather than on a page of its own: the question is always about ONE
              campaign, and a combined log is a log he has to filter before he can read it. */}
          {runs ? (
            <div className="flex flex-col gap-2 rounded-lg bg-surface-2 p-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">ماذا حدث</span>
                <Button variant="ghost" onClick={() => setRuns(null)}>إغلاق</Button>
              </div>
              {runs.length === 0 ? (
                <p className="text-sm text-text-secondary">لم تخرج إرسالة بعد.</p>
              ) : (
                runs.map((r, i) => (
                  <div key={i} className="flex items-center justify-between gap-2 border-t border-border-subtle pt-2 first:border-0 first:pt-0">
                    <span className="flex flex-col">
                      <span className="text-sm tabular-nums">
                        {r.sent ?? 0} وصلت · {r.suppressed ?? 0} امتنعت
                      </span>
                      {r.reason ? (
                        <span className="text-xs text-text-secondary">{r.reason}</span>
                      ) : null}
                    </span>
                    <span className="text-xs text-text-secondary">{when(r.at ?? 0)}</span>
                  </div>
                ))
              )}
            </div>
          ) : null}
        </section>
      )}
    </div>
  );
}
