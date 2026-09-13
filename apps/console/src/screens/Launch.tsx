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
import { useEffect, useRef, useState } from 'react';
import {
  Cake, Clock, Gift, Info, Megaphone, RotateCcw, Search, Tag, type LucideIcon,
} from 'lucide-react';
import { Badge } from '../rj-ui/Badge';
import { Button } from '../rj-ui/Button';
import { HourRangePicker } from '../rj-ui/HourRangePicker';
import { RangeSlider } from '../rj-ui/RangeSlider';
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
 * Flow button under one of these four goals' sends; one that does not just gets the plain text
 * (`core/shape.py::for_send` — the multi-item carousel that used to sit here as the non-booking
 * fallback was deleted 2026-09-13, and its own reasoning explains why: every carousel template row
 * was `active: false`, so reminders' `merged_service_text` plain-text fallback already carried
 * every such send in production). Every other goal (announce/reward_loyal) always sends plain
 * text — no Flow applies. Hand-mirrored, same posture Messages.tsx's own `GOAL_TEMPLATE_TYPE`
 * already takes: a table this small drifting is a one-line fix, not worth a network round trip for
 * exactly one screen's preview.
 */
export const FLOW_ELIGIBLE_GOALS = new Set(['win_back', 'occasion', 'service_offer', 'package_offer']);

// Which of three rewards a campaign gives (services/campaigns/app/core/models.py's own
// REWARD_ENABLED_GOALS) — started as the `occasion`-only pilot, then `win_back`, then
// `service_offer`/`package_offer` once those proved out (both fire `mkt_offer`). BUG FIXED HERE
// (2026-09-13): this set had gone stale at the `occasion`/`win_back` pilot stage — an owner
// launching a service_offer or package_offer campaign never saw the reward-type picker at all,
// silently defaulting to a plain discount with no way to choose a gift or points instead, even
// though the backend has accepted that choice for those two goals since the day it shipped.
// `reward_loyal` (redeeming an EXISTING balance, a different mechanic) and `announce` (offers
// nothing) stay out, matching the backend exactly.
const REWARD_ENABLED_GOALS = new Set(['occasion', 'win_back', 'service_offer', 'package_offer']);

// THE SINGLE-ITEM QUICK-REPLY BUTTON'S OWN ELIGIBLE GOALS (core/shape.py's BUTTON_TYPES,
// 2026-09-13) — every goal EXCEPT the ones with no launch card at all. Mirrored by goal name
// (BUTTON_TYPES is keyed by template_type, which this screen never carries) the same way
// FLOW_ELIGIBLE_GOALS above already mirrors BOOKING_TYPES.
export const BUTTON_ELIGIBLE_GOALS = new Set([
  'win_back', 'occasion', 'service_offer', 'package_offer', 'reward_loyal', 'announce',
]);

/**
 * EACH GOAL'S OWN COLOUR, hand-mirrored from the approved mockup's own per-goal assignment —
 * every rail row used to draw the SAME neutral/accent icon regardless of which goal it was,
 * which is exactly the "no colour differentiation" the owner flagged directly, comparing this
 * screen against the mockup card by card. Same tone vocabulary/classes Messages.tsx's own
 * `TONE_ICON_BG` already uses, so a goal's colour reads consistently with everything else in the
 * product rather than inventing a second palette. A goal missing here (a future addition) simply
 * falls back to `accent` below, never to a colourless grey.
 */
const GOAL_TONE: Record<string, 'accent' | 'warning' | 'danger' | 'info'> = {
  service_offer: 'accent', package_offer: 'warning', win_back: 'danger',
  reward_loyal: 'accent', occasion: 'info', announce: 'info',
};
const GOAL_TONE_ICON_BG: Record<string, string> = {
  accent: 'bg-accent-soft text-accent-on-soft', warning: 'bg-warning-soft text-warning-on-soft',
  danger: 'bg-danger-soft text-danger-on-soft', info: 'bg-info-soft text-info-on-soft',
};
function goalToneClass(goal: string): string {
  return GOAL_TONE_ICON_BG[GOAL_TONE[goal] ?? 'accent'];
}

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
  /** THE MESSAGE MAY BE REAL WHILE IT IS NOT YET SENDABLE (2026-09-13) — a template still under
   *  Meta's review, or never submitted at all, still has real words, a real audience, and real
   *  blanks he can fill; only pressing launch is refused. `undefined`/`true` both read as sendable
   *  (an older server that never sent this field never blocked anything either). */
  template_active?: boolean;
  template_inactive_reason?: string;
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
 *  `translate` export exists for, so a pure-function test can call this without a provider.
 *
 *  `announce` USED TO NAME ITS OWN LABEL HERE ("ما الجديد؟") — dead since 2026-09-13: its
 *  template no longer declares an "owner" blank at all (Meta forbids free-typed promotional
 *  content in an approved template's variable — the real bug this fixed), so `hasBlank(picked,
 *  'owner')` can never be true for it any more and this branch could never run. `goal` is kept
 *  as a parameter rather than dropped: the day a future goal legitimately needs its own free-blank
 *  wording, this is where that one line goes, not a reason to keep an unreachable one today. */
export function freeBlankLabel(_goal: string, t: (key: string) => string = (k) => translate('ar', k)): string {
  return t('launch.freeBlank.default');
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
  // SEVERAL SERVICES, ONE OFFER (2026-09-13) — every one selected is named together in the same
  // merged message (reminders' own `merged_service_text`, never a per-item carousel card — that
  // path was deleted 2026-09-13); `serviceIds` is the whole selection, in the order he picked
  // them, which is also the order the names are listed in.
  const [serviceIds, setServiceIds] = useState<string[]>([]);
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
  // WHICH KIND THE %/ريال SEGMENTED IS ON — BUG FIXED HERE (2026-09-14, the owner's own report):
  // this used to be read straight off `offerValue.includes('ريال')`, so with the amount box still
  // empty (nothing typed yet) `offerValue` was always '' either way and the control could never
  // even LOOK switched — a tap on «ريال» composed nothing (there was no number to compose it
  // with) and the segmented stayed stuck on «نسبة» until he typed a digit first. Tracked as its
  // OWN state now, independent of whether a number exists yet.
  const [discountKind, setDiscountKind] = useState<'pct' | 'sar'>('pct');
  /**
   * WHICH OF THREE REWARDS THIS CAMPAIGN GIVES — `occasion` ONLY, for now (the pilot;
   * `win_back`/`service_offer`/`package_offer` still only ever give the discount they always
   * have). "discount" reproduces exactly today's screen; `gift` and `points` are the two new
   * doors (`services/campaigns/app/core/models.py::validate_reward`).
   */
  const [rewardType, setRewardType] = useState<'discount' | 'gift' | 'points'>('discount');
  // THE "points" REWARD'S OWN AMOUNT — a plain string while he types, same reasoning as
  // `offerValue`'s own digit-folding above applies at the point it is read, not while it is held.
  const [rewardPoints, setRewardPoints] = useState('');
  const [services, setServices] = useState<Service[] | null>([]);
  // `package_offer`'s OWN answer for the "catalogue" blank — a package, never a service (packages
  // feature). Fetched the same way `services` is: this service holds no catalogue of its own.
  const [packages, setPackages] = useState<Package[] | null>([]);
  // SEVERAL PACKAGES, SAME REASONING AS `serviceIds` above.
  const [packageIds, setPackageIds] = useState<string[]>([]);
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
   * «كافئ المخلصين»'s OWN AUDIENCE THRESHOLDS (2026-09-12 backend, 2026-09-13 this control) —
   * never a fixed 90-day/3-visit rule baked into the code (services/campaigns'
   * `Campaign.loyalty_window_days`/`loyalty_min_visits` own note). Defaults match what every
   * campaign got before this control existed, so a shop that never drags either slider sees
   * exactly today's behaviour.
   */
  const [loyaltyWindowDays, setLoyaltyWindowDays] = useState(90);
  const [loyaltyMinVisits, setLoyaltyMinVisits] = useState(3);
  // DEBOUNCED — a slider fires many `input` events while it is being dragged, and a live preview
  // re-fetch on every single one would flood the preview endpoint. 300ms of stillness before the
  // real ask() call, cleared on every intervening move.
  const loyaltyDebounce = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

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

  // WHICH OF THREE REWARDS THE WIRE ACTUALLY CARRIES — "discount"/0 for every goal outside
  // `REWARD_ENABLED_GOALS`, so a goal that has never heard of this field sends exactly what it
  // always sent (the server's own default matches, but sending it explicitly here keeps both
  // sides reading the same value rather than trusting two defaults to agree forever).
  const rewardEnabled = REWARD_ENABLED_GOALS.has(picked?.goal ?? '');
  const wireRewardType = rewardEnabled ? rewardType : 'discount';
  const wireRewardPoints = rewardEnabled && rewardType === 'points'
    ? Number(western(rewardPoints).replace(/[^0-9]/g, '')) || 0 : 0;
  // WHAT STILL NEEDS FILLING BEFORE THE PREVIEW CAN EVEN BE ASKED FOR — mirrors
  // `validate_reward`'s own three checks, so the button greys out before he pastes it as a
  // refusal from the server instead. `package_offer` names PACKAGES, not services, for its
  // "gift" — `packageIds` is the array that goal's own catalogue picker fills (see the picker's
  // own note on why `mkt_offer` shares one blank kind between the two).
  const occasionRewardIncomplete = rewardEnabled && (
    (rewardType === 'discount' && !offerValue)
    || (rewardType === 'gift'
        && (picked?.goal === 'package_offer' ? packageIds.length === 0 : serviceIds.length === 0))
    || (rewardType === 'points' && wireRewardPoints <= 0)
  );

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

  // `loyaltyOverride` — THE SLIDER'S OWN FRESH VALUE, not the state it just asked for (2026-09-13).
  // React's state update from the SAME `onChange` that triggers this debounced call has not
  // necessarily committed yet by the time this closure runs; the event's own local `v` is never
  // stale, so the live-preview call passes it straight through instead of trusting the state read.
  const ask = async (goal: Goal, loyaltyOverride?: { windowDays?: number; minVisits?: number }) => {
    if (!previewAction) return;
    setBusy(true); setError(''); setPreview(null);
    try {
      setPreview(await call<Preview>(session, previewAction, {
        goal: goal.goal,
        owner_text: ownerText,
        // SEVERAL SERVICES/PACKAGES, ONE OFFER (2026-09-13) — every one selected, in order.
        // MUTUALLY EXCLUSIVE — only `package_offer` ever sets the package fields.
        service_ids: serviceIds,
        package_ids: packageIds,
        // «كافئ المخلصين»'s OWN THRESHOLDS — meaningless for every other goal, and today's
        // defaults (90/3) for a goal that never touches the sliders below.
        loyalty_window_days: loyaltyOverride?.windowDays ?? loyaltyWindowDays,
        loyalty_min_visits: loyaltyOverride?.minVisits ?? loyaltyMinVisits,
        // THE BRANCH IS IN THE PREVIEW TOO, and that is the whole point of previewing: the count
        // he decides on must be the count that goes out.
        branch_id: branchId,
        offer_value: offerValue,
        service_names: serviceIds.map((id) => (services ?? []).find((x) => x.id === id)?.name ?? ''),
        package_names: packageIds.map((id) => (packages ?? []).find((x) => x.id === id)?.name ?? ''),
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
        // WHICH OF THREE REWARDS — `occasion` ONLY; see `wireRewardType`'s own comment above.
        reward_type: wireRewardType,
        reward_points: wireRewardPoints,
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

  // ── THE RAIL — ALWAYS VISIBLE, exactly the approved mockup's own shape: a slim goal picker
  // beside the canvas, not a full-width step the builder replaces. Picking a different goal never
  // leaves this screen; it just changes what the centre panel holds, the same way the campaigns
  // tab's own management screen never rebuilds its rail when a row is opened. */
  const visibleGoals = (isReady(goals) ? goals : [])
    .filter((g) => (!activeCategory || g.category === activeCategory)
      && (!search.trim() || g.title.includes(search.trim()) || g.line.includes(search.trim())));
  const rail = (
    <div className="flex flex-col gap-2 lg:sticky lg:top-4 lg:w-72 lg:shrink-0">
      {goalsFailed ? (
        <p className="text-sm text-text-secondary">{t('launch.goalsReadFailed')}</p>
      ) : isDenied(goals) ? (
        <p className="text-sm text-text-secondary">{t('launch.goalsDenied')}</p>
      ) : hasFailed(goals) ? (
        // «لا أهداف متاحة» IS A CLAIM ABOUT HIS ENABLED APPS. Said after a failed read it sends
        // him to the pricing page for something he already owns.
        <p className="text-sm text-text-secondary">{t('launch.goalsReadFailed')}</p>
      ) : goals.length === 0 ? (
        <p className="text-sm text-text-secondary">{t('launch.noGoalsAvailable')}</p>
      ) : (
        <div className="flex flex-col gap-2 rounded-card border border-border-subtle bg-surface-1 p-3 shadow-sm">
          <label className="flex items-center gap-2 rounded-lg bg-surface-1 border border-border-subtle px-3 py-2">
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
                                 activeCategory === '' ? 'bg-text-primary text-surface-1' : 'bg-surface-1 border border-border-subtle text-text-secondary'].join(' ')}>
                {t('launch.category.all')}
              </button>
              {categories.map((cat) => (
                <button key={cat} type="button" onClick={() => setActiveCategory(cat)}
                       className={['rounded-full px-3 py-1 text-xs font-medium',
                                   activeCategory === cat ? 'bg-text-primary text-surface-1' : 'bg-surface-1 border border-border-subtle text-text-secondary'].join(' ')}>
                  {cat}
                </button>
              ))}
            </div>
          ) : null}

          <div className="flex flex-col gap-1">
            {visibleGoals.map((g) => {
              const Icon = g.icon ? (GOAL_ICONS[g.icon] ?? Tag) : Tag;
              const active = picked?.goal === g.goal;
              return (
                <button
                  key={g.goal}
                  type="button"
                  onClick={() => {
                    setPicked(g); setServiceIds([]); setPackageIds([]);
                    setLoyaltyWindowDays(90); setLoyaltyMinVisits(3);
                    setRewardType('discount'); setRewardPoints('');
                  }}
                  className={['flex items-start gap-2.5 rounded-lg px-2.5 py-2 text-start transition-colors',
                             active ? 'bg-accent-soft ring-1 ring-inset ring-accent/30' : 'hover:bg-surface-2'].join(' ')}
                >
                  <span className={['flex h-8 w-8 shrink-0 items-center justify-center rounded-full',
                                    goalToneClass(g.goal)].join(' ')}>
                    <Icon size={15} aria-hidden />
                  </span>
                  <span className="flex min-w-0 flex-col gap-0.5">
                    <span className="flex flex-wrap items-center gap-1.5">
                      <span className="truncate text-sm font-medium">{g.title}</span>
                      {g.template_status && g.template_status !== 'unknown' ? (
                        <Badge tone={TEMPLATE_STATUS_META[g.template_status].tone}>
                          {TEMPLATE_STATUS_META[g.template_status].label}
                        </Badge>
                      ) : null}
                    </span>
                    <span className="truncate text-xs text-text-secondary">{g.line}</span>
                    {/* SHOWN ONLY WHEN THIS GOAL HAS EVER BEEN USED — a permanent "استُخدمت 0
                        مرة" on every never-launched goal is noise on the one screen meant to help
                        him pick one. */}
                    {g.uses ? (
                      <span className="flex items-center gap-2 text-xs text-text-muted tabular-nums">
                        {tf(t, 'launch.goalStats.uses', { n: g.uses })}
                        {g.reach ? <>· {tf(t, 'launch.goalStats.reach', { n: g.reach })}</> : null}
                      </span>
                    ) : null}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );

  // ── NOTHING PICKED YET — the rail is the whole story; the canvas says so rather than sitting
  // empty, which would read as broken rather than as "waiting for a choice". */
  if (!picked) {
    return (
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
        {rail}
        <div className="flex flex-1 items-center justify-center rounded-card border border-dashed border-border-subtle p-10 text-center text-sm text-text-secondary">
          {t('launch.step1.prompt')}
        </div>
      </div>
    );
  }

  // ── THE BUILDER + THE PHONE — what will happen, and the one press ────────────────────────────
  {
    // THE MATCHING REASON, IF ONE EXISTS AND HAS ACTUALLY LOADED — absent for the goals with no
    // automatic counterpart yet (announce, service_offer/package_offer), and absent
    // while `reasons` is still `null` (loading or denied).
    const linkedReasonId = GOAL_REASON_ID[picked.goal];
    const linkedReason = linkedReasonId ? (reasons ?? []).find((r) => r.id === linkedReasonId) : undefined;
    const flowEligible = FLOW_ELIGIBLE_GOALS.has(picked.goal);
    const hasBookings = owns(owned ?? null, 'feature.bookings') === true;
    // THE SINGLE-ITEM QUICK-REPLY BUTTON (core/shape.py, 2026-09-13) — BUG FIXED HERE: this phone
    // never showed it at all before, regardless of how many services were scoped, so picking one
    // service vs. several looked identical even though the real send attaches a real button for
    // exactly one. Same two entitlements the server's own `_card_button_allowed` requires
    // (bookings AND the AI assistant app) — and never alongside the Flow button above: shape.py
    // checks `opens_booking` FIRST, so a booking goal with bookings owned always gets the Flow,
    // never this button, whatever the item count.
    const hasAssistant = owns(owned ?? null, 'feature.whatsapp') === true;
    const scopedItems = picked.goal === 'package_offer' ? packageIds : serviceIds;
    const singleItemButtonShown = BUTTON_ELIGIBLE_GOALS.has(picked.goal) && hasBookings
      && hasAssistant && scopedItems.length === 1 && !(flowEligible && hasBookings);
    // ── THE PHONE LANE — the mockup's third column, ALWAYS beside the builder rather than
    // gated behind a preview call: the same rendering engine every other preview in the product
    // uses, fed whatever this form currently holds. Numbers (reach/excluded/the launch button)
    // arrive only once `preview` has actually answered — a phone showing a plan is honest even
    // before the count behind it is known, a phone showing a count it never asked for is not.
    const phone = (
      <div className="flex flex-col gap-3 lg:sticky lg:top-4 lg:w-72 lg:shrink-0">
        {/* AN EMPTY BUBBLE READS AS BROKEN, NOT AS "NOTHING YET" — `WhatsAppTemplatePreview` draws
            whatever `data.body` holds, including nothing at all, and a blank speech bubble inside
            a real phone chrome looks like a rendering bug rather than an unanswered question. Real
            text exists only once the server has actually rendered it (`ask()`'s own `preview.message`
            — this screen composes nothing client-side, see the module's own docstring), so until
            then the frame holds a plain waiting sentence instead of an empty shape. */}
        {preview?.message ? (
          <WhatsAppTemplatePreview
            data={(() => {
              const data: WaTemplateData = { body: preview.message ?? '' };
              if (flowEligible && hasBookings) {
                data.flowButton = { flowName: 'booking', text: t('launch.preview.bookingButton') };
              } else if (singleItemButtonShown) {
                data.replyButton = { text: t('launch.preview.singleItemButton') };
              }
              return data;
            })()}
            fetchFlowJson={!flowEligible || !hasBookings ? undefined : (flowName: string) => {
              const a = action(catalog, 'operations.whatsapp_flow_json');
              if (!a) return Promise.reject(new Error(t('launch.previewFailed')));
              return call<FlowJson>(session, a, { name: flowName });
            }}
          />
        ) : (
          <div className="flex min-h-[280px] flex-col items-center justify-center gap-2 rounded-card border border-dashed border-border-subtle p-6 text-center">
            <p className="text-sm text-text-secondary">{t('launch.previewPending')}</p>
          </div>
        )}

        <div className="flex flex-col gap-2 rounded-card bg-surface-1 p-4 shadow-sm">
          {preview ? (
            <>
              {preview.when ? (
                <p className="text-sm font-medium text-text-secondary">{preview.when}</p>
              ) : null}
              <p className="text-sm">
                {t('launch.reaches.prefix')} <b className="tabular-nums">{preview.reaches ?? 0}</b> {t('launch.reaches.suffix')}
              </p>
              {preview.excluded ? (
                <p className="text-xs text-text-secondary">{tf(t, 'launch.excludedNote', { n: preview.excluded })}</p>
              ) : null}
              {preview.too_recent ? (
                <p className="text-xs text-text-secondary">{tf(t, 'launch.tooRecentNote', { n: preview.too_recent })}</p>
              ) : null}
              {/* THE ONE THING THIS STATUS ACTUALLY FORBIDS IS THE PRESS BELOW, NOT THE WORDS
                  ABOVE (2026-09-13) — the message, the reach count and every field on this screen
                  stay real and usable while a template is still under Meta's review or never
                  submitted; only the launch button reads this. */}
              {preview.template_active === false ? (
                <p className="text-sm text-warning">{preview.template_inactive_reason}</p>
              ) : preview.spread?.refused ? (
                <p className="text-sm text-danger">{preview.spread.refused}</p>
              ) : preview.spread_says ? (
                <p className="text-sm text-success">{preview.spread_says}</p>
              ) : null}
              {(preview.why ?? []).map((line) => (
                <p key={line} className="text-xs text-text-secondary">{line}</p>
              ))}
            </>
          ) : null}
          {/* NO SECOND "اضغط عرض ما سيصل" HERE — found live, a real duplicate: the phone
              frame right above this box already carries that same waiting sentence
              (`preview?.message` gate), so a second copy in this box repeated it back to back on
              screen for no reason other than both blocks sharing the same `!preview` guard. */}
          {error ? <p className="text-sm text-danger">{error}</p> : null}
          <div className="flex flex-wrap gap-2">
            {!preview ? (
              <Button disabled={busy
                                || (hasBlank(picked, 'amount') && !offerValue)
                                || (hasBlank(picked, 'date') && !endsOn)
                                || Boolean(occasionRewardIncomplete)}
                      onClick={() => void ask(picked)}>{t('launch.previewButton')}</Button>
            ) : (
              <Button
                disabled={busy || !createAction || Boolean(preview.spread?.refused)
                          || preview.template_active === false}
                onClick={async () => {
                  if (!createAction || preview.spread?.refused || preview.template_active === false) return;
                  setBusy(true); setError('');
                  try {
                    await call(session, createAction, {
                      goal: picked.goal,
                      owner_text: ownerText,
                      service_ids: serviceIds,
                      package_ids: packageIds,
                      loyalty_window_days: loyaltyWindowDays,
                      loyalty_min_visits: loyaltyMinVisits,
                      branch_id: branchId,
                      offer_value: offerValue,
                      service_names: serviceIds.map((id) => (services ?? []).find((x) => x.id === id)?.name ?? ''),
                      package_names: packageIds.map((id) => (packages ?? []).find((x) => x.id === id)?.name ?? ''),
                      expires_at: expiresAt,
                      fire_at: combinedFireAt,
                      window_start_hour: windowOn ? windowStartHour : 0,
                      window_end_hour: windowOn ? windowEndHour : 24,
                      window_weekdays: windowOn ? windowWeekdays : [],
                      reward_type: wireRewardType,
                      reward_points: wireRewardPoints,
                    });
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
        </div>
      </div>
    );
    return (
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
        {rail}
      <section className="flex flex-1 flex-col gap-3 rounded-card bg-surface-1 p-4 shadow-sm">
        {/* NO "تغيير الهدف" BUTTON — the rail beside this panel IS the goal switcher now
            (2026-09-13, matching the approved mockup): every goal already sits one press away on
            it, always visible, so a second control here duplicated the same choice. */}
        <div className="flex items-center gap-2.5">
          <span className={['flex h-9 w-9 shrink-0 items-center justify-center rounded-full', goalToneClass(picked.goal)].join(' ')}>

            {(() => {
              const Icon = picked.icon ? (GOAL_ICONS[picked.icon] ?? Tag) : Tag;
              return <Icon size={17} aria-hidden />;
            })()}
          </span>
          <div className="flex min-w-0 flex-col">
            <span className="font-medium">{picked.title}</span>
            {picked.behaviour ? (
              <span className="truncate text-xs text-text-secondary">{picked.behaviour}</span>
            ) : null}
          </div>
        </div>

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

        {/* «من هم عملاؤك المخلصون؟» — reward_loyal ONLY. Two live sliders, never a fixed rule
            (2026-09-13, the owner's own instruction) — dragging either re-asks the preview so
            the reach count moves with the slider itself, not after a separate button press. */}
        {picked.goal === 'reward_loyal' ? (
          <div className="flex flex-col gap-3 rounded-card border border-border-subtle p-3">
            <span className="text-sm font-medium">{t('launch.loyalty.title')}</span>
            <RangeSlider
              label={t('launch.loyalty.windowLabel')}
              value={loyaltyWindowDays}
              min={7}
              max={365}
              onChange={(v) => {
                setLoyaltyWindowDays(v);
                if (loyaltyDebounce.current) clearTimeout(loyaltyDebounce.current);
                if (preview) {
                  loyaltyDebounce.current = setTimeout(
                    () => void ask(picked, { windowDays: v }), 300);
                }
              }}
              valueLabel={tf(t, 'launch.loyalty.windowValue', { n: loyaltyWindowDays })}
              testId="loyalty-window-days"
            />
            <RangeSlider
              label={t('launch.loyalty.minVisitsLabel')}
              value={loyaltyMinVisits}
              min={1}
              max={50}
              onChange={(v) => {
                setLoyaltyMinVisits(v);
                if (loyaltyDebounce.current) clearTimeout(loyaltyDebounce.current);
                if (preview) {
                  loyaltyDebounce.current = setTimeout(
                    () => void ask(picked, { minVisits: v }), 300);
                }
              }}
              valueLabel={tf(t, 'launch.loyalty.minVisitsValue', { n: loyaltyMinVisits })}
              testId="loyalty-min-visits"
            />
            <p className="text-xs text-text-secondary">{t('launch.loyalty.hint')}</p>
          </div>
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
                    className="h-11 rounded-lg bg-surface-1 border border-border-subtle px-3 text-sm"
                  />
                </label>
                <label className="flex flex-col gap-1">
                  <span className="text-xs text-text-secondary">{t('launch.when.hourLabel')}</span>
                  <input
                    type="text"
                    value={launchHour}
                    onChange={(e) => { setLaunchHour(e.target.value); setPreview(null); }}
                    dir="ltr"
                    className="h-11 w-24 rounded-lg bg-surface-1 border border-border-subtle px-3 text-sm"
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
              className="rounded-lg bg-surface-1 border border-border-subtle p-3 text-sm"
            />
            <span className="text-xs text-text-secondary tabular-nums">
              {ownerText.length} / 60
            </span>
          </label>
        ) : null}

        {/* ── which of three rewards, REWARD_ENABLED_GOALS only ──────────────────────────────
            THE OWNER PICKS ONE, AND THE MESSAGE IS COMPOSED AROUND IT SERVER-SIDE — no new Meta
            template exists for this: the body stays reward-agnostic and one slot carries the
            whole composed sentence (`rendering.campaign_slots`'s own "reward" branch). */}
        {rewardEnabled ? (
          <div className="flex flex-col gap-2 rounded-card border border-border-subtle p-3">
            <span className="text-sm font-medium">{t('launch.reward.title')}</span>
            <Segmented
              ariaLabel={t('launch.reward.title')}
              value={rewardType}
              onChange={(v) => { setRewardType(v as 'discount' | 'gift' | 'points'); setPreview(null); }}
              options={[
                { value: 'discount', label: t('launch.reward.discount') },
                { value: 'gift', label: t('launch.reward.gift') },
                { value: 'points', label: t('launch.reward.points') },
              ]}
            />
          </div>
        ) : null}

        {/* WHICH SERVICE(S), when the goal is about them — MORE THAN ONE, now (2026-09-13): every
            selected service is named together in the same merged message (reminders' own
            `merged_service_text`), never a free paragraph he'd have to write himself. The cycle
            lock (§10.9.1) holds back whoever took EVERY selected one too recently — ready for even
            one is ready for the offer, since the message names all the chosen items together
            regardless of which one applies to him.
            `package_offer` shares this SAME blank kind (one template, `mkt_offer`, approved once
            for both — see core/models.py's own note) but fills it with PACKAGES instead: no cycle
            lock applies to them (a package has no single rhythm to hold anyone back on), so this
            is purely which packages the message names. Reads `rewardEnabled` alongside
            `hasBlank(picked, 'catalogue')` for the same reason the service picker below does:
            `mkt_offer` no longer declares a "catalogue" blank of its own now that its slot is
            "reward" — see that picker's own note.
            MOVED HERE, RIGHT AFTER THE REWARD-TYPE PICKER (2026-09-14, the owner's own report):
            this used to render after the amount/points input AND the end-date field, so ITS OWN
            vertical position shifted depending on which reward was picked — gift renders neither
            of those two fields, so «على أي خدمة؟» jumped straight up under the reward picker for
            gift alone, while discount/points still had a field between them. One fixed slot now,
            whatever the reward. */}
        {(hasBlank(picked, 'catalogue') || rewardEnabled) && picked.goal === 'package_offer' ? (
          <div className="flex flex-col gap-1.5">
            <span className="text-sm">{t('launch.packagePickLabel')}</span>
            <div className="flex flex-wrap gap-1.5" role="group" aria-label={t('launch.packagePickLabel')}>
              {(packages ?? []).length === 0 ? (
                <p className="text-xs text-text-secondary">{t('launch.packagePickPlaceholder')}</p>
              ) : (packages ?? []).map((p) => {
                const active = packageIds.includes(p.id);
                return (
                  <button
                    key={p.id}
                    type="button"
                    aria-pressed={active}
                    onClick={() => {
                      setPackageIds(active ? packageIds.filter((id) => id !== p.id) : [...packageIds, p.id]);
                      setPreview(null);
                    }}
                    className={['rounded-full px-3 py-1.5 text-xs font-medium transition-colors',
                               active ? 'bg-text-primary text-surface-1' : 'bg-surface-1 border border-border-subtle text-text-secondary hover:bg-surface-3'].join(' ')}
                  >
                    {p.name}
                  </button>
                );
              })}
            </div>
          </div>
        ) : hasBlank(picked, 'catalogue')
            || (rewardEnabled && rewardType !== 'points') ? (
          <div className="flex flex-col gap-1.5">
            <span className="text-sm">{t('launch.servicePickLabel')}</span>
            {/* ORDERED LEAST-TAKEN FIRST, SILENTLY — «عرض على خدمة» exists for exactly this: an
                owner looking for the service that needs a push, not the one that already sells
                itself. `serviceDemand`'s own comment is why this is chain-wide, never one
                branch's own count. Plain names only, no count printed on the chip itself —
                the ORDER is the feature; a number beside every row is a second thing to read for
                a picker that should stay a one-glance choice. */}
            <div className="flex flex-wrap gap-1.5" role="group" aria-label={t('launch.servicePickLabel')}>
              {(services ?? []).length === 0 ? (
                <p className="text-xs text-text-secondary">{t('launch.servicePickPlaceholder')}</p>
              ) : (services ?? [])
                .slice()
                .sort((a, b) => (serviceDemand[a.id] ?? 0) - (serviceDemand[b.id] ?? 0))
                .map((s) => {
                  const active = serviceIds.includes(s.id);
                  return (
                    <button
                      key={s.id}
                      type="button"
                      aria-pressed={active}
                      onClick={() => {
                        setServiceIds(active ? serviceIds.filter((id) => id !== s.id) : [...serviceIds, s.id]);
                        setPreview(null);
                      }}
                      className={['rounded-full px-3 py-1.5 text-xs font-medium transition-colors',
                                 active ? 'bg-text-primary text-surface-1' : 'bg-surface-1 border border-border-subtle text-text-secondary hover:bg-surface-3'].join(' ')}
                    >
                      {s.name}
                    </button>
                  );
                })}
            </div>
          </div>
        ) : null}

        {/* عدد النقاط — REWARD_ENABLED_GOALS + `points` ONLY. Hides the discount value and the
            service picker: a points reward names no service and no percentage, only the credit
            itself. */}
        {rewardEnabled && rewardType === 'points' ? (
          <label className="flex flex-col gap-1">
            <span className="text-sm">{t('launch.reward.pointsLabel')}</span>
            <input
              type="number"
              min={1}
              dir="ltr"
              value={western(rewardPoints).replace(/[^0-9]/g, '')}
              onChange={(e) => {
                setRewardPoints(western(e.target.value).replace(/[^0-9]/g, ''));
                setPreview(null);
              }}
              className="h-11 w-24 rounded-lg bg-surface-1 border border-border-subtle px-3 text-center text-sm tabular-nums"
            />
          </label>
        ) : null}

        {/* ── how much ────────────────────────────────────────────────────────────────────
            TWO BUTTONS AND A NUMBER, not a free field. He taps «نسبة» or «مبلغ» and types the
            number; we build «20%» or «50 ريال». A field that accepts anything accepts «خصم كبير»,
            and the send refuses it after he has already decided he is done.
            A REWARD-ENABLED GOAL READS ITS OWN `rewardType` HERE RATHER THAN
            `hasBlank(picked, 'amount')` — its template's own blank is now "reward", not
            "amount" (no new Meta template exists for this — see the module's own note), so the
            server no longer lists "amount" among such a goal's blanks at all. */}
        {(rewardEnabled ? rewardType === 'discount' : hasBlank(picked, 'amount')) ? (
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
                  setOfferValue(n ? (discountKind === 'sar' ? `${n} ${sar}` : `${n}%`) : '');
                  setPreview(null);
                }}
                className="h-11 w-24 rounded-lg bg-surface-1 border border-border-subtle px-3 text-center text-sm tabular-nums"
              />
              <Segmented
                ariaLabel={t('launch.discountKindAria')}
                value={discountKind}
                onChange={(kind) => {
                  setDiscountKind(kind as 'pct' | 'sar');
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
              className="h-11 rounded-lg bg-surface-1 border border-border-subtle px-3 text-sm"
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
              className="h-11 rounded-lg bg-surface-1 border border-border-subtle px-3 text-sm"
            />
            <span className="text-xs text-text-secondary">
              {t('launch.occasionDateNote')}
            </span>
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
              className="h-11 rounded-lg bg-surface-1 border border-border-subtle px-3 text-sm"
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
        <div className="flex flex-col gap-2 rounded-card border border-dashed border-accent/35 bg-accent-soft/25 p-3">
          <div className="flex items-center justify-between gap-2">
            <span className="flex items-center gap-2 text-sm font-medium">
              <Clock size={15} className="text-accent" aria-hidden />
              {t('launch.window.title')}
            </span>
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
      </section>
        {phone}
      </div>
    );
  }
}
