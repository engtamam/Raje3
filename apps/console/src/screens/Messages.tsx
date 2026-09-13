/**
 * «الحملات» — what goes out in my name.
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
 * AND «حملاتي» IS SHOWN LOCKED WHEN THE CAMPAIGNS APP IS NOT ENABLED, never removed. It used to vanish —
 * `campaigns === null` rendered nothing at all — and a section that disappears reads as a fault,
 * while a capability nobody can see is one nobody can buy.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import type { LucideIcon } from 'lucide-react';
import {
  AlertTriangle, Award, BarChart3, Cake, CalendarClock, ClipboardCheck, Clock, Clock3, Compass,
  FileBarChart, FileText, Gauge, Gift, Heart, Hourglass, Lock, Mail, MessageSquare,
  Megaphone, Pause, RotateCcw, ShieldAlert, ShieldCheck, Star, Tag, Users, Wallet, X, Zap,
} from 'lucide-react';
import { Badge } from '../rj-ui/Badge';
import { BarCompare } from '../rj-ui/BarCompare';
import { EmptyState } from '../rj-ui/EmptyState';
import { FilterRail, type FilterRailItem } from '../rj-ui/FilterRail';
import { KpiCard } from '../rj-ui/KpiCard';
import { PageHeader } from '../rj-ui/PageHeader';
import { Segmented } from '../rj-ui/Segmented';
import { Table, type TableColumn } from '../rj-ui/Table';
import { DENIED, hasFailed, isDenied, isLoading, isReady, type Loading } from '../loading';
import { Skeleton } from '../rj-ui/Skeleton';
import { TEMPLATE_STATUS_META, type TemplateStatus } from './templateStatus';
import { Toggle } from '../rj-ui/Toggle';
import { Button } from '../rj-ui/Button';
import { AssistantHint } from '../AssistantHint';
import { Launch } from './Launch';
import { LockedCard } from './Locked';
import { MessagePreview } from './MessagePreview';
import { Modal } from '../rj-ui/Modal';
import { WhatsAppTemplatePreview, type FlowJson, type WaCarouselCard } from '../rj-ui/WhatsAppPreview';
import { APP_ROWS, owns, type Owned } from '../apps';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';
import { digitsOnly } from '../digits';
import { useOperatorI18n, tf } from '../operator-i18n';
import './messages-i18n';

/**
 * A campaign as the service answers with it. `state` is one of `draft|active|paused|done` — and
 * the screen used to compare it against `'running'`, a value the model has never had, so the
 * pause button never appeared on a single live campaign and «أوقفها» was unreachable for its
 * whole life. There is no `name` either: a campaign is named by its goal.
 */
interface Campaign {
  id: string; goal?: string; state?: string; sent?: number;
  /** WHEN IT LAUNCHES — a future value with `last_evaluated === 0` means job-service is holding
   *  this campaign for its exact moment (campaigns' own core/models.py::Campaign), not yet fired
   *  even once. 0 means "no schedule" — an ordinary manual/standing campaign. */
  fire_at?: number;
  last_evaluated?: number;
  /** THE OWNER'S OWN RECURRING WINDOW — any goal may carry one (2026-09-12). Defaults
   *  (0, 24, []) mean "no window", the same "" `window_sentence()` itself returns for them. */
  window_start_hour?: number;
  window_end_hour?: number;
  window_weekdays?: number[];
  created?: number;
}

/** A goal's own key → translation key, so a row reads a real title rather than `win_back`. */
const GOAL_KEY: Record<string, string> = {
  win_back: 'messages.goal.win_back',
  reward_loyal: 'messages.goal.reward_loyal',
  announce: 'messages.goal.announce',
  occasion: 'messages.goal.occasion',
  service_offer: 'messages.goal.service_offer',
  // KEPT DELIBERATELY — `safety` was removed from `CARDS`/`GOAL_TEMPLATE` (goals.py) whole, so
  // no NEW campaign can ever carry this goal again, but a shop that already launched one before
  // the removal still has that row in its own history here. Without this entry that OLD row
  // would fall back to the raw key ("safety") instead of a real title — a real record made to
  // look broken by a feature removal it had nothing to do with.
  safety: 'messages.goal.safety',
};
function goalTitle(t: (key: string) => string, goal: string): string | undefined {
  const key = GOAL_KEY[goal];
  return key ? t(key) : undefined;
}

/** The four states, in his words rather than ours. */
const STATE_KEY: Record<string, string> = {
  active: 'messages.state.active',
  paused: 'messages.state.paused',
  done: 'messages.state.done',
  draft: 'messages.state.draft',
  // A DISPLAY-ONLY STATE, NEVER WRITTEN BY THE SERVER — the backend row's own `state` stays
  // `active` the whole time job-service holds it for a future moment; this is computed
  // client-side (`isScheduled()`, above) from `fire_at`/`last_evaluated`, the exact fields
  // campaigns' own core/tick.py already keys its rescue on.
  scheduled: 'messages.state.scheduled',
};
const STATE_TONE: Record<string, 'success' | 'warning' | 'neutral' | 'accent'> = {
  active: 'success', paused: 'warning', done: 'neutral', draft: 'neutral', scheduled: 'accent',
};
function stateLabel(t: (key: string) => string, state: string): string | undefined {
  const key = STATE_KEY[state];
  return key ? t(key) : undefined;
}

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
/** When it happened, in the words an owner uses. Same shape as "My Customers" — one habit, not two. */
function when(at: number, t: (key: string) => string): string {
  if (!at) return '';
  const days = Math.floor((Date.now() / 1000 - at) / 86_400);
  if (days <= 0) return t('messages.when.today');
  if (days === 1) return t('messages.when.yesterday');
  return tf(t, 'messages.when.daysAgo', { n: days });
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
  /** Which of the five classes this is. Not decoration: the class decides whether the message
   *  needs the customer's explicit consent, whether it may go out inside the quiet window
   *  (10pm–7am), what it counts against, and what Meta charges for it. Both fields come from the
   *  server — the key to colour by, the label to print — so the Arabic cannot drift from ours. */
  cls?: string;
  cls_label?: string;
  /** The badge — see templateStatus.ts's own docstring for why the words here are ours,
   *  never Meta's raw status name. */
  template_status?: TemplateStatus;
}

/** SOME AUTOMATIC REASONS ARE THE EXACT SAME MESSAGE «حملاتي» ALSO LAUNCHES BY HAND — «تجاوز
 *  دورته ولم يعد» (this reason) IS «رجّع اللي غابوا» (that goal), both `mkt_winback`, and until
 *  now nothing on either screen said so. An owner editing one wording had no way to know a
 *  second screen sends it too, and reading it as two unrelated messages is how a shop rewrites
 *  «رجّع اللي غابوا» and is confused when the automatic reminder still reads in the old words.
 *
 *  KEYED BY REASON ID, matched by hand against GOAL_TEMPLATE (campaigns/app/core/models.py) —
 *  not derived, because a shared `template_type` alone is not enough: `mkt_loyalty_activation`
 *  backs TWO reasons (`reward_within_reach` and `loyal_customer`) and only one of them is the
 *  same occasion «حملاتي»'s own `reward_loyal` goal describes. The remaining goals have no
 *  automatic counterpart at all yet (`announce`, `service_offer`/`package_offer`) —
 *  absent here on purpose, not an oversight. */
const REASON_GOAL: Record<string, { goal: string; title: string }> = {
  gone_missing: { goal: 'win_back', title: 'رجّع اللي غابوا' },
  personal_occasion: { goal: 'occasion', title: 'هنّئ في مناسبة' },
  loyal_customer: { goal: 'reward_loyal', title: 'كافئ المخلصين' },
};

/** THE FIVE, EACH WITH ITS OWN COLOUR, AND THE ONE THAT MATTERS MOST WEARS THE LOUDEST.
 *
 *  Marketing is the only class that needs consent, is barred from the quiet window and is billed
 *  at the higher rate — so it is the one an owner must be able to find in a list without reading.
 *  The other four behave alike and are toned to sit quietly. */
// «شخصية» WAS «neutral», AND UNDER THE VIOLET REBRAND THAT READ AS «تسويقية» IN DISGUISE. Neutral
// draws from `surface-2` — a pale violet-tinted grey on this theme — which sits close enough to
// `accent-soft` to be confused with it, and `accent` itself is reserved for the product's one
// primary action / active-nav colour under the 60-30-10 rule — not for a message-class label.
// `marketing` is the class an owner is legally answerable for (consent, billing, the quiet
// window), so it earns `warning` — a real "pay attention to this one" tone — while `success` gives
// «شخصية» its own third hue rather than a third shade of the same one.
const CLASS_TONE: Record<string, 'neutral' | 'success' | 'info' | 'warning' | 'danger'> = {
  service: 'info',
  personal: 'success',
  warning: 'warning',
  marketing: 'warning',
};

/** THE APPROVED MOCKUP'S OWN CARD LANGUAGE — every class/section gets its own colour, carried on
 *  BOTH the icon circle and a left stripe on the card itself (`border-inline-start`, RTL-safe,
 *  same technique the queue/log rows already use), not just a badge. `offers`/`bot` are
 *  SECTION_ORDER's own two extra buckets (goal-only cards, no `CLASS_TONE` entry of their own)
 *  — mapped here too, so every section this screen can ever show has a real colour, never falling
 *  back to plain grey. */
const SECTION_TONE: Record<string, 'info' | 'success' | 'warning' | 'danger' | 'accent' | 'neutral'> = {
  service: 'info', personal: 'success', marketing: 'warning',
  offers: 'danger', bot: 'neutral', warning: 'warning',
};
const TONE_VAR: Record<string, string> = {
  info: 'var(--info)', success: 'var(--success)', warning: 'var(--warning)',
  danger: 'var(--danger)', accent: 'var(--accent)', neutral: 'var(--border-subtle)',
};
const TONE_ICON_BG: Record<string, string> = {
  info: 'bg-info-soft text-info-on-soft', success: 'bg-success-soft text-success-on-soft',
  warning: 'bg-warning-soft text-warning-on-soft', danger: 'bg-danger-soft text-danger-on-soft',
  accent: 'bg-accent-soft text-accent-on-soft', neutral: 'bg-surface-2 text-text-secondary',
};
/** THE RAIL'S OWN DOT — the SAME tone as the card's own stripe/icon above, never a second,
 *  independently-assigned colour rotation (that mismatch — the rail picking a colour by POSITION
 *  while the card picked one by MEANING — is exactly what made the rail's dots disagree with the
 *  cards they filter). */
const TONE_DOT: Record<string, string> = {
  info: 'bg-info', success: 'bg-success', warning: 'bg-warning', danger: 'bg-danger',
  accent: 'bg-accent', neutral: 'bg-text-muted',
};
/** EACH ROW'S OWN ICON, BY THE ONE THING THAT ACTUALLY DIFFERS ACROSS THEM — the reason id, or
 *  the goal, or the bot-tool id. A single generic envelope for every one of the thirteen-plus rows
 *  (the previous shape) is exactly what read as "unfinished" beside the mockup's own per-row
 *  icons. Kept as a lookup, same hand-mirrored posture as `REASON_TEMPLATE_TYPE` above — a table
 *  this small drifting is a one-line fix. */
const CARD_ICON: Record<string, LucideIcon> = {
  visit_recorded: ClipboardCheck, rating_requested: Star, booking_confirmed: CalendarClock,
  visit_redeemed: Gift, service_due: Clock3, after_visit: Heart, no_response: RotateCcw,
  balance_changed: Wallet, points_expiring: Hourglass, reward_within_reach: Gift,
  gone_missing: Compass, loyal_customer: Award, personal_occasion: Cake, weekly_digest: FileBarChart,
  privacy_code: ShieldCheck,
  win_back: Compass, reward_loyal: Award, announce: Megaphone, occasion: Cake,
  service_offer: Tag, package_offer: Tag, safety: ShieldAlert,
};
function cardIcon(card: TemplateCard): LucideIcon {
  const key = card.reason?.id ?? card.goal ?? card.key.replace(/^bot:/, '');
  return CARD_ICON[key] ?? MessageSquare;
}

/**
 * ONE GOAL CARD, READ FROM `campaigns.goals` — just enough to build the five that have no
 * automatic reason of their own (win_back/occasion/reward_loyal are read from `reasons` instead,
 * via REASON_GOAL, and never duplicated here — see `templateCards` below).
 */
interface GoalRow {
  goal: string;
  title: string;
  line: string;
  template_status?: TemplateStatus;
  /** THE RAIL'S OWN "استُخدمت N مرة"/"N وصلهم" — campaigns' own side counter
   *  (core/goal_stats.py, 2026-09-12), never computed here. Used for the management screen's own
   *  "كم عميل وصلته حملاتك" KPI — a real sum, not an invented one. */
  uses?: number;
  reach?: number;
}

/**
 * THE TEMPLATE TYPE EACH GOAL SENDS — the same table campaigns/app/core/models.py's own
 * `GOAL_TEMPLATE` holds, mirrored here so «القوالب» can open the by-type preview
 * (`reminders.preview_by_type`) WITHOUT a reason id, for the five goals that have none. Kept in
 * sync by hand, the same way `GOAL_TITLE` above already is — a table this small drifting is a
 * one-line fix; a network round trip just to learn it is not worth the goals endpoint growing a
 * field for exactly one screen.
 */
const GOAL_TEMPLATE_TYPE: Record<string, string> = {
  announce: 'mkt_announcement',
  service_offer: 'mkt_offer',
  package_offer: 'mkt_offer',
};

/** THE THREE SECTIONS, IN THE ORDER AN OWNER SHOULD READ THEM — the `cls` values the reasons
 *  registry already uses. `offers` USED TO BE A FOURTH, SEPARATE ONE (2026-09-13, merged away): it
 *  held exactly the same regulatory class as `marketing` — the split was never about the class,
 *  only about whether the owner has to press «أطلق» each time (`service_offer`/`package_offer`,
 *  both `trigger: "manual"`) or the send is standing/scheduled on its own — and `announce` was
 *  ALSO manual yet already lived under `marketing`, so the split did not even track that
 *  consistently. The per-card badge already says «آلي»/«يدوي» (see `templateCards`'s own `tags`);
 *  a whole extra section duplicated a distinction the badge already carries. */
// «bot» LAST ON PURPOSE — every section before it is a message this shop's own settings shaped
// (scheduled or launched by hand); the bot's own live tool replies are a different kind of thing
// entirely (composed fresh per conversation, never stored or edited here), so they read as an
// appendix, not mixed in among the shop's own configured messages.
const SECTION_ORDER = ['service', 'personal', 'marketing', 'bot'] as const;

const SECTION_KEY: Record<string, string> = {
  service: 'messages.section.service',
  personal: 'messages.section.personal',
  marketing: 'messages.section.marketing',
  bot: 'messages.section.bot',
};
function sectionLabel(t: (key: string) => string, section: string): string {
  return t(SECTION_KEY[section] ?? section);
}

/** Which section a GOAL-ONLY card lands under (win_back/occasion/reward_loyal are reason cards,
 *  never built from this — see `templateCards`). `announce` sits with the marketing reasons: it
 *  is exactly as promotional as they are, just never automatic. */
const GOAL_SECTION: Record<string, string> = {
  announce: 'marketing',
  service_offer: 'offers',
  package_offer: 'offers',
};

/** A reason whose message needs an app this shop may not own — never hidden, LOCKED (Locked.tsx's
 *  own `AppGate`). Read from `reasons.py`'s `source` field where it is clean (`booking_confirmed`
 *  is `source="bookings"`); `rating_requested` carries no such source (it is fired by reminders
 *  itself, on behalf of the rating app) so its app is named here by hand. */
const REASON_APP: Record<string, string> = {
  booking_confirmed: 'bookings',
  rating_requested: 'rating',
};

/** EVERY REASON'S OWN `template_type` — `reasons.py`'s own REASONS tuple, mirrored by hand (same
 *  posture `GOAL_TEMPLATE_TYPE` above already holds: a table this small drifting is a one-line fix,
 *  not worth a network round trip). Needed here for exactly one thing: resolving whether a reason
 *  card's message is INTERACTIVE (see `INTERACTIVE_TEMPLATE_TYPES` below) — a reason card never
 *  carried its own `templateType` before this, only goal-only cards did. */
const REASON_TEMPLATE_TYPE: Record<string, string> = {
  visit_recorded: 'svc_visit_confirmation',
  rating_requested: 'svc_visit_confirmation_rating',
  booking_confirmed: 'svc_booking_confirmation',
  visit_redeemed: 'svc_visit_redeemed',
  service_due: 'svc_service_reminder',
  after_visit: 'svc_follow_up',
  no_response: 'svc_service_reminder',
  balance_changed: 'per_account_notice',
  points_expiring: 'per_points_expiring',
  reward_within_reach: 'mkt_loyalty_activation',
  gone_missing: 'mkt_winback',
  loyal_customer: 'mkt_loyalty_activation',
  personal_occasion: 'mkt_personal_occasion',
  weekly_digest: 'per_weekly_digest',
};

/** تفاعلي = يفتح شاشات حقيقية داخل واتساب (فلو)، لا مجرد نص يُقرأ. مأخوذة يدوياً من
 *  `operations/data/templates.seed.json`'s الفعلي (أي صف فيه `flow_button`) — نفس أسلوب
 *  `REASON_TEMPLATE_TYPE` أعلاه، جدول صغير يُحدَّث يدوياً بدل استدعاء شبكة لأجل حقيقة نادراً ما
 *  تتغيّر. القوالب المجدولة فقط — كاروسيل البوت وأدواته الحيّة أضيفت لاحقاً كبطاقات مستقلة
 *  (`BOT_TOOL_CARDS` أدناه)، ولا تعتمد على هذا الجدول أصلاً. */
const INTERACTIVE_TEMPLATE_TYPES = new Set([
  'mkt_offer', 'mkt_personal_occasion', 'mkt_winback', 'per_weekly_digest',
  'svc_visit_confirmation_rating',
]);

/**
 * أدوات المساعد الذكي — لا قالب من reminders يمثّلها: هي ردود حيّة يركّبها البوت أثناء
 * محادثة حقيقية، مو رسالة مجدولة ثابتة. وصفها هنا مأخوذ حرفياً من نفس الوصف الحقيقي اللي يُعطى
 * للذكاء الاصطناعي (`adapters/llm/assistant_service.py`'s الخاص بـ`_TOOL_SCHEMAS`)، مترجم لجملة
 * قصيرة — لا مخترعة. `check_availability` غائبة عمداً — أداة سحب بيانات داخلية لا ترسل شي بشكلها
 * الخاص (تُغذّي `propose_booking` فقط)، بالضبط الاستثناء اللي طلبه المالك: "كل اداة في ارسال مو
 * سحب بيانات".
 */
interface BotToolCard {
  id: string;
  label: string;
  when: string;
  interactive: boolean;
  // الحجز والتأجيل كلاهما له معاينة فلو حيّة فعلياً — `operations.whatsapp_flow_json`
  // (notification-service v0.19.30's own `build_flow_preview_json` dispatcher) يرسم شاشات
  // RescheduleEngine بنفس مولّد شاشات BookingEngine؛ الاختلاف الوحيد `routing_model`، والمحرّك
  // العام (`WaFlowScreens`) لا يحتاج تمييزاً خاصاً لأيّ منهما.
  preview: { kind: 'text'; text: string }
    | { kind: 'carousel'; intro: string; cards: WaCarouselCard[] }
    | { kind: 'flow'; flowName: string; intro: string };
}

/** Every bot-tool card, translated — built once per render from the active locale rather than a
 *  single hardcoded Arabic array (same move Shop.tsx's own `dayLetters`/`dayNames` make). */
function botToolCards(t: (key: string) => string): BotToolCard[] {
  return [
    {
      id: 'propose_booking', label: t('messages.bot.propose_booking.label'), interactive: true,
      when: t('messages.bot.propose_booking.when'),
      preview: { kind: 'flow', flowName: 'booking', intro: t('messages.bot.propose_booking.intro') },
    },
    {
      id: 'suggest_services_carousel', label: t('messages.bot.suggest_services_carousel.label'), interactive: true,
      when: t('messages.bot.suggest_services_carousel.when'),
      preview: {
        kind: 'carousel', intro: t('messages.bot.suggest_services_carousel.intro'),
        cards: [
          { id: 's1', kind: 'service', name: t('messages.bot.carousel.haircut'), priceMinor: 5000, buttonLabel: t('messages.bot.bookNowButton') },
          { id: 's2', kind: 'service', name: t('messages.bot.carousel.beardShave'), priceMinor: 3000, buttonLabel: t('messages.bot.bookNowButton') },
          { id: 's3', kind: 'package', name: t('messages.bot.carousel.careBundle'), priceMinor: 12000, buttonLabel: t('messages.bot.bookNowButton') },
        ],
      },
    },
    {
      id: 'get_customer_points_summary', label: t('messages.bot.get_customer_points_summary.label'), interactive: false,
      when: t('messages.bot.get_customer_points_summary.when'),
      preview: { kind: 'text', text: t('messages.bot.get_customer_points_summary.text') },
    },
    {
      id: 'suggest_redeemable_offer', label: t('messages.bot.suggest_redeemable_offer.label'), interactive: false,
      when: t('messages.bot.suggest_redeemable_offer.when'),
      preview: { kind: 'text', text: t('messages.bot.suggest_redeemable_offer.text') },
    },
    {
      id: 'suggest_related_service', label: t('messages.bot.suggest_related_service.label'), interactive: false,
      when: t('messages.bot.suggest_related_service.when'),
      preview: { kind: 'text', text: t('messages.bot.suggest_related_service.text') },
    },
    {
      id: 'list_my_bookings', label: t('messages.bot.list_my_bookings.label'), interactive: false,
      when: t('messages.bot.list_my_bookings.when'),
      preview: { kind: 'text', text: t('messages.bot.list_my_bookings.text') },
    },
    {
      id: 'propose_cancel_booking', label: t('messages.bot.propose_cancel_booking.label'), interactive: false,
      when: t('messages.bot.propose_cancel_booking.when'),
      preview: { kind: 'text', text: t('messages.bot.propose_cancel_booking.text') },
    },
    {
      id: 'propose_reschedule_booking', label: t('messages.bot.propose_reschedule_booking.label'), interactive: true,
      when: t('messages.bot.propose_reschedule_booking.when'),
      preview: { kind: 'flow', flowName: 'reschedule', intro: t('messages.bot.propose_reschedule_booking.intro') },
    },
    {
      id: 'list_packages', label: t('messages.bot.list_packages.label'), interactive: false,
      when: t('messages.bot.list_packages.when'),
      preview: { kind: 'text', text: t('messages.bot.list_packages.text') },
    },
    {
      id: 'list_due_services', label: t('messages.bot.list_due_services.label'), interactive: false,
      when: t('messages.bot.list_due_services.when'),
      preview: { kind: 'text', text: t('messages.bot.list_due_services.text') },
    },
    {
      id: 'list_lapsed_services', label: t('messages.bot.list_lapsed_services.label'), interactive: false,
      when: t('messages.bot.list_lapsed_services.when'),
      preview: { kind: 'text', text: t('messages.bot.list_lapsed_services.text') },
    },
  ];
}

/** One entry in «القوالب» — a reason, a goal, or (for the three that are both) one card carrying
 *  both capabilities, never shown twice. */
interface TemplateCard {
  key: string;
  label: string;
  when: string;
  cls: string;
  clsLabel: string;
  /** 'auto' when a reason fires this without anybody pressing anything; 'manual' when it is a
   *  goal the owner launches himself from «حملاتي»; 'bot' when it is a live AI-assistant tool
   *  reply, never a scheduled/reminders template at all — see `BOT_TOOL_CARDS`. A card carrying
   *  both 'auto' and 'manual' is the three shared ones — REASON_GOAL's own three; 'bot' never
   *  combines with either. */
  tags: ('auto' | 'manual' | 'bot')[];
  reason?: ReasonRow;
  /** Set whenever a goal is attached — either because THIS card came from `goals` directly (a
   *  goal with no reason), or because a reason card shares one via REASON_GOAL. Used for the
   *  cross-link to «حملاتي» and, when there is no `reason`, for the by-type preview. */
  goal?: string;
  templateType?: string;
  lockAppId?: string;
  /** يفتح شاشات فلو حقيقية داخل واتساب، لا نص يُقرأ فقط — see `INTERACTIVE_TEMPLATE_TYPES`
   *  (reminders' own cards) and `BOT_TOOL_CARDS` (each names its own). */
  interactive: boolean;
  /** ONLY on a bot-tool card — no `reason`/`templateType` to fetch a server preview against
   *  (nothing is stored; the bot composes it live), so `reading.botPreview` opens
   *  `WhatsAppTemplatePreview` directly with this local data instead of `MessagePreview`'s own
   *  server round trip. */
  botPreview?: BotToolCard['preview'];
}

/** THE GOAL → REASON MAP, THE OTHER DIRECTION FROM `REASON_GOAL` above — so a goal read from
 *  `campaigns.goals` that already has a reason card is skipped here rather than drawn twice. */
const GOAL_HAS_REASON = new Set(Object.values(REASON_GOAL).map((r) => r.goal));

/** Every template in the product, once — reasons first (their own order), then the goals with no
 *  reason of their own, grouped by section and never duplicated. Pure, so a test can hold the
 *  rule without rendering anything. */
export function templateCards(
  reasons: ReasonRow[], goals: GoalRow[], t: (key: string) => string = (k) => k,
): TemplateCard[] {
  const out: TemplateCard[] = [];
  for (const r of reasons) {
    const linked = REASON_GOAL[r.id];
    const templateType = REASON_TEMPLATE_TYPE[r.id];
    out.push({
      key: `reason:${r.id}`, label: r.label, when: r.when,
      cls: r.cls ?? '', clsLabel: r.cls_label ?? '',
      tags: linked ? ['auto', 'manual'] : ['auto'],
      reason: r, goal: linked?.goal, templateType,
      lockAppId: REASON_APP[r.id],
      interactive: Boolean(templateType && INTERACTIVE_TEMPLATE_TYPES.has(templateType)),
    });
  }
  for (const g of goals) {
    if (GOAL_HAS_REASON.has(g.goal)) continue; // already carried by its reason card, above
    const cls = GOAL_SECTION[g.goal] ?? 'marketing';
    const templateType = GOAL_TEMPLATE_TYPE[g.goal];
    out.push({
      key: `goal:${g.goal}`, label: g.title, when: g.line,
      cls, clsLabel: sectionLabel(t, cls),
      tags: ['manual'], goal: g.goal, templateType,
      interactive: Boolean(templateType && INTERACTIVE_TEMPLATE_TYPES.has(templateType)),
    });
  }
  for (const c of botToolCards(t)) {
    out.push({
      key: `bot:${c.id}`, label: c.label, when: c.when,
      cls: 'bot', clsLabel: sectionLabel(t, 'bot'),
      tags: ['bot'], interactive: c.interactive, botPreview: c.preview,
    });
  }
  return out;
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
const OCCASION_KEY: Record<string, string> = {
  reminder: 'messages.occasion.reminder',
  follow_up: 'messages.occasion.follow_up',
  review_request: 'messages.occasion.review_request',
  campaign: 'messages.occasion.campaign',
};
function occasionLabel(t: (key: string) => string, kind: string): string {
  const key = OCCASION_KEY[kind];
  return key ? t(key) : t('messages.occasion.fallback');
}

/** How far off it is, in the words he would use — "in 3 days", not a date he has to subtract. */
function dueIn(at: number, t: (key: string) => string): string {
  const days = Math.round((at - Date.now() / 1000) / 86_400);
  if (days < 0) return t('messages.due.overdue');
  if (days === 0) return t('messages.due.today');
  if (days === 1) return t('messages.due.tomorrow');
  return tf(t, 'messages.due.inDays', { n: days });
}

/** THE RAIL'S OWN URGENCY BUCKET for one queued message — 'soon' (within the hour), 'today', or
 *  'later'. Three buckets, not a continuous countdown: an owner scanning the rail wants "should I
 *  worry about this one right now", not a precise minute count for every row. */
type Urgency = 'soon' | 'today' | 'later';
function urgencyOf(dueAt: number): Urgency {
  const secondsLeft = dueAt - Date.now() / 1000;
  if (secondsLeft <= 3_600) return 'soon';
  if (secondsLeft <= 86_400) return 'today';
  return 'later';
}
const URGENCY_DOT: Record<Urgency, string> = { soon: 'bg-danger', today: 'bg-warning', later: 'bg-text-muted' };

/** A campaign's own recurring window, as a short chip — or `null` when it carries none (the
 *  (0, 24, []) defaults `Campaign.window_*` itself uses to mean "no window"). Mirrors
 *  campaigns' own `window_sentence()` (preview.py) at a glance rather than the full sentence,
 *  which only the preview screen has room for. */
function windowChip(c: Campaign): string | null {
  const start = c.window_start_hour ?? 0;
  const end = c.window_end_hour ?? 24;
  const days = c.window_weekdays ?? [];
  if (start === 0 && end === 24 && days.length === 0) return null;
  const hours = `${start}–${end}`;
  if (days.length === 0) return hours;
  return `${hours} · ${days.length} أيام`;
}

/** Whether job-service is holding this campaign for a future moment it has not fired even once
 *  — `fire_at` in the future AND `last_evaluated === 0` (campaigns' own core/tick.py rescue is
 *  keyed on the exact same field). A campaign already fired at least once is never "scheduled"
 *  again, however its `fire_at` reads. */
function isScheduled(c: Campaign): boolean {
  return Boolean(c.fire_at) && (c.fire_at ?? 0) > Date.now() / 1000 && !c.last_evaluated;
}

/** THE DETAIL PANEL'S OWN "الإرسال عبر الأيام" — every run this campaign has ever had, grouped by
 *  the calendar day it fired, so a shop can see at a glance whether sends cluster (a standing
 *  campaign firing daily) or spread thin (a one-time launch). Real numbers only: `runs` is the
 *  exact list `/runs` already returned, never re-fetched or estimated. */
function runsByDay(runs: Run[]): { label: string; value: number }[] {
  const byDay = new Map<string, number>();
  for (const r of runs) {
    if (!r.at) continue;
    const label = new Date(r.at * 1000).toLocaleDateString('ar', { day: 'numeric', month: 'short' });
    byDay.set(label, (byDay.get(label) ?? 0) + (r.sent ?? 0));
  }
  // OLDEST FIRST — `runs` itself arrives newest-first (the route's own order), and a trend reads
  // naturally left-to-right in the order it actually happened.
  return Array.from(byDay.entries()).reverse().map(([label, value]) => ({ label, value }));
}

/** 966xxxxxxxxx → 05xxxxxxxx. The form he reads on his own phone. */
function asLocal(phone: string): string {
  const d = digitsOnly(phone || '');
  return d.startsWith('966') ? `0${d.slice(3)}` : d;
}

/**
 * «هل كل شيء يعمل؟» — everything `reminders.today` answers, in one call (owner.py's own note on
 * the route: no screen had ever called it before this pass). This IS the summary the section was
 * missing: whether sending is blocked at all, how many messages are calmly waiting versus stuck
 * retrying, and how much of today's WhatsApp ceiling is left.
 */
interface Today {
  can_send: boolean;
  /** Empty when nothing is wrong — a field that always carries a sentence becomes furniture. */
  blocked: string;
  messages: { sent_today: number; waiting: number; retrying: number; retrying_reason: string };
  ceiling: {
    known: boolean; unlimited: boolean; limit?: number; reached_today?: number;
    remaining?: number; quality?: string;
  };
}

/** GREEN | YELLOW | RED | NA | UNKNOWN — Meta's own scale (services/reminders/core/ceiling.py).
 *  The last two are deliberately unmapped: a quality we could not read is not «متوسطة», it is
 *  nothing to say at all. */
const QUALITY_KEY: Record<string, string> = {
  GREEN: 'messages.quality.GREEN', YELLOW: 'messages.quality.YELLOW', RED: 'messages.quality.RED',
};
function qualityLabel(t: (key: string) => string, quality: string): string | undefined {
  const key = QUALITY_KEY[quality];
  return key ? t(key) : undefined;
}

/** One number, named. Three of these make the whole «هل كل شيء يعمل؟» answer scannable in the
 *  half-second an owner actually spends on it. */
function Stat({ label, value, warn }: { label: string; value: number; warn?: boolean }) {
  return (
    <div className="flex flex-1 flex-col items-center gap-0.5 px-2 text-center">
      <span className={[
        'text-lg font-semibold tabular-nums',
        warn && value > 0 ? 'text-warning' : 'text-text-primary',
      ].join(' ')}>
        {value}
      </span>
      <span className="text-xs text-text-secondary">{label}</span>
    </div>
  );
}

/**
 * THE CARD THAT DID NOT EXIST. «الحملات» is the screen an owner opens nervous — something went out
 * or did not — and it never said, in one glance, whether sending was even possible today. Sending
 * is blocked entirely (one sentence, in red, above everything else); or it is not, and three
 * numbers say what is happening right now; and the WhatsApp ceiling, when it is close, is the
 * quiet line under them rather than a fourth number competing for attention.
 */
function TodayCard({ today, session }: { today: Today; session: Session }) {
  const { t } = useOperatorI18n();
  // DEFENSIVE ALL THE WAY DOWN. `today` arrives from one network call, same as every other
  // reader in this file — `messages` or `ceiling` missing from a malformed or partial answer
  // must not crash the screen it decorates; it should just draw the parts that did arrive.
  const messages = today.messages ?? { sent_today: 0, waiting: 0, retrying: 0, retrying_reason: '' };
  const ceiling = today.ceiling ?? { known: false, unlimited: false };
  const quality = qualityLabel(t, ceiling.quality ?? '');
  return (
    <section className="flex flex-col gap-3 rounded-card border border-border-subtle bg-surface-1 p-4 shadow-sm">
      {today.blocked ? (
        <div className="flex items-start gap-2 rounded-lg bg-danger-soft p-3 text-sm text-danger-on-soft">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden />
          <p>{today.blocked}</p>
        </div>
      ) : (
        <div className="flex flex-col gap-1">
          <div className="flex items-stretch divide-x divide-border-subtle rtl:divide-x-reverse">
            <Stat label={t('messages.stat.sentToday')} value={messages.sent_today ?? 0} />
            <Stat label={t('messages.stat.waiting')} value={messages.waiting ?? 0} />
            <Stat label={t('messages.stat.retrying')} value={messages.retrying ?? 0} warn />
          </div>
          <div className="flex justify-center">
            <AssistantHint session={session} anchor="messages.todayStats" />
          </div>
        </div>
      )}
      {messages.retrying_reason ? (
        <p className="text-xs text-text-secondary">{messages.retrying_reason}</p>
      ) : null}
      {ceiling.known && !ceiling.unlimited ? (
        <p className="flex items-center gap-1.5 border-t border-border-subtle pt-3 text-xs text-text-secondary">
          <Gauge size={13} className="shrink-0" aria-hidden />
          <span className="tabular-nums">
            {tf(t, 'messages.ceiling.line', { remaining: ceiling.remaining ?? 0, limit: ceiling.limit ?? 0 })}
          </span>
          {quality ? tf(t, 'messages.ceiling.quality', { quality }) : ''}
          <AssistantHint session={session} anchor="messages.ceiling" />
        </p>
      ) : null}
    </section>
  );
}

/** THE TAG, IN HIS WORDS — the owner's own explicit ask: whether a card fires by itself, whether
 *  he presses it himself, or both, must be visible on the card, never buried in a modal. */
const TAG_KEY: Record<'auto' | 'manual' | 'bot', string> = {
  auto: 'messages.tag.auto',
  manual: 'messages.tag.manual',
  bot: 'messages.tag.bot',
};
function tagLabel(t: (key: string) => string, tag: 'auto' | 'manual' | 'bot'): string {
  return t(TAG_KEY[tag]);
}

/**
 * A BOT-TOOL CARD'S OWN PREVIEW — no `reminders.preview_reason`/`preview_by_type` round trip
 * (nothing is stored server-side to fetch), so this builds `WaTemplateData` locally from
 * `BOT_TOOL_CARDS`'s own sample content and hands it straight to the SAME phone-mockup engine
 * every other preview in the product uses (`WhatsAppTemplatePreview`), reused rather than a
 * fourth rendering path. `fetchFlowJson` is wired only for `kind: 'flow'` — the same
 * `operations.whatsapp_flow_json` route `MessagePreview.tsx`'s own `openFlowButton` already calls.
 */
function BotToolPreviewModal({ session, catalog, card, preview, onClose }: {
  session: Session; catalog: Catalog; card: TemplateCard; preview: BotToolCard['preview'];
  onClose: () => void;
}) {
  const { t } = useOperatorI18n();
  const data = preview.kind === 'carousel'
    ? { body: preview.intro, carousel: preview.cards }
    : preview.kind === 'flow'
      ? { body: preview.intro, flowButton: { flowName: preview.flowName, text: t('messages.botPreviewOpen') } }
      : { body: preview.text };
  return (
    <Modal open onClose={onClose} title={card.label} subtitle={card.when}>
      <div className="flex flex-col gap-3">
        <p className="text-xs text-text-secondary">
          {t('messages.botPreviewApprox')}
        </p>
        <WhatsAppTemplatePreview
          data={data}
          fetchFlowJson={preview.kind === 'flow' ? (flowName) => {
            const a = action(catalog, 'operations.whatsapp_flow_json');
            if (!a) return Promise.reject(new Error(t('messages.noFlowPermission')));
            return call<FlowJson>(session, a, { name: flowName });
          } : undefined}
        />
      </div>
    </Modal>
  );
}

/**
 * ONE CARD, WHATEVER IT IS BACKED BY. `card.reason` present means a switch, a «بنصّك أنت» badge
 * and the reasons-based preview; absent means a bare goal, opened through the by-type preview
 * instead. Matches the product's existing card idiom — rounded-card, shadow-sm, an icon circle —
 * rather than inventing new chrome (see LockedCard in Locked.tsx, the establishment this pass
 * borrows its visual language from).
 */
function TemplateCardItem({ card, session, busy, onOpen, onFlip, onCrossLink, locked }: {
  card: TemplateCard;
  session: Session;
  busy: string;
  onOpen: () => void;
  onFlip?: (on: boolean) => void;
  onCrossLink: () => void;
  /** THE APP THIS REASON BELONGS TO ISN'T BOUGHT YET — never hides the card any more (that was
   *  the bug: `AppGate` used to swap the WHOLE card for a generic upsell, so pressing it could
   *  never open the real preview — owner's own words: "حتى لو مقفلة العرض المفروض يكون متاح بحيث
   *  يشوفها ويجربها ويتحمس يشتريها"). `onOpen` stays live either way; only the switch — which
   *  would turn on a send he cannot pay for — is replaced. */
  locked?: boolean;
}) {
  const { t } = useOperatorI18n();
  const r = card.reason;
  // THE MOCKUP'S OWN CARD LANGUAGE — a coloured left stripe and a matching tinted icon circle,
  // by class/section. `bot` cards share `SECTION_TONE`'s own 'bot' entry same as every other row.
  const tone = SECTION_TONE[card.cls] ?? 'neutral';
  const Icon = cardIcon(card);
  return (
    <div style={{ borderInlineStart: `4px solid ${TONE_VAR[tone]}` }}
        className={['flex items-center gap-3 rounded-card border border-border-subtle',
                   'bg-surface-1 p-3 shadow-sm', (r && !r.on) || locked ? 'opacity-70' : ''].join(' ')}>
      {/* THE ICON CIRCLE — tinted by the same tone as the stripe, one real icon per row rather
          than a single generic envelope for all of them. */}
      <span className={['flex h-9 w-9 shrink-0 items-center justify-center rounded-full', TONE_ICON_BG[tone]].join(' ')}>
        <Icon size={16} aria-hidden />
      </span>

      <button type="button" onClick={onOpen}
              className="flex min-w-0 flex-1 flex-col gap-1 text-start">
        <span className="flex flex-wrap items-center gap-2">
          <span className="truncate font-medium">{card.label}</span>
          {card.clsLabel ? (
            <Badge tone={CLASS_TONE[card.cls] ?? 'neutral'}>{card.clsLabel}</Badge>
          ) : null}
          {/* THE TAG(S) — BOTH, ON ONE CARD, FOR THE THREE THAT ARE BOTH. */}
          {card.tags.length === 2 ? (
            <Badge tone="neutral">{t('messages.tag.both')}</Badge>
          ) : (
            <Badge tone="neutral">{tagLabel(t, card.tags[0])}</Badge>
          )}
          {/* INTERACTIVE — opens real Flow screens inside WhatsApp, not just text. No inverse
             badge for the non-interactive case (same logic as "your own text" beside it — the
             exception is marked, not the rule). */}
          {card.interactive ? <Badge tone="info">{t('messages.tag.interactive')}</Badge> : null}
          {r?.template_status && r.template_status !== 'unknown' ? (
            <Badge tone={TEMPLATE_STATUS_META[r.template_status].tone}>
              {TEMPLATE_STATUS_META[r.template_status].label}
            </Badge>
          ) : null}
          {r?.template ? (
            <>
              <Badge tone="neutral">{t('messages.customTextBadge')}</Badge>
              <AssistantHint session={session} anchor="messages.customTextBadge" />
            </>
          ) : null}
        </span>
        <span className="truncate text-xs text-text-secondary">{card.when}</span>
      </button>

      {/* THE CROSS-LINK — a SIBLING of the card's own button, never nested inside it. Shown for
          every card carrying a goal: the three shared reason cards AND the goal-only cards, both
          link to «حملاتي» the same way. */}
      {card.goal ? (
        <button type="button" onClick={onCrossLink}
               className="shrink-0 whitespace-nowrap text-xs text-text-secondary underline underline-offset-2 hover:text-text-primary">
          {tf(t, 'messages.crossLink', { goal: goalTitle(t, card.goal) ?? t('messages.goal.fallback') })}
        </button>
      ) : null}

      {/* THE SWITCH — only for a reason. A bare goal has nothing to switch: it fires only when he
          presses «أطلق حملة» in «حملاتي», never by itself. */}
      {r ? (
        <span className="flex w-24 shrink-0 items-center justify-end gap-2">
          {locked ? (
            <span className="flex items-center gap-1 text-xs text-text-secondary">
              <Lock size={14} aria-hidden />
              {t('messages.afterPurchase')}
            </span>
          ) : (
            <>
              <span className="text-xs text-text-secondary">
                {r.can_switch ? (r.on ? t('messages.reasonOn') : t('messages.reasonOff')) : ''}
              </span>
              {r.can_switch && onFlip ? (
                <span className="[&_label>span]:sr-only">
                  <Toggle
                    label={card.label}
                    checked={r.on}
                    disabled={busy === r.id}
                    onChange={onFlip}
                  />
                </span>
              ) : (
                <span className="flex items-center gap-1 text-xs text-text-secondary">
                  <Lock size={14} aria-hidden />
                  {t('messages.customerRight')}
                </span>
              )}
            </>
          )}
        </span>
      ) : null}
    </div>
  );
}

export function MessagesScreen(
  { session, catalog, owned, branch }:
  { session: Session; catalog: Catalog; owned?: Loading<Owned>; branch?: string },
) {
  const { t } = useOperatorI18n();
  // ARRIVING FROM ANOTHER SCREEN WITH THE DECISION ALREADY MADE — "My Shop"'s "deserve your
  // follow-up" card links here with `?tab=campaigns&launch=win_back` rather than a plain link to
  // "My Messages", because a plain link still makes him find the tab, press "launch campaign",
  // and pick the one goal he already came here for. Read once, on mount — a tab change
  // afterwards is his own choice to keep.
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const launchGoal = params.get('launch') || undefined;
  const [tab, setTab] = useState<'reasons' | 'auto' | 'campaigns' | 'log'>(
    params.get('tab') === 'campaigns' ? 'campaigns' : 'reasons');

  /**
   * WHAT SENDS IN HIS NAME — the question this whole section is named after, and the one it could
   * not answer. «الحملات» listed a queue and a log: what is about to go and what already went. It
   * never said WHAT THE SYSTEM SENDS AT ALL, so the only way to stop a kind of message was to
   * cancel its rows one at a time, for ever, as they appeared.
   */
  const [reasons, setReasons] = useState<Loading<ReasonRow[]>>(undefined);
  const [busy, setBusy] = useState('');
  /** The card he opened to read its wording. `null` is closed — it is not a screen of its own. */
  const [reading, setReading] = useState<TemplateCard | null | undefined>(undefined);
  /** THE FIVE GOALS WITH NO REASON OF THEIR OWN — read once, with the screen, same as `reasons`:
   *  «القوالب» is now the one place both live, and a goal fetched only after a tab switch would
   *  make the first paint of that tab incomplete. `null` on a denied/failed read simply means
   *  those five cards do not appear — the three shared ones still do, via `reasons` alone. */
  const [goals, setGoals] = useState<GoalRow[] | null>(null);
  const [switchError, setSwitchError] = useState('');

  /** «هل كل شيء يعمل؟» — read once, with the screen, same as the reasons table below it: it is
   *  the first thing an owner wants an answer to, so it is not gated behind any tab. */
  const [today, setToday] = useState<Loading<Today>>(undefined);

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
  /** Which branch's messages he is reading. '' is all of them; '_none' is the ones with none.
   *  DEFAULTS TO THE RAIL'S OWN «الفرع المعروض» — an owner who already narrowed the whole console
   *  to one branch must not land here reading every branch's log by default, the exact
   *  «comparing two different shops» BranchSwitch.tsx's own docstring warns about. He can still
   *  widen it back to «كل الفروع» right here, or pick «بلا فرع محدَّد» — a finer-grained choice
   *  than the rail's own control offers, which is why this stays a real, separate field rather
   *  than being replaced by `branch` outright. */
  const [logBranch, setLogBranch] = useState(branch || '');
  // FOLLOWS THE RAIL, LIVE — switching the console's own branch while already on this screen
  // re-narrows the log the same way arriving here fresh now does, rather than leaving a now-stale
  // selection in place until he happens to notice and change it back himself.
  useEffect(() => setLogBranch(branch || ''), [branch]);
  const [branches, setBranches] = useState<{ id: string; name: string }[] | null>([]);
  const [schedule, setSchedule] = useState<Schedule | null | undefined>(undefined);
  const [campaigns, setCampaigns] = useState<Campaign[] | null | undefined>(undefined);
  // A SECOND FACT NEEDS A SECOND FIELD. `null` already means «the campaigns app is not enabled»
  // on this screen, so putting «we could not read» into it would collapse two
  // different answers into one — the same mistake this pass exists to undo, committed in a new
  // place. He is told to buy something he already owns, or told he owns nothing during an outage.
  const [campaignsFailed, setCampaignsFailed] = useState(false);
  /** The composer, open only when he asks for it — this tab is a list first. Except arriving with
   *  `?launch=`, where asking for it again would be the second ask this turn already answered. */
  // THE APPROVED MOCKUP'S OWN TWO SCREENS — «لوحة الحملات» is never gated behind a button/empty
  // state before he can even see the create screen; it is one of two persistent modes, "شاشة
  // الإنشاء" the default (an owner opening this tab is usually here TO launch something) and
  // "شاشة الإدارة" the real KPI/table/detail view. Arriving with `?launch=` still opens on
  // create — it already answers "why" — but that is what create already defaults to regardless.
  const [campaignScreen, setCampaignScreen] = useState<'create' | 'manage'>('create');
  /** One campaign's sends, open under its row. `null` is closed — it is not a screen of its own.
   *  `runsFor` is WHICH campaign it belongs to — without it the panel had one place to render
   *  (under the whole list) rather than under the row that asked for it, so a shop with more than
   *  one campaign saw «ماذا حدث» open somewhere its own row never pointed to. */
  const [runs, setRuns] = useState<Run[] | null | undefined>(undefined);
  const [runsFor, setRunsFor] = useState('');
  /** THE SAME ROUTE'S OWN TOTALS — matched/sent/suppressed/redeemed across every run, not
   *  reconstructed here by summing `runs` (which the route itself may have paginated). Was
   *  fetched and thrown away before this pass; the detail panel's own KPI tiles need it. */
  const [runsTotals, setRunsTotals] = useState<Record<string, number> | null>(null);
  /** Which row's «ماذا حدث»/«أوقفها» is mid-request — so a second tap while the first is still in
   *  flight does nothing rather than firing the same call twice. */
  const [campaignBusy, setCampaignBusy] = useState('');
  /** Same idea, for a scheduled message's own «أوقفها» in the «بانتظار الخروج» tab. */
  const [cancelBusy, setCancelBusy] = useState('');
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

  // THE FIVE GOALS WITH NO AUTOMATIC COUNTERPART — read once, beside `reasons`, so «القوالب»
  // opens complete. A shop whose role/plan cannot see `campaigns.goals` simply keeps the reasons
  // it already has: the three shared cards still carry «أنت ترسلها» via REASON_GOAL.
  useEffect(() => {
    const a = action(catalog, 'campaigns.goals');
    if (!a) return;
    call<{ goals: GoalRow[] }>(session, a)
      .then((x) => setGoals(x.goals ?? []))
      .catch(() => setGoals(null));
  }, [session, catalog]);

  /** EVERY TEMPLATE, ONCE — the whole point of the rename. Built only once both reads have
   *  something to say; a goal read that has not arrived yet must not make the three shared cards
   *  flicker from "both" to "automatic only" and back. */
  const cards = useMemo(
    () => templateCards(isReady(reasons) ? reasons : [], goals ?? [], t),
    [reasons, goals, t],
  );

  /** THE SMART FILTER — stackable chips (both together means "automated AND interactive", not
   *  either alone), on top of the section split (SECTION_ORDER) rather than instead of it — the
   *  section stays the primary organization, the filter narrows within it. */
  type CardFilter = 'auto' | 'interactive' | 'bot';
  const [activeFilters, setActiveFilters] = useState<Set<CardFilter>>(new Set());
  const toggleFilter = (f: CardFilter) => setActiveFilters((prev) => {
    const next = new Set(prev);
    if (next.has(f)) next.delete(f); else next.add(f);
    return next;
  });
  const filteredCards = useMemo(() => cards.filter((c) =>
    (!activeFilters.has('auto') || c.tags.includes('auto'))
    && (!activeFilters.has('bot') || c.tags.includes('bot'))
    && (!activeFilters.has('interactive') || c.interactive)), [cards, activeFilters]);

  /** THE RAIL'S OWN CLASS FILTER — narrows which section is shown, on top of `filteredCards`'
   *  own tag filter above (both apply together: a class AND a tag). '' means every class. */
  const [classFilter, setClassFilter] = useState<string>('');
  /** THE QUEUE TAB'S OWN RAIL — same idea, one dimension (urgency) instead of class. */
  const [urgencyFilter, setUrgencyFilter] = useState<'' | Urgency>('');
  /** THE LOG TAB'S OWN RAIL — replaces the old `only` Segmented with the same rail shape every
   *  other tab now uses; `only` itself (still read by the network effect above) is unchanged. */
  const classFilteredCards = useMemo(
    () => (classFilter ? filteredCards.filter((c) => c.cls === classFilter) : filteredCards),
    [filteredCards, classFilter],
  );

  // THE SUMMARY, ONCE, WITH THE SCREEN. Cheap by its own design (owner.py's docstring: one call
  // rather than four, exactly so a status screen is never briefly wrong) — and silent on failure
  // or denial rather than a second error box: it is a bonus answer layered over a screen that
  // already works without it, not a thing this screen is named after.
  useEffect(() => {
    const a = action(catalog, 'reminders.today');
    if (!a) { setToday(DENIED); return; }
    call<Today>(session, a).then(setToday).catch(() => setToday(null));
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
      setSwitchError(e instanceof Error ? e.message : t('messages.switchSaveError'));
    } finally {
      setBusy('');
    }
  };

  // THE LOG IS FETCHED WHEN ITS TAB OPENS, not with the screen. It is the heaviest read here and
  // the least often wanted — an owner opens «الحملات» to see what is coming, and pays for the log
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
      // NOT AN ERROR AND NOT AN EMPTY LIST: the campaigns app is not enabled. `null` is the
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
    // A SECOND TAP CLOSES IT, rather than re-fetching the same answer — the whole point of
    // pinning the panel to a row is that pressing that row's own button again is «hide it».
    if (runsFor === id) { setRuns(null); setRunsTotals(null); setRunsFor(''); return; }
    const a = action(catalog, 'campaigns.runs');
    if (!a) return;
    setRunsFor(id);
    setCampaignBusy(`runs:${id}`);
    // AN EMPTY LIST RATHER THAN A CLOSED PANEL ON FAILURE: he asked a question, and silence is
    // the one answer that sends him to support.
    const out = await call<{ runs: Run[]; totals?: Record<string, number> }>(session, a, { campaign_id: id })
      .then((r) => ({ runs: r.runs ?? [], totals: r.totals ?? null }))
      .catch(() => ({ runs: [] as Run[], totals: null }));
    setRuns(out.runs);
    setRunsTotals(out.totals);
    setCampaignBusy('');
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
      <PageHeader icon={MessageSquare} title={t('messages.title')} />

      {isLoading(today) ? (
        <Skeleton height={76} radius="card" />
      ) : isReady(today) ? (
        <TodayCard today={today} session={session} />
      ) : null}

      <Segmented
        // FULL WIDTH, SPLIT EVENLY, NEVER WRAPPED. The kit's Segmented is
        // `inline-flex flex-wrap`, which on a phone stacks two long Arabic labels into a
        // ragged block half the screen wide. It takes a className and merges with
        // tailwind-merge, so this is a fix at the call site rather than a fork of the kit.
        className="flex w-full [&>button]:flex-1 [&>button]:whitespace-nowrap"
        ariaLabel={t('messages.tabsAriaLabel')}
        value={tab}
        onChange={setTab}
        options={[
          {
            value: 'reasons', label: t('messages.tab.reasons'), icon: FileText,
            // A REAL COUNT, ONLY ONCE THE READ HAS ACTUALLY ANSWERED — never 0 while it is still
            // loading or denied, which would read as "nothing sends" about a shop whose engine we
            // simply have not asked yet.
            badge: isReady(reasons) ? String(reasons.length) : undefined,
          },
          {
            value: 'auto', label: t('messages.tab.auto'), icon: Clock,
            badge: isReady(schedule) && Array.isArray(schedule.schedule)
              ? String(schedule.schedule.length) : undefined,
          },
          { value: 'campaigns', label: t('messages.tab.campaigns'), icon: Zap },
          { value: 'log', label: t('messages.tab.log'), icon: Mail },
        ]}
      />

      {tab === 'reasons' ? (
        <section className="flex flex-col gap-4">
          {/* ── EVERY TEMPLATE IN THE PRODUCT, ONCE ─────────────────────────────────────────
              THE RENAME'S WHOLE POINT. «متى نرسل» only ever listed the thirteen automatic
              reasons; «حملاتي» separately explained eight goals, and only three of them ever got
              the rich preview an owner could actually read and edit. «القوالب» is now the one
              place both live — every card carrying its own tags, its own class, and, for the
              three that are both, both capabilities on one card rather than two. */}
          {switchError ? <p className="px-1 text-sm text-danger">{switchError}</p> : null}

          {/* THE SMART FILTER — two stackable chips, not a dropdown: the choice here is a simple
             binary (has it/doesn't) for now, not a multi-value taxonomy that needs a heavier form. */}
          {isReady(reasons) && reasons.length > 0 ? (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-text-secondary">{t('messages.filter.label')}</span>
              <button type="button" onClick={() => toggleFilter('auto')}
                     aria-pressed={activeFilters.has('auto')}
                     className={['rounded-pill border px-3 py-1 text-xs font-medium transition',
                       activeFilters.has('auto')
                         ? 'border-accent bg-accent-soft text-accent-on-soft'
                         : 'border-border-subtle bg-surface-1 text-text-secondary hover:bg-surface-2'].join(' ')}>
                {t('messages.filter.autoOnly')}
              </button>
              <button type="button" onClick={() => toggleFilter('interactive')}
                     aria-pressed={activeFilters.has('interactive')}
                     className={['rounded-pill border px-3 py-1 text-xs font-medium transition',
                       activeFilters.has('interactive')
                         ? 'border-accent bg-accent-soft text-accent-on-soft'
                         : 'border-border-subtle bg-surface-1 text-text-secondary hover:bg-surface-2'].join(' ')}>
                {t('messages.filter.interactiveOnly')}
              </button>
              <button type="button" onClick={() => toggleFilter('bot')}
                     aria-pressed={activeFilters.has('bot')}
                     className={['rounded-pill border px-3 py-1 text-xs font-medium transition',
                       activeFilters.has('bot')
                         ? 'border-accent bg-accent-soft text-accent-on-soft'
                         : 'border-border-subtle bg-surface-1 text-text-secondary hover:bg-surface-2'].join(' ')}>
                {t('messages.filter.botOnly')}
              </button>
              {activeFilters.size > 0 ? (
                <button type="button" onClick={() => setActiveFilters(new Set())}
                       className="text-xs text-text-secondary underline">
                  {t('messages.filter.clear')}
                </button>
              ) : null}
            </div>
          ) : null}

          {isLoading(reasons) ? (
            <Skeleton height={200} />
          ) : isDenied(reasons) ? (
            <EmptyState
              title={t('messages.reasons.deniedTitle')}
              description={t('messages.reasons.deniedDesc')}
            />
          ) : hasFailed(reasons) ? (
            <EmptyState
              title={t('messages.reasons.failedTitle')}
              description={t('messages.reasons.failedDesc')}
            />
          ) : reasons.length === 0 ? (
            <EmptyState
              title={t('messages.reasons.emptyTitle')}
              description={t('messages.reasons.emptyDesc')}
            />
          ) : activeFilters.size > 0 && filteredCards.length === 0 ? (
            <EmptyState
              title={t('messages.reasons.filterEmptyTitle')}
              description={t('messages.reasons.filterEmptyDesc')}
            />
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-[220px_1fr]">
              {/* THE RAIL — every real class this shop's own cards actually carry, never a
                  hardcoded list that could name a class with nothing in it (or miss one). */}
              <FilterRail
                ariaLabel={t('messages.classRailAriaLabel')}
                active={classFilter}
                onChange={setClassFilter}
                items={[
                  { id: '', label: t('messages.category.all'), count: filteredCards.length },
                  ...SECTION_ORDER
                    .map((section) => ({
                      id: section,
                      label: sectionLabel(t, section),
                      count: filteredCards.filter((c) => c.cls === section).length,
                      dotClassName: TONE_DOT[SECTION_TONE[section] ?? 'neutral'],
                    }))
                    .filter((it) => it.count > 0),
                ]}
              />

              <div className="flex flex-col gap-4">
                {(classFilter ? [classFilter] : SECTION_ORDER).map((section) => {
                  const inSection = classFilteredCards.filter((c) => c.cls === section);
                  if (inSection.length === 0) return null;
                  return (
                    <div key={section} className="flex flex-col gap-2">
                      {!classFilter ? (
                        <h3 className="px-1 text-sm font-medium text-text-secondary">
                          {sectionLabel(t, section)}
                        </h3>
                      ) : null}
                      <ul className="flex flex-col gap-2">
                        {inSection.map((c) => {
                          // NEVER SWAP THE WHOLE CARD FOR A LOCK ANY MORE — `AppGate` used to
                          // replace it outright, which meant pressing a locked reason could never
                          // open the real preview at all (owner's own words: "حتى لو مقفلة العرض
                          // المفروض يكون متاح بحيث يشوفها ويجربها ويتحمس يشتريها"). The card itself
                          // (and its `onOpen`) always renders; only the switch is replaced, and the
                          // app's own real feature list + buy link render ALONGSIDE it, never
                          // instead of it.
                          const lockedRow = c.lockAppId
                            ? owns(owned, APP_ROWS.find((a) => a.id === c.lockAppId)?.key ?? null) === false
                            : false;
                          return (
                            <li key={c.key} className="flex flex-col gap-2">
                              <TemplateCardItem card={c} session={session} busy={busy}
                                                onOpen={() => setReading(c)}
                                                onFlip={c.reason ? (on) => flip(c.reason!, on) : undefined}
                                                onCrossLink={() => c.goal
                                                  && navigate(`?tab=campaigns&launch=${c.goal}`)}
                                                locked={lockedRow} />
                              {lockedRow ? (
                                <LockedCard appId={c.lockAppId!} session={session} catalog={catalog} owned={owned} />
                              ) : null}
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  );
                })}
                {classFilteredCards.length === 0 ? (
                  <EmptyState
                    title={t('messages.reasons.filterEmptyTitle')}
                    description={t('messages.reasons.filterEmptyDesc')}
                  />
                ) : null}
                <p className="px-1 text-xs text-text-secondary">
                  {t('messages.reasons.footnote')}
                </p>
              </div>
            </div>
          )}
          {reading ? (
            reading.botPreview ? (
              <BotToolPreviewModal session={session} catalog={catalog} card={reading}
                                   preview={reading.botPreview} onClose={() => setReading(null)} />
            ) : reading.reason ? (
              <MessagePreview
                session={session}
                catalog={catalog}
                reasonId={reading.reason.id}
                label={reading.label}
                when={reading.when}
                canRetext={reading.reason.can_retext}
                onClose={() => setReading(null)}
                onChosen={() => {
                  const a = action(catalog, 'reminders.reasons');
                  if (a) {
                    call<{ reasons: ReasonRow[] }>(session, a)
                      .then((x) => setReasons(x.reasons ?? []))
                      .catch(() => {});
                  }
                }}
              />
            ) : (
              <MessagePreview
                session={session}
                catalog={catalog}
                templateType={reading.templateType}
                label={reading.label}
                when={reading.when}
                canRetext={false}
                onClose={() => setReading(null)}
                onChosen={() => {}}
              />
            )
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
            title={t('messages.schedule.failedTitle')}
            description={t('messages.schedule.failedDesc')}
          />
        ) : (schedule.schedule ?? []).length === 0 ? (
          <EmptyState
            title={t('messages.schedule.emptyTitle')}
            description={t('messages.schedule.emptyDesc')}
          />
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-[220px_1fr]">
            <FilterRail
              ariaLabel={t('messages.urgencyRailAriaLabel')}
              active={urgencyFilter}
              onChange={(id) => setUrgencyFilter(id as '' | Urgency)}
              items={(['soon', 'today', 'later'] as Urgency[])
                .map((u) => ({
                  id: u,
                  label: t(`messages.urgency.${u}`),
                  dotClassName: URGENCY_DOT[u],
                  count: schedule.schedule.filter((r) => urgencyOf(r.due_at ?? 0) === u).length,
                }))
                .reduce<FilterRailItem[]>((acc, it) => [...acc, it], [
                  { id: '', label: t('messages.category.all'), count: schedule.schedule.length },
                ])}
            />
            <div className="flex flex-col gap-3">
              <p className="px-1 text-sm text-text-secondary">
                {tf(t, 'messages.schedule.summary', { n: schedule.schedule.length })}
              </p>
              <ul className="flex flex-col gap-2">
                {[...schedule.schedule]
                  .filter((r) => !urgencyFilter || urgencyOf(r.due_at ?? 0) === urgencyFilter)
                  .sort((a, b) => (a.due_at ?? 0) - (b.due_at ?? 0))
                  .slice(0, 100)
                  .map((r, i) => {
                    const person = r.subject_ref ? who[r.subject_ref] : undefined;
                    const urgency = urgencyOf(r.due_at ?? 0);
                    // A REAL LOGICAL-DIRECTION BORDER, RTL-SAFE — the same `border-inline-start`
                    // property `.legal-callout` (index.css) already uses for this exact "a
                    // coloured stripe naming urgency" shape; done inline here since it is per-row
                    // data (which colour), not a shared static rule a stylesheet class can hold.
                    const urgencyColor = urgency === 'soon' ? 'var(--danger)'
                      : urgency === 'today' ? 'var(--warning)' : 'var(--border-subtle)';
                    return (
                      <li key={r.id || i}
                          style={{ borderInlineStart: `4px solid ${urgencyColor}` }}
                          className="flex items-center justify-between gap-3 rounded-card bg-surface-1 p-3 shadow-sm">
                        <span className="flex min-w-0 flex-col">
                          {/* THE NAME IF HE WROTE ONE, THE NUMBER IF HE DID NOT — never a
                              pseudonym. Names are optional at the counter (§4.3), so the phone is
                              the fallback that always identifies somebody. */}
                          <span className="truncate font-medium">
                            {person?.name || (person?.phone ? asLocal(person.phone) : t('messages.customerFallback'))}
                          </span>
                          <span className="truncate text-sm text-text-secondary">
                            {occasionLabel(t, r.kind ?? '')}
                            {r.due_at ? ` · ${dueIn(r.due_at, t)}` : ''}
                          </span>
                        </span>
                        {/* CANCELS THE MESSAGE, NOT THE RULE — the route's own words, repeated here
                            so he is not surprised: the next visit schedules a new one. */}
                        {action(catalog, 'reminders.cancel') && r.id ? (
                          <Button
                            variant="ghost"
                            disabled={cancelBusy === r.id}
                            onClick={async () => {
                              const a2 = action(catalog, 'reminders.cancel');
                              if (!a2 || !r.id) return;
                              setCancelBusy(r.id);
                              await call(session, a2, { id: r.id }).catch(() => null);
                              setCancelBusy('');
                              loadSchedule();
                            }}
                          >
                            {cancelBusy === r.id ? t('messages.cancel.busy') : t('messages.cancel.action')}
                          </Button>
                        ) : null}
                      </li>
                    );
                  })}
              </ul>
              <p className="px-1 text-xs text-text-secondary">
                {t('messages.schedule.footnote')}
              </p>
            </div>
          </div>
        )}
      </section>
      ) : tab === 'log' ? (
        <section className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            {/* THE SENTENCE MOVED ABOVE THE FILTER, not below it as every other hint on this page
                reads — this tab sits directly under the page's own top-level strip (the "أقسام
                الرسائل" Segmented above), and a second Segmented (this log filter) with nothing
                between them is exactly "شريطين تحت بعض", the shape the owner ruled out. The
                sentence is real content, not filler inserted just to separate two strips: it is
                the same "why is a message missing" explanation this tab always carried, just
                placed where it now also does the job of keeping the two strips apart. */}
            <p className="flex flex-wrap items-center gap-1 px-1 text-sm text-text-secondary">
              {t('messages.log.intro')}
              <AssistantHint session={session} anchor="messages.deliveryStatus" />
            </p>
            <Segmented
              className="flex w-full [&>button]:flex-1 [&>button]:whitespace-nowrap"
              ariaLabel={t('messages.log.filterAriaLabel')}
              value={only}
              onChange={(v) => setOnly(v as '' | 'sent' | 'suppressed')}
              options={[
                { value: '', label: t('messages.log.filter.all') },
                { value: 'sent', label: t('messages.log.filter.sent') },
                // THE ONE HE CAME FOR. Named by what happened to the message rather than by our
                // word for it: "suppressed" is a term from the engine, and he is asking why his
                // customer heard nothing.
                { value: 'suppressed', label: t('messages.log.filter.suppressed') },
              ]}
            />
            {/* SHOWN ONLY TO A SHOP WITH MORE THAN ONE PLACE. "Filter by your only branch" is a
                control that does nothing, and one more thing to read past. */}
            {(branches ?? []).length > 1 ? (
              <label className="flex items-center gap-2 px-1 text-sm">
                <span className="text-text-secondary">{t('messages.log.branchLabel')}</span>
                <select
                  className="min-h-11 flex-1 rounded-xl bg-surface-2 px-3 text-sm"
                  value={logBranch}
                  aria-label={t('messages.log.branchAriaLabel')}
                  onChange={(e) => setLogBranch(e.target.value)}
                >
                  <option value="">{t('messages.log.allBranches')}</option>
                  {(branches ?? []).map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
                  {/* A GROUP, NOT A LEFTOVER: campaign sends have no visit behind them, and rows
                      from before we carried the field will never have one. */}
                  <option value="_none">{t('messages.log.noBranch')}</option>
                </select>
              </label>
            ) : null}
          </div>

          {isLoading(log) ? (
            <Skeleton height={120} />
          ) : isDenied(log) ? (
            <EmptyState
              title={t('messages.log.deniedTitle')}
              description={t('messages.log.deniedDesc')}
            />
          ) : logFailed || hasFailed(log) ? (
            // OURS, NOT HIS. "Nothing in the log yet" is a statement about his shop, and we may
            // only make it once we have actually read the log — otherwise an owner whose messages
            // did go out is told they did not, on the one screen whose whole job is to say what
            // left in his name.
            <EmptyState
              title={t('messages.log.failedTitle')}
              description={t('messages.log.failedDesc')}
            />
          ) : !isReady(log) || log.length === 0 ? (
            // NOT AN APOLOGY AND NOT A FAULT. A shop whose engine has not had to refuse anything
            // yet is a shop working correctly, and the sentence says which.
            <EmptyState
              title={t('messages.log.emptyTitle')}
              description={t('messages.log.emptyDesc')}
            />
          ) : (
            <ul className="flex flex-col gap-2">
              {log.map((r) => {
                // THE SAME TONE THE BADGE BELOW ALREADY COMPUTES — read once, used twice (the
                // badge's own fill and this row's own colour-coded stripe), never a second,
                // independently-guessed colour rule that could disagree with the badge beside it.
                const outcomeTone = r.outcome !== 'sent' ? 'warning' : r.read_at ? 'success' : 'neutral';
                const outcomeColor = outcomeTone === 'warning' ? 'var(--warning)'
                  : outcomeTone === 'success' ? 'var(--success)' : 'var(--border-subtle)';
                return (
                <li key={r.id} style={{ borderInlineStart: `4px solid ${outcomeColor}` }}
                    className="rounded-card bg-surface-1 p-3 shadow-sm">
                  <div className="flex items-center justify-between gap-3">
                    {/* WHO IT WAS ABOUT, FIRST. A log line that says only «لم تخرج» and a reason
                        leaves the owner unable to act: he cannot call the customer, cannot check
                        the number, cannot tell whether it matters. */}
                    <span className="flex min-w-0 flex-col">
                      <span className="truncate font-medium">
                        {(() => {
                          const person = r.subject_ref ? who[r.subject_ref] : undefined;
                          return person?.name
                            || (person?.phone ? asLocal(person.phone) : t('messages.customerFallback'));
                        })()}
                      </span>
                      <span className="text-xs text-text-secondary tabular-nums">
                        {r.at ? `${when(r.at, t)} · ${occasionLabel(t, r.cls ?? '')}` : ''}
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
                    <Badge tone={outcomeTone}>
                      {r.outcome !== 'sent' ? t('messages.log.outcome.suppressed')
                        : r.read_at ? t('messages.log.outcome.read') : r.delivered_at ? t('messages.log.outcome.delivered') : t('messages.log.outcome.sent')}
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
                );
              })}
            </ul>
          )}
        </section>
      ) : owns(owned ?? null, 'feature.campaigns') === false ? (
        // LOCKED ON THE ENTITLEMENT, NOT ON THE CAPABILITY — and that swap is the whole defect.
        // The lock used to be drawn from `campaigns.list` being absent from the catalogue, which
        // is a question about the person's ROLE: an owner holds `campaigns.manage` regardless of
        // which app is enabled, so the lock never appeared for the one person who would have paid
        // to remove it. He pressed «أطلق الحملة» with no campaigns app enabled and it went out.
        //
        // And the card now carries a way to buy it. Naming a feature he cannot reach, with no
        // button, is an advertisement rather than a product.
        <LockedCard appId="campaigns" session={session} catalog={catalog} owned={owned} />
      ) : campaignsFailed ? (
        <EmptyState
          title={t('messages.campaigns.failedTitle')}
          description={t('messages.campaigns.failedDesc')}
        />
      ) : isLoading(campaigns) ? (
        // A DIFFERENT ABSENCE, KEPT SEPARATE: the shop HAS campaigns and this person may not use
        // them. Nothing to buy, so nothing to sell him — the sentence is about permission.
        <section className="rounded-card bg-surface-1 p-4 text-center shadow-sm">
          <Lock size={20} className="mx-auto mb-3 text-text-secondary" aria-hidden />
          <EmptyState
            title={t('messages.campaigns.roleLockedTitle')}
            description={t('messages.campaigns.roleLockedDesc')}
          />
        </section>
      ) : (
        <section className="flex flex-col gap-4">
          {/* THE APPROVED MOCKUP'S OWN TWO SCREENS — never a button gating an empty state before
              he can even reach the create screen; «شاشة الإنشاء» is the default because an owner
              opening this tab has usually come to launch something, and «شاشة الإدارة» is one
              press away, always, never conditional on whether anything has been launched yet. */}
          <Segmented
            className="self-start"
            ariaLabel={t('messages.campaigns.screenAriaLabel')}
            value={campaignScreen}
            onChange={setCampaignScreen}
            options={[
              { value: 'create', label: t('messages.campaigns.screen.create') },
              { value: 'manage', label: t('messages.campaigns.screen.manage') },
            ]}
          />
          {campaignScreen === 'create' ? (
            <Launch session={session} catalog={catalog} initialGoalId={launchGoal} owned={owned}
                    onDone={() => { setCampaignScreen('manage'); loadCampaigns(); }} />
          ) : (
            <>
              {hasFailed(campaigns) ? (
                // "Haven't launched a campaign yet" IS A FACT ABOUT HIS SHOP. Said after a failed
                // read it tells an owner mid-campaign that nothing of his is running.
                <EmptyState
                  title={t('messages.campaigns.failedTitle')}
                  description={t('messages.campaigns.failedDesc')}
                />
              ) : (campaigns ?? []).length === 0 ? (
                <EmptyState
                  title={t('messages.campaigns.emptyTitle')}
                  description={t('messages.campaigns.emptyDesc')}
                />
              ) : (
                <>
                  {/* THE THREE NUMBERS AN OWNER ACTUALLY WANTS AT A GLANCE — every one real,
                      never invented: active count and total from the list this tab already
                      reads, reach summed from the SAME side counter (core/goal_stats.py) the
                      create screen's own rail already shows per goal — no new network call,
                      `goals` is already fetched for «القوالب»'s own cross-link cards. A
                      redemption-rate tile was deliberately left OUT: computing it honestly needs
                      every campaign's own `/runs` totals, one call each, which does not belong on
                      a screen that opens on every visit to this tab. */}
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                    <KpiCard
                      icon={<Megaphone size={18} aria-hidden />}
                      tone="success"
                      label={t('messages.campaigns.kpi.active')}
                      value={campaigns.filter((c) => c.state === 'active').length}
                    />
                    <KpiCard
                      icon={<BarChart3 size={18} aria-hidden />}
                      tone="accent"
                      label={t('messages.campaigns.kpi.total')}
                      value={campaigns.length}
                    />
                    <KpiCard
                      icon={<Users size={18} aria-hidden />}
                      tone="info"
                      label={t('messages.campaigns.kpi.reach')}
                      value={(goals ?? []).reduce((sum, g) => sum + (g.reach ?? 0), 0)}
                    />
                  </div>

                  <Table<Campaign>
                    columns={[
                      {
                        key: 'name', header: t('messages.campaigns.col.name'),
                        render: (c) => (
                          <span className="flex flex-col">
                            <span className="font-medium">
                              {goalTitle(t, c.goal ?? '') || c.goal || t('messages.campaigns.fallbackName')}
                            </span>
                            {isScheduled(c) ? (
                              <span className="flex items-center gap-1 text-xs text-accent-on-soft">
                                <CalendarClock size={11} aria-hidden />
                                {tf(t, 'messages.campaigns.scheduledIn', { when: dueIn(c.fire_at ?? 0, t) })}
                              </span>
                            ) : null}
                          </span>
                        ),
                      },
                      {
                        key: 'state', header: t('messages.campaigns.col.state'), width: '18%',
                        render: (c) => {
                          const st = isScheduled(c) ? 'scheduled' : (c.state || '');
                          return st ? <Badge tone={STATE_TONE[st] ?? 'neutral'}>{stateLabel(t, st) ?? st}</Badge> : null;
                        },
                      },
                      {
                        key: 'window', header: t('messages.campaigns.col.window'), width: '22%',
                        render: (c) => {
                          const w = windowChip(c);
                          return w ? (
                            <span className="inline-flex items-center gap-1 whitespace-nowrap rounded-pill bg-accent-soft px-2 py-0.5 text-xs text-accent-on-soft">
                              <CalendarClock size={11} aria-hidden />{w}
                            </span>
                          ) : <span className="text-xs text-text-muted">{t('messages.campaigns.noWindow')}</span>;
                        },
                      },
                      {
                        key: 'actions', header: '', width: '90px', hideOnCard: true,
                        render: (c) => (
                          // STOPPING A STANDING RULE, not deleting its history. Only while it
                          // runs — a pause button on a finished campaign is a control that does
                          // nothing. `stopPropagation` so pressing it never also opens/closes
                          // the row's own detail panel underneath it.
                          c.state === 'active' && action(catalog, 'campaigns.pause') ? (
                            <Button
                              variant="ghost" size="sm"
                              disabled={campaignBusy === `pause:${c.id}`}
                              onClick={async (e) => {
                                e.stopPropagation();
                                const a2 = action(catalog, 'campaigns.pause');
                                if (!a2) return;
                                setCampaignBusy(`pause:${c.id}`);
                                await call(session, a2, { campaign_id: c.id }).catch(() => null);
                                setCampaignBusy('');
                                loadCampaigns();
                              }}
                            >
                              {campaignBusy === `pause:${c.id}` ? t('messages.cancel.busy') : (
                                <span className="flex items-center gap-1"><Pause size={13} aria-hidden />{t('messages.cancel.action')}</span>
                              )}
                            </Button>
                          ) : null
                        ),
                      },
                    ]}
                    rows={campaigns}
                    getRowId={(c) => c.id}
                    onRowClick={action(catalog, 'campaigns.runs') ? (c) => void openRuns(c.id) : undefined}
                  />

                  {/* THE DETAIL PANEL — opened under the whole table (never under one row, since
                      the table itself may re-sort/re-render) but pinned to the campaign it
                      answers for by name, so a shop with several campaigns never has to guess
                      which one this is describing. */}
                  {runsFor && runs ? (
                    <div className="flex flex-col gap-3 rounded-card border border-border-subtle bg-surface-1 p-4 shadow-sm">
                      <div className="flex items-center justify-between gap-2">
                        <h3 className="font-medium">
                          {tf(t, 'messages.campaigns.detailTitle', {
                            name: goalTitle(t, campaigns.find((c) => c.id === runsFor)?.goal ?? '')
                              || t('messages.campaigns.fallbackName'),
                          })}
                        </h3>
                        <button type="button" aria-label={t('messages.campaigns.closeDetail')}
                               onClick={() => { setRuns(null); setRunsTotals(null); setRunsFor(''); }}
                               className="text-text-secondary hover:text-text-primary">
                          <X size={16} aria-hidden />
                        </button>
                      </div>

                      {runsTotals ? (
                        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                          {(['matched', 'sent', 'suppressed', 'redeemed'] as const)
                            .filter((k) => typeof runsTotals[k] === 'number')
                            .map((k) => (
                              <div key={k} className="rounded-lg bg-surface-2 p-2.5 text-center">
                                <div className="text-lg font-semibold tabular-nums">{runsTotals[k]}</div>
                                <div className="text-xs text-text-secondary">{t(`messages.campaigns.totals.${k}`)}</div>
                              </div>
                            ))}
                        </div>
                      ) : null}

                      {/* THE TREND — real per-day sums from the same `runs` list below, never a
                          separate estimate. Only worth drawing once there is more than one day
                          to compare. */}
                      {runsByDay(runs).length > 1 ? (
                        <div className="flex flex-col gap-1.5">
                          <span className="text-xs font-medium text-text-secondary">
                            {t('messages.campaigns.trendLabel')}
                          </span>
                          <BarCompare items={runsByDay(runs)} />
                        </div>
                      ) : null}

                      {/* WHAT ACTUALLY WENT OUT, PER SEND, WITH ITS REASON. */}
                      {runs.length === 0 ? (
                        <p className="text-sm text-text-secondary">{t('messages.runs.empty')}</p>
                      ) : (
                        <ul className="flex flex-col gap-2">
                          {runs.map((r, i) => (
                            <li key={i} className="flex items-center justify-between gap-2 border-t border-border-subtle pt-2 first:border-0 first:pt-0">
                              <span className="flex flex-col">
                                <span className="text-sm tabular-nums">
                                  {tf(t, 'messages.runs.summary', { sent: r.sent ?? 0, suppressed: r.suppressed ?? 0 })}
                                </span>
                                {r.reason ? (
                                  <span className="text-xs text-text-secondary">{r.reason}</span>
                                ) : null}
                              </span>
                              <span className="text-xs text-text-secondary">{when(r.at ?? 0, t)}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ) : null}
                </>
              )}
            </>
          )}
        </section>
      )}
    </div>
  );
}
