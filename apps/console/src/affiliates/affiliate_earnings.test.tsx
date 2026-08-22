/**
 * «أرباحي» — the hero balance always renders even at zero (empty-state-first, confirmed against
 * the live server), the withdraw CTA hides behind an open request rather than sitting next to it,
 * and a manager sees the team card a promoter never does.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { AffiliateEarnings } from './AffiliateEarnings';
import type {
  AffiliateSession, Me, Balance, Commission, WithdrawalRequest, Team,
} from './api';

const SESSION: AffiliateSession = { access_token: 'tok-1' };
const ZERO_BALANCE: Balance = { pending_halalas: 0, confirmed_available_halalas: 0, withdrawn_halalas: 0 };
const NO_ELIGIBILITY = {
  active_shops: 0, tier_shops: 50, shops_until_next_tier: 50, eligible: false,
  current_tier_amount_halalas: 0, retention_rate: 1, refund_rate: 0,
};

let meMock: () => Promise<Me>;
let balanceMock: () => Promise<Balance>;
let commissionsMock: () => Promise<{ commissions: Commission[] }>;
let withdrawalsMock: () => Promise<{ withdrawals: WithdrawalRequest[] }>;
let wafaEligibilityMock: () => Promise<typeof NO_ELIGIBILITY>;
let wafaRequestsMock: () => Promise<{ wafa_requests: [] }>;
let teamMock: () => Promise<Team>;
let teamWafaMock: () => Promise<{ wafa_requests: [] }>;

vi.mock('./api', async (importOriginal) => {
  const real = await importOriginal<typeof import('./api')>();
  return {
    ...real,
    me: (...args: unknown[]) => meMock(),
    balance: (...args: unknown[]) => balanceMock(),
    commissions: (...args: unknown[]) => commissionsMock(),
    myWithdrawals: (...args: unknown[]) => withdrawalsMock(),
    wafaEligibility: (...args: unknown[]) => wafaEligibilityMock(),
    myWafaRequests: (...args: unknown[]) => wafaRequestsMock(),
    team: (...args: unknown[]) => teamMock(),
    teamWafaRequests: (...args: unknown[]) => teamWafaMock(),
  };
});

const PROMOTER: Me = { id: 'a1', role: 'affiliate_promoter', name: 'سلمان', parent_id: '', status: 'active' };
const MANAGER: Me = { id: 'a2', role: 'affiliate_manager', name: 'عبدالله', parent_id: '', status: 'active' };

function stubCommon() {
  balanceMock = () => Promise.resolve(ZERO_BALANCE);
  commissionsMock = () => Promise.resolve({ commissions: [] });
  withdrawalsMock = () => Promise.resolve({ withdrawals: [] });
  wafaEligibilityMock = () => Promise.resolve(NO_ELIGIBILITY);
  wafaRequestsMock = () => Promise.resolve({ wafa_requests: [] });
  teamWafaMock = () => Promise.resolve({ wafa_requests: [] });
}

afterEach(() => vi.clearAllMocks());

describe('AffiliateEarnings', () => {
  it('renders an honest zero balance for a brand-new marketer, never a broken-looking blank', async () => {
    meMock = () => Promise.resolve(PROMOTER);
    stubCommon();
    render(<AffiliateEarnings session={SESSION} />);
    await waitFor(() => expect(screen.getByText('رصيدك الجاهز للسحب')).toBeTruthy());
    expect(screen.getAllByText('0 ريال').length).toBeGreaterThan(0);
    expect(screen.getByText('لا عمولات بعد')).toBeTruthy();
  });

  it('the withdraw CTA is replaced by the open-request notice, never shown alongside it', async () => {
    meMock = () => Promise.resolve(PROMOTER);
    stubCommon();
    balanceMock = () => Promise.resolve({ ...ZERO_BALANCE, confirmed_available_halalas: 5000 });
    withdrawalsMock = () => Promise.resolve({
      withdrawals: [{ id: 'w1', affiliate_id: 'a1', amount_halalas: 5000, commission_ids: [],
                     status: 'requested', payout_channel: 'bank_iban', payout_channel_name: '',
                     payout_account_ref: '', requested_at: 0, decided_at: 0, decided_by: '',
                     receipt_reference: '', receipt_content_type: '', reason: '' }],
    });
    render(<AffiliateEarnings session={SESSION} />);
    await waitFor(() => expect(screen.getByText(/طلب سحبك بقيمة/)).toBeTruthy());
    expect(screen.queryByText('اسحب أرباحك')).toBeFalsy();
  });

  it('a promoter never sees the team-earnings card', async () => {
    meMock = () => Promise.resolve(PROMOTER);
    stubCommon();
    render(<AffiliateEarnings session={SESSION} />);
    await waitFor(() => expect(screen.getByText('رصيدك الجاهز للسحب')).toBeTruthy());
    expect(screen.queryByText('أرباح فريقك')).toBeFalsy();
  });

  it('a manager sees the team-earnings card with real member figures', async () => {
    meMock = () => Promise.resolve(MANAGER);
    stubCommon();
    teamMock = () => Promise.resolve({
      my_shops: 2, my_net_revenue_minor: 0, my_revenue_partial: false,
      members: [{ id: 'm1', name: 'فيصل', status: 'active', confirmed_halalas: 10000,
                 pending_halalas: 0, commission_count: 2, shops: 3, total_net_revenue_minor: 0,
                 revenue_partial: false }],
      team_confirmed_halalas: 10000, team_pending_halalas: 0, team_net_revenue_minor: 0,
      team_revenue_partial: false, platform_revenue_enabled: false,
    });
    render(<AffiliateEarnings session={SESSION} />);
    await waitFor(() => expect(screen.getByText('أرباح فريقك')).toBeTruthy());
    expect(screen.getByText('فيصل')).toBeTruthy();
  });

  it('lists a commission with its real status label', async () => {
    meMock = () => Promise.resolve(PROMOTER);
    stubCommon();
    commissionsMock = () => Promise.resolve({
      commissions: [{ id: 'c1', tenant: 't1', affiliate_id: 'a1', kind: 'conversion',
                     amount_halalas: 15000, status: 'confirmed', earned_at: '', confirms_at: 0,
                     created_at: 100, withdrawal_id: '' }],
    });
    render(<AffiliateEarnings session={SESSION} />);
    await waitFor(() => expect(screen.getByText('150 ريال')).toBeTruthy());
    expect(screen.getByText('مؤكَّدة')).toBeTruthy();
  });
});
