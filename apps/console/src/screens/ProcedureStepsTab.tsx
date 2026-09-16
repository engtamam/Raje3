/**
 * «الإجراءات» — a tab inside «خدماتي ومنتجاتي», not a screen of its own — same reasoning
 * PackagesTab.tsx's own header already gives for why a package stayed a tab rather than a new
 * rail section: a procedure step is a smaller concern living entirely inside the service
 * catalogue this screen already owns.
 *
 * SELF-CONTAINED, SAME AS PackagesTab — its own fetch, its own state, independent of the
 * SERVICES tab's own `services`/`settings` (which never carry `procedure_step_ids` at the
 * depth this tab needs, and refetching here is one call, not a prop-drilling exercise).
 *
 * SERVICE-FIRST, THE LIBRARY SECOND — the owner's own mental model is "what does غسيل السيارة
 * involve", not "what steps exist" ([[task-service-procedure-checklists]] phase 3 design). The
 * shared library (create/edit text+severity/retire) is one link away, reached rarely — assigning
 * an existing step to a service is the common action, so it is the default view.
 *
 * "مستخدمة بـN خدمات" — THE ONE SIGNAL THAT MAKES A SHARED ENTITY SAFE TO EDIT. A step is a
 * single row referenced by id from every service that lists it (Service.procedure_step_ids'
 * own docstring) — editing its text/severity from EITHER the drawer or the library changes it
 * everywhere at once, and a shop that does not see this coming reads that as a bug the first
 * time it happens. Computed client-side from the one services list already fetched below —
 * never a second round trip per step.
 */
import { useEffect, useMemo, useState } from 'react';
import { Reorder } from 'framer-motion';
import { AlertTriangle, ClipboardList, GripVertical, Library, Plus, Printer, X } from 'lucide-react';
import { Button } from '../rj-ui/Button';
import { Badge } from '../rj-ui/Badge';
import { Drawer } from '../rj-ui/Drawer';
import { Input, Select } from '../rj-ui/Field';
import { EmptyState } from '../rj-ui/EmptyState';
import { Skeleton } from '../rj-ui/Skeleton';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';
import { useOperatorI18n, tf } from '../operator-i18n';
import { fresh } from '../renew';
import './procedure-steps-tab-i18n';

const API_BASE = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '');

type Severity = 'normal' | 'critical';

interface ProcedureStep {
  id: string; text: string; severity: Severity; active: boolean;
}
interface ServiceLite {
  id: string; name: string; active?: boolean; procedure_step_ids: string[];
}

function stepCountLabel(t: (k: string) => string, n: number): string {
  if (n === 0) return t('procedures.stepCount_zero');
  if (n === 1) return t('procedures.stepCount_one');
  return tf(t, 'procedures.stepCount_other', { n });
}

function usedInLabel(t: (k: string) => string, n: number): string {
  if (n === 1) return t('procedures.drawer.usedIn_one');
  return tf(t, 'procedures.drawer.usedIn_other', { n });
}

function selectedCountLabel(t: (k: string) => string, n: number): string {
  if (n === 0) return t('procedures.bulkPrint.selectedCount_zero');
  if (n === 1) return t('procedures.bulkPrint.selectedCount_one');
  return tf(t, 'procedures.bulkPrint.selectedCount_other', { n });
}

function SeverityDot({ severity }: { severity: Severity }) {
  return (
    <span
      aria-hidden
      className={severity === 'critical'
        ? 'size-2.5 shrink-0 rounded-full bg-danger'
        : 'size-2.5 shrink-0 rounded-full bg-text-muted/50'}
    />
  );
}

// A RAW fetch, NOT `call()` — the response is a PDF byte stream, not the JSON `call()` always
// parses (same reasoning Rating.tsx's own export button already settled on). Shared by the
// per-service drawer's own print button AND the service-list's multi-select bulk print — one
// service or several, the server-side route always takes a `service_ids` list.
async function downloadProcedureChecklist(
  session: Session, catalog: Catalog, serviceIds: string[], filename: string,
): Promise<void> {
  const a = action(catalog, 'operations.export_procedure_checklist');
  if (!a) throw new Error('no action');
  const bearer = await fresh(session.token);
  const res = await fetch(`${API_BASE}${a.path}`, {
    method: a.method,
    headers: { Authorization: `Bearer ${bearer}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ service_ids: serviceIds, file_format: 'pdf' }),
  });
  if (!res.ok) throw new Error('export failed');
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a2 = document.createElement('a');
  a2.href = url; a2.download = filename;
  document.body.appendChild(a2); a2.click(); a2.remove();
  URL.revokeObjectURL(url);
}

export function ProcedureStepsTab({ session, catalog }: { session: Session; catalog: Catalog }) {
  const { t } = useOperatorI18n();
  const [steps, setSteps] = useState<ProcedureStep[] | null | undefined>(undefined);
  const [services, setServices] = useState<ServiceLite[] | null | undefined>(undefined);
  const [openServiceId, setOpenServiceId] = useState<string | null>(null);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkPrinting, setBulkPrinting] = useState(false);
  const [bulkPrintError, setBulkPrintError] = useState('');

  const load = () => {
    const stepsAction = action(catalog, 'operations.list_procedure_steps');
    const svcAction = action(catalog, 'operations.manage_services');
    if (!stepsAction || !svcAction) { setSteps(null); setServices(null); return; }
    call<{ procedure_steps: ProcedureStep[] }>(session, stepsAction)
      .then((x) => setSteps(x.procedure_steps ?? []))
      .catch(() => setSteps(null));
    call<{ services: ServiceLite[] }>(session, svcAction)
      .then((x) => setServices(x.services ?? []))
      .catch(() => setServices(null));
  };
  useEffect(load, [session, catalog]); // eslint-disable-line react-hooks/exhaustive-deps

  const stepsById = useMemo(() => {
    const m = new Map<string, ProcedureStep>();
    for (const s of steps ?? []) m.set(s.id, s);
    return m;
  }, [steps]);

  const usageCount = useMemo(() => {
    const counts = new Map<string, number>();
    for (const svc of services ?? []) {
      for (const sid of svc.procedure_step_ids) counts.set(sid, (counts.get(sid) ?? 0) + 1);
    }
    return counts;
  }, [services]);

  const openService = services?.find((s) => s.id === openServiceId) ?? null;

  if (steps === undefined || services === undefined) {
    return (
      <div className="flex flex-col gap-3 p-4">
        {[0, 1, 2].map((i) => <Skeleton key={i} height={68} radius="card" />)}
      </div>
    );
  }
  if (steps === null || services === null) {
    return (
      <div className="p-4">
        <p role="alert" className="text-sm text-danger">{t('procedures.loadFailed')}</p>
      </div>
    );
  }

  const visibleServices = services.filter((s) => s.active !== false);

  const toggleSelected = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const printSelected = async () => {
    if (bulkPrinting || selected.size === 0) return;
    setBulkPrinting(true); setBulkPrintError('');
    try {
      const ids = [...selected];
      const names = visibleServices.filter((s) => selected.has(s.id)).map((s) => s.name);
      await downloadProcedureChecklist(session, catalog, ids,
        `${names.join(' + ') || 'إجراءات'}.pdf`);
      setSelected(new Set());
    } catch {
      setBulkPrintError(t('procedures.drawer.printFailed'));
    } finally {
      setBulkPrinting(false);
    }
  };

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex items-start justify-between gap-3">
        <p className="max-w-lg text-sm text-text-secondary">{t('procedures.subtitle')}</p>
        <button
          type="button"
          onClick={() => setLibraryOpen(true)}
          className="flex shrink-0 items-center gap-1.5 whitespace-nowrap text-sm font-semibold text-accent hover:underline"
        >
          <Library size={15} aria-hidden />
          {t('procedures.libraryLink')}
        </button>
      </div>

      {selected.size > 0 ? (
        <div className="flex flex-wrap items-center gap-2 rounded-card border border-accent/30
                        bg-accent-soft p-3">
          <span className="text-sm font-semibold text-accent-on-soft">
            {selectedCountLabel(t, selected.size)}
          </span>
          {bulkPrintError ? <p role="alert" className="text-caption text-danger">{bulkPrintError}</p> : null}
          <div className="ms-auto flex gap-2">
            <Button type="button" variant="ghost" onClick={() => setSelected(new Set())}>
              {t('procedures.bulkPrint.clear')}
            </Button>
            <Button type="button" onClick={printSelected} disabled={bulkPrinting}>
              <Printer size={15} />
              {bulkPrinting ? t('procedures.drawer.printing') : t('procedures.bulkPrint.print')}
            </Button>
          </div>
        </div>
      ) : null}

      {visibleServices.length === 0 ? (
        <EmptyState
          icon={<ClipboardList size={28} aria-hidden />}
          title={t('procedures.empty.title')}
          description={t('procedures.empty.description')}
        />
      ) : (
        <div className="grid gap-2.5">
          {visibleServices.map((svc) => (
            <div
              key={svc.id}
              role="button"
              tabIndex={0}
              onClick={() => setOpenServiceId(svc.id)}
              onKeyDown={(e) => { if (e.key === 'Enter') setOpenServiceId(svc.id); }}
              className="flex cursor-pointer items-center gap-3 rounded-card border border-border-subtle
                         bg-surface-1 p-4 text-start transition-colors hover:border-accent"
            >
              <input
                type="checkbox"
                aria-label={tf(t, 'procedures.bulkPrint.selectOne', { name: svc.name })}
                checked={selected.has(svc.id)}
                onClick={(e) => e.stopPropagation()}
                onChange={() => toggleSelected(svc.id)}
                className="size-4 shrink-0 accent-accent"
              />
              <div className="min-w-0 flex-1">
                <div className="truncate font-semibold text-text-primary">{svc.name}</div>
                <div className="mt-0.5 text-caption text-text-secondary">
                  {stepCountLabel(t, svc.procedure_step_ids.length)}
                </div>
              </div>
              <Badge tone={svc.procedure_step_ids.length > 0 ? 'accent' : 'neutral'}>
                {svc.procedure_step_ids.length}
              </Badge>
            </div>
          ))}
        </div>
      )}

      {openService ? (
        <ServiceDrawer
          key={openService.id}
          session={session}
          catalog={catalog}
          service={openService}
          allSteps={steps}
          stepsById={stepsById}
          usageCount={usageCount}
          onClose={() => setOpenServiceId(null)}
          onSaved={load}
        />
      ) : null}

      <LibraryDrawer
        open={libraryOpen}
        session={session}
        catalog={catalog}
        steps={steps}
        usageCount={usageCount}
        onClose={() => setLibraryOpen(false)}
        onChanged={load}
      />
    </div>
  );
}

// ── per-service drawer: ordered steps, drag to reorder, add/remove ─────────────────────────────

function ServiceDrawer({
  session, catalog, service, allSteps, stepsById, usageCount, onClose, onSaved,
}: {
  session: Session; catalog: Catalog; service: ServiceLite;
  allSteps: ProcedureStep[]; stepsById: Map<string, ProcedureStep>; usageCount: Map<string, number>;
  onClose: () => void; onSaved: () => void;
}) {
  const { t } = useOperatorI18n();
  const [order, setOrder] = useState<string[]>(service.procedure_step_ids);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [printing, setPrinting] = useState(false);
  const [printError, setPrintError] = useState('');

  const dirty = order.length !== service.procedure_step_ids.length
    || order.some((id, i) => id !== service.procedure_step_ids[i]);

  const save = async () => {
    const a = action(catalog, 'operations.update_service');
    if (!a) return;
    setSaving(true); setError('');
    try {
      await call(session, a, { id: service.id, procedure_step_ids: order });
      onSaved();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('procedures.drawer.saveFailed'));
    } finally {
      setSaving(false);
    }
  };

  const print = async () => {
    if (printing) return;
    setPrinting(true); setPrintError('');
    try {
      await downloadProcedureChecklist(session, catalog, [service.id], `${service.name}.pdf`);
    } catch {
      setPrintError(t('procedures.drawer.printFailed'));
    } finally {
      setPrinting(false);
    }
  };

  return (
    <Drawer
      open
      onClose={onClose}
      title={service.name}
      subtitle={t('procedures.drawer.subtitle')}
      footer={
        <div className="flex w-full items-center gap-2">
          {error ? <p role="alert" className="text-caption text-danger">{error}</p> : null}
          {printError ? <p role="alert" className="text-caption text-danger">{printError}</p> : null}
          <Button type="button" variant="ghost" onClick={print} disabled={printing || order.length === 0}>
            <Printer size={15} />
            {printing ? t('procedures.drawer.printing') : t('procedures.drawer.print')}
          </Button>
          <div className="ms-auto flex gap-2">
            <Button type="button" variant="ghost" onClick={onClose}>{t('procedures.drawer.cancel')}</Button>
            <Button type="button" onClick={save} disabled={!dirty || saving}>
              {t('procedures.drawer.save')}
            </Button>
          </div>
        </div>
      }
    >
      {order.length === 0 ? (
        <p className="py-6 text-center text-sm text-text-secondary">{t('procedures.drawer.empty')}</p>
      ) : (
        <Reorder.Group axis="y" values={order} onReorder={setOrder} className="flex flex-col gap-2">
          {order.map((sid) => {
            const step = stepsById.get(sid);
            if (!step) return null;
            const used = usageCount.get(sid) ?? 0;
            return (
              <Reorder.Item
                key={sid}
                value={sid}
                className="flex items-center gap-2.5 rounded-lg border border-border-subtle bg-surface-1 p-3"
              >
                <GripVertical size={16} className="shrink-0 cursor-grab text-text-muted" aria-hidden />
                <SeverityDot severity={step.severity} />
                <span className="min-w-0 flex-1 truncate text-sm">{step.text}</span>
                {used > 1 ? (
                  <span className="shrink-0 whitespace-nowrap rounded-full bg-surface-2 px-2 py-0.5 text-caption text-text-secondary">
                    {usedInLabel(t, used)}
                  </span>
                ) : null}
                <button
                  type="button"
                  aria-label={t('procedures.drawer.remove')}
                  onClick={() => setOrder((cur) => cur.filter((x) => x !== sid))}
                  className="shrink-0 rounded p-1 text-text-muted hover:bg-danger-soft hover:text-danger"
                >
                  <X size={15} />
                </button>
              </Reorder.Item>
            );
          })}
        </Reorder.Group>
      )}

      <button
        type="button"
        onClick={() => setPickerOpen(true)}
        className="mt-3 w-full rounded-lg border border-dashed border-border-strong p-3 text-sm font-semibold
                   text-accent transition-colors hover:border-accent hover:bg-accent-soft"
      >
        {t('procedures.drawer.addButton')}
      </button>

      {pickerOpen ? (
        <StepPicker
          session={session}
          catalog={catalog}
          allSteps={allSteps}
          usageCount={usageCount}
          excludeIds={order}
          onClose={() => setPickerOpen(false)}
          onApply={(ids) => { setOrder((cur) => [...cur, ...ids]); setPickerOpen(false); }}
          onCreated={(newStep) => { allSteps.push(newStep); }}
        />
      ) : null}
    </Drawer>
  );
}

// ── the picker: search + multiselect + create-new, nested inside the service drawer ────────────

function StepPicker({
  session, catalog, allSteps, usageCount, excludeIds, onClose, onApply, onCreated,
}: {
  session: Session; catalog: Catalog; allSteps: ProcedureStep[]; usageCount: Map<string, number>;
  excludeIds: string[]; onClose: () => void; onApply: (ids: string[]) => void;
  onCreated: (step: ProcedureStep) => void;
}) {
  const { t } = useOperatorI18n();
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [newText, setNewText] = useState('');
  const [newSeverity, setNewSeverity] = useState<Severity>('normal');
  const [creating, setCreating] = useState(false);

  const excluded = new Set(excludeIds);
  const results = allSteps.filter((s) =>
    s.active && !excluded.has(s.id) && s.text.toLowerCase().includes(query.trim().toLowerCase()));

  const toggle = (id: string) => {
    setSelected((cur) => {
      const next = new Set(cur);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const createStep = async () => {
    const text = newText.trim();
    if (!text) return;
    const a = action(catalog, 'operations.create_procedure_step');
    if (!a) return;
    setCreating(true);
    try {
      const created = await call<ProcedureStep>(session, a, { text, severity: newSeverity });
      onCreated(created);
      setSelected((cur) => new Set(cur).add(created.id));
      setNewText('');
    } finally {
      setCreating(false);
    }
  };

  return (
    <Drawer
      open
      onClose={onClose}
      title={t('procedures.pick.title')}
      footer={
        <div className="flex w-full items-center gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>{t('procedures.pick.close')}</Button>
          <Button
            type="button" className="ms-auto"
            disabled={selected.size === 0}
            onClick={() => onApply(Array.from(selected))}
          >
            {t('procedures.pick.apply')} ({selected.size})
          </Button>
        </div>
      }
    >
      <Input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={t('procedures.pick.search')}
        className="mb-3"
        autoFocus
      />
      <div className="flex flex-col gap-1">
        {results.length === 0 ? (
          <p className="py-4 text-center text-sm text-text-secondary">{t('procedures.pick.empty')}</p>
        ) : results.map((s) => {
          const used = usageCount.get(s.id) ?? 0;
          return (
            <label key={s.id} className="flex items-center gap-2.5 rounded-lg p-2.5 hover:bg-surface-2">
              <input
                type="checkbox"
                checked={selected.has(s.id)}
                onChange={() => toggle(s.id)}
                className="size-4 accent-accent"
              />
              <SeverityDot severity={s.severity} />
              <span className="min-w-0 flex-1 truncate text-sm">{s.text}</span>
              {used > 0 ? (
                <span className="shrink-0 text-caption text-text-muted">{used}</span>
              ) : null}
            </label>
          );
        })}
      </div>

      <div className="mt-4 flex gap-2 border-t border-border-subtle pt-3">
        <Input
          value={newText}
          onChange={(e) => setNewText(e.target.value)}
          placeholder={t('procedures.pick.createPlaceholder')}
          className="flex-1"
        />
        <Select
          value={newSeverity}
          onChange={(e) => setNewSeverity(e.target.value as Severity)}
          className="w-28 shrink-0"
        >
          <option value="normal">{t('procedures.severity.normal')}</option>
          <option value="critical">{t('procedures.severity.critical')}</option>
        </Select>
        <Button
          type="button" variant="outline" disabled={!newText.trim() || creating} onClick={createStep}
          aria-label={t('procedures.pick.create')}
        >
          <Plus size={15} aria-hidden />
        </Button>
      </div>
    </Drawer>
  );
}

// ── the shared library: create/edit text+severity/retire ───────────────────────────────────────

function LibraryDrawer({
  open, session, catalog, steps, usageCount, onClose, onChanged,
}: {
  open: boolean; session: Session; catalog: Catalog; steps: ProcedureStep[];
  usageCount: Map<string, number>; onClose: () => void; onChanged: () => void;
}) {
  const { t } = useOperatorI18n();
  const [showRetired, setShowRetired] = useState(false);
  const [newText, setNewText] = useState('');
  const [newSeverity, setNewSeverity] = useState<Severity>('normal');
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState('');

  if (!open) return null;

  const visible = steps.filter((s) => showRetired || s.active);

  const addStep = async () => {
    const text = newText.trim();
    if (!text) return;
    const a = action(catalog, 'operations.create_procedure_step');
    if (!a) return;
    setError('');
    try {
      await call(session, a, { text, severity: newSeverity });
      setNewText('');
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('procedures.library.saveFailed'));
    }
  };

  const patchStep = async (id: string, body: Record<string, unknown>) => {
    const a = action(catalog, 'operations.update_procedure_step');
    if (!a) return;
    setBusyId(id); setError('');
    try {
      await call(session, a, { id, ...body });
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('procedures.library.saveFailed'));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <Drawer open onClose={onClose} title={t('procedures.library.title')} subtitle={t('procedures.library.subtitle')}>
      <div className="mb-4 flex gap-2">
        <Input
          value={newText}
          onChange={(e) => setNewText(e.target.value)}
          placeholder={t('procedures.library.newPlaceholder')}
          className="flex-1"
        />
        <Select value={newSeverity} onChange={(e) => setNewSeverity(e.target.value as Severity)} className="w-28 shrink-0">
          <option value="normal">{t('procedures.severity.normal')}</option>
          <option value="critical">{t('procedures.severity.critical')}</option>
        </Select>
        <Button type="button" disabled={!newText.trim()} onClick={addStep}>{t('procedures.library.add')}</Button>
      </div>

      {error ? <p role="alert" className="mb-2 text-caption text-danger">{error}</p> : null}

      <label className="mb-3 flex items-center gap-2 text-caption text-text-secondary">
        <input type="checkbox" checked={showRetired} onChange={(e) => setShowRetired(e.target.checked)}
               className="size-3.5 accent-accent" />
        {t('procedures.library.showRetired')}
      </label>

      {visible.length === 0 ? (
        <p className="py-6 text-center text-sm text-text-secondary">{t('procedures.library.empty')}</p>
      ) : (
        <div className="flex flex-col gap-2">
          {visible.map((s) => {
            const used = usageCount.get(s.id) ?? 0;
            return (
              <div key={s.id} className="flex items-center gap-2.5 rounded-lg border border-border-subtle p-2.5">
                <SeverityDot severity={s.severity} />
                <Input
                  defaultValue={s.text}
                  disabled={busyId === s.id || !s.active}
                  onBlur={(e) => {
                    const next = e.target.value.trim();
                    if (next && next !== s.text) patchStep(s.id, { text: next });
                  }}
                  className="flex-1"
                />
                <Select
                  value={s.severity}
                  disabled={busyId === s.id || !s.active}
                  onChange={(e) => patchStep(s.id, { severity: e.target.value })}
                  className="w-24 shrink-0"
                >
                  <option value="normal">{t('procedures.severity.normal')}</option>
                  <option value="critical">{t('procedures.severity.critical')}</option>
                </Select>
                {used > 0 ? (
                  <span className="shrink-0 text-caption text-text-muted">{used}</span>
                ) : null}
                {!s.active ? <Badge tone="neutral">{t('procedures.library.retired')}</Badge> : null}
                <Button
                  type="button" variant="ghost" size="sm" disabled={busyId === s.id}
                  onClick={() => patchStep(s.id, { active: !s.active })}
                >
                  {s.active ? t('procedures.library.retire') : t('procedures.library.reactivate')}
                </Button>
              </div>
            );
          })}
        </div>
      )}
      <p className="mt-4 flex items-start gap-1.5 text-caption text-text-muted">
        <AlertTriangle size={13} className="mt-0.5 shrink-0" aria-hidden />
        {t('procedures.severity.hint')}
      </p>
    </Drawer>
  );
}
