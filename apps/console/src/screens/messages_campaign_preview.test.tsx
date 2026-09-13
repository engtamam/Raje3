/**
 * «لوحة الحملات»'s own detail panel now shows the ACTUAL message an already-launched campaign
 * sends, re-rendered from its own stored settings — not only the numbers it always showed.
 * Closes the gap this session found: an owner opening a running campaign here saw a trend chart
 * and a send count, never the words behind them.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { DENIED, type Loading } from '../loading';
import type { Owned } from '../apps';
import { OperatorI18nProvider } from '../operator-i18n';

const CAMPAIGNS = [
  {
    id: 'c1', goal: 'win_back', state: 'active', sent: 40,
    owner_text: '', offer_value: '20%', scope_service_ids: ['svc_1'],
    scope_service_names: ['قص شعر'],
  },
  {
    id: 'c2', goal: 'reward_loyal', state: 'active', sent: 5,
    scope_service_ids: ['svc_1', 'svc_2'], scope_service_names: ['قص شعر', 'صبغة'],
  },
  // A DIFFERENT GOAL, NOT ANOTHER reward_loyal — its title ("أعلن جديدك") must be its own, since
  // two rows sharing one title would make `openRow`'s row lookup ambiguous.
  {
    id: 'c3', goal: 'announce', state: 'active', sent: 3,
    scope_service_ids: ['svc_1'], scope_service_names: ['قص شعر'],
  },
];

const previewCalls: unknown[] = [];

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }, body?: { campaign_id?: string }) => {
      if (a.id === 'reminders.today') {
        return {
          can_send: true, blocked: '',
          messages: { sent_today: 0, waiting: 0, retrying: 0, retrying_reason: '' },
          ceiling: { known: false, unlimited: false },
        };
      }
      if (a.id === 'reminders.reasons') return { reasons: [] };
      if (a.id === 'campaigns.list') return { campaigns: CAMPAIGNS };
      if (a.id === 'campaigns.runs') return { runs: [] };
      if (a.id === 'campaigns.preview') {
        previewCalls.push(body);
        return { message: 'وحشتنا! لك خصم 20% على قص شعر' };
      }
      return {};
    },
  };
});

const { MessagesScreen } = await import('./Messages');

afterEach(() => { cleanup(); previewCalls.length = 0; });

const session = {} as never;
const catalog = { services: [], unreachable: [] } as never;
const BOOKINGS_AND_ASSISTANT: Loading<Owned> = {
  checked: true, message: '', apps: [],
  keys: ['feature.campaigns', 'feature.bookings', 'feature.whatsapp'],
} as never;

function open(owned: Loading<Owned> = DENIED) {
  return render(
    <OperatorI18nProvider session={session}>
      <MemoryRouter initialEntries={['/?tab=campaigns']}>
        <MessagesScreen session={session} catalog={catalog} owned={owned} />
      </MemoryRouter>
    </OperatorI18nProvider>,
  );
}

async function openRow(name: string) {
  fireEvent.click(await screen.findByText('شاشة الإدارة'));
  await screen.findAllByText(name);
  const rows = screen.getAllByRole('listitem');
  const row = rows.find((r) => within(r).queryByText(name))!;
  fireEvent.click(within(row).getByRole('button'));
}

describe('opening a campaign asks for its own real message', () => {
  it('previews with THIS campaign\'s own stored fields, not invented ones', async () => {
    open();
    await openRow('رجّع اللي غابوا');
    await screen.findByText(/وحشتنا! لك خصم/);
    expect(previewCalls.length).toBe(1);
    const body = previewCalls[0] as {
      goal: string; offer_value: string; service_ids: string[]; service_names: string[];
    };
    expect(body.goal).toBe('win_back');
    expect(body.offer_value).toBe('20%');
  });

  it('shows a loading skeleton before the preview answers, never a blank gap', async () => {
    open();
    await openRow('رجّع اللي غابوا');
    // The mocked call resolves asynchronously — right after the click, the message text is not
    // there yet, and neither is a stale one from a previous row.
    expect(screen.queryByText(/وحشتنا! لك خصم/)).toBeNull();
    await screen.findByText(/وحشتنا! لك خصم/);
  });

  it('switching to a different campaign replaces the previewed message', async () => {
    open();
    await openRow('رجّع اللي غابوا');
    await screen.findByText(/وحشتنا! لك خصم/);
    previewCalls.length = 0;
    await openRow('كافئ المخلصين');
    await screen.findByText(/وحشتنا! لك خصم/);
    expect(previewCalls.length).toBe(1);
  });

  it('closing the panel drops the preview so a re-open never flashes stale text', async () => {
    open();
    await openRow('رجّع اللي غابوا');
    await screen.findByText(/وحشتنا! لك خصم/);
    fireEvent.click(await screen.findByLabelText('إغلاق التفاصيل'));
    expect(screen.queryByText(/وحشتنا! لك خصم/)).toBeNull();
  });
});

describe('the single-item quick-reply button on an already-launched campaign', () => {
  it('shows it for a non-booking goal with exactly one item scoped and both entitlements owned', async () => {
    open(BOOKINGS_AND_ASSISTANT);
    await openRow('أعلن جديدك');
    await screen.findByText(/وحشتنا! لك خصم/);
    expect(screen.getByText('احجز الآن')).toBeTruthy();
  });

  it('never shows it with more than one item scoped', async () => {
    open(BOOKINGS_AND_ASSISTANT);
    await openRow('كافئ المخلصين');
    await screen.findByText(/وحشتنا! لك خصم/);
    expect(screen.queryByText('احجز الآن')).toBeNull();
  });

  it('never shows it without the AI assistant app, bookings alone is not enough', async () => {
    open({ checked: true, message: '', apps: [], keys: ['feature.campaigns', 'feature.bookings'] } as never);
    await openRow('أعلن جديدك');
    await screen.findByText(/وحشتنا! لك خصم/);
    expect(screen.queryByText('احجز الآن')).toBeNull();
  });

  it('shows the booking Flow button instead, never both, for a booking goal (DENIED reads as "show the surface")', async () => {
    // `owns()`'s own contract: a DENIED entitlement read answers `true` ("not his to ask, show
    // him the surface"), so both entitlements read as owned here — win_back is FLOW_ELIGIBLE,
    // and the Flow always wins over the single-item button when bookings reads as owned.
    open(DENIED);
    await openRow('رجّع اللي غابوا');
    await screen.findByText(/وحشتنا! لك خصم/);
    expect(screen.getByText('احجز موعدك الآن')).toBeTruthy();
    expect(screen.queryByText('احجز الآن')).toBeNull();
  });
});
