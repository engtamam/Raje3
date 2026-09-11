/**
 * The generic engine — renders ANY declared admin action automatically, per §1 of the admin
 * plan's own reasoning: 24+ خدمة × عدة إجراءات = مئات الشاشات لو بُنيت يدوياً؛ يكفي مُفسِّر واحد.
 *
 * A GET action with no path params becomes a list (`Table`, dynamic columns from the response's
 * own shape — the catalog declares REQUEST params, never response fields, so there is no schema
 * to render exact columns from; every key on the first row becomes a column instead). Any
 * mutating action in the SAME `group` whose only path param resolves against a row (see
 * `actionApi.ts::resolvePath`'s own id-fallback) becomes a row action automatically — confirmed
 * through `ConfirmDialog`, armed (types the row's own label) when `danger` is set.
 *
 * THIS IS THE FALLBACK TIER, NOT THE ONLY TIER — §9/10 of the plan hand-polish the
 * highest-traffic screens (Config, Secrets, the customer profile) instead of generating them;
 * this component is what makes every OTHER declared action reachable without waiting for a
 * hand-built screen to catch up.
 */
import { useEffect, useState } from 'react';
import { Check, Play, RotateCcw, Trash2, type LucideIcon } from 'lucide-react';
import { Table, type TableColumn } from '../rj-ui/Table';
import { Field, Input } from '../rj-ui/Field';
import { ConfirmDialog } from '../rj-ui/ConfirmDialog';
import { EmptyState } from '../rj-ui/EmptyState';
import type { AdminAction, AdminCatalog } from './catalog';
import { req, type AdminSession } from './api';
import { extraParamsOf, resolvePath, runAction, rowLabel, targetsRow } from './actionApi';
import { NoActionAvailable } from './NoActionAvailable';
import { sentenceFor } from '../api';

type Row = Record<string, unknown>;

/** The response to a GET action is never a bare array (every route on this platform answers
 *  `{ok, <noun>: [...]}` or similar) — take the first array value found, at any depth one level
 *  in. Returns `[]`, never throws, on a shape nobody anticipated: an empty list reads as "read it
 *  and there was nothing", which is honest enough for a generic fallback. */
function firstArray(body: unknown): Row[] {
  if (Array.isArray(body)) return body as Row[];
  if (body && typeof body === 'object') {
    for (const v of Object.values(body as Record<string, unknown>)) {
      if (Array.isArray(v)) return v as Row[];
    }
  }
  return [];
}

function truncate(v: unknown): string {
  if (v == null) return '—';
  if (typeof v === 'object') return JSON.stringify(v).slice(0, 60);
  const s = String(v);
  return s.length > 60 ? `${s.slice(0, 57)}…` : s;
}

/** A raw epoch-seconds number (`0` reads as "never set", not 1970) into a date a human reads at a
 *  glance — the generic engine used to print these as bare numbers (`1799712000`), same value,
 *  unreadable, exactly the complaint a screenshot showed for this table. */
function fmtEpoch(v: unknown): string {
  const n = Number(v);
  if (!n) return '—';
  return new Date(n * 1000).toLocaleDateString('ar-SA-u-nu-latn', {
    year: 'numeric', month: 'short', day: 'numeric',
  });
}

/** `true`/`false`, or the string shape a JSON API sometimes answers with ("true"/"false") — every
 *  other value reads as itself, never silently swallowed into "لا". */
function fmtBool(v: unknown): string {
  if (v === true || v === 'true') return 'نعم';
  if (v === false || v === 'false') return 'لا';
  return truncate(v);
}

/** A DEFAULT icon by shape, when the caller names none for this specific action (`actionMeta`
 *  below) — a generic engine covering hundreds of actions across the whole catalog cannot ask
 *  every caller to pick one for each. Guessed from the verb the method/danger pair usually means:
 *  a destructive POST/DELETE reads as Trash2, a plain POST as Play (fire it), PUT/PATCH as
 *  RotateCcw (change something), GET as Check (a read-only confirm, e.g. "verify"). */
function defaultIcon(a: AdminAction): LucideIcon {
  if (a.danger) return Trash2;
  if (a.method === 'GET') return Check;
  if (a.method === 'PUT' || a.method === 'PATCH') return RotateCcw;
  return Play;
}

export interface ActionMeta {
  /** Arabic label — replaces the catalog's own (often English) `label` on the button's tooltip,
   *  the confirm dialog title, and the error sentence. The catalog value is never mutated; this
   *  is display-only, read by this component alone. */
  label?: string;
  icon?: LucideIcon;
}

export function ActionListGroup({ session, listAction, rowActions, extraQuery, columnLabels,
                                 hiddenColumns, dateColumns, booleanColumns, valueLabels, actionMeta }: {
  session: AdminSession;
  listAction: AdminAction;
  /** Mutating actions from the same catalog group — offered per row when their path param
   *  resolves against it. */
  rowActions: AdminAction[];
  /** Query params a CALLER supplies on top of the plain list — e.g. an operator-chosen tenant a
   *  catalog-declared param exists for but this generic engine has no form to collect on its own
   *  (that stays the caller's own screen, same as `AdminCompliance.tsx`'s customer lookup). Never
   *  read from the catalog itself — only ever what the caller explicitly passes. */
  extraQuery?: Record<string, string>;
  /** Raw response key → Arabic header, e.g. `{status: 'الحالة'}`. A key with no entry falls back
   *  to its raw name (still shown — an untranslated column beats a silently dropped one). */
  columnLabels?: Record<string, string>;
  /** Raw response keys to drop from the table entirely — technical fields with nothing to show a
   *  human (an empty `subject_kind` on every row, say). Never drops `id`/whatever `getRowId` uses. */
  hiddenColumns?: string[];
  /** Raw response keys that carry an epoch-seconds number — rendered via `fmtEpoch` instead of
   *  the raw digits (`1799712000` read at a glance means nothing; a date does). */
  dateColumns?: string[];
  /** Raw response keys that carry a real boolean — rendered as «نعم»/«لا» instead of the raw
   *  `true`/`false`/`"true"` a status-code-shaped API answers with. */
  booleanColumns?: string[];
  /** Raw response key → {raw value → Arabic label} — an enum-shaped column (`status: "pending"`,
   *  `type: "erasure"`) read in English otherwise, since it comes straight off the wire. A value
   *  with no entry falls back to itself, same posture as `columnLabels`. */
  valueLabels?: Record<string, Record<string, string>>;
  /** Per action id — an Arabic label and/or icon, read instead of `defaultIcon`/the catalog's own
   *  (often English) label. See `ActionMeta`'s own docstring. */
  actionMeta?: Record<string, ActionMeta>;
}) {
  const [rows, setRows] = useState<Row[] | 'loading' | 'failed'>('loading');
  const [confirming, setConfirming] = useState<{ action: AdminAction; row: Row | null } | null>(null);
  const [extraValues, setExtraValues] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const qs = extraQuery && Object.keys(extraQuery).length > 0
    ? `?${new URLSearchParams(extraQuery).toString()}` : '';

  const load = () => {
    setRows('loading');
    req<unknown>(`${listAction.path}${qs}`, 'GET', undefined, session.access_token)
      .then((body) => setRows(firstArray(body)))
      .catch(() => setRows('failed'));
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps -- qs is derived from extraQuery each render
  useEffect(load, [session, listAction.path, qs]);

  // ONLY AN ACTION THAT ACTUALLY NAMES THIS ROW — see `targetsRow`'s own docstring: a create or a
  // query/body-only action used to pass this filter trivially (nothing to fail resolving) and
  // show up as a button on every row despite having nothing to do with any one of them.
  const usableRowActions = (row: Row) => rowActions.filter((a) => {
    if (!targetsRow(a)) return false;
    try { resolvePath(a, row); return true; } catch { return false; }
  });

  // THE OTHER HALF OF THAT SAME SPLIT — an action with NO path param never targets an existing
  // row at all; it is a CREATE (a new DSAR, a new legal hold, …). Offered once, above the table,
  // never per-row — the confusion `targetsRow` exists to remove in the first place.
  const createActions = rowActions.filter((a) => !targetsRow(a));

  const labelOf = (a: AdminAction) => actionMeta?.[a.id]?.label ?? a.label;
  const iconOf = (a: AdminAction) => actionMeta?.[a.id]?.icon ?? defaultIcon(a);

  function openConfirm(action: AdminAction, row: Row | null) {
    setExtraValues({});
    setError('');
    setConfirming({ action, row });
  }

  async function confirmAndRun() {
    if (!confirming) return;
    const missing = extraParamsOf(confirming.action)
      .filter((p) => p.required && !(extraValues[p.name] ?? '').trim());
    if (missing.length > 0) {
      setError(`الحقل «${missing[0].name}» مطلوب.`);
      return;
    }
    setBusy(true);
    setError('');
    try {
      await runAction(session, confirming.action, confirming.row, undefined, extraValues);
      setConfirming(null);
      load();
    } catch (err) {
      setError(sentenceFor(err, `تعذّر تنفيذ «${labelOf(confirming.action)}»`));
    } finally {
      setBusy(false);
    }
  }

  const dataKeys = rows === 'loading' || rows === 'failed' || rows.length === 0
    ? []
    : Object.keys(rows[0]).filter((k) => !(hiddenColumns ?? []).includes(k)).slice(0, 6);

  // SMART WIDTH: a fixed-percent grid, computed from however many columns actually survive —
  // fewer, wider columns (a technical id truncates fine; a status/type word needs room to read at
  // a glance) instead of every column claiming an equal, cramped slice regardless of count. The
  // actions column (when present) gets a fixed floor, never squeezed by the count.
  const dataColCount = dataKeys.length;
  const actionsColWidth = rowActions.length > 0 ? 108 : 0;

  const columns: TableColumn<Row>[] = rows === 'loading' || rows === 'failed' || rows.length === 0
    ? []
    : [
        ...dataKeys.map((key): TableColumn<Row> => ({
          key, header: columnLabels?.[key] ?? key,
          render: (r) => (dateColumns ?? []).includes(key) ? fmtEpoch(r[key])
            : (booleanColumns ?? []).includes(key) ? fmtBool(r[key])
            : valueLabels?.[key]?.[String(r[key])] ?? truncate(r[key]),
          width: dataColCount > 0 ? `calc((100% - ${actionsColWidth}px) / ${dataColCount})` : undefined,
        })),
        ...(rowActions.length > 0 ? [{
          key: '__actions',
          header: 'إجراءات',
          width: actionsColWidth,
          render: (r: Row) => (
            <div className="flex flex-wrap gap-1">
              {usableRowActions(r).map((a) => {
                const Icon = iconOf(a);
                return (
                  <button key={a.id} type="button" title={labelOf(a)} aria-label={labelOf(a)}
                         onClick={(e) => { e.stopPropagation(); openConfirm(a, r); }}
                         className={[
                           'grid h-8 w-8 shrink-0 place-items-center rounded-lg border transition',
                           a.danger
                             ? 'border-danger-soft bg-danger-soft text-danger hover:opacity-80'
                             : 'border-border-subtle bg-surface-1 text-text-secondary hover:bg-surface-2',
                         ].join(' ')}>
                    <Icon size={14} aria-hidden />
                  </button>
                );
              })}
            </div>
          ),
          hideOnCard: false,
        } satisfies TableColumn<Row>] : []),
      ];

  const extraFields = confirming ? extraParamsOf(confirming.action) : [];
  const empty = rows !== 'loading' && rows !== 'failed' && rows.length === 0;

  return (
    <div className="flex flex-col gap-3">
      {/* CREATE ACTIONS — offered ONCE here, never per-row (see `createActions`'s own note above).
         Shown even on an empty list: the first row has to come from somewhere. */}
      {createActions.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {createActions.map((a) => {
            const Icon = iconOf(a);
            return (
              <button key={a.id} type="button" onClick={() => openConfirm(a, null)}
                     className={[
                       'flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium transition',
                       a.danger
                         ? 'border-danger-soft bg-danger-soft text-danger hover:opacity-80'
                         : 'border-border-subtle bg-surface-1 text-text-secondary hover:bg-surface-2',
                     ].join(' ')}>
                <Icon size={14} aria-hidden /> {labelOf(a)}
              </button>
            );
          })}
        </div>
      ) : null}

      {empty ? (
        <EmptyState title={`لا نتائج — ${listAction.label}`} />
      ) : (
        <Table columns={columns} rows={rows} getRowId={(r) => String(r.id ?? JSON.stringify(r))}
              emptyTitle={listAction.label} failedTitle={`تعذّرت قراءة "${listAction.label}"`} />
      )}

      {confirming ? (
        <ConfirmDialog
          open onClose={() => { if (!busy) setConfirming(null); }}
          onConfirm={confirmAndRun}
          title={labelOf(confirming.action)}
          body={confirming.action.help}
          danger={confirming.action.danger}
          busy={busy}
          confirmText={confirming.row && confirming.action.danger ? rowLabel(confirming.row) : undefined}
        >
          {/* ANY EXTRA FIELD THE ACTION DECLARES (beyond the row it already targets) — a plain
             text input per one, so an action like «تحقق من الطلب» (needs the code the customer
             reads back) is actually operable here instead of always failing silently with the
             field missing. */}
          {extraFields.length > 0 ? (
            <div className="flex flex-col gap-2">
              {extraFields.map((f) => (
                <Field key={f.name} label={f.name} htmlFor={`extra-${f.name}`}>
                  <Input id={`extra-${f.name}`} dir="ltr"
                        value={extraValues[f.name] ?? ''}
                        onChange={(e) => setExtraValues((v) => ({ ...v, [f.name]: e.target.value }))} />
                </Field>
              ))}
            </div>
          ) : null}
          {error ? <p role="alert" className="text-danger text-sm">{error}</p> : null}
        </ConfirmDialog>
      ) : null}
    </div>
  );
}

/** Groups a catalog slice by `group`, and renders one `ActionListGroup` per group that has a
 *  read (GET, no path params) action — the entry point `ComingSoon` placeholders get swapped for
 *  once a section's real screen isn't built yet. */
export function ActionCatalogPanel({ session, actions, catalog }: {
  session: AdminSession; actions: AdminAction[]; catalog: AdminCatalog;
}) {
  const byGroup = new Map<string, AdminAction[]>();
  for (const a of actions) {
    const key = a.group || 'أخرى';
    byGroup.set(key, [...(byGroup.get(key) ?? []), a]);
  }

  const sections = Array.from(byGroup.entries())
    .map(([group, list]) => {
      const listAction = list.find((a) => a.method === 'GET' && (a.params ?? []).every((p) => p.in !== 'path'));
      const rowActions = list.filter((a) => a.method !== 'GET');
      return listAction ? { group, listAction, rowActions } : null;
    })
    .filter((s): s is { group: string; listAction: AdminAction; rowActions: AdminAction[] } => s !== null);

  if (sections.length === 0) {
    return <NoActionAvailable catalog={catalog} permissionTitle="لا إجراءات متاحة لصلاحياتك هنا بعد" />;
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      {sections.map((s) => (
        <div key={s.group} className="flex flex-col gap-2">
          <h2 className="text-lg font-semibold">{s.listAction.label}</h2>
          <ActionListGroup session={session} listAction={s.listAction} rowActions={s.rowActions} />
        </div>
      ))}
    </div>
  );
}
