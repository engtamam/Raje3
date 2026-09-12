/**
 * A REAL, LIVE BUG (2026-09-12): `AffiliatePortal`'s signed-out branch rendered `<AffiliateDoor>`
 * with no `<OperatorI18nProvider>` ancestor anywhere — `DoorLayout` (shared with the shop door)
 * reads `useOperatorI18n()`, which throws with no provider, so every signed-out visitor to the
 * affiliate portal hit a hard crash. `affiliate_door.test.tsx` never caught this because it wraps
 * `<AffiliateDoor>` directly in its own test-only provider — this test renders the real top-level
 * `AffiliatePortal` component, unwrapped, exactly as `main.tsx` does, so a missing provider here
 * fails loudly again if it ever regresses.
 */
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AffiliatePortal } from './AffiliatePortal';

afterEach(() => { cleanup(); localStorage.clear(); });

describe('AffiliatePortal, signed out, exactly as main.tsx renders it', () => {
  it('renders the door instead of throwing "useOperatorI18n() outside <OperatorI18nProvider>"', () => {
    localStorage.clear();
    render(<MemoryRouter><AffiliatePortal /></MemoryRouter>);
    expect(screen.getAllByRole('textbox').length).toBeGreaterThan(0);
  });
});
