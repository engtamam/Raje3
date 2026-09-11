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
 * AND «حملاتي» IS SHOWN LOCKED WHEN THE CAMPAIGNS APP IS NOT ENABLED, never removed. It used to vanish —
 * `campaigns === null` rendered nothing at all — and a section that disappears reads as a fault,
 * while a capability nobody can see is one nobody can buy.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { MessageSquare } from 'lucide-react';
import { Badge } from '../rj-ui/Badge';
import { EmptyState } from '../rj-ui/EmptyState';
import { PageHeader } from '../rj-ui/PageHeader';
import { Segmented } from '../rj-ui/Segmented';
import { DENIED, hasFailed, isDenied, isLoading, isReady, type Loading } from '../loading';
import { Skeleton } from '../rj-ui/Skeleton';
import { TEMPLATE_STATUS_META, type TemplateStatus } from './templateStatus';
import { Toggle } from '../rj-ui/Toggle';
import { AlertTriangle, Gauge, Lock } from 'lucide-react';
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
  // The two goals goals.py added after this map was first written — a campaign of either kind
  // fell back to `c.goal` (the raw English key) in the list below until this was caught live
  // against campaigns.goals: an owner would have read "seasonal_care" instead of its own title.
  seasonal_care: 'نصيحة موسمية',
  // KEPT DELIBERATELY — `safety` was removed from `CARDS`/`GOAL_TEMPLATE` (goals.py) whole, so
  // no NEW campaign can ever carry this goal again, but a shop that already launched one before
  // the removal still has that row in its own history here. Without this entry that OLD row
  // would fall back to the raw key ("safety") instead of a real title — a real record made to
  // look broken by a feature removal it had nothing to do with.
  safety: 'نبّه عن خطر',
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
 *  automatic counterpart at all yet (`announce`, `service_offer`/`package_offer`, `awareness`,
 *  `seasonal_care`) — absent here on purpose, not an oversight. */
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
  awareness: 'neutral',
  warning: 'warning',
  marketing: 'warning',
};

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
  awareness: 'awr_care_tip',
  seasonal_care: 'awr_seasonal_care',
  service_offer: 'mkt_offer',
  package_offer: 'mkt_offer',
};

/** THE FIVE SECTIONS, IN THE ORDER AN OWNER SHOULD READ THEM — the three `cls` values the reasons
 *  registry already uses, then the two that exist only for campaign goals with no automatic
 *  counterpart at all. */
// «bot» LAST ON PURPOSE — every section before it is a message this shop's own settings shaped
// (scheduled or launched by hand); the bot's own live tool replies are a different kind of thing
// entirely (composed fresh per conversation, never stored or edited here), so they read as an
// appendix, not mixed in among the shop's own configured messages.
const SECTION_ORDER = ['service', 'personal', 'marketing', 'tips', 'offers', 'bot'] as const;
const SECTION_LABEL: Record<string, string> = {
  service: 'خدمية',
  personal: 'شخصية',
  marketing: 'تسويقية',
  tips: 'وعي ونصائح',
  offers: 'عروض',
  bot: 'أدوات المساعد الذكي',
};

/** Which section a GOAL-ONLY card lands under (win_back/occasion/reward_loyal are reason cards,
 *  never built from this — see `templateCards`). `announce` sits with the marketing reasons: it
 *  is exactly as promotional as they are, just never automatic. */
const GOAL_SECTION: Record<string, string> = {
  announce: 'marketing',
  awareness: 'tips',
  seasonal_care: 'tips',
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
  privacy_code: 'per_dsar_code',
};

/** تفاعلي = يفتح شاشات حقيقية داخل واتساب (فلو)، لا مجرد نص يُقرأ. مأخوذة يدوياً من
 *  `operations/data/templates.seed.json`'s الفعلي (أي صف فيه `flow_button`) — نفس أسلوب
 *  `REASON_TEMPLATE_TYPE` أعلاه، جدول صغير يُحدَّث يدوياً بدل استدعاء شبكة لأجل حقيقة نادراً ما
 *  تتغيّر. مرحلة ١ فقط: القوالب المجدولة الموجودة اليوم — كاروسيل البوت وأدواته الحيّة (المرحلة ٣)
 *  ليست هنا بعد، لأنها أصلاً ليست بطاقات بهذي الشاشة اليوم. */
const INTERACTIVE_TEMPLATE_TYPES = new Set([
  'mkt_offer', 'mkt_personal_occasion', 'mkt_winback', 'per_weekly_digest',
  'svc_visit_confirmation_rating',
]);

/**
 * أدوات المساعد الذكي (phase 3) — لا قالب من reminders يمثّلها: هي ردود حيّة يركّبها البوت أثناء
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
  preview: { kind: 'text'; text: string }
    | { kind: 'carousel'; intro: string; cards: WaCarouselCard[] }
    // الحجز فقط له معاينة فلو حيّة فعلياً اليوم — `operations.whatsapp_flow_json` (شوف
    // `MessagePreview.tsx`'s الخاص بـ`openFlowButton`) يرفض أي محرّك غير BookingEngine
    // (`platform.py::whatsapp_flow_json`), والتأجيل (reschedule) محرّك مختلف — معاينته الحيّة
    // ليست متاحة عبر هذا الطريق اليوم، فتُعرض كنص وصفي بدل معاينة مكسورة.
    | { kind: 'flow'; flowName: string; intro: string };
}

const BOT_TOOL_CARDS: BotToolCard[] = [
  {
    id: 'propose_booking', label: 'اقتراح حجز موعد', interactive: true,
    when: 'يقترح البوت وقتاً محدداً لخدمة أو باقة — اقتراح لا تأكيد، ويفتح شاشات الحجز الحقيقية',
    preview: { kind: 'flow', flowName: 'booking', intro: 'شوف، عندنا وقت فاضي — تحب أحجزه لك؟' },
  },
  {
    id: 'suggest_services_carousel', label: 'كاروسيل الخدمات', interactive: true,
    when: 'يعرض بطاقات صور حقيقية لبعض خدمات/باقات المحل — فقط لما العميل يستكشف بلا طلب محدد',
    preview: {
      kind: 'carousel', intro: 'شوف بعض خدماتنا:',
      cards: [
        { id: 's1', kind: 'service', name: 'قص شعر', priceMinor: 5000, buttonLabel: 'احجز الآن' },
        { id: 's2', kind: 'service', name: 'حلاقة ذقن', priceMinor: 3000, buttonLabel: 'احجز الآن' },
        { id: 's3', kind: 'package', name: 'باقة العناية', priceMinor: 12000, buttonLabel: 'احجز الآن' },
      ],
    },
  },
  {
    id: 'get_customer_points_summary', label: 'ملخص نقاط العميل', interactive: false,
    when: 'يعرض للعميل نمط رصيده من النقاط — بلا أي بيانات شخصية خام',
    preview: { kind: 'text', text: 'عندك 320 نقطة — تقدر تستبدلها بخصم أو هدية من عروضنا.' },
  },
  {
    id: 'suggest_redeemable_offer', label: 'اقتراح استبدال نقاط', interactive: false,
    when: 'يسمّي هدية يقدر العميل يستبدلها برصيده الحالي فقط — لا يستبدل شي بنفسه',
    preview: { kind: 'text', text: 'عندك نقاط تكفي لهدية مجانية! تبي أضيفها لحجزك القادم؟' },
  },
  {
    id: 'suggest_related_service', label: 'اقتراح خدمة مكمّلة', interactive: false,
    when: 'يذكّر بخدمة تُحجز غالباً مع الخدمة اللي يناقشها العميل الآن',
    preview: { kind: 'text', text: 'غالباً اللي يحجزون قص الشعر يحبون معه تهذيب اللحية — تحب تضيفها؟' },
  },
  {
    id: 'list_my_bookings', label: 'عرض حجوزاتي', interactive: false,
    when: 'يسرد حجوزات العميل الحالية والقادمة، وحجوزاته القديمة إذا سأل عنها تحديداً',
    preview: { kind: 'text', text: 'حجوزاتك القادمة:\nقص شعر — الخميس 4:00 م\nتهذيب لحية — بعد أسبوعين' },
  },
  {
    id: 'propose_cancel_booking', label: 'اقتراح إلغاء حجز', interactive: false,
    when: 'يقترح إلغاء حجز قائم للعميل — اقتراح لا إلغاء فعلي',
    preview: { kind: 'text', text: 'تأكيد: تبي تلغي حجزك يوم الخميس الساعة 4:00 م؟' },
  },
  {
    id: 'propose_reschedule_booking', label: 'اقتراح تأجيل حجز', interactive: true,
    when: 'يقترح نقل حجز قائم لوقت جديد فاضٍ فعلياً — يفتح شاشات تفاعلية (معاينتها الحيّة غير متاحة هنا بعد)',
    preview: { kind: 'text', text: 'تحب أأجّل حجزك ليوم السبت الساعة 5:00 م بدل الخميس؟' },
  },
  {
    id: 'list_packages', label: 'عرض الباقات', interactive: false,
    when: 'يسرد باقات المحل الحقيقية المتاحة للحجز قريباً، بأسعارها الحقيقية',
    preview: { kind: 'text', text: 'باقاتنا الحالية:\nباقة العناية الكاملة — 150 ريال\nباقة العريس — 300 ريال' },
  },
  {
    id: 'list_due_services', label: 'خدمات حان وقتها', interactive: false,
    when: 'يقترح خدمة اعتاد العميل عليها بدورته الخاصة — اقتراح طبيعي بلا ذكر أنه "متأخر"',
    preview: { kind: 'text', text: 'وقتها حان! قص الشعر يناسبك هالأسبوع — تحب تحجز؟' },
  },
  {
    id: 'list_lapsed_services', label: 'خدمات توقّف عنها', interactive: false,
    when: 'يقترح خدمة توقّف العميل عن حجزها بوضوح — دعوة طبيعية بلا ذكر أنه "توقف"',
    preview: { kind: 'text', text: 'اشتقناك! تحب نحجز لك موعد قص شعر قريب؟' },
  },
];

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
export function templateCards(reasons: ReasonRow[], goals: GoalRow[]): TemplateCard[] {
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
      cls, clsLabel: SECTION_LABEL[cls] ?? cls,
      tags: ['manual'], goal: g.goal, templateType,
      interactive: Boolean(templateType && INTERACTIVE_TEMPLATE_TYPES.has(templateType)),
    });
  }
  for (const t of BOT_TOOL_CARDS) {
    out.push({
      key: `bot:${t.id}`, label: t.label, when: t.when,
      cls: 'bot', clsLabel: SECTION_LABEL.bot,
      tags: ['bot'], interactive: t.interactive, botPreview: t.preview,
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
const QUALITY_LABEL: Record<string, string> = { GREEN: 'ممتازة', YELLOW: 'متوسطة', RED: 'ضعيفة' };

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
 * THE CARD THAT DID NOT EXIST. «رسائلي» is the screen an owner opens nervous — something went out
 * or did not — and it never said, in one glance, whether sending was even possible today. Sending
 * is blocked entirely (one sentence, in red, above everything else); or it is not, and three
 * numbers say what is happening right now; and the WhatsApp ceiling, when it is close, is the
 * quiet line under them rather than a fourth number competing for attention.
 */
function TodayCard({ today, session }: { today: Today; session: Session }) {
  // DEFENSIVE ALL THE WAY DOWN. `today` arrives from one network call, same as every other
  // reader in this file — `messages` or `ceiling` missing from a malformed or partial answer
  // must not crash the screen it decorates; it should just draw the parts that did arrive.
  const messages = today.messages ?? { sent_today: 0, waiting: 0, retrying: 0, retrying_reason: '' };
  const ceiling = today.ceiling ?? { known: false, unlimited: false };
  const quality = QUALITY_LABEL[ceiling.quality ?? ''];
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
            <Stat label="خرجت اليوم" value={messages.sent_today ?? 0} />
            <Stat label="بانتظار الخروج" value={messages.waiting ?? 0} />
            <Stat label="تعيد المحاولة" value={messages.retrying ?? 0} warn />
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
            {`سقف واتساب اليوم: ${ceiling.remaining ?? 0} متبقٍّ من ${ceiling.limit ?? 0}`}
          </span>
          {quality ? ` · جودة الحساب: ${quality}` : ''}
          <AssistantHint session={session} anchor="messages.ceiling" />
        </p>
      ) : null}
    </section>
  );
}

/** THE TAG, IN HIS WORDS — the owner's own explicit ask: whether a card fires by itself, whether
 *  he presses it himself, or both, must be visible on the card, never buried in a modal. */
const TAG_LABEL: Record<'auto' | 'manual' | 'bot', string> = {
  auto: 'تلقائي',
  manual: 'أنت ترسلها',
  bot: 'رسائل البوت',
};

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
  const data = preview.kind === 'carousel'
    ? { body: preview.intro, carousel: preview.cards }
    : preview.kind === 'flow'
      ? { body: preview.intro, flowButton: { flowName: preview.flowName, text: 'فتح' } }
      : { body: preview.text };
  return (
    <Modal open onClose={onClose} title={card.label} subtitle={card.when}>
      <div className="flex flex-col gap-3">
        <p className="text-xs text-text-secondary">
          مثال تقريبي — الذكاء الاصطناعي يركّب الرد فعلياً وقت المحادثة، فقد يختلف نصّه عن هذا
          المثال بالضبط.
        </p>
        <WhatsAppTemplatePreview
          data={data}
          fetchFlowJson={preview.kind === 'flow' ? (flowName) => {
            const a = action(catalog, 'operations.whatsapp_flow_json');
            if (!a) return Promise.reject(new Error('لا صلاحية لقراءة شاشات الفلو'));
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
  const r = card.reason;
  return (
    <div className={['flex items-center gap-3 rounded-card border border-border-subtle',
                     'bg-surface-1 p-3 shadow-sm', (r && !r.on) || locked ? 'opacity-70' : ''].join(' ')}>
      {/* THE ICON CIRCLE — the product's own idiom, not a new one. */}
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface-2">
        <MessageSquare size={16} className="text-text-secondary" aria-hidden />
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
            <Badge tone="neutral">تلقائي + يمكن إطلاقه يدوياً</Badge>
          ) : (
            <Badge tone="neutral">{TAG_LABEL[card.tags[0]]}</Badge>
          )}
          {/* تفاعلي — يفتح شاشات فلو حقيقية داخل واتساب، لا مجرد نص. لا شارة عكسية لغير التفاعلي
             (نفس منطق "بنصّك أنت" جمبها — الاستثناء يُعلَّم، لا القاعدة). */}
          {card.interactive ? <Badge tone="info">تفاعلي</Badge> : null}
          {r?.template_status && r.template_status !== 'unknown' ? (
            <Badge tone={TEMPLATE_STATUS_META[r.template_status].tone}>
              {TEMPLATE_STATUS_META[r.template_status].label}
            </Badge>
          ) : null}
          {r?.template ? (
            <>
              <Badge tone="neutral">بنصّك أنت</Badge>
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
          {`أطلقها من «${GOAL_TITLE[card.goal] ?? 'حملاتي'}»`}
        </button>
      ) : null}

      {/* THE SWITCH — only for a reason. A bare goal has nothing to switch: it fires only when he
          presses «أطلق حملة» in «حملاتي», never by itself. */}
      {r ? (
        <span className="flex w-24 shrink-0 items-center justify-end gap-2">
          {locked ? (
            <span className="flex items-center gap-1 text-xs text-text-secondary">
              <Lock size={14} aria-hidden />
              بعد الشراء
            </span>
          ) : (
            <>
              <span className="text-xs text-text-secondary">
                {r.can_switch ? (r.on ? 'مفعّلة' : 'موقوفة') : ''}
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
                  حقٌّ لعميلك
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
  // ARRIVING FROM ANOTHER SCREEN WITH THE DECISION ALREADY MADE — محلّي's «يستحقون متابعتك» card
  // links here with `?tab=campaigns&launch=win_back` rather than a plain link to «رسائلي», because
  // a plain link still makes him find the tab, press «أطلق حملة», and pick the one goal he already
  // came here for. Read once, on mount — a tab change afterwards is his own choice to keep.
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const launchGoal = params.get('launch') || undefined;
  const [tab, setTab] = useState<'reasons' | 'auto' | 'campaigns' | 'log'>(
    params.get('tab') === 'campaigns' ? 'campaigns' : 'reasons');

  /**
   * WHAT SENDS IN HIS NAME — the question this whole section is named after, and the one it could
   * not answer. «رسائلي» listed a queue and a log: what is about to go and what already went. It
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
  const [launching, setLaunching] = useState(Boolean(launchGoal));
  /** One campaign's sends, open under its row. `null` is closed — it is not a screen of its own.
   *  `runsFor` is WHICH campaign it belongs to — without it the panel had one place to render
   *  (under the whole list) rather than under the row that asked for it, so a shop with more than
   *  one campaign saw «ماذا حدث» open somewhere its own row never pointed to. */
  const [runs, setRuns] = useState<Run[] | null | undefined>(undefined);
  const [runsFor, setRunsFor] = useState('');
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
    () => templateCards(isReady(reasons) ? reasons : [], goals ?? []),
    [reasons, goals],
  );

  /** الفلتر الذكي — رقائق قابلة للتراكم (كلاهما معاً يعني "تلقائية وتفاعلية"، لا أحدهما فقط)،
   *  فوق التقسيم إلى أقسام (SECTION_ORDER) لا بدلاً عنه — القسم يبقى التنظيم الأساسي، الفلتر يضيّق
   *  داخله. */
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
    if (runsFor === id) { setRuns(null); setRunsFor(''); return; }
    const a = action(catalog, 'campaigns.runs');
    if (!a) return;
    setRunsFor(id);
    setCampaignBusy(`runs:${id}`);
    // AN EMPTY LIST RATHER THAN A CLOSED PANEL ON FAILURE: he asked a question, and silence is
    // the one answer that sends him to support.
    setRuns(await call<{ runs: Run[] }>(session, a, { campaign_id: id })
      .then((r) => r.runs ?? []).catch(() => []));
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
      <PageHeader icon={MessageSquare} title="رسائلي" />

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
        ariaLabel="أقسام الرسائل"
        value={tab}
        onChange={setTab}
        options={[
          { value: 'reasons', label: 'القوالب' },
          { value: 'auto', label: 'بانتظار الخروج' },
          { value: 'campaigns', label: 'حملاتي' },
          { value: 'log', label: 'السجل' },
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

          {/* الفلتر الذكي — رقاقتان تتراكمان، لا قائمة منسدلة: الاختيار هنا ثنائي بسيط (فيه/مو
             فيه) لبعدين، مو تصنيفاً متعدد القيم يحتاج نموذجاً أثقل. */}
          {isReady(reasons) && reasons.length > 0 ? (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-text-secondary">فلترة:</span>
              <button type="button" onClick={() => toggleFilter('auto')}
                     aria-pressed={activeFilters.has('auto')}
                     className={['rounded-pill border px-3 py-1 text-xs font-medium transition',
                       activeFilters.has('auto')
                         ? 'border-accent bg-accent-soft text-accent-on-soft'
                         : 'border-border-subtle bg-surface-1 text-text-secondary hover:bg-surface-2'].join(' ')}>
                مؤتمتة فقط
              </button>
              <button type="button" onClick={() => toggleFilter('interactive')}
                     aria-pressed={activeFilters.has('interactive')}
                     className={['rounded-pill border px-3 py-1 text-xs font-medium transition',
                       activeFilters.has('interactive')
                         ? 'border-accent bg-accent-soft text-accent-on-soft'
                         : 'border-border-subtle bg-surface-1 text-text-secondary hover:bg-surface-2'].join(' ')}>
                تفاعلية فقط
              </button>
              <button type="button" onClick={() => toggleFilter('bot')}
                     aria-pressed={activeFilters.has('bot')}
                     className={['rounded-pill border px-3 py-1 text-xs font-medium transition',
                       activeFilters.has('bot')
                         ? 'border-accent bg-accent-soft text-accent-on-soft'
                         : 'border-border-subtle bg-surface-1 text-text-secondary hover:bg-surface-2'].join(' ')}>
                رسائل البوت فقط
              </button>
              {activeFilters.size > 0 ? (
                <button type="button" onClick={() => setActiveFilters(new Set())}
                       className="text-xs text-text-secondary underline">
                  مسح الفلتر
                </button>
              ) : null}
            </div>
          ) : null}

          {isLoading(reasons) ? (
            <Skeleton height={200} />
          ) : isDenied(reasons) ? (
            <EmptyState
              title="لا يشمل دورك دواعي الإرسال"
              description="راجع صاحب المحل إن كنت تحتاج هذا القسم."
            />
          ) : hasFailed(reasons) ? (
            <EmptyState
              title="تعذّر قراءة رسائلك"
              description="حسابك سليم، والخلل عندنا. حاول بعد قليل."
            />
          ) : reasons.length === 0 ? (
            <EmptyState
              title="لا دواعي إرسال بعد"
              description="تظهر هنا حالما يبدأ محلك في تسجيل الزيارات."
            />
          ) : activeFilters.size > 0 && filteredCards.length === 0 ? (
            <EmptyState
              title="ما فيه قوالب تطابق الفلتر"
              description="جرّب رقاقة ثانية، أو امسح الفلتر لعرض الكل."
            />
          ) : (
            <>
              {SECTION_ORDER.map((section) => {
                const inSection = filteredCards.filter((c) => c.cls === section);
                if (inSection.length === 0) return null;
                return (
                  <div key={section} className="flex flex-col gap-2">
                    <h3 className="px-1 text-sm font-medium text-text-secondary">
                      {SECTION_LABEL[section]}
                    </h3>
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
              <p className="px-1 text-xs text-text-secondary">
                الإيقاف يوقف هذا النوع كلّه — وما هو في الطابور الآن يسقط معه.
                التسويقية تنطلق وحدها؛ ما تُطلقه أنت بنفسك ففي «حملاتي».
              </p>
            </>
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
                          {cancelBusy === r.id ? 'تُوقَف…' : 'أوقفها'}
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
            {/* THE SENTENCE MOVED ABOVE THE FILTER, not below it as every other hint on this page
                reads — this tab sits directly under the page's own top-level strip (the "أقسام
                الرسائل" Segmented above), and a second Segmented (this log filter) with nothing
                between them is exactly "شريطين تحت بعض", the shape the owner ruled out. The
                sentence is real content, not filler inserted just to separate two strips: it is
                the same "why is a message missing" explanation this tab always carried, just
                placed where it now also does the job of keeping the two strips apart. */}
            <p className="flex flex-wrap items-center gap-1 px-1 text-sm text-text-secondary">
              كل رسالة لم تخرج، ومعها سببها — لا شيء يُمنع بصمت.
              <AssistantHint session={session} anchor="messages.deliveryStatus" />
            </p>
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
        // is a question about the person's ROLE: an owner holds `campaigns.manage` regardless of
        // which app is enabled, so the lock never appeared for the one person who would have paid
        // to remove it. He pressed «أطلق الحملة» with no campaigns app enabled and it went out.
        //
        // And the card now carries a way to buy it. Naming a feature he cannot reach, with no
        // button, is an advertisement rather than a product.
        <LockedCard appId="campaigns" session={session} catalog={catalog} owned={owned} />
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
            <Launch session={session} catalog={catalog} initialGoalId={launchGoal}
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
            // ONE ROW SHAPE, EVERYWHERE ON THIS SCREEN. This used to hash the name, the sent
            // count, a badge and two buttons into one horizontal line with nothing to wrap on a
            // narrow phone — «بانتظار الخروج» already solved this with a stacked card, and a
            // campaign is exactly as much information as a queued message.
            <ul className="flex flex-col gap-2">
              {campaigns.map((c) => (
                <li key={c.id} className="flex flex-col gap-2 rounded-card bg-surface-1 p-3 shadow-sm">
                  <div className="flex items-center justify-between gap-3">
                    <span className="flex min-w-0 flex-col">
                      <span className="truncate font-medium">
                        {GOAL_TITLE[c.goal ?? ''] || c.goal || 'حملة'}
                      </span>
                      {typeof c.sent === 'number' ? (
                        <span className="text-sm text-text-secondary tabular-nums">
                          {c.sent} أُرسلت
                        </span>
                      ) : null}
                    </span>
                    {c.state ? (
                      <Badge tone={c.state === 'active' ? 'info' : 'neutral'}>
                        {STATE[c.state] ?? c.state}
                      </Badge>
                    ) : null}
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {/* «ماذا حدث» — THE MOST IMPORTANT ROUTE THIS SERVICE HAS, by its own note:
                        "it didn't arrive" is the only complaint this product generates, and every
                        correct refusal (consent, the ceiling, quiet hours) reads as a fault until
                        it is named. It was declared and called by nothing. */}
                    {action(catalog, 'campaigns.runs') ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={campaignBusy === `runs:${c.id}`}
                        aria-expanded={runsFor === c.id}
                        onClick={() => void openRuns(c.id)}
                      >
                        {campaignBusy === `runs:${c.id}` ? 'يُحمَّل…' : 'ماذا حدث'}
                      </Button>
                    ) : null}
                    {/* STOPPING A STANDING RULE, not deleting its history. Only while it runs —
                        a pause button on a finished campaign is a control that does nothing. */}
                    {c.state === 'active' && action(catalog, 'campaigns.pause') ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={campaignBusy === `pause:${c.id}`}
                        onClick={async () => {
                          const a2 = action(catalog, 'campaigns.pause');
                          if (!a2) return;
                          setCampaignBusy(`pause:${c.id}`);
                          await call(session, a2, { campaign_id: c.id }).catch(() => null);
                          setCampaignBusy('');
                          loadCampaigns();
                        }}
                      >
                        {campaignBusy === `pause:${c.id}` ? 'تُوقَف…' : 'أوقفها'}
                      </Button>
                    ) : null}
                  </div>

                  {/* WHAT ACTUALLY WENT OUT, PER SEND, WITH ITS REASON. Opened under ITS OWN
                      row — never under the whole list — so a shop with more than one campaign
                      can actually tell which one the panel is answering for. */}
                  {runsFor === c.id && runs ? (
                    <div className="flex flex-col gap-2 rounded-lg bg-surface-2 p-3">
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
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
