/**
 * Home.tsx — «/» picks a screen by role, and now prefers «تسجيل زيارة» over «محلّي» when a person
 * holds both (2026-09-14, owner's own call: fewer requests fired on the one route every sign-in
 * and reload lands on first). Visit.tsx/Shop.tsx are heavy real screens with their own data
 * fetching — mocked here to a marker so this test asserts ONLY which one Home.tsx picked.
 */
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { OperatorI18nProvider } from '../operator-i18n';
import type { Catalog } from '../catalog';

vi.mock('./Shop', () => ({ ShopScreen: () => <div data-testid="shop-screen" /> }));
vi.mock('./Visit', () => ({ Visit: () => <div data-testid="visit-screen" /> }));

let outletCatalog: Catalog;
vi.mock('react-router-dom', async (importOriginal) => {
  const real = await importOriginal<typeof import('react-router-dom')>();
  return { ...real, useOutletContext: () => ({ catalog: outletCatalog }) };
});

const { Home } = await import('./Home');

function open() {
  return render(
    <MemoryRouter>
      <OperatorI18nProvider session={{} as never}>
        <Home />
      </OperatorI18nProvider>
    </MemoryRouter>,
  );
}

function catalogWith(...actionIds: string[]): Catalog {
  return {
    services: [{ service: 'x', actions: actionIds.map((id) => (
      { id, label: id, method: 'GET', path: '/', capability: id })) }],
    unreachable: [],
  };
}

describe('Home — the default landing screen', () => {
  it('an owner with every section lands on «تسجيل زيارة», not «محلّي»', () => {
    // Every action every SECTIONS row requires — an owner/manager holds them all.
    outletCatalog = catalogWith(
      'reminders.today', 'insights.dashboard', 'operations.record_visit', 'bookings.list',
      'operations.recent', 'operations.ratings', 'operations.update_service',
      'reminders.get_settings', 'loyalty.rewards.update', 'billing.plans', 'tickets.open',
    );
    open();
    expect(screen.getByTestId('visit-screen')).toBeTruthy();
    expect(screen.queryByTestId('shop-screen')).toBeFalsy();
  });

  it('an operator with only «تسجيل زيارة» is unaffected — same screen as always', () => {
    outletCatalog = catalogWith('operations.record_visit');
    open();
    expect(screen.getByTestId('visit-screen')).toBeTruthy();
  });

  it('a role with «محلّي» but not «تسجيل زيارة» still lands on «محلّي»', () => {
    outletCatalog = catalogWith('reminders.today', 'insights.dashboard');
    open();
    expect(screen.getByTestId('shop-screen')).toBeTruthy();
    expect(screen.queryByTestId('visit-screen')).toBeFalsy();
  });

  it('a role reaching neither shows the honest empty state, not a blank page', () => {
    outletCatalog = catalogWith();
    open();
    expect(screen.queryByTestId('visit-screen')).toBeFalsy();
    expect(screen.queryByTestId('shop-screen')).toBeFalsy();
  });
});
