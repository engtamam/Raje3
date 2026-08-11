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
import { EmptyState } from '@base-ui/design-system/EmptyState';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';

interface Service { id: string; name: string; cycle_days: number; price_minor: number; catchall?: boolean }

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

export function ServicesScreen({ session, catalog }: { session: Session; catalog: Catalog }) {
  const [services, setServices] = useState<Service[] | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null);
  /** The name box, shown only after he asks for the group — never as a field waiting to be filled. */
  const [naming, setNaming] = useState<string | null>(null);

  const load = () => {
    const list = action(catalog, 'operations.list_services');
    if (list) {
      call<{ services: Service[] }>(session, list)
        .then((x) => setServices(x.services))
        .catch(() => setServices([]));
    } else {
      setServices([]);
    }

    const s = action(catalog, 'reminders.get_settings');
    if (s) call<Settings>(session, s).then(setSettings).catch(() => setSettings(null));

    // A PROPOSAL, AND ITS ABSENCE IS THE NORMAL CASE. It reads null until the owner has repeated
    // himself across at least three services, which is the point: a shop on its first day is not
    // shown an organisational chore it has no reason for yet.
    const sg = action(catalog, 'reminders.suggest_group');
    if (sg) {
      call<{ suggestion: Suggestion | null }>(session, sg)
        .then((x) => setSuggestion(x.suggestion))
        .catch(() => setSuggestion(null));
    }
  };

  useEffect(load, [session, catalog]);

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
          title="لا توجد خدمات"
          description="قائمة قطاعك تُضاف تلقائياً عند إنشاء الحساب — تواصل معنا إن بقيت فارغة."
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

      {grouped(services).map(([group, inGroup]) => (
        <section key={group || 'ungrouped'} className="flex flex-col gap-3">
          {/* THE HEADING CARRIES THE GROUP'S OWN CYCLE, because that is what the services under it
              follow — a heading that is only a name leaves the owner reading each service to work
              out what the group actually does. The remainder bin has no settings and says so by
              carrying no number. */}
          <h2 className="px-1 pt-2 text-sm font-semibold text-text-secondary">
            {group === UNGROUPED ? 'خدمات غير مجمّعة' : group}
            {group !== UNGROUPED && settings?.groups?.[group]?.interval_days
              ? ` · كل ${settings.groups[group].interval_days} يوماً`
              : ''}
          </h2>
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
                <span className="text-sm text-text-secondary tabular-nums">
                  {value.interval_days ? `كل ${value.interval_days} يوماً` : 'بلا دورة'}
                </span>
              </span>
              {/* SHOWN WHERE IT HAPPENED. Without this the owner cannot tell which services he has
                  customised, and a general change that "did not work" is really a service holding
                  its own value. */}
              {own ? <Badge tone="accent">إعداد خاص</Badge> : null}
            </button>

            {isOpen ? (
              <div className="flex flex-col gap-3 border-t border-border-subtle px-4 py-3">
                {/* THE REMINDER FIELDS ARE A SECOND CAPABILITY. The name and the price are
                    operations'; the cycle and the follow-up are reminders' — and a role can hold
                    one without the other. Rendering an input that will be refused teaches the
                    person the product is broken, so it is absent instead. */}
                {action(catalog, 'reminders.set_service_settings') ? (
                <>
                <label className="flex items-center justify-between gap-3">
                  <span className="text-sm">دورة التذكير (بالأيام)</span>
                  <input
                    type="number"
                    min={0}
                    defaultValue={value.interval_days ?? 0}
                    // A BLANK FIELD IS NOT A ZERO. `Number('')` is 0, which would silently turn
                    // "I have not decided" into "this service has no cycle" — so an empty box
                    // saves nothing and leaves the value where it was.
                    onBlur={(e) => {
                      const raw = e.target.value.trim();
                      if (raw !== '') setService(svc.id, { interval_days: Number(raw) });
                    }}
                    dir="ltr"
                    className="h-10 w-28 rounded-lg bg-surface-2 px-3 text-center tabular-nums"
                  />
                </label>
                <label className="flex items-center justify-between gap-3">
                  <span className="text-sm">الاطمئنان بعد الزيارة (بالأيام)</span>
                  <input
                    type="number"
                    min={0}
                    defaultValue={value.follow_up_days ?? 0}
                    onBlur={(e) => {
                      const raw = e.target.value.trim();
                      if (raw !== '') setService(svc.id, { follow_up_days: Number(raw) });
                    }}
                    dir="ltr"
                    className="h-10 w-28 rounded-lg bg-surface-2 px-3 text-center tabular-nums"
                  />
                </label>

                </>
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
              </div>
            ) : null}
          </div>
        );
          })}
        </section>
      ))}
    </div>
  );
}
