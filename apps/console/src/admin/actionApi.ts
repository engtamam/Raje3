/**
 * Running a declared admin action — the one place a `{id, method, path, params}` row from the
 * catalog turns into a real HTTP call. Every screen that reads/writes through the catalog goes
 * through this, so the substitution rule (path params only, one shape) is written once.
 */
import { req, type AdminSession } from './api';
import type { AdminAction } from './catalog';

/** `/api/v1/admin/affiliates/{application_id}/approve` + a row carrying `application_id` (or,
 *  failing that, `id` — most of this platform's list rows key themselves `id`, not
 *  `<noun>_id`, so a raw param-name match alone would miss almost every real row) → the real
 *  path. Throws if a required path param cannot be resolved from the row at all — better a clear
 *  error here than a request sent with a literal `{application_id}` still in the URL. */
export function resolvePath(action: AdminAction, row: Record<string, unknown> | null): string {
  let path = action.path;
  for (const p of action.params ?? []) {
    if (p.in !== 'path') continue;
    const raw = row?.[p.name] ?? row?.id;
    if (raw == null || raw === '') {
      throw new Error(`تعذّر تنفيذ "${action.label}" — الحقل ${p.name} غير متاح بهذا الصف.`);
    }
    path = path.replace(`{${p.name}}`, encodeURIComponent(String(raw)));
  }
  return path;
}

/** TRUE only when this action actually NAMES the row it acts on (a real `path` param it resolves
 *  against — see `resolvePath`). An action with NO path params (a plain create, or one scoped
 *  entirely by query/body params) trivially "resolves" against ANY row, which used to make it
 *  show up as a button on every single row despite having nothing to do with any one of them —
 *  found live: compliance's «Open a DSAR» (a CREATE, no path param at all) appeared as a row
 *  button on every DSAR already open, and pressing it opened ANOTHER one, unrelated to the row it
 *  sat under. This is the actual gate `usableRowActions` filters on now. */
export function targetsRow(action: AdminAction): boolean {
  return (action.params ?? []).some((p) => p.in === 'path');
}

/** Every declared param this action needs BEYOND the row it targets — query or body, never path
 *  (those come from the row itself, silently). `ActionListGroup`'s own confirm step renders one
 *  plain text field per entry so an action like `compliance.verify_dsar` (needs `token`, the code
 *  a customer reads back over the phone) is actually operable through the generic engine instead
 *  of silently calling the route with the field missing and reading "تعذّر إكمال الطلب" with no
 *  hint why — found live, the exact symptom on a real screenshot. */
export function extraParamsOf(action: AdminAction): { name: string; in: 'query' | 'body'; required?: boolean }[] {
  return (action.params ?? []).filter((p): p is typeof p & { in: 'query' | 'body' } => p.in !== 'path');
}

export async function runAction<T = unknown>(
  session: AdminSession, action: AdminAction, row: Record<string, unknown> | null,
  body?: unknown, extra?: Record<string, string>,
): Promise<T> {
  let path = resolvePath(action, row);
  const method = action.method === 'GET' ? 'GET' : action.method;
  const bodyOut: Record<string, unknown> = { ...(typeof body === 'object' && body ? body : {}) };
  const query = new URLSearchParams();
  for (const p of extraParamsOf(action)) {
    const v = extra?.[p.name];
    if (v == null || v === '') continue;
    if (p.in === 'query') query.set(p.name, v); else bodyOut[p.name] = v;
  }
  const qs = query.toString();
  if (qs) path += (path.includes('?') ? '&' : '?') + qs;
  return req<T>(path, method, method === 'GET' ? undefined : bodyOut, session.access_token);
}

/** A row's own best human-readable label, for the ConfirmDialog's "type this to confirm" arm —
 *  falls back to the resolved path param so a row with no name still gets SOMETHING specific to
 *  type, never a blank confirm-anything. */
export function rowLabel(row: Record<string, unknown> | null): string {
  if (!row) return '';
  const candidate = row.name ?? row.label ?? row.title ?? row.phone ?? row.id;
  return candidate == null ? '' : String(candidate);
}
