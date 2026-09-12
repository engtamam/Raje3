/**
 * THE ORIGINAL, LIVE BUG (2026-09-12, reported straight off production): the shop console's own
 * `<App/>` rendered `<Door>` with no `<OperatorI18nProvider>` ancestor — `Door.tsx`/`DoorLayout.tsx`
 * were migrated to `useOperatorI18n()` (no fallback) without ever checking they sit inside the
 * provider that migration assumes. Every signed-out visitor to the sign-in page hit
 * "Unexpected Application Error! useOperatorI18n() outside <OperatorI18nProvider>" — the product's
 * own front door, broken for anyone not already signed in.
 *
 * This renders the real top-level `App`, unwrapped, exactly as `main.tsx`'s router does.
 */
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { App } from './App';

afterEach(() => { cleanup(); localStorage.clear(); });

describe('App, signed out, exactly as main.tsx renders it', () => {
  it('renders the door instead of throwing "useOperatorI18n() outside <OperatorI18nProvider>"', () => {
    localStorage.clear();
    render(<MemoryRouter><App /></MemoryRouter>);
    expect(screen.getAllByRole('textbox').length).toBeGreaterThan(0);
  });
});
