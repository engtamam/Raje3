/**
 * AppShell (ui/packages/ui/src/shell/AppShell.tsx) — the sidebar redesign's own accessibility
 * fixes, pinned down directly rather than trusted by eye: a collapsed rail's accessible name, and
 * the mobile drawer's dialog semantics + Escape-to-close.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AppShell, type AppShellNavItem } from '../../../ui/packages/ui/src/shell';
import { Home } from 'lucide-react';

afterEach(() => { cleanup(); localStorage.clear(); });

const ITEMS: AppShellNavItem[] = [{ to: '/', label: 'الرئيسية', icon: Home }];
const LABELS = { collapse: 'طي', expand: 'توسيع', signOut: 'خروج', account: 'حسابي' };

function renderShell() {
  return render(
    <MemoryRouter>
      <AppShell
        navItems={ITEMS}
        brand={{ name: 'راجع' }}
        user={{ name: 'محمد' }}
        labels={LABELS}
        onSignOut={() => {}}
      />
    </MemoryRouter>,
  );
}

describe('AppShell — collapsed rail keeps a real accessible name', () => {
  it('a collapsed item is announced by aria-label, not just a hover title', () => {
    renderShell();
    fireEvent.click(screen.getByTestId('nav-collapse'));
    // getByRole('link', { name }) resolves via the accessible name computation, which reads
    // aria-label — the exact thing `title=` alone (the previous behaviour) never gives a screen
    // reader, since it is only exposed on hover.
    expect(screen.getByRole('link', { name: 'الرئيسية' })).toBeTruthy();
  });
});

describe('AppShell — the mobile drawer is a real dialog', () => {
  it('carries role=dialog and aria-modal only while open', () => {
    renderShell();
    const sidebar = screen.getByTestId('sidebar');
    expect(sidebar.getAttribute('role')).toBeNull();

    fireEvent.click(screen.getByLabelText(LABELS.expand));
    expect(sidebar.getAttribute('role')).toBe('dialog');
    expect(sidebar.getAttribute('aria-modal')).toBe('true');
  });

  it('Escape closes it, the same as the scrim tap', () => {
    renderShell();
    fireEvent.click(screen.getByLabelText(LABELS.expand));
    expect(screen.getByTestId('sidebar').getAttribute('role')).toBe('dialog');

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.getByTestId('sidebar').getAttribute('role')).toBeNull();
  });
});
