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
}
interface EarnSettings {
  general?: { points?: number };
  defaults?: { points?: number };
  groups?: Record<string, { points?: number }>;
  services?: Record<string, { points?: number }>;
  service_group?: Record<string, string>;
  packages?: Record<string, { points?: number }>;
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
        .catch(() => setServices([]));
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
  });

  const openEdit = (p: PackageRow) => setDraft({
    id: p.id, name: p.name, serviceIds: [...p.service_ids],
    priceText: riyalsRaw(p.price_minor),
    pointsText: String(earn?.packages?.[p.id]?.points ?? pointsSumFor(p.service_ids, earn)),
    source: p.source ?? 'manual', sourceServiceIds: [],
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
      let id = draft.id;
      if (id === null) {
        const create = action(catalog, 'operations.create_package');
        if (!create) throw new Error('لا تملك صلاحية إنشاء باقة');
        const created = await call<{ id: string }>(session, create, {
          name: draft.name.trim(), service_ids: draft.serviceIds, price_minor: priceMinor,
          source: draft.source, source_service_ids: draft.sourceServiceIds,
        });
        id = created.id;
      } else {
        const patch = action(catalog, 'operations.update_package');
        if (!patch) throw new Error('لا تملك صلاحية تعديل باقة');
        await call(session, patch, {
          id, name: draft.name.trim(), service_ids: draft.serviceIds, price_minor: priceMinor,
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
  const canSave = !!draft && draft.name.trim().length > 0 && draft.serviceIds.length >= 2 && priceValid;

  return (
    <div className="flex flex-col gap-3">
      {error ? <p className="text-danger">{error}</p> : null}

      {(packages ?? []).length === 0 ? (
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
                    <span className="text-sm text-text-secondary">{riyalsLabel(p.price_minor)}</span>
                  </div>
                  {p.source === 'suggested' ? <Badge tone="accent">من اقتراح محلّي</Badge> : null}
                </div>
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
