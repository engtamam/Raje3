/**
 * `catalog.ts` itself had zero direct tests through phases 1-6 — every consumer mocked
 * `fetchCatalog` with an assumed shape instead of the real one (`{services: [{service,
 * actions}], unreachable}`, per `admin_catalog.py::build_catalog`), so the mistake never
 * surfaced until this file was read directly. These tests exist so it cannot happen again
 * silently: they exercise `allActions`/`byGroup` against the REAL response shape, not a
 * convenient one.
 */
import { describe, expect, it } from 'vitest';
import { allActions, byGroup, type AdminCatalog } from './catalog';

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
