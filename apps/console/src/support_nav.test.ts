/**
 * «الدعم الفني» in the rail — offered on `tickets.open` alone, same rule every other row follows.
 */
import { describe, expect, it } from 'vitest';
import { visibleSections } from './nav';

const catalog = (...ids: string[]) => ({
  services: [{ name: 'ticket-service', actions: ids.map((id) => ({ id, label: id, method: 'GET', path: `/${id}` })) }],
  unreachable: [],
}) as never;

describe('«الدعم الفني» — a row for a shop holding tickets.open', () => {
  it('appears for a role that can raise a ticket', () => {
    const rows = visibleSections(catalog('tickets.open'));
    const support = rows.find((s) => s.label === 'الدعم الفني');
    expect(support).toBeTruthy();
    expect(support?.path).toBe('/support');
  });

  it('is absent for a role that cannot', () => {
    const rows = visibleSections(catalog('operations.record_visit'));
    expect(rows.some((s) => s.label === 'الدعم الفني')).toBe(false);
  });
});
