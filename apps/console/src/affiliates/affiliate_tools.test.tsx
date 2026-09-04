/**
 * «أدواتي» — the hub itself (role-gated cards), and the template library's own preview/performance
 * badge, since those are the two things worth pinning down: a promoter never sees a manager-only
 * card, and a template with real uses shows its real advance rate rather than a fabricated one.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { AffiliateTools } from './AffiliateTools';
import type {
  AffiliateSession, Me, OutreachStage, MessageTemplate, TemplateStat, StatCitation, SectorStat,
  ReferredShop, ShopTicket,
} from './api';

const SESSION: AffiliateSession = { access_token: 'tok-1' };

let meMock: () => Promise<Me>;
let stagesMock: () => Promise<{ stages: OutreachStage[] }>;
let templatesMock: () => Promise<{ templates: MessageTemplate[] }>;
let templateStatsMock: () => Promise<{ stats: TemplateStat[] }>;
let citationsMock: () => Promise<{ citations: StatCitation[] }>;
let sectorStatsMock: () => Promise<{ stats: SectorStat[] }>;
let referredShopsMock: () => Promise<{ shops: ReferredShop[] }>;
let shopTicketsMock: () => Promise<{ tickets: ShopTicket[] }>;

vi.mock('./api', async (importOriginal) => {
  const real = await importOriginal<typeof import('./api')>();
  return {
    ...real,
    me: (...args: unknown[]) => meMock(),
    outreachStages: (...args: unknown[]) => stagesMock(),
    templates: (...args: unknown[]) => templatesMock(),
    templateStats: (...args: unknown[]) => templateStatsMock(),
    statCitations: (...args: unknown[]) => citationsMock(),
    sectorStats: (...args: unknown[]) => sectorStatsMock(),
    referredShops: (...args: unknown[]) => referredShopsMock(),
    shopTickets: (...args: unknown[]) => shopTicketsMock(),
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
      citations: [{ id: 'c1', title: 'الانقطاع الصامت', body: 'من كل 100 عميل...',
                   source_label: 'Bain & Company', source_url: 'https://example.com', stage_code: '', active: true }],
    });

    render(<AffiliateTools session={SESSION} />);
    await waitFor(() => expect(screen.getByText('مكتبة الأدلة')).toBeTruthy());
    fireEvent.click(screen.getByText('مكتبة الأدلة'));

    await waitFor(() => expect(screen.getByText('الانقطاع الصامت')).toBeTruthy());
    expect(screen.getByText(/Bain & Company/)).toBeTruthy();
  });
});

describe('AffiliateTools — sector stats (manager only)', () => {
  it('a promoter never sees the sector-stats card', async () => {
    meMock = () => Promise.resolve(PROMOTER);
    render(<AffiliateTools session={SESSION} />);
    await waitFor(() => expect(screen.getByText('مكتبة الرسائل')).toBeTruthy());
    expect(screen.queryByText('إحصائيات القطاعات')).toBeFalsy();
  });

  it('a manager opens it and sees real counts, sorted by lead_count', async () => {
    meMock = () => Promise.resolve(MANAGER);
    sectorStatsMock = () => Promise.resolve({
      stats: [
        { sector_code: 'صالونات', city: 'جدة', lead_count: 3, by_status: {}, registered_count: 0 },
        { sector_code: 'صالونات', city: 'الرياض', lead_count: 12, by_status: {}, registered_count: 2 },
      ],
    });
    render(<AffiliateTools session={SESSION} />);
    await waitFor(() => expect(screen.getByText('إحصائيات القطاعات')).toBeTruthy());
    fireEvent.click(screen.getByText('إحصائيات القطاعات'));
    await waitFor(() => expect(screen.getByText('الرياض')).toBeTruthy());
    expect(screen.getByText('سجَّل 2 من 12')).toBeTruthy();
  });
});

describe('AffiliateTools — shop tickets (§13)', () => {
  it('is visible to both roles, and lists referred shops', async () => {
    meMock = () => Promise.resolve(PROMOTER);
    referredShopsMock = () => Promise.resolve({
      shops: [{ tenant: 't1', shop_name: 'صالون النخبة', status: 'referred', stamped_at: 0 }],
    });
    render(<AffiliateTools session={SESSION} />);
    await waitFor(() => expect(screen.getByText('تذاكر المحلات')).toBeTruthy());
    fireEvent.click(screen.getByText('تذاكر المحلات'));
    await waitFor(() => expect(screen.getByText('صالون النخبة')).toBeTruthy());
  });

  it('opening a shop lists its tickets', async () => {
    meMock = () => Promise.resolve(PROMOTER);
    referredShopsMock = () => Promise.resolve({
      shops: [{ tenant: 't1', shop_name: 'صالون النخبة', status: 'referred', stamped_at: 0 }],
    });
    shopTicketsMock = () => Promise.resolve({
      tickets: [{ id: 'tk1', subject: 'مشكلة بالحجز', status: 'open' }],
    });
    render(<AffiliateTools session={SESSION} />);
    await waitFor(() => expect(screen.getByText('تذاكر المحلات')).toBeTruthy());
    fireEvent.click(screen.getByText('تذاكر المحلات'));
    await waitFor(() => expect(screen.getByText('صالون النخبة')).toBeTruthy());
    fireEvent.click(screen.getByText('صالون النخبة'));
    await waitFor(() => expect(screen.getByText('مشكلة بالحجز')).toBeTruthy());
  });
});

describe('AffiliateTools — deep-linked ticket (Home\'s own carousel, 2026-08-23)', () => {
  it('jumps straight into the ticket thread, skipping the shop picker and the ticket list', async () => {
    meMock = () => Promise.resolve(PROMOTER);
    render(<AffiliateTools session={SESSION}
                          deepLinkTicket={{ id: 'tk-dl', tenant: 't-dl', shop_name: 'مغسلة الأمل',
                                            subject: 'الجهاز متوقف', status: 'open' }} />);
    await waitFor(() => expect(screen.getByText('الجهاز متوقف')).toBeTruthy());
    expect(screen.getByPlaceholderText('اكتب ردّك')).toBeTruthy();
    // never rendered the menu or the shop picker on the way there
    expect(screen.queryByText('تذاكر المحلات')).toBeFalsy();
  });

  it('going back calls onConsumeDeepLinkTicket, not a local view change', async () => {
    meMock = () => Promise.resolve(PROMOTER);
    const onConsume = vi.fn();
    render(<AffiliateTools session={SESSION}
                          deepLinkTicket={{ id: 'tk-dl2', tenant: 't-dl2', shop_name: 'محل',
                                            subject: 'س', status: 'open' }}
                          onConsumeDeepLinkTicket={onConsume} />);
    await waitFor(() => expect(screen.getByText('س')).toBeTruthy());
    fireEvent.click(screen.getByLabelText('رجوع'));
    expect(onConsume).toHaveBeenCalledTimes(1);
  });
});
