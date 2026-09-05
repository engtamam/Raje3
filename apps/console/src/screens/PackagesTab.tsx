/**
 * «الباقات» — a tab inside «خدماتي ومنتجاتي», not a screen of its own.
 *
 * WHY A TAB AND NOT A NEW SECTION IN THE RAIL: a package is a repackaging of the catalogue that
 * already lives here — every field it needs (a name, a price, which services) is a subset of what
 * `Service` already models — never a new domain like الحجوزات or رسائلي. The rail is already
 * documented as full at nine labels on a phone (nav.ts), and a package is a smaller concern than
 * even فريقي was when IT was demoted to a tab for exactly that reason.
 *
 * TWO CREATION DOORS, ONE FORM. Built by hand here, or accepted straight from محلّي's «باقات
 * مقترحة» card (Shop.tsx navigates to `?tab=packages&prefill_a=&prefill_b=` for a brand-new
 * package, or `?extend_package=&extend_service=` to add one more service into an existing one) —
 * both land on the exact same dialog, pre-filled differently. See `Services.tsx`'s own reading of
 * these query params.
 *
 * PRICE AND POINTS ARE ALWAYS THE OWNER'S OWN NUMBER, NEVER DERIVED. `price_minor` has no relation
 * to the sum of the components' own prices (operations' Package model), and points behave the
 * same way — the sum of the selected services' CURRENT points is only ever a starting SUGGESTION,
 * written into the box for him to keep or change, never silently recomputed after.
 */
import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Button } from '../rj-ui/Button';
import { Badge } from '../rj-ui/Badge';
import { Modal } from '../rj-ui/Modal';
import { Toggle } from '../rj-ui/Toggle';
import { EmptyState } from '../rj-ui/EmptyState';
import { Skeleton } from '../rj-ui/Skeleton';
import { Boxes, Plus } from 'lucide-react';
import { action, call, type Catalog } from '../catalog';
import { halalas, riyalsLabel } from '../money';
import type { Session } from '../session';

interface ServiceLite { id: string; name: string; active?: boolean }
interface PackageRow {
  id: string; name: string; service_ids: string[]; price_minor: number; active: boolean;
  source?: string;
  starts_at?: number; ends_at?: number;
  recurrence?: 'none' | 'weekly' | 'monthly' | 'yearly';
  recurrence_weekdays?: number[]; recurrence_days_of_month?: number[];
  recurrence_yearly_from?: string; recurrence_yearly_to?: string;
  person_count?: number;
  /** THE SAME `core/scheduling.py::is_offerable` ANSWER, computed server-side — never
   *  recomputed here. `active` but `offerable_now === false` means "outside its own schedule
   *  today" (e.g. viewing a Saturday-only package on a Tuesday), a different, honest sentence
   *  from "the owner turned it off". */
  offerable_now?: boolean;
}

/** Saturday-first, matching how a Saudi week is actually read — but the VALUE stored is always
 *  Python's `date.weekday()` convention (Monday=0..Sunday=6), the same one operations' own
 *  core/scheduling.py compares against, so the label order here is purely cosmetic. */
const WEEKDAYS: { value: number; label: string }[] = [
  { value: 5, label: 'السبت' }, { value: 6, label: 'الأحد' }, { value: 0, label: 'الاثنين' },
  { value: 1, label: 'الثلاثاء' }, { value: 2, label: 'الأربعاء' }, { value: 3, label: 'الخميس' },
  { value: 4, label: 'الجمعة' },
];

const RECURRENCE_OPTIONS: { value: 'none' | 'weekly' | 'monthly' | 'yearly'; label: string }[] = [
  { value: 'none', label: 'بلا جدولة' },
  { value: 'weekly', label: 'أسبوعياً' },
  { value: 'monthly', label: 'شهرياً' },
  { value: 'yearly', label: 'سنوياً' },
];

/** unix seconds -> "YYYY-MM-DD" for a date input, in Riyadh — "" for 0 (no bound). */
function dateInputValue(ts: number | undefined): string {
  if (!ts) return '';
  const d = new Date((ts + 3 * 3600) * 1000);       // Riyadh = UTC+3, no DST
  return d.toISOString().slice(0, 10);
}

/** "YYYY-MM-DD" from a date input -> unix seconds at Riyadh midnight, or 0 for "" (no bound). */
function dateInputToTs(value: string): number {
  if (!value) return 0;
  const [y, m, d] = value.split('-').map(Number);
  return Math.floor(Date.UTC(y, m - 1, d, -3) / 1000);   // midnight Riyadh = 03:00 UTC back-shifted
}

/** "MM-DD" from a date input's value (year discarded — only the month/day matter here). */
function mmddFromDateInput(value: string): string {
  return value ? value.slice(5, 10) : '';
}

/** A date input's own value from a stored "MM-DD" — any fixed year works, since only MM-DD is
 *  ever read back out. 2024 chosen so "02-29" (a leap-only boundary) still renders without the
 *  browser's date input rejecting it. */
function dateInputFromMmdd(mmdd: string): string {
  return mmdd ? `2024-${mmdd}` : '';
}
interface EarnSettings {
  general?: { points?: number };
  defaults?: { points?: number };
  groups?: Record<string, { points?: number }>;
  services?: Record<string, { points?: number }>;
  service_group?: Record<string, string>;
  packages?: Record<string, { points?: number }>;
}

/** One short line under the package's name — "" when there is nothing worth saying (no schedule
 *  restriction and no absolute bound at all, i.e. a fully open-ended package). */
function scheduleSummary(p: PackageRow): string {
  const parts: string[] = [];
  if (p.recurrence === 'weekly' && p.recurrence_weekdays?.length) {
    parts.push('كل ' + p.recurrence_weekdays.map(
      (w) => WEEKDAYS.find((x) => x.value === w)?.label ?? '').join('، '));
  } else if (p.recurrence === 'monthly' && p.recurrence_days_of_month?.length) {
    parts.push('أيام ' + p.recurrence_days_of_month.join('، ') + ' من كل شهر');
  } else if (p.recurrence === 'yearly' && p.recurrence_yearly_from && p.recurrence_yearly_to) {
    parts.push(`من ${p.recurrence_yearly_from} إلى ${p.recurrence_yearly_to} كل سنة`);
  }
  if (p.starts_at) parts.push('من ' + dateInputValue(p.starts_at));
  if (p.ends_at) parts.push('حتى ' + dateInputValue(p.ends_at));
  return parts.join(' — ');
}

function pointsSumFor(ids: string[], earn: EarnSettings | null | undefined): number {
  if (!earn) return 0;
  let total = 0;
  for (const id of ids) {
    const own = earn.services?.[id]?.points;
    if (own !== undefined) { total += own; continue; }
    const group = earn.service_group?.[id];
    const fromGroup = group ? earn.groups?.[group]?.points : undefined;
    total += fromGroup ?? earn.general?.points ?? earn.defaults?.points ?? 0;
  }
  return total;
}

export function PackagesTab({ session, catalog }: { session: Session; catalog: Catalog }) {
  const [params, setParams] = useSearchParams();
  const [packages, setPackages] = useState<PackageRow[] | null | undefined>(undefined);
  const [services, setServices] = useState<ServiceLite[] | null | undefined>(undefined);
  const [earn, setEarn] = useState<EarnSettings | null | undefined>(undefined);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  // The dialog's own state — `null` closed, an object mid-edit. A fresh create and an edit of an
  // existing row share ONE shape so the form itself never branches on which door opened it.
  const [draft, setDraft] = useState<{
    id: string | null;                 // null = creating
    name: string; serviceIds: string[]; priceText: string; pointsText: string;
    source: string; sourceServiceIds: string[];
    startsAt: string; endsAt: string;                         // date-input strings, "" = no bound
    recurrence: 'none' | 'weekly' | 'monthly' | 'yearly';
    weekdays: number[]; daysOfMonth: number[];
    yearlyFrom: string; yearlyTo: string;                     // date-input strings (MM-DD used)
    personCountText: string;
  } | null>(null);

  const canManage = !!action(catalog, 'operations.manage_services');

  const load = () => {
    const list = action(catalog, 'operations.list_packages');
    if (list) {
      call<{ packages: PackageRow[] }>(session, list, { include_retired: true })
        .then((x) => setPackages(x.packages))
        .catch(() => setPackages(null));
    } else {
      setPackages([]);
    }
    const svc = action(catalog, 'operations.list_services');
    if (svc) {
      call<{ services: ServiceLite[] }>(session, svc, {})
        .then((x) => setServices((x.services ?? []).filter((s) => s.active !== false)))
        .catch(() => setServices(null));
    } else {
      setServices([]);
    }
    const es = action(catalog, 'loyalty.settings.read');
    if (es) call<EarnSettings>(session, es).then(setEarn).catch(() => setEarn(null));
  };

  useEffect(load, [session, catalog]);

  const namesById = useMemo(() => {
    const m: Record<string, string> = {};
    for (const s of services ?? []) m[s.id] = s.name;
    return m;
  }, [services]);

  // ── the two prefill doors from محلّي ────────────────────────────────────────────────────────
  useEffect(() => {
    if (services === undefined || draft) return;    // wait for the picker's own list first
    const a = params.get('prefill_a');
    const b = params.get('prefill_b');
    const extendPkg = params.get('extend_package');
    const extendSvc = params.get('extend_service');
    if (a && b) {
      setDraft({
        id: null, name: '', serviceIds: [a, b],
        priceText: '', pointsText: String(pointsSumFor([a, b], earn)),
        source: 'suggested', sourceServiceIds: [a, b],
        startsAt: '', endsAt: '', recurrence: 'none', weekdays: [], daysOfMonth: [],
        yearlyFrom: '', yearlyTo: '', personCountText: '1',
      });
      const next = new URLSearchParams(params);
      next.delete('prefill_a'); next.delete('prefill_b'); next.delete('tab');
      setParams(next, { replace: true });
    } else if (extendPkg && extendSvc && packages) {
      const target = packages.find((p) => p.id === extendPkg);
      if (target) {
        const ids = target.service_ids.includes(extendSvc)
          ? target.service_ids : [...target.service_ids, extendSvc];
        setDraft({
          id: target.id, name: target.name, serviceIds: ids,
          priceText: riyalsRaw(target.price_minor),
          pointsText: String(earn?.packages?.[target.id]?.points ?? pointsSumFor(ids, earn)),
          source: target.source ?? 'manual', sourceServiceIds: [],
          startsAt: dateInputValue(target.starts_at), endsAt: dateInputValue(target.ends_at),
          recurrence: target.recurrence ?? 'none',
          weekdays: target.recurrence_weekdays ?? [], daysOfMonth: target.recurrence_days_of_month ?? [],
          yearlyFrom: dateInputFromMmdd(target.recurrence_yearly_from ?? ''),
          yearlyTo: dateInputFromMmdd(target.recurrence_yearly_to ?? ''),
          personCountText: String(target.person_count ?? 1),
        });
      }
      const next = new URLSearchParams(params);
      next.delete('extend_package'); next.delete('extend_service'); next.delete('tab');
      setParams(next, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [services, packages, params]);

  const openCreate = () => setDraft({
    id: null, name: '', serviceIds: [], priceText: '', pointsText: '0',
    source: 'manual', sourceServiceIds: [],
    startsAt: '', endsAt: '', recurrence: 'none', weekdays: [], daysOfMonth: [],
    yearlyFrom: '', yearlyTo: '', personCountText: '1',
  });

  const openEdit = (p: PackageRow) => setDraft({
    id: p.id, name: p.name, serviceIds: [...p.service_ids],
    priceText: riyalsRaw(p.price_minor),
    pointsText: String(earn?.packages?.[p.id]?.points ?? pointsSumFor(p.service_ids, earn)),
    source: p.source ?? 'manual', sourceServiceIds: [],
    startsAt: dateInputValue(p.starts_at), endsAt: dateInputValue(p.ends_at),
    recurrence: p.recurrence ?? 'none',
    weekdays: p.recurrence_weekdays ?? [], daysOfMonth: p.recurrence_days_of_month ?? [],
    yearlyFrom: dateInputFromMmdd(p.recurrence_yearly_from ?? ''),
    yearlyTo: dateInputFromMmdd(p.recurrence_yearly_to ?? ''),
    personCountText: String(p.person_count ?? 1),
  });

  const toggleService = (id: string) => {
    if (!draft) return;
    const has = draft.serviceIds.includes(id);
    setDraft({ ...draft, serviceIds: has ? draft.serviceIds.filter((x) => x !== id) : [...draft.serviceIds, id] });
  };

  const save = async () => {
    if (!draft) return;
    const priceMinor = halalas(draft.priceText);
    if (!draft.name.trim() || draft.serviceIds.length < 2 || priceMinor === null || priceMinor <= 0) return;
    setSaving(true); setError('');
    try {
      const schedule = {
        starts_at: dateInputToTs(draft.startsAt), ends_at: dateInputToTs(draft.endsAt),
        recurrence: draft.recurrence,
        recurrence_weekdays: draft.weekdays,
        recurrence_days_of_month: draft.daysOfMonth,
        recurrence_yearly_from: mmddFromDateInput(draft.yearlyFrom),
        recurrence_yearly_to: mmddFromDateInput(draft.yearlyTo),
        person_count: Math.max(1, Number(draft.personCountText) || 1),
      };
      let id = draft.id;
      if (id === null) {
        const create = action(catalog, 'operations.create_package');
        if (!create) throw new Error('لا تملك صلاحية إنشاء باقة');
        const created = await call<{ id: string }>(session, create, {
          name: draft.name.trim(), service_ids: draft.serviceIds, price_minor: priceMinor,
          source: draft.source, source_service_ids: draft.sourceServiceIds, ...schedule,
        });
        id = created.id;
      } else {
        const patch = action(catalog, 'operations.update_package');
        if (!patch) throw new Error('لا تملك صلاحية تعديل باقة');
        await call(session, patch, {
          id, name: draft.name.trim(), service_ids: draft.serviceIds, price_minor: priceMinor,
          ...schedule,
        });
      }
      const points = Number(draft.pointsText);
      const setPts = action(catalog, 'loyalty.settings.package');
      if (setPts && id && Number.isFinite(points) && points >= 0) {
        await call(session, setPts, { package_id: id, points });
      }
      setDraft(null);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'تعذّر حفظ الباقة الآن — حاول مجدداً.');
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (p: PackageRow) => {
    const patch = action(catalog, 'operations.update_package');
    if (!patch) return;
    setSaving(true); setError('');
    try {
      await call(session, patch, { id: p.id, active: !p.active });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'تعذّر الحفظ الآن.');
    } finally {
      setSaving(false);
    }
  };

  if (packages === undefined || services === undefined) {
    return (
      <div className="flex flex-col gap-3">
        <Skeleton height={96} radius="card" />
        <Skeleton height={96} radius="card" />
      </div>
    );
  }

  const suggestedPoints = draft ? pointsSumFor(draft.serviceIds, earn) : 0;
  const priceValid = draft ? (halalas(draft.priceText) ?? 0) > 0 : false;
  const scheduleValid = !draft ? false
    : draft.recurrence === 'none' ? true
    : draft.recurrence === 'weekly' ? draft.weekdays.length > 0
    : draft.recurrence === 'monthly' ? draft.daysOfMonth.length > 0
    : !!draft.yearlyFrom && !!draft.yearlyTo;
  const canSave = !!draft && draft.name.trim().length > 0 && draft.serviceIds.length >= 2
    && priceValid && scheduleValid;

  return (
    <div className="flex flex-col gap-3">
      {error ? <p className="text-danger">{error}</p> : null}

      {/* A NULL READ IS NOT AN EMPTY ONE — `packages`/`services` set to `null` after a failed
          fetch used to fall straight into `(packages ?? []).length === 0`, rendering «لا توجد
          باقات بعد» to a shop whose read simply failed. Told apart here so the sentence he gets
          matches what actually happened. */}
      {packages === null || services === null ? (
        <p role="alert" className="text-sm text-danger">تعذّرت قراءة الباقات أو الخدمات — حاول مجدداً.</p>
      ) : (packages ?? []).length === 0 ? (
        <EmptyState
          icon={<Boxes size={22} />}
          title="لا توجد باقات بعد"
          description="اجمع خدمتين أو أكثر بسعر واحد ونقاط واحدة — تُحجز وتُسجَّل كأنها خدمة مستقلة بذاتها."
          action={canManage ? <Button onClick={openCreate}><Plus size={16} /> أنشئ باقتك الأولى</Button> : undefined}
        />
      ) : (
        <>
          {canManage ? (
            <Button className="self-start" onClick={openCreate}><Plus size={16} /> باقة جديدة</Button>
          ) : null}
          <div className="grid gap-3 sm:grid-cols-2">
            {(packages ?? []).map((p) => (
              <div key={p.id}
                  className="flex flex-col gap-2 rounded-card border border-border-subtle bg-surface-1 p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex flex-col">
                    <span className="font-semibold">{p.name}</span>
                    <span className="text-sm text-text-secondary">
                      {riyalsLabel(p.price_minor)}
                      {(p.person_count ?? 1) > 1 ? ` · لِـ${p.person_count} أشخاص` : ''}
                    </span>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    {p.source === 'suggested' ? <Badge tone="accent">من اقتراح محلّي</Badge> : null}
                    {p.active && p.offerable_now === false ? (
                      <Badge tone="warning">غير مفعّلة اليوم</Badge>
                    ) : null}
                  </div>
                </div>
                {scheduleSummary(p) ? (
                  <span className="text-xs text-text-muted">{scheduleSummary(p)}</span>
                ) : null}
                <div className="flex flex-wrap gap-1">
                  {p.service_ids.map((sid) => (
                    <Badge key={sid} tone="neutral">{namesById[sid] ?? sid}</Badge>
                  ))}
                </div>
                <div className="mt-1 flex items-center justify-between gap-2">
                  {canManage ? (
                    <Button variant="outline" size="sm" onClick={() => openEdit(p)}>تعديل</Button>
                  ) : <span />}
                  {canManage ? (
                    <Toggle checked={p.active} onChange={() => toggleActive(p)}
                           ariaLabel={p.active ? 'إيقاف الباقة' : 'تفعيل الباقة'} />
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      <Modal open={!!draft} onClose={() => setDraft(null)}
            title={draft?.id ? 'تعديل الباقة' : 'باقة جديدة'}
            subtitle="السعر والنقاط دائماً من عندك — لا نحسبهما من مجموع الخدمات.">
        {draft ? (
          <div className="flex flex-col gap-4">
            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium">اسم الباقة</span>
              <input
                autoFocus
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                placeholder="مثال: باقة الصيانة الشاملة"
                className="h-10 rounded-lg bg-surface-2 px-3"
              />
            </label>

            <div className="flex flex-col gap-1">
              <span className="text-sm font-medium">
                الخدمات ({draft.serviceIds.length} مُختارة — خدمتان على الأقل)
              </span>
              <div className="grid max-h-52 grid-cols-2 gap-1 overflow-y-auto rounded-lg border border-border-subtle p-2">
                {(services ?? []).map((s) => {
                  const checked = draft.serviceIds.includes(s.id);
                  return (
                    <button
                      key={s.id} type="button" onClick={() => toggleService(s.id)}
                      className={
                        'flex items-center gap-2 rounded-md px-2 py-1.5 text-start text-sm transition-colors ' +
                        (checked ? 'bg-accent-soft text-accent-on-soft' : 'hover:bg-surface-2')
                      }
                    >
                      <span className={
                        'grid h-4 w-4 shrink-0 place-items-center rounded border ' +
                        (checked ? 'border-accent bg-accent text-accent-contrast' : 'border-border-strong')
                      }>
                        {checked ? '✓' : ''}
                      </span>
                      {s.name}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <label className="flex flex-col gap-1">
                <span className="text-sm font-medium">السعر (ريال)</span>
                <input
                  value={draft.priceText} inputMode="decimal"
                  onChange={(e) => setDraft({ ...draft, priceText: e.target.value })}
                  placeholder="0"
                  className="h-10 rounded-lg bg-surface-2 px-3"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-sm font-medium">النقاط</span>
                <input
                  value={draft.pointsText} inputMode="numeric"
                  onChange={(e) => setDraft({ ...draft, pointsText: e.target.value })}
                  className="h-10 rounded-lg bg-surface-2 px-3"
                />
                {draft.serviceIds.length >= 2 && Number(draft.pointsText) !== suggestedPoints ? (
                  <button type="button" className="text-start text-xs text-accent underline"
                         onClick={() => setDraft({ ...draft, pointsText: String(suggestedPoints) })}>
                    استخدم مجموع نقاط الخدمات ({suggestedPoints})
                  </button>
                ) : null}
              </label>
            </div>

            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium">لعدد أشخاص (اختياري — وصفي فقط)</span>
              <input
                value={draft.personCountText} inputMode="numeric"
                onChange={(e) => setDraft({ ...draft, personCountText: e.target.value })}
                placeholder="1" className="h-10 w-24 rounded-lg bg-surface-2 px-3"
              />
            </label>

            <div className="flex flex-col gap-2 rounded-lg border border-border-subtle p-3">
              <span className="text-sm font-medium">جدولة الباقة</span>

              <div className="grid grid-cols-2 gap-3">
                <label className="flex flex-col gap-1">
                  <span className="text-xs text-text-secondary">تبدأ من (اختياري)</span>
                  <input type="date" value={draft.startsAt}
                        onChange={(e) => setDraft({ ...draft, startsAt: e.target.value })}
                        className="h-10 rounded-lg bg-surface-2 px-3" />
                </label>
                <label className="flex flex-col gap-1">
                  <span className="text-xs text-text-secondary">حتى (اختياري)</span>
                  <input type="date" value={draft.endsAt}
                        onChange={(e) => setDraft({ ...draft, endsAt: e.target.value })}
                        className="h-10 rounded-lg bg-surface-2 px-3" />
                </label>
              </div>

              <div className="flex flex-wrap gap-1">
                {RECURRENCE_OPTIONS.map((r) => (
                  <button key={r.value} type="button"
                         onClick={() => setDraft({ ...draft, recurrence: r.value })}
                         className={
                           'rounded-full px-3 py-1 text-xs font-medium transition-colors ' +
                           (draft.recurrence === r.value
                             ? 'bg-accent text-accent-contrast'
                             : 'bg-surface-2 text-text-secondary hover:bg-surface-3')
                         }>
                    {r.label}
                  </button>
                ))}
              </div>

              {draft.recurrence === 'weekly' ? (
                <div className="flex flex-wrap gap-1">
                  {WEEKDAYS.map((w) => {
                    const checked = draft.weekdays.includes(w.value);
                    return (
                      <button key={w.value} type="button"
                             onClick={() => setDraft({
                               ...draft,
                               weekdays: checked ? draft.weekdays.filter((x) => x !== w.value)
                                                 : [...draft.weekdays, w.value],
                             })}
                             className={
                               'rounded-full px-3 py-1 text-xs transition-colors ' +
                               (checked ? 'bg-accent-soft text-accent-on-soft'
                                       : 'bg-surface-2 text-text-secondary hover:bg-surface-3')
                             }>
                        {w.label}
                      </button>
                    );
                  })}
                </div>
              ) : null}

              {draft.recurrence === 'monthly' ? (
                <div className="grid grid-cols-7 gap-1">
                  {Array.from({ length: 31 }, (_, i) => i + 1).map((day) => {
                    const checked = draft.daysOfMonth.includes(day);
                    return (
                      <button key={day} type="button"
                             onClick={() => setDraft({
                               ...draft,
                               daysOfMonth: checked ? draft.daysOfMonth.filter((x) => x !== day)
                                                    : [...draft.daysOfMonth, day],
                             })}
                             className={
                               'h-8 rounded-md text-xs transition-colors ' +
                               (checked ? 'bg-accent-soft text-accent-on-soft'
                                       : 'bg-surface-2 text-text-secondary hover:bg-surface-3')
                             }>
                        {day}
                      </button>
                    );
                  })}
                </div>
              ) : null}

              {draft.recurrence === 'yearly' ? (
                <div className="grid grid-cols-2 gap-3">
                  <label className="flex flex-col gap-1">
                    <span className="text-xs text-text-secondary">من (يوم وشهر)</span>
                    <input type="date" value={draft.yearlyFrom}
                          onChange={(e) => setDraft({ ...draft, yearlyFrom: e.target.value })}
                          className="h-10 rounded-lg bg-surface-2 px-3" />
                  </label>
                  <label className="flex flex-col gap-1">
                    <span className="text-xs text-text-secondary">إلى (يوم وشهر)</span>
                    <input type="date" value={draft.yearlyTo}
                          onChange={(e) => setDraft({ ...draft, yearlyTo: e.target.value })}
                          className="h-10 rounded-lg bg-surface-2 px-3" />
                  </label>
                </div>
              ) : null}

              {!scheduleValid ? (
                <span className="text-xs text-danger">أكمل تفاصيل الجدولة، أو اخترها «بلا جدولة».</span>
              ) : null}
            </div>

            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setDraft(null)}>إلغاء</Button>
              <Button disabled={!canSave || saving} onClick={save}>حفظ</Button>
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}

/** Halalas → the text a price INPUT should hold (no trailing currency word, unlike `riyalsLabel`). */
function riyalsRaw(minor: number): string {
  if (!Number.isFinite(minor) || minor <= 0) return '';
  const whole = Math.floor(minor / 100);
  const cents = minor % 100;
  return cents === 0 ? String(whole) : `${whole}.${String(cents).padStart(2, '0')}`;
}
