/**
 * The app-card feature list — component #9, and the one that renders another layer's own content
 * rather than data this kit already owned.
 *
 * WHY THIS EXISTS. Every "app card" in the console (شرائي's own `AppCard`, the admin panel's
 * `PlanCard`, `Locked.tsx`'s upsell card) used to draw its feature list from `LIMIT_WORDS` — one
 * flat sentence per BILLING LIMIT key, with a plain repeated checkmark and no icon at all. The
 * 2026-09-11 "features, not services" architecture moved the real content to each owning
 * service's own `core/features.py` (bookings/loyalty/campaigns/whatsapp-assistant/insights each
 * expose `GET .../features`; operations' own `apps()` carries تسجيل زيارة/جهات الاتصال/التقييم's
 * inline) — real, cited capabilities, each with its OWN icon and colour, never a billing-key
 * translation. This file is the one place that renders that shape, so every card in the console
 * shows the identical component for the identical feature (a shared feature like reminders'
 * learned-rhythm engine renders byte-identical wherever it appears, per
 * `ci/check_shared_features_match.py`'s own guarantee on the backend side).
 *
 * TWO REGISTRIES, BOTH KEYS NOT VALUES. The backend sends `icon: "clock"` / `tone: "blue"` —
 * strings, never a component or a class — so a new feature never needs a matching console PR:
 * `ICONS`/`TONE_CLASSES` below are the one place a new icon/tone key is taught to this console,
 * and an unknown key degrades to a generic icon/neutral tone rather than crashing the card.
 *
 * TONE KEYS MAP ONTO rj-ui/Badge's OWN FIVE VIVID TONES (accent/success/warning/danger/info) —
 * not a new palette invented for this file. Reusing the kit's own soft/on-soft pair per tone is
 * what makes a shelf of cards read as distinct products (2026-09-11 product decision, direct
 * screenshot feedback: "مافي تمايز الوان — كل الايقونات بنفس اللون") without adding a second
 * colour system next to the one every other screen already uses.
 */
import { useEffect, useState } from 'react';
import {
  AlertTriangle, Bell, BadgeCheck, Bot, Calendar, Car, CheckCircle2, Clock, Cloud, Gift, HandHeart,
  HelpCircle, Layers, MapPin, Megaphone, MessageCircle, Move, Receipt, Search, ShieldCheck,
  Sparkles, Star, Truck, Users, UserPlus, type LucideIcon,
} from 'lucide-react';
import { cn } from '../cn';
import type { AppFeature } from '../apps';
import { Skeleton } from './Skeleton';

/** Every icon key any backend `core/features.py` currently emits. `HelpCircle` is the honest
 *  fallback for a key this console has not learned yet — a sparse-looking bullet is a far smaller
 *  failure than a blank crash on a card meant to be selling something. */
export const APP_ICONS: Record<string, LucideIcon> = {
  clock: Clock,
  users: Users,
  'alert-triangle': AlertTriangle,
  'check-badge': BadgeCheck,
  move: Move,
  'shield-check': ShieldCheck,
  bell: Bell,
  'check-circle': CheckCircle2,
  car: Car,
  receipt: Receipt,
  search: Search,
  'user-plus': UserPlus,
  gift: Gift,
  star: Star,
  'message-circle': MessageCircle,
  calendar: Calendar,
  cloud: Cloud,
  layers: Layers,
  megaphone: Megaphone,
  sparkles: Sparkles,
  truck: Truck,
  'map-pin': MapPin,
  'hand-heart': HandHeart,
  bot: Bot,
};

/** `bg-{x}-soft` / `text-{x}-on-soft` — the exact pair `rj-ui/Badge.tsx`'s own `rjBadgeVariants`
 *  already defines for these five tones; this only reuses the class names, never redefines them. */
export const TONE_CLASSES: Record<string, string> = {
  teal: 'bg-success-soft text-success-on-soft',
  violet: 'bg-accent-soft text-accent-on-soft',
  amber: 'bg-warning-soft text-warning-on-soft',
  rose: 'bg-danger-soft text-danger-on-soft',
  blue: 'bg-info-soft text-info-on-soft',
  // App-header badges (apps.ts's own `tone` field) are named directly after Badge's own tones —
  // accepted here too so ONE map serves both the per-app header badge and the per-feature icon.
  accent: 'bg-accent-soft text-accent-on-soft',
  success: 'bg-success-soft text-success-on-soft',
  warning: 'bg-warning-soft text-warning-on-soft',
  danger: 'bg-danger-soft text-danger-on-soft',
  info: 'bg-info-soft text-info-on-soft',
};
const FALLBACK_TONE = 'bg-surface-2 text-text-secondary';

export function appIcon(key: string): LucideIcon {
  return APP_ICONS[key] ?? HelpCircle;
}

export function toneClasses(key: string): string {
  return TONE_CLASSES[key] ?? FALLBACK_TONE;
}

/** One bullet — an icon in its own tinted circle, a bold value-line title, and a shorter
 *  supporting sentence under it. No plain checkmark: a list where every icon is the same shape
 *  reads as decoration, not information (the same lesson the artifact mockup's own review found). */
function FeatureRow({ feature }: { feature: AppFeature }) {
  const Icon = appIcon(feature.icon);
  return (
    <li className="flex items-start gap-2.5">
      <span
        aria-hidden
        className={cn('grid h-7 w-7 shrink-0 place-items-center rounded-lg mt-0.5', toneClasses(feature.tone))}
      >
        <Icon size={14} />
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-semibold leading-snug text-text-primary">{feature.title}</span>
        <span className="block text-xs leading-relaxed text-text-secondary">{feature.detail}</span>
      </span>
    </li>
  );
}

function FeatureRowSkeleton() {
  return (
    <li className="flex items-start gap-2.5">
      <Skeleton className="h-7 w-7 shrink-0 rounded-lg" />
      <span className="flex min-w-0 flex-1 flex-col gap-1.5 pt-0.5">
        <Skeleton className="h-3.5 w-3/4" />
        <Skeleton className="h-3 w-full" />
      </span>
    </li>
  );
}

/**
 * The list itself — given features directly (operations already returned them inline, for
 * تسجيل زيارة/جهات الاتصال/التقييم) OR a `fetchFrom` path to read them from the owning service's
 * own route on mount (bookings/loyalty/campaigns/whatsapp-assistant/insights). Never both: a
 * caller passes whichever `apps.ts`'s own `AppRow`/`Owned.apps[]` actually gave it.
 */
export function AppFeatureList({
  features, actionId, fetcher, collapseAt,
}: {
  /** Already-known features (operations' own apps() response) — skips the fetch entirely. */
  features?: AppFeature[];
  /** `AppRow.featuresAction` — the catalog action id to fetch from when `features` is not
   *  already known. */
  actionId?: string;
  /** Resolves ONE catalog action id to its real content — the caller's own
   *  `action(catalog, id)` + `call(session, action)` pair (or the admin panel's `req()`
   *  equivalent), injected so this component never has to know which catalog or session it is. */
  fetcher?: (actionId: string) => Promise<{ features: AppFeature[] }>;
  /** Show only the first N rows behind a «عرض الكل» toggle — an OWNED card sitting in a row next
   *  to other owned cards (شرائي's own «التطبيقات» grid) used to print every feature's full
   *  title+detail regardless of how many the app carried, so a 7-feature app towered over its
   *  1-feature neighbour and the whole row read as uneven and text-heavy (owner's own screenshot:
   *  "طويلة لهذي الدرجة"). UNSET ON PURPOSE for a locked/upsell card — see Locked.tsx's own note
   *  on why that one shows every feature, never trimmed: a card arguing you should buy something
   *  must not hide the argument, but a card you already bought is a receipt, not a pitch. */
  collapseAt?: number;
}) {
  const [fetched, setFetched] = useState<AppFeature[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (features || !actionId || !fetcher) return;
    let live = true;
    setFetched(null);
    setFailed(false);
    fetcher(actionId)
      .then((r) => { if (live) setFetched(r.features ?? []); })
      .catch(() => { if (live) setFailed(true); });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- re-fetch only when the action id itself changes
  }, [actionId]);

  const rows = features ?? fetched;

  if (!rows && !failed) {
    return (
      <ul className="flex flex-col gap-3 border-t border-border-subtle pt-3">
        <FeatureRowSkeleton />
        <FeatureRowSkeleton />
        <FeatureRowSkeleton />
      </ul>
    );
  }
  // A CARD THAT COULD NOT READ ITS OWN FEATURES STILL SELLS — no error banner on a purchase
  // surface; it simply shows fewer lines than it should, same "degrade quietly" posture the rest
  // of this console's own store screen already holds for a billing read that failed.
  if (!rows || rows.length === 0) return null;

  const collapsed = collapseAt != null && rows.length > collapseAt && !expanded;
  const visible = collapsed ? rows.slice(0, collapseAt) : rows;

  return (
    <ul className="flex flex-col gap-3 border-t border-border-subtle pt-3">
      {visible.map((f) => <FeatureRow key={f.id} feature={f} />)}
      {collapsed ? (
        <li>
          <button type="button" onClick={() => setExpanded(true)}
                  className="text-xs font-medium text-accent hover:underline">
            عرض كل الميزات ({rows.length})
          </button>
        </li>
      ) : null}
    </ul>
  );
}
