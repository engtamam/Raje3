/**
 * «بوابة المسوّق» — الشاشة الرئيسية: كل قسم مبني على حقل حقيقي من `home()`، وغائب تمامًا حين
 * الحقل يقول إنه فارغ — لا "لا شيء بعد" مزيّفة، ولا رقم مخترع.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { AffiliateHome } from './AffiliateHome';
import type { AffiliateSession, Home } from './api';

const SESSION: AffiliateSession = { access_token: 'tok-1' };

const BASE_PROMOTER: Home = {
  affiliate: { id: 'aff-1', name: 'سلمان', role: 'affiliate_promoter' },
  balance: { pending_halalas: 0, confirmed_available_halalas: 0, withdrawn_halalas: 0,
            min_withdrawal_halalas: 0 },
  payout_method_set: false,
  stale_leads_count: 0,
  stale_leads: [],
  open_tickets: [],
  wafa_eligibility: { active_shops: 0, tier_shops: 50, shops_until_next_tier: 50,
                      eligible: false, current_tier_amount_halalas: 0, retention_rate: 1,
                      refund_rate: 0 },
  employment_eligibility: { converted_customers: 0, threshold: 500, eligible: false,
                            customers_until_eligible: 500 },
  top_template_this_period: null,
};

let homeMock: () => Promise<Home>;

vi.mock('./api', async (importOriginal) => {
  const real = await importOriginal<typeof import('./api')>();
  return {
    ...real,
    home: (...args: unknown[]) => homeMock(),
    invite: vi.fn(),
  };
});

afterEach(() => vi.clearAllMocks());

describe('AffiliateHome', () => {
  it('greets him by name once the read resolves', async () => {
    homeMock = () => Promise.resolve(BASE_PROMOTER);
    render(<AffiliateHome session={SESSION} onOpenTicket={() => {}} />);
    await waitFor(() => expect(screen.getByText('مرحباً، سلمان')).toBeTruthy());
  });

  it('shows the urgent strip only when a stale lead actually exists', async () => {
    homeMock = () => Promise.resolve({
      ...BASE_PROMOTER, stale_leads_count: 1,
      stale_leads: [{ id: 'l1', name: 'صالون النخبة', city: 'الرياض', status: 'assigned', found_at: 0 }],
    });
    render(<AffiliateHome session={SESSION} onOpenTicket={() => {}} />);
    await waitFor(() => expect(screen.getByText('عميل واحد بانتظار ردك')).toBeTruthy());
    expect(screen.getByText('صالون النخبة')).toBeTruthy();
  });

  it('the urgent strip is absent for a fresh account with nothing waiting', async () => {
    homeMock = () => Promise.resolve(BASE_PROMOTER);
    render(<AffiliateHome session={SESSION} onOpenTicket={() => {}} />);
    await waitFor(() => expect(screen.getByText('مرحباً، سلمان')).toBeTruthy());
    expect(screen.queryByText(/بانتظار ردك/)).toBeFalsy();
  });

  it('the payout-method nudge appears only when it is genuinely unset', async () => {
    homeMock = () => Promise.resolve({
      ...BASE_PROMOTER, payout_method_set: false,
      balance: { pending_halalas: 0, confirmed_available_halalas: 5000, withdrawn_halalas: 0,
                min_withdrawal_halalas: 0 },
    });
    render(<AffiliateHome session={SESSION} onOpenTicket={() => {}} />);
    await waitFor(() => expect(screen.getByText(/أضف طريقة استلام أرباحك/)).toBeTruthy());
  });

  it('the top-template card is absent until at least one template has been used', async () => {
    homeMock = () => Promise.resolve(BASE_PROMOTER);
    render(<AffiliateHome session={SESSION} onOpenTicket={() => {}} />);
    await waitFor(() => expect(screen.getByText('مرحباً، سلمان')).toBeTruthy());
    expect(screen.queryByText(/أفضل قالب/)).toBeFalsy();
  });

  it('shows the top template once one is returned, with its real advance rate', async () => {
    homeMock = () => Promise.resolve({
      ...BASE_PROMOTER,
      top_template_this_period: { template_id: 't1', title: 'العطاء أولاً', stage_code: 'gatekeeper',
                                  kind: 'رسالة', uses: 13, advanced: 6, no_response: 5, rejected: 2,
                                  pending: 0, advance_rate: 0.46 },
    });
    render(<AffiliateHome session={SESSION} onOpenTicket={() => {}} />);
    await waitFor(() => expect(screen.getByText('العطاء أولاً')).toBeTruthy());
    expect(screen.getByText('46٪')).toBeTruthy();
  });

  it('a promoter never sees the team section — a manager does', async () => {
    homeMock = () => Promise.resolve(BASE_PROMOTER);
    render(<AffiliateHome session={SESSION} onOpenTicket={() => {}} />);
    await waitFor(() => expect(screen.getByText('مرحباً، سلمان')).toBeTruthy());
    expect(screen.queryByText('فريقك')).toBeFalsy();
  });

  it('a manager sees his team, including a pending-decisions badge when one exists', async () => {
    homeMock = () => Promise.resolve({
      ...BASE_PROMOTER,
      affiliate: { id: 'aff-2', name: 'عبدالله', role: 'affiliate_manager' },
      team: { member_count: 3, team_confirmed_halalas: 100000, team_pending_halalas: 5000,
             pending_wafa_requests_count: 2 },
    });
    render(<AffiliateHome session={SESSION} onOpenTicket={() => {}} />);
    await waitFor(() => expect(screen.getByText('فريقك')).toBeTruthy());
    expect(screen.getByText('2 قرار بانتظارك')).toBeTruthy();
  });

  it('a failed read says so rather than showing a stale or empty screen', async () => {
    homeMock = () => Promise.reject(new Error('network'));
    render(<AffiliateHome session={SESSION} onOpenTicket={() => {}} />);
    await waitFor(() => expect(screen.getByRole('alert')).toBeTruthy());
  });

  it('the ticket carousel is absent with no open tickets', async () => {
    homeMock = () => Promise.resolve(BASE_PROMOTER);
    render(<AffiliateHome session={SESSION} onOpenTicket={() => {}} />);
    await waitFor(() => expect(screen.getByText('مرحباً، سلمان')).toBeTruthy());
    expect(screen.queryByText(/تحتاج ردك/)).toBeFalsy();
  });

  it('the ticket carousel shows an open ticket with its shop name', async () => {
    homeMock = () => Promise.resolve({
      ...BASE_PROMOTER,
      open_tickets: [{ id: 'tk-1', tenant: 't1', shop_name: 'مغسلة الأمل',
                       subject: 'الجهاز متوقف', status: 'open', created_at: Math.floor(Date.now() / 1000) }],
    });
    render(<AffiliateHome session={SESSION} onOpenTicket={() => {}} />);
    await waitFor(() => expect(screen.getByText('تذكرة تحتاج ردك')).toBeTruthy());
    expect(screen.getByText('مغسلة الأمل')).toBeTruthy();
    expect(screen.getByText('الجهاز متوقف')).toBeTruthy();
  });

  it('tapping a ticket card hands the exact ticket to onOpenTicket', async () => {
    const ticket = { id: 'tk-2', tenant: 't2', shop_name: 'صالون النخبة', subject: 'استفسار',
                     status: 'open', created_at: Math.floor(Date.now() / 1000) };
    homeMock = () => Promise.resolve({ ...BASE_PROMOTER, open_tickets: [ticket] });
    const onOpenTicket = vi.fn();
    render(<AffiliateHome session={SESSION} onOpenTicket={onOpenTicket} />);
    await waitFor(() => expect(screen.getByText('استفسار')).toBeTruthy());

    screen.getByText('استفسار').closest('button')!.click();
    expect(onOpenTicket).toHaveBeenCalledWith(ticket);
  });
});
