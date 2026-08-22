import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { AffiliateAccount } from './AffiliateAccount';
import type { AffiliateSession, Me } from './api';

const SESSION: AffiliateSession = { access_token: 'tok-1' };

let meMock: () => Promise<Me>;

vi.mock('./api', async (importOriginal) => {
  const real = await importOriginal<typeof import('./api')>();
  return { ...real, me: (...args: unknown[]) => meMock() };
});

afterEach(() => vi.clearAllMocks());

describe('AffiliateAccount', () => {
  it('shows the signed-in affiliate\'s name and a translated role label', async () => {
    meMock = () => Promise.resolve({ id: 'a1', role: 'affiliate_manager', name: 'سلمان', parent_id: '', status: 'active' });
    render(<AffiliateAccount session={SESSION} onSignOut={() => {}} />);
    await waitFor(() => expect(screen.getByText('سلمان')).toBeTruthy());
    expect(screen.getByText('مدير تسويق')).toBeTruthy();
  });

  it('sign-out fires even if the read is still loading', () => {
    meMock = () => new Promise(() => {});   // never resolves
    const onSignOut = vi.fn();
    render(<AffiliateAccount session={SESSION} onSignOut={onSignOut} />);
    fireEvent.click(screen.getByText('تسجيل الخروج'));
    expect(onSignOut).toHaveBeenCalledOnce();
  });

  it('a failed read still leaves sign-out reachable', async () => {
    meMock = () => Promise.reject(new Error('network'));
    const onSignOut = vi.fn();
    render(<AffiliateAccount session={SESSION} onSignOut={onSignOut} />);
    await waitFor(() => expect(screen.getByText('تعذّرت قراءة بيانات حسابك')).toBeTruthy());
    fireEvent.click(screen.getByText('تسجيل الخروج'));
    expect(onSignOut).toHaveBeenCalledOnce();
  });
});
