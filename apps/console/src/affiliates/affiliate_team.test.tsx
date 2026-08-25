/**
 * «فريقي» — moved out of «أرباحي» entirely ("فريقه خلاص ننقلها لتبويب مختلف
 * بشكل ذكي كل شي عن فريقه هناك"): the roster + its earnings, the pending WAFA queue, and — new —
 * each member's own performance numbers (retention/refund/support KPIs), previously computed by
 * the backend and silently discarded by the frontend.
 *
 * NO MORE INVITE FORM (2026-08-23) — the manager shares his OWN referral link himself; see this
 * file's own ReferralLinkSection.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { AffiliateTeam } from './AffiliateTeam';
import type { AffiliateSession, Me, Team, WafaRequest } from './api';

vi.mock('qrcode', () => ({
  default: { toDataURL: vi.fn(async (text: string) => `data:image/png;base64,QR(${text})`) },
}));

const SESSION: AffiliateSession = { access_token: 'tok-1' };

let teamMock: () => Promise<Team>;
let teamWafaMock: () => Promise<{ wafa_requests: WafaRequest[] }>;
let meMock: () => Promise<Me>;
const decideCalls: { id: string; decision: string }[] = [];

vi.mock('./api', async (importOriginal) => {
  const real = await importOriginal<typeof import('./api')>();
  return {
    ...real,
    team: (...args: unknown[]) => teamMock(),
    teamWafaRequests: (...args: unknown[]) => teamWafaMock(),
    me: (...args: unknown[]) => meMock(),
    decideTeamWafaRequest: async (_s: unknown, id: string, decision: string) => {
      decideCalls.push({ id, decision });
      return { ok: true };
    },
  };
});

const EMPTY_TEAM: Team = {
  my_shops: 0, my_net_revenue_minor: 0, my_revenue_partial: false, members: [],
  team_confirmed_halalas: 0, team_pending_halalas: 0, team_net_revenue_minor: 0,
  team_revenue_partial: false, platform_revenue_enabled: false,
};

const SELF: Me = { id: 'mgr-1', role: 'affiliate_manager', name: 'عبدالله', parent_id: '',
                   status: 'active' };

afterEach(() => { vi.clearAllMocks(); decideCalls.length = 0; });

describe('AffiliateTeam — referral link', () => {
  it('shows the manager\'s own referral link, ready to copy or download as a QR code', async () => {
    teamMock = () => Promise.resolve(EMPTY_TEAM);
    teamWafaMock = () => Promise.resolve({ wafa_requests: [] });
    meMock = () => Promise.resolve(SELF);
    render(<AffiliateTeam session={SESSION} />);
    await waitFor(() => expect(screen.getByText('أضف عضواً لفريقك')).toBeTruthy());
    const input = screen.getByDisplayValue(/\/affiliates\?ref=mgr-1$/);
    expect(input).toBeTruthy();
    expect(screen.getByLabelText('تنزيل كباركود')).toBeTruthy();
  });

  it('copying writes the exact link to the clipboard', async () => {
    teamMock = () => Promise.resolve(EMPTY_TEAM);
    teamWafaMock = () => Promise.resolve({ wafa_requests: [] });
    meMock = () => Promise.resolve(SELF);
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    render(<AffiliateTeam session={SESSION} />);
    await waitFor(() => expect(screen.getByText('أضف عضواً لفريقك')).toBeTruthy());

    fireEvent.click(screen.getByText('نسخ'));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(
      `${window.location.origin}/affiliates?ref=mgr-1`));
  });
});

describe('AffiliateTeam — roster', () => {
  it('an honest empty state before any team member exists', async () => {
    teamMock = () => Promise.resolve(EMPTY_TEAM);
    teamWafaMock = () => Promise.resolve({ wafa_requests: [] });
    render(<AffiliateTeam session={SESSION} />);
    await waitFor(() => expect(screen.getByText('لا أعضاء بفريقك بعد.')).toBeTruthy());
  });

  it('lists a member with his earnings, and expands to his performance on tap', async () => {
    teamMock = () => Promise.resolve({
      ...EMPTY_TEAM,
      members: [{ id: 'm1', name: 'فيصل', status: 'active', confirmed_halalas: 10000,
                 pending_halalas: 0, commission_count: 2, shops: 3, total_net_revenue_minor: 0,
                 revenue_partial: false, active_shops: 3, retention_rate: 0.9, refund_rate: 0.02,
                 total_referrals: 10, total_commissions: 5,
                 support_kpis: { available: true, avg_first_response_seconds: 120,
                                avg_resolution_seconds: 3600, escalation_rate: 0.05 } }],
      team_confirmed_halalas: 10000,
    });
    teamWafaMock = () => Promise.resolve({ wafa_requests: [] });
    render(<AffiliateTeam session={SESSION} />);
    await waitFor(() => expect(screen.getByText('فيصل')).toBeTruthy());
    expect(screen.queryByText('معدّل الاحتفاظ')).toBeFalsy();   // collapsed by default

    fireEvent.click(screen.getByText('فيصل').closest('button')!);
    await waitFor(() => expect(screen.getByText('معدّل الاحتفاظ')).toBeTruthy());
    expect(screen.getByText('90٪')).toBeTruthy();
  });

  it('a member with no performance data yet cannot be expanded', async () => {
    teamMock = () => Promise.resolve({
      ...EMPTY_TEAM,
      members: [{ id: 'm2', name: 'نورة', status: 'active', confirmed_halalas: 0,
                 pending_halalas: 0, commission_count: 0, shops: 0, total_net_revenue_minor: 0,
                 revenue_partial: false }],
    });
    teamWafaMock = () => Promise.resolve({ wafa_requests: [] });
    render(<AffiliateTeam session={SESSION} />);
    await waitFor(() => expect(screen.getByText('نورة')).toBeTruthy());
    expect((screen.getByText('نورة').closest('button') as HTMLButtonElement).disabled).toBe(true);
  });
});

describe('AffiliateTeam — WAFA queue', () => {
  it('is absent with nothing pending', async () => {
    teamMock = () => Promise.resolve(EMPTY_TEAM);
    teamWafaMock = () => Promise.resolve({ wafa_requests: [] });
    render(<AffiliateTeam session={SESSION} />);
    await waitFor(() => expect(screen.getByText('لا أعضاء بفريقك بعد.')).toBeTruthy());
    expect(screen.queryByText('طلبات دعم الوفاء بانتظارك')).toBeFalsy();
  });

  it('approving a request calls decideTeamWafaRequest with the right id', async () => {
    teamMock = () => Promise.resolve(EMPTY_TEAM);
    teamWafaMock = () => Promise.resolve({
      wafa_requests: [{ id: 'w1', affiliate_id: 'm1', active_shops: 50, tier_amount_halalas: 20000,
                       status: 'requested', system_recommendation: 'approve', requested_at: 0,
                       system_retention_rate: 0.9, system_refund_rate: 0.02, manager_decision: '',
                       manager_decided_by: '', manager_decided_at: 0, manager_reason: '',
                       decided_by: '', decided_at: 0, reason: '', granted_at: 0 }],
    });
    render(<AffiliateTeam session={SESSION} />);
    await waitFor(() => expect(screen.getByText('طلبات دعم الوفاء بانتظارك')).toBeTruthy());
    fireEvent.click(screen.getByLabelText('موافقة'));
    await waitFor(() => expect(decideCalls).toEqual([{ id: 'w1', decision: 'approve' }]));
  });
});
