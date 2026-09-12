/**
 * Launching a campaign — the journey that did not exist.
 *
 * THE ENGINE WAS COMPLETE AND HAD NO BUTTON. `campaigns.goals`, `preview`, `create`, `runs` and
 * `pause` were declared, served, tested and deployed; «حملاتي» listed campaigns and explained what
 * a campaign is FOR, which made it a brochure for a feature its owner could not use. Half of what
 * §7.2 and §10.9.1 describe was unreachable from the product.
 *
 * THREE STEPS, AND THE MIDDLE ONE IS THE PRODUCT. Goal, then preview, then send:
 *
 *   THE GOAL comes from the server WITH ITS LOCK — «هذا الهدف مقفل حتى…» is rendered from what the
 *   server returned rather than computed here. A console that decides availability for itself
 *   disagrees with the server the first time either changes, and the owner is the one who finds
 *   out, by pressing a card that then refuses him.
 *
 *   THE PREVIEW IS WHY THIS EXISTS. The real message, the number of PEOPLE it reaches, who was
 *   excluded and why, and how many days it will take. An owner who expected an afternoon and got a
 *   week will say the product is broken and he will be right — nothing told him. The number is
 *   shown while he is deciding, not reconstructed afterwards from a progress bar.
 *
 *   AND THE SEND IS ONE PRESS, on the screen that already shows exactly what will happen.
 *
 * NOTHING IS COMPOSED HERE. The text is the approved template plus one line of his — his own
 * sentence is the only free field, deliberately (§8.4.1): a template Meta approved cannot be
 * rewritten in a browser, and a form asking him to write a message would be a form he abandons.
 */
import { useEffect, useState } from 'react';
import {
  Cake, Gift, Info, Megaphone, RotateCcw, Search, Tag, type LucideIcon,
} from 'lucide-react';
import { Badge } from '../rj-ui/Badge';
import { Button } from '../rj-ui/Button';
import { HourRangePicker } from '../rj-ui/HourRangePicker';
import { Segmented } from '../rj-ui/Segmented';
import { Toggle } from '../rj-ui/Toggle';
import { WeekdayPicker } from '../rj-ui/WeekdayPicker';
import { WhatsAppTemplatePreview, type FlowJson, type WaTemplateData } from '../rj-ui/WhatsAppPreview';
import { isDenied, isReady, DENIED, hasFailed, isLoading, type Loading } from '../loading';
import { Waiting } from '../Waiting';
import { action, call, type Catalog } from '../catalog';
import { owns, type Owned } from '../apps';
import type { Session } from '../session';
import { TEMPLATE_STATUS_META, type TemplateStatus } from './templateStatus';
import { western } from '../digits';
import { MessagePreview } from './MessagePreview';
import { useOperatorI18n, tf, translate } from '../operator-i18n';
import './launch-i18n';

/**
 * THE SAME MEMBERSHIP shape.py's OWN `BOOKING_TYPES` HOLDS (mkt_winback/mkt_personal_occasion/
 * mkt_offer), named by GOAL rather than by template type — a shop that owns bookings gets a real
 * Flow button under one of these four goals' sends; a shop that does not gets a carousel instead
 * (core/shape.py::for_send). Every other goal (announce/awareness/reward_loyal) always sends
 * plain text — neither shape applies. Hand-mirrored, same posture Messages.tsx's own
 * `GOAL_TEMPLATE_TYPE` already takes: a table this small drifting is a one-line fix, not worth a
 * network round trip for exactly one screen's preview.
 */
const CAROUSEL_ELIGIBLE_GOALS = new Set(['win_back', 'occasion', 'service_offer', 'package_offer']);

/** WEEKDAY LABELS, Monday=0..Sunday=6 — `Campaign.window_weekdays`'s own encoding
 *  (operations/core/scheduling.py::recurrence_weekdays). */
function weekdayLabels(t: (key: string) => string): string[] {
  return [
    t('launch.weekday.mon'), t('launch.weekday.tue'), t('launch.weekday.wed'),
    t('launch.weekday.thu'), t('launch.weekday.fri'), t('launch.weekday.sat'),
    t('launch.weekday.sun'),
  ];
}

/**
 * `campaigns-service` (app/core/goals.py) sends a NAME, never an emoji — "return", "gift",
 * "megaphone"... the same identifier scheme `nav.ts` already uses for the rail. Rendering it as
 * literal text (which this screen did — an Arabic title with the
 * English word "return" printed right beside it) is what a caller does with a name it never
 * mapped. An unknown name falls back to `Tag` rather than rendering nothing — a wrong icon is a
 * smaller fault than a blank one, and both are more honest than the raw string.
 */
const GOAL_ICONS: Record<string, LucideIcon> = {
  return: RotateCcw,
  gift: Gift,
  megaphone: Megaphone,
  cake: Cake,
  info: Info,
  tag: Tag,
};

interface Goal {
  goal: string;
  title: string;
  line: string;
  icon?: string;
  /** One of `categories` below (goals.py::GOAL_CATEGORIES) — how the rail groups this card. */
  category?: string;
  /** How many times this goal has been launched, and how many customers it has actually reached
   *  — the side counter (campaigns' own core/goal_stats.py, 2026-09-12), never computed here. */
  uses?: number;
  reach?: number;
  available?: boolean;
  unavailable_reason?: string;
  behaviour?: string;
  needs_enabling?: boolean;
  /** Whether this goal promises something — and therefore must name the day it stops. */
  offers?: boolean;
  /**
   * The blanks this goal's message has for HIM to fill, by kind and in order — `amount`,
   * `catalogue`, `date`, `code`, `owner`. Read from the template this shop would actually send,
   * so a shop that rewrote its own message gets its own blanks.
   */
  blanks?: string[];
  /** The badge — same picture the admin panel's own template screen shows, on every card
   *  whether it is locked or not (see templateStatus.ts's own docstring). */
  template_status?: TemplateStatus;
}

interface Preview {
  message?: string;
  /** WHAT WILL ACTUALLY HAPPEN, in the owner's own words (preview.py::describe_when) — "تُرسَل
   *  الآن", "تُرسَل في الموعد الذي حدّدته", or, when this campaign carries its own recurring
   *  window, that sentence appended ("تُرسَل فقط بين الساعة 14 و16..."). Rendered once, from the
   *  server that actually enforces it — never reconstructed here from the raw hour/weekday
   *  fields, which is how a screen and an engine agree today and disagree the day either changes. */
  when?: string;
  reaches?: number;
  excluded?: number;
  too_recent?: number;
  spread_says?: string;
  /** The plan itself, and `refused` is the half the screen never read (ج-4): the sentence was
   *  rendered as advice before the launch and AS THE SUCCESS BANNER after it. A refusal shown in
   *  the place a confirmation goes is a refusal nobody reads as one. */
  spread?: { days?: number; per_day?: number; total?: number; refused?: string };
  why?: string[];
}

/**
 * DOES THIS GOAL'S MESSAGE HAVE A BLANK OF THIS KIND FOR HIM TO FILL? (ط-4)
 *
 * Meta approves the WORDS. The numbered blanks are the only thing a shop decides, and each one
 * belongs to somebody: `system` is ours — his name, the shop, a balance — and never a question;
 * `catalogue` is a tap on his own service list; `amount`/`code`/`date` are typed values with a
 * shape we can check; `owner` is the single free blank, and only where the sentence has nothing
 * but his own words to put there.
 *
 * WHAT THIS REPLACED. The screen drew a free text box for EVERY goal under «سطرك في الرسالة»,
 * and decided the three typed fields from `offers` — a fact about the goal rather than about the
 * message it sends. For four of the six goals that free line reached nothing: `mkt_offer` is «لك
 * خصم {{3}} على {{4}}. ساري حتى {{5}}» and has no room for a sentence at all. He typed one,
 * pressed launch, and never saw his words again. Nothing failed.
 *
 * Pure and exported so the rule is one thing a test can hold, rather than a condition spread
 * across four JSX branches that only a rendered page could check.
 */
export function hasBlank(picked: { blanks?: string[]; goal?: string }, kind: string): boolean {
  return (picked.blanks ?? []).includes(kind);
}

/** What to call the free blank, named by what it fills rather than by where it lands.
 *  `t` defaults to the Arabic catalog — same optional-t pattern operator-i18n.tsx's own
 *  `translate` export exists for, so a pure-function test can call this without a provider. */
export function freeBlankLabel(goal: string, t: (key: string) => string = (k) => translate('ar', k)): string {
  return goal === 'announce' ? t('launch.freeBlank.announce') : t('launch.freeBlank.default');
}

interface Branch { id: string; name: string; active?: boolean }

interface Service { id: string; name: string }

interface Package { id: string; name: string; active?: boolean }

export function Launch({ session, catalog, onDone, initialGoalId, owned }:
    { session: Session; catalog: Catalog; onDone: () => void; initialGoalId?: string;
      owned?: Loading<Owned> }) {
  const { t } = useOperatorI18n();
  const [goals, setGoals] = useState<Loading<Goal[]>>(undefined);
  // THE RAIL'S OWN GROUPING — `campaigns.goals` now returns these alongside the cards
  // themselves (goals.py::GOAL_CATEGORIES, 2026-09-12), in display order. A goal with none
  // (an older server, or a read that failed before this field existed) simply carries no
  // `category` and is never filtered out by "الكل".
  const [categories, setCategories] = useState<string[]>([]);
  const [activeCategory, setActiveCategory] = useState('');
  const [search, setSearch] = useState('');
  // `null` MEANS «STILL READING» HERE — the screen shows a Waiting on it — so the failure needs a
  // field of its own. Sharing one would make a dead peer indistinguishable from a slow one, and
  // «لا أهداف متاحة الآن» is a claim about the product rather than about the read.
  const [goalsFailed, setGoalsFailed] = useState(false);
  const [picked, setPicked] = useState<Goal | null | undefined>(undefined);
  const [ownerText, setOwnerText] = useState('');
  const [serviceId, setServiceId] = useState('');
  /**
   * WHEN THE OFFER STOPS. «لا افتراض له» (§10.9.1) — we do not pick a date for him, because a
   * discount whose end we chose is a discount he honours at the till on a day he did not agree to.
   *
   * IT WAS NOT ON THIS SCREEN AT ALL, and three of the six goals refuse without it: «عرض على
   * خدمة»، «رجّع اللي غابوا»، «كافئ المخلصين» each answered «حدّد تاريخ انتهاء العرض» to a screen
   * that had no field to answer with. Half the campaign engine was unreachable.
   */
  const [endsOn, setEndsOn] = useState('');
  /**
   * THE DISCOUNT, AS A VALUE RATHER THAN A SENTENCE. It used to live inside his one free line, so
   * «خصم كبير» reached customers as a promise nobody could be held to, and «٢٠٪» reached them in
   * digits half the phones in this market render badly. Typed, we phrase it the same way every
   * time and refuse a number that cannot be honoured.
   */
  // arabic-indic-digits: intentional — «٢٠٪» appears in the note above as the shape we refuse.
  const [offerValue, setOfferValue] = useState('');
  const [services, setServices] = useState<Service[] | null>([]);
  // `package_offer`'s OWN answer for the "catalogue" blank — a package, never a service (packages
  // feature). Fetched the same way `services` is: this service holds no catalogue of its own.
  const [packages, setPackages] = useState<Package[] | null>([]);
  const [packageId, setPackageId] = useState('');
  // HIS BRANCHES, and the empty list is the common case — one branch, or a role that may not read
  // them. The picker below simply does not render then, which is right: a shop with one place has
  // no targeting decision to make, and a control offering one option is a control that lies about
  // having a choice.
  const [branches, setBranches] = useState<Branch[] | null>([]);
  const [branchId, setBranchId] = useState('');
  const [preview, setPreview] = useState<Preview | null | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [sent, setSent] = useState('');
  // WHICH REASONS «متى نرسل» ALREADY KNOWS ABOUT, read once so a picked goal that shares a
  // reason (see GOAL_REASON_ID's own docstring) can offer the SAME message-preview/retext
  // screen «متى نرسل» itself uses, instead of building a second one.
  const [reasons, setReasons] = useState<{ id: string; label: string; when: string;
    can_retext: boolean }[] | null>(null);
  const [previewingReason, setPreviewingReason] = useState(false);
  // HOW MANY TIMES EACH SERVICE WAS ACTUALLY TAKEN — «insights»'s own `service_popularity`,
  // read WITHOUT a `branch_id` so it is the chain-wide count (insights keys a separate "_all"
  // snapshot precisely for this), never one branch's own share. A campaign here always reaches
  // every branch's customers together, so the order this drives must never be built from one
  // branch's own numbers — the owner's own instruction. `{}` (nothing loaded, or a shop too new
  // for the engine to have anything) leaves the picker in its original, unordered shape.
  const [serviceDemand, setServiceDemand] = useState<Record<string, number>>({});

  /**
   * THE OWNER'S OWN RECURRING WINDOW (`Campaign.window_*`, every goal may set one since
   * 2026-09-12) — collapsed by default, exactly the mockup's own posture: most campaigns need no
   * window at all, and a form that opens with every optional field expanded is a form that reads
   * as more decisions than it is.
   */
  const [windowOn, setWindowOn] = useState(false);
  const [windowStartHour, setWindowStartHour] = useState(9);
  const [windowEndHour, setWindowEndHour] = useState(21);
  const [windowWeekdays, setWindowWeekdays] = useState<number[]>([]);

  /**
   * WHEN IT LAUNCHES — for EVERY goal, not only «هنّئ في مناسبة» (job-service-backed, 2026-09-12):
   * a future `fire_at` is handed to the platform's own scheduler for a prompt, exact launch
   * instead of waiting on the next 15-minute tick. Defaults to "الآن", same posture as the window
   * above — a date field nobody asked for is a date field nobody should see.
   */
  const [launchLater, setLaunchLater] = useState(false);
  const [launchDate, setLaunchDate] = useState('');
  const [launchHour, setLaunchHour] = useState('08:00');

  /**
   * THE DAY «هنّئ في مناسبة» IS ABOUT, AND THE GOAL HAD NO WAY TO NAME IT.
   *
   * `occasion` is one of the six goals this screen offers; its card reads «رسالة في يوم يخصّه»
   * and the behaviour line the server sends back for it reads «تُرسَل في موعد تحدّده» — a moment
   * HE defines. The screen gave him nothing to define it with.
   *
   * AND THE CAMPAIGN THEN NEVER SENT AT ALL. `occasion` is the one goal whose trigger is
   * `scheduled` (`GOAL_TRIGGER`), and the dispatcher's guard is
   *
   *     if not fire_at or fire_at > now: skipped
   *
   * so `fire_at = 0` is not «send now» — it is «skip, every tick, for ever». The campaign was
   * created, listed as active, previewed correctly, and the banner said تم. Nothing failed, no
   * log said anything, and not one greeting was ever delivered by this product.
   */
  const [occasionOn, setOccasionOn] = useState('');

  /**
   * THE MORNING OF HIS DAY, not its last minute. `expiresAt` below takes 23:59 because an offer
   * «حتى الخميس» is good all Thursday; a greeting works the other way — it belongs at the start of
   * the day, not as it ends.
   */
  const fireAt = (() => {
    if (!occasionOn) return 0;
    const at = Date.parse(`${occasionOn}T08:00:00+03:00`);
    return Number.isNaN(at) ? 0 : Math.floor(at / 1000);
  })();

  /** THE GENERAL "متى تُطلق" ANSWER, for every goal OTHER than `occasion` (which already has its
   *  own day, above — a moment that IS the message, not a scheduling choice layered on top of
   *  one). `combinedFireAt` below is what actually goes on the wire. */
  const generalFireAt = (() => {
    if (!launchLater || !launchDate) return 0;
    const at = Date.parse(`${launchDate}T${launchHour || '08:00'}:00+03:00`);
    return Number.isNaN(at) ? 0 : Math.floor(at / 1000);
  })();
  const combinedFireAt = picked?.goal === 'occasion' ? fireAt : generalFireAt;

  /** The chosen day, at its last minute in Riyadh — an offer «حتى الخميس» is good all Thursday. */
  const expiresAt = (() => {
    if (!endsOn) return 0;
    const at = Date.parse(`${endsOn}T23:59:59+03:00`);
    return Number.isNaN(at) ? 0 : Math.floor(at / 1000);
  })();

  const goalsAction = action(catalog, 'campaigns.goals');
  const previewAction = action(catalog, 'campaigns.preview');
  const createAction = action(catalog, 'campaigns.create');

  useEffect(() => {
    if (!goalsAction) { setGoals(DENIED); return; }
    call<{ goals: Goal[]; categories?: string[] }>(session, goalsAction)
      .then((r) => {
        const list = r.goals ?? [];
        setGoals(list);
        setCategories(r.categories ?? []);
        // ARRIVING WITH A GOAL ALREADY DECIDED — a card sent us here ("أرسل رسالة رجوع") having
        // already answered "why", so asking him to pick it again from six tiles is a second
        // decision he already made once. Only pre-selects if the goal is actually AVAILABLE —
        // an unreachable goal falls through to the normal picker instead of a dead pre-selection.
        if (initialGoalId) {
          const match = list.find((g) => g.goal === initialGoalId && g.available !== false);
          if (match) setPicked(match);
        }
      })
      .catch(() => { setGoalsFailed(true); setGoals([]); });

    // HIS OWN CATALOGUE, because «عرض على خدمة» must name one of HIS services. Without it that
    // goal would be an untargeted announcement wearing a targeted goal's name — which is exactly
    // the bug the service_id field was added to fix.
    const list = action(catalog, 'operations.list_services');
    if (list) {
      call<{ services: Service[] }>(session, list)
        .then((x) => setServices(x.services ?? []))
        .catch(() => setServices(null));
    }

    // AND HIS PACKAGES, for `package_offer` — same reasoning, same door.
    const pkgs = action(catalog, 'operations.list_packages');
    if (pkgs) {
      call<{ packages: Package[] }>(session, pkgs)
        .then((x) => setPackages((x.packages ?? []).filter((p) => p.active !== false)))
        .catch(() => setPackages(null));
    }

    // AND HIS BRANCHES, for the same reason: a campaign aimed at one of them must name it, and a
    // name this screen invented would reach nobody.
    const brs = action(catalog, 'operations.list_branches');
    if (brs) {
      call<{ branches: Branch[] }>(session, brs)
        .then((x) => setBranches((x.branches ?? []).filter((b) => b.active !== false)))
        .catch(() => setBranches(null));
    }

    // AND HOW OFTEN EACH SERVICE IS ACTUALLY TAKEN — `service_popularity`, free on every plan
    // (insights/app/core/plans.py's own REQUIRES never lists it), so this asks unconditionally.
    // NO `branch_id` — see `serviceDemand`'s own comment on why this must stay chain-wide.
    const dash = action(catalog, 'insights.dashboard');
    if (dash) {
      call<{ values?: { service_popularity?: { service_id: string; count: number }[] } }>(
        session, dash)
        .then((x) => {
          const map: Record<string, number> = {};
          for (const row of x.values?.service_popularity ?? []) map[row.service_id] = row.count;
          setServiceDemand(map);
        })
        .catch(() => {});
    }

    // AND «متى نرسل»'s OWN REASONS — only to learn `can_retext` for the few that share a
    // template with a goal here (GOAL_REASON_ID). `null` on a failed/denied read simply hides
    // the cross-link rather than breaking anything this screen otherwise does.
    const rsn = action(catalog, 'reminders.reasons');
    if (rsn) {
      call<{ reasons: { id: string; label: string; when: string; can_retext: boolean }[] }>(
        session, rsn)
        .then((x) => setReasons(x.reasons ?? []))
        .catch(() => setReasons(null));
    }
  }, [session, catalog, goalsAction]);

  /** THE SAME MAP «متى نرسل»'s OWN `REASON_GOAL` USES, THE OTHER DIRECTION — see that file's own
   *  docstring for why this is hand-matched against GOAL_TEMPLATE rather than derived. */
  const GOAL_REASON_ID: Record<string, string> = {
    win_back: 'gone_missing', occasion: 'personal_occasion', reward_loyal: 'loyal_customer',
  };

  const ask = async (goal: Goal) => {
    if (!previewAction) return;
    setBusy(true); setError(''); setPreview(null);
    try {
      setPreview(await call<Preview>(session, previewAction, {
        goal: goal.goal, owner_text: ownerText, service_id: serviceId,
        // MUTUALLY EXCLUSIVE WITH `service_id` — only `package_offer` ever sets this.
        package_id: packageId,
        // THE BRANCH IS IN THE PREVIEW TOO, and that is the whole point of previewing: the count
        // he decides on must be the count that goes out.
        branch_id: branchId,
        offer_value: offerValue,
        service_name: (services ?? []).find((x) => x.id === serviceId)?.name ?? '',
        package_name: (packages ?? []).find((x) => x.id === packageId)?.name ?? '',
        // CARRIED INTO THE PREVIEW TOO, not only into the launch: the spread refuses a plan that
        // would still be sending after the offer has ended, and that refusal is only useful
        // BEFORE he presses.
        expires_at: expiresAt,
        // AND THE DAY, for the same reason: a greeting scheduled for next month spreads over a
        // different window than one going out now, and he should see that count before pressing.
        fire_at: combinedFireAt,
        // THE RECURRING WINDOW — sent only while he has actually turned it on; off is exactly
        // today's defaults (0, 24, []), which the server reads as "no window at all".
        window_start_hour: windowOn ? windowStartHour : 0,
        window_end_hour: windowOn ? windowEndHour : 24,
        window_weekdays: windowOn ? windowWeekdays : [],
      }));
    } catch (e) {
      // THE SERVER'S SENTENCE, RENDERED AS IT CAME. «لا يوجد قالب مفعّل لهذا الهدف» is actionable;
      // «تعذّر» is not, and inventing our own explanation for somebody else's refusal is how
      // support ends up answering for a rule that does not exist.
      setError(e instanceof Error ? e.message : t('launch.previewFailed'));
    } finally {
      setBusy(false);
    }
  };

  // «NOT YET» IS NOT «IT FAILED» (م · النمط 1). The guard read `=== null` and the failure
  // handler set `null`, so a failed read rendered this for ever and the sentence written
  // for the failure was unreachable. `undefined` waits; `null` says so.
  if (isLoading(goals)) return <Waiting what={t('launch.waitingGoals')} />;

  if (sent) {
    return (
      <section className="flex flex-col gap-3 rounded-card bg-surface-1 p-4 text-center shadow-sm">
        <p className="font-medium">{t('launch.sentTitle')}</p>
        <p className="text-sm text-text-secondary">{sent}</p>
        <div><Button onClick={onDone}>{t('launch.done')}</Button></div>
      </section>
    );
  }

  // ── step 2 and 3: what will happen, and the one press ────────────────────────────────────────
  if (picked) {
    // THE MATCHING REASON, IF ONE EXISTS AND HAS ACTUALLY LOADED — absent for the goals with no
    // automatic counterpart yet (announce, service_offer/package_offer, awareness), and absent
    // while `reasons` is still `null` (loading or denied).
    const linkedReasonId = GOAL_REASON_ID[picked.goal];
    const linkedReason = linkedReasonId ? (reasons ?? []).find((r) => r.id === linkedReasonId) : undefined;
    return (
      <section className="flex flex-col gap-3 rounded-card bg-surface-1 p-4 shadow-sm">
        <div className="flex items-center justify-between gap-2">
          <span className="font-medium">{picked.title}</span>
          <Button variant="ghost" onClick={() => {
            setPicked(null); setPreview(null); setError('');
            setWindowOn(false); setWindowStartHour(9); setWindowEndHour(21); setWindowWeekdays([]);
            setLaunchLater(false); setLaunchDate(''); setLaunchHour('08:00');
          }}>
            {t('launch.changeGoal')}
          </Button>
        </div>
        {picked.behaviour ? (
          <p className="text-sm text-text-secondary">{picked.behaviour}</p>
        ) : null}

        {/* THE CROSS-LINK, THE OTHER DIRECTION — «متى نرسل»'s own row for the exact same
            template opens with a link back here (Messages.tsx's own REASON_GOAL); this is the
            same door from this side, reusing MessagePreview/TextEditor whole rather than a
            second, smaller preview-and-edit screen built just for goal cards. */}
        {linkedReason ? (
          <button type="button" onClick={() => setPreviewingReason(true)}
                 className="w-fit text-sm text-text-secondary underline underline-offset-2 hover:text-text-primary">
            {t('launch.viewOrEditMessage')}
          </button>
        ) : null}
        {previewingReason && linkedReason ? (
          <MessagePreview
            session={session}
            catalog={catalog}
            reasonId={linkedReason.id}
            label={linkedReason.label}
            when={linkedReason.when}
            canRetext={linkedReason.can_retext}
            onClose={() => setPreviewingReason(false)}
            onChosen={() => {}}
          />
        ) : null}

        {/* متى تُطلق؟ — EVERY GOAL BUT `occasion`, which already answers this with its own day
            field below (a moment that IS the message, not a schedule layered on it). A future
            date is handed to the platform's own job scheduler for a prompt, exact launch —
            core/tick.py's ordinary 15-minute scan is the fallback if that peer is ever
            unreachable, never the only path. */}
        {picked.goal !== 'occasion' ? (
          <div className="flex flex-col gap-2 rounded-card border border-border-subtle p-3">
            <span className="text-sm font-medium">{t('launch.when.title')}</span>
            <Segmented
              ariaLabel={t('launch.when.title')}
              value={launchLater ? 'later' : 'now'}
              onChange={(v) => setLaunchLater(v === 'later')}
              options={[
                { value: 'now', label: t('launch.when.now') },
                { value: 'later', label: t('launch.when.later') },
              ]}
            />
            {launchLater ? (
              <div className="flex flex-wrap gap-2">
                <label className="flex flex-col gap-1">
                  <span className="text-xs text-text-secondary">{t('launch.when.dateLabel')}</span>
                  <input
                    type="date"
                    value={launchDate}
                    min={new Date().toISOString().slice(0, 10)}
                    onChange={(e) => { setLaunchDate(e.target.value); setPreview(null); }}
                    dir="ltr"
                    className="h-11 rounded-lg bg-surface-2 px-3 text-sm"
                  />
                </label>
                <label className="flex flex-col gap-1">
                  <span className="text-xs text-text-secondary">{t('launch.when.hourLabel')}</span>
                  <input
                    type="text"
                    value={launchHour}
                    onChange={(e) => { setLaunchHour(e.target.value); setPreview(null); }}
                    dir="ltr"
                    className="h-11 w-24 rounded-lg bg-surface-2 px-3 text-sm"
                  />
                </label>
              </div>
            ) : null}
          </div>
        ) : null}

        {/* THE FREE BLANK — DRAWN ONLY WHERE THE MESSAGE HAS ONE (ط-4).
            
            This box used to appear for every goal, labelled «سطرك في الرسالة». Four of the six
            goals send a template with no free slot at all — `mkt_offer` is «لك خصم {{3}} على
            {{4}}. ساري حتى {{5}}», three typed values and no room for a sentence — so the owner
            wrote one, launched, and his words reached nobody. Nothing failed anywhere.

            Now the server says which blanks exist and this draws exactly those. The label names
            what the blank FILLS rather than promising a place in the message: «ما الجديد؟» for
            an announcement, whose whole content is that blank.

            THE LIMIT IS THE SERVER'S. The counter read «/ 200» while the server refused at 61 —
            a shop wrote three lines, pressed, and was told to shorten what the screen had just
            called fine. Sixty is the template's room. */}
        {hasBlank(picked, 'owner') ? (
          <label className="flex flex-col gap-1">
            <span className="text-sm">{freeBlankLabel(picked.goal, t)}</span>
            <textarea
              value={ownerText}
              maxLength={60}
              rows={2}
              onChange={(e) => { setOwnerText(e.target.value); setPreview(null); }}
              placeholder={t('launch.ownerText.placeholder')}
              className="rounded-lg bg-surface-2 p-3 text-sm"
            />
            <span className="text-xs text-text-secondary tabular-nums">
              {ownerText.length} / 60
            </span>
          </label>
        ) : null}

        {/* ── how much ────────────────────────────────────────────────────────────────────
            TWO BUTTONS AND A NUMBER, not a free field. He taps «نسبة» or «مبلغ» and types the
            number; we build «20%» or «50 ريال». A field that accepts anything accepts «خصم كبير»,
            and the send refuses it after he has already decided he is done. */}
        {hasBlank(picked, 'amount') ? (
          <div className="flex flex-col gap-1">
            <span className="text-sm">{t('launch.discountLabel')}</span>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min={1}
                // 99, WHICH IS WHAT THE SEND ACCEPTS. It said 90 while `_OFFER` in campaigns and
                // `_AMOUNT` in reminders both accept 1-99 — a third number for one rule, and the
                // only one a person ever reads.
                max={99}
                dir="ltr"
                value={western(offerValue).replace(/[^0-9.]/g, '')}
                onChange={(e) => {
                  // FOLD, THEN DROP THE PUNCTUATION. `[^0-9.]` is exactly 0-9 plus a dot, so an
                  // Arabic keyboard's digits were deleted here as he typed the discount — the
                  // box stayed empty on the screen that launches a campaign.
                  const n = western(e.target.value).replace(/[^0-9.]/g, '');
                  const sar = t('launch.discountKind.sar');
                  setOfferValue(n ? (offerValue.includes(sar) ? `${n} ${sar}` : `${n}%`) : '');
                  setPreview(null);
                }}
                className="h-11 w-24 rounded-lg bg-surface-2 px-3 text-center text-sm tabular-nums"
              />
              <Segmented
                ariaLabel={t('launch.discountKindAria')}
                value={offerValue.includes(t('launch.discountKind.sar')) ? 'sar' : 'pct'}
                onChange={(kind) => {
                  const n = western(offerValue).replace(/[^0-9.]/g, '');
                  const sar = t('launch.discountKind.sar');
                  setOfferValue(n ? (kind === 'sar' ? `${n} ${sar}` : `${n}%`) : '');
                  setPreview(null);
                }}
                options={[{ value: 'pct', label: t('launch.discountKind.pct') }, { value: 'sar', label: t('launch.discountKind.sar') }]}
              />
            </div>
            <span className="text-xs text-text-secondary">
              {tf(t, 'launch.discountPreviewNote', { value: offerValue || '20%' })}
            </span>
          </div>
        ) : null}

        {/* ── when it stops ────────────────────────────────────────────────────────────────
            NO DEFAULT, DELIBERATELY (§10.9.1). A date we picked is a date he honours at the till
            without having agreed to it — and «إلى متى؟» is the one question a customer asks about
            an offer. */}
        {hasBlank(picked, 'date') ? (
          <label className="flex flex-col gap-1">
            <span className="text-sm">{t('launch.offerEndsLabel')}</span>
            <input
              type="date"
              value={endsOn}
              min={new Date(Date.now() + 86_400_000).toISOString().slice(0, 10)}
              onChange={(e) => { setEndsOn(e.target.value); setPreview(null); }}
              dir="ltr"
              className="h-11 rounded-lg bg-surface-2 px-3 text-sm"
            />
            <span className="text-xs text-text-secondary">
              {t('launch.offerEndsNote')}
            </span>
          </label>
        ) : null}

        {/* ── the day it is about ──────────────────────────────────────────────────────────
            ON THE GOAL, NOT ON A BLANK. Every other control here is drawn from `blanks` — what
            the approved message has room for him to fill. This one is not about the words at all:
            `fire_at` decides WHEN the campaign leaves, and `occasion` is the one goal whose whole
            premise is a day («رسالة في يوم يخصّه»). Reading it off a blank would tie the schedule
            to whichever template Meta happened to approve.

            AND IT MAY BE LEFT EMPTY, which means today. A shop congratulating a customer this
            afternoon is doing something ordinary; the defect was never having the choice. */}
        {picked.goal === 'occasion' ? (
          <label className="flex flex-col gap-1">
            <span className="text-sm">{t('launch.occasionDateLabel')}</span>
            <input
              type="date"
              value={occasionOn}
              min={new Date().toISOString().slice(0, 10)}
              onChange={(e) => { setOccasionOn(e.target.value); setPreview(null); }}
              dir="ltr"
              className="h-11 rounded-lg bg-surface-2 px-3 text-sm"
            />
            <span className="text-xs text-text-secondary">
              {t('launch.occasionDateNote')}
            </span>
          </label>
        ) : null}

        {/* WHICH SERVICE, when the goal is about one. The cycle lock (§10.9.1) holds back whoever
            took it too recently — and it can only do that if the campaign names the service.
            `package_offer` shares this SAME "catalogue" blank kind (one template, `mkt_offer`,
            approved once for both — see core/models.py's own note) but fills it with a PACKAGE
            instead: no cycle lock applies to it (a package has no single rhythm to hold anyone
            back on), so this is purely which package the message names. */}
        {hasBlank(picked, 'catalogue') && picked.goal === 'package_offer' ? (
          <label className="flex flex-col gap-1">
            <span className="text-sm">{t('launch.packagePickLabel')}</span>
            <select
              value={packageId}
              onChange={(e) => { setPackageId(e.target.value); setPreview(null); }}
              className="h-11 rounded-lg bg-surface-2 px-3 text-sm"
            >
              <option value="">{t('launch.packagePickPlaceholder')}</option>
              {(packages ?? []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
        ) : hasBlank(picked, 'catalogue') ? (
          <label className="flex flex-col gap-1">
            <span className="text-sm">{t('launch.servicePickLabel')}</span>
            {/* ORDERED LEAST-TAKEN FIRST, SILENTLY — «عرض على خدمة» exists for exactly this: an
                owner looking for the service that needs a push, not the one that already sells
                itself. `serviceDemand`'s own comment is why this is chain-wide, never one
                branch's own count. Plain names only, no count printed on the option itself —
                the ORDER is the feature; a number beside every row is a second thing to read for
                a picker that should stay a one-glance choice. */}
            <select
              value={serviceId}
              onChange={(e) => { setServiceId(e.target.value); setPreview(null); }}
              className="h-11 rounded-lg bg-surface-2 px-3 text-sm"
            >
              <option value="">{t('launch.servicePickPlaceholder')}</option>
              {(services ?? [])
                .slice()
                .sort((a, b) => (serviceDemand[a.id] ?? 0) - (serviceDemand[b.id] ?? 0))
                .map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </label>
        ) : null}

        {/* WHICH BRANCH — only for a shop that has more than one, and «كل الفروع» stays the
            default. Changing it drops the preview: a count computed for the whole chain sitting
            under a branch's name is the exact kind of wrong that nobody notices. */}
        {(branches ?? []).length > 1 ? (
          <label className="flex flex-col gap-1">
            <span className="text-sm">{t('launch.branchPickLabel')}</span>
            <select
              value={branchId}
              onChange={(e) => { setBranchId(e.target.value); setPreview(null); }}
              className="h-11 rounded-lg bg-surface-2 px-3 text-sm"
            >
              <option value="">{t('launch.allBranches')}</option>
              {(branches ?? []).map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
            <span className="text-xs text-text-secondary">
              {t('launch.branchPickNote')}
            </span>
          </label>
        ) : null}

        {/* ساعات وأيام إرسال متكررة (اختياري) — EVERY GOAL MAY SET ONE (2026-09-12 correction),
            collapsed by default. Not a second gate on TOP of «متى تُطلق» above: that decides the
            one moment this campaign starts existing; this decides which hours/days it is ever
            allowed to actually SEND on, for as long as it runs. */}
        <div className="flex flex-col gap-2 rounded-card border border-dashed border-border-subtle p-3">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-medium">{t('launch.window.title')}</span>
            <Toggle checked={windowOn}
                   ariaLabel={t('launch.window.title')}
                   onChange={(v) => { setWindowOn(v); setPreview(null); }} />
          </div>
          {windowOn ? (
            <div className="flex flex-col gap-3">
              <p className="text-xs text-text-secondary">{t('launch.window.hint')}</p>
              <HourRangePicker
                startHour={windowStartHour}
                endHour={windowEndHour}
                fromLabel={t('launch.window.fromLabel')}
                toLabel={t('launch.window.toLabel')}
                ariaLabel={t('launch.window.hoursLabel')}
                onChange={(s, e) => { setWindowStartHour(s); setWindowEndHour(e); setPreview(null); }}
              />
              <div className="flex flex-col gap-1">
                <span className="text-xs text-text-secondary">{t('launch.window.daysLabel')}</span>
                <WeekdayPicker
                  ariaLabel={t('launch.window.daysLabel')}
                  options={[5, 6, 0, 1, 2, 3, 4].map((value) => ({ value, label: weekdayLabels(t)[value] }))}
                  selected={windowWeekdays}
                  onChange={(v) => { setWindowWeekdays(v); setPreview(null); }}
                />
              </div>
            </div>
          ) : null}
        </div>

        {preview ? (
          <div className="flex flex-col gap-2 rounded-lg bg-surface-2 p-3">
            {/* THE MESSAGE AS IT WILL ARRIVE — the SAME phone-mockup engine every other preview
                in the product uses (see MessagePreview.tsx/Messages.tsx's own BotToolPreviewModal),
                fed the REAL rendered text — never a plain paragraph pretending to be one, and
                never a second rendering path an owner could be shown two different things by. */}
            <WhatsAppTemplatePreview
              data={(() => {
                const data: WaTemplateData = { body: preview.message ?? '' };
                const carouselShaped = CAROUSEL_ELIGIBLE_GOALS.has(picked.goal);
                const hasBookings = owns(owned ?? null, 'feature.bookings') === true;
                // A SHOP THAT OWNS THE BOOK gets the real Flow button (core/shape.py::for_send) —
                // never guessed here, read from the same entitlement the console already carries.
                if (carouselShaped && hasBookings) {
                  data.flowButton = { flowName: 'booking', text: t('launch.preview.bookingButton') };
                }
                return data;
              })()}
              fetchFlowJson={(() => {
                const carouselShaped = picked && CAROUSEL_ELIGIBLE_GOALS.has(picked.goal);
                const hasBookings = owns(owned ?? null, 'feature.bookings') === true;
                if (!carouselShaped || !hasBookings) return undefined;
                return (flowName: string) => {
                  const a = action(catalog, 'operations.whatsapp_flow_json');
                  if (!a) return Promise.reject(new Error(t('launch.previewFailed')));
                  return call<FlowJson>(session, a, { name: flowName });
                };
              })()}
            />
            {/* A CAROUSEL-ELIGIBLE GOAL ON A SHOP WITHOUT BOOKINGS — the send itself becomes
                image cards instead of this one bubble (core/shape.py::for_send), and this note
                says so rather than fabricating card content the screen has no real photos or
                prices to fill honestly. */}
            {CAROUSEL_ELIGIBLE_GOALS.has(picked.goal) && owns(owned ?? null, 'feature.bookings') !== true ? (
              <p className="text-xs text-text-secondary">{t('launch.preview.carouselNote')}</p>
            ) : null}
            {/* WHAT WILL ACTUALLY HAPPEN, IN HIS WORDS — the server's own sentence
                (preview.py::describe_when), the one place «الآن»/«في الموعد الذي حدّدته» and this
                campaign's own recurring window (if it has one) are said together, truthfully. */}
            {preview.when ? (
              <p className="text-sm font-medium text-text-secondary">{preview.when}</p>
            ) : null}
            <p className="text-sm">
              {t('launch.reaches.prefix')} <b className="tabular-nums">{preview.reaches ?? 0}</b> {t('launch.reaches.suffix')}
            </p>
            {/* SHOWN ONLY WHEN NON-ZERO. A permanent «0 مستثنى» is noise, and noise is what teaches
                a person to stop reading the area where the real number appears. */}
            {preview.excluded ? (
              <p className="text-xs text-text-secondary">
                {tf(t, 'launch.excludedNote', { n: preview.excluded })}
              </p>
            ) : null}
            {preview.too_recent ? (
              <p className="text-xs text-text-secondary">
                {tf(t, 'launch.tooRecentNote', { n: preview.too_recent })}
              </p>
            ) : null}
            {/* THE REFUSAL LOOKS LIKE A REFUSAL. Same sentence, and the colour is the whole
                difference between «here is the plan» and «this cannot run as configured». */}
            {preview.spread?.refused ? (
              <p className="text-sm text-danger">{preview.spread.refused}</p>
            ) : preview.spread_says ? (
              <p className="text-sm text-success">{preview.spread_says}</p>
            ) : null}
            {/* WHY THIS AUDIENCE AND NOT ANOTHER — the server's own reasons, and the screen
                declared this field for months without ever rendering it. An owner who cannot see
                why 47 became 47 has no way to trust the number. */}
            {(preview.why ?? []).map((line) => (
              <p key={line} className="text-xs text-text-secondary">{line}</p>
            ))}
          </div>
        ) : null}

        {error ? <p className="text-sm text-danger">{error}</p> : null}

        <div className="flex flex-wrap gap-2">
          {!preview ? (
            // REFUSED HERE RATHER THAN BY THE SERVER, BUT ONLY FOR A FIELD HE CAN ACTUALLY SEE.
            // This used to gate on `picked.offers` — a fact about the GOAL, not about what THIS
            // shop's template currently has room for. A goal whose template is still under Meta's
            // review (or never seeded) comes back with `blanks: []` — no amount/date box renders
            // at all (both gated on `hasBlank` below) — yet the button still demanded them,
            // deadlocking the exact screen the card was just unlocked to let him reach. Gating on
            // `hasBlank` instead means: if the box is not drawn, nothing here waits on it — press
            // resolves to the server's own refusal (`ask()`'s catch already renders it as-is).
            <Button disabled={busy
                              || (hasBlank(picked, 'amount') && !offerValue)
                              || (hasBlank(picked, 'date') && !endsOn)}
                    onClick={() => void ask(picked)}>{t('launch.previewButton')}</Button>
          ) : (
            <Button
              // A PLAN THE SERVER WILL REFUSE IS NOT A PLAN TO PRESS. The refusal names two
              // remedies — shrink the audience, or extend the date — and both are edits on this
              // screen: the button that offers neither is the one that should not be live.
              disabled={busy || !createAction || Boolean(preview.spread?.refused)}
              onClick={async () => {
                if (!createAction || preview.spread?.refused) return;
                setBusy(true); setError('');
                try {
                  await call(session, createAction, {
                    goal: picked.goal, owner_text: ownerText, service_id: serviceId,
                    package_id: packageId,
                    branch_id: branchId,
                    offer_value: offerValue,
                    service_name: (services ?? []).find((x) => x.id === serviceId)?.name ?? '',
                    package_name: (packages ?? []).find((x) => x.id === packageId)?.name ?? '',
                    expires_at: expiresAt,
                    fire_at: combinedFireAt,
                    window_start_hour: windowOn ? windowStartHour : 0,
                    window_end_hour: windowOn ? windowEndHour : 24,
                    window_weekdays: windowOn ? windowWeekdays : [],
                  });
                  // WHAT HAPPENED, NOT WHAT WAS PLANNED. This used to print `spread_says` as the
                  // confirmation — so a campaign the server refused announced its own refusal in
                  // the voice of a success, and the owner walked away believing it had gone.
                  setSent(tf(t, 'launch.sentSummary', { n: preview.reaches ?? 0 }));
                } catch (e) {
                  setError(e instanceof Error ? e.message : t('launch.launchFailed'));
                } finally {
                  setBusy(false);
                }
              }}
            >
              {t('launch.launchButton')}
            </Button>
          )}
          <Button variant="ghost" onClick={onDone}>{t('launch.cancel')}</Button>
        </div>
      </section>
    );
  }

  // ── step 1: what does he want to achieve ─────────────────────────────────────────────────────
  return (
    <section className="flex flex-col gap-2">
      <p className="text-sm text-text-secondary">{t('launch.step1.prompt')}</p>
      {goalsFailed ? (
        <p className="text-sm text-text-secondary">
          {t('launch.goalsReadFailed')}
        </p>
      ) : isDenied(goals) ? (
        <p className="text-sm text-text-secondary">{t('launch.goalsDenied')}</p>
      ) : hasFailed(goals) ? (
        // «لا أهداف متاحة» IS A CLAIM ABOUT HIS ENABLED APPS. Said after a failed read it sends him to
        // the pricing page for something he already owns.
        <p className="text-sm text-text-secondary">
          {t('launch.goalsReadFailed')}
        </p>
      ) : goals.length === 0 ? (
        <p className="text-sm text-text-secondary">{t('launch.noGoalsAvailable')}</p>
      ) : null}

      {/* THE RAIL'S OWN FILTER — a search box and the real categories `campaigns.goals` returns
          (goals.py::GOAL_CATEGORIES), not a screen-invented grouping. Seven goals today read fine
          as a plain list; this is what keeps a fiftieth goal just as findable, without a redesign
          the day the library grows past a handful. */}
      {isReady(goals) && goals.length > 0 ? (
        <div className="flex flex-col gap-2">
          <label className="flex items-center gap-2 rounded-lg bg-surface-2 px-3 py-2">
            <Search size={14} className="shrink-0 text-text-secondary" aria-hidden />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t('launch.search.placeholder')}
              className="w-full bg-transparent text-sm outline-none"
            />
          </label>
          {categories.length > 0 ? (
            <div className="flex flex-wrap gap-1.5" role="group" aria-label={t('launch.category.all')}>
              <button type="button" onClick={() => setActiveCategory('')}
                     className={['rounded-full px-3 py-1 text-xs font-medium',
                                 activeCategory === '' ? 'bg-text-primary text-surface-1' : 'bg-surface-2 text-text-secondary'].join(' ')}>
                {t('launch.category.all')}
              </button>
              {categories.map((cat) => (
                <button key={cat} type="button" onClick={() => setActiveCategory(cat)}
                       className={['rounded-full px-3 py-1 text-xs font-medium',
                                   activeCategory === cat ? 'bg-text-primary text-surface-1' : 'bg-surface-2 text-text-secondary'].join(' ')}>
                  {cat}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      {(isReady(goals) ? goals : [])
        .filter((g) => (!activeCategory || g.category === activeCategory)
          && (!search.trim() || g.title.includes(search.trim()) || g.line.includes(search.trim())))
        .map((g) => (
        <button
          key={g.goal}
          type="button"
          onClick={() => setPicked(g)}
          className="flex items-start gap-3 rounded-card bg-surface-1 p-4 text-start shadow-sm"
        >
          {g.icon ? (() => {
            const Icon = GOAL_ICONS[g.icon!] ?? Tag;
            return <Icon size={20} className="shrink-0" aria-hidden />;
          })() : null}
          <span className="flex min-w-0 flex-col gap-0.5">
            <span className="flex flex-wrap items-center gap-2">
              <span className="font-medium">{g.title}</span>
              {/* THE BADGE, ON THE CARD ITSELF — whether it is locked or not (§ audit): an
                  available card can still be «pending» for the tone THIS establishment ended
                  up with, and an owner is entitled to see that without pressing a locked card
                  to learn why. «unknown» draws nothing — a status this screen could not vouch
                  for must not be shown as if it were one. */}
              {g.template_status && g.template_status !== 'unknown' ? (
                <Badge tone={TEMPLATE_STATUS_META[g.template_status].tone}>
                  {TEMPLATE_STATUS_META[g.template_status].label}
                </Badge>
              ) : null}
            </span>
            <span className="text-sm text-text-secondary">{g.line}</span>
            {/* THE RAIL'S OWN "استُخدمت N مرة" / "N وصلهم" — SHOWN ONLY WHEN THIS GOAL HAS EVER
                BEEN USED. A permanent "استُخدمت 0 مرة" on every never-launched goal is noise on
                the very screen meant to help him pick one; the number earns its place on screen
                the first time it says something. */}
            {g.uses ? (
              <span className="flex items-center gap-2 text-xs text-text-secondary tabular-nums">
                {tf(t, 'launch.goalStats.uses', { n: g.uses })}
                {g.reach ? <>· {tf(t, 'launch.goalStats.reach', { n: g.reach })}</> : null}
              </span>
            ) : null}
            {/* NOT DISABLED ANY MORE, ON PURPOSE. Found live: an owner asked why he could not
                even OPEN this and compose his message while a template was under Meta's review —
                a wait that can run hours, during which the card blocked him from doing anything
                productive. `ask()`/`create()` already refuse this exact case with the server's
                own sentence — the same principle the admin panel already uses for an unapproved
                template: TRY, and let the one place that actually knows say no. A card that looks
                pressable and then refuses honestly beats one that never lets him find out what
                he is waiting for. The reason still shows below, informational now, not a lock. */}
            {g.available === false && g.unavailable_reason ? (
              <span className="mt-1 text-xs text-text-secondary">{g.unavailable_reason}</span>
            ) : null}
          </span>
        </button>
      ))}
    </section>
  );
}
