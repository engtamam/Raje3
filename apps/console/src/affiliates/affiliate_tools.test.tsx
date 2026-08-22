/**
 * «أدواتي» — the hub itself (role-gated cards), and the template library's own preview/performance
 * badge, since those are the two things worth pinning down: a promoter never sees a manager-only
 * card, and a template with real uses shows its real advance rate rather than a fabricated one.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { AffiliateTools } from './AffiliateTools';
import type {
  AffiliateSession, Me, OutreachStage, MessageTemplate, TemplateStat, StatCitation,
} from './api';

const SESSION: AffiliateSession = { access_token: 'tok-1' };

let meMock: () => Promise<Me>;
let stagesMock: () => Promise<{ stages: OutreachStage[] }>;
let templatesMock: () => Promise<{ templates: MessageTemplate[] }>;
let templateStatsMock: () => Promise<{ stats: TemplateStat[] }>;
let citationsMock: () => Promise<{ citations: StatCitation[] }>;

vi.mock('./api', async (importOriginal) => {
  const real = await importOriginal<typeof import('./api')>();
  return {
    ...real,
    me: (...args: unknown[]) => meMock(),
    outreachStages: (...args: unknown[]) => stagesMock(),
    templates: (...args: unknown[]) => templatesMock(),
    templateStats: (...args: unknown[]) => templateStatsMock(),
    statCitations: (...args: unknown[]) => citationsMock(),
  };
});

const PROMOTER: Me = { id: 'a1', role: 'affiliate_promoter', name: 'سلمان', parent_id: '', status: 'active' };
const MANAGER: Me = { id: 'a2', role: 'affiliate_manager', name: 'عبدالله', parent_id: '', status: 'active' };
const STAGE: OutreachStage = { code: 'gatekeeper', name: 'حارس البوابة', order: 1, active: true };

afterEach(() => vi.clearAllMocks());

describe('AffiliateTools — the hub', () => {
  it('a promoter sees only the two read-relevant cards, never the search tool', async () => {
    meMock = () => Promise.resolve(PROMOTER);
    render(<AffiliateTools session={SESSION} />);
    await waitFor(() => expect(screen.getByText('مكتبة الرسائل')).toBeTruthy());
    expect(screen.getByText('مكتبة الأدلة')).toBeTruthy();
    expect(screen.queryByText('أداة البحث عن عملاء محتملين')).toBeFalsy();
  });

  it('a manager sees all three cards', async () => {
    meMock = () => Promise.resolve(MANAGER);
    render(<AffiliateTools session={SESSION} />);
    await waitFor(() => expect(screen.getByText('أداة البحث عن عملاء محتملين')).toBeTruthy());
  });
});

describe('AffiliateTools — the template library', () => {
  it('shows the template body as a preview, and its real advance rate when it has uses', async () => {
    meMock = () => Promise.resolve(PROMOTER);
    stagesMock = () => Promise.resolve({ stages: [STAGE] });
    templatesMock = () => Promise.resolve({
      templates: [{ id: 't1', stage_code: 'gatekeeper', kind: '', title: 'العطاء أولاً',
                   body: 'مرحباً بك', media_url: '', objection_type: '', active: true }],
    });
    templateStatsMock = () => Promise.resolve({
      stats: [{ template_id: 't1', stage_code: 'gatekeeper', kind: '', title: 'العطاء أولاً',
               uses: 10, pending: 2, advanced: 5, no_response: 2, rejected: 1, advance_rate: 0.5 }],
    });

    render(<AffiliateTools session={SESSION} />);
    await waitFor(() => expect(screen.getByText('مكتبة الرسائل')).toBeTruthy());
    fireEvent.click(screen.getByText('مكتبة الرسائل'));

    await waitFor(() => expect(screen.getByText('العطاء أولاً')).toBeTruthy());
    expect(screen.getByText('مرحباً بك')).toBeTruthy();
    expect(screen.getByText('50٪ تقدّم — 10 استخدام')).toBeTruthy();
  });

  it('a promoter sees no edit/deactivate/new-template controls', async () => {
    meMock = () => Promise.resolve(PROMOTER);
    stagesMock = () => Promise.resolve({ stages: [STAGE] });
    templatesMock = () => Promise.resolve({
      templates: [{ id: 't1', stage_code: 'gatekeeper', kind: '', title: 'قالب',
                   body: 'نص', media_url: '', objection_type: '', active: true }],
    });
    templateStatsMock = () => Promise.resolve({ stats: [] });

    render(<AffiliateTools session={SESSION} />);
    await waitFor(() => expect(screen.getByText('مكتبة الرسائل')).toBeTruthy());
    fireEvent.click(screen.getByText('مكتبة الرسائل'));

    await waitFor(() => expect(screen.getByText('قالب')).toBeTruthy());
    expect(screen.queryByText('قالب جديد لهذه المرحلة')).toBeFalsy();
    expect(screen.queryByLabelText('تعديل')).toBeFalsy();
  });

  it('a manager sees the new-template action', async () => {
    meMock = () => Promise.resolve(MANAGER);
    stagesMock = () => Promise.resolve({ stages: [STAGE] });
    templatesMock = () => Promise.resolve({ templates: [] });
    templateStatsMock = () => Promise.resolve({ stats: [] });

    render(<AffiliateTools session={SESSION} />);
    await waitFor(() => expect(screen.getByText('مكتبة الرسائل')).toBeTruthy());
    fireEvent.click(screen.getByText('مكتبة الرسائل'));

    await waitFor(() => expect(screen.getByText('قالب جديد لهذه المرحلة')).toBeTruthy());
  });
});

describe('AffiliateTools — the citation library', () => {
  it('renders a citation with its source label as a link', async () => {
    meMock = () => Promise.resolve(PROMOTER);
    citationsMock = () => Promise.resolve({
      citations: [{ id: 'c1', title: 'الانقطاع الصامت', body: 'من كل ١٠٠ عميل...',
                   source_label: 'Bain & Company', source_url: 'https://example.com', stage_code: '', active: true }],
    });

    render(<AffiliateTools session={SESSION} />);
    await waitFor(() => expect(screen.getByText('مكتبة الأدلة')).toBeTruthy());
    fireEvent.click(screen.getByText('مكتبة الأدلة'));

    await waitFor(() => expect(screen.getByText('الانقطاع الصامت')).toBeTruthy());
    expect(screen.getByText(/Bain & Company/)).toBeTruthy();
  });
});
