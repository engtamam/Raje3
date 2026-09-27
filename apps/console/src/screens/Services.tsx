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
import { Fragment, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { NAV_ACCENTS } from '../../../../ui/packages/ui/src/theme';
import { Button } from '../rj-ui/Button';
import { Modal } from '../rj-ui/Modal';
import { ConfirmDialog } from '../rj-ui/ConfirmDialog';
import { Badge } from '../rj-ui/Badge';
import { Segmented } from '../rj-ui/Segmented';
import { EmptyState } from '../rj-ui/EmptyState';
import { PageHeader } from '../rj-ui/PageHeader';
import { CircleHelp, ImageOff, Pencil, Plus, Power, PowerOff, SlidersHorizontal, Trash2, Upload, Wrench } from 'lucide-react';
import { Hint } from '../Hint';
import { Card } from '../rj-ui/Card';
import { AssistantHint } from '../AssistantHint';
import { Toggle } from '../rj-ui/Toggle';
import { FilterMenu } from '../rj-ui/FilterMenu';
import { hasFailed, isLoading, isReady } from '../loading';
import { Waiting } from '../Waiting';
import { action, call, downloadUrl, type Catalog } from '../catalog';
import { sentenceFor } from '../api';
import { halalas, riyals } from '../money';
import type { Session } from '../session';
import { useOperatorI18n, tf } from '../operator-i18n';
import './services-i18n';
import { ServicesImportDrawer } from './ServicesImportDrawer';
import { PackagesTab } from './PackagesTab';
import { ProcedureStepsTab } from './ProcedureStepsTab';

interface Service {
  id: string; name: string; cycle_days: number; price_minor: number;
  // DEFAULTS TO 0 = «NOT CONFIGURED», not «free» and not «instant» — bookings refuses to create a
  // slot for a service carrying this, by design (see BookingDialog's own missingDuration check).
  // Editable here for the first time; the field itself was already read by bookings and never
  // writable anywhere in the console — a service could only ever get a real duration by seed.
  duration_minutes?: number;
  catchall?: boolean; active?: boolean;
  /** WHO CAN ACTUALLY DO IT. Absent/empty = every active FIELD-ROLE operator (role === 'operator'
   *  — «الموظف الميداني», the zero-config default: a single-operator shop, or one where every
   *  field hire does everything, never touches this). Naming anyone explicitly — including a
   *  manager/supervisor/marketer — still works; the role default only fills the gap when nobody
   *  was chosen (server-enforced in operations' own service-eligibility route, assignment-mode
   *  redesign phase 2 — this comment used to say "every active operator", which stopped being
   *  true the day that shipped and had to be corrected here too). */
  eligible_staff_ids?: string[];
  /** NAMED vs AUTO (assignment-mode redesign, phase 1/3) — does booking this service ask "which
   *  operator" at all, or does the booking system pick among `eligible_staff_ids` itself with no
   *  question asked. Default "auto" for a new service; independent of `eligible_staff_ids` being
   *  empty or full — a service can be "auto" with a real restricted list (pick automatically, but
   *  only among these three), same as it can be "named" with an empty one (ask by name, offering
   *  everyone). */
  assignment_mode?: 'named' | 'auto';
  /** A short owner-written line — the WhatsApp assistant's only source for "what does this
   *  service actually involve" (services-images-board.md phase 1). */
  description?: string;
  /** NEVER the image itself, NEVER a key — just whether one exists. The real bytes are fetched
   *  through their own gated route (operations.get_service_image), same "never leak an internal
   *  reference" discipline the rest of this product already holds. */
  has_image?: boolean;
}

/** Just enough of an operator to list him as a candidate — same shape Team.tsx reads. `role` is
 *  what decides the field-role default set above (Team.tsx's own ROLES: 'operator' is «الموظف
 *  الميداني» — the value this screen checks against, never a translated label). */
interface StaffMember { id: string; name: string; active?: boolean; role?: string }

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

/** One row of «الحملات التلقائية» — this screen reads only the visit confirmation from it. */
interface ReasonRow { id: string; on: boolean }

/** The one proposal this screen ever makes: several services already share a value. */
interface Suggestion { field: string; value: number | boolean; services: string[] }

/** Services with no group, gathered under one heading rather than left looking unfiled. */
const UNGROUPED = '';

/**
 * The one line under a service name, and it reports EVERYTHING that service is set to do.
 *
 * Two messages can be scheduled off one visit and they are not the same message. The cycle is the
 * one that brings him back — «حان وقت قص شعر» — and it is timed to when the need returns. The
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
type ServicesPageTab = 'services' | 'packages' | 'procedures';

export function ServicesScreen({ session, catalog }: { session: Session; catalog: Catalog }) {
  const { t } = useOperatorI18n();
  const [params, setParams] = useSearchParams();
  const tabParam = params.get('tab');
  const tab: ServicesPageTab =
    tabParam === 'packages' ? 'packages' : tabParam === 'procedures' ? 'procedures' : 'services';
  const setTab = (next: ServicesPageTab) => {
    const p = new URLSearchParams(params);
    if (next === 'services') p.delete('tab'); else p.set('tab', next);
    setParams(p, { replace: true });
  };
  const packagesEnabled = !!action(catalog, 'operations.list_packages');
  const proceduresEnabled = !!action(catalog, 'operations.list_procedure_steps');
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
  /** A blob: URL for `pendingImage`'s own preview inside the add-service modal's dropzone — kept
   *  in state (not recomputed with `URL.createObjectURL` on every render) so the browser is only
   *  ever asked to mint one live object URL per picked file, and the old one is revoked the
   *  moment it stops being shown rather than leaking for the rest of the tab's lifetime. */
  const [pendingImageUrl, setPendingImageUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!pendingImage) { setPendingImageUrl(null); return; }
    const url = URL.createObjectURL(pendingImage);
    setPendingImageUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [pendingImage]);
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
  /** «الإعداد العام» — used to be a native `<details>` sitting on its own row below the toolbar,
   *  which put a whole extra line between the toolbar and the table for a control that belongs
   *  beside «شرح الأعمدة» and «استيراد من ملف» (same row, same kind of ask: "show me something
   *  about this list"). Plain state instead of `<details>` so the trigger can live in the toolbar
   *  while the panel itself still opens below the table header, same place it always has. */
  const [openGeneral, setOpenGeneral] = useState(false);
  /** Which service the GRID view's «تعديل» opened, if any. The table view keeps its own
   *  inline-edit (`open`/`editing`) unchanged — a row IS the columns, so editing in place there
   *  already reads as one continuous thing. A card is a photo first; jumping him to the table to
   *  edit the very thing he was just looking at threw away the view he chose. This is a second,
   *  separate piece of state on purpose — the two edit surfaces are not the same control. */
  const [modalSvc, setModalSvc] = useState<string | null>(null);
  /** The service pending an «إيقاف» confirmation — never triggered on activate, which is not
   *  destructive and needs no dialog to stand in its way. */
  const [confirmStopId, setConfirmStopId] = useState<string | null>(null);
  // WHO EXISTS AT ALL — read only so the eligibility row can be shown/hidden and its checkboxes
  // labelled. A shop with one operator (or none of this screen's role) never reads this at all
  // in any way that shows: the row below is hidden whenever there is one or fewer of them.
  const [staff, setStaff] = useState<StaffMember[] | null | undefined>(undefined);

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
      setError(sentenceFor(e, t('services.error.pointsSaveFailed'), t));
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
      // Mutate the existing bin in place instead of copying the whole array on every
      // service — the copy-on-append version was O(n²) for a shop with a long menu.
      const bin = bins.get(key);
      if (bin) bin.push(svc);
      else bins.set(key, [svc]);
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
      setError(sentenceFor(e, t('services.error.groupCreateFailed'), t));
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
      setError(sentenceFor(e, t('services.error.moveToGroupFailed'), t));
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
        // EACH FOLLOW-UP STEP RUNS EVEN IF AN EARLIER ONE FAILED — the service itself is already
        // created and real, and the comment below already promised "partial creation is fine, rest
        // is editable after" for the photo specifically. That promise did not actually hold: these
        // four steps shared one try/catch, so a refused follow-up-days or group call (an unrelated
        // 400, a service hiccup) threw straight past the photo upload below it, and the row came
        // back from `load()` with no error visible past the form closing — reported live as "we
        // added a product with a photo, and the photo never made it, only editing it in after
        // the fact works." Isolating each awaited call means one refusal costs only its own field.
        let firstError: unknown = null;
        const attempt = async (fn: () => Promise<unknown>) => {
          try { await fn(); } catch (e) { firstError ??= e; }
        };

        const rem = action(catalog, 'reminders.set_service_settings');
        // THE CYCLE WENT WITH THE ROW ALREADY; the follow-up is reminders' and has to be said
        // separately. Zero means "do not ask after this service", which is a real answer and not
        // an unset field — so it is only sent when he typed something above zero.
        if (rem && opts.followUpDays > 0) {
          await attempt(() => call(session, rem, { service_id: id, follow_up_days: opts.followUpDays }));
        }
        // NULL MEANS "follow the general rule" (§9.2: inherit, never copy). Writing today's
        // general number instead would freeze it, and the next change to the general setting
        // would skip this service without saying so.
        if (earnAction && opts.points !== null) {
          await attempt(() => call(session, earnAction, { service_id: id, points: opts.points }));
        }
        const grp = action(catalog, 'reminders.set_group');
        if (grp && opts.group.trim()) {
          await attempt(() => call(session, grp, { name: opts.group.trim(), service_ids: [id] }));
        }
        // THE HELD PHOTO GOES LAST, AGAINST THE REAL ID — the only moment it can go anywhere at
        // all. uploadServiceImage() does its own load()/error handling, so nothing further is
        // needed here beyond forgetting the held file either way (success or failure both leave
        // the form closing; a failed photo does not undo the service that was already created).
        if (action(catalog, 'operations.upload_service_image') && opts.image) {
          await uploadServiceImage(id, opts.image);
        }
        if (firstError) throw firstError;
      }

      setPendingImage(null);
      setAdding(false);
      load();
    } catch (e) {
      setError(sentenceFor(e, t('services.error.addFailed'), t));
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
      setError(sentenceFor(e, t('services.error.editSaveFailed'), t));
    } finally {
      setSaving(false);
    }
  };

  /** Activating is never destructive and goes straight through; stopping needs a real confirmation
   *  — the long explanation used to be squeezed onto the button itself, unreadable in a card row,
   *  when it belongs in the moment he is actually asked to decide. */
  const requestStop = (svc: { id: string; active?: boolean }) => {
    if (svc.active === false) { patchService(svc.id, { active: true }); return; }
    setConfirmStopId(svc.id);
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
      setError(sentenceFor(e, t('services.error.editSaveFailed'), t));
    } finally {
      setSaving(false);
    }
  };

  // THE PICKABLE UNIVERSE (any active staff, any role — an owner can still name a manager
  // explicitly) IS NOT THE SAME SET AS THE UNRESTRICTED DEFAULT (field-role only, server-side —
  // see Service.eligible_staff_ids's own docstring above). Two different questions: "who may I
  // choose from" vs "who is chosen when I choose nobody".
  const allActiveIds = (staff ?? []).filter((s) => s.active !== false).map((s) => s.id);
  const fieldActiveIds = (staff ?? [])
    .filter((s) => s.active !== false && s.role === 'operator').map((s) => s.id);

  /**
   * Toggle one operator's eligibility for one service.
   *
   * NEVER STORES "THE FIELD DEFAULT, NAMED" — the moment the resulting set is EXACTLY the
   * field-role default, it is written back as `[]` rather than that same list spelled out. `[]`
   * and "every field operator by name" read the same today, but only `[]` still means that the
   * day a new field hire joins — a named list would silently exclude him from a service nobody
   * meant to restrict.
   */
  const toggleEligible = async (svc: Service, operatorId: string) => {
    // «الافتراضي بلا قيد» — الموظفون الميدانيون فقط
    const current = svc.eligible_staff_ids && svc.eligible_staff_ids.length > 0
      ? new Set(svc.eligible_staff_ids)
      : new Set(fieldActiveIds);
    if (current.has(operatorId)) current.delete(operatorId); else current.add(operatorId);
    const isExactlyTheDefault = current.size === fieldActiveIds.length
      && fieldActiveIds.every((id) => current.has(id));
    const eligible_staff_ids = isExactlyTheDefault ? [] : [...current];
    await patchService(svc.id, { eligible_staff_ids });
  };

  /** Which operator ids `svc` is currently eligible for — unrestricted reads as every field-role
   *  operator (the server's own default), never every active operator regardless of role. */
  const eligibleIdsFor = (svc: Service): string[] => {
    return svc.eligible_staff_ids && svc.eligible_staff_ids.length > 0
      ? svc.eligible_staff_ids.filter((id) => allActiveIds.includes(id))
      : fieldActiveIds;
  };

  /** FilterMenu only ever hands back "the new full selection" — the actual write is one
   *  operator's toggle, found by diffing against what was selected a moment ago. */
  const onEligibleChange = (svc: Service, next: string[]) => {
    const before = eligibleIdsFor(svc);
    const changedId = next.find((id) => !before.includes(id))
      ?? before.find((id) => !next.includes(id));
    if (changedId) toggleEligible(svc, changedId);
  };

  const setAssignmentMode = async (svc: Service, mode: 'named' | 'auto') => {
    if (mode === svc.assignment_mode) return;
    await patchService(svc.id, { assignment_mode: mode });
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
      setError(sentenceFor(e, t('services.error.leaveGroupFailed'), t));
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
      setError(sentenceFor(e, t('services.error.deleteGroupFailed'), t));
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
   * home; the twelve others live in «الحملات», and this one is repeated here because this is the
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
      setError(sentenceFor(e, t('services.error.visitSettingFailed'), t));
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
      setError(sentenceFor(e, t('services.error.generalSettingFailed'), t));
    } finally {
      setSaving(false);
    }
  };

  // A DIFFERENT PEER FROM THE OTHER THREE ROWS IN THIS SAME CARD — reminders owns the cycle and
  // the follow-up, loyalty owns the points, and the card only exists to be "one place for every
  // service-wide default" (the owner's own ask: he was setting this on «نقاطي» and had no reason
  // to expect a second, separate general setting to live on a different screen entirely).
  const setGeneralPoints = async (n: number) => {
    const a = action(catalog, 'loyalty.settings.general');
    if (!a) return;
    setSaving(true); setError('');
    try {
      await call(session, a, { points: n });
      load();
    } catch (e) {
      setError(sentenceFor(e, t('services.error.generalSettingFailed'), t));
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
      setError(sentenceFor(e, t('services.error.saveFailed'), t));
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
      {packagesEnabled || proceduresEnabled ? (
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
            ...(packagesEnabled ? [{ value: 'packages' as const, label: t('services.packagesTab') }] : []),
            ...(proceduresEnabled
              ? [{ value: 'procedures' as const, label: t('procedures.tab') }] : []),
          ]}
        />
      ) : null}
    </>
  );

  // GROUPING/FILTERING, COMPUTED ONCE PER MEANINGFUL CHANGE — not on every render. This was an
  // IIFE inline in the JSX, so it reran (and re-grouped every service) on every keystroke while
  // editing a service field, not just when the underlying list, settings, tab, or filter changed.
  // Placed BEFORE every early return below (hooks must run in the same order on every render,
  // including the «packages» tab and loading/failed/empty states) — guarded internally since
  // `services` isn't narrowed to a real array at this point yet.
  const { stoppedCount, view, visible, bins, shown } = useMemo(() => {
    if (!isReady(services)) {
      return { stoppedCount: 0, view: 'active' as const, visible: [] as Service[],
        bins: [] as [string, Service[]][], shown: [] as [string, Service[]][] };
    }
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
    return { stoppedCount, view, visible, bins, shown };
  }, [services, settings, show, only]);

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

  // «الإجراءات» IS ITS OWN SELF-CONTAINED SUB-COMPONENT TOO — same reasoning as «الباقات» right
  // above: it does not depend on `services`/`settings` having loaded here, so it short-circuits
  // before every guard below that is all about the SERVICES tab's own data.
  if (tab === 'procedures') {
    return (
      <div className="flex flex-col gap-3 p-4">
        {switcher}
        <ProcedureStepsTab session={session} catalog={catalog} />
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
        <Card className="p-4">
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
                className="h-10 flex-1 rounded-lg border border-border-subtle bg-surface-1 px-3"
              />
              <Button disabled={saving || !naming.trim()} onClick={() => makeGroup(naming)}>
                {t('services.save')}
              </Button>
              <Button variant="ghost" onClick={() => setNaming(null)}>{t('services.cancel')}</Button>
            </div>
          )}
        </Card>
      ) : null}

      {/* ── the rail: his own groups, as navigation ──────────────────────────────────────────
          DERIVED FROM `grouped`, NEVER FROM A LIST OF ITS OWN. It carries exactly the headings
          below it and counts the same services, so a group he makes appears here the moment it
          exists and one he deletes leaves — there is nothing to keep in step. */}
      {(() => {
        // `stoppedCount`, `view`, `visible`, `bins`, `shown` come from the memoized pipeline above.
        return (
      <div className="flex items-start gap-4">
      {/* ── THE SIDEBAR RAIL — his own groups, as real navigation, colour-coded ──────────────
          REPLACES THE OLD DROPDOWN (2026-09-14, the owner's own request: "مساحة عمل احترافية …
          تمايز لوني عالي"). Same data the dropdown always read (`bins`/`only`/`setOnly` —
          nothing new is fetched), just shown as a real rail instead of a one-line `<select>`,
          each group carrying a fixed colour from the SAME categorical palette the sidebar's own
          nav icons use (`NAV_ACCENTS`, never the brand accent — that stays reserved for "press
          this button" per the 60-30-10 rule nav.ts's own comment states). The colour is derived
          from the group's own position in `bins`, so it never depends on group content and never
          collides with a semantic colour (danger/warning/success). */}
      {action(catalog, 'reminders.set_group') && bins.length > 1 ? (
        <aside className="hidden w-48 shrink-0 flex-col gap-1 rounded-card border border-border-subtle
                          bg-surface-1 p-2 shadow-sm sm:flex">
          <button
            type="button"
            onClick={() => setOnly(null)}
            className={[
              'flex items-center gap-2 rounded-lg px-3 py-2 text-start text-sm font-medium transition-colors',
              only === null ? 'bg-accent-soft text-accent-on-soft' : 'text-text-secondary hover:bg-surface-2',
            ].join(' ')}
          >
            <span className="size-2 shrink-0 rounded-full bg-text-primary" aria-hidden />
            <span className="min-w-0 flex-1 truncate">{tf(t, 'services.allGroups', { n: visible.length })}</span>
          </button>
          <div className="my-1 border-t border-border-subtle" />
          {bins.map(([g, list], i) => (
            <div key={g || 'ungrouped'} className="group/g flex items-center">
              <button
                type="button"
                onClick={() => setOnly(g)}
                className={[
                  'flex min-w-0 flex-1 items-center gap-2 rounded-lg px-3 py-2 text-start text-sm font-medium transition-colors',
                  only === g ? 'bg-accent-soft text-accent-on-soft' : 'text-text-secondary hover:bg-surface-2',
                ].join(' ')}
              >
                <span className="size-2 shrink-0 rounded-full"
                     style={{ background: g === UNGROUPED ? 'var(--text-muted)' : NAV_ACCENTS[i % NAV_ACCENTS.length] }}
                     aria-hidden />
                <span className="min-w-0 flex-1 truncate">
                  {g === UNGROUPED ? t('services.ungroupedHeading') : g}
                </span>
                <span className="shrink-0 text-xs tabular-nums text-text-muted">{list.length}</span>
              </button>
              {/* THE GROUP CAN BE UNMADE — restored here (the sidebar rail) after the table (its
                  only home before) was removed entirely (2026-09-15). Not offered on the
                  remainder bin: «غير مجمّعة» is not a group, and a delete button on it would
                  delete nothing. Shown on hover only, so the rail stays calm while browsing. */}
              {g !== UNGROUPED && action(catalog, 'reminders.delete_group') ? (
                <button
                  type="button"
                  disabled={saving}
                  aria-label={tf(t, 'services.deleteGroupAriaLabel', { group: g })}
                  onClick={() => deleteGroup(g)}
                  className="grid size-7 shrink-0 place-items-center rounded-lg text-text-muted opacity-0 transition-opacity hover:bg-danger-soft hover:text-danger-on-soft group-hover/g:opacity-100"
                >
                  <Trash2 size={14} aria-hidden />
                </button>
              ) : null}
            </div>
          ))}
        </aside>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col gap-3">
      {/* ── one toolbar, and nothing beside the table ───────────────────────────────────────
          THE GENERAL SETTING IS A LINE, NOT A CARD. As a bordered box with a folded panel it read
          like an input at the top of the screen — the owner's own words were that it looked like a
          field he had to fill. It states what it is and opens only when he asks. */}
      <div className="flex flex-wrap items-center gap-2">
        {/* THE DROPDOWN FILTER — kept as a small-screen fallback for the same filter, since the
            rail above hides below `sm` (a column of group buttons does not fit a phone's width
            beside the table it is meant to filter). */}
        {action(catalog, 'reminders.set_group') && bins.length > 1 ? (
          <select
            aria-label={t('services.filterByGroup')}
            value={only ?? ''}
            onChange={(e) => setOnly(e.target.value === '' ? null : e.target.value)}
            className="h-10 rounded-lg border border-border-subtle bg-surface-1 px-3 text-sm sm:hidden"
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

        {/* ONE «؟» FOR THE TABLE, NOT ONE PER COLUMN. Four marks across a header sixty-four
            pixels per column wide crowded into each other and spilled onto the neighbouring
            label — «النقاط؟» reading as one word. A legend answers all four at once, in a
            sentence each, and the header goes back to being four words. */}
        <Button type="button" variant="ghost" size="sm"
               aria-expanded={Boolean(asked)}
               onClick={() => setAsked(asked ? null : 'legend')}>
          <CircleHelp size={15} aria-hidden />
          {asked ? t('services.hideExplain') : t('services.showExplain')}
        </Button>

        {/* «الإعداد العام» MOVED HERE, out of its own row below the toolbar — the same kind of
            ask as the two buttons beside it ("show me something about this list"), so it earns
            the same spot rather than a whole line of its own. The panel it opens still renders
            below the table header, unchanged — only the trigger moved. */}
        {action(catalog, 'reminders.set_general') ? (
          <Button type="button" variant="ghost" size="sm"
                 aria-expanded={openGeneral}
                 onClick={() => setOpenGeneral((v) => !v)}>
            <SlidersHorizontal size={15} aria-hidden />
            {t('services.generalSetting')}
            <span className="tabular-nums text-text-muted">
              {summarise(t, {
                interval_days: settings?.general?.interval_days,
                follow_up_days: settings?.general?.follow_up_days,
              })}
            </span>
          </Button>
        ) : null}

        {action(catalog, 'operations.bulk_import_services') && !adding ? (
          <Button className={action(catalog, 'operations.create_service') ? undefined : 'ms-auto'}
                 variant="outline" onClick={() => setImporting(true)}>
            <Upload size={15} aria-hidden />
            {t('services.importFromFile')}
          </Button>
        ) : null}

        {action(catalog, 'operations.create_service') && !adding ? (
          <Button className="ms-auto" onClick={() => { setModalSvc(null); setAdding(true); }}>
            <Plus size={16} aria-hidden />
            {t('services.addServiceOrProduct')}
          </Button>
        ) : null}
      </div>

      <ServicesImportDrawer session={session} catalog={catalog}
                           existing={(services ?? []).map((s) => ({ name: s.name, active: s.active }))}
                           open={importing} onClose={() => setImporting(false)} onImported={load} />

      {action(catalog, 'reminders.set_general') && openGeneral ? (
        <>
          <Card className="flex flex-col gap-2 p-4">
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

            {action(catalog, 'loyalty.settings.general') ? (
              <Setting
                label={t('services.pointsPerVisit.label')}
                name={t('services.pointsPerVisit.name')}
                meaning={t('services.pointsPerVisit.meaning')}
                value={earn?.general?.points}
                preview={(n) => tf(t, 'services.pointsPerVisit.preview', { n })}
                zero={t('services.pointsPerVisit.zero')}
                onSave={setGeneralPoints}
              />
            ) : null}

            {/* ── the confirmation of the visit itself ──────────────────────────────────────
                NOT A NUMBER, SO NOT A `Setting`. The other two rows answer "after how many
                days"; this one answers "at all?".

                AND IT IS A TRIGGER'S SWITCH, not a setting of its own. It lived in the settings
                tree for a day — which became two switches for one behaviour the moment every
                message got one, and two switches for one behaviour is one of them quietly doing
                nothing. The other twelve live in «الحملات»; this one stays here too because it is
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
          </Card>
        </>
      ) : null}

      <div className="flex flex-col gap-3">

          {/* A REAL WINDOW, NOT A PANEL WEDGED INTO THE GRID (2026-09-15, owner's own call after
              seeing the shipped result: "خلي اضافة منتج يفتح نافذه", matching the approved
              mockup). Adding is a focused act with nothing worth seeing behind it — unlike
              editing, which stays in the docked inspector so the grid he is browsing never
              disappears. Same shared <Modal> every other screen already reaches for (Escape,
              scrim, scroll-lock — nothing reimplemented here), same fields as the inspector's
              own six-cell grid so "add" and "edit" never look like two different products. */}
          <Modal
            open={Boolean(action(catalog, 'operations.create_service') && adding)}
            onClose={() => { setAdding(false); setPendingImage(null); }}
            title={t('services.addServiceOrProduct')}
            footer={
              <div className="flex w-full items-center justify-end gap-2">
                <Button type="button" variant="ghost"
                       onClick={() => { setAdding(false); setPendingImage(null); }}>{t('services.cancel')}</Button>
                <Button type="submit" form="add-service-form" disabled={saving}>{t('services.add')}</Button>
              </div>
            }
          >
            <form
              id="add-service-form"
              className="flex flex-col gap-4"
              onSubmit={(e) => {
                e.preventDefault();
                const f = new FormData(e.currentTarget);
                const pts = String(f.get('points') || '').trim();
                const priceText = String(f.get('price') || '').trim();
                // SAME SILENT DROP AS THE INSPECTOR'S OWN PRICE CELL, caught here before the
                // create call rather than inside it: `halalas` returning null for typed-but-
                // invalid text used to fall into the same branch as an empty box, so «إضافة»
                // created the service with no price at all and said nothing about why.
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
              {/* THE PHOTO STAYS ON THIS SIDE OF THE NETWORK UNTIL «إضافة». There is no
                  server-side draft for it — nothing to attach a file to before a service id
                  exists — so the "hold it, only real if confirmed" behaviour is just this: a
                  File object living in `pendingImage`, never read by anything until submit calls
                  uploadServiceImage() with the real id, and dropped untouched on cancel (or on a
                  second pick, which replaces rather than adds to it — one photo per service, same
                  as the inspector's own edit view). Styled as a real dropzone, not a native
                  file-picker button, matching the approved mockup. */}
              {action(catalog, 'operations.upload_service_image') ? (
                <label className="relative flex aspect-[16/9] cursor-pointer flex-col items-center justify-center gap-1.5 rounded-lg border border-dashed border-border-strong bg-surface-1 text-text-muted transition-colors hover:border-accent hover:text-accent-on-soft">
                  {pendingImage ? (
                    <img src={pendingImageUrl ?? ''} alt=""
                        className="absolute inset-0 h-full w-full rounded-lg object-cover" />
                  ) : (
                    <>
                      <Upload size={22} aria-hidden />
                      <span className="text-xs font-medium">صورة الخدمة (اختياري)</span>
                    </>
                  )}
                  <input type="file" accept="image/jpeg,image/png,image/webp" className="hidden"
                         onChange={(e) => setPendingImage(e.target.files?.[0] ?? null)} />
                </label>
              ) : null}

              <label className="flex flex-col gap-1">
                <span className="text-xs font-medium text-text-secondary">{t('services.name')}</span>
                <input name="name" required autoFocus maxLength={128}
                       placeholder={t('services.name.placeholder')}
                       className="h-10 rounded-lg border border-border-subtle bg-surface-1 px-3 text-sm font-medium" />
              </label>

              {/* SAME BOX, SAME WORDING, AS THE INSPECTOR'S OWN EDIT FIELD — this is the same
                  `description` the server already accepts on create, not a new one added just
                  for this form. */}
              <label className="flex flex-col gap-1">
                <span className="text-xs font-medium text-text-secondary">وصف قصير (اختياري)</span>
                <textarea name="description" maxLength={300} rows={2}
                          placeholder="وصف قصير (يستخدمه الذكاء الاصطناعي بالواتساب)"
                          className="w-full rounded-lg border border-border-subtle bg-surface-1 px-3 py-2 text-sm" />
              </label>

              {/* SIX CELLS, ALWAYS — the same field-grid shape the inspector uses, so a field
                  granted or withheld by permission never leaves an orphan cell breaking the
                  two-column rhythm (the exact defect the owner flagged in the old list form). */}
              <div className="grid grid-cols-2 gap-3">
                <label className="flex flex-col gap-1">
                  <span className="text-xs font-medium text-text-secondary">{t('services.duration.label')}</span>
                  <input name="duration_minutes" type="number" min={0} max={720} step={15} defaultValue={15} dir="ltr"
                         className="h-10 rounded-lg border border-border-subtle bg-surface-1 px-2 text-center font-mono tabular-nums" />
                </label>
                <label className="flex flex-col gap-1">
                  <span className="text-xs font-medium text-text-secondary">{t('services.price.label')}</span>
                  <input name="price" type="text" inputMode="decimal" dir="ltr" placeholder="—"
                         className="h-10 rounded-lg border border-border-subtle bg-surface-1 px-2 text-center font-mono tabular-nums" />
                </label>
                <label className="flex flex-col gap-1">
                  <span className="text-xs font-medium text-text-secondary">{t('services.reminderCycle.label')}</span>
                  <input name="cycle_days" type="number" min={0} defaultValue={0} dir="ltr"
                         className="h-10 rounded-lg border border-border-subtle bg-surface-1 px-2 text-center font-mono tabular-nums" />
                </label>
                {action(catalog, 'reminders.set_service_settings') ? (
                  <label className="flex flex-col gap-1">
                    <span className="text-xs font-medium text-text-secondary">{t('services.followUp')}</span>
                    <input name="follow_up_days" type="number" min={0} defaultValue={0} dir="ltr"
                           className="h-10 rounded-lg border border-border-subtle bg-surface-1 px-2 text-center font-mono tabular-nums" />
                  </label>
                ) : null}
                {earnAction ? (
                  <label className="flex flex-col gap-1">
                    <span className="text-xs font-medium text-text-secondary">{t('services.points')}</span>
                    <input name="points" type="number" min={0} dir="ltr"
                           placeholder={String(earn?.general?.points ?? 0)}
                           className="h-10 rounded-lg border border-border-subtle bg-surface-1 px-2 text-center font-mono tabular-nums" />
                  </label>
                ) : null}
                {action(catalog, 'reminders.set_group') ? (
                  <label className="flex flex-col gap-1">
                    <span className="text-xs font-medium text-text-secondary">{t('services.group')}</span>
                    <select name="group" className="h-10 rounded-lg border border-border-subtle bg-surface-1 px-2 text-sm">
                      <option value="">{t('services.noGroupOption')}</option>
                      {Object.keys(settings?.groups ?? {}).map((g) => (
                        <option key={g} value={g}>{g}</option>
                      ))}
                    </select>
                  </label>
                ) : null}
              </div>
            </form>
          </Modal>

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
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {shown.flatMap(([, inGroup]) => inGroup).map((svc) => {
            const stopped = svc.active === false;
            const selected = modalSvc === svc.id;
            return (
              <Card key={svc.id}
                  className={[
                    'flex flex-col overflow-hidden p-0',
                    'transition-all duration-200 hover:-translate-y-0.5 hover:shadow-pop',
                    selected ? 'border-accent' : '',
                    stopped ? 'opacity-60' : '',
                  ].join(' ')}>
                {/* A REAL PHOTO, LARGE, OR A NEUTRAL PLACEHOLDER — never a blank box. The absence
                    of a photo is a fact worth seeing at a glance (an owner missing photos across
                    his catalogue should notice), not something the layout quietly hides. The
                    active/stopped state rides on the photo itself as a small pill (2026-09-14
                    workspace redesign) rather than a badge beside the name below, matching the
                    approved mockup's own "shape carries state" convention. */}
                <div className="relative aspect-[16/10] overflow-hidden bg-gradient-to-br from-accent-soft to-surface-2">
                  {images[svc.id] ? (
                    <img src={images[svc.id]} alt="" className="h-full w-full object-cover" />
                  ) : (
                    <div className="grid h-full place-items-center text-accent-on-soft opacity-60">
                      <ImageOff size={28} aria-hidden />
                    </div>
                  )}
                  <span className={[
                    'absolute top-2.5 rounded-full px-2.5 py-1 text-[10px] font-bold',
                    stopped ? 'end-2.5 bg-danger text-danger-contrast'
                            : 'start-2.5 bg-text-primary/55 text-white backdrop-blur',
                  ].join(' ')}>
                    {stopped ? t('services.stoppedBadge') : t('services.active')}
                  </span>
                </div>
                <div className="flex flex-1 flex-col gap-2 p-3.5 pb-3">
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="min-w-0 truncate text-[15px] font-bold">{svc.name}</h3>
                    <span className="shrink-0 whitespace-nowrap font-mono text-sm font-bold text-accent-on-soft tabular-nums">
                      {svc.price_minor ? riyals(svc.price_minor) : '—'}
                    </span>
                  </div>
                  <p className="line-clamp-2 min-h-[2.6em] text-xs text-text-secondary">
                    {svc.description || ' '}
                  </p>
                  {svc.duration_minutes ? (
                    <div className="mt-auto border-t border-border-subtle pt-2 text-[11.5px] text-text-muted">
                      {tf(t, 'services.duration.cardValue', { n: svc.duration_minutes })}
                    </div>
                  ) : null}
                </div>
                {action(catalog, 'operations.update_service') ? (
                  <div className="flex border-t border-border-subtle">
                    <button type="button" onClick={() => setModalSvc(svc.id)}
                           className="flex flex-1 items-center justify-center gap-1.5 border-e border-border-subtle py-2 text-xs font-medium text-text-secondary transition-colors hover:bg-accent-soft hover:text-accent-on-soft">
                      <Pencil size={14} aria-hidden /> {t('services.edit')}
                    </button>
                    <button type="button" disabled={saving}
                           onClick={() => requestStop(svc)}
                           className={[
                             'flex flex-1 items-center justify-center gap-1.5 py-2 text-xs font-medium transition-colors',
                             stopped ? 'text-text-secondary hover:bg-surface-2'
                                     : 'text-danger hover:bg-danger-soft',
                           ].join(' ')}>
                      {stopped
                        ? <Power size={14} aria-hidden />
                        : <PowerOff size={14} aria-hidden />}
                      {stopped ? t('services.activate') : t('services.deactivateShort')}
                    </button>
                  </div>
                ) : null}
              </Card>
            );
          })}
        </div>
      </div>
      {/* closes the min-w-0 flex-1 column beside the sidebar rail */}
      </div>

      {/* ── RIGHT: the inspector — docked, always occupying its own pane, never a floating modal
          (2026-09-14 workspace redesign, replacing the old <Modal>; 2026-09-15: the table/list
          layout it once coexisted with is gone entirely — this workspace is the only view now).
          Same fields, same save-on-blur handlers as before (patchService/setService/
          setServicePoints/uploadServiceImage — nothing here is a second source of truth). */}
      {(() => {
        const svc = (services ?? []).find((s) => s.id === modalSvc);
        if (!svc) {
          return (
            <aside className="hidden w-[22rem] shrink-0 flex-col items-center justify-center gap-2
                              rounded-card border border-dashed border-border-strong p-6
                              text-center text-sm text-text-muted lg:flex">
              <SlidersHorizontal size={22} aria-hidden />
              <span>{t('services.inspector.empty')}</span>
            </aside>
          );
        }
        const { value, own } = settingFor(svc.id);
        const stopped = svc.active === false;
        return (
          <aside className="flex w-[22rem] shrink-0 flex-col rounded-card border border-accent
                            bg-surface-1 shadow-sm">
            <div className="flex items-center justify-between gap-2 border-b border-border-subtle px-4 py-3">
              <h3 className="truncate text-sm font-bold">{svc.name}</h3>
              <button type="button" onClick={() => setModalSvc(null)}
                     aria-label={t('services.finishEditing')}
                     className="grid size-7 shrink-0 place-items-center rounded-lg text-text-secondary hover:bg-surface-2">
                ✕
              </button>
            </div>
            <div className="flex flex-col gap-4 overflow-y-auto p-4">
              <div className="relative aspect-[16/10] overflow-hidden rounded-lg bg-surface-1">
                {images[svc.id] ? (
                  <img src={images[svc.id]} alt="" className="h-full w-full object-cover" />
                ) : (
                  <div className="grid h-full place-items-center text-text-muted">
                    <ImageOff size={28} aria-hidden />
                  </div>
                )}
                {action(catalog, 'operations.upload_service_image') ? (
                  <div className="absolute inset-x-0 bottom-0 flex items-center justify-between gap-2 bg-gradient-to-t from-black/60 to-transparent p-2.5">
                    <label className="flex cursor-pointer items-center gap-1.5 rounded-lg bg-surface-1/90 px-2.5 py-1 text-[11px] font-medium text-text-primary shadow-sm backdrop-blur">
                      <Upload size={12} aria-hidden /> {svc.has_image ? 'استبدال الصورة' : 'صورة'}
                      <input type="file" accept="image/jpeg,image/png,image/webp" className="hidden"
                            onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadServiceImage(svc.id, f); }} />
                    </label>
                  </div>
                ) : null}
              </div>

              <label className="flex flex-col gap-1">
                <span className="text-xs font-medium text-text-secondary">{t('services.name')}</span>
                <input
                  defaultValue={svc.name}
                  maxLength={128}
                  onBlur={(e) => { const v = e.target.value.trim(); if (v && v !== svc.name) patchService(svc.id, { name: v }); }}
                  className="h-10 rounded-lg border border-border-subtle bg-surface-1 px-3 text-sm font-medium"
                />
              </label>

              <label className="flex flex-col gap-1">
                <span className="text-xs font-medium text-text-secondary">وصف قصير (اختياري)</span>
                <textarea
                  defaultValue={svc.description ?? ''}
                  maxLength={300}
                  rows={2}
                  placeholder="وصف قصير (يستخدمه الذكاء الاصطناعي بالواتساب)"
                  onBlur={(e) => { const v = e.target.value.trim(); if (v !== (svc.description ?? '')) patchService(svc.id, { description: v }); }}
                  className="w-full rounded-lg border border-border-subtle bg-surface-1 px-3 py-2 text-sm"
                />
              </label>

              <div className="grid grid-cols-2 gap-3">
                <label className="flex flex-col gap-1">
                  <span className="text-xs font-medium text-text-secondary">{t('services.duration.label')}</span>
                  <input type="number" min={0} max={720} dir="ltr"
                        defaultValue={svc.duration_minutes ? String(svc.duration_minutes) : ''}
                        onBlur={(e) => {
                          const raw = e.target.value.trim();
                          if (raw === '') return;
                          const n = Number(raw);
                          if (n !== (svc.duration_minutes ?? 0)) patchService(svc.id, { duration_minutes: n });
                        }}
                        className="h-10 rounded-lg border border-border-subtle bg-surface-1 px-2 text-center font-mono tabular-nums" />
                </label>
                <label className="flex flex-col gap-1">
                  <span className="text-xs font-medium text-text-secondary">{t('services.price.label')}</span>
                  <input type="text" inputMode="decimal" dir="ltr" placeholder="—"
                        defaultValue={svc.price_minor ? riyals(svc.price_minor) : ''}
                        onBlur={(e) => {
                          const raw = e.target.value.trim();
                          if (raw === '') return;
                          const minor = halalas(raw);
                          if (minor === null) { setError(t('services.error.priceInvalid')); return; }
                          if (minor !== svc.price_minor) patchService(svc.id, { price_minor: minor });
                        }}
                        className="h-10 rounded-lg border border-border-subtle bg-surface-1 px-2 text-center font-mono tabular-nums" />
                </label>
                {action(catalog, 'reminders.set_service_settings') ? (
                  <>
                    <label className="flex flex-col gap-1">
                      <span className="text-xs font-medium text-text-secondary">{t('services.reminderCycle.label')}</span>
                      <input type="number" min={0} dir="ltr"
                            defaultValue={value.interval_days ? String(value.interval_days) : ''}
                            placeholder={own ? '0' : String(value.interval_days ?? 0)}
                            onBlur={(e) => {
                              const raw = e.target.value.trim();
                              if (raw === '') return;
                              const n = Number(raw);
                              if (n !== (value.interval_days ?? 0)) setService(svc.id, { interval_days: n });
                            }}
                            className="h-10 rounded-lg border border-border-subtle bg-surface-1 px-2 text-center font-mono tabular-nums" />
                    </label>
                    <label className="flex flex-col gap-1">
                      <span className="text-xs font-medium text-text-secondary">{t('services.followUp')}</span>
                      <input type="number" min={0} dir="ltr"
                            defaultValue={value.follow_up_days ? String(value.follow_up_days) : ''}
                            placeholder={own ? '0' : String(value.follow_up_days ?? 0)}
                            onBlur={(e) => {
                              const raw = e.target.value.trim();
                              if (raw === '') return;
                              const n = Number(raw);
                              if (n !== (value.follow_up_days ?? 0)) setService(svc.id, { follow_up_days: n });
                            }}
                            className="h-10 rounded-lg border border-border-subtle bg-surface-1 px-2 text-center font-mono tabular-nums" />
                    </label>
                  </>
                ) : null}
                {earnAction ? (
                  <label className="flex flex-col gap-1">
                    <span className="text-xs font-medium text-text-secondary">{t('services.points')}</span>
                    <input type="number" min={0} dir="ltr"
                          defaultValue={earnFor(svc.id).own ? String(earnFor(svc.id).points) : ''}
                          placeholder={String(earnFor(svc.id).points)}
                          onBlur={(e) => {
                            const raw = e.target.value.trim();
                            if (raw === '') return;
                            const n = Number(raw);
                            if (n !== earnFor(svc.id).points) setServicePoints(svc.id, n);
                          }}
                          className="h-10 rounded-lg border border-border-subtle bg-surface-1 px-2 text-center font-mono tabular-nums" />
                  </label>
                ) : null}
              </div>

              {action(catalog, 'reminders.set_group') ? (
                <label className="flex flex-col gap-1">
                  <span className="text-xs font-medium text-text-secondary">{t('services.group')}</span>
                  <select
                    value={settings?.service_group?.[svc.id] ?? ''}
                    onChange={(e) => {
                      const v = e.target.value;
                      if (v === '__new__') { setNaming(svc.id); return; }
                      if (!v) { leaveGroup(svc.id); return; }
                      joinGroup(svc.id, v);
                    }}
                    className="h-10 w-full rounded-lg border border-border-subtle bg-surface-1 px-2 text-sm"
                  >
                    <option value="">{t('services.noGroupOption')}</option>
                    {Object.keys(settings?.groups ?? {}).map((g) => (
                      <option key={g} value={g}>{g}</option>
                    ))}
                    <option value="__new__">{t('services.newGroupOption')}</option>
                  </select>
                </label>
              ) : null}

              {/* THE NEW-GROUP BOX — same «__new__» affordance the select above just offered,
                  restored here after the table (its only home before) was removed entirely
                  (2026-09-15). */}
              {naming === svc.id ? (
                <div className="flex items-center gap-2">
                  <input
                    autoFocus
                    aria-label={t('services.newGroupNameAriaLabel')}
                    placeholder={t('services.newGroupPlaceholder')}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') joinGroup(svc.id, e.currentTarget.value);
                      if (e.key === 'Escape') setNaming(null);
                    }}
                    className="h-9 flex-1 rounded-lg border border-border-subtle bg-surface-1 px-3 text-sm"
                  />
                  <Button variant="ghost" size="sm" onClick={() => setNaming(null)}>{t('services.cancel')}</Button>
                </div>
              ) : null}

              {/* «من يقدر يسوّيها» — يظهر فقط حين يوجد أكثر من موظف نشط واحد؛ محل بموظف واحد لا
                  يرى هذا القسم إطلاقاً لأنه لا معنى له. كان يعيش داخل صف التعديل بالجدول قبل
                  حذفه كاملاً (2026-09-15) — استُعيد هنا، بنفس المعالجات تماماً، لأنه ميزة حقيقية
                  لا شاشة عرض جانبية. */}
              {(staff ?? []).filter((s) => s.active !== false).length > 1
                  && action(catalog, 'operations.update_service') ? (
                <div className="flex flex-col gap-2 border-t border-border-subtle pt-3">
                  <Segmented
                    size="sm"
                    ariaLabel={t('services.assignmentMode.ariaLabel')}
                    value={svc.assignment_mode === 'named' ? 'named' : 'auto'}
                    onChange={(v) => setAssignmentMode(svc, v as 'named' | 'auto')}
                    options={[
                      { value: 'auto', label: t('services.assignmentMode.auto'),
                       hint: t('services.assignmentMode.auto.hint') },
                      { value: 'named', label: t('services.assignmentMode.named'),
                       hint: t('services.assignmentMode.named.hint') },
                    ]}
                  />
                  <p className="text-xs text-text-secondary">
                    {svc.assignment_mode === 'named'
                      ? t('services.assignmentMode.named.hint')
                      : t('services.assignmentMode.auto.hint')}
                  </p>
                  <FilterMenu
                    label={t('services.whoCanDoIt')}
                    options={(staff ?? []).filter((s) => s.active !== false)
                      .map((s) => ({ value: s.id, label: s.name }))}
                    selected={eligibleIdsFor(svc)}
                    onChange={(next) => onEligibleChange(svc, next)}
                  />
                </div>
              ) : null}
            </div>
            {action(catalog, 'operations.update_service') ? (
              <div className="flex items-center justify-between border-t border-border-subtle px-4 py-3">
                <span className="text-xs text-text-secondary">
                  {stopped ? t('services.stoppedBadge') : t('services.active')}
                </span>
                <Button variant={stopped ? 'solid' : 'outline'} size="sm"
                       onClick={() => requestStop(svc)}>
                  {stopped
                    ? <Power size={14} aria-hidden />
                    : <PowerOff size={14} aria-hidden />}
                  {stopped ? t('services.activate') : t('services.deactivateShort')}
                </Button>
              </div>
            ) : null}
          </aside>
        );
      })()}
      </div>
        );
      })()}

      {/* THE LONG EXPLANATION MOVED HERE FROM THE BUTTON ITSELF — it used to be squeezed onto a
          card-row button ("إيقاف — تختفي من شاشة الزيارة وتسكت تذكيراتها"), unreadable at that
          size and wrapping over the tile's own layout. It belongs in the one moment he is actually
          deciding, not printed in miniature on every card all the time. */}
      <ConfirmDialog
        open={Boolean(confirmStopId)}
        onClose={() => setConfirmStopId(null)}
        onConfirm={() => {
          if (confirmStopId) patchService(confirmStopId, { active: false });
          setConfirmStopId(null);
        }}
        title={tf(t, 'services.deactivateConfirmTitle',
          { name: (services ?? []).find((s) => s.id === confirmStopId)?.name ?? '' })}
        body={t('services.deactivate')}
        confirmLabel={t('services.deactivateShort')}
        busy={saving}
      />
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
