/**
 * `Can` is the one primitive new write-action call sites are meant to compose from now on
 * (2026-09-24, phase 1 of the permission-gate effort) — these tests pin its ONLY real contract:
 * renders `children` iff `action(catalog, id)` returns a real action, exactly the same question
 * every existing inline `action(catalog, id) ? <Btn/> : null` already asks.
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Can } from './Can';
import type { Action, Catalog } from './catalog';

function catalogWith(ids: string[]): Catalog {
  const actions: Action[] = ids.map((id) => ({
    id, label: id, method: 'POST', path: '/x', capability: id,
  }));
  return { services: [{ service: 'operations', actions }], unreachable: [] };
}

describe('Can', () => {
  it('renders children when the catalogue holds the action', () => {
    render(<Can catalog={catalogWith(['operations.update_service'])} action="operations.update_service">تعديل</Can>);
    expect(screen.getByText('تعديل')).toBeTruthy();
  });

  it('renders nothing when the catalogue lacks the action', () => {
    render(<Can catalog={catalogWith(['operations.list_services'])} action="operations.update_service">تعديل</Can>);
    expect(screen.queryByText('تعديل')).toBeFalsy();
  });

  it('renders nothing against an empty catalogue', () => {
    render(<Can catalog={{ services: [], unreachable: [] }} action="operations.update_service">تعديل</Can>);
    expect(screen.queryByText('تعديل')).toBeFalsy();
  });
});
