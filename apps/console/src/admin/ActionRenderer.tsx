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
import { Table, type TableColumn } from '../rj-ui/Table';
import { Button } from '../rj-ui/Button';
import { ConfirmDialog } from '../rj-ui/ConfirmDialog';
import { EmptyState } from '../rj-ui/EmptyState';
import type { AdminAction, AdminCatalog } from './catalog';
import { req, type AdminSession } from './api';
import { resolvePath, runAction, rowLabel } from './actionApi';
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

export function ActionListGroup({ session, listAction, rowActions }: {
  session: AdminSession;
  listAction: AdminAction;
  /** Mutating actions from the same catalog group — offered per row when their path param
   *  resolves against it. */
  rowActions: AdminAction[];
}) {
  const [rows, setRows] = useState<Row[] | 'loading' | 'failed'>('loading');
  const [confirming, setConfirming] = useState<{ action: AdminAction; row: Row } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const load = () => {
    setRows('loading');
    req<unknown>(listAction.path, 'GET', undefined, session.access_token)
      .then((body) => setRows(firstArray(body)))
      .catch(() => setRows('failed'));
  };
  useEffect(load, [session, listAction.path]);

  const usableRowActions = (row: Row) => rowActions.filter((a) => {
    try { resolvePath(a, row); return true; } catch { return false; }
  });

  async function confirmAndRun() {
    if (!confirming) return;
    setBusy(true);
    setError('');
    try {
      await runAction(session, confirming.action, confirming.row);
      setConfirming(null);
      load();
    } catch (err) {
      setError(sentenceFor(err, `تعذّر تنفيذ «${confirming.action.label}»`));
    } finally {
      setBusy(false);
    }
  }

  const columns: TableColumn<Row>[] = rows === 'loading' || rows === 'failed' || rows.length === 0
    ? []
    : [
        ...Object.keys(rows[0]).slice(0, 6).map((key): TableColumn<Row> => ({
          key, header: key, render: (r) => truncate(r[key]),
        })),
        ...(rowActions.length > 0 ? [{
          key: '__actions',
          header: 'إجراءات',
          render: (r: Row) => (
            <div className="flex flex-wrap gap-1.5">
              {usableRowActions(r).map((a) => (
                <Button key={a.id} type="button" size="sm"
                       variant={a.danger ? 'danger' : 'outline'}
                       onClick={(e) => { e.stopPropagation(); setConfirming({ action: a, row: r }); }}>
                  {a.label}
                </Button>
              ))}
            </div>
          ),
          hideOnCard: false,
        } satisfies TableColumn<Row>] : []),
      ];

  if (rows !== 'loading' && rows !== 'failed' && rows.length === 0) {
    return <EmptyState title={`لا نتائج — ${listAction.label}`} />;
  }

  return (
    <div className="flex flex-col gap-3">
      <Table columns={columns} rows={rows} getRowId={(r) => String(r.id ?? JSON.stringify(r))}
            emptyTitle={listAction.label} failedTitle={`تعذّرت قراءة "${listAction.label}"`} />

      {confirming ? (
        <ConfirmDialog
          open onClose={() => { if (!busy) setConfirming(null); }}
          onConfirm={confirmAndRun}
          title={confirming.action.label}
          body={confirming.action.help}
          danger={confirming.action.danger}
          busy={busy}
          confirmText={confirming.action.danger ? rowLabel(confirming.row) : undefined}
        >
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
