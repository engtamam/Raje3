/**
 * «متجر التطبيقات» is a place: a row in the rail, an address, and the destination of every «أضِفه».
 *
 * WHAT SHIPPED BEFORE THIS. Four screens printed the name and none of them could reach it. The
 * locked card of every unbought app said «أضِفه إلى اشتراكي» and pointed at `/account?tab=billing`;
 * the branch cap said «رقِّ باقتك من «متجر التطبيقات»» and pointed at nothing at all. The tab was
 * called «اشتراكي», and the rail had no row for either name. An owner who read the sentence and
 * went looking found four tabs, none of them the one he had just been sent to.
 */
import { describe, expect, it } from 'vitest';
import { render as rtlRender, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { ReactElement } from 'react';
import { SECTIONS, STORE_PATH, visibleSections } from '../nav';
import { LockedCard } from './Locked';
import { ANONYMOUS } from '../session';
import { OperatorI18nProvider } from '../operator-i18n';

// LockedCard now reads `useOperatorI18n()` — wrap once here so every existing `render(<...>)`
// call site below stays unchanged.
const SESSION_FOR_I18N = { tenant: 't1', operator: '', operatorName: '', token: 'tok' } as never;
function render(ui: ReactElement) {
  return rtlRender(<OperatorI18nProvider session={SESSION_FOR_I18N}>{ui}</OperatorI18nProvider>);
}

const catalog = (...ids: string[]) => ({
  services: [{ name: 'billing', actions: ids.map((id) => ({ id, label: id, method: 'GET', path: `/${id}` })) }],
  unreachable: [],
}) as never;

describe('«متجر التطبيقات» — the name has an address now', () => {
  it('is a row in the rail, not a link somebody has to already be looking at', () => {
    const rows = visibleSections(catalog('billing.plans'));
    const store = rows.find((s) => s.label === 'متجر التطبيقات');
    expect(store).toBeTruthy();
    expect(store?.path).toBe(STORE_PATH);
  });

  it('is offered on the shop\'s entitlement, not to everybody', () => {
    // A person the gateway never handed billing to is not shown a till he cannot open — the same
    // rule every other row follows, and the reason none of this needs a role check.
    const rows = visibleSections(catalog('operations.record_visit'));
    expect(rows.some((s) => s.label === 'متجر التطبيقات')).toBe(false);
  });

  it('is the one address every «أضِفه» points at', () => {
    // NOT A SECOND LITERAL. The locked card used to spell out `/account?tab=billing`, so the name
    // in the rail and the destination of the button were two facts that could drift apart.
    render(
      <MemoryRouter>
        <LockedCard appId={'campaigns'} session={ANONYMOUS} catalog={catalog()} />
      </MemoryRouter>,
    );
    const link = screen.getByRole('link');
    expect(link.getAttribute('href')).toContain(STORE_PATH);
    expect(link.textContent).toContain('متجر التطبيقات');
  });

  it('keeps every section pointing at a path the rail can highlight', () => {
    // A query string is not a route, and a row the shell cannot match is a row that never lights
    // up — which is why the store got an address of its own rather than `?tab=`.
    for (const s of SECTIONS) expect(s.path.includes('?')).toBe(false);
  });
});
