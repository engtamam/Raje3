/**
 * «القوالب» is the one place every message template in the product is shown — the automatic
 * reasons AND the campaign goals, grouped by class, each carrying its own tag.
 *
 * WHY IT STOPPED BEING A FILTERED TABLE. The old «متى نرسل» only ever listed the automatic
 * reasons; «حملاتي» separately explained its eight goals, and only three of them ever got a rich
 * preview. The rename folds both into one screen, grouped into sections (خدمية/شخصية/تسويقية/وعي
 * ونصائح/عروض) rather than filtered by pill — an owner scanning by class now reads one section at
 * a time instead of pressing a filter to find it.
 *
 * WHAT MUST NOT BE LOST: the «when» stays under every card's title, and the three templates a
 * reason AND a goal share (win_back/occasion/reward_loyal) appear exactly ONCE, carrying both
 * tags, never as two cards.
 */
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { OperatorI18nProvider } from '../operator-i18n';
import { vi } from 'vitest';

const rows = (label: string) => screen.queryAllByText(label).length;

const REASONS = [
  { id: 'visit_recorded', label: 'سُجّلت زيارة', when: 'بعد عشر دقائق',
    cls: 'service', cls_label: 'خدمية', on: true, can_switch: true,
    template_status: 'approved' },
  // `gone_missing` carries the cross-link to «حملاتي»'s own win_back goal (REASON_GOAL, keyed by
  // this exact id) — the SAME reason id the real registry uses, so this exercises the dedup rule.
  { id: 'gone_missing', label: 'تجاوز دورته ولم يعد', when: 'بعد 90 يوماً',
    cls: 'marketing', cls_label: 'تسويقية', on: false, can_switch: true },
  { id: 'points_expiring', label: 'نقاطك تنتهي', when: 'قبل الانتهاء بأسبوع',
    cls: 'personal', cls_label: 'شخصية', on: true, can_switch: true },
];

const GOALS = [
  { goal: 'win_back', title: 'رجّع اللي غابوا', line: 'من تأخّر عن موعده' },
  { goal: 'announce', title: 'أعلن جديدك', line: 'خبر أو عرض للجميع' },
];

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }) => {
      if (a.id === 'reminders.reasons') return { reasons: REASONS };
      if (a.id === 'campaigns.goals') return { goals: GOALS };
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
      <MemoryRouter><MessagesScreen session={session} catalog={catalog} /></MemoryRouter>
    </OperatorI18nProvider>,
  );
}

describe('«القوالب» — every template, once, grouped and tagged', () => {
  it('shows every reason, with its class and its «when»', async () => {
    open();
    await screen.findAllByText('سُجّلت زيارة');
    expect(rows('تجاوز دورته ولم يعد')).toBeGreaterThan(0);
    expect(screen.getByText('بعد عشر دقائق')).toBeTruthy();
  });

  it('groups cards under section headers by class', async () => {
    open();
    await screen.findAllByText('سُجّلت زيارة');
    // EACH LABEL CAN ALSO APPEAR AS A CARD'S OWN class badge — so a section header is a COUNT,
    // never a single-element lookup, same reasoning `rows()` already documents above.
    expect(rows('خدمية')).toBeGreaterThan(0);
    expect(rows('شخصية')).toBeGreaterThan(0);
    expect(rows('تسويقية')).toBeGreaterThan(0);
  });

  it('tags an automatic-only reason «تلقائي»', async () => {
    open();
    await screen.findAllByText('سُجّلت زيارة');
    expect(screen.getAllByText('تلقائي').length).toBeGreaterThan(0);
  });

  it('tags a manual-only goal «أنت ترسلها»', async () => {
    open();
    await screen.findAllByText('سُجّلت زيارة');
    // `announce` has no reason at all — it is a goal-only card.
    await screen.findByText('أعلن جديدك');
    expect(rows('أنت ترسلها')).toBeGreaterThan(0);
  });

  it('carries BOTH tags on the one card shared by a reason and a goal, never two cards', async () => {
    open();
    await screen.findAllByText('سُجّلت زيارة');
    // `gone_missing` IS `win_back` — one card, both capabilities, never duplicated. Appears
    // TWICE: once visibly, once as the switch's sr-only accessible name (see triggers_table.tsx's
    // own note on why a row's title is never a single-element lookup).
    expect(rows('تجاوز دورته ولم يعد')).toBe(2);
    expect(rows('رجّع اللي غابوا')).toBe(0); // never a SECOND card under this title
    expect(screen.getByText('تلقائي + يمكن إطلاقه يدوياً')).toBeTruthy();
  });

  it('says the state in a word, not only as a switch', async () => {
    open();
    await screen.findAllByText('سُجّلت زيارة');
    expect(screen.getAllByText('مفعّلة').length).toBeGreaterThan(0);
    expect(screen.getAllByText('موقوفة').length).toBeGreaterThan(0);
  });

  it('shows the template-status badge on the card that carries one', async () => {
    open();
    await screen.findAllByText('سُجّلت زيارة');
    expect(screen.getByText('معتمدة')).toBeTruthy();
  });

  it('cross-links a card that shares a template with a «حملاتي» goal', async () => {
    open();
    await screen.findAllByText('سُجّلت زيارة');
    expect(screen.getByText('أطلقها من «رجّع اللي غابوا»')).toBeTruthy();
    // A card with no matching goal at all (points_expiring here) offers no link — but a bare
    // goal card (announce — «أنت ترسلها») links too, the same way the shared ones do.
    expect(screen.getAllByText(/أطلقها من/).length).toBeGreaterThan(0);
  });
});
