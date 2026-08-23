/**
 * The admin catalog — `GET /api/v1/admin/catalog` (platform/services/api-gateway/app/api/v1/
 * admin.py + core/admin_catalog.py), already built and audited: fans out to every service's own
 * `admin_actions.py`, validates each declaration as untrusted input, and filters to only the
 * actions the caller's own capabilities actually reach. We read it, never edit it — that file
 * lives outside `services/` and is `base-services-dc`'s.
 */
import { req, type AdminSession } from './api';

export interface AdminAction {
  id: string;
  label: string;
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  path: string;
  capability: string;
  params?: { name: string; in: 'path' | 'query' | 'body'; type: string; required?: boolean }[];
  confirm?: boolean;
  danger?: boolean;
  group?: string;
  help?: string;
}

export interface AdminCatalog {
  actions: AdminAction[];
}

export async function fetchCatalog(session: AdminSession): Promise<AdminCatalog> {
  return req<AdminCatalog>('/api/v1/admin/catalog', 'GET', undefined, session.access_token);
}

/** Actions grouped by their own `group` field, in first-seen order — the shape §١'s five-section
 *  nav (and later `ActionRenderer`) both read from directly. An action with no group lands in
 *  "أخرى", never silently dropped. */
export function byGroup(catalog: AdminCatalog): Map<string, AdminAction[]> {
  const groups = new Map<string, AdminAction[]>();
  for (const action of catalog.actions) {
    const key = action.group || 'أخرى';
    const list = groups.get(key) ?? [];
    list.push(action);
    groups.set(key, list);
  }
  return groups;
}
