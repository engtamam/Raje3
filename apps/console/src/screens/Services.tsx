/**
 * «خدماتي» — what I sell, and when I remind about it.
 *
 * TWO STORES BEHIND ONE FORM, AND GETTING IT WRONG RECREATES A FIXED BUG.
 *
 *   name, price, order        → operations (the Service row)
 *   cycle, lead, follow-up    → REMINDERS' settings tree
 *
 * The engine reads the TREE. A screen that wrote operations' `cycle_days` column instead would
 * reproduce exactly what the tree was introduced to fix: the owner changes a cycle, sees no effect,
 * and concludes the feature is broken. The two writes are deliberately separate calls here rather
 * than hidden behind one helper, so the next person reading this cannot lose the distinction.
 *
 * AND THE CUSTOMISATION IS SHOWN WHERE IT HAPPENED (§10.8.1). A service the owner edited says so,
 * on itself, with one tap back to the general setting — never in a distant settings screen he
 * would have to find. Inheritance, not copying: a service either FOLLOWS the general value or
 * holds its own, which is why "return to general" is a DELETE and not a write of today's default.
 */
import { Fragment, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Button } from '../rj-ui/Button';
import { Badge } from '../rj-ui/Badge';
import { Segmented } from '../rj-ui/Segmented';
import { EmptyState } from '../rj-ui/EmptyState';
import { PageHeader } from '../rj-ui/PageHeader';
import { Check, ImageOff, LayoutGrid, List, Pencil, Power, RotateCcw, Upload, Wrench, X } from 'lucide-react';
import { Hint } from '../Hint';
import { AssistantHint } from '../AssistantHint';
import { Toggle } from '../rj-ui/Toggle';
import { FilterMenu } from '../rj-ui/FilterMenu';
import { hasFailed, isLoading } from '../loading';
import { Waiting } from '../Waiting';
import { action, call, downloadUrl, type Catalog } from '../catalog';
import { halalas, riyals } from '../money';
import type { Session } from '../session';
import { useOperatorI18n, tf } from '../operator-i18n';
import './services-i18n';
import { ServicesImportDrawer } from './ServicesImportDrawer';
import { PackagesTab } from './PackagesTab';

interface Service {
  id: string; name: string; cycle_days: number; price_minor: number;
  // DEFAULTS TO 0 = «NOT CONFIGURED», not «free» and not «instant» — bookings refuses to create a
  // slot for a service carrying this, by design (see BookingDialog's own missingDuration check).
  // Editable here for the first time; the field itself was already read by bookings and never
  // writable anywhere in the console — a service could only ever get a real duration by seed.
  duration_minutes?: number;
  catchall?: boolean; active?: boolean;
  /** WHO CAN ACTUALLY DO IT. Absent/empty = every active operator (the zero-config default — a
   *  single-operator shop, or one where everybody does everything, never touches this). A real
   *  list narrows it to those specific people. */
  eligible_staff_ids?: string[];
  /** A short owner-written line — the WhatsApp assistant's only source for "what does this
   *  service actually involve" (services-images-board.md phase 1). */
  description?: string;
  /** NEVER the image itself, NEVER a key — just whether one exists. The real bytes are fetched
   *  through their own gated route (operations.get_service_image), same "never leak an internal
   *  reference" discipline the rest of this product already holds. */
  has_image?: boolean;
}

/** Just enough of an operator to list him as a candidate — same shape Team.tsx reads. */
interface StaffMember { id: string; name: string; active?: boolean }

/** One service's entry in the tree, and whether it is its own or inherited. */
interface ServiceSetting { interval_days?: number; lead_days?: number; follow_up_days?: number; enabled?: boolean }
/** What may be written at the general level, and nowhere else. */
type GeneralPatch = ServiceSetting;
interface Settings {
  general: ServiceSetting;
  /** Only what a service OVERRIDES. Absent means it follows — following is not a value. */
  services: Record<string, ServiceSetting>;
  /** Group name → its settings, and service id → its group. Two maps, exactly as the tree holds
   *  them, so a service moving between groups stays one write rather than two. */
  groups: Record<string, ServiceSetting>;
  service_group: Record<string, string>;
}

/** One row of «رسائلي التلقائية» — this screen reads only the visit confirmation from it. */
interface ReasonRow { id: string; on: boolean }

/** The one proposal this screen ever makes: several services already share a value. */
interface Suggestion { field: string; value: number | boolean; services: string[] }

/** Services with no group, gathered under one heading rather than left looking unfiled. */
const UNGROUPED = '';

/**
 * The one line under a service name, and it reports EVERYTHING that service is set to do.
 *
 * Two messages can be scheduled off one visit and they are not the same message. The cycle is the
 * one that brings him back — «حان وقت غيار الزيت» — and it is timed to when the need returns. The
 * follow-up asks whether the last visit went well, and is timed to a few days after it. An owner
 * reading this line is deciding whether to open the row, so it has to say which of the two are on.
 */
function summarise(t: (key: string) => string, v: ServiceSetting): string {
  const parts: string[] = [];
  if (v.interval_days) parts.push(tf(t, 'services.summary.interval', { n: v.interval_days }));
  if (v.follow_up_days) parts.push(tf(t, 'services.summary.followUp', { n: v.follow_up_days }));
  // NOT «بلا دورة» WHEN A FOLLOW-UP EXISTS. A service with no cycle but a follow-up is a perfectly
  // ordinary thing — a one-off job you still check on — and the old line called it silent.
  return parts.length ? parts.join(' · ') : t('services.summary.none');
}

/** loyalty's settings tree, in the shape it answers with: a number per level, and where it came from. */
interface EarnSettings {
  general?: { points?: number };
  /** THE PLATFORM'S OWN DEFAULT — the fourth level, and the one this screen used to miss. The
   *  visit grid showed «+10» on every tile while this table showed «—» beside every service,
   *  because the engine resolves service → group → general → defaults and the table stopped one
   *  short. Two screens disagreeing about the same number is worse than either being wrong. */
  defaults?: { points?: number };
  groups?: Record<string, { points?: number }>;
  services?: Record<string, { points?: number }>;
  service_group?: Record<string, string>;
}

/** «الخدمات» (this screen's original body) / «الباقات» (PackagesTab.tsx) — two tabs, one route.
 *  `?tab=packages` is how محلّي's «باقات مقترحة» card and «أضفها لهذه الباقة» button (Shop.tsx)
 *  land here already on the right tab, carrying their own prefill params that PackagesTab reads
 *  and clears itself. */
type ServicesPageTab = 'services' | 'packages';

export function ServicesScreen({ session, catalog }: { session: Session; catalog: Catalog }) {
  const { t } = useOperatorI18n();
  const [params, setParams] = useSearchParams();
  const tab: ServicesPageTab = params.get('tab') === 'packages' ? 'packages' : 'services';
  const setTab = (next: ServicesPageTab) => {
    const p = new URLSearchParams(params);
    if (next === 'services') p.delete('tab'); else p.set('tab', next);
    setParams(p, { replace: true });
  };
  const packagesEnabled = !!action(catalog, 'operations.list_packages');
  const [services, setServices] = useState<Service[] | null | undefined>(undefined);
  /** The list could not be READ — as opposed to being read and found empty. Two different facts,
   *  and this screen used to say the same sentence for both. */
  const [unread, setUnread] = useState(false);
  const [settings, setSettings] = useState<Settings | null | undefined>(undefined);
  const [open, setOpen] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [suggestion, setSuggestion] = useState<Suggestion | null | undefined>(undefined);
  /** The name box, shown only after he asks for the group — never as a field waiting to be filled. */
  const [naming, setNaming] = useState<string | null>(null);
  /**
   * THE POINTS EACH SERVICE EARNS — read here so the shortcut can show the INHERITED number too.
   *
   * Without it the field would render 0 for every service that simply follows the general rule,
   * and an owner reading a zero next to a service that does earn points would type the number
   * again — turning "follows the general setting" into a frozen copy that stops tracking it (§9.2).
   */
  const [earn, setEarn] = useState<EarnSettings | null | undefined>(undefined);
  /**
   * WHICH GROUP THE WORKSPACE IS SHOWING. `null` means all of them.
   *
   * A shop with a long menu opens this screen every week, and scrolling past four headings to
   * reach the fifth is the tax it paid for having organised itself. The rail turns the structure
   * he built into navigation instead of scenery.
   */
  const [only, setOnly] = useState<string | null>(null);
  /** The add-a-service form, shown only when he asks for it. */
  const [adding, setAdding] = useState(false);
  /** A photo picked on the CREATE form, held only in the browser until «إضافة» is actually
   *  pressed — there is no server-side draft for it, because there is nowhere to attach one to
   *  before a service id exists. Confirm uploads it against the id create_service just returned;
   *  cancel (or closing the form) drops this state and the file is never sent at all — the same
   *  "temporary, only real if confirmed" behaviour a server-side draft would give, achieved by
   *  simply not touching the network until the id exists. */
  const [pendingImage, setPendingImage] = useState<File | null>(null);
  /** The file-import drawer (ServicesImportDrawer.tsx), same "shown only when asked" idiom. */
  const [importing, setImporting] = useState(false);
  /**
   * WHICH ONES ARE ON SCREEN — and it opens on «المفعّلة», which is the answer he wants nine
   * visits out of ten.
   *
   * Retired lines have to be REACHABLE or «تفعيل» acts on nothing (the bug that sent us to build
   * the owner's list in the first place). But reachable is not the same as always present: a shop
   * that has been open two years accumulates lines it stopped selling, and mixing them into the
   * working list makes every ordinary edit a matter of reading past the dead ones. Default to what
   * he sells, one tap to what he stopped, one tap to everything.
   */
  const [show, setShow] = useState<'active' | 'stopped'>('active');
  /**
   * WHICH COLUMN'S EXPLANATION IS OPEN — held here, and shown ABOVE the table.
   *
   * The «؟» used to open its sentence inside its own `<th>`. A header cell is sixty-four pixels
   * wide, so the paragraph rendered one word per line and pushed the whole header taller than the
   * rows under it: the answer was technically on screen and unreadable. A table cell is the wrong
   * container for prose, and no amount of styling fixes that — the text belongs to the width of
   * the table, not to the width of one column.
   */
  const [asked, setAsked] = useState<string | null>(null);
  // WHO EXISTS AT ALL — read only so the eligibility row can be shown/hidden and its checkboxes
  // labelled. A shop with one operator (or none of this screen's role) never reads this at all
  // in any way that shows: the row below is hidden whenever there is one or fewer of them.
  const [staff, setStaff] = useState<StaffMember[] | null | undefined>(undefined);

  // ── board/cards view (services-images-board.md phase 3) ────────────────────────────────────
  // SAME DEFAULT-BY-INPUT-TYPE AS Bookings.tsx's OWN TOGGLE, read once at mount, never tracked
  // live — a touch device opens on cards, a mouse on the dense table, and rotating a tablet
  // mid-glance must not yank the layout out from under him.
  const [layout, setLayout] = useState<'list' | 'grid'>(() => (
    typeof window !== 'undefined' && typeof window.matchMedia === 'function'
      && window.matchMedia('(pointer: coarse)').matches
      ? 'grid' : 'list'
  ));
  // Object URLs, one per service that HAS a photo — fetched lazily (never for a service with no
  // photo at all) and revoked on unmount so a long session does not leak blob handles.
  const [images, setImages] = useState<Record<string, string>>({});
  useEffect(() => {
    const getAction = action(catalog, 'operations.get_service_image');
    if (!getAction || !services) return;
    let cancelled = false;
    for (const svc of services) {
      if (!svc.has_image || images[svc.id]) continue;
      downloadUrl(session, getAction, { id: svc.id }).then((url) => {
        if (!cancelled) setImages((m) => ({ ...m, [svc.id]: url }));
      }).catch(() => undefined);
    }
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [services, catalog]);
  useEffect(() => () => { Object.values(images).forEach((u) => URL.revokeObjectURL(u)); },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []);

  const load = () => {
    // THE OWNER'S LIST WHEN HE HAS IT, and it includes what he has retired. The field grid is
    // active-only and rightly so — an operator must not be offered a service the shop stopped —
    // but it was the only list there was, so stopping a service made it vanish from the very
    // screen that stopped it, with «تفعيل» left acting on nothing.
    const mine = action(catalog, 'operations.manage_services');
    const list = mine ?? action(catalog, 'operations.list_services');
    if (list) {
      call<{ services: Service[] }>(session, list, mine ? { include_retired: true } : {})
        .then((x) => { setServices(x.services); setUnread(false); })
        // A FAILED READ IS NOT AN EMPTY SHOP. This used to set [], so a 401, a 503 or a dropped
        // connection all rendered «لا توجد خدمات» — the screen telling an owner with a full
        // catalogue that he sells nothing, in the same words it uses for a genuinely new shop.
        // He cannot tell those apart, and the wrong one costs him the trust the true one needs.
        .catch(() => { setServices(null); setUnread(true); });
    } else {
      setServices([]);
    }

    const s = action(catalog, 'reminders.get_settings');
    if (s) call<Settings>(session, s).then(setSettings).catch(() => setSettings(null));

    // A PROPOSAL, AND ITS ABSENCE IS THE NORMAL CASE. It reads null until the owner has repeated
    // himself across at least three services, which is the point: a shop on its first day is not
    // shown an organisational chore it has no reason for yet.
    const es = action(catalog, 'loyalty.settings.read');
    if (es) call<EarnSettings>(session, es).then(setEarn).catch(() => setEarn(null));

    const tg = action(catalog, 'reminders.reasons');
    if (tg) {
      call<{ reasons: ReasonRow[] }>(session, tg)
        .then((x) => applyReasons(x.reasons))
        // A FAILED READ LEAVES THE SWITCH AS IT WAS. Rendering it off would tell an owner his
        // confirmations are stopped because a request timed out.
        .catch(() => {});
    }

    const op = action(catalog, 'operations.list_operators');
    if (op) {
      call<{ operators: StaffMember[] }>(session, op)
        .then((x) => setStaff(x.operators ?? []))
        .catch(() => setStaff(null));
    } else {
      setStaff(null);
    }

    const sg = action(catalog, 'reminders.suggest_group');
    if (sg) {
      call<{ suggestion: Suggestion | null }>(session, sg)
        .then((x) => setSuggestion(x.suggestion))
        .catch(() => setSuggestion(null));
    }
  };

  useEffect(load, [session, catalog]);

  const earnAction = action(catalog, 'loyalty.settings.service');

  /** Its points, and whether that number is its own — the same three levels the engine resolves. */
  const earnFor = (id: string): { points: number; own: boolean } => {
    const own = earn?.services?.[id]?.points;
    if (own !== undefined) return { points: own, own: true };
    const group = earn?.service_group?.[id];
    const fromGroup = group ? earn?.groups?.[group]?.points : undefined;
    return {
      points: fromGroup ?? earn?.general?.points ?? earn?.defaults?.points ?? 0,
      own: false,
    };
  };

  const setServicePoints = async (serviceId: string, points: number) => {
    if (!earnAction) return;
    setSaving(true); setError('');
    try {
      await call(session, earnAction, { service_id: serviceId, points });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('services.error.pointsSaveFailed'));
    } finally {
      setSaving(false);
    }
  };

  /**
   * A service's effective reminder cycle, and whether that value is its own.
   *
   * THREE LEVELS, RESOLVED IN THE ORDER THE ENGINE RESOLVES THEM — service, then its group, then
   * general. Skipping the group here would show a number the engine does not use, which is the
   * exact complaint the settings tree exists to prevent: "I changed it and nothing happened."
   */
  const settingFor = (id: string): { value: ServiceSetting; own: boolean } => {
    const own = settings?.services?.[id];
    if (own) return { value: own, own: true };
    const group = settings?.service_group?.[id];
    const fromGroup = group ? settings?.groups?.[group] : undefined;
    return { value: fromGroup ?? settings?.general ?? {}, own: false };
  };

  /**
   * The screen's structure, taken from the system rather than invented.
   *
   * The tree has known groups since it was written; this screen listed twenty services flat and
   * showed none of it, so an owner who had already organised his shop was shown a wall — and
   * «خدماتي» is the one section a shop with a long menu opens every week.
   */
  const grouped = (list: Service[]): [string, Service[]][] => {
    const bins = new Map<string, Service[]>();
    for (const svc of list) {
      const key = settings?.service_group?.[svc.id] ?? UNGROUPED;
      bins.set(key, [...(bins.get(key) ?? []), svc]);
    }
    // NAMED GROUPS FIRST, ungrouped last: the ungrouped bin is a remainder, not a category, and
    // opening on it would bury the structure the owner built.
    return [...bins.entries()].sort((a, b) =>
      a[0] === UNGROUPED ? 1 : b[0] === UNGROUPED ? -1 : a[0].localeCompare(b[0], 'ar'));
  };

  /** Accept the proposal: one write, carrying the shared value and the services that share it. */
  const makeGroup = async (name: string) => {
    const a = action(catalog, 'reminders.set_group');
    if (!a || !suggestion || !name.trim()) return;
    setSaving(true);
    setError('');
    try {
      await call(session, a, {
        name: name.trim(),
        service_ids: suggestion.services,
        [suggestion.field]: suggestion.value,
      });
      setNaming(null);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('services.error.groupCreateFailed'));
    } finally {
      setSaving(false);
    }
  };

  /**
   * Put one service into a group, creating the group if it is new.
   *
   * NO VALUES SENT. `set_group` merges what it is given into the group's settings, so passing the
   * service's current numbers here would stamp one service's cycle onto every other member — the
   * opposite of what "put this in that group" means. Membership is the whole write; whatever the
   * group already decides is what this service now follows.
   */
  const joinGroup = async (serviceId: string, name: string) => {
    const a = action(catalog, 'reminders.set_group');
    if (!a || !name.trim()) return;
    setSaving(true);
    setError('');
    try {
      await call(session, a, { name: name.trim(), service_ids: [serviceId] });
      setNaming(null);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('services.error.moveToGroupFailed'));
    } finally {
      setSaving(false);
    }
  };

  /**
   * Adding, renaming and retiring a service — the acts the screen named nowhere.
   *
   * «خدماتي» could show the catalogue and set its reminder cycles, and offered no way to put a
   * service INTO it, correct a name, or stop selling something. The owner's words: «ماني شايف
   * أساساً مكان أضيف فيه خدمات أو أعدّل اسمها».
   *
   * RETIRED, NEVER DELETED — the service says why: deleting a service orphans every visit that
   * references it, and a shop that stopped offering something still needs last year's records to
   * make sense.
   */
  /**
   * A NEW SERVICE, WITH EVERY ANSWER IT NEEDS — not a name and one number.
   *
   * The form asked for the cycle alone, so every service arrived half-configured: no follow-up, no
   * points, no group. The owner had no way to know that; the form looked finished. He would add
   * «تلميع», walk away, and find out weeks later that it never asked his customer anything and
   * never earned a point — by which time the visits it should have counted are gone.
   *
   * FOUR SERVICES ANSWER THIS, IN THIS ORDER, AND THE FIRST ONE IS THE ONLY REQUIRED ONE.
   * operations owns the service, reminders owns its cycle and its follow-up and its group, loyalty
   * owns its points. So the row is created first and the rest are applied to the id it returns —
   * and any of them that his role cannot reach is simply not asked for on the form.
   *
   * A FAILURE AFTER THE FIRST STEP LEAVES A REAL SERVICE. That is deliberate: the service exists,
   * it is on the operator's grid, and the settings it is missing are all editable on the card he
   * is looking at. Rolling it back would delete something he successfully created because a
   * secondary setting timed out.
   */
  const addService = async (
    name: string,
    opts: { cycleDays: number; durationMinutes: number; priceMinor: number | null; followUpDays: number;
            points: number | null; group: string; description: string; image: File | null },
  ) => {
    const a = action(catalog, 'operations.create_service');
    if (!a || !name.trim()) return;
    setSaving(true);
    setError('');
    try {
      const created = await call<{ id?: string }>(
        session, a, {
          name: name.trim(), cycle_days: opts.cycleDays, duration_minutes: opts.durationMinutes,
          // OPTIONAL, NOT ZERO. `price_minor` defaults to 0 on the server when
          // omitted — the same "0 = not configured" reading duration already uses — so a blank box
          // sends nothing at all rather than sending a real 0 (which would read as "free").
          ...(opts.priceMinor !== null ? { price_minor: opts.priceMinor } : {}),
          // ALREADY ACCEPTED AT CREATE TIME (server default ""), unlike the image below — the row
          // itself carries this from the first moment, same field the table's own edit box writes.
          ...(opts.description.trim() ? { description: opts.description.trim() } : {}),
        });
      const id = created?.id ?? '';

      if (id) {
        const rem = action(catalog, 'reminders.set_service_settings');
        // THE CYCLE WENT WITH THE ROW ALREADY; the follow-up is reminders' and has to be said
        // separately. Zero means "do not ask after this service", which is a real answer and not
        // an unset field — so it is only sent when he typed something above zero.
        if (rem && opts.followUpDays > 0) {
          await call(session, rem, { service_id: id, follow_up_days: opts.followUpDays });
        }
        // NULL MEANS "follow the general rule" (§9.2: inherit, never copy). Writing today's
        // general number instead would freeze it, and the next change to the general setting
        // would skip this service without saying so.
        if (earnAction && opts.points !== null) {
          await call(session, earnAction, { service_id: id, points: opts.points });
        }
        const grp = action(catalog, 'reminders.set_group');
        if (grp && opts.group.trim()) {
          await call(session, grp, { name: opts.group.trim(), service_ids: [id] });
        }
        // THE HELD PHOTO GOES LAST, AGAINST THE REAL ID — the only moment it can go anywhere at
        // all. uploadServiceImage() does its own load()/error handling, so nothing further is
        // needed here beyond forgetting the held file either way (success or failure both leave
        // the form closing; a failed photo does not undo the service that was already created,
        // same "partial creation is fine, rest is editable after" posture as every field above).
        if (action(catalog, 'operations.upload_service_image') && opts.image) {
          await uploadServiceImage(id, opts.image);
        }
      }

      setPendingImage(null);
      setAdding(false);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('services.error.addFailed'));
    } finally {
      setSaving(false);
    }
  };

  const patchService = async (id: string, patch: Record<string, unknown>) => {
    const a = action(catalog, 'operations.update_service');
    if (!a) return;
    setSaving(true);
    setError('');
    try {
      await call(session, a, { id, ...patch });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('services.error.editSaveFailed'));
    } finally {
      setSaving(false);
    }
  };

  /** A picked file, read as base64 and sent as-is — the server (catalogue_image.py) is the one
   *  place that validates type/size, matching AccountPanes.tsx's own "the server decides" posture
   *  for a write this small; no client-side resize needed for a product photo (unlike the shop
   *  logo, which is inlined directly and so had to be shrunk by hand). */
  const uploadServiceImage = async (id: string, file: File) => {
    const a = action(catalog, 'operations.upload_service_image');
    if (!a) return;
    setSaving(true);
    setError('');
    try {
      const data_base64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result).split(',')[1] ?? '');
        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(file);
      });
      await call(session, a, { id, content_type: file.type, data_base64 });
      setImages((m) => { const n = { ...m }; delete n[id]; return n; });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('services.error.editSaveFailed'));
    } finally {
      setSaving(false);
    }
  };

  const deleteServiceImage = async (id: string) => {
    const a = action(catalog, 'operations.delete_service_image');
    if (!a) return;
    setSaving(true);
    setError('');
    try {
      await call(session, a, { id });
      setImages((m) => { const n = { ...m }; delete n[id]; return n; });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('services.error.editSaveFailed'));
    } finally {
      setSaving(false);
    }
  };

  /**
   * Toggle one operator's eligibility for one service.
   *
   * NEVER STORES "EVERYONE, NAMED" — the moment the resulting set covers every active operator, it
   * is written back as `[]` rather than the full list. `[]` and "everyone by name" read the same
   * today, but only `[]` still means that the day a new operator is hired — a named list would
   * silently exclude him from a service nobody meant to restrict.
   */
  const toggleEligible = async (svc: Service, operatorId: string) => {
    const activeIds = (staff ?? []).filter((s) => s.active !== false).map((s) => s.id);
    // «كل الموظفين» — لا قيد بعد
    const current = svc.eligible_staff_ids && svc.eligible_staff_ids.length > 0
      ? new Set(svc.eligible_staff_ids)
      : new Set(activeIds);
    if (current.has(operatorId)) current.delete(operatorId); else current.add(operatorId);
    const eligible_staff_ids = activeIds.every((id) => current.has(id)) ? [] : [...current];
    await patchService(svc.id, { eligible_staff_ids });
  };

  /** Which operator ids `svc` is currently eligible for — unrestricted reads as everyone active. */
  const eligibleIdsFor = (svc: Service): string[] => {
    const activeIds = (staff ?? []).filter((s) => s.active !== false).map((s) => s.id);
    return svc.eligible_staff_ids && svc.eligible_staff_ids.length > 0
      ? svc.eligible_staff_ids.filter((id) => activeIds.includes(id))
      : activeIds;
  };

  /** FilterMenu only ever hands back "the new full selection" — the actual write is one
   *  operator's toggle, found by diffing against what was selected a moment ago. */
  const onEligibleChange = (svc: Service, next: string[]) => {
    const before = eligibleIdsFor(svc);
    const changedId = next.find((id) => !before.includes(id))
      ?? before.find((id) => !next.includes(id));
    if (changedId) toggleEligible(svc, changedId);
  };

  /** Take a service out of its group; it goes back to following the general setting. */
  const leaveGroup = async (serviceId: string) => {
    const name = settings?.service_group?.[serviceId];
    if (!name) return;
    const a = action(catalog, 'reminders.leave_group');
    if (!a) {
      // NOT A SILENT NO-OP. The catalogue is cached per token for the session, so a browser open
      // since before this action existed simply does not have it — and returning quietly made the
      // dropdown look broken. Say the one thing that fixes it.
      setError(t('services.error.actionNeedsRefresh'));
      return;
    }
    setSaving(true);
    setError('');
    try {
      await call(session, a, { name, service_id: serviceId });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('services.error.leaveGroupFailed'));
    } finally {
      setSaving(false);
    }
  };

  /**
   * Delete a group. Its services stay exactly where they are, without a group.
   *
   * ASKED FIRST, because it changes every member at once — and unlike the per-service controls
   * there is no single row whose line reports what happened.
   */
  const deleteGroup = async (name: string) => {
    const a = action(catalog, 'reminders.delete_group');
    if (!a) return;
    if (!window.confirm(tf(t, 'services.confirmDeleteGroup', { name }))) return;
    setSaving(true);
    setError('');
    try {
      await call(session, a, { name });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('services.error.deleteGroupFailed'));
    } finally {
      setSaving(false);
    }
  };

  /**
   * THE GENERAL SETTING — the value every service that has not been customised follows.
   *
   * IT COULD NOT BE SET FROM ANYWHERE. The screen offered per-service numbers and «العودة إلى
   * العام», so «العام» was a value an owner could return to and never choose: the only way to
   * change what his whole catalogue does was to open sixteen services and type the same number
   * sixteen times. `reminders.set_general` existed, declared and served, and no screen called it.
   *
   * IT LEAVES CUSTOMISATIONS ALONE, and the route says so: an owner who spent a minute setting the
   * oil change to 60 days has not asked us to undo that minute.
   */
  /**
   * «تأكيد الزيارة» — the one reason this screen owns.
   *
   * IT IS THE TRIGGER STORE, NOT THE SETTINGS TREE. The behaviour has exactly one switch and one
   * home; the twelve others live in «رسائلي», and this one is repeated here because this is the
   * screen where an owner asks what happens after a visit.
   */
  const [visitOn, setVisitOn] = useState(true);

  const applyReasons = (rows?: ReasonRow[]) => {
    const row = (rows || []).find((r) => r.id === 'visit_recorded');
    if (row) setVisitOn(row.on !== false);
  };

  const setVisitConfirmation = async (on: boolean) => {
    const a = action(catalog, 'reminders.set_reason');
    if (!a) return;
    setSaving(true); setError('');
    // OPTIMISTIC, AND CORRECTED BY THE ANSWER. A toggle that waits for a round trip before it
    // moves reads as broken on a phone.
    setVisitOn(on);
    try {
      const out = await call<{ ok?: boolean; error?: string; reasons?: ReasonRow[] }>(
        session, a, { reason_id: 'visit_recorded', on });
      if (out?.error) { setError(out.error); }
      applyReasons(out?.reasons);
    } catch (e) {
      setVisitOn(!on);
      setError(e instanceof Error ? e.message : t('services.error.visitSettingFailed'));
    } finally {
      setSaving(false);
    }
  };

  const setGeneral = async (patch: GeneralPatch) => {
    const a = action(catalog, 'reminders.set_general');
    if (!a) return;
    setSaving(true); setError('');
    try {
      await call(session, a, { ...patch });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('services.error.generalSettingFailed'));
    } finally {
      setSaving(false);
    }
  };

  const setService = async (id: string, patch: ServiceSetting) => {
    const a = action(catalog, 'reminders.set_service_settings');
    if (!a) return;
    setSaving(true);
    setError('');
    try {
      await call(session, a, { service_id: id, ...patch });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('services.error.saveFailed'));
    } finally {
      setSaving(false);
    }
  };

  const followGeneral = async (id: string) => {
    const a = action(catalog, 'reminders.follow_general');
    if (!a) return;
    setSaving(true);
    try {
      await call(session, a, { service_id: id });
      load();
    } finally {
      setSaving(false);
    }
  };

  // THE TITLE, AND THE TAB SWITCHER — shown above every state below it (loading, failed, empty,
  // and the full page), so switching to «الباقات» never depends on «الخدمات» having finished
  // loading first. The switcher itself is hidden entirely for a role that cannot see packages at
  // all, same "don't show a control that does nothing" rule the whole console follows — the
  // title stays regardless, same as every other screen's own PageHeader.
  const switcher = (
    <>
      <PageHeader icon={Wrench} title={t('services.title')} />
      {packagesEnabled ? (
        <Segmented
          // FULL WIDTH, SPLIT EVENLY — same top-level-switcher convention as Points.tsx/Messages.tsx's
          // own tab bars, not the default hug-content sizing (that default is for a nested filter row,
          // never for the two primary sections of this whole screen).
          className="flex w-full [&>button]:flex-1 [&>button]:whitespace-nowrap"
          ariaLabel={t('services.tabSwitcherAriaLabel')}
          value={tab}
          onChange={(v) => setTab(v as ServicesPageTab)}
          options={[
            { value: 'services', label: t('services.title') },
            { value: 'packages', label: t('services.packagesTab') },
          ]}
        />
      ) : null}
    </>
  );

  // «الباقات» IS ITS OWN SELF-CONTAINED SUB-COMPONENT — it does not depend on `services`/
  // `settings` having loaded here at all, so it renders regardless of this screen's own guards
  // below (which are all about the SERVICES tab's own data).
  if (tab === 'packages') {
    return (
      <div className="flex flex-col gap-3 p-4">
        {switcher}
        <PackagesTab session={session} catalog={catalog} />
      </div>
    );
  }

  // A PAGE WITH NO KNOWN SHAPE YET WAITS IN OUR OWN MARK, not as one grey rectangle —
  // see Waiting.tsx. The skeletons inside the page stay: there the shape IS known.
  // «NOT YET» IS NOT «IT FAILED» (م · النمط 1). This guard read `=== null` and the failure
  // handler set `null` too, so a failed read waited here for ever and the `unread` sentence below
  // — which was written for exactly this — could never be reached.
  if (isLoading(services)) return (
    <div className="flex flex-col gap-3 p-4">{switcher}<Waiting what={t('services.loading')} /></div>
  );

  // TWO DIFFERENT EMPTIES, AND THEY MUST NOT SHARE A SENTENCE. «We could not read your services»
  // is about us; «you have not added any yet» is about his shop — and until now both arrived here
  // as one branch, because a catalogue was seeded from his trade at sign-up and an empty list
  // could only mean the seeding had failed.
  //
  // NOTHING IS SEEDED NOW. A list guessed from a trade we have never seen was wrong on its first
  // day for any shop that does two things, so a new shop starts empty and its owner writes what he
  // actually sells. Empty is therefore the true first state of the product, and this screen has to
  // invite rather than apologise.
  if (hasFailed(services) || unread) {
    return (
      <div className="flex flex-col gap-3 p-4">
        {switcher}
        <EmptyState
          title={t('services.loadFailed.title')}
          description={t('services.loadFailed.description')}
          action={<Button onClick={load}>{t('services.retry')}</Button>}
        />
      </div>
    );
  }

  // `&& !adding` — WITHOUT IT THIS WAS A DEAD END. The button and form that actually create a
  // service live in the render below, past this guard; a shop with zero services never reached
  // them, so a brand-new account had literally no way to add its first one (a screenshot showed
  // an empty screen with no button anywhere). Falling through once he asks to add keeps this
  // exact branch the true first state of the product while still letting him leave it.
  if (services.length === 0 && !adding && !importing) {
    return (
      <div className="flex flex-col gap-3 p-4">
        {switcher}
        <EmptyState
          title={t('services.empty.title')}
          description={t('services.empty.description')}
          action={
            <div className="flex gap-2">
              {action(catalog, 'operations.create_service') ? (
                <Button onClick={() => setAdding(true)}>{t('services.addFirst')}</Button>
              ) : null}
              {/* A SHOP MIGRATING FROM A CASHIER/POS SYSTEM ALREADY HAS ITS FULL LIST SOMEWHERE —
                  offering only "type your first one" here means the fastest path for exactly that
                  shop (import the whole thing at once) was invisible until services.length > 0,
                  which it can never be before the first import. Found while wiring the button in,
                  fixed here rather than shipped with the same gap. */}
              {action(catalog, 'operations.bulk_import_services') ? (
                <Button variant="outline" onClick={() => setImporting(true)}>{t('services.importFromFile')}</Button>
              ) : null}
            </div>
          }
        />
        <ServicesImportDrawer session={session} catalog={catalog} existing={[]}
                             open={importing} onClose={() => setImporting(false)} onImported={load} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 p-4">
      {switcher}
      {error ? <p className="text-danger">{error}</p> : null}

      {/* THE PROPOSAL, AND IT ONLY EVER PROPOSES. The engine noticed the owner set the same value
          on several services; it says so once, in the screen where those services are, and does
          nothing until he agrees. Rearranging his settings on his behalf is the fastest way to
          lose his trust in this page. */}
      {suggestion && action(catalog, 'reminders.set_group') ? (
        <div className="rounded-card border border-border-subtle bg-surface-1 p-4">
          <p className="text-sm">
            {tf(t, 'services.suggestion.text', { n: suggestion.services.length })}
          </p>
          <p className="mt-1 text-sm text-text-secondary">
            {t('services.suggestion.hint')}
          </p>
          {naming === null ? (
            <div className="mt-3 flex gap-2">
              <Button onClick={() => setNaming('')}>{t('services.groupThem')}</Button>
              {/* DISMISSED, NOT SAVED AS A REFUSAL. The suggestion is recomputed from his own
                  settings; if he changes them it should be free to reappear. */}
              <Button variant="ghost" onClick={() => setSuggestion(null)}>{t('services.notNow')}</Button>
            </div>
          ) : (
            <div className="mt-3 flex gap-2">
              <input
                autoFocus
                value={naming}
                onChange={(e) => setNaming(e.target.value)}
                placeholder={t('services.groupName.placeholder')}
                className="h-10 flex-1 rounded-lg bg-surface-2 px-3"
              />
              <Button disabled={saving || !naming.trim()} onClick={() => makeGroup(naming)}>
                {t('services.save')}
              </Button>
              <Button variant="ghost" onClick={() => setNaming(null)}>{t('services.cancel')}</Button>
            </div>
          )}
        </div>
      ) : null}

      {/* ── the rail: his own groups, as navigation ──────────────────────────────────────────
          DERIVED FROM `grouped`, NEVER FROM A LIST OF ITS OWN. It carries exactly the headings
          below it and counts the same services, so a group he makes appears here the moment it
          exists and one he deletes leaves — there is nothing to keep in step. */}
      {(() => {
        const stoppedCount = services.filter((x) => x.active === false).length;
        // THE TAB HE IS STANDING ON CAN CEASE TO EXIST UNDER HIM. Re-activating the last stopped
        // service takes the count to zero, which hides the whole strip — and the state still said
        // «الموقوفة», so the screen rendered an empty list with no control anywhere to leave it.
        // He was stuck on a tab that was no longer on screen, by doing exactly the right thing.
        //
        // DERIVED, NOT JUST RESET. A `useEffect` that corrects the state afterwards renders the
        // trapped frame first; reading the view through this expression means the frame that
        // cannot happen never does.
        const view = stoppedCount > 0 ? show : 'active';
        const visible = services.filter((svc) => {
          // `active` absent means active: the field grid has never sent the flag, and treating a
          // missing field as "stopped" would empty the screen for every shop reading that route.
          const stopped = svc.active === false;
          return view === 'stopped' ? stopped : !stopped;
        });
        const bins = grouped(visible);
        const shown = only === null ? bins : bins.filter(([g]) => g === only);
        return (
      <div className="flex flex-col gap-3">
      {/* ── one toolbar, and nothing beside the table ───────────────────────────────────────
          THE SIDE RAIL IS GONE. A column of group chips beside a table is a second navigation for
          a page that already has one — it took 11rem of every desktop screen, stacked into a
          scrolling strip on a phone, and all it did was filter a list short enough to read. It is
          a dropdown now: same filter, one line, and no furniture.

          THE GENERAL SETTING IS A LINE, NOT A CARD. As a bordered box with a folded panel it read
          like an input at the top of the screen — the owner's own words were that it looked like a
          field he had to fill. It states what it is and opens only when he asks. */}
      <div className="flex flex-wrap items-center gap-2">
        {action(catalog, 'reminders.set_group') && bins.length > 1 ? (
          <select
            aria-label={t('services.filterByGroup')}
            value={only ?? ''}
            onChange={(e) => setOnly(e.target.value === '' ? null : e.target.value)}
            className="h-10 rounded-lg border border-border-subtle bg-surface-1 px-3 text-sm"
          >
            <option value="">{tf(t, 'services.allGroups', { n: visible.length })}</option>
            {bins.map(([g, list]) => (
              <option key={g || 'ungrouped'} value={g}>
                {tf(t, 'services.groupOption', { group: g === UNGROUPED ? t('services.ungroupedHeading') : g, n: list.length })}
              </option>
            ))}
          </select>
        ) : null}

        {stoppedCount > 0 ? (
          <Segmented
            ariaLabel={t('services.viewAriaLabel')}
            value={view}
            onChange={(v) => setShow(v as 'active' | 'stopped')}
            options={[
              // TWO, NOT THREE. «الكل» mixes what he sells with what he stopped, which is the one
              // view that answers no question.
              { value: 'active', label: t('services.active') },
              { value: 'stopped', label: tf(t, 'services.stopped', { n: stoppedCount }) },
            ]}
          />
        ) : null}

        {/* GRID vs LIST — same control Bookings.tsx already carries, same reason: it changes only
            how the same read is drawn, never what is filtered. Icon-only, each with its own
            aria-label/title for the first glance an icon alone does not explain. */}
        <div className="flex items-center gap-1 rounded-full bg-surface-2 p-1">
          {([
            { id: 'list' as const, icon: List, label: 'جدول' },
            { id: 'grid' as const, icon: LayoutGrid, label: 'بطاقات' },
          ]).map(({ id, icon: Icon, label }) => (
            <button key={id} type="button" onClick={() => setLayout(id)}
                   aria-label={label} title={label}
                   className={[
                     'grid h-8 w-9 place-items-center rounded-full transition-colors',
                     layout === id ? 'bg-accent text-accent-contrast shadow-sm'
                                  : 'text-text-secondary hover:text-text-primary',
                   ].join(' ')}>
              <Icon size={15} aria-hidden />
            </button>
          ))}
        </div>

        {/* ONE «؟» FOR THE TABLE, NOT ONE PER COLUMN. Four marks across a header sixty-four
            pixels per column wide crowded into each other and spilled onto the neighbouring
            label — «النقاط؟» reading as one word. A legend answers all four at once, in a
            sentence each, and the header goes back to being four words. */}
        <button
          type="button"
          aria-expanded={Boolean(asked)}
          onClick={() => setAsked(asked ? null : 'legend')}
          className="grid h-10 place-items-center rounded-lg px-3 text-sm text-text-secondary"
        >
          {asked ? t('services.hideExplain') : t('services.showExplain')}
        </button>

        {action(catalog, 'operations.bulk_import_services') && !adding ? (
          <Button className={action(catalog, 'operations.create_service') ? undefined : 'ms-auto'}
                 variant="outline" onClick={() => setImporting(true)}>
            {t('services.importFromFile')}
          </Button>
        ) : null}

        {action(catalog, 'operations.create_service') && !adding ? (
          <Button className="ms-auto" onClick={() => setAdding(true)}>{t('services.addServiceOrProduct')}</Button>
        ) : null}
      </div>

      <ServicesImportDrawer session={session} catalog={catalog}
                           existing={(services ?? []).map((s) => ({ name: s.name, active: s.active }))}
                           open={importing} onClose={() => setImporting(false)} onImported={load} />

      {action(catalog, 'reminders.set_general') ? (
        <details className="group">
          <summary className="flex cursor-pointer list-none items-center gap-2 px-1 py-1 text-sm text-text-secondary">
            <span className="font-medium text-text-primary">{t('services.generalSetting')}</span>
            <span className="tabular-nums">
              {summarise(t, {
                interval_days: settings?.general?.interval_days,
                follow_up_days: settings?.general?.follow_up_days,
              })}
            </span>
            <span className="text-xs opacity-70 group-open:hidden">{t('services.change')}</span>
          </summary>
          <div className="mt-2 flex flex-col gap-2 rounded-card border border-border-subtle bg-surface-1 p-4">
            <div className="flex items-center gap-2">
              <span className="text-sm text-text-secondary">{t('services.appliesToUncustomized')}</span>
              <Hint>
                {t('services.appliesToUncustomized.hint')}
              </Hint>
            </div>
            <Setting
              label={t('services.reminderCycle.label')}
              name={t('services.reminderCycle.name')}
              meaning={t('services.reminderCycle.meaning')}
              value={settings?.general?.interval_days}
              preview={(n) => tf(t, 'services.reminderCycle.preview', { n })}
              zero={t('services.reminderCycle.zero')}
              onSave={(n) => setGeneral({ interval_days: n })}
            />
            <Setting
              label={t('services.followUp')}
              name={t('services.followUp.name')}
              meaning={t('services.followUp.meaning')}
              value={settings?.general?.follow_up_days}
              preview={(n) => tf(t, 'services.followUp.preview', { n })}
              zero={t('services.followUp.zero')}
              onSave={(n) => setGeneral({ follow_up_days: n })}
            />

            {/* ── the confirmation of the visit itself ──────────────────────────────────────
                NOT A NUMBER, SO NOT A `Setting`. The other two rows answer "after how many
                days"; this one answers "at all?".

                AND IT IS A TRIGGER'S SWITCH, not a setting of its own. It lived in the settings
                tree for a day — which became two switches for one behaviour the moment every
                message got one, and two switches for one behaviour is one of them quietly doing
                nothing. The other twelve live in «رسائلي»; this one stays here too because it is
                where an owner asks "what happens after a visit". */}
            <div className="flex items-start justify-between gap-3 border-t border-border-subtle pt-3">
              <span className="flex min-w-0 flex-col gap-1">
                <span className="flex items-center gap-2 text-sm font-medium">
                  {t('services.visitConfirmation')}
                  <Hint>
                    {t('services.visitConfirmation.hint')}
                  </Hint>
                </span>
                <span className="text-xs text-text-secondary">
                  {visitOn
                    ? t('services.visitConfirmation.on')
                    : t('services.visitConfirmation.off')}
                </span>
              </span>
              <Toggle
                ariaLabel={t('services.visitConfirmation')}
                disabled={saving}
                // PRESENCE, NOT TRUTH — the server answers with the reason's own state, and
                // «لم يختر» is «نرسل». Rendering undefined as off would show a switch that
                // disagrees with what actually goes out.
                checked={visitOn}
                onChange={setVisitConfirmation}
              />
            </div>
          </div>
        </details>
      ) : null}

      <div className="flex flex-col gap-3">

          {/* THE FORM, WHOSE BUTTON NOW LIVES IN THE TOOLBAR ABOVE. «خدماتي» once listed a
              catalogue and offered no way to add to it — a shop selling something new had nowhere
              to say so. */}
          {action(catalog, 'operations.create_service') && adding ? (
            (
              <form
                className="flex flex-col gap-3 rounded-card bg-surface-1 p-4 shadow-sm"
                onSubmit={(e) => {
                  e.preventDefault();
                  const f = new FormData(e.currentTarget);
                  const pts = String(f.get('points') || '').trim();
                  const priceText = String(f.get('price') || '').trim();
                  // SAME SILENT DROP AS THE TABLE'S OWN PRICE CELL, caught here before the create
                  // call rather than inside it: `halalas` returning null for typed-but-invalid text
                  // used to fall into the same branch as an empty box, so «إضافة» created the
                  // service with no price at all and said nothing about why.
                  if (priceText !== '' && halalas(priceText) === null) {
                    setError(t('services.error.priceInvalid'));
                    return;
                  }
                  addService(String(f.get('name') || ''), {
                    cycleDays: Number(f.get('cycle_days') || 0),
                    durationMinutes: Number(f.get('duration_minutes') || 0),
                    priceMinor: priceText === '' ? null : halalas(priceText),
                    followUpDays: Number(f.get('follow_up_days') || 0),
                    // AN EMPTY BOX IS NOT A ZERO HERE. Blank means "whatever the shop's general
                    // rule is"; a typed 0 means "this one earns nothing", and they are different
                    // instructions with different futures.
                    points: pts === '' ? null : Number(pts),
                    group: String(f.get('group') || ''),
                    description: String(f.get('description') || ''),
                    image: pendingImage,
                  });
                }}
              >
                <label className="flex flex-col gap-1">
                  <span className="text-sm">{t('services.name')}</span>
                  <input name="name" required autoFocus maxLength={128}
                         placeholder={t('services.name.placeholder')}
                         className="h-10 rounded-lg bg-surface-2 px-3" />
                </label>

                {/* SAME BOX, SAME WORDING, AS THE TABLE'S OWN EDIT FIELD — this is the same
                    `description` the server already accepts on create, not a new one added just
                    for this form. */}
                <label className="flex flex-col gap-1">
                  <span className="text-sm">وصف قصير (اختياري)</span>
                  <textarea name="description" maxLength={300} rows={2}
                            placeholder="وصف قصير (يستخدمه الذكاء الاصطناعي بالواتساب)"
                            className="w-full rounded-lg bg-surface-2 px-3 py-2 text-sm" />
                </label>

                {/* THE PHOTO STAYS ON THIS SIDE OF THE NETWORK UNTIL «إضافة». There is no
                    server-side draft for it — nothing to attach a file to before a service id
                    exists — so the "hold it, only real if confirmed" behaviour is just this: a
                    File object living in `pendingImage`, never read by anything until submit
                    calls uploadServiceImage() with the real id, and dropped untouched on cancel
                    (or on a second pick, which replaces rather than adds to it — one photo per
                    service, same as the row's own edit view). */}
                {action(catalog, 'operations.upload_service_image') ? (
                  <label className="flex flex-col gap-1">
                    <span className="text-sm">صورة الخدمة (اختياري)</span>
                    <input type="file" accept="image/jpeg,image/png,image/webp"
                           onChange={(e) => setPendingImage(e.target.files?.[0] ?? null)}
                           className="text-sm" />
                    {pendingImage ? (
                      <span className="text-xs text-text-secondary">
                        {pendingImage.name} — تُرفع فقط لو ضغطت «{t('services.add')}»
                      </span>
                    ) : null}
                  </label>
                ) : null}

                {/* SHORT LABELS, AND THE QUESTION LIVES IN THE «؟». The full sentences did not
                    fit the label column on a phone and arrived clipped mid-word — «كل كم يوماً
                    ي…» is worse than a short name, because a truncated question is unanswerable
                    while a short one is merely brief. */}
                <Row label={t('services.reminderCycle.label')}
                     hint={t('services.reminderCycle.rowHint')}>
                  <input name="cycle_days" type="number" min={0} defaultValue={0} dir="ltr"
                         className="h-10 w-full rounded-lg bg-surface-2 px-3 text-center tabular-nums" />
                </Row>

                {/* 15 دقيقة، القيمة المقترحة والخطوة معاً — أصغر وحدة يتحرّك عليها الجدول
                    أصلاً، وأقرب افتراض واقعي لخدمة سريعة. رقم مقترح يُعدَّل قبل الحفظ، لا قيمة
                    يفرضها الخادم بصمت — العطاء الفعلي في operations يبقى «0 = غير مضبوطة» دائماً.
                    `step` يحرّك أسهم الحقل بوحدات 15 فقط — لا يمنع كتابة رقم آخر يدوياً. */}
                <Row label={t('services.duration.label')}
                     hint={t('services.duration.hint')}>
                  <input name="duration_minutes" type="number" min={0} max={720} step={15} defaultValue={15} dir="ltr"
                         className="h-10 w-full rounded-lg bg-surface-2 px-3 text-center tabular-nums" />
                </Row>

                {/* السعر اختياري — فارغ يبقى فارغاً، لا صفر مفروض. */}
                <Row label={t('services.price.label')} hint={t('services.price.hint')}>
                  <input name="price" type="text" inputMode="decimal" dir="ltr" placeholder="—"
                         className="h-10 w-full rounded-lg bg-surface-2 px-3 text-center tabular-nums" />
                </Row>

                {action(catalog, 'reminders.set_service_settings') ? (
                  <Row label={t('services.followUp')}
                       hint={t('services.followUp.rowHint')}>
                    <input name="follow_up_days" type="number" min={0} defaultValue={0} dir="ltr"
                           className="h-10 w-full rounded-lg bg-surface-2 px-3 text-center tabular-nums" />
                  </Row>
                ) : null}

                {earnAction ? (
                  <Row label={t('services.points.label')}
                       hint={t('services.points.hint')}>
                    <input name="points" type="number" min={0} dir="ltr"
                           placeholder={String(earn?.general?.points ?? 0)}
                           className="h-10 w-full rounded-lg bg-surface-2 px-3 text-center tabular-nums" />
                  </Row>
                ) : null}

                {action(catalog, 'reminders.set_group') ? (
                  <Row label={t('services.group')}
                       hint={t('services.group.hint')}>
                    <select name="group" className="h-10 w-full rounded-lg bg-surface-2 px-2 text-sm">
                      <option value="">{t('services.noGroupOption')}</option>
                      {Object.keys(settings?.groups ?? {}).map((g) => (
                        <option key={g} value={g}>{g}</option>
                      ))}
                    </select>
                  </Row>
                ) : null}

                <div className="flex gap-2">
                  <Button type="submit" disabled={saving}>{t('services.add')}</Button>
                  <Button type="button" variant="ghost"
                          onClick={() => { setAdding(false); setPendingImage(null); }}>{t('services.cancel')}</Button>
                </div>
              </form>
            )
          ) : null}

      {/* THE LEGEND, AT THE TABLE'S OWN WIDTH. Prose does not fit in a header cell; four
          sentences at the width of the page do. */}
      {asked ? (
        <dl className="flex flex-col gap-2 rounded-card border border-border-subtle bg-surface-2/60 px-4 py-3 text-sm leading-relaxed">
          {[
            [t('services.legend.duration.term'), t('services.legend.duration.def')],
            [t('services.price.label'), t('services.legend.price.def')],
            [t('services.legend.cycle.term'), t('services.legend.cycle.def')],
            [t('services.followUp'), t('services.legend.followUp.def')],
            [t('services.points'), t('services.legend.points.def')],
            [t('services.group'), t('services.legend.group.def')],
          ].map(([term, said]) => (
            <div key={term} className="flex flex-wrap gap-x-2">
              <dt className="font-medium">{term}</dt>
              <dd className="min-w-0 flex-1 text-text-secondary">{said}</dd>
            </div>
          ))}
        </dl>
      ) : null}

      {/* ── the table ────────────────────────────────────────────────────────────────────────
          ONE QUESTION PER COLUMN, ASKED ONCE AT THE TOP. Every service used to carry its own «؟»
          beside every field, so a shop with sixteen services rendered the same four explanations
          sixteen times — and none of them could be read without opening a card first. A column
          header is the natural place for «ما معنى هذا الرقم؟»: it is asked once, answered once,
          and applies to everything under it.

          AND THE ROW IS THE SERVICE. Editing happens in the cell; the actions live in one column
          at the end, so scanning down a column compares the same number across the whole
          catalogue — which is the act this screen exists for and a stack of cards made
          impossible. */}
      {/* NO HORIZONTAL SCROLL, AND NO SHRUNKEN COPY OF THE DESKTOP TABLE. Six columns cannot fit a
          phone: forcing them produces a sideways-scrolling grid where the numbers he came to
          compare are off-screen — the worst of both shapes. So the phone gets the three columns
          that answer «ما عندي، وكل كم يوماً، وماذا أفعل بها», and the other three appear stacked
          under the row the moment he taps ✎. Nothing is unreachable; it is only unasked. */}
      {layout === 'grid' ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {shown.flatMap(([, inGroup]) => inGroup).map((svc) => {
            const stopped = svc.active === false;
            const live = !stopped;
            return (
              <div key={svc.id}
                  className={[
                    'group relative flex flex-col gap-2 overflow-hidden rounded-2xl border p-3',
                    'transition-all duration-200 hover:-translate-y-0.5',
                    live
                      ? 'border-border-subtle bg-surface-1 shadow-sm hover:shadow-lg hover:shadow-success/5'
                      : 'border-border-subtle bg-surface-1 opacity-70',
                  ].join(' ')}>
                {live ? (
                  <span aria-hidden
                       className="absolute inset-y-3 start-0 w-[3px] rounded-full bg-gradient-to-b from-success to-success/40" />
                ) : null}
                {/* A REAL PHOTO, LARGE, OR A NEUTRAL PLACEHOLDER — never a blank box. The absence
                    of a photo is a fact worth seeing at a glance (an owner missing photos across
                    his catalogue should notice), not something the layout quietly hides. */}
                <div className="relative -mx-3 -mt-3 mb-1 aspect-[16/9] overflow-hidden bg-surface-2">
                  {images[svc.id] ? (
                    <img src={images[svc.id]} alt="" className="h-full w-full object-cover" />
                  ) : (
                    <div className="grid h-full place-items-center text-text-muted">
                      <ImageOff size={22} aria-hidden />
                    </div>
                  )}
                </div>
                <div className="relative flex items-start justify-between gap-2 ps-2">
                  <span className="flex min-w-0 items-center gap-2 font-medium">
                    <span className="truncate">{svc.name}</span>
                    {stopped ? <Badge tone="neutral">{t('services.stoppedBadge')}</Badge> : null}
                  </span>
                </div>
                {svc.description ? (
                  <p className="relative line-clamp-2 ps-2 text-xs text-text-secondary">{svc.description}</p>
                ) : null}
                <span className="relative ps-2 text-sm text-text-secondary">
                  {svc.price_minor ? riyals(svc.price_minor) : '—'}
                </span>
                <div className="relative mt-1 flex items-center justify-end ps-2">
                  {action(catalog, 'operations.update_service') ? (
                    <Button variant="outline" size="sm"
                           onClick={() => { setLayout('list'); setOpen(svc.id); }}>
                      {t('services.edit')}
                    </Button>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
      <div className="rounded-card border border-border-subtle bg-surface-1">
        {/* THE NAME TAKES THE SLACK, THE NUMBERS STAY NARROW. With every column an equal share the
            table spread four dashes across a desktop — a metre of white between a service and the
            one number about it. `w-full` on the first cell and `w-px` on the others is the CSS
            way to say "one column is the content, the rest are labels". */}
        {/* FIXED, NOT AUTO — and this is what broke it on a phone. With `table-auto` the browser
            sizes columns from their content, so seven service names plus five headers asked for
            more width than the card had and the rows simply ran out past its edges: a list whose
            right side was cut off by the screen. Fixed widths mean the table can never be wider
            than its container, and a long name truncates instead of pushing the table off. */}
        <table className="w-full table-fixed border-collapse text-sm">
          <thead>
            <tr className="border-b border-border-subtle bg-surface-2/50 text-text-secondary">
              <Th className="w-[38%]">{t('services.table.service')}</Th>
              <Th wide className="w-24">{t('services.table.duration')}</Th>
              <Th wide className="w-24">{t('services.price.label')}</Th>
              <Th narrow>{t('services.legend.cycle.term')}</Th>
              <Th narrow wide>{t('services.followUp')}</Th>
              {earnAction ? <Th narrow wide>{t('services.points')}</Th> : null}
              {action(catalog, 'reminders.set_group') ? (
                // WIDER THAN THE NUMBER COLUMNS, because it holds a name and a dropdown arrow.
                // At 64px «بلا مجموعة» rendered as «بلا» — a truncation that reads as a value.
                <Th wide className="w-36">{t('services.group')}</Th>
              ) : null}
              <Th narrow className="w-24">{t('services.table.actions')}</Th>
            </tr>
          </thead>
          <tbody>
      {shown.map(([group, inGroup]) => (
        <Fragment key={group || 'ungrouped'}>
          {/* THE HEADING CARRIES THE GROUP'S OWN CYCLE, because that is what the services under it
              follow — a heading that is only a name leaves the owner reading each service to work
              out what the group actually does. The remainder bin has no settings and says so by
              carrying no number. */}
          {/* A HEADING ROW INSIDE THE TABLE, so the columns never break alignment. Hidden when the
              whole table is one bin: a single heading over everything is a label for the screen,
              not a division of it. */}
          {shown.length > 1 ? (
            <tr className="border-b border-border-subtle bg-surface-2/30">
              <td colSpan={11} className="px-3 py-2">
                <div className="flex items-center justify-between gap-3">
                  <span className="min-w-0 text-sm font-semibold text-text-secondary">
                    {group === UNGROUPED ? t('services.ungroupedHeading') : group}
                    {group !== UNGROUPED && settings?.groups?.[group]?.interval_days
                      ? tf(t, 'services.groupIntervalSuffix', { n: settings.groups[group].interval_days as number })
                      : ''}
                  </span>
                  {/* THE GROUP CAN BE UNMADE. It could be created and never removed, so an owner
                      who grouped his services wrongly was stuck with the mistake on every future
                      screen. Not offered on the remainder bin: «غير مجمّعة» is not a group, it is
                      what is left over, and a delete button on it would delete nothing. */}
                  {group !== UNGROUPED && action(catalog, 'reminders.delete_group') ? (
                    <Button variant="ghost" disabled={saving} onClick={() => deleteGroup(group)}>
                      {t('services.deleteGroup')}
                    </Button>
                  ) : null}
                </div>
              </td>
            </tr>
          ) : null}
          {inGroup.map((svc) => {
        const { value, own } = settingFor(svc.id);
        const stopped = svc.active === false;
        const editing = open === svc.id;
        return (
          <Fragment key={svc.id}>
          {/* ONE ROW PER SERVICE, AND THE COLUMNS ARE THE COMPARISON. A stack of cards could only
              ever answer "what is this service set to"; the owner's real question is "which of my
              services is set differently", and that is a column read top to bottom. */}
          <tr className={[
            'border-b border-border-subtle last:border-0 align-middle',
            stopped ? 'opacity-55' : '',
          ].join(' ')}>
            <td className="px-3 py-2">
              <div className="flex items-center gap-2">
                {/* THE THUMBNAIL — present or absent, never a blank gap, so a missing photo reads
                    as a real fact rather than a layout hiccup. Small here on purpose: the table's
                    own value is a column scan, and a large photo per row would be the phone-table
                    mistake this screen's own header comment already argues against, just moved to
                    a different column. */}
                <span className="grid size-8 shrink-0 place-items-center overflow-hidden rounded-md bg-surface-2 text-text-muted">
                  {images[svc.id] ? (
                    <img src={images[svc.id]} alt="" className="h-full w-full object-cover" />
                  ) : <ImageOff size={14} aria-hidden />}
                </span>
                {editing && action(catalog, 'operations.update_service') ? (
                  <div className="flex min-w-0 flex-1 flex-col gap-1">
                    <input
                      defaultValue={svc.name}
                      autoFocus
                      aria-label={tf(t, 'services.nameAriaLabel', { name: svc.name })}
                      maxLength={128}
                      onBlur={(e) => {
                        const v = e.target.value.trim();
                        if (v && v !== svc.name) patchService(svc.id, { name: v });
                      }}
                      // NO MINIMUM WIDTH. A `min-w` inside a fixed-width cell does not widen the
                      // column — it overflows it, which is what put the name box outside its own row
                      // on a phone. The column is half the table; the input takes exactly that.
                      className="h-9 w-full min-w-0 rounded-lg bg-surface-2 px-2"
                    />
                    <input
                      defaultValue={svc.description ?? ''}
                      placeholder="وصف قصير (يستخدمه الذكاء الاصطناعي بالواتساب)"
                      maxLength={300}
                      onBlur={(e) => {
                        const v = e.target.value.trim();
                        if (v !== (svc.description ?? '')) patchService(svc.id, { description: v });
                      }}
                      className="h-8 w-full min-w-0 rounded-lg bg-surface-2 px-2 text-xs"
                    />
                    {action(catalog, 'operations.upload_service_image') ? (
                      <div className="flex items-center gap-1">
                        <label className="flex cursor-pointer items-center gap-1 text-xs text-text-secondary">
                          <Upload size={12} aria-hidden /> صورة
                          <input type="file" accept="image/jpeg,image/png,image/webp" className="hidden"
                                onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadServiceImage(svc.id, f); }} />
                        </label>
                        {svc.has_image ? (
                          <button type="button" onClick={() => deleteServiceImage(svc.id)}
                                 className="flex items-center gap-1 text-xs text-danger">
                            <X size={12} aria-hidden /> حذف الصورة
                          </button>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <span className="flex min-w-0 items-center gap-2">
                    <span className="truncate font-medium">{svc.name}</span>
                    {stopped ? (
                      <>
                        <Badge tone="neutral">{t('services.stoppedBadge')}</Badge>
                        <AssistantHint session={session} anchor="services.stoppedBadge" />
                      </>
                    ) : null}
                  </span>
                )}
              </div>
            </td>

            {/* THE ONE FIELD BOOKINGS ACTUALLY REFUSES WITHOUT (docs/خطة-تنفيذ-الحجوزات.md §6.2):
                a service with no duration cannot be scheduled at all — this was readable
                everywhere and writable nowhere in the console until now. `operations.update_service`
                already accepted it; only the console never asked. */}
            <td className="hidden px-3 py-2 tabular-nums md:table-cell">
              {editing && action(catalog, 'operations.update_service') ? (
                <input
                  type="number" min={0} max={720} dir="ltr"
                  defaultValue={svc.duration_minutes ? String(svc.duration_minutes) : ''}
                  aria-label={tf(t, 'services.durationAriaLabel', { name: svc.name })}
                  onBlur={(e) => {
                    const raw = e.target.value.trim();
                    if (raw === '') return;   // blank saves nothing, same rule as every Num cell
                    const n = Number(raw);
                    if (n !== (svc.duration_minutes ?? 0)) patchService(svc.id, { duration_minutes: n });
                  }}
                  className="h-9 w-full min-w-0 rounded-lg bg-surface-2 px-1 text-center tabular-nums"
                />
              ) : (
                <span className={svc.duration_minutes ? '' : 'text-danger'}>
                  {svc.duration_minutes ? svc.duration_minutes : t('services.notSet')}
                </span>
              )}
            </td>

            {/* THE PRICE IS OPTIONAL — a shop that only wants operations'
                scheduling and reminders, never invoicing, leaves it at «—» and nothing downstream
                requires it. Riyals on the screen, halalas on the wire — see money.ts; never a
                float, never `* 100` at this call site. */}
            <td className="hidden px-3 py-2 tabular-nums md:table-cell">
              {editing && action(catalog, 'operations.update_service') ? (
                <input
                  type="text" inputMode="decimal" dir="ltr"
                  defaultValue={svc.price_minor ? riyals(svc.price_minor) : ''}
                  aria-label={tf(t, 'services.priceAriaLabel', { name: svc.name })}
                  placeholder="—"
                  onBlur={(e) => {
                    const raw = e.target.value.trim();
                    if (raw === '') return;
                    const minor = halalas(raw);
                    // INVALID TEXT USED TO DROP SILENTLY HERE — `halalas` returning null (garbage,
                    // or a third decimal place) fell through both branches with no write and no
                    // word said, so the box quietly kept whatever he had actually typed while the
                    // service kept its old price. `halalas`'s own comment says the caller shows a
                    // reason; this was the caller, and it never did.
                    if (minor === null) { setError(t('services.error.priceInvalid')); return; }
                    if (minor !== svc.price_minor) patchService(svc.id, { price_minor: minor });
                  }}
                  className="h-9 w-full min-w-0 rounded-lg bg-surface-2 px-1 text-center tabular-nums"
                />
              ) : (
                <span className={svc.price_minor ? '' : 'text-text-secondary/60'}>
                  {svc.price_minor ? riyals(svc.price_minor) : '—'}
                </span>
              )}
            </td>

            {/* THE CELL EDITS IN PLACE, AND A BLANK BOX SAVES NOTHING. `Number('')` is 0, which
                would silently turn "I have not decided" into "this service has no cycle". */}
            <Num
              value={value.interval_days}
              own={own}
              editable={editing && !!action(catalog, 'reminders.set_service_settings')}
              label={tf(t, 'services.cycleAriaLabel', { name: svc.name })}
              onSave={(n) => setService(svc.id, { interval_days: n })}
            />
            <Num
              wide
              value={value.follow_up_days}
              own={own}
              editable={editing && !!action(catalog, 'reminders.set_service_settings')}
              label={tf(t, 'services.followUpAriaLabel', { name: svc.name })}
              onSave={(n) => setService(svc.id, { follow_up_days: n })}
            />
            {earnAction ? (
              <Num
                wide
                value={earnFor(svc.id).points}
                own={earnFor(svc.id).own}
                editable={editing}
                label={tf(t, 'services.pointsAriaLabel', { name: svc.name })}
                onSave={(n) => { if (n !== earnFor(svc.id).points) setServicePoints(svc.id, n); }}
              />
            ) : null}

            {action(catalog, 'reminders.set_group') ? (
              <td className="hidden truncate px-3 py-2 md:table-cell">
                {editing ? (
                  <select
                    aria-label={tf(t, 'services.groupAriaLabel', { name: svc.name })}
                    value={settings?.service_group?.[svc.id] ?? ''}
                    onChange={(e) => {
                      const v = e.target.value;
                      if (v === '__new__') { setNaming(svc.id); return; }
                      // «بلا مجموعة» IS AN ACT. It was an option with nothing behind it, so an
                      // owner who grouped something could never ungroup it.
                      if (!v) { leaveGroup(svc.id); return; }
                      joinGroup(svc.id, v);
                    }}
                    className="h-9 w-full min-w-0 rounded-lg bg-surface-2 px-2 text-sm"
                  >
                    <option value="">{t('services.noGroupOption')}</option>
                    {Object.keys(settings?.groups ?? {}).map((g) => (
                      <option key={g} value={g}>{g}</option>
                    ))}
                    <option value="__new__">{t('services.newGroupOption')}</option>
                  </select>
                ) : (
                  <span className="text-text-secondary">
                    {settings?.service_group?.[svc.id] || '—'}
                  </span>
                )}
              </td>
            ) : null}

            {/* ── the actions column ───────────────────────────────────────────────────────
                TWO ICONS, AND NEITHER OF THEM DELETES. A service cannot be deleted at all: every
                visit ever recorded names one, and removing the row would leave last year's
                history pointing at nothing. «إيقاف» is the whole of what "remove" means here —
                it leaves the operator's grid and its reminders go silent, and the record stays
                readable. So the second icon is a power switch rather than a bin, because an icon
                that promises deletion and performs retirement is a lie told in one glyph. */}
            <td className="px-3 py-2">
              <div className="flex items-center justify-end gap-0.5 md:gap-1">
                {own && action(catalog, 'reminders.follow_general') ? (
                  <IconButton
                    title={t('services.returnToGeneral')}
                    disabled={saving}
                    onClick={() => followGeneral(svc.id)}
                  ><RotateCcw size={18} aria-hidden /></IconButton>
                ) : null}
                <IconButton
                  title={editing ? t('services.finishEditing') : t('services.edit')}
                  onClick={() => setOpen(editing ? null : svc.id)}
                  active={editing}
                >{editing ? <Check size={18} aria-hidden /> : <Pencil size={18} aria-hidden />}</IconButton>
                {action(catalog, 'operations.update_service') ? (
                  <IconButton
                    title={stopped ? t('services.activate') : t('services.deactivate')}
                    disabled={saving}
                    danger={!stopped}
                    onClick={() => patchService(svc.id, { active: stopped })}
                  >
                    {/* AN SVG, NOT A CHARACTER. «⏻» (U+23FB) is a text glyph most phone fonts do
                        not carry, so the button rendered as an empty box that pressed and did
                        something — the worst possible state for the one action that takes a
                        service off the operator's grid. */}
                    <Power size={18} aria-hidden />
                  </IconButton>
                ) : null}
              </div>
            </td>
          </tr>

          {/* ── the phone's edit row ──────────────────────────────────────────────────────
              THE THREE COLUMNS THE PHONE DOES NOT SHOW, STACKED, AND ONLY WHILE HE IS EDITING.
              Hiding a column on a narrow screen is only honest if the field is reachable
              somewhere; this is that somewhere. It costs nothing until ✎ is tapped, and then it
              is a short labelled form under the row it belongs to — which is what a phone is
              good at, and what a six-column grid squeezed into 380px never is. */}
          {editing ? (
            <tr className="border-b border-border-subtle bg-surface-2/40 md:hidden">
              <td colSpan={3} className="px-3 py-3">
                <div className="flex flex-col gap-2">
                  {action(catalog, 'reminders.set_service_settings') ? (
                    <Field label={t('services.followUp')}>
                      <input
                        type="number" min={0} dir="ltr"
                        defaultValue={String(value.follow_up_days ?? 0)}
                        aria-label={tf(t, 'services.followUpAriaLabel', { name: svc.name })}
                        onBlur={(e) => {
                          const raw = e.target.value.trim();
                          if (raw !== '' && Number(raw) !== (value.follow_up_days ?? 0)) {
                            setService(svc.id, { follow_up_days: Number(raw) });
                          }
                        }}
                        className="h-10 w-20 rounded-lg bg-surface-1 px-2 text-center tabular-nums"
                      />
                    </Field>
                  ) : null}
                  {earnAction ? (
                    <Field label={t('services.points')}>
                      <input
                        type="number" min={0} dir="ltr"
                        defaultValue={String(earnFor(svc.id).points)}
                        aria-label={tf(t, 'services.pointsAriaLabel', { name: svc.name })}
                        onBlur={(e) => {
                          const raw = e.target.value.trim();
                          if (raw !== '' && Number(raw) !== earnFor(svc.id).points) {
                            setServicePoints(svc.id, Number(raw));
                          }
                        }}
                        className="h-10 w-20 rounded-lg bg-surface-1 px-2 text-center tabular-nums"
                      />
                    </Field>
                  ) : null}
                  {action(catalog, 'reminders.set_group') ? (
                    <Field label={t('services.group')}>
                      <select
                        aria-label={tf(t, 'services.groupAriaLabel', { name: svc.name })}
                        value={settings?.service_group?.[svc.id] ?? ''}
                        onChange={(e) => {
                          const v = e.target.value;
                          if (v === '__new__') { setNaming(svc.id); return; }
                          if (!v) { leaveGroup(svc.id); return; }
                          joinGroup(svc.id, v);
                        }}
                        className="h-10 rounded-lg bg-surface-1 px-2 text-sm"
                      >
                        <option value="">{t('services.noGroupOption')}</option>
                        {Object.keys(settings?.groups ?? {}).map((g) => (
                          <option key={g} value={g}>{g}</option>
                        ))}
                        <option value="__new__">{t('services.newGroupOption')}</option>
                      </select>
                    </Field>
                  ) : null}
                </div>
              </td>
            </tr>
          ) : null}

          {/* «من يقدر يسوّيها» — يظهر فقط حين يوجد أكثر من موظف نشط واحد؛ محل بموظف واحد لا يرى
              هذا الصف إطلاقاً لأنه لا معنى له (§3 من الخطة: البساطة الافتراضية). نفس منيو
              الفلترة المستخدمة في كل مكان آخر بالكونسول — زر بعدّاد + منيو بمربعات اختيار. */}
          {editing && (staff ?? []).filter((s) => s.active !== false).length > 1
              && action(catalog, 'operations.update_service') ? (
            <tr className="border-b border-border-subtle bg-surface-2/40">
              <td colSpan={11} className="px-3 py-2">
                <FilterMenu
                  label={t('services.whoCanDoIt')}
                  options={(staff ?? []).filter((s) => s.active !== false)
                    .map((s) => ({ value: s.id, label: s.name }))}
                  selected={eligibleIdsFor(svc)}
                  onChange={(next) => onEligibleChange(svc, next)}
                />
              </td>
            </tr>
          ) : null}

          {/* THE NEW-GROUP BOX, on its own full-width row so it cannot squeeze a column. */}
          {naming === svc.id ? (
            <tr className="border-b border-border-subtle bg-surface-2/40">
              <td colSpan={11} className="px-3 py-2">
                <div className="flex items-center gap-2">
                  <input
                    autoFocus
                    aria-label={t('services.newGroupNameAriaLabel')}
                    placeholder={t('services.newGroupPlaceholder')}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') joinGroup(svc.id, e.currentTarget.value);
                      if (e.key === 'Escape') setNaming(null);
                    }}
                    className="h-9 flex-1 rounded-lg bg-surface-1 px-3"
                  />
                  <Button variant="ghost" onClick={() => setNaming(null)}>{t('services.cancel')}</Button>
                </div>
              </td>
            </tr>
          ) : null}
          </Fragment>
        );
          })}
        </Fragment>
      ))}
          </tbody>
        </table>
      </div>
      )}
      </div>
      </div>
        );
      })()}
    </div>
  );
}

/**
 * A column header, and the «؟» that explains the WHOLE column.
 *
 * THIS IS THE ONE REAL SAVING OF THE TABLE. The same four explanations used to be rendered once
 * per service — sixteen services, sixty-four hints — and every one of them was invisible until a
 * card was opened. Asked once at the top, the question is answered before he reads a single row.
 */
function Th({ children, wide, narrow, className = '' }: {
  children: React.ReactNode;
  /** An explicit width when the default narrow one does not fit. */
  className?: string;
  /** Only on a screen wide enough for it — the phone reaches this field from the edit row. */
  wide?: boolean;
  /** As wide as its content and no wider; the name column absorbs what is left. */
  narrow?: boolean;
}) {
  return (
    <th scope="col" className={[
      'whitespace-nowrap px-3 py-2 text-start text-xs font-medium',
      narrow ? 'w-16' : '',
      wide ? 'hidden md:table-cell' : '',
      className,
    ].join(' ')}>
      {children}
    </th>
  );
}

/**
 * A number cell: read as text, edited in place, and PALE WHEN IT IS INHERITED.
 *
 * The paleness is the whole of «إعداد خاص» in a table — a badge per row would be a column of
 * badges, while a number that is dimmer than its neighbours says "this one follows the general
 * rule" without spending a column or a word. And it matters: an owner who cannot tell inherited
 * from own retypes the number he is already following, which freezes it (§9.2 — inherit, never
 * copy) and makes the next general change skip that service in silence.
 */
function Num({ value, own, editable, label, onSave, wide }: {
  value?: number;
  own: boolean;
  editable: boolean;
  label: string;
  onSave: (n: number) => void;
  wide?: boolean;
}) {
  const n = value ?? 0;
  return (
    <td className={['px-3 py-2 tabular-nums', wide ? 'hidden md:table-cell' : ''].join(' ')}>
      {editable ? (
        <input
          type="number"
          min={0}
          dir="ltr"
          defaultValue={String(n)}
          aria-label={label}
          onBlur={(e) => {
            const raw = e.target.value.trim();
            // A BLANK BOX SAVES NOTHING. `Number('')` is 0, and 0 is a real instruction here.
            if (raw !== '' && Number(raw) !== n) onSave(Number(raw));
          }}
          className="h-9 w-full min-w-0 rounded-lg bg-surface-2 px-1 text-center tabular-nums"
        />
      ) : (
        <span className={own ? '' : 'text-text-secondary/60'}>{n > 0 ? n : '—'}</span>
      )}
    </td>
  );
}

/** One labelled control in the phone's edit row: the name on the right, the control on the left. */
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex items-center justify-between gap-3">
      <span className="text-sm text-text-secondary">{label}</span>
      {children}
    </label>
  );
}

/** One square action. A title on every one, because a glyph alone is a guess. */
function IconButton({ children, title, onClick, disabled, danger, active }: {
  children: React.ReactNode;
  title: string;
  onClick: () => void;
  disabled?: boolean;
  danger?: boolean;
  active?: boolean;
}) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      disabled={disabled}
      onClick={onClick}
      className={[
        // 40px, WHICH IS A THUMB. Icon buttons that fit the glyph fit nothing else, and this
        // screen is used standing at a counter.
        'grid h-10 w-9 shrink-0 place-items-center rounded-lg text-base transition-colors md:w-10',
        'disabled:opacity-40',
        active
          ? 'bg-surface-2 text-text-primary'
          : danger
            ? 'text-danger hover:bg-danger/10'
            : 'text-text-secondary hover:bg-surface-2',
      ].join(' ')}
    >
      {children}
    </button>
  );
}

/** One question on the add form: its label, its «؟», and the control that answers it. */
function Row({ label, hint, children }:
    { label: string; hint: string; children: React.ReactNode }) {
  return (
    // A GRID, NOT A WRAPPING FLEX ROW. As a flex row with `ms-auto` the control dropped onto its
    // own line the moment a label was one word too long — so the form arrived as a ragged ladder,
    // some boxes beside their label and some beneath it, each starting at a different edge. Two
    // columns put every label on the right and every control on the left, at one width, always.
    // THREE CELLS ON ONE ROW, AND THE EXPLANATION UNDER ALL OF THEM. The «؟» is a direct child
    // of this grid rather than of the label, which is what lets its sentence span the full width
    // when it opens; the control is placed explicitly so the sentence cannot push it down a row.
    <div className="grid grid-cols-[1fr_auto_7.5rem] items-center gap-x-2 gap-y-1">
      {/* WRAPS RATHER THAN CLIPS. A label cut mid-word reads as a rendering fault; a label on
          two lines reads as a label. */}
      {/* THE LABEL COLUMN TAKES THE SLACK (`1fr`), so the «؟» sits at the same x on every row
          instead of trailing each label wherever it happens to end — four marks scattered across
          the card read as decoration; four in a line read as one control repeated. */}
      <span className="min-w-0 text-sm">{label}</span>
      <Hint wide>{hint}</Hint>
      <span className="col-start-3 row-start-1">{children}</span>
    </div>
  );
}

/**
 * One reminder setting: what it means, the number, and what that number will actually do.
 *
 * THE PREVIEW IS THE POINT. A box labelled «الاطمئنان بعد الزيارة (بالأيام)» with 15 in it tells
 * an owner nothing about what his customer receives; «سؤال بعد 15 يوماً من الزيارة», changing as
 * he types, tells him the whole thing. The number is his, the sentence is the consequence, and he
 * reads the consequence before he leaves the field rather than after a message has gone out.
 *
 * LIVE WHILE TYPING, SAVED ON LEAVING. Saving per keystroke would write 1, then 15 — and 1 is a
 * real setting that would really send. So the preview follows the box and the write waits for blur.
 */
function Setting({
  label, meaning, value, preview, zero, onSave, name,
}: {
  label: string;
  /** The accessible name, when two cards on the page carry the same visible label. */
  name?: string;
  meaning: string;
  value?: number;
  preview: (n: number) => string;
  /** What zero means HERE — «بلا دورة» and «لا نسأل» are different silences. */
  zero: string;
  onSave: (n: number) => void;
}) {
  const { t } = useOperatorI18n();
  const [draft, setDraft] = useState(String(value ?? 0));
  const n = Number(draft.trim() || 0);

  return (
    <div className="flex flex-col gap-1 rounded-lg bg-surface-2/60 p-3">
      {/* STACKED ON A PHONE, SIDE BY SIDE WHEN THERE IS ROOM — and `min-w-0` is the part that
          actually fixes it. A flex child defaults to `min-width: auto`, so a paragraph refuses to
          shrink below its content and pushes the number box off the edge of the screen instead of
          wrapping. That is what the owner photographed: the inputs were there, just not on the
          phone. */}
      <div className="flex flex-wrap items-center gap-2">
        {/* THE SENTENCE MOVES BEHIND «؟». Every field on this card carried two lines of prose, and
            with two fields open on a phone the explanations alone filled the screen — the owner
            photographed a card he could not see the bottom of. He reads each of these once in his
            life. The preview line below stays, because that one is not an explanation: it is what
            this number will actually do, and it changes as he types. */}
        <span className="text-sm">{label}</span>
        <Hint>{meaning}</Hint>
        <input
          type="number"
          min={0}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={(e) => {
            const raw = e.target.value.trim();
            if (raw !== '') onSave(Number(raw));
          }}
          // TWO CARDS, TWO NAMES. The general card and a service's card both say «دورة التذكير»
          // on screen — correctly, it is the same setting at two levels — and an accessible name
          // repeated twice on one page is a screen reader announcing two identical fields and a
          // person unable to tell which one he is in.
          aria-label={tf(t, 'services.byDaysAriaLabel', { name: name || label })}
          dir="ltr"
          className="ms-auto h-10 w-24 shrink-0 rounded-lg bg-surface-1 px-3 text-center tabular-nums"
        />
      </div>
      <span className="text-sm text-text-secondary">{n > 0 ? preview(n) : zero}</span>
    </div>
  );
}
