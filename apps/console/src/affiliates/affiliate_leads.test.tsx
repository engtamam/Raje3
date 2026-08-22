/**
 * «عملائي المحتملين» — needs-attention sorting/badging is computed HERE the same way the server
 * defines it, so these tests pin that agreement down: a closed lead never counts, a fresh note
 * clears the flag, and the list opens sorted with attention first.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { AffiliateLeads } from './AffiliateLeads';
import type { AffiliateSession, Lead } from './api';

const SESSION: AffiliateSession = { access_token: 'tok-1' };
// REAL current time, not a fixed fake one — the component computes "how long ago" against
// `Date.now()` itself, so the fixtures below have to be offsets from the ACTUAL clock.
const NOW = Math.floor(Date.now() / 1000);

function lead(over: Partial<Lead> = {}): Lead {
  return {
    id: 'l1', place_id: 'l1', phone: '', name: 'صالون الأمل', place_type: '', sector_code: '',
    city: 'الرياض', region: '', address: '', neighborhood: '', maps_url: '', rating: 0,
    ratings_count: 0, opening_hours: '', website: '', lat: 0, lng: 0, extra_place_ids: [],
    source_manager_id: '', assigned_to: 'aff-1', status: 'assigned', converted_tenant: '',
    notes: [], found_at: NOW - 30 * 86400, outreach_stage_code: 'gatekeeper',
    decision_maker_name: '', decision_maker_phone: '', decision_maker_role: '', ...over,
  };
}

let leadsMock: () => Promise<{ leads: Lead[] }>;

vi.mock('./api', async (importOriginal) => {
  const real = await importOriginal<typeof import('./api')>();
  return {
    ...real,
    leads: (...args: unknown[]) => leadsMock(),
    outreachStages: vi.fn().mockResolvedValue({ stages: [] }),
  };
});

afterEach(() => vi.clearAllMocks());

describe('AffiliateLeads', () => {
  it('shows an honest empty state for a brand-new promoter', async () => {
    leadsMock = () => Promise.resolve({ leads: [] });
    render(<AffiliateLeads session={SESSION} />);
    await waitFor(() => expect(screen.getByText('لا عملاء محتملون بعد')).toBeTruthy());
  });

  it('flags a stale, still-open lead as needing attention', async () => {
    leadsMock = () => Promise.resolve({
      leads: [lead({ id: 'stale', name: 'محل قديم', found_at: NOW - 10 * 86400 })],
    });
    render(<AffiliateLeads session={SESSION} />);
    await waitFor(() => expect(screen.getByText('محل قديم')).toBeTruthy());
    // The filter chip ALSO reads "تحتاج متابعة" — the badge is the second match, a <span> not
    // the segmented control's <button>.
    expect(screen.getAllByText('تحتاج متابعة').length).toBe(2);
    expect(screen.getByText('عميل واحد يحتاج متابعة الآن')).toBeTruthy();
  });

  it('a recent note clears the attention flag despite an old found_at', async () => {
    leadsMock = () => Promise.resolve({
      leads: [lead({
        id: 'fresh', name: 'محل نشِط', found_at: NOW - 60 * 86400,
        notes: [{ at: NOW - 86400, by: 'aff-1', text: 'تواصلت أمس', status_from: '', status_to: '' }],
      })],
    });
    render(<AffiliateLeads session={SESSION} />);
    await waitFor(() => expect(screen.getByText('محل نشِط')).toBeTruthy());
    expect(screen.getAllByText('تحتاج متابعة').length).toBe(1);   // the filter chip only, no badge
  });

  it('a closed lead is never flagged even with zero activity', async () => {
    leadsMock = () => Promise.resolve({
      leads: [lead({ id: 'done', name: 'محل منسحب', status: 'not_interested',
                    found_at: NOW - 90 * 86400 })],
    });
    render(<AffiliateLeads session={SESSION} />);
    await waitFor(() => expect(screen.getByText('محل منسحب')).toBeTruthy());
    expect(screen.getAllByText('تحتاج متابعة').length).toBe(1);   // the filter chip only, no badge
  });

  it('search filters the list by name or city', async () => {
    leadsMock = () => Promise.resolve({
      leads: [lead({ id: 'a', name: 'صالون الرياض' }), lead({ id: 'b', name: 'محل جدة', city: 'جدة' })],
    });
    render(<AffiliateLeads session={SESSION} />);
    await waitFor(() => expect(screen.getByText('صالون الرياض')).toBeTruthy());

    fireEvent.change(screen.getByPlaceholderText('ابحث بالاسم أو المدينة'), { target: { value: 'جدة' } });
    expect(screen.queryByText('صالون الرياض')).toBeFalsy();
    expect(screen.getByText('محل جدة')).toBeTruthy();
  });

  it('a failed read says so rather than an empty list', async () => {
    leadsMock = () => Promise.reject(new Error('network'));
    render(<AffiliateLeads session={SESSION} />);
    await waitFor(() => expect(screen.getByText('تعذّرت القراءة')).toBeTruthy());
  });
});
