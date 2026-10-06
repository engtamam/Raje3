/**
 * «الاستضافة المهنية» — a shop's own bookable resources (rooms/desks rented to freelancers by the
 * hour), and everything an owner does to run that side of the shop: the resources themselves
 * (photo, description, price, weekly availability), who may book them at all (join requests, a
 * shop-wide approval gate), and the bookings that result.
 *
 * THREE TABS, THREE DIFFERENT SCOPES, ON PURPOSE — matching services/coworking's own
 * `api/v1/admin.py` module doc exactly:
 *
 *   الموارد     — branch-scoped (a resource belongs to one branch, or to none = every branch)
 *   طلبات الانضمام — SHOP-WIDE, NEVER BRANCH-SCOPED (core/joins.py: a freelancer approved once
 *                    may book any resource at that shop; branch-scoping this gate would be a real
 *                    behaviour change nobody asked for)
 *   الحجوزات    — branch-scoped, filtered by the SAME `branch` this whole console is looking at
 *
 * GATED BY CAPABILITY ALONE, NOT BY THE APP STORE — same posture Services.tsx already holds
 * (`apps.ts` has no APP_ROW for coworking; every control below is `action(catalog, id) ? … : null`,
 * the same idiom `Can.tsx`'s own header describes). nav.ts's own `requires: ['coworking.list_resources']`
 * is the section-level gate; this file is the finer, per-button one.
 */
import { useEffect, useMemo, useState } from 'react';
import {
  Briefcase, Building2, Calendar1, Check, CircleSlash2, Copy, Image as ImageIcon, Layers, Plus,
  Users,
} from 'lucide-react';
import { PageHeader } from '../rj-ui/PageHeader';
import { Segmented } from '../rj-ui/Segmented';
import { Card } from '../rj-ui/Card';
import { Badge } from '../rj-ui/Badge';
import { Button } from '../rj-ui/Button';
import { Toggle } from '../rj-ui/Toggle';
import { Modal } from '../rj-ui/Modal';
import { ConfirmDialog } from '../rj-ui/ConfirmDialog';
import { EmptyState } from '../rj-ui/EmptyState';
import { Waiting } from '../Waiting';
import { action, call, downloadUrl, type Catalog } from '../catalog';
import { sentenceFor } from '../api';
import { hasFailed, isLoading, isReady } from '../loading';
import type { Session } from '../session';
import { useOperatorI18n, tf } from '../operator-i18n';
import './coworking-i18n';

// ── shapes, straight off services/coworking's own `core/models.py::Resource.public()` and
// `api/v1/admin.py` — never invented, always what the route actually returns/accepts. ─────────
interface Resource {
  id: string;
  name: string;
  branch_id: string;
  description?: string;
  active?: boolean;
  has_image?: boolean;
  hourly_price_minor?: number;
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

function formatWhen(epochSeconds?: number): string {
  if (!epochSeconds) return '';
  return new Date(epochSeconds * 1000).toLocaleString();
}

// THE REAL, DEPLOYED GATEWAY ORIGIN (vite.config.ts's own `define`, off `config/product.json`'s
// `urls.app`) — never a hardcoded domain a rebrand would silently miss.
declare const __PUBLIC_APP_ORIGIN__: string;

type Tab = 'resources' | 'joins' | 'bookings';

// THREE REAL COLOUR IDENTITIES, ONE PER TAB — the owner's own request for "تمايز لوني عالي"
// (high colour differentiation): الموارد (what you own) reads accent/violet, طلبات الانضمام (a
// pending decision) reads warning/amber, الحجوزات (a settled fact) reads info/teal. Same "colour
// before number" precedent Shop.tsx's own Tile and referrals_screen.dart's own reward bands
// already set — applied here to each tab's own section header and card accents, never the
// Segmented control itself (rj-ui/Segmented.tsx has no per-option colour slot by design).
const TAB_ACCENT: Record<Tab, { tone: 'accent' | 'warning' | 'info'; soft: string; onSoft: string; ring: string }> = {
  resources: { tone: 'accent', soft: 'bg-accent-soft', onSoft: 'text-accent-on-soft', ring: 'ring-accent/30' },
  joins: { tone: 'warning', soft: 'bg-warning-soft', onSoft: 'text-warning-on-soft', ring: 'ring-warning/30' },
  bookings: { tone: 'info', soft: 'bg-info-soft', onSoft: 'text-info-on-soft', ring: 'ring-info/30' },
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

export function CoworkingScreen({
  session, catalog, branch,
}: { session: Session; catalog: Catalog; branch: string }) {
  const { t } = useOperatorI18n();
  const [tab, setTab] = useState<Tab>('resources');

  const [resources, setResources] = useState<Resource[] | null | undefined>(undefined);
  const [joins, setJoins] = useState<JoinRow[] | null | undefined>(undefined);
  const [bookings, setBookings] = useState<BookingRow[] | null | undefined>(undefined);
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

  // A BOOKING ROW ONLY EVER HOLDS `resource_id` (core/bookings.py's own stored dict) — never a raw
  // id shown to an owner, who has no reason to recognise a UUID; the full (unfiltered) resource
  // list is always available here regardless of which tab is open, so this is a plain lookup, not
  // a second fetch.
  const resourceNameById = useMemo(() => {
    const out: Record<string, string> = {};
    if (isReady(resources)) for (const r of resources) out[r.id] = r.name;
    return out;
  }, [resources]);

  const pendingJoinsCount = isReady(joins) ? joins.filter((j) => j.status === 'pending').length : 0;

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
        ]}
      />
    </>
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
    <div className="flex flex-col gap-3 p-4">
      {switcher}
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
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [openId, setOpenId] = useState<string | null>(null);

  const create = action(catalog, 'coworking.create_resource');
  const update = action(catalog, 'coworking.update_resource');

  const addResource = async () => {
    if (!create || !name.trim()) return;
    setSaving(true); setError('');
    try {
      await call(session, create, { name: name.trim(), branch_id: branch, description: description.trim() });
      setAdding(false); setName(''); setDescription('');
      load();
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

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
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
            <input autoFocus value={name} onChange={(e) => setName(e.target.value)}
              placeholder={t('coworking.resources.namePlaceholder')}
              className="h-10 rounded-lg bg-surface-2 px-3" />
            <textarea value={description} onChange={(e) => setDescription(e.target.value)}
              placeholder={t('coworking.resources.descriptionPlaceholder')}
              className="min-h-20 rounded-lg bg-surface-2 px-3 py-2 text-sm" />
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
  const price = typeof r.hourly_price_minor === 'number' && r.hourly_price_minor > 0
    ? tf(t, 'coworking.resources.pricePerHour', { price: (r.hourly_price_minor / 100).toFixed(2) })
    : t('coworking.resources.noPrice');

  return (
    <Card interactive onClick={onOpen}
      className={`flex flex-col gap-2 overflow-hidden p-0 ${active ? 'ring-1 ring-accent/20' : 'opacity-80'}`}>
      {/* A REAL ACCENT STRIP, NOT ANOTHER FLAT GREY TOP — echoes الموارد's own violet identity
          (`TAB_ACCENT.resources`) on every card, active or not; a paused resource dims instead of
          losing the strip entirely, so the shelf still reads as "one product family". */}
      <div className={`h-1 w-full ${active ? 'bg-accent' : 'bg-border-subtle'}`} />
      <div className="flex h-32 items-center justify-center bg-surface-2">
        {imageUrl ? (
          <img src={imageUrl} alt={r.name} className="h-full w-full object-cover" />
        ) : (
          <ImageIcon size={28} className="text-text-muted" aria-hidden />
        )}
      </div>
      <div className="flex flex-col gap-1.5 p-3">
        <div className="flex items-center justify-between gap-2">
          <p className="truncate text-sm font-semibold">{r.name}</p>
          <Badge tone={active ? 'success' : 'neutral'}>
            {active ? t('coworking.resources.active') : t('coworking.resources.paused')}
          </Badge>
        </div>
        {!r.branch_id ? (
          <Badge tone="info" className="self-start">{t('coworking.resources.branch.unassigned')}</Badge>
        ) : null}
        {r.description ? <p className="line-clamp-1 text-xs text-text-secondary">{r.description}</p> : null}
        <p className="text-xs text-text-muted">{price}</p>
        <div className="mt-1 flex gap-2">
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

  const update = action(catalog, 'coworking.update_resource');
  const setAvailability = action(catalog, 'coworking.set_availability');
  const uploadImage = action(catalog, 'coworking.upload_resource_image');

  if (!resource) return null;

  const saveDetails = async () => {
    if (!update) return;
    setSaving(true); setError('');
    try {
      await call(session, update, {
        resource_id: resource.id, name: name.trim() || resource.name,
        description: description.trim(),
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
    <Modal open onClose={onClose} title={resource.name} size="lg"
      footer={(
        <>
          <Button variant="ghost" onClick={onClose}>{t('coworking.resources.cancel')}</Button>
          <Button onClick={saveDetails} disabled={saving}>{t('coworking.resources.save')}</Button>
        </>
      )}>
      <div className="flex flex-col gap-5">
        {error ? <p className="text-danger text-sm">{error}</p> : null}

        <div className="flex flex-col gap-2">
          <input value={name} onChange={(e) => setName(e.target.value)}
            placeholder={t('coworking.resources.namePlaceholder')}
            className="h-10 rounded-lg bg-surface-2 px-3" />
          <textarea value={description} onChange={(e) => setDescription(e.target.value)}
            placeholder={t('coworking.resources.descriptionPlaceholder')}
            className="min-h-16 rounded-lg bg-surface-2 px-3 py-2 text-sm" />
        </div>

        {uploadImage ? (
          <div className="flex flex-col gap-1.5">
            <span className="text-label font-medium text-text-secondary">{t('coworking.resources.photo')}</span>
            <label className="inline-flex w-fit cursor-pointer items-center gap-2 rounded-lg border
                               border-dashed border-border-subtle px-3 py-2 text-sm">
              <ImageIcon size={14} aria-hidden />
              {uploading ? t('coworking.loading') : t('coworking.resources.uploadPhoto')}
              <input type="file" accept="image/*" className="hidden" disabled={uploading}
                onChange={(e) => { const f = e.target.files?.[0]; if (f) void onPickImage(f); }} />
            </label>
          </div>
        ) : null}

        {setAvailability ? (
          <div className="flex flex-col gap-3 border-t border-border-subtle pt-4">
            <div>
              <p className="text-sm font-semibold">{t('coworking.resources.availability')}</p>
              <p className="text-xs text-text-secondary">{t('coworking.resources.availabilityHint')}</p>
            </div>

            <label className="flex flex-col gap-1 text-xs">
              {t('coworking.resources.hourlyPrice')}
              <input type="number" min={0} value={price} onChange={(e) => setPrice(e.target.value)}
                className="h-9 w-40 rounded-lg bg-surface-2 px-3 text-sm" />
            </label>

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
    </Modal>
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

  if (isLoading(raw)) return <Waiting what={t('coworking.loading')} />;
  if (hasFailed(raw)) {
    return (
      <EmptyState title={t('coworking.loadFailed.title')} description={t('coworking.loadFailed.description')}
        action={<Button onClick={load}>{t('coworking.retry')}</Button>} />
    );
  }
  if (bookings.length === 0) {
    return <EmptyState title={t('coworking.bookings.empty.title')} description={t('coworking.bookings.empty.description')} />;
  }

  const toneFor = (status?: string) => status === 'cancelled' ? 'neutral' : status === 'completed' ? 'info' : 'success';

  return (
    <div className="flex flex-col gap-2">
      {error ? <p className="text-danger text-sm">{error}</p> : null}
      <div className="overflow-x-auto rounded-card border border-border-subtle">
        <table className="w-full text-sm">
          <thead className="bg-surface-2 text-xs text-text-secondary">
            <tr>
              <th className="p-2 text-start">{t('coworking.bookings.resource')}</th>
              <th className="p-2 text-start">{t('coworking.bookings.phone')}</th>
              <th className="p-2 text-start">{t('coworking.bookings.when')}</th>
              <th className="p-2 text-start">{t('coworking.bookings.status')}</th>
              <th className="p-2" />
            </tr>
          </thead>
          <tbody>
            {bookings.map((b) => (
              <tr key={b.id} className="border-t border-border-subtle">
                <td className="p-2">{resourceNameById[b.resource_id] ?? b.resource_id}</td>
                <td className="p-2 font-mono">{b.freelancer_phone ?? ''}</td>
                <td className="p-2">{formatWhen(b.starts_at)}{b.ends_at ? ` – ${formatWhen(b.ends_at)}` : ''}</td>
                <td className="p-2">
                  <Badge tone={toneFor(b.status)}>
                    {b.status ? (t(`coworking.bookings.status.${b.status}`) || b.status) : ''}
                  </Badge>
                </td>
                <td className="p-2">
                  {cancel && b.status !== 'cancelled' ? (
                    <Button size="sm" variant="ghost" onClick={() => setConfirmId(b.id)} disabled={busy}>
                      {t('coworking.bookings.cancel')}
                    </Button>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

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
