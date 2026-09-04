/**
 * The admin catalog — `GET /api/v1/admin/catalog` (platform/services/api-gateway/app/api/v1/
 * admin.py + core/admin_catalog.py), already built and audited: fans out to every service's own
 * `admin_actions.py`, validates each declaration as untrusted input, and filters to only the
 * actions the caller's own capabilities actually reach. We read it, never edit it — that file
 * lives outside `services/` and is `base-services-dc`'s.
 *
 * REAL SHAPE, VERIFIED AGAINST `admin_catalog.py::build_catalog` DIRECTLY (2026-08-24, after this
 * module shipped with the WRONG one for several phases and every consumer's own test mocked
 * around the mistake instead of catching it) — grouped BY SERVICE, never a flat action list:
 *   {"services": [{"service": "affiliate-service", "actions": [...]}], "unreachable": [...]}
 * `unreachable` names a configured service that failed to answer — reported, not swallowed, per
 * the aggregator's own header note ("a missing service should be visible, not invisible").
 */
import { req, type AdminSession } from './api';

export interface AdminAction {
  id: string;
  label: string;
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  path: string;
  capability: string;
  params?: {
    name: string; in: 'path' | 'query' | 'body'; type: string; required?: boolean;
    // OPTIONAL, and untouched by the aggregator's own sanitizer (platform/services/api-gateway's
    // admin_catalog.py keeps every param object whole, filtering only on `name` being a string —
    // see its own note) — a service that knows its exact expected credential names declares them
    // here instead of leaving an operator to type one by hand and hope it matches. AdminSecrets.tsx
    // renders a picker when this is present, free text when it is not; no schema change needed on
    // the aggregator side to add it.
    choices?: { value: string; label: string; impact: string }[];
  }[];
  confirm?: boolean;
  danger?: boolean;
  group?: string;
  help?: string;
}

export interface AdminCatalog {
  services: { service: string; actions: AdminAction[] }[];
  unreachable: string[];
}

export async function fetchCatalog(session: AdminSession): Promise<AdminCatalog> {
  return req<AdminCatalog>('/api/v1/admin/catalog', 'GET', undefined, session.access_token);
}

/** Every action across every service, flattened — the shape most screens actually want. Two
 *  services declaring the same `id` is possible in principle (nothing in the aggregator
 *  deduplicates across services, only validates each in isolation), so callers that key off `id`
 *  should still treat the first match as authoritative rather than assume uniqueness. */
export function allActions(catalog: AdminCatalog): AdminAction[] {
  return catalog.services.flatMap((s) => s.actions);
}

/** Actions grouped by their own `group` field, in first-seen order — the shape §1's five-section
 *  nav (and `ActionRenderer`) both read from directly. An action with no group lands in "أخرى",
 *  never silently dropped. Flattens across services first — `group` is a UI grouping independent
 *  of which service happened to declare the action. */
export function byGroup(catalog: AdminCatalog): Map<string, AdminAction[]> {
  const groups = new Map<string, AdminAction[]>();
  for (const action of allActions(catalog)) {
    const key = action.group || 'أخرى';
    const list = groups.get(key) ?? [];
    list.push(action);
    groups.set(key, list);
  }
  return groups;
}
