/**
 * SAME REAL, LIVE BUG AS `affiliates/affiliate_portal_signed_out.test.tsx` (2026-09-12):
 * `AdminPortal`'s signed-out branch rendered `<AdminDoor>` with no `<OperatorI18nProvider>`
 * ancestor — `DoorLayout` reads `useOperatorI18n()`, which throws with none. This renders the
 * real top-level `AdminPortal`, unwrapped, exactly as `main.tsx` does.
 */
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AdminPortal } from './AdminPortal';

afterEach(() => { cleanup(); localStorage.clear(); });

describe('AdminPortal, signed out, exactly as main.tsx renders it', () => {
  it('renders the door instead of throwing "useOperatorI18n() outside <OperatorI18nProvider>"', () => {
    localStorage.clear();
    render(<MemoryRouter><AdminPortal /></MemoryRouter>);
    expect(screen.getAllByRole('textbox').length).toBeGreaterThan(0);
  });
});
