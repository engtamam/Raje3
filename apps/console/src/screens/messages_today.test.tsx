/**
 * «هل كل شيء يعمل؟» — the summary card `reminders.today` finally feeds, and the campaigns tab's
 * «ماذا حدث» panel now opening under its OWN row rather than under the whole list.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { DENIED } from '../loading';

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
  { id: 'c2', goal: 'announce', state: 'active', sent: 5 },
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
    <MemoryRouter initialEntries={['/?tab=campaigns']}>
      <MessagesScreen session={session} catalog={catalog} owned={DENIED} />
    </MemoryRouter>,
  );
}

describe('«رسائلي» — the status card', () => {
  it('shows the three counts and the ceiling when sending is not blocked', async () => {
    todayResponse = TODAY_OK;
    open();
    await screen.findByText('12');
    expect(screen.getByText('3')).toBeTruthy();
    expect(screen.getByText('2')).toBeTruthy();
    expect(screen.getByText(/رسائل تحاول الخروج/)).toBeTruthy();
    expect(screen.getByText(/238 متبقٍّ من 250/)).toBeTruthy();
  });

  it('shows the blocked reason instead of any count when sending cannot happen at all', async () => {
    todayResponse = TODAY_BLOCKED;
    open();
    await screen.findByText(/اسم محلّك غير مضبوط/);
    expect(screen.queryByText('238')).toBeNull();
  });
});

describe('«حملاتي» — «ماذا حدث» opens under its own row', () => {
  it('opens the right campaign\'s runs, not the other one\'s', async () => {
    todayResponse = TODAY_OK;
    open();
    await screen.findAllByText('رجّع اللي غابوا');
    const rows = screen.getAllByRole('listitem');
    const c1Row = rows.find((r) => within(r).queryByText('رجّع اللي غابوا'));
    const c2Row = rows.find((r) => within(r).queryByText('أعلن جديدك'));
    expect(c1Row).toBeTruthy();
    expect(c2Row).toBeTruthy();

    fireEvent.click(within(c1Row!).getByRole('button', { name: 'ماذا حدث' }));
    await within(c1Row!).findByText(/40 وصلت/);
    // THE OTHER ROW STAYS CLOSED — the whole point of pinning the panel to a row.
    expect(within(c2Row!).queryByText(/5 وصلت/)).toBeNull();
  });

  it('closes on a second press of the same row\'s button', async () => {
    todayResponse = TODAY_OK;
    open();
    await screen.findAllByText('رجّع اللي غابوا');
    const rows = screen.getAllByRole('listitem');
    const c1Row = rows.find((r) => within(r).queryByText('رجّع اللي غابوا'))!;
    const btn = within(c1Row).getByRole('button', { name: 'ماذا حدث' });
    fireEvent.click(btn);
    await within(c1Row).findByText(/40 وصلت/);
    fireEvent.click(within(c1Row).getByRole('button', { name: 'ماذا حدث' }));
    expect(within(c1Row).queryByText(/40 وصلت/)).toBeNull();
  });
});
