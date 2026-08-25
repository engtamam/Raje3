/**
 * «أرباحي» — the hero balance always renders even at zero (empty-state-first, confirmed against
 * the live server), the withdraw CTA hides behind an open request rather than sitting next to it,
 * and a manager sees the team card a promoter never does.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { AffiliateEarnings } from './AffiliateEarnings';
import type {
  AffiliateSession, Me, Balance, Commission, WithdrawalRequest, WafaEligibility,
} from './api';

const SESSION: AffiliateSession = { access_token: 'tok-1' };
const ZERO_BALANCE: Balance = {
  pending_halalas: 0, confirmed_available_halalas: 0, withdrawn_halalas: 0, min_withdrawal_halalas: 0,
};
const NO_ELIGIBILITY: WafaEligibility = {
  active_shops: 0, tier_shops: 50, shops_until_next_tier: 50, eligible: false,
  current_tier_amount_halalas: 0, retention_rate: 1, refund_rate: 0,
  support_kpis: { available: false, reason: 'no_shared_tickets' },
  total_referrals: 0, total_commissions: 0,
  recent_conversions: 0, min_recent_conversions: 1, conversion_lookback_days: 30,
};
const NO_EMPLOYMENT_ELIGIBILITY = {
  converted_customers: 0, threshold: 500, eligible: false, customers_until_eligible: 500,
};

let meMock: () => Promise<Me>;
let balanceMock: () => Promise<Balance>;
let commissionsMock: () => Promise<{ commissions: Commission[] }>;
let withdrawalsMock: () => Promise<{ withdrawals: WithdrawalRequest[] }>;
let wafaEligibilityMock: () => Promise<typeof NO_ELIGIBILITY>;
let wafaRequestsMock: () => Promise<{ wafa_requests: [] }>;
let employmentEligibilityMock: () => Promise<typeof NO_EMPLOYMENT_ELIGIBILITY>;
let employmentRequestsMock: () => Promise<{ employment_requests: [] }>;

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
    employmentEligibility: (...args: unknown[]) => employmentEligibilityMock(),
    myEmploymentRequests: (...args: unknown[]) => employmentRequestsMock(),
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
  employmentEligibilityMock = () => Promise.resolve(NO_EMPLOYMENT_ELIGIBILITY);
  employmentRequestsMock = () => Promise.resolve({ employment_requests: [] });
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

  it('shows his OWN performance numbers on the wafa card — a manager included, same as any marketer', async () => {
    // "مدير التسويق يعتبر مسوّي، عنده نفس المؤشرات لنفسه" — this used to be the
    // ONE thing a manager could see about his TEAM (GET /me/team) but never about himself.
    meMock = () => Promise.resolve(MANAGER);
    stubCommon();
    wafaEligibilityMock = () => Promise.resolve({
      ...NO_ELIGIBILITY, retention_rate: 0.82, refund_rate: 0.05, total_referrals: 10,
      total_commissions: 4,
      support_kpis: { available: true, avg_first_response_seconds: 300,
                     avg_resolution_seconds: 7200, escalation_rate: 0.1 },
    });
    render(<AffiliateEarnings session={SESSION} />);
    await waitFor(() => expect(screen.getByText('معدّل الاحتفاظ')).toBeTruthy());
    expect(screen.getByText('82٪')).toBeTruthy();
    expect(screen.getByText('5 دقيقة')).toBeTruthy();   // avg_first_response_seconds: 300
    expect(screen.getByText('2 ساعة')).toBeTruthy();     // avg_resolution_seconds: 7200
  });

  it('says support kpis are not in yet, rather than a blank or a fabricated zero', async () => {
    meMock = () => Promise.resolve(PROMOTER);
    stubCommon();   // NO_ELIGIBILITY's own support_kpis: { available: false }
    render(<AffiliateEarnings session={SESSION} />);
    await waitFor(() => expect(screen.getByText('معدّل الاحتفاظ')).toBeTruthy());
    expect(screen.getByText(/تظهر أول ما محل يشارك تذاكره/)).toBeTruthy();
  });

  it('never shows a fabricated 100% retention with zero referred shops behind it', async () => {
    // "كيف كذا وهو صفر اساس! في غلط في المعادلة" — retention_rate defaults to
    // 1.0 with no referral history at all (correct for the eligibility FORMULA, wrong to present
    // as an earned 100%). NO_ELIGIBILITY's own retention_rate is already 1 with total_referrals: 0.
    meMock = () => Promise.resolve(PROMOTER);
    stubCommon();
    render(<AffiliateEarnings session={SESSION} />);
    await waitFor(() => expect(screen.getByText('معدّل الاحتفاظ')).toBeTruthy());
    expect(screen.queryByText('100٪')).toBeFalsy();
    expect(screen.queryByText('0٪')).toBeFalsy();   // refund_rate's own fabricated default
    const dashes = screen.getAllByText('—');
    expect(dashes.length).toBe(2);   // retention AND refund, both with no sample behind them
  });

  it('tells him he has enough shops but needs a recent conversion, not the shop-count progress message', async () => {
    meMock = () => Promise.resolve(PROMOTER);
    stubCommon();
    wafaEligibilityMock = () => Promise.resolve({
      ...NO_ELIGIBILITY, active_shops: 50, shops_until_next_tier: 50,
    });
    render(<AffiliateEarnings session={SESSION} />);
    await waitFor(() => expect(screen.getByText(/عندك 50 محل/)).toBeTruthy());
    expect(screen.getByText(/عميلاً جديداً/)).toBeTruthy();
    expect(screen.getByText(/آخر 30 يوماً/)).toBeTruthy();
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

  it('the employment card shows the request action once eligible', async () => {
    meMock = () => Promise.resolve(PROMOTER);
    stubCommon();
    employmentEligibilityMock = () => Promise.resolve({
      converted_customers: 500, threshold: 500, eligible: true, customers_until_eligible: 0,
    });
    render(<AffiliateEarnings session={SESSION} />);
    await waitFor(() => expect(screen.getByText('رشّح نفسي')).toBeTruthy());
  });

  it('the employment card has no action before eligibility is reached', async () => {
    meMock = () => Promise.resolve(PROMOTER);
    stubCommon();
    render(<AffiliateEarnings session={SESSION} />);
    await waitFor(() => expect(screen.getByText('رشّح نفسك لوظيفة')).toBeTruthy());
    expect(screen.queryByText('رشّح نفسي')).toBeFalsy();
  });
});
