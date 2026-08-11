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
import { useEffect, useState } from 'react';
import { Button } from '@base-ui/design-system/Button';
import { Badge } from '@base-ui/design-system/Badge';
import { Segmented } from '@base-ui/design-system/Segmented';
import { EmptyState } from '@base-ui/design-system/EmptyState';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import { Hint } from '../Hint';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';

interface Service { id: string; name: string; cycle_days: number; price_minor: number; catchall?: boolean; active?: boolean }

/** One service's entry in the tree, and whether it is its own or inherited. */
interface ServiceSetting { interval_days?: number; lead_days?: number; follow_up_days?: number; enabled?: boolean }
interface Settings {
  general: ServiceSetting;
  /** Only what a service OVERRIDES. Absent means it follows — following is not a value. */
  services: Record<string, ServiceSetting>;
  /** Group name → its settings, and service id → its group. Two maps, exactly as the tree holds
   *  them, so a service moving between groups stays one write rather than two. */
  groups: Record<string, ServiceSetting>;
  service_group: Record<string, string>;
}

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
function summarise(v: ServiceSetting): string {
  const parts: string[] = [];
  if (v.interval_days) parts.push(`كل ${v.interval_days} يوماً`);
  if (v.follow_up_days) parts.push(`واطمئنان بعد ${v.follow_up_days}`);
  // NOT «بلا دورة» WHEN A FOLLOW-UP EXISTS. A service with no cycle but a follow-up is a perfectly
  // ordinary thing — a one-off job you still check on — and the old line called it silent.
  return parts.length ? parts.join(' · ') : 'بلا دورة';
}

/** loyalty's settings tree, in the shape it answers with: a number per level, and where it came from. */
interface EarnSettings {
  general?: { points?: number };
  groups?: Record<string, { points?: number }>;
  services?: Record<string, { points?: number }>;
  service_group?: Record<string, string>;
}

export function ServicesScreen({ session, catalog }: { session: Session; catalog: Catalog }) {
  const [services, setServices] = useState<Service[] | null>(null);
  /** The list could not be READ — as opposed to being read and found empty. Two different facts,
   *  and this screen used to say the same sentence for both. */
  const [unread, setUnread] = useState(false);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null);
  /** The name box, shown only after he asks for the group — never as a field waiting to be filled. */
  const [naming, setNaming] = useState<string | null>(null);
  /**
   * THE POINTS EACH SERVICE EARNS — read here so the shortcut can show the INHERITED number too.
   *
   * Without it the field would render 0 for every service that simply follows the general rule,
   * and an owner reading a zero next to a service that does earn points would type the number
   * again — turning "follows the general setting" into a frozen copy that stops tracking it (§9.2).
   */
  const [earn, setEarn] = useState<EarnSettings | null>(null);
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
        .catch(() => { setServices([]); setUnread(true); });
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
    return { points: fromGroup ?? earn?.general?.points ?? 0, own: false };
  };

  const setServicePoints = async (serviceId: string, points: number) => {
    if (!earnAction) return;
    setSaving(true); setError('');
    try {
      await call(session, earnAction, { service_id: serviceId, points });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'تعذّر حفظ النقاط.');
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
      setError(e instanceof Error ? e.message : 'تعذّر إنشاء المجموعة.');
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
      setError(e instanceof Error ? e.message : 'تعذّر نقل الخدمة إلى المجموعة.');
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
  const addService = async (name: string, cycleDays: number) => {
    const a = action(catalog, 'operations.create_service');
    if (!a || !name.trim()) return;
    setSaving(true);
    setError('');
    try {
      await call(session, a, { name: name.trim(), cycle_days: cycleDays });
      setAdding(false);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'تعذّرت إضافة الخدمة.');
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
      setError(e instanceof Error ? e.message : 'تعذّر حفظ التعديل.');
    } finally {
      setSaving(false);
    }
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
      setError('هذا الإجراء جديد — أعد فتح الصفحة أو سجّل الدخول من جديد ليظهر.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      await call(session, a, { name, service_id: serviceId });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'تعذّر إخراج الخدمة من المجموعة.');
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
    if (!window.confirm(`حذف مجموعة «${name}»؟ تبقى خدماتها كما هي، بلا مجموعة.`)) return;
    setSaving(true);
    setError('');
    try {
      await call(session, a, { name });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'تعذّر حذف المجموعة.');
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
      setError(e instanceof Error ? e.message : 'تعذّر الحفظ.');
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

  if (services === null) return <div className="p-4"><Skeleton height={200} /></div>;

  if (services.length === 0) {
    // A SHOP SHOULD NEVER SEE THIS. Its catalogue is seeded full from its sector at creation
    // (§4.6) precisely so nobody starts from a blank page — so an empty list means the seeding did
    // not run, which is a fault to report rather than an invitation to type twenty services.
    return (
      <div className="p-4">
        <EmptyState
          title={unread ? 'تعذّر عرض خدماتك' : 'لا توجد خدمات'}
          description={unread
            ? 'خدماتك موجودة ولم نستطع قراءتها الآن. أعد المحاولة، وإن تكرّر فتواصل معنا.'
            : 'قائمة قطاعك تُضاف تلقائياً عند إنشاء الحساب — تواصل معنا إن بقيت فارغة.'}
          action={unread ? <Button onClick={load}>أعد المحاولة</Button> : undefined}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 p-4">
      {error ? <p className="text-danger">{error}</p> : null}

      {/* THE PROPOSAL, AND IT ONLY EVER PROPOSES. The engine noticed the owner set the same value
          on several services; it says so once, in the screen where those services are, and does
          nothing until he agrees. Rearranging his settings on his behalf is the fastest way to
          lose his trust in this page. */}
      {suggestion && action(catalog, 'reminders.set_group') ? (
        <div className="rounded-card border border-border-subtle bg-surface-1 p-4">
          <p className="text-sm">
            {`${suggestion.services.length} خدمات لها نفس الإعداد. تبغى تجمعها في مجموعة واحدة؟`}
          </p>
          <p className="mt-1 text-sm text-text-secondary">
            تعديل المجموعة بعدها يكفي عن تعديلها خدمةً خدمة.
          </p>
          {naming === null ? (
            <div className="mt-3 flex gap-2">
              <Button onClick={() => setNaming('')}>اجمعها</Button>
              {/* DISMISSED, NOT SAVED AS A REFUSAL. The suggestion is recomputed from his own
                  settings; if he changes them it should be free to reappear. */}
              <Button variant="ghost" onClick={() => setSuggestion(null)}>ليس الآن</Button>
            </div>
          ) : (
            <div className="mt-3 flex gap-2">
              <input
                autoFocus
                value={naming}
                onChange={(e) => setNaming(e.target.value)}
                placeholder="اسم المجموعة"
                className="h-10 flex-1 rounded-lg bg-surface-2 px-3"
              />
              <Button disabled={saving || !naming.trim()} onClick={() => makeGroup(naming)}>
                حفظ
              </Button>
              <Button variant="ghost" onClick={() => setNaming(null)}>إلغاء</Button>
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
      {/* SHOWN ONLY WHEN HE HAS STOPPED SOMETHING. A filter offering «الموقوفة» to a shop with
          none is a control that answers a question nobody asked, and it costs a line on a phone. */}
      {stoppedCount > 0 ? (
        <Segmented
          ariaLabel="عرض الخدمات والمنتجات"
          value={view}
          onChange={(v) => setShow(v as 'active' | 'stopped')}
          className="flex w-full [&>button]:flex-1 [&>button]:whitespace-nowrap"
          options={[
            // TWO, NOT THREE. «الكل» mixes what he sells with what he stopped, which is the
            // one view that answers no question: every ordinary edit becomes a matter of reading
            // past the dead lines, and finding a stopped one is what the second tab is for.
            { value: 'active', label: 'المفعّلة' },
            { value: 'stopped', label: `الموقوفة (${stoppedCount})` },
          ]}
        />
      ) : null}

      <div className="grid gap-4 md:grid-cols-[11rem_1fr]">
        <nav aria-label="مجموعات الخدمات" className="flex gap-2 overflow-x-auto md:flex-col md:overflow-visible">
          <button
            type="button"
            onClick={() => setOnly(null)}
            className={[
              'shrink-0 rounded-card px-3 py-2 text-start text-sm',
              only === null ? 'bg-accent-soft text-accent-on-soft' : 'bg-surface-1',
            ].join(' ')}
          >
            الكل <span className="tabular-nums text-text-secondary">{visible.length}</span>
          </button>
          {bins.map(([g, list]) => (
            <button
              key={g || 'ungrouped'}
              type="button"
              onClick={() => setOnly(g)}
              className={[
                'shrink-0 rounded-card px-3 py-2 text-start text-sm',
                only === g ? 'bg-accent-soft text-accent-on-soft' : 'bg-surface-1',
              ].join(' ')}
            >
              {g === UNGROUPED ? 'غير مجمّعة' : g}{' '}
              <span className="tabular-nums text-text-secondary">{list.length}</span>
            </button>
          ))}
        </nav>

        <div className="flex flex-col gap-3">
          {/* THE ACT THIS SCREEN IS NAMED FOR, and it was missing. «خدماتي» listed a catalogue and
              offered no way to add to it — a shop selling something new had nowhere to say so. */}
          {action(catalog, 'operations.create_service') ? (
            adding ? (
              <form
                className="flex flex-col gap-3 rounded-card bg-surface-1 p-4 shadow-sm"
                onSubmit={(e) => {
                  e.preventDefault();
                  const f = new FormData(e.currentTarget);
                  addService(String(f.get('name') || ''), Number(f.get('cycle_days') || 0));
                }}
              >
                <label className="flex flex-col gap-1">
                  <span className="text-sm">الاسم</span>
                  <input name="name" required autoFocus maxLength={128}
                         placeholder="مثال: تلميع وتشميع، أو كيس قهوة 250 جم"
                         className="h-10 rounded-lg bg-surface-2 px-3" />
                </label>
                <label className="flex items-center justify-between gap-3">
                  <span className="flex flex-col">
                    <span className="text-sm">كل كم يوماً يحتاجه العميل؟</span>
                    {/* ZERO IS A REAL ANSWER, not an empty field: a one-off job has no natural
                        cycle and must not produce a reminder. Said here rather than discovered. */}
                    <span className="text-sm text-text-secondary">
                      اتركه 0 إن كان لمرة واحدة — فلا تذكير له.
                    </span>
                  </span>
                  <input name="cycle_days" type="number" min={0} defaultValue={0} dir="ltr"
                         className="h-10 w-24 shrink-0 rounded-lg bg-surface-2 px-3 text-center tabular-nums" />
                </label>
                <div className="flex gap-2">
                  <Button type="submit" disabled={saving}>إضافة</Button>
                  <Button type="button" variant="ghost" onClick={() => setAdding(false)}>إلغاء</Button>
                </div>
              </form>
            ) : (
              <div>
                <Button onClick={() => setAdding(true)}>إضافة خدمة أو منتج</Button>
              </div>
            )
          ) : null}

      {shown.map(([group, inGroup]) => (
        <section key={group || 'ungrouped'} className="flex flex-col gap-3">
          {/* THE HEADING CARRIES THE GROUP'S OWN CYCLE, because that is what the services under it
              follow — a heading that is only a name leaves the owner reading each service to work
              out what the group actually does. The remainder bin has no settings and says so by
              carrying no number. */}
          <div className="flex items-center justify-between gap-3 px-1 pt-2">
            <h2 className="min-w-0 text-sm font-semibold text-text-secondary">
              {group === UNGROUPED ? 'غير مجمّعة' : group}
              {group !== UNGROUPED && settings?.groups?.[group]?.interval_days
                ? ` · كل ${settings.groups[group].interval_days} يوماً`
                : ''}
            </h2>
            {/* THE GROUP CAN BE UNMADE. It could be created and never removed, so an owner who
                grouped his services wrongly was stuck with the mistake on every future screen.
                Not offered on the remainder bin: «خدمات غير مجمّعة» is not a group, it is what is
                left over, and a delete button on it would be a delete of nothing. */}
            {group !== UNGROUPED && action(catalog, 'reminders.delete_group') ? (
              <Button variant="ghost" disabled={saving} onClick={() => deleteGroup(group)}>
                حذف المجموعة
              </Button>
            ) : null}
          </div>
          {inGroup.map((svc) => {
        const { value, own } = settingFor(svc.id);
        const isOpen = open === svc.id;
        return (
          <div key={svc.id} className="rounded-card bg-surface-1 shadow-sm">
            <button
              type="button"
              onClick={() => setOpen(isOpen ? null : svc.id)}
              className="flex w-full items-center justify-between px-4 py-3 text-start"
            >
              <span className="flex flex-col">
                <span>{svc.name}</span>
                {/* BOTH NUMBERS, BECAUSE HE SET BOTH. The line used to read only the cycle, so an
                    owner who typed 15 into «الاطمئنان», closed the row and saw «كل 10 يوماً» had
                    every reason to believe it had not saved — it had. A summary that reports one
                    of two saved values is worse than no summary: it is a confident wrong answer. */}
                <span className="text-sm text-text-secondary tabular-nums">
                  {summarise(value)}
                </span>
              </span>
              {/* SHOWN WHERE IT HAPPENED. Without this the owner cannot tell which services he has
                  customised, and a general change that "did not work" is really a service holding
                  its own value. */}
              <span className="flex items-center gap-2">
                {svc.active === false ? <Badge tone="neutral">موقوفة</Badge> : null}
                {own ? <Badge tone="accent">إعداد خاص</Badge> : null}
              </span>
            </button>

            {isOpen ? (
              <div className="flex flex-col gap-3 border-t border-border-subtle px-4 py-3">
                {/* THE REMINDER FIELDS ARE A SECOND CAPABILITY. The name and the price are
                    operations'; the cycle and the follow-up are reminders' — and a role can hold
                    one without the other. Rendering an input that will be refused teaches the
                    person the product is broken, so it is absent instead. */}
                {action(catalog, 'reminders.set_service_settings') ? (
                <>
                {/* TWO MESSAGES, AND THEY ARE NOT THE SAME MESSAGE. Rendered as two identical
                    number boxes they looked like one setting asked twice, and «الاطمئنان» was a
                    word with no meaning attached — the owner in the screenshot typed a number into
                    it without being told what it would send. Each now carries the sentence that
                    says what goes out and when, and a preview of the actual timing. */}
                <Setting
                  label="دورة التذكير"
                  meaning="الرسالة التي تُرجعه: تُرسَل حين يحين وقت الخدمة القادمة."
                  value={value.interval_days}
                  preview={(n) => `تذكير بعد ${n} يوماً من كل زيارة`}
                  zero="لا تذكير لهذه الخدمة"
                  // A BLANK FIELD IS NOT A ZERO. `Number('')` is 0, which would silently turn
                  // "I have not decided" into "this service has no cycle" — so an empty box
                  // saves nothing and leaves the value where it was.
                  onSave={(n) => setService(svc.id, { interval_days: n })}
                />
                <Setting
                  label="الاطمئنان بعد الزيارة"
                  meaning="رسالة قصيرة تسأل إن كان كل شيء تمام — تُلغى تلقائياً إن عاد قبل موعدها."
                  value={value.follow_up_days}
                  preview={(n) => `سؤال بعد ${n} يوماً من الزيارة`}
                  zero="لا نسأل بعد هذه الخدمة"
                  onSave={(n) => setService(svc.id, { follow_up_days: n })}
                />

                </>
                ) : null}

                {/* THE SERVICE ITSELF — its name, and whether the shop still sells it. Above the
                    reminder settings because it is the more basic fact: what this thing is comes
                    before when we message about it. */}
                {action(catalog, 'operations.update_service') ? (
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
                    <label className="flex min-w-0 flex-1 items-center gap-2">
                      <span className="text-sm text-text-secondary">الاسم</span>
                      <input
                        defaultValue={svc.name}
                        aria-label={`اسم ${svc.name}`}
                        maxLength={128}
                        onBlur={(e) => {
                          const v = e.target.value.trim();
                          if (v && v !== svc.name) patchService(svc.id, { name: v });
                        }}
                        className="h-10 flex-1 rounded-lg bg-surface-2 px-3"
                      />
                    </label>
                    {/* STOPPED, NOT DELETED — and the button says which. Deleting a service would
                        orphan every visit that names it. */}
                    {/* IT LOOKS LIKE WHAT IT DOES. As a ghost button «إيقاف» was a word floating
                        in the middle of the card — indistinguishable from a label, and no warmer
                        than the group heading under it. Stopping a service takes it off the
                        operator's grid and silences its reminders, so it carries the colour of a
                        withdrawal; «تفعيل», which restores, is an ordinary outline. */}
                    <Button
                      variant={svc.active === false ? 'outline' : 'danger'}
                      disabled={saving}
                      onClick={() => patchService(svc.id, { active: svc.active === false })}
                    >
                      {svc.active === false ? 'تفعيل' : 'إيقاف'}
                    </Button>
                  </div>
                ) : null}

                {/* PUTTING A SERVICE IN A GROUP, DIRECTLY.
                    Until now a group could only come into existence when the system NOTICED the
                    owner repeating himself across three services and offered to make one. That
                    proposal is good and it stays — nobody is asked to design a taxonomy on day one
                    — but it was the ONLY way, so an owner who already knew «هذه كلها خدمات محرك»
                    had no way to say it. He had to set the same number three times and wait to be
                    asked. The suggestion is now the shortcut, not the gate. */}
                {action(catalog, 'reminders.set_group') ? (
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
                    {/* BEHIND «؟» LIKE THE REST. Same reason: read once, then furniture. */}
                    <span className="flex min-w-0 items-center gap-2">
                      <span className="text-sm">المجموعة</span>
                      <Hint>ما في مجموعة واحدة يأخذ إعداداً واحداً — تغيّره مرة لها كلها.</Hint>
                    </span>
                    <select
                      aria-label={`مجموعة ${svc.name}`}
                      value={settings?.service_group?.[svc.id] ?? ''}
                      onChange={(e) => {
                        const v = e.target.value;
                        if (v === '__new__') { setNaming(svc.id); return; }
                        // «بلا مجموعة» IS AN ACT NOW. It was an option in this list with nothing
                        // behind it — the service had `leave_group` missing entirely, so an owner
                        // who grouped something could never ungroup it.
                        if (!v) { leaveGroup(svc.id); return; }
                        joinGroup(svc.id, v);
                      }}
                      className="h-10 w-full shrink-0 rounded-lg bg-surface-2 px-3 sm:w-auto"
                    >
                      <option value="">بلا مجموعة</option>
                      {Object.keys(settings?.groups ?? {}).map((g) => (
                        <option key={g} value={g}>{g}</option>
                      ))}
                      <option value="__new__">مجموعة جديدة…</option>
                    </select>
                  </div>
                ) : null}

                {naming === svc.id ? (
                  <div className="flex items-center gap-2">
                    <input
                      autoFocus
                      aria-label="اسم المجموعة الجديدة"
                      placeholder="مثال: خدمات المحرك"
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') joinGroup(svc.id, e.currentTarget.value);
                        if (e.key === 'Escape') setNaming(null);
                      }}
                      className="h-10 flex-1 rounded-lg bg-surface-2 px-3"
                    />
                    <Button variant="ghost" onClick={() => setNaming(null)}>إلغاء</Button>
                  </div>
                ) : null}

                {/* HIS POINTS FOR THIS SERVICE, HERE. The number lived in «نقاطي» alone, so an
                    owner setting up a service had to leave the screen he was on, find the same
                    service in another list, set one number, and come back — for the one field
                    that belongs to the thing he is already looking at. The screen that owns the
                    setting keeps owning it; this is the same action, reachable where the question
                    is actually asked.

                    IT SHOWS THE INHERITED NUMBER AS WELL AS AN OWN ONE (§9.2: inherit, never
                    copy), so «إعداد عام» is visible rather than looking like a zero he forgot. */}
                {earnAction ? (
                  <div className="flex flex-wrap items-center gap-2 rounded-lg bg-surface-2/60 p-3">
                    <span className="text-sm">نقاط هذه الخدمة</span>
                    <Hint>
                      كم نقطة يكسبها عميلك من هذه الخدمة في كل زيارة. اتركها كما هي لتتبع الإعداد
                      العام — وتغييرها هنا يجعلها خاصة بهذه الخدمة وحدها.
                    </Hint>
                    {!earnFor(svc.id).own ? (
                      <span className="text-xs text-text-secondary">تتبع العام</span>
                    ) : null}
                    <input
                      type="number"
                      min={0}
                      dir="ltr"
                      defaultValue={String(earnFor(svc.id).points)}
                      aria-label={`نقاط ${svc.name}`}
                      onBlur={(e) => {
                        const raw = e.target.value.trim();
                        if (raw === '') return;
                        const n = Number(raw);
                        if (n !== earnFor(svc.id).points) setServicePoints(svc.id, n);
                      }}
                      className="ms-auto h-10 w-24 shrink-0 rounded-lg bg-surface-1 px-3 text-center tabular-nums"
                    />
                  </div>
                ) : null}

                {own && action(catalog, 'reminders.follow_general') ? (
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm text-text-secondary">
                      هذه الخدمة لها إعدادها الخاص.
                    </span>
                    {/* A DELETE, NOT A WRITE OF TODAY'S DEFAULT. Following the general value means
                        this service tracks it from now on — writing the current number would
                        freeze it, and the next general change would skip this service silently. */}
                    <Button variant="ghost" disabled={saving} onClick={() => followGeneral(svc.id)}>
                      العودة إلى العام
                    </Button>
                  </div>
                ) : null}
                {/* CLOSED FROM THE BOTTOM, WHERE HIS THUMB ALREADY IS. The only way out of an
                    open service was the header — which by then is a full screen above him, so
                    closing a card meant scrolling back up past everything he had just read. */}
                <Button variant="ghost" onClick={() => setOpen(null)}>إغلاق</Button>
              </div>
            ) : null}
          </div>
        );
          })}
        </section>
      ))}
        </div>
      </div>
      </div>
        );
      })()}
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
  label, meaning, value, preview, zero, onSave,
}: {
  label: string;
  meaning: string;
  value?: number;
  preview: (n: number) => string;
  /** What zero means HERE — «بلا دورة» and «لا نسأل» are different silences. */
  zero: string;
  onSave: (n: number) => void;
}) {
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
          aria-label={`${label} (بالأيام)`}
          dir="ltr"
          className="ms-auto h-10 w-24 shrink-0 rounded-lg bg-surface-1 px-3 text-center tabular-nums"
        />
      </div>
      <span className="text-sm text-accent-on-soft">{n > 0 ? preview(n) : zero}</span>
    </div>
  );
}
