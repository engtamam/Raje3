import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { AffiliateAccount } from './AffiliateAccount';
import type { AffiliateSession, Me, PayoutMethod } from './api';

const SESSION: AffiliateSession = { access_token: 'tok-1' };

let meMock: () => Promise<Me>;
let payoutMethodMock: () => Promise<PayoutMethod>;
const setPayoutMethodMock = vi.fn();

vi.mock('./api', async (importOriginal) => {
  const real = await importOriginal<typeof import('./api')>();
  return {
    ...real,
    me: (...args: unknown[]) => meMock(),
    payoutMethod: (...args: unknown[]) => payoutMethodMock(),
    setPayoutMethod: (...args: unknown[]) => setPayoutMethodMock(...args),
  };
});

afterEach(() => vi.clearAllMocks());

describe('AffiliateAccount', () => {
  it('shows the signed-in affiliate\'s name and a translated role label', async () => {
    meMock = () => Promise.resolve({ id: 'a1', role: 'affiliate_manager', name: 'سلمان', parent_id: '', status: 'active' });
    payoutMethodMock = () => Promise.resolve({ set: false });
    render(<AffiliateAccount session={SESSION} onSignOut={() => {}} />);
    await waitFor(() => expect(screen.getByText('سلمان')).toBeTruthy());
    expect(screen.getByText('مدير تسويق')).toBeTruthy();
  });

  it('sign-out fires even if both reads are still loading', () => {
    meMock = () => new Promise(() => {});   // never resolves
    payoutMethodMock = () => new Promise(() => {});
    const onSignOut = vi.fn();
    render(<AffiliateAccount session={SESSION} onSignOut={onSignOut} />);
    fireEvent.click(screen.getByText('تسجيل الخروج'));
    expect(onSignOut).toHaveBeenCalledOnce();
  });

  it('a failed profile read still leaves sign-out reachable', async () => {
    meMock = () => Promise.reject(new Error('network'));
    payoutMethodMock = () => Promise.resolve({ set: false });
    const onSignOut = vi.fn();
    render(<AffiliateAccount session={SESSION} onSignOut={onSignOut} />);
    await waitFor(() => expect(screen.getByText('تعذّرت قراءة بيانات حسابك')).toBeTruthy());
    fireEvent.click(screen.getByText('تسجيل الخروج'));
    expect(onSignOut).toHaveBeenCalledOnce();
  });

  it('an unset payout method nudges him to add one', async () => {
    meMock = () => Promise.resolve({ id: 'a1', role: 'affiliate_promoter', name: 'سلمان', parent_id: '', status: 'active' });
    payoutMethodMock = () => Promise.resolve({ set: false });
    render(<AffiliateAccount session={SESSION} onSignOut={() => {}} />);
    await waitFor(() => expect(screen.getByText(/لن تقدر تسحب أرباحك بدونها/)).toBeTruthy());
  });

  it('a set payout method shows only its masked reference, never a full one', async () => {
    meMock = () => Promise.resolve({ id: 'a1', role: 'affiliate_promoter', name: 'سلمان', parent_id: '', status: 'active' });
    payoutMethodMock = () => Promise.resolve({
      set: true, channel: 'bank_iban', channel_name: '', masked_account_ref: '••••1234',
    });
    render(<AffiliateAccount session={SESSION} onSignOut={() => {}} />);
    await waitFor(() => expect(screen.getByText('••••1234')).toBeTruthy());
    expect(screen.getByText('حساب بنكي (آيبان)')).toBeTruthy();
  });

  it('changing the payout method calls setPayoutMethod with what he typed', async () => {
    meMock = () => Promise.resolve({ id: 'a1', role: 'affiliate_promoter', name: 'سلمان', parent_id: '', status: 'active' });
    payoutMethodMock = () => Promise.resolve({
      set: true, channel: 'bank_iban', channel_name: '', masked_account_ref: '••••1234',
    });
    setPayoutMethodMock.mockResolvedValue({ channel: 'bank_iban', channel_name: '', account_ref: 'SA00' });
    render(<AffiliateAccount session={SESSION} onSignOut={() => {}} />);
    await waitFor(() => expect(screen.getByText('••••1234')).toBeTruthy());

    fireEvent.click(screen.getByText('تغيير'));
    fireEvent.change(screen.getByPlaceholderText('رقم الآيبان'), { target: { value: 'SA9999' } });
    fireEvent.click(screen.getByText('حفظ'));

    await waitFor(() => expect(setPayoutMethodMock).toHaveBeenCalledWith(
      SESSION, { channel: 'bank_iban', channelName: '', accountRef: 'SA9999' }));
  });
});
