/**
 * «الاستضافة المهنية» — a shop's own bookable resources (rooms/desks rented to freelancers by the
 * hour, OR a seat membership billed by the month/year), and everything an owner does to run that
 * side of the shop: the resources themselves (photo, description, price, capacity, weekly
 * availability), who may book/join at all (join requests, a shop-wide approval gate), the
 * bookings that result, and — for a membership resource — the members themselves.
 *
 * FOUR TABS, FOUR DIFFERENT SCOPES, ON PURPOSE — matching services/coworking's own
 * `api/v1/admin.py` module doc exactly:
 *
 *   الموارد       — branch-scoped (a resource belongs to one branch, or to none = every branch)
 *   طلبات الانضمام — SHOP-WIDE, NEVER BRANCH-SCOPED (core/joins.py: a freelancer approved once
 *                    may book/join any resource at that shop; branch-scoping this gate would be a
 *                    real behaviour change nobody asked for)
 *   الحجوزات      — branch-scoped, filtered by the SAME `branch` this whole console is looking at
 *   الأعضاء       — owner decision 2026-10-06: «month»/«year» resources are SEAT memberships, never
 *                    a specific desk (core/memberships.py's own module doc) — this tab is the
 *                    shop's own view of who holds a seat, and the two distinct ways a membership
 *                    ends (stop_renewal, ordinary vs force_end, which REQUIRES an explicit
 *                    acknowledgment — see `ForceEndDialog` below for why this can never be a plain
 *                    confirm dialog).
 *
 * GATED BY CAPABILITY ALONE, NOT BY THE APP STORE — same posture Services.tsx already holds
 * (`apps.ts` has no APP_ROW for coworking; every control below is `action(catalog, id) ? … : null`,
 * the same idiom `Can.tsx`'s own header describes). nav.ts's own `requires: ['coworking.list_resources']`
 * is the section-level gate; this file is the finer, per-button one.
 */
import { useEffect, useMemo, useState } from 'react';
import {
  Briefcase, Building2, Calendar1, Check, CircleSlash2, Copy, Image as ImageIcon, Layers, Pause,
  Play, Plus, UserRound, Users, X,
} from 'lucide-react';
import { PageHeader } from '../rj-ui/PageHeader';
import { Segmented } from '../rj-ui/Segmented';
import { Card } from '../rj-ui/Card';
import { Badge } from '../rj-ui/Badge';
import { Button } from '../rj-ui/Button';
import { Toggle } from '../rj-ui/Toggle';
import { Drawer } from '../rj-ui/Drawer';
import { Modal } from '../rj-ui/Modal';
import { ConfirmDialog } from '../rj-ui/ConfirmDialog';
import { EmptyState } from '../rj-ui/EmptyState';
import { Field, Input, Select, Textarea } from '../rj-ui/Field';
import { KpiCard } from '../rj-ui/KpiCard';
import { Table, type TableColumn } from '../rj-ui/Table';
import { Waiting } from '../Waiting';
import { action, call, downloadUrl, type Catalog } from '../catalog';
import { sentenceFor } from '../api';
import { hasFailed, isLoading, isReady } from '../loading';
import type { Session } from '../session';
import { useOperatorI18n, tf } from '../operator-i18n';
import './coworking-i18n';

// ── shapes, straight off services/coworking's own `core/models.py::Resource.public()`/
// `Membership.to_dict()` and `api/v1/admin.py` — never invented, always what the route actually
// returns/accepts. ───────────────────────────────────────────────────────────────────────────
type RentalPeriod = 'hourly' | 'month' | 'year';

interface Resource {
  id: string;
  name: string;
  branch_id: string;
  description?: string;
  active?: boolean;
  has_image?: boolean;
  hourly_price_minor?: number;
  // owner decision 2026-10-06 — absent on any row written before this feature existed reads as
  // "hourly"/1/0, which is byte-for-byte the row's own old behaviour (models.py::from_dict's own
  // doc). NEVER editable after creation (resources.py::update's own doc) — the create form is the
  // only place this is ever chosen.
  rental_period?: RentalPeriod;
  quantity?: number;
  period_price_minor?: number;
  // THE REAL WIRE SHAPE — `core/models.py::weekly_to_storage` stores (and `to_dict`/`public`
  // return) plain `[start, end]` pairs, e.g. `{"0": [[540, 780]]}`, never `{start_minute,
  // end_minute}` objects (that object shape is only the PUT request body's own `WindowIn`,
  // admin.py's own `AvailabilityIn` — the response is not the request, and this screen's first
  // draft conflated the two, which would have shown NaN times for any resource with a real
  // schedule already saved).
  weekly?: Record<string, [number, number][]>;
}

interface JoinRow {
  phone: string;
  status: 'pending' | 'approved' | 'blocked' | string;
  requested_at?: string;
}

interface BookingRow {
  id: string;
  resource_id: string;
  branch_id?: string;
  /** The freelancer's own phone — `core/bookings.py::create`'s real stored field name, never
   *  `phone` (this screen's own first draft assumed that name and rendered a blank column against
   *  a real seeded booking; verified against the real running service before fixing). */
  freelancer_phone?: string;
  /** Epoch seconds, same shape `core/bookings.py::list_for_tenant` actually returns — not an ISO
   *  string. Rendered through `formatWhen` below, never printed raw. */
  starts_at?: number;
  ends_at?: number;
  status?: string;
}

interface MembershipRow {
  id: string;
  resource_id: string;
  freelancer_phone: string;
  started_at: number;
  period_end: number;
  auto_renew: boolean;
  status: 'active' | 'ended' | string;
  period_price_minor: number;
  ended_at?: number;
  end_reason?: string;
  force_ack_by?: string;
  force_ack_note?: string;
}

function formatWhen(epochSeconds?: number): string {
  if (!epochSeconds) return '';
  return new Date(epochSeconds * 1000).toLocaleString();
}
function formatDate(epochSeconds?: number): string {
  if (!epochSeconds) return '';
  return new Date(epochSeconds * 1000).toLocaleDateString();
}

// THE REAL, DEPLOYED GATEWAY ORIGIN (vite.config.ts's own `define`, off `config/product.json`'s
// `urls.app`) — never a hardcoded domain a rebrand would silently miss.
declare const __PUBLIC_APP_ORIGIN__: string;

type Tab = 'resources' | 'joins' | 'bookings' | 'memberships';

// FOUR REAL COLOUR IDENTITIES, ONE PER TAB — the owner's own request for "تمايز لوني عالي"
// (high colour differentiation): الموارد (what you own) reads accent/violet, طلبات الانضمام (a
// pending decision) reads warning/amber, الحجوزات (a settled fact) reads info/teal, الأعضاء (a
// standing relationship, not a one-off event) reads success/emerald — never the same flat look
// repeated across four tabs. Same "colour before number" precedent Shop.tsx's own Tile and
// referrals_screen.dart's own reward bands already set.
const TAB_ACCENT: Record<Tab, { tone: 'accent' | 'warning' | 'info' | 'success'; soft: string; onSoft: string; ring: string }> = {
  resources: { tone: 'accent', soft: 'bg-accent-soft', onSoft: 'text-accent-on-soft', ring: 'ring-accent/30' },
  joins: { tone: 'warning', soft: 'bg-warning-soft', onSoft: 'text-warning-on-soft', ring: 'ring-warning/30' },
  bookings: { tone: 'info', soft: 'bg-info-soft', onSoft: 'text-info-on-soft', ring: 'ring-info/30' },
  memberships: { tone: 'success', soft: 'bg-success-soft', onSoft: 'text-success-on-soft', ring: 'ring-success/30' },
};

function TabSectionHeader({ tab, icon: Icon, title, said }: {
  tab: Tab; icon: typeof Layers; title: string; said: string;
}) {
  const a = TAB_ACCENT[tab];
  return (
    <div className="flex items-center gap-2.5">
      <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-full ${a.soft} ${a.onSoft} ring-2 ${a.ring}`}>
        <Icon size={17} aria-hidden />
      </span>
      <div className="flex flex-col">
        <h2 className="text-sm font-bold">{title}</h2>
        <p className="text-xs text-text-secondary">{said}</p>
      </div>
    </div>
  );
}

// «الرابط المشترك» — one shareable link per shop (services/coworking/app/api/public.py's own
// module docstring), handed to whichever freelancers the shop already works with. ALWAYS SHOWN,
// REGARDLESS OF TAB, same posture the pause banner above already takes — this is a shop-wide
// fact, not something scoped to one tab's own content.
function ShareLinkCard({ tenant, t }: { tenant: string; t: (key: string) => string }) {
  const [copied, setCopied] = useState(false);
  const url = `${__PUBLIC_APP_ORIGIN__}/p/coworking/${tenant}`;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch { /* clipboard denied — the link is still selectable/readable on screen */ }
  };

  return (
    <div className="flex items-center gap-3 rounded-card border border-border-subtle
                     bg-gradient-to-l from-amber-50 to-orange-50 p-3
                     dark:from-amber-950/40 dark:to-orange-950/30">
      <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-amber-500/15 text-amber-600 dark:text-amber-400">
        <Briefcase size={18} aria-hidden />
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <p className="text-xs font-semibold text-text-secondary">{t('coworking.shareLink.label')}</p>
        <p dir="ltr" className="truncate text-start font-mono text-xs text-text-primary">{url}</p>
      </div>
      <Button size="sm" variant={copied ? 'solid' : 'outline'} onClick={copy}>
        {copied ? <Check size={14} aria-hidden /> : <Copy size={14} aria-hidden />}
        {copied ? t('coworking.shareLink.copied') : t('coworking.shareLink.copy')}
      </Button>
    </div>
  );
}

// Weekday 0=Monday..6=Sunday, the exact convention `admin.py`'s own `AvailabilityIn` documents
// (Python's `date.weekday()`) — shown Saturday→Friday order to match the region's own week start,
// same display order Team.tsx already settled on for the identical field.
const DISPLAY_ORDER = [5, 6, 0, 1, 2, 3, 4];

function minutesToTime(m: number): string {
  return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
}
function timeToMinutes(t: string): number {
  const [h, m] = t.split(':').map(Number);
  return (h || 0) * 60 + (m || 0);
}

function rentalLabel(t: (k: string) => string, period?: RentalPeriod): string {
  return t(`coworking.resources.period.${period ?? 'hourly'}`);
}

function priceLabel(t: (k: string) => string, r: Resource): string {
  if ((r.rental_period ?? 'hourly') === 'hourly') {
    return typeof r.hourly_price_minor === 'number' && r.hourly_price_minor > 0
      ? tf(t, 'coworking.resources.pricePerHour', { price: (r.hourly_price_minor / 100).toFixed(2) })
      : t('coworking.resources.noPrice');
  }
  const key = r.rental_period === 'year' ? 'coworking.resources.pricePerYear' : 'coworking.resources.pricePerMonth';
  return typeof r.period_price_minor === 'number' && r.period_price_minor > 0
    ? tf(t, key, { price: (r.period_price_minor / 100).toFixed(2) })
    : t('coworking.resources.noPrice');
}

export function CoworkingScreen({
  session, catalog, branch,
}: { session: Session; catalog: Catalog; branch: string }) {
  const { t } = useOperatorI18n();
  const [tab, setTab] = useState<Tab>('resources');

  const [resources, setResources] = useState<Resource[] | null | undefined>(undefined);
  const [joins, setJoins] = useState<JoinRow[] | null | undefined>(undefined);
  const [bookings, setBookings] = useState<BookingRow[] | null | undefined>(undefined);
  const [memberships, setMemberships] = useState<MembershipRow[] | null | undefined>(undefined);
  const [paused, setPaused] = useState<boolean | null | undefined>(undefined);

  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const load = () => {
    const listResources = action(catalog, 'coworking.list_resources');
    if (listResources) {
      call<{ resources: Resource[] }>(session, listResources)
        .then((x) => setResources(x.resources))
        .catch(() => setResources(null));
    } else {
      setResources(null);
    }

    const listJoins = action(catalog, 'coworking.list_joins');
    if (listJoins) {
      call<{ joins: JoinRow[] }>(session, listJoins)
        .then((x) => setJoins(x.joins ?? []))
        .catch(() => setJoins(null));
    } else {
      setJoins(null);
    }

    const listBookings = action(catalog, 'coworking.list_bookings');
    if (listBookings) {
      call<{ bookings: BookingRow[] }>(session, listBookings)
        .then((x) => setBookings(x.bookings ?? []))
        .catch(() => setBookings(null));
    } else {
      setBookings(null);
    }

    const listMemberships = action(catalog, 'coworking.list_memberships');
    if (listMemberships) {
      call<{ memberships: MembershipRow[] }>(session, listMemberships)
        .then((x) => setMemberships(x.memberships ?? []))
        .catch(() => setMemberships(null));
    } else {
      setMemberships(null);
    }

    const getPause = action(catalog, 'coworking.get_pause');
    if (getPause) {
      call<{ paused: boolean }>(session, getPause)
        .then((x) => setPaused(Boolean(x.paused)))
        .catch(() => setPaused(null));
    } else {
      setPaused(null);
    }
  };

  useEffect(load, [session, catalog]);

  // BOOKINGS ARE ALREADY SERVER-FILTERED BY BRANCH SCOPE (admin.py's own `_in_scope` for THIS
  // caller's role), but a manager scoped to "every branch" still wants the header's own
  // BranchSwitch to narrow what he is looking at right now — the same client-side narrowing
  // Bookings.tsx applies on top of its own server-scoped read.
  const bookingsShown = useMemo(() => {
    if (!isReady(bookings)) return [];
    if (!branch) return bookings;
    return bookings.filter((b) => (b.branch_id ?? '') === branch);
  }, [bookings, branch]);

  const resourcesShown = useMemo(() => {
    if (!isReady(resources)) return [];
    if (!branch) return resources;
    // UNASSIGNED STAYS VISIBLE REGARDLESS OF THE BRANCH FILTER — admin.py's own docstring:
    // "a row with no branch is kept for everyone", never a data error to hide.
    return resources.filter((r) => !r.branch_id || r.branch_id === branch);
  }, [resources, branch]);

  // A BOOKING/MEMBERSHIP ROW ONLY EVER HOLDS `resource_id` (core/bookings.py's own stored dict,
  // core/memberships.py's own) — never a raw id shown to an owner, who has no reason to recognise
  // a UUID; the full (unfiltered) resource list is always available here regardless of which tab
  // is open, so this is a plain lookup, not a second fetch.
  const resourceById = useMemo(() => {
    const out: Record<string, Resource> = {};
    if (isReady(resources)) for (const r of resources) out[r.id] = r;
    return out;
  }, [resources]);
  const resourceNameById = useMemo(() => {
    const out: Record<string, string> = {};
    for (const [id, r] of Object.entries(resourceById)) out[id] = r.name;
    return out;
  }, [resourceById]);

  const pendingJoinsCount = isReady(joins) ? joins.filter((j) => j.status === 'pending').length : 0;
  const activeMembersCount = isReady(memberships)
    ? memberships.filter((m) => m.status === 'active').length : 0;

  const setPause = action(catalog, 'coworking.set_pause');
  const [confirmingPause, setConfirmingPause] = useState<boolean | null>(null);

  const applyPause = async (next: boolean) => {
    if (!setPause) return;
    setSaving(true); setError('');
    try {
      const out = await call<{ paused: boolean }>(session, setPause, { paused: next });
      setPaused(Boolean(out.paused));
    } catch (e) {
      setError(sentenceFor(e, t('coworking.pauseToggle.error'), t));
    } finally {
      setSaving(false);
      setConfirmingPause(null);
    }
  };

  const switcher = (
    <>
      <PageHeader icon={Building2} title={t('coworking.title')} />
      <Segmented
        className="flex w-full [&>button]:flex-1 [&>button]:whitespace-nowrap"
        ariaLabel={t('coworking.title')}
        value={tab}
        onChange={(v) => setTab(v as Tab)}
        options={[
          { value: 'resources', label: t('coworking.tab.resources'), icon: Layers },
          {
            value: 'joins', label: t('coworking.tab.joins'), icon: Users,
            ...(pendingJoinsCount > 0
              ? { badge: String(pendingJoinsCount), badgeTone: 'partial' as const } : {}),
          },
          { value: 'bookings', label: t('coworking.tab.bookings'), icon: Calendar1 },
          { value: 'memberships', label: t('coworking.tab.memberships'), icon: UserRound },
        ]}
      />
    </>
  );

  // THE HERO KPI STRIP — the owner's own request for a "فاخر" (luxury) feel: four numbers that
  // orient the whole screen in one glance, never buried inside a tab's own content. Shown
  // regardless of which tab is open, same "shop-wide fact, not tab-scoped" posture the pause
  // banner and the share-link card already hold.
  const kpis = (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <KpiCard icon={<Layers size={18} aria-hidden />}
        label={t('coworking.kpi.resources')}
        value={isReady(resources) ? String(resourcesShown.filter((r) => r.active !== false).length) : '—'}
        tone="accent" />
      <KpiCard icon={<Users size={18} aria-hidden />}
        label={t('coworking.kpi.pendingJoins')}
        value={isReady(joins) ? String(pendingJoinsCount) : '—'}
        tone="warning" />
      <KpiCard icon={<Calendar1 size={18} aria-hidden />}
        label={t('coworking.kpi.bookings')}
        value={isReady(bookings) ? String(bookingsShown.filter((b) => b.status !== 'cancelled').length) : '—'}
        tone="info" />
      <KpiCard icon={<UserRound size={18} aria-hidden />}
        label={t('coworking.kpi.activeMembers')}
        value={isReady(memberships) ? String(activeMembersCount) : '—'}
        tone="success" />
    </div>
  );

  // «موقوف الآن» — A FULL-WIDTH DANGER BANNER, ABOVE EVERYTHING, IMPOSSIBLE TO MISS. Shop-wide by
  // design (admin.py's own docstring: pause is never branch-scoped) — shown regardless of which
  // tab is open, since it changes what EVERY tab means.
  const pauseBanner = isReady(paused) && paused ? (
    <div className="flex items-center gap-2 rounded-card border border-danger/30 bg-danger-soft
                     px-4 py-3 text-sm font-medium text-danger-on-soft">
      <CircleSlash2 size={16} aria-hidden className="shrink-0" />
      {t('coworking.pausedBanner')}
    </div>
  ) : null;

  const pauseControl = setPause && isReady(paused) ? (
    <div className="flex items-center gap-2">
      <Toggle
        checked={paused}
        onChange={(next) => setConfirmingPause(next)}
        label={t('coworking.pauseToggle.label')}
        disabled={saving}
      />
    </div>
  ) : null;

  if (isLoading(resources) && isLoading(joins) && isLoading(bookings)) {
    return <div className="flex flex-col gap-3 p-4">{switcher}<Waiting what={t('coworking.loading')} /></div>;
  }

  if (hasFailed(resources) && hasFailed(joins) && hasFailed(bookings)) {
    return (
      <div className="flex flex-col gap-3 p-4">
        {switcher}
        <EmptyState
          title={t('coworking.loadFailed.title')}
          description={t('coworking.loadFailed.description')}
          action={<Button onClick={load}>{t('coworking.retry')}</Button>}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-4">
      {switcher}
      {kpis}
      {session.tenant ? <ShareLinkCard tenant={session.tenant} t={t} /> : null}
      {pauseBanner}
      {pauseControl}
      {error ? <p className="text-danger text-sm">{error}</p> : null}

      {tab === 'resources' ? (
        <div className="flex flex-col gap-3">
          <TabSectionHeader tab="resources" icon={Layers}
            title={t('coworking.tab.resources')} said={t('coworking.resources.said')} />
          <ResourcesTab
            session={session} catalog={catalog} resources={resourcesShown} raw={resources}
            load={load} branch={branch}
          />
        </div>
      ) : null}
      {tab === 'joins' ? (
        <div className="flex flex-col gap-3">
          <TabSectionHeader tab="joins" icon={Users}
            title={t('coworking.tab.joins')} said={t('coworking.joins.said')} />
          <JoinsTab session={session} catalog={catalog} joins={joins} load={load} />
        </div>
      ) : null}
      {tab === 'bookings' ? (
        <div className="flex flex-col gap-3">
          <TabSectionHeader tab="bookings" icon={Calendar1}
            title={t('coworking.tab.bookings')} said={t('coworking.bookings.said')} />
          <BookingsTab session={session} catalog={catalog} bookings={bookingsShown} raw={bookings}
            load={load} resourceNameById={resourceNameById} />
        </div>
      ) : null}
      {tab === 'memberships' ? (
        <div className="flex flex-col gap-3">
          <TabSectionHeader tab="memberships" icon={UserRound}
            title={t('coworking.tab.memberships')} said={t('coworking.memberships.said')} />
          <MembershipsTab session={session} catalog={catalog} memberships={memberships}
            raw={memberships} load={load} resourceNameById={resourceNameById} />
        </div>
      ) : null}

      <ConfirmDialog
        open={confirmingPause !== null}
        onClose={() => setConfirmingPause(null)}
        onConfirm={() => applyPause(Boolean(confirmingPause))}
        title={confirmingPause
          ? t('coworking.pauseToggle.confirmPause')
          : t('coworking.pauseToggle.confirmResume')}
        danger={Boolean(confirmingPause)}
        busy={saving}
        confirmLabel={t('coworking.resources.save')}
        cancelLabel={t('coworking.resources.cancel')}
      />
    </div>
  );
}

// ── الموارد ────────────────────────────────────────────────────────────────────────────────────
function ResourcesTab({
  session, catalog, resources, raw, load, branch,
}: {
  session: Session; catalog: Catalog; resources: Resource[]; raw: Resource[] | null | undefined;
  load: () => void; branch: string;
}) {
  const { t } = useOperatorI18n();
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [rentalPeriod, setRentalPeriod] = useState<RentalPeriod>('hourly');
  const [quantity, setQuantity] = useState('1');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [openId, setOpenId] = useState<string | null>(null);

  const create = action(catalog, 'coworking.create_resource');
  const update = action(catalog, 'coworking.update_resource');

  const addResource = async () => {
    if (!create || !name.trim()) return;
    setSaving(true); setError('');
    try {
      const created = await call<Resource>(session, create, {
        name: name.trim(), branch_id: branch, description: description.trim(),
        rental_period: rentalPeriod, quantity: Math.max(1, Math.round(Number(quantity) || 1)),
      });
      setAdding(false); setName(''); setDescription(''); setRentalPeriod('hourly'); setQuantity('1');
      load();
      // STRAIGHT INTO THE EDITOR, NOT BACK TO THE GRID — a resource is created with no photo at
      // all (the create form never asks for one; `coworking.create_resource` has no body slot
      // for it — a photo needs a real resource_id to upload against, same reason
      // `upload_resource_image`'s own path requires one). Without this, a shop adds a resource,
      // lands back on a grid showing its own new placeholder-icon card, and has to notice that
      // tapping the card again opens the one place a photo can actually be added — found live
      // (owner's own report, 2026-10-06): "مافي إدراج صورة" was never a missing capability, it
      // was a missing NEXT STEP.
      if (created?.id) setOpenId(created.id);
    } catch (e) {
      setError(sentenceFor(e, t('coworking.resources.createFailed'), t));
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (r: Resource) => {
    if (!update) return;
    try {
      await call(session, update, { resource_id: r.id, active: r.active === false });
      load();
    } catch { /* the row simply keeps its old state on screen; the retry is another tap */ }
  };

  if (isLoading(raw)) return <Waiting what={t('coworking.loading')} />;
  if (hasFailed(raw)) {
    return (
      <EmptyState title={t('coworking.loadFailed.title')} description={t('coworking.loadFailed.description')}
        action={<Button onClick={load}>{t('coworking.retry')}</Button>} />
    );
  }

  if (resources.length === 0 && !adding) {
    return (
      <EmptyState
        title={t('coworking.resources.empty.title')}
        description={t('coworking.resources.empty.description')}
        action={create ? <Button onClick={() => setAdding(true)}>{t('coworking.resources.addFirst')}</Button> : null}
      />
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {create ? (
        <Button className="self-start" onClick={() => setAdding(true)}>
          <Plus size={16} aria-hidden /> {t('coworking.resources.add')}
        </Button>
      ) : null}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {resources.map((r) => (
          <ResourceCard key={r.id} r={r} session={session} catalog={catalog}
            onToggleActive={() => toggleActive(r)} onOpen={() => setOpenId(r.id)} t={t} />
        ))}
      </div>

      {adding ? (
        <Modal open={adding} onClose={() => setAdding(false)} title={t('coworking.resources.add')}
          footer={(
            <>
              <Button variant="ghost" onClick={() => setAdding(false)} disabled={saving}>
                {t('coworking.resources.cancel')}
              </Button>
              <Button onClick={addResource} disabled={saving || !name.trim()}>
                {t('coworking.resources.save')}
              </Button>
            </>
          )}>
          <div className="flex flex-col gap-3">
            {error ? <p className="text-danger text-sm">{error}</p> : null}
            <Field label={t('coworking.resources.name')} required>
              <Input autoFocus value={name} onChange={(e) => setName(e.target.value)}
                placeholder={t('coworking.resources.namePlaceholder')} />
            </Field>
            <Field label={t('coworking.resources.descriptionLabel')}>
              <Textarea value={description} onChange={(e) => setDescription(e.target.value)}
                placeholder={t('coworking.resources.descriptionPlaceholder')} rows={3} />
            </Field>
            {/* NEVER EDITABLE AFTER CREATION (resources.py::update's own doc) — the one and only
                moment this is chosen, so it is front and centre here, never buried in the edit
                drawer where an owner might expect to change it later. */}
            <Field label={t('coworking.resources.rentalPeriod')}
              hint={t('coworking.resources.rentalPeriodHint')}>
              <Select value={rentalPeriod} onChange={(e) => setRentalPeriod(e.target.value as RentalPeriod)}>
                <option value="hourly">{t('coworking.resources.period.hourly')}</option>
                <option value="month">{t('coworking.resources.period.month')}</option>
                <option value="year">{t('coworking.resources.period.year')}</option>
              </Select>
            </Field>
            <Field label={t('coworking.resources.quantity')} hint={t('coworking.resources.quantityHint')}>
              <Input type="number" min={1} value={quantity} onChange={(e) => setQuantity(e.target.value)} />
            </Field>
          </div>
        </Modal>
      ) : null}

      {openId ? (
        <ResourceDrawer
          resource={resources.find((r) => r.id === openId) ?? null}
          session={session} catalog={catalog} onClose={() => setOpenId(null)} onSaved={load} t={t}
        />
      ) : null}
    </div>
  );
}

function ResourceCard({
  r, session, catalog, onToggleActive, onOpen, t,
}: {
  r: Resource; session: Session; catalog: Catalog; onToggleActive: () => void; onOpen: () => void;
  t: (key: string) => string;
}) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  useEffect(() => {
    const get = action(catalog, 'coworking.get_resource_image');
    if (!get || !r.has_image) return;
    let cancelled = false;
    downloadUrl(session, get, { resource_id: r.id }).then((url) => {
      if (!cancelled) setImageUrl(url);
    }).catch(() => undefined);
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [r.id, r.has_image]);
  useEffect(() => () => { if (imageUrl) URL.revokeObjectURL(imageUrl); }, [imageUrl]);

  const active = r.active !== false;
  const period = r.rental_period ?? 'hourly';
  const quantity = r.quantity ?? 1;

  return (
    <Card interactive onClick={onOpen}
      className={`group flex flex-col gap-0 overflow-hidden p-0 transition-shadow ${active ? 'ring-1 ring-accent/20 hover:shadow-lg' : 'opacity-80'}`}>
      {/* A TALLER, PHOTO-FORWARD HERO — the owner's own "تصميم فاخر" request: the old card gave the
          image a cramped 128px strip above a dense text block; this one lets the photo carry the
          card, with the name/price legible straight over it (a gradient scrim, never a flat
          overlay) the same way a real listing card (a rental, a hotel room) earns its look. */}
      <div className="relative h-44 w-full overflow-hidden bg-surface-2">
        {imageUrl ? (
          <img src={imageUrl} alt={r.name}
            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105" />
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <ImageIcon size={32} className="text-text-muted" aria-hidden />
          </div>
        )}
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-20 bg-gradient-to-t from-black/70 to-transparent" />
        <div className="absolute inset-x-3 bottom-2 flex items-end justify-between gap-2">
          <p className="truncate text-sm font-bold text-white drop-shadow">{r.name}</p>
          <Badge tone={active ? 'success' : 'neutral'}>
            {active ? t('coworking.resources.active') : t('coworking.resources.paused')}
          </Badge>
        </div>
        <div className="absolute inset-x-3 top-2 flex items-center justify-between gap-2">
          <Badge tone={period === 'hourly' ? 'accent' : 'success'} className="shadow">
            {rentalLabel(t, period)}
          </Badge>
          {!r.branch_id ? (
            <Badge tone="info" className="shadow">{t('coworking.resources.branch.unassigned')}</Badge>
          ) : null}
        </div>
      </div>
      <div className="flex flex-col gap-1.5 p-4">
        {r.description ? <p className="line-clamp-2 text-xs text-text-secondary">{r.description}</p> : null}
        <div className="flex items-center justify-between">
          <p className="text-sm font-semibold text-text-primary">{priceLabel(t, r)}</p>
          <p className="text-xs text-text-muted">
            {tf(t, 'coworking.resources.quantityBadge', { n: String(quantity) })}
          </p>
        </div>
        <div className="mt-1.5 flex gap-2">
          <Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); onOpen(); }}>
            {t('coworking.resources.edit')}
          </Button>
          {action(catalog, 'coworking.update_resource') ? (
            <Button size="sm" variant="ghost" onClick={(e) => { e.stopPropagation(); onToggleActive(); }}>
              {active ? t('coworking.resources.deactivate') : t('coworking.resources.activate')}
            </Button>
          ) : null}
        </div>
      </div>
    </Card>
  );
}

function ResourceDrawer({
  resource, session, catalog, onClose, onSaved, t,
}: {
  resource: Resource | null; session: Session; catalog: Catalog; onClose: () => void;
  onSaved: () => void; t: (key: string) => string;
}) {
  const [name, setName] = useState(resource?.name ?? '');
  const [description, setDescription] = useState(resource?.description ?? '');
  const [price, setPrice] = useState(String(resource?.hourly_price_minor ?? 0));
  const [periodPrice, setPeriodPrice] = useState(String(resource?.period_price_minor ?? 0));
  const [quantity, setQuantity] = useState(String(resource?.quantity ?? 1));
  const [weekly, setWeekly] = useState<Record<number, { start_minute: number; end_minute: number }[]>>(() => {
    const out: Record<number, { start_minute: number; end_minute: number }[]> = {};
    // CONVERTED HERE, ONCE — the wire shape is `[start, end]` pairs (see the `Resource` interface's
    // own comment above); everything past this point in the drawer works in `{start_minute,
    // end_minute}` objects, which is what the PUT body actually wants.
    for (const [day, windows] of Object.entries(resource?.weekly ?? {})) {
      out[Number(day)] = (windows ?? []).map(([start_minute, end_minute]) => ({ start_minute, end_minute }));
    }
    return out;
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [uploading, setUploading] = useState(false);
  const [imageUrl, setImageUrl] = useState<string | null>(null);

  const update = action(catalog, 'coworking.update_resource');
  const setAvailability = action(catalog, 'coworking.set_availability');
  const uploadImage = action(catalog, 'coworking.upload_resource_image');
  const getImage = action(catalog, 'coworking.get_resource_image');

  const period = resource?.rental_period ?? 'hourly';

  useEffect(() => {
    if (!resource || !getImage || !resource.has_image) return;
    let cancelled = false;
    downloadUrl(session, getImage, { resource_id: resource.id }).then((url) => {
      if (!cancelled) setImageUrl(url);
    }).catch(() => undefined);
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resource?.id, resource?.has_image]);
  useEffect(() => () => { if (imageUrl) URL.revokeObjectURL(imageUrl); }, [imageUrl]);

  if (!resource) return null;

  const saveDetails = async () => {
    if (!update) return;
    setSaving(true); setError('');
    try {
      await call(session, update, {
        resource_id: resource.id, name: name.trim() || resource.name,
        description: description.trim(),
        quantity: Math.max(1, Math.round(Number(quantity) || 1)),
        ...(period !== 'hourly'
          ? { period_price_minor: Math.max(0, Math.round(Number(periodPrice) || 0)) } : {}),
      });
      onSaved();
    } catch (e) {
      setError(sentenceFor(e, t('coworking.resources.updateFailed'), t));
    } finally {
      setSaving(false);
    }
  };

  const saveAvailability = async () => {
    if (!setAvailability) return;
    setSaving(true); setError('');
    try {
      const weeklyOut: Record<number, { start_minute: number; end_minute: number }[]> = {};
      for (let d = 0; d < 7; d++) weeklyOut[d] = weekly[d] ?? [];
      await call(session, setAvailability, {
        resource_id: resource.id, weekly: weeklyOut, exceptions: {},
        hourly_price_minor: Math.max(0, Math.round(Number(price) || 0)),
      });
      onSaved();
    } catch (e) {
      setError(sentenceFor(e, t('coworking.resources.availabilityFailed'), t));
    } finally {
      setSaving(false);
    }
  };

  const onPickImage = async (file: File) => {
    if (!uploadImage) return;
    setUploading(true); setError('');
    try {
      const data_base64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result).split(',')[1] ?? '');
        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(file);
      });
      await call(session, uploadImage, { resource_id: resource.id, content_type: file.type, data_base64 });
      onSaved();
    } catch (e) {
      setError(sentenceFor(e, t('coworking.resources.uploadFailed'), t));
    } finally {
      setUploading(false);
    }
  };

  function addWindow(day: number) {
    setWeekly((cur) => ({
      ...cur,
      [day]: [...(cur[day] ?? []), { start_minute: 9 * 60, end_minute: 17 * 60 }],
    }));
  }
  function removeWindow(day: number, idx: number) {
    setWeekly((cur) => ({ ...cur, [day]: (cur[day] ?? []).filter((_, i) => i !== idx) }));
  }
  function patchWindow(day: number, idx: number, patch: Partial<{ start_minute: number; end_minute: number }>) {
    setWeekly((cur) => ({
      ...cur,
      [day]: (cur[day] ?? []).map((w, i) => (i === idx ? { ...w, ...patch } : w)),
    }));
  }

  return (
    <Drawer open onClose={onClose} title={resource.name}
      subtitle={rentalLabel(t, period)}
      footer={(
        <>
          <Button variant="ghost" onClick={onClose}>{t('coworking.resources.cancel')}</Button>
          <Button onClick={saveDetails} disabled={saving}>{t('coworking.resources.save')}</Button>
        </>
      )}>
      <div className="flex flex-col gap-5">
        {error ? <p className="text-danger text-sm">{error}</p> : null}

        {/* A REAL, LARGE PHOTO PREVIEW — not a bare upload button. The owner sees exactly what a
            freelancer opening the public link sees, before he ever touches "رفع صورة". */}
        <div className="relative h-48 w-full overflow-hidden rounded-card bg-surface-2">
          {imageUrl ? (
            <img src={imageUrl} alt={resource.name} className="h-full w-full object-cover" />
          ) : (
            <div className="flex h-full w-full items-center justify-center">
              <ImageIcon size={36} className="text-text-muted" aria-hidden />
            </div>
          )}
        </div>
        {uploadImage ? (
          <label className="inline-flex w-fit cursor-pointer items-center gap-2 self-start rounded-lg border
                             border-dashed border-border-strong px-3 py-2 text-sm hover:bg-surface-2">
            <ImageIcon size={14} aria-hidden />
            {uploading ? t('coworking.loading') : t('coworking.resources.uploadPhoto')}
            <input type="file" accept="image/*" className="hidden" disabled={uploading}
              onChange={(e) => { const f = e.target.files?.[0]; if (f) void onPickImage(f); }} />
          </label>
        ) : null}

        <div className="flex flex-col gap-3 border-t border-border-subtle pt-4">
          <Field label={t('coworking.resources.name')} required>
            <Input value={name} onChange={(e) => setName(e.target.value)}
              placeholder={t('coworking.resources.namePlaceholder')} />
          </Field>
          <Field label={t('coworking.resources.descriptionLabel')}>
            <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3}
              placeholder={t('coworking.resources.descriptionPlaceholder')} />
          </Field>
          <Field label={t('coworking.resources.quantity')} hint={t('coworking.resources.quantityHint')}>
            <Input type="number" min={1} value={quantity} onChange={(e) => setQuantity(e.target.value)} />
          </Field>
          {period !== 'hourly' ? (
            <Field label={period === 'year' ? t('coworking.resources.yearlyPrice') : t('coworking.resources.monthlyPrice')}>
              <Input type="number" min={0} value={periodPrice} onChange={(e) => setPeriodPrice(e.target.value)}
                className="w-40" />
            </Field>
          ) : null}
        </div>

        {/* HOURLY ONLY — a membership resource has no time-of-day schedule at all
            (core/memberships.py's own module doc: "no time-of-day span at all"). */}
        {period === 'hourly' && setAvailability ? (
          <div className="flex flex-col gap-3 border-t border-border-subtle pt-4">
            <div>
              <p className="text-sm font-semibold">{t('coworking.resources.availability')}</p>
              <p className="text-xs text-text-secondary">{t('coworking.resources.availabilityHint')}</p>
            </div>

            <Field label={t('coworking.resources.hourlyPrice')}>
              <Input type="number" min={0} value={price} onChange={(e) => setPrice(e.target.value)}
                className="w-40" />
            </Field>

            <div className="flex flex-col gap-2">
              {DISPLAY_ORDER.map((day) => {
                const windows = weekly[day] ?? [];
                return (
                  <div key={day} className="flex flex-col gap-1.5 rounded-lg bg-surface-2 p-2.5">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold">{t(`coworking.resources.day.${day}`)}</span>
                      <Button size="sm" variant="ghost" onClick={() => addWindow(day)}>
                        <Plus size={12} aria-hidden /> {t('coworking.resources.addWindow')}
                      </Button>
                    </div>
                    {windows.length === 0 ? (
                      <p className="text-xs text-text-muted">{t('coworking.resources.dayClosed')}</p>
                    ) : windows.map((w, idx) => (
                      <div key={idx} className="flex items-center gap-2">
                        <span className="text-xs text-text-muted">{t('coworking.resources.from')}</span>
                        <input type="time" value={minutesToTime(w.start_minute)}
                          onChange={(e) => patchWindow(day, idx, { start_minute: timeToMinutes(e.target.value) })}
                          className="h-8 rounded-md bg-surface-1 px-2 text-xs" />
                        <span className="text-xs text-text-muted">{t('coworking.resources.to')}</span>
                        <input type="time" value={minutesToTime(w.end_minute)}
                          onChange={(e) => patchWindow(day, idx, { end_minute: timeToMinutes(e.target.value) })}
                          className="h-8 rounded-md bg-surface-1 px-2 text-xs" />
                        <button type="button" aria-label={t('coworking.resources.removeWindow')}
                          onClick={() => removeWindow(day, idx)}
                          className="ms-auto text-xs text-danger">×</button>
                      </div>
                    ))}
                  </div>
                );
              })}
            </div>

            <Button className="self-start" onClick={saveAvailability} disabled={saving}>
              {t('coworking.resources.save')}
            </Button>
          </div>
        ) : null}
      </div>
    </Drawer>
  );
}

// ── طلبات الانضمام (شامل المحل، بلا فرع) ─────────────────────────────────────────────────────────
function JoinsTab({
  session, catalog, joins, load,
}: { session: Session; catalog: Catalog; joins: JoinRow[] | null | undefined; load: () => void }) {
  const { t } = useOperatorI18n();
  const [busyPhone, setBusyPhone] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [confirming, setConfirming] = useState<{ phone: string; kind: 'approve' | 'reject' | 'block' | 'unblock' } | null>(null);

  const approve = action(catalog, 'coworking.approve_join');
  const reject = action(catalog, 'coworking.reject_join');
  const block = action(catalog, 'coworking.block_phone');
  const unblock = action(catalog, 'coworking.unblock_phone');

  const run = async (phone: string, kind: 'approve' | 'reject' | 'block' | 'unblock') => {
    const a = kind === 'approve' ? approve : kind === 'reject' ? reject : kind === 'block' ? block : unblock;
    if (!a) return;
    setBusyPhone(phone); setError('');
    try {
      await call(session, a, { phone });
      load();
    } catch (e) {
      setError(sentenceFor(e, t('coworking.joins.actionFailed'), t));
    } finally {
      setBusyPhone(null);
      setConfirming(null);
    }
  };

  if (isLoading(joins)) return <Waiting what={t('coworking.loading')} />;
  if (hasFailed(joins)) {
    return (
      <EmptyState title={t('coworking.loadFailed.title')} description={t('coworking.loadFailed.description')}
        action={<Button onClick={load}>{t('coworking.retry')}</Button>} />
    );
  }
  if (joins.length === 0) {
    return <EmptyState title={t('coworking.joins.empty.title')} description={t('coworking.joins.empty.description')} />;
  }

  const toneFor = (status: string) => status === 'pending' ? 'warning' : status === 'blocked' ? 'danger'
    : status === 'approved' ? 'success' : 'neutral';

  return (
    <div className="flex flex-col gap-2">
      {error ? <p className="text-danger text-sm">{error}</p> : null}
      {joins.map((j) => (
        <Card key={j.phone} className="flex items-center justify-between gap-3 p-3">
          <div className="flex flex-col gap-0.5">
            <p className="font-mono text-sm">{j.phone}</p>
            <div className="flex items-center gap-2">
              <Badge tone={toneFor(j.status)}>{t(`coworking.joins.status.${j.status}`) || j.status}</Badge>
              {j.requested_at ? (
                <span className="text-xs text-text-muted">
                  {tf(t, 'coworking.joins.requestedAt', { when: j.requested_at })}
                </span>
              ) : null}
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            {j.status === 'pending' && approve ? (
              <Button size="sm" onClick={() => setConfirming({ phone: j.phone, kind: 'approve' })}
                disabled={busyPhone === j.phone}>
                {t('coworking.joins.approve')}
              </Button>
            ) : null}
            {j.status === 'pending' && reject ? (
              <Button size="sm" variant="outline" onClick={() => setConfirming({ phone: j.phone, kind: 'reject' })}
                disabled={busyPhone === j.phone}>
                {t('coworking.joins.reject')}
              </Button>
            ) : null}
            {/* THE MORE FINAL ACT LIVES BEHIND AN OVERFLOW, NEVER BESIDE APPROVE/REJECT — a block
                is a different order of decision than the two everyday ones beside it. */}
            {j.status !== 'blocked' && block ? (
              <Button size="sm" variant="ghost" onClick={() => setConfirming({ phone: j.phone, kind: 'block' })}
                disabled={busyPhone === j.phone}>
                {t('coworking.joins.block')}
              </Button>
            ) : null}
            {j.status === 'blocked' && unblock ? (
              <Button size="sm" variant="ghost" onClick={() => setConfirming({ phone: j.phone, kind: 'unblock' })}
                disabled={busyPhone === j.phone}>
                {t('coworking.joins.unblock')}
              </Button>
            ) : null}
          </div>
        </Card>
      ))}

      <ConfirmDialog
        open={confirming !== null}
        onClose={() => setConfirming(null)}
        onConfirm={() => confirming && run(confirming.phone, confirming.kind)}
        title={confirming ? t(`coworking.joins.confirm${confirming.kind[0].toUpperCase()}${confirming.kind.slice(1)}`) : ''}
        danger={confirming?.kind === 'block'}
        busy={busyPhone !== null}
        confirmLabel={confirming ? t(`coworking.joins.${confirming.kind}`) : ''}
        cancelLabel={t('coworking.resources.cancel')}
      />
    </div>
  );
}

// ── الحجوزات (بحسب فرع المُشاهدة الحالي) ──────────────────────────────────────────────────────────
function BookingsTab({
  session, catalog, bookings, raw, load, resourceNameById,
}: {
  session: Session; catalog: Catalog; bookings: BookingRow[]; raw: BookingRow[] | null | undefined;
  load: () => void; resourceNameById: Record<string, string>;
}) {
  const { t } = useOperatorI18n();
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const cancel = action(catalog, 'coworking.cancel_booking');

  const doCancel = async (id: string) => {
    if (!cancel) return;
    setBusy(true); setError('');
    try {
      await call(session, cancel, { booking_id: id });
      load();
    } catch (e) {
      setError(sentenceFor(e, t('coworking.bookings.cancelFailed'), t));
    } finally {
      setBusy(false);
      setConfirmId(null);
    }
  };

  const toneFor = (status?: string) => status === 'cancelled' ? 'neutral' : status === 'completed' ? 'info' : 'success';

  const columns: TableColumn<BookingRow>[] = [
    { key: 'resource', header: t('coworking.bookings.resource'),
      render: (b) => resourceNameById[b.resource_id] ?? b.resource_id },
    { key: 'phone', header: t('coworking.bookings.phone'),
      render: (b) => <span className="font-mono">{b.freelancer_phone ?? ''}</span> },
    { key: 'when', header: t('coworking.bookings.when'),
      render: (b) => `${formatWhen(b.starts_at)}${b.ends_at ? ` – ${formatWhen(b.ends_at)}` : ''}` },
    { key: 'status', header: t('coworking.bookings.status'),
      render: (b) => (
        <Badge tone={toneFor(b.status)}>{b.status ? (t(`coworking.bookings.status.${b.status}`) || b.status) : ''}</Badge>
      ) },
    { key: 'actions', header: '', width: 120,
      render: (b) => (
        cancel && b.status !== 'cancelled' ? (
          <Button size="sm" variant="ghost" onClick={() => setConfirmId(b.id)} disabled={busy}>
            {t('coworking.bookings.cancel')}
          </Button>
        ) : null
      ) },
  ];

  return (
    <div className="flex flex-col gap-2">
      {error ? <p className="text-danger text-sm">{error}</p> : null}
      <Table
        columns={columns}
        rows={isLoading(raw) ? 'loading' : hasFailed(raw) ? 'failed' : bookings}
        getRowId={(b) => b.id}
        emptyTitle={t('coworking.bookings.empty.title')}
        emptyDescription={t('coworking.bookings.empty.description')}
        failedTitle={t('coworking.loadFailed.title')}
      />

      <ConfirmDialog
        open={confirmId !== null}
        onClose={() => setConfirmId(null)}
        onConfirm={() => confirmId && doCancel(confirmId)}
        title={t('coworking.bookings.confirmCancel')}
        busy={busy}
        confirmLabel={t('coworking.bookings.cancel')}
        cancelLabel={t('coworking.resources.cancel')}
      />
    </div>
  );
}

// ── الأعضاء (owner decision 2026-10-06) — moment-to-moment seats on «month»/«year» resources ───
function MembershipsTab({
  session, catalog, memberships, raw, load, resourceNameById,
}: {
  session: Session; catalog: Catalog; memberships: MembershipRow[] | null | undefined;
  raw: MembershipRow[] | null | undefined; load: () => void;
  resourceNameById: Record<string, string>;
}) {
  const { t } = useOperatorI18n();
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState<string | null>(null);
  const [forceEndTarget, setForceEndTarget] = useState<MembershipRow | null>(null);

  const stopRenewal = action(catalog, 'coworking.stop_membership_renewal');
  const resumeRenewal = action(catalog, 'coworking.resume_membership_renewal');
  const forceEnd = action(catalog, 'coworking.force_end_membership');

  const toggleRenewal = async (m: MembershipRow) => {
    const a = m.auto_renew ? stopRenewal : resumeRenewal;
    if (!a) return;
    setBusyId(m.id); setError('');
    try {
      await call(session, a, { membership_id: m.id });
      load();
    } catch (e) {
      setError(sentenceFor(e, t('coworking.memberships.actionFailed'), t));
    } finally {
      setBusyId(null);
    }
  };

  const rows = (memberships ?? []).slice().sort((a, b) => {
    // ACTIVE FIRST, THEN SOONEST TO LAPSE — the shop's own question is almost always "who do I
    // need to think about", and an ended row from months ago answers that least.
    if (a.status !== b.status) return a.status === 'active' ? -1 : 1;
    return a.period_end - b.period_end;
  });

  const statusTone = (m: MembershipRow) => m.status === 'active' ? 'success' : 'neutral';

  const columns: TableColumn<MembershipRow>[] = [
    { key: 'resource', header: t('coworking.memberships.resource'),
      render: (m) => resourceNameById[m.resource_id] ?? m.resource_id },
    { key: 'phone', header: t('coworking.memberships.phone'),
      render: (m) => <span className="font-mono">{m.freelancer_phone}</span> },
    { key: 'status', header: t('coworking.memberships.status'),
      render: (m) => (
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge tone={statusTone(m)}>
            {m.status === 'active' ? t('coworking.memberships.active') : t('coworking.memberships.ended')}
          </Badge>
          {m.status === 'active' ? (
            <Badge tone={m.auto_renew ? 'info' : 'warning'}>
              {m.auto_renew ? t('coworking.memberships.renewing') : t('coworking.memberships.notRenewing')}
            </Badge>
          ) : (
            <Badge tone={m.end_reason === 'force_ended' ? 'danger' : 'neutral'}>
              {t(`coworking.memberships.endReason.${m.end_reason || 'expired'}`)}
            </Badge>
          )}
        </div>
      ) },
    { key: 'period_end', header: t('coworking.memberships.periodEnd'),
      render: (m) => formatDate(m.status === 'active' ? m.period_end : m.ended_at) },
    { key: 'actions', header: '', width: 230,
      render: (m) => (
        m.status !== 'active' ? null : (
          <div className="flex items-center gap-1.5">
            {stopRenewal || resumeRenewal ? (
              <Button size="sm" variant="outline" onClick={() => toggleRenewal(m)} disabled={busyId === m.id}>
                {m.auto_renew ? (
                  <><Pause size={12} aria-hidden /> {t('coworking.memberships.stopRenewal')}</>
                ) : (
                  <><Play size={12} aria-hidden /> {t('coworking.memberships.resumeRenewal')}</>
                )}
              </Button>
            ) : null}
            {forceEnd ? (
              <Button size="sm" variant="ghost" onClick={() => setForceEndTarget(m)} disabled={busyId === m.id}>
                <X size={12} aria-hidden /> {t('coworking.memberships.forceEnd')}
              </Button>
            ) : null}
          </div>
        )
      ) },
  ];

  return (
    <div className="flex flex-col gap-2">
      {error ? <p className="text-danger text-sm">{error}</p> : null}
      <Table
        columns={columns}
        rows={isLoading(raw) ? 'loading' : hasFailed(raw) ? 'failed' : rows}
        getRowId={(m) => m.id}
        emptyTitle={t('coworking.memberships.empty.title')}
        emptyDescription={t('coworking.memberships.empty.description')}
        failedTitle={t('coworking.loadFailed.title')}
      />

      {forceEndTarget ? (
        <ForceEndDialog
          session={session} membership={forceEndTarget} resourceName={resourceNameById[forceEndTarget.resource_id] ?? ''}
          onClose={() => setForceEndTarget(null)}
          onDone={() => { setForceEndTarget(null); load(); }}
          actionId={forceEnd!} t={t}
        />
      ) : null}
    </div>
  );
}

/** THE EXPLICIT ACKNOWLEDGMENT DIALOG — never a plain `ConfirmDialog`. services/coworking's own
 * `core/memberships.py::force_end` module doc is explicit about why: real money may already have
 * changed hands between the shop and the member for days neither will use, and "I never agreed to
 * leave early" is a real dispute this screen exists to make impossible. The backend REFUSES the
 * call outright without `acknowledged: true` — this dialog is simply the UI that makes typing
 * that acknowledgment a real, deliberate act (a checkbox the owner must tick himself, not a
 * pre-ticked default) rather than a second "are you sure?" click indistinguishable from any
 * other confirm dialog on this screen. */
function ForceEndDialog({
  session, membership, resourceName, onClose, onDone, actionId, t,
}: {
  session: Session; membership: MembershipRow; resourceName: string; onClose: () => void;
  onDone: () => void; actionId: ReturnType<typeof action>; t: (key: string) => string;
}) {
  const [acknowledged, setAcknowledged] = useState(false);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const submit = async () => {
    if (!actionId || !acknowledged) return;
    setBusy(true); setError('');
    try {
      await call(session, actionId, {
        membership_id: membership.id, acknowledged: true, note: note.trim(),
      });
      onDone();
    } catch (e) {
      setError(sentenceFor(e, t('coworking.memberships.forceEndFailed'), t));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open onClose={onClose} title={t('coworking.memberships.forceEnd')}
      footer={(
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>{t('coworking.resources.cancel')}</Button>
          <Button variant="danger" onClick={submit} disabled={busy || !acknowledged}>
            {t('coworking.memberships.forceEndConfirm')}
          </Button>
        </>
      )}>
      <div className="flex flex-col gap-3">
        {error ? <p className="text-danger text-sm">{error}</p> : null}
        <p className="text-sm text-text-secondary">
          {tf(t, 'coworking.memberships.forceEndIntro', {
            phone: membership.freelancer_phone, resource: resourceName,
          })}
        </p>
        <div className="rounded-card border border-warning/30 bg-warning-soft p-3 text-xs text-warning-on-soft">
          {t('coworking.memberships.forceEndWarning')}
        </div>
        <Field label={t('coworking.memberships.forceEndNote')}>
          <Textarea value={note} onChange={(e) => setNote(e.target.value)} rows={3}
            placeholder={t('coworking.memberships.forceEndNotePlaceholder')} />
        </Field>
        <label className="flex cursor-pointer items-start gap-2 rounded-lg border border-border-strong p-3 text-sm">
          <input type="checkbox" className="mt-0.5" checked={acknowledged}
            onChange={(e) => setAcknowledged(e.target.checked)} />
          <span>{t('coworking.memberships.forceEndAck')}</span>
        </label>
      </div>
    </Modal>
  );
}
