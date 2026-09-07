/**
 * `catalog.ts` itself had zero direct tests through phases 1-6 — every consumer mocked
 * `fetchCatalog` with an assumed shape instead of the real one (`{services: [{service,
 * actions}], unreachable}`, per `admin_catalog.py::build_catalog`), so the mistake never
 * surfaced until this file was read directly. These tests exist so it cannot happen again
 * silently: they exercise `allActions`/`byGroup` against the REAL response shape, not a
 * convenient one.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { allActions, byGroup, fetchCatalog, invalidateCatalogCache, type AdminCatalog } from './catalog';

let reqMock: ReturnType<typeof vi.fn>;
vi.mock('./api', async (importOriginal) => {
  const real = await importOriginal<typeof import('./api')>();
  return { ...real, req: (...args: unknown[]) => reqMock(...args) };
});

const CATALOG: AdminCatalog = {
  services: [
    { service: 'billing-service', actions: [
      { id: 'billing.list_plans', label: 'x', method: 'GET', path: '/a', capability: 'c', group: 'Catalogue' },
      { id: 'billing.list_coupons', label: 'x', method: 'GET', path: '/b', capability: 'c', group: 'Catalogue' },
    ] },
    { service: 'tenant-service', actions: [
      { id: 'tenant.list', label: 'x', method: 'GET', path: '/c', capability: 'c' },
    ] },
  ],
  unreachable: ['notification-service'],
};

describe('allActions', () => {
  it('flattens actions across every service, not just the first', () => {
    const flat = allActions(CATALOG);
    expect(flat.map((a) => a.id)).toEqual(['billing.list_plans', 'billing.list_coupons', 'tenant.list']);
  });

  it('an empty services list flattens to an empty array, not a crash', () => {
    expect(allActions({ services: [], unreachable: [] })).toEqual([]);
  });
});

describe('byGroup', () => {
  it('groups across services by the action\'s own group field', () => {
    const groups = byGroup(CATALOG);
    expect(groups.get('Catalogue')?.map((a) => a.id)).toEqual(['billing.list_plans', 'billing.list_coupons']);
  });

  it('an action with no group lands in "أخرى", never dropped', () => {
    const groups = byGroup(CATALOG);
    expect(groups.get('أخرى')?.map((a) => a.id)).toEqual(['tenant.list']);
  });
});

describe('fetchCatalog caching', () => {
  afterEach(() => { vi.clearAllMocks(); invalidateCatalogCache(); });

  it('a second call for the same token, within the TTL, never hits the network again', async () => {
    reqMock = vi.fn().mockResolvedValue(CATALOG);
    const session = { access_token: 'tok-1' };

    const first = await fetchCatalog(session);
    const second = await fetchCatalog(session);

    expect(first).toBe(second);   // THE SAME OBJECT, not just an equal one — one shared promise.
    expect(reqMock).toHaveBeenCalledTimes(1);
  });

  it('a different token is never served the previous token\'s cached answer', async () => {
    reqMock = vi.fn().mockResolvedValue(CATALOG);
    await fetchCatalog({ access_token: 'tok-1' });
    await fetchCatalog({ access_token: 'tok-2' });
    expect(reqMock).toHaveBeenCalledTimes(2);
  });

  it('a failed fetch is never cached — the next call retries the network, not the same rejection', async () => {
    reqMock = vi.fn().mockRejectedValueOnce(new Error('outage')).mockResolvedValueOnce(CATALOG);
    const session = { access_token: 'tok-1' };

    await expect(fetchCatalog(session)).rejects.toThrow('outage');
    const second = await fetchCatalog(session);

    expect(second).toEqual(CATALOG);
    expect(reqMock).toHaveBeenCalledTimes(2);
  });

  it('invalidateCatalogCache forces the very next call back onto the network', async () => {
    reqMock = vi.fn().mockResolvedValue(CATALOG);
    const session = { access_token: 'tok-1' };

    await fetchCatalog(session);
    invalidateCatalogCache();
    await fetchCatalog(session);

    expect(reqMock).toHaveBeenCalledTimes(2);
  });
});
