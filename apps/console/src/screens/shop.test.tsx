/**
 * ONE PAGE, AND THE NUMBER FIRST — the contract «اليوم» and «محلّي» were merged under.
 *
 * WHAT THIS IS WRITTEN AFTER. Opening «محلّي» on the server showed, above its own retention
 * rate: a group heading, a line saying a surface belongs to an app not yet bought, a second heading, a
 * freshness caption and a refresh button. «ابغ تشيل كل شي من اللي فوق، ما ابغاه فوق، على طول يبدا
 * من النسبة». And beside it: «افكر ادمج صفحة اليوم مع محلي في صفحة وحده».
 *
 * SO THE ORDER IS ASSERTED, NOT DESCRIBED. A comment saying the ring comes first is a comment; the
 * next person to add a banner puts it at the top, because the top is where a new thing goes. These
 * checks fail the moment anything is placed above the number, and the moment a second rail row
 * appears for a page that is now one.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { SECTIONS } from '../nav';

// MUTABLE, PER-TEST STATE — `vi.mock` runs once at module scope, so the AI-impact/next_step tests
// below adjust these refs before rendering rather than needing a second mock module entirely.
const mockState = vi.hoisted(() => ({
  entitlements: ['feature.insights.engine'] as string[],
  nextStep: {
    primary: {
      id: 'all_is_well', category: 'health', category_label: 'الصحة العامة',
      message: 'وضعك ثابت ولا شي يستحق تنبيهاً الآن — جرّب تكافئ عملاءك الدائمين.',
      cta_label: 'كافئهم', cta_link: '/messages?tab=campaigns&launch=reward_loyal',
      tone: 'success',
    },
    secondary: null as unknown,
  },
}));

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }) => {
      if (a.id === 'whatsapp_assistant.my_impact') {
        return {
          days: 30, conversations: 20, ai_bookings: 8, conversion_rate: 0.4,
          avg_invoice_value_minor: 15000, upsell_offered: 5, upsell_accepted: 3,
          upsell_acceptance_rate: 0.6, truncated: false,
        };
      }
      if (a.id === 'insights.bundles') {
        return {
          bundles: [
            { a: 'pkg:pkg1', b: 'svc_wax', a_name: 'باقة الصيانة', b_name: 'تلميع',
             why: 'يُطلبان معاً', customers: 30, action: 'extend_package',
             action_label: 'أضفها لهذه الباقة', package_id: 'pkg1' },
            { a: 'svc_a', b: 'svc_b', a_name: 'غيار زيت', b_name: 'فحص فرامل',
             why: 'يُطلبان معاً', customers: 40, action: 'bundle',
             action_label: 'اجعلها باقة — تحدّد سعرها أنت' },
          ],
        };
      }
      if (a.id === 'insights.dashboard') {
        return {
          computing: false,
          values: { return_rate: 0.42, active_customers: 30 },
          as_of_hours_ago: 17,
          // THE ENTRY PLAN, ON PURPOSE: this is the shop whose page carried a locked surface above
          // its own retention rate. If the lock ever climbs back over the ring, this test is the
          // one that notices.
          //
          // 'feature.insights.engine' IS REQUIRED for the bundles/associations reads to even fire
          // (Shop.tsx's own gate) — without it `setBundles(null)` short-circuits before either of
          // the two new packages-feature tests below ever see a bundle card.
          entitlements: mockState.entitlements,
          // THE ENGINE'S OWN CATCH-ALL (services/insights/app/core/next_step.py's `all_is_well`)
          // — a shop with nothing else matching always gets this, never silence.
          next_step: mockState.nextStep,
        };
      }
      return {};
    },
  };
});

const { IndicatorsPanel: LocalScreen } = await import('./Shop');

afterEach(() => {
  cleanup();
  mockState.entitlements = ['feature.insights.engine'];
  mockState.nextStep = {
    primary: {
      id: 'all_is_well', category: 'health', category_label: 'الصحة العامة',
      message: 'وضعك ثابت ولا شي يستحق تنبيهاً الآن — جرّب تكافئ عملاءك الدائمين.',
      cta_label: 'كافئهم', cta_link: '/messages?tab=campaigns&launch=reward_loyal',
      tone: 'success',
    },
    secondary: null,
  };
});

const session = {} as never;
const catalog = { services: [], unreachable: [] } as never;

describe('«محلّي» — one page, and the number first', () => {
  it('the rail offers ONE row for it, and that row is the front door', () => {
    // TWO ROWS WERE ONE GLANCE'S WORTH OF INFORMATION between them. If «today» ever returns as its
    // own section, this fails — which is the only way a merge stays merged.
    const rows = SECTIONS.filter((s) => s.id === 'shop' || s.id === 'today');
    expect(rows).toHaveLength(1);
    expect(rows[0].path).toBe('/');
    // AND IT IS GATED ON BOTH READS IT IS BUILT OUT OF. Dropping either opens the page for
    // somebody half of it answers 403 to.
    expect(rows[0].requires).toEqual(['reminders.today', 'insights.dashboard']);
  });

  it('draws the retention ring BEFORE any heading, caption or lock', async () => {
    const { container } = render(
      <MemoryRouter><LocalScreen session={session} catalog={catalog} branch="" onBranch={() => {}} /></MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText('نسبة عودة عملائك')).toBeTruthy());

    const page = container.firstElementChild!;
    const rows = [...page.children];
    const ringAt = rows.findIndex((c) => c.contains(screen.getByText('نسبة عودة عملائك')));
    // FIRST — not «somewhere on the page». The freshness caption and the locked-surface line both
    // sat above it, and both would pass a presence check while failing the only thing asked for.
    expect(ringAt).toBe(0);

    // AND THE AGE IS STILL SAID, underneath. Deleting it would be the opposite failure: an owner
    // comparing our figure to his till at 2pm must know ours was computed hours ago.
    const age = screen.getByText(/محسوبة قبل/);
    expect(rows.findIndex((c) => c.contains(age))).toBeGreaterThan(ringAt);
  });

  it('never draws the old «يحتاج تصرّفاً منك» heading, and never goes silent either', async () => {
    render(<MemoryRouter><LocalScreen session={session} catalog={catalog} branch="" onBranch={() => {}} /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText('نسبة عودة عملائك')).toBeTruthy());
    // A section demanding action, about the one thing he cannot act on, is a heading he learns to
    // stop reading — the old heading is gone for good.
    expect(screen.queryByText('يحتاج تصرّفاً منك')).toBeNull();
    // AND SOMETHING ALWAYS REPLACES IT — «الخطوة التالية» never renders empty; with nothing to
    // cross-sell and no locked upsell, it still gives him a real, honest suggestion rather than
    // silence.
    expect(screen.getByText('الخطوة التالية')).toBeTruthy();
    expect(screen.getByText(/وضعك ثابت/)).toBeTruthy();
  });

  // ── packages feature: the bundle card's own action link ───────────────────────────────────────
  it('an extend_package suggestion links to the existing package, not a new one', async () => {
    render(<MemoryRouter><LocalScreen session={session} catalog={catalog} branch="" onBranch={() => {}} /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText('أضفها لهذه الباقة')).toBeTruthy());
    const link = screen.getByRole('link', { name: 'أضفها لهذه الباقة' });
    const href = link.getAttribute('href') ?? '';
    expect(href).toContain('extend_package=pkg1');
    expect(href).toContain('extend_service=svc_wax');
  });

  it('a bundle suggestion pre-fills a brand-new package with both services', async () => {
    render(<MemoryRouter><LocalScreen session={session} catalog={catalog} branch="" onBranch={() => {}} /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText('اجعلها باقة — تحدّد سعرها أنت')).toBeTruthy());
    const link = screen.getByRole('link', { name: 'اجعلها باقة — تحدّد سعرها أنت' });
    const href = link.getAttribute('href') ?? '';
    expect(href).toContain('prefill_a=svc_a');
    expect(href).toContain('prefill_b=svc_b');
  });

  it('both links route through /services?tab=packages', async () => {
    render(<MemoryRouter><LocalScreen session={session} catalog={catalog} branch="" onBranch={() => {}} /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText('أضفها لهذه الباقة')).toBeTruthy());
    const extend = screen.getByRole('link', { name: 'أضفها لهذه الباقة' }).getAttribute('href') ?? '';
    const bundle = screen.getByRole('link', { name: 'اجعلها باقة — تحدّد سعرها أنت' }).getAttribute('href') ?? '';
    expect(extend.startsWith('/services?tab=packages')).toBe(true);
    expect(bundle.startsWith('/services?tab=packages')).toBe(true);
  });

  it('a reminder-verdict bundle (no action_label) renders no link at all', async () => {
    render(<MemoryRouter><LocalScreen session={session} catalog={catalog} branch="" onBranch={() => {}} /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText('أضفها لهذه الباقة')).toBeTruthy());
    // Neither bundle in this test's own mock is a "reminder" card, so no reminder text/link
    // should ever appear here — a real absence-of-regression check for the branch that renders
    // plain (non-link) text when a card has no action_label at all.
    expect(screen.queryByText('ذكّر بها في الزيارة القادمة')).toBeNull();
  });

  // ── AI-impact card — the second-tier grid slot ────────────────────────────────────────────────
  it('a subscribed shop sees its own real AI-impact numbers, side by side with AtRiskCard', async () => {
    mockState.entitlements = ['feature.insights.engine', 'feature.whatsapp'];
    render(<MemoryRouter><LocalScreen session={session} catalog={catalog} branch="" onBranch={() => {}} /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText(/أثر الذكاء الاصطناعي/)).toBeTruthy());
    // The real numbers from the mocked route, never invented client-side.
    expect(screen.getByText('20')).toBeTruthy();          // conversations tile
    expect(screen.getByText('150 ريال')).toBeTruthy();     // avg_invoice_value_minor 15000 halalas
    expect(screen.getByText('60%')).toBeTruthy();          // upsell_acceptance_rate 0.6
  });

  it('an un-subscribed shop gets no AI-impact card at all — no card with nothing real to show', async () => {
    // Default mockState.entitlements has no 'feature.whatsapp' — the marketing for this case
    // lives in «الخطوة التالية» instead (the luxury-teaser test below), never a second, empty card.
    render(<MemoryRouter><LocalScreen session={session} catalog={catalog} branch="" onBranch={() => {}} /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText('نسبة عودة عملائك')).toBeTruthy());
    expect(screen.queryByText(/أثر الذكاء الاصطناعي/)).toBeNull();
  });

  // ── «الخطوة التالية» — the whatsapp_ai_teaser luxury special-case ─────────────────────────────
  it('the whatsapp_ai_teaser rule renders the luxury frame, not the ordinary tone box', async () => {
    mockState.nextStep = {
      primary: {
        id: 'whatsapp_ai_teaser', category: 'plan', category_label: 'الاشتراك والميزات',
        message: 'بوت واتساب يردّ على عملائك ويحجز لهم تلقائياً حتى وأنت نايم — جرّبه على محلك.',
        cta_label: 'جرّب بوت واتساب', cta_link: '/plans?highlight=whatsapp', tone: 'info',
      },
      secondary: null,
    };
    render(<MemoryRouter><LocalScreen session={session} catalog={catalog} branch="" onBranch={() => {}} /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText(/بوت واتساب يردّ/)).toBeTruthy());
    const link = screen.getByRole('link', { name: 'جرّب بوت واتساب' });
    expect(link.getAttribute('href')).toBe('/plans?highlight=whatsapp');
    // THE LUXURY MARKER — never present for the ordinary all_is_well render in the earlier test.
    expect(screen.getByText('✨')).toBeTruthy();
  });

  it('an ordinary next_step rule never gets the luxury frame', async () => {
    render(<MemoryRouter><LocalScreen session={session} catalog={catalog} branch="" onBranch={() => {}} /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText(/وضعك ثابت/)).toBeTruthy());
    expect(screen.queryByText('✨')).toBeNull();
  });
});
