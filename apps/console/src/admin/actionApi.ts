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

export async function runAction<T = unknown>(
  session: AdminSession, action: AdminAction, row: Record<string, unknown> | null,
  body?: unknown,
): Promise<T> {
  const path = resolvePath(action, row);
  const method = action.method === 'GET' ? 'GET' : action.method;
  return req<T>(path, method, method === 'GET' ? undefined : (body ?? {}), session.access_token);
}

/** A row's own best human-readable label, for the ConfirmDialog's "type this to confirm" arm —
 *  falls back to the resolved path param so a row with no name still gets SOMETHING specific to
 *  type, never a blank confirm-anything. */
export function rowLabel(row: Record<string, unknown> | null): string {
  if (!row) return '';
  const candidate = row.name ?? row.label ?? row.title ?? row.phone ?? row.id;
  return candidate == null ? '' : String(candidate);
}
