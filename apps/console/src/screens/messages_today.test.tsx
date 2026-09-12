/**
 * «هل كل شيء يعمل؟» — the summary card `reminders.today` finally feeds, and «لوحة الحملات»'s own
 * detail panel — one panel, pinned by name to whichever campaign it answers for, below the real
 * table (2026-09-12 rebuild; it used to open under each row individually, back when the list was
 * a plain `<ul>` rather than a real `Table`).
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { DENIED } from '../loading';
import { OperatorI18nProvider } from '../operator-i18n';

const TODAY_OK = {
  can_send: true,
  blocked: '',
  messages: { sent_today: 12, waiting: 3, retrying: 2, retrying_reason: 'رسائل تحاول الخروج ولا تنجح.' },
  ceiling: { known: true, unlimited: false, limit: 250, reached_today: 12, remaining: 238, quality: 'YELLOW' },
};

const TODAY_BLOCKED = {
  can_send: false,
  blocked: 'اسم محلّك غير مضبوط، ولا تخرج أي رسالة باسم فارغ.',
  messages: { sent_today: 0, waiting: 0, retrying: 0, retrying_reason: '' },
  ceiling: { known: false, unlimited: false },
};

const CAMPAIGNS = [
  { id: 'c1', goal: 'win_back', state: 'active', sent: 40 },
  // PAUSED, DELIBERATELY — an active count of exactly 1 (not 2) keeps this mock from colliding
  // with «هل كل شيء يعمل؟»'s own "2 retrying" stat now that the management screen's own KPI
  // tiles (2026-09-12) render a real active-campaign count on the same page.
  { id: 'c2', goal: 'announce', state: 'paused', sent: 5 },
];

let todayResponse: typeof TODAY_OK | typeof TODAY_BLOCKED = TODAY_OK;

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }, body?: { campaign_id?: string }) => {
      if (a.id === 'reminders.today') return todayResponse;
      if (a.id === 'reminders.reasons') return { reasons: [] };
      if (a.id === 'campaigns.list') return { campaigns: CAMPAIGNS };
      if (a.id === 'campaigns.runs') {
        return { runs: [{ at: 0, sent: body?.campaign_id === 'c1' ? 40 : 5, suppressed: 0 }] };
      }
      return {};
    },
  };
});

const { MessagesScreen } = await import('./Messages');

afterEach(cleanup);

const session = {} as never;
const catalog = { services: [], unreachable: [] } as never;

function open() {
  return render(
    <OperatorI18nProvider session={session}>
      <MemoryRouter initialEntries={['/?tab=campaigns']}>
        <MessagesScreen session={session} catalog={catalog} owned={DENIED} />
      </MemoryRouter>
    </OperatorI18nProvider>,
  );
}

describe('«الحملات» — the status card', () => {
  it('shows the three counts and the ceiling when sending is not blocked', async () => {
    todayResponse = TODAY_OK;
    open();
    const sentToday = await screen.findByText('12');
    // SCOPED TO THE CARD ITSELF — «لوحة الحملات»'s own KPI tiles (2026-09-12) render a real
    // campaign count on the same page, and a plain shop with two campaigns makes "2" ambiguous
    // read from the whole document.
    const card = sentToday.closest('section')!;
    expect(within(card).getByText('3')).toBeTruthy();
    expect(within(card).getByText('2')).toBeTruthy();
    expect(within(card).getByText(/رسائل تحاول الخروج/)).toBeTruthy();
    expect(within(card).getByText(/238 متبقٍّ من 250/)).toBeTruthy();
  });

  it('shows the blocked reason instead of any count when sending cannot happen at all', async () => {
    todayResponse = TODAY_BLOCKED;
    open();
    await screen.findByText(/اسم محلّك غير مضبوط/);
    expect(screen.queryByText('238')).toBeNull();
  });
});

describe('«لوحة الحملات» — the detail panel is pinned by name, one at a time', () => {
  it('shows the right campaign\'s totals when its row (card) is pressed', async () => {
    todayResponse = TODAY_OK;
    open();
    // «شاشة الإنشاء» IS THE DEFAULT (2026-09-13, matching the approved mockup) — the management
    // table lives one press away on «شاشة الإدارة», never gated behind a launch button any more.
    fireEvent.click(await screen.findByText('شاشة الإدارة'));
    await screen.findAllByText('رجّع اللي غابوا');
    // THE MOBILE CARD LAYOUT — Table.tsx renders both layouts unconditionally; jsdom has no CSS,
    // so `listitem` always finds the phone-card `<li>`s regardless of viewport. Each card is ONE
    // button (the actions column is hidden on the card layout), so no name filter is needed.
    const rows = screen.getAllByRole('listitem');
    const c1Row = rows.find((r) => within(r).queryByText('رجّع اللي غابوا'))!;
    const c2Row = rows.find((r) => within(r).queryByText('أعلن جديدك'))!;

    fireEvent.click(within(c1Row).getByRole('button'));
    await screen.findByText(/رجّع اللي غابوا — التفاصيل/);
    expect(screen.getByText(/40 وصلت/)).toBeTruthy();

    // PRESSING THE OTHER ROW REPLACES THE PANEL — one campaign's detail at a time, never two.
    fireEvent.click(within(c2Row).getByRole('button'));
    await screen.findByText(/أعلن جديدك — التفاصيل/);
    expect(screen.queryByText(/رجّع اللي غابوا — التفاصيل/)).toBeNull();
  });

  it('closes on a second press of the same row', async () => {
    todayResponse = TODAY_OK;
    open();
    fireEvent.click(await screen.findByText('شاشة الإدارة'));
    await screen.findAllByText('رجّع اللي غابوا');
    const rows = screen.getAllByRole('listitem');
    const c1Row = rows.find((r) => within(r).queryByText('رجّع اللي غابوا'))!;
    fireEvent.click(within(c1Row).getByRole('button'));
    await screen.findByText(/رجّع اللي غابوا — التفاصيل/);
    fireEvent.click(within(c1Row).getByRole('button'));
    expect(screen.queryByText(/رجّع اللي غابوا — التفاصيل/)).toBeNull();
  });
});
