/**
 * ONE PAGE, AND THE NUMBER FIRST — the contract «اليوم» and «محلّي» were merged under.
 *
 * WHAT THIS IS WRITTEN AFTER. Tamam opened «محلّي» on the server and read, above his own retention
 * rate: a group heading, a line saying a surface belongs to a higher plan, a second heading, a
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
import { SECTIONS } from '../nav';

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }) => {
      if (a.id === 'insights.dashboard') {
        return {
          computing: false,
          values: { return_rate: 0.42, active_customers: 30 },
          as_of_hours_ago: 17,
          // THE ENTRY PLAN, ON PURPOSE: this is the shop whose page carried a locked surface above
          // its own retention rate. If the lock ever climbs back over the ring, this test is the
          // one that notices.
          entitlements: [],
        };
      }
      return {};
    },
  };
});

const { IndicatorsPanel: LocalScreen } = await import('./Shop');

afterEach(cleanup);

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
      <LocalScreen session={session} catalog={catalog} branch="" onBranch={() => {}} />,
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

  it('draws no «يحتاج تصرّفاً منك» heading when there is nothing under it', async () => {
    render(<LocalScreen session={session} catalog={catalog} branch="" onBranch={() => {}} />);
    await waitFor(() => expect(screen.getByText('نسبة عودة عملائك')).toBeTruthy());
    // A section demanding action, about the one thing he cannot act on, is a heading he learns to
    // stop reading.
    expect(screen.queryByText('يحتاج تصرّفاً منك')).toBeNull();
  });
});
