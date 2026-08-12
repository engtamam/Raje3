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
import { useEffect, useState } from 'react';
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

interface Schedule { schedule: { id?: string; kind?: string; due_at?: number }[]; count: number }

/**
 * The occasions, by their names rather than by their template ids.
 *
 * `kind` matches what the scheduler stores, which is how a count is attached to each without the
 * screen inventing a mapping. A kind the backend adds later and this list does not name simply
 * does not appear here — which is the safe direction: a missed row is a gap, an invented one is a
 * promise the engine does not keep.
 */
const OCCASIONS: { kind: string; label: string; help: string }[] = [
  { kind: 'reminder', label: 'تذكير الموعد', help: 'قبل موعد الخدمة القادمة بأيام.' },
  { kind: 'follow_up', label: 'الاطمئنان بعد الزيارة', help: 'بعد الزيارة بأيام — يسأل إن كان كل شيء تمام.' },
  { kind: 'review_request', label: 'طلب التقييم', help: 'بعد زيارة ناجحة.' },
  { kind: 'campaign', label: 'الحملات', help: 'ما تُطلقه أنت على شريحة من عملائك.' },
];

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
  /** Which occasion's queue is open. One at a time — this is a list, not a dashboard. */
  const [openKind, setOpenKind] = useState('');

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

  const waitingOf = (kind: string) =>
    (schedule?.schedule ?? []).filter((r) => r.kind === kind).length;

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
      <section className="rounded-card bg-surface-1 p-4 shadow-sm">
        <h2 className="mb-3 text-sm text-text-secondary">ما يُرسَل تلقائياً</h2>
        {schedule === null ? (
          <Skeleton height={140} />
        ) : (
          <ul className="flex flex-col gap-2">
            {OCCASIONS.map((o) => {
              const waiting = waitingOf(o.kind);
              const rows = (schedule?.schedule ?? []).filter((r) => r.kind === o.kind);
              return (
                <li key={o.kind} className="flex flex-col gap-2">
                  <div className="flex items-center justify-between gap-3">
                    <span className="flex flex-col">
                      <span>{o.label}</span>
                      <span className="text-sm text-text-secondary">{o.help}</span>
                    </span>
                    {/* THE STATE, NOT A SWITCH. Turning an occasion off is a per-service setting
                        in the tree, and it lives in «خدماتي» where he is looking at the service it
                        belongs to. A global switch here would be a second place to change one
                        thing, and the two would disagree.

                        BUT THE COUNT OPENS NOW. Seeing comes before acting — the route says so in
                        its own note — and the count used to be the end of the road: an owner who
                        knew one particular reminder should not go out could not reach it. */}
                    <button
                      type="button"
                      disabled={waiting === 0}
                      onClick={() => setOpenKind(openKind === o.kind ? '' : o.kind)}
                      // A COUNT THAT OPENS IS A BUTTON, and a button on this screen answers to the
                      // same 44px floor as every other. Bare text passed review because it looks
                      // like a label — which is exactly why the thumb misses it.
                      className="grid min-h-11 shrink-0 place-items-center px-2 tabular-nums text-text-secondary disabled:opacity-60"
                    >
                      {waiting > 0 ? `${waiting} بانتظار الإرسال` : '—'}
                    </button>
                  </div>

                  {openKind === o.kind ? (
                    <div className="flex flex-col gap-2 rounded-lg bg-surface-2 p-3">
                      {rows.slice(0, 20).map((r, i) => (
                        <div key={r.id || i} className="flex items-center justify-between gap-2">
                          <span className="text-sm tabular-nums text-text-secondary">
                            {r.due_at ? `يخرج ${when(r.due_at)}` : 'بانتظار موعده'}
                          </span>
                          {/* CANCELS THE MESSAGE, NOT THE RULE — the route's own words, repeated
                              here so he is not surprised: the next visit schedules a new one,
                              which is what he almost always means. */}
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
                              ألغِه
                            </Button>
                          ) : null}
                        </div>
                      ))}
                      <p className="text-xs text-text-secondary">
                        الإلغاء يوقف هذه الرسالة وحدها — والزيارة القادمة تجدول واحدة جديدة.
                      </p>
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
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
                    <span className="text-sm text-text-secondary tabular-nums">
                      {r.at ? new Date(r.at * 1000).toLocaleString('ar-SA-u-ca-gregory') : ''}
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
