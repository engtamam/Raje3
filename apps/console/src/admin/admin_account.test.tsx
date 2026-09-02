/**
 * حسابي — the admin panel's only sign-out button. Found missing entirely (session.ts's own
 * signOut existed, unwired) — this test exists so it cannot silently disappear again.
 */
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { AdminAccount } from './AdminAccount';

describe('AdminAccount', () => {
  it('a sign-out button exists and calls onSignOut', () => {
    const onSignOut = vi.fn();
    render(<AdminAccount onSignOut={onSignOut} />);
    fireEvent.click(screen.getByText('تسجيل الخروج'));
    expect(onSignOut).toHaveBeenCalledOnce();
  });
});
