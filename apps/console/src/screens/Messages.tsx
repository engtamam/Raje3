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
interface Schedule { schedule: { kind?: string; due_at?: number }[]; count: number }

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

    const c = action(catalog, 'campaigns.list');
    if (c) {
      call<{ campaigns: Campaign[] }>(session, c)
        .then((x) => setCampaigns(x.campaigns ?? []))
        .catch(() => setCampaigns([]));
    } else {
      // NOT AN ERROR AND NOT AN EMPTY LIST: the plan does not include campaigns. `null` is the
      // LOCKED state — the tab is still there, and it says why.
      setCampaigns(null);
    }
  }, [session, catalog]);

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
              return (
                <li key={o.kind} className="flex items-center justify-between gap-3">
                  <span className="flex flex-col">
                    <span>{o.label}</span>
                    <span className="text-sm text-text-secondary">{o.help}</span>
                  </span>
                  {/* THE STATE, NOT A SWITCH. Turning an occasion off is a per-service setting in
                      the tree, and it lives in «خدماتي» where he is looking at the service it
                      belongs to. A global switch here would be a second place to change one thing,
                      and the two would disagree. */}
                  <span className="shrink-0 tabular-nums text-text-secondary">
                    {waiting > 0 ? `${waiting} بانتظار الإرسال` : '—'}
                  </span>
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
        <section className="rounded-card bg-surface-1 p-4 shadow-sm">
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
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
