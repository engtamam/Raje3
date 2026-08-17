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
 * FOUR TABS, BECAUSE THEY ANSWER FOUR DIFFERENT QUESTIONS: what the system sends at all, what is
 * about to go, what I launched myself, and what happened. Stacked in one scroll, an owner hunting
 * for "did my campaign go out" scrolls past everything else every time.
 *
 * AND IT OPENS ON «ما يُرسَل», which is the question the section is named after and the one it
 * could not answer for its whole life: the only way to stop a KIND of message was to cancel its
 * rows one at a time as they appeared.
 *
 * THE OLD NOTE, KEPT BECAUSE THE REASON STILL HOLDS. Stacked in one scroll, an owner
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
import { DENIED, hasFailed, isDenied, isLoading, isReady, type Loading } from '../loading';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import { Toggle } from '@base-ui/design-system/Toggle';
import { Lock } from 'lucide-react';
import { Button } from '@base-ui/design-system/Button';
import { Launch } from './Launch';
import { LockedCard } from './Locked';
import { MessagePreview } from './MessagePreview';
import { owns, type Owned } from '../apps';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';
import { digitsOnly } from '../digits';

/**
 * A campaign as the service answers with it. `state` is one of `draft|active|paused|done` — and
 * the screen used to compare it against `'running'`, a value the model has never had, so the
 * pause button never appeared on a single live campaign and «أوقفها» was unreachable for its
 * whole life. There is no `name` either: a campaign is named by its goal.
 */
interface Campaign { id: string; goal?: string; state?: string; sent?: number }

/** A goal's name, so a row reads «رجّع اللي غابوا» rather than `win_back`. */
const GOAL_TITLE: Record<string, string> = {
  win_back: 'رجّع اللي غابوا',
  reward_loyal: 'كافئ المخلصين',
  announce: 'أعلن جديدك',
  occasion: 'هنّئ في مناسبة',
  awareness: 'وعِّ عملاءك',
  service_offer: 'عرض على خدمة',
};

/** The four states, in his words rather than ours. */
const STATE: Record<string, string> = {
  active: 'تعمل',
  paused: 'موقوفة',
  done: 'انتهت',
  draft: 'مسودّة',
};

/** One line of the send log. `reason` is the service's own sentence — never re-worded here. */
interface LogRow {
  id: string;
  /** Where the visit behind this message happened. Empty for a campaign, and for a shop that
   *  labels nothing — «غير محدَّد» is a real answer here, not a gap. */
  branch_id?: string;
  at?: number;
  outcome?: string;
  /** WHAT HAPPENED AFTER IT LEFT. `outcome: 'sent'` only ever meant «we handed it to Meta», and
   *  the screen said «خرجت» — which an owner reads as «وصلت». These two carry the answer to the
   *  question he is actually asking, and absent means «لم نسمع بعد»: not delivered, not failed. */
  delivered_at?: number;
  read_at?: number;
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

/**
 * One thing the system does in his name. Every field is the SERVER'S — the label, and the sentence
 * saying when it fires. A screen that held its own copy of either would drift from the engine the
 * first time a reason changed, and the owner would be reading a promise nothing keeps.
 */
interface ReasonRow {
  id: string;
  label: string;
  when: string;
  on: boolean;
  can_switch: boolean;
  can_retext: boolean;
  template?: string;
}

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
  const d = digitsOnly(phone || '');
  return d.startsWith('966') ? `0${d.slice(3)}` : d;
}

export function MessagesScreen(
  { session, catalog, owned }:
  { session: Session; catalog: Catalog; owned?: Loading<Owned> },
) {
  const [tab, setTab] = useState<'reasons' | 'auto' | 'campaigns' | 'log'>('reasons');

  /**
   * WHAT SENDS IN HIS NAME — the question this whole section is named after, and the one it could
   * not answer. «رسائلي» listed a queue and a log: what is about to go and what already went. It
   * never said WHAT THE SYSTEM SENDS AT ALL, so the only way to stop a kind of message was to
   * cancel its rows one at a time, for ever, as they appeared.
   */
  const [reasons, setReasons] = useState<Loading<ReasonRow[]>>(undefined);
  const [busy, setBusy] = useState('');
  /** The row he opened to read its wording. `null` is closed — it is not a screen of its own. */
  const [reading, setReading] = useState<ReasonRow | null | undefined>(undefined);
  const [switchError, setSwitchError] = useState('');

  /**
   * WHAT WENT OUT AND WHAT DID NOT, WITH THE REASON.
   *
   * `reminders.log` describes itself as the most important route this service has, and no screen
   * called it. Every correct suppression we make — quiet hours, the daily ceiling, missing
   * consent, an unapproved template — therefore reads to the owner as a fault, and every refusal
   * we wrote in plain Arabic goes to a place nobody opens. That is not a missing feature; it
   * turns every rule in the engine into a suspected bug.
   */
  const [log, setLog] = useState<Loading<LogRow[]>>(undefined);
  // `null` IS «STILL LOADING» ON THIS SCREEN (see the read below), so the failure needs a field of
  // its own — otherwise a dead peer looks exactly like a slow one, for ever, and the owner reads
  // «لا شيء في السجل بعد» about messages that did go out.
  const [logFailed, setLogFailed] = useState(false);
  const [only, setOnly] = useState<'' | 'sent' | 'suppressed'>('');
  /** Which branch's messages he is reading. '' is all of them; '_none' is the ones with none. */
  const [logBranch, setLogBranch] = useState('');
  const [branches, setBranches] = useState<{ id: string; name: string }[] | null>([]);
  const [schedule, setSchedule] = useState<Schedule | null | undefined>(undefined);
  const [campaigns, setCampaigns] = useState<Campaign[] | null | undefined>(undefined);
  // A SECOND FACT NEEDS A SECOND FIELD. `null` already means «the plan does not include
  // campaigns» on this screen, so putting «we could not read» into it would collapse two
  // different answers into one — the same mistake this pass exists to undo, committed in a new
  // place. He is told to buy something he already owns, or told he owns nothing during an outage.
  const [campaignsFailed, setCampaignsFailed] = useState(false);
  /** The composer, open only when he asks for it — this tab is a list first. */
  const [launching, setLaunching] = useState(false);
  /** One campaign's sends, open under its row. `null` is closed — it is not a screen of its own. */
  const [runs, setRuns] = useState<Run[] | null | undefined>(undefined);
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
   * recording it cannot itself fire the effect that reads it.
   */
  const asked = useRef<Set<string>>(new Set());

  // WITH THE SCREEN, NOT WITH ITS TAB. It is thirteen small rows and it is the first thing shown,
  // so paying for it on open costs nothing and paying for it on a tab switch would show a
  // skeleton to somebody who is already looking at the answer.
  useEffect(() => {
    const a = action(catalog, 'reminders.reasons');
    if (!a) { setReasons(DENIED); return; }
    call<{ reasons: ReasonRow[] }>(session, a)
      .then((x) => setReasons(x.reasons ?? []))
      // A FAILED READ IS NOT AN EMPTY SYSTEM. `[]` here would tell an owner his shop sends
      // nothing, which is the one sentence that must never be shown by mistake.
      .catch(() => setReasons(null));
  }, [session, catalog]);

  const flip = async (row: ReasonRow, on: boolean) => {
    const a = action(catalog, 'reminders.set_reason');
    if (!a) return;
    setBusy(row.id); setSwitchError('');
    // OPTIMISTIC, AND CORRECTED BY THE ANSWER. A switch that waits for a round trip before moving
    // reads as broken on a phone, and this screen is opened on a phone.
    // THE OPTIMISTIC MOVE APPLIES TO ROWS THAT EXIST. A denied or unread value has no rows to
    // move, and mapping over it would turn a permission state into an empty list — the exact
    // collapse this pattern is about.
    setReasons((rows) => (isReady(rows) ? rows.map((r) => (r.id === row.id ? { ...r, on } : r))
                                        : rows));
    try {
      const out = await call<{ ok?: boolean; error?: string; reasons?: ReasonRow[] }>(
        session, a, { reason_id: row.id, on });
      if (out?.error) {
        setSwitchError(out.error);
        setReasons((rows) => (isReady(rows)
          ? rows.map((r) => (r.id === row.id ? { ...r, on: !on } : r))
          : rows));
      } else if (out?.reasons) {
        setReasons(out.reasons);
      }
    } catch (e) {
      setReasons((rows) => (isReady(rows)
        ? rows.map((r) => (r.id === row.id ? { ...r, on: !on } : r))
        : rows));
      setSwitchError(e instanceof Error ? e.message : 'تعذّر الحفظ.');
    } finally {
      setBusy('');
    }
  };

  // THE LOG IS FETCHED WHEN ITS TAB OPENS, not with the screen. It is the heaviest read here and
  // the least often wanted — an owner opens «رسائلي» to see what is coming, and pays for the log
  // only when he asks why something did not.
  useEffect(() => {
    if (tab !== 'log') return;
    const a = action(catalog, 'reminders.log');
    if (!a) { setLog(DENIED); return; }
    setLog(null);
    call<{ log: LogRow[] }>(session, a, {
      limit: 100,
      ...(only ? { outcome: only } : {}),
      ...(logBranch ? { branch_id: logBranch } : {}),
    })
      .then((x) => { setLogFailed(false); setLog(x.log ?? []); })
      .catch(() => { setLogFailed(true); setLog([]); });
  }, [tab, only, logBranch, session, catalog]);

  // THE NAMES, FROM THE SERVICE THAT OWNS THEM. reminders stores a branch id on every row and no
  // names at all — printing the id would give an owner a string to hunt for in his own shop.
  useEffect(() => {
    const b = action(catalog, 'operations.list_branches');
    if (!b) return;
    call<{ branches: { id: string; name: string }[] }>(session, b)
      .then((x) => setBranches(x.branches ?? []))
      .catch(() => setBranches(null));
  }, [session, catalog]);

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
      ...(isReady(schedule) ? schedule.schedule ?? [] : []).map((r) => r.subject_ref),
      ...(isReady(log) ? log : []).map((r) => r.subject_ref),
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
      .then((x) => { setCampaignsFailed(false); setCampaigns(x.campaigns ?? []); })
      .catch(() => setCampaignsFailed(true));
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
          { value: 'reasons', label: 'متى نرسل' },
          { value: 'auto', label: 'بانتظار الخروج' },
          { value: 'campaigns', label: 'حملاتي' },
          { value: 'log', label: 'السجل' },
        ]}
      />

      {tab === 'reasons' ? (
        <section className="flex flex-col gap-3">
          {/* ── everything that sends in his name, and the switch for each ──────────────────
              THE ROW IS A SENTENCE, NOT A SETTING. «سُجّلت زيارة» with «بعد تسجيل الزيارة
              بعشر دقائق» under it answers the two questions he has — what and when — before he
              touches anything. Both come from the server: a label kept here would drift from the
              engine the first time a reason changed, and he would be reading a promise nothing
              keeps. */}
          {switchError ? <p className="px-1 text-sm text-danger">{switchError}</p> : null}
          {isLoading(reasons) ? (
            <Skeleton height={200} />
          ) : isDenied(reasons) ? (
            // THE ONE ANSWER WAITING NEVER CHANGES. This section is decided by his role, so
            // «حاول بعد قليل» sends him back tomorrow to the same closed door (م · النمط 2).
            <EmptyState
              title="لا يشمل دورك دواعي الإرسال"
              description="راجع صاحب المحل إن كنت تحتاج هذا القسم."
            />
          ) : hasFailed(reasons) ? (
            // THE ONLY PATH TO THIS SENTENCE USED TO BE AN EMPTY LIST, and an empty list here
            // meant «the action is not in your catalogue» — a permission answer wearing an outage
            // sentence, so he retried every day on something waiting would never open.
            <EmptyState
              title="تعذّر قراءة رسائلك"
              description="حسابك سليم، والخلل عندنا. حاول بعد قليل."
            />
          ) : reasons.length === 0 ? (
            <EmptyState
              title="لا دواعي إرسال بعد"
              description="تظهر هنا حالما يبدأ محلك في تسجيل الزيارات."
            />
          ) : (
            <ul className="flex flex-col gap-2">
              {reasons.map((t) => (
                <li key={t.id}
                    className={[
                      'flex items-start justify-between gap-3 rounded-card bg-surface-1 p-3 shadow-sm',
                      t.on ? '' : 'opacity-70',
                    ].join(' ')}>
                  {/* THE WHOLE ROW OPENS IT, not a small "preview" link. What the message SAYS is
                      the thing he came to see; the switch is the smaller act, and it keeps its own
                      hit area on the other side. */}
                  <button type="button"
                          onClick={() => setReading(t)}
                          className="flex min-w-0 flex-1 flex-col gap-1 text-start">
                    <span className="truncate font-medium">{t.label}</span>
                    <span className="text-sm text-text-secondary">{t.when}</span>
                    {/* WHOSE WORDS GO OUT. Silent while it is ours — the normal case, and a line
                        saying «بصياغتنا» on thirteen rows is thirteen lines of noise. */}
                    {t.template ? (
                      <Badge tone="neutral">بنصّك أنت</Badge>
                    ) : null}
                  </button>
                  {t.can_switch ? (
                    // THE NAME STAYS, THE SECOND COPY GOES. The kit uses `label` for BOTH the
                    // switch's accessible name and a visible caption beside it — so every row
                    // printed its own title twice, once as the heading and once next to the
                    // switch. Dropping the label would fix the look and leave the switch unnamed
                    // to a screen reader and to our own tests, which find it by name.
                    //
                    // So the caption is hidden VISUALLY ONLY: `sr-only` keeps it in the
                    // accessibility tree, where it is the one thing that makes thirteen identical
                    // switches distinguishable.
                    <span className="shrink-0 [&_label>span]:sr-only">
                      <Toggle
                        label={t.label}
                        checked={t.on}
                        disabled={busy === t.id}
                        onChange={(on) => flip(t, on)}
                      />
                    </span>
                  ) : (
                    // NOT A DISABLED SWITCH. A greyed toggle invites him to try, and trying does
                    // nothing; a lock with a reason answers before he asks.
                    <span className="flex shrink-0 items-center gap-1 text-xs text-text-secondary">
                      <Lock size={14} aria-hidden />
                      حقٌّ لعميلك
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
          <p className="px-1 text-xs text-text-secondary">
            الإيقاف يوقف هذا النوع كلّه — وما هو في الطابور الآن يسقط معه.
          </p>
          {reading ? (
            <MessagePreview
              session={session}
              catalog={catalog}
              reasonId={reading.id}
              label={reading.label}
              when={reading.when}
              canRetext={reading.can_retext}
              onClose={() => setReading(null)}
              // The chosen text changed, so the row's «بنصّك أنت» badge has to be re-read from
              // the server rather than guessed at here.
              onChosen={() => {
                const a = action(catalog, 'reminders.reasons');
                if (a) {
                  call<{ reasons: ReasonRow[] }>(session, a)
                    .then((x) => setReasons(x.reasons ?? []))
                    .catch(() => {});
                }
              }}
            />
          ) : null}
        </section>
      ) : tab === 'auto' ? (
      <section className="flex flex-col gap-3">
        {/* ── the queue, as PEOPLE ────────────────────────────────────────────────────────────
            «مين بيوصله إيش، ومتى» — and the one act that belongs here, which is stopping one of
            them. The old shape was four fixed rows, one per message TYPE, each carrying a count
            and three dashes: a shop with one queued reminder read «تذكير الموعد … 1» and «—» three
            times, and could not tell whose reminder it was without opening a nested panel. Nothing
            on the screen was about a customer, which is the only thing this section is about. */}
        {isLoading(schedule) ? (
          <Skeleton height={160} />
        ) : hasFailed(schedule) ? (
          // HE CAME TO STOP ONE. «ما في رسائل بانتظار الخروج» after a failed read closes the
          // screen for him, reassured, while the message he wanted to stop goes out on time.
          <EmptyState
            title="تعذّرت قراءة الرسائل المجدولة"
            description="والخلل عندنا. أعد المحاولة بعد قليل — لم يُلغَ شيء."
          />
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
            {/* SHOWN ONLY TO A SHOP WITH MORE THAN ONE PLACE. «صفِّ حسب فرعك الوحيد» is a control
                that does nothing, and one more thing to read past. */}
            {(branches ?? []).length > 1 ? (
              <label className="flex items-center gap-2 px-1 text-sm">
                <span className="text-text-secondary">الفرع</span>
                <select
                  className="min-h-11 flex-1 rounded-xl bg-surface-2 px-3 text-sm"
                  value={logBranch}
                  aria-label="تصفية السجل حسب الفرع"
                  onChange={(e) => setLogBranch(e.target.value)}
                >
                  <option value="">كل الفروع</option>
                  {(branches ?? []).map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
                  {/* A GROUP, NOT A LEFTOVER: campaign sends have no visit behind them, and rows
                      from before we carried the field will never have one. */}
                  <option value="_none">بلا فرع محدَّد</option>
                </select>
              </label>
            ) : null}
          </div>

          {isLoading(log) ? (
            <Skeleton height={120} />
          ) : isDenied(log) ? (
            <EmptyState
              title="لا يشمل دورك سجلّ الإرسال"
              description="راجع صاحب المحل إن كنت تحتاج هذا القسم."
            />
          ) : logFailed || hasFailed(log) ? (
            // OURS, NOT HIS. «لا شيء في السجل بعد» is a statement about his shop, and we may only
            // make it once we have actually read the log — otherwise an owner whose messages did
            // go out is told they did not, on the one screen whose whole job is to say what left
            // in his name.
            <EmptyState
              title="تعذّرت قراءة السجل"
              description="لم نستطع جلبه الآن، والخلل عندنا. أعد المحاولة بعد قليل."
            />
          ) : !isReady(log) || log.length === 0 ? (
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
                    {/* THREE STATES, NOT TWO — and «خرجت» was doing the work of all three.
                        It meant «we handed it to Meta», the owner read it as «وصلت», and nothing
                        in the product could tell those apart. Now a receipt says which:

                          قرأها   — he opened it
                          وصلت    — it reached his handset, and he has not opened it yet
                          خرجت    — it left us, and we have not heard back

                        The third is not a failure and must not be coloured as one: WhatsApp
                        receipts arrive minutes late and a shop reading this at the counter would
                        otherwise think every recent message had failed. */}
                    <Badge tone={r.outcome !== 'sent' ? 'warning'
                      : r.read_at ? 'success' : 'neutral'}>
                      {r.outcome !== 'sent' ? 'لم تخرج'
                        : r.read_at ? 'قرأها' : r.delivered_at ? 'وصلت' : 'خرجت'}
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
      ) : owns(owned ?? null, 'feature.campaigns') === false ? (
        // LOCKED ON THE ENTITLEMENT, NOT ON THE CAPABILITY — and that swap is the whole defect.
        // The lock used to be drawn from `campaigns.list` being absent from the catalogue, which
        // is a question about the person's ROLE: an owner holds `campaigns.manage` on every plan,
        // so the lock never appeared for the one person who would have paid to remove it. He
        // pressed «أطلق الحملة» on the cheapest plan and it went out.
        //
        // And the card now carries a way to buy it. Naming a feature he cannot reach, with no
        // button, is an advertisement rather than a product.
        <LockedCard appId="campaigns" />
      ) : campaignsFailed ? (
        <EmptyState
          title="تعذّرت قراءة حملاتك"
          description="لم نستطع جلب القائمة الآن، والخلل عندنا. أعد المحاولة بعد قليل."
        />
      ) : isLoading(campaigns) ? (
        // A DIFFERENT ABSENCE, KEPT SEPARATE: the shop HAS campaigns and this person may not use
        // them. Nothing to buy, so nothing to sell him — the sentence is about permission.
        <section className="rounded-card bg-surface-1 p-4 text-center shadow-sm">
          <Lock size={20} className="mx-auto mb-3 text-text-secondary" aria-hidden />
          <EmptyState
            title="الحملات ليست من صلاحياتك"
            description="اطلب من المالك أن يفتحها لك."
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

          {hasFailed(campaigns) ? (
            // «لم تُطلق حملة بعد» IS A FACT ABOUT HIS SHOP. Said after a failed read it tells an
            // owner mid-campaign that nothing of his is running.
            <EmptyState
              title="تعذّرت قراءة حملاتك"
              description="لم نستطع جلبها الآن، والخلل عندنا. أعد المحاولة بعد قليل."
            />
          ) : (campaigns ?? []).length === 0 ? (
            <EmptyState
              title="لم تُطلق حملة بعد"
              description="اختر شريحة من عملائك الموافقين وأرسل لهم عرضاً."
            />
          ) : (
            <ul className="flex flex-col gap-2">
              {campaigns.map((c) => (
                <li key={c.id} className="flex items-center justify-between">
                  <span>{GOAL_TITLE[c.goal ?? ''] || c.goal || 'حملة'}</span>
                  <span className="flex items-center gap-2">
                    {typeof c.sent === 'number' ? (
                      <span className="tabular-nums text-text-secondary">{c.sent} أُرسلت</span>
                    ) : null}
                    {c.state ? (
                      <Badge tone={c.state === 'active' ? 'accent' : 'neutral'}>
                        {STATE[c.state] ?? c.state}
                      </Badge>
                    ) : null}
                    {/* «ماذا حدث» — THE MOST IMPORTANT ROUTE THIS SERVICE HAS, by its own note:
                        "it didn't arrive" is the only complaint this product generates, and every
                        correct refusal (consent, the ceiling, quiet hours) reads as a fault until
                        it is named. It was declared and called by nothing. */}
                    {action(catalog, 'campaigns.runs') ? (
                      <Button variant="ghost" onClick={() => void openRuns(c.id)}>ماذا حدث</Button>
                    ) : null}
                    {/* STOPPING A STANDING RULE, not deleting its history. Only while it runs —
                        a pause button on a finished campaign is a control that does nothing. */}
                    {c.state === 'active' && action(catalog, 'campaigns.pause') ? (
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
