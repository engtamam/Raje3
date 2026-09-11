/**
 * The strip says what the service learned: a message that keeps failing is not one that is waiting.
 *
 * THE HALF-FINISHED FIX THIS COMPLETES. The service began telling the two apart — a reminder booked
 * for next Tuesday, and a message that has thrown eleven times and is retried hourly until it is
 * given up on — and reported the second under its own key with its own sentence. The strip rendered
 * `sent_today` and `waiting`, as it always had, and knew nothing about the new one.
 *
 * So the work stopped one layer short of the person it was for: the shop whose every message was
 * failing still read two calm numbers. This file is what makes the last step hold.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { createElement } from 'react';
import { OperatorI18nProvider } from '../operator-i18n';

let today: Record<string, unknown> = {};

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }) => {
      if (a.id === 'reminders.today') return today;
      return {};
    },
  };
});

const { TodayPulse: TodayStrip } = await import('./Shop');

afterEach(cleanup);

const session = {} as never;
const catalog = { services: [], unreachable: [] } as never;

const CEILING = { known: true, unlimited: false, limit: 100, reached_today: 3, remaining: 97 };

function open(messages: Record<string, unknown>) {
  today = { can_send: true, blocked: '', messages, ceiling: CEILING };
  return render(createElement(OperatorI18nProvider, {
    session, children: createElement(TodayStrip, { session, catalog }),
  }));
}

describe('«هل كل شيء يعمل؟» — what is stuck is said out loud', () => {
  it('says nothing about retries when nothing is retrying', async () => {
    open({ sent_today: 4, waiting: 3, retrying: 0, retrying_reason: '' });
    await screen.findByText('بانتظار الإرسال');
    // A WARNING THAT IS ALWAYS ON SCREEN IS FURNITURE, and the next real one is read as furniture
    // too. Zero is a real answer here and the honest thing to do with it is nothing.
    expect(screen.queryByText(/تحاول الخروج/)).toBeNull();
  });

  it('names the count and carries the service sentence when messages are failing', async () => {
    open({
      sent_today: 0, waiting: 1, retrying: 12,
      retrying_reason: 'رسائل تحاول الخروج ولا تنجح — سنعيد المحاولة.',
    });
    await waitFor(() => expect(screen.getByText(/12 رسالة تحاول الخروج/)).toBeTruthy());
    // THE SERVICE'S OWN WORDS, WHOLE. Re-writing them here would give the product two vocabularies
    // for one condition, and the owner would be told something subtly different from what happened.
    expect(screen.getByText('رسائل تحاول الخروج ولا تنجح — سنعيد المحاولة.')).toBeTruthy();
  });

  it('keeps «بانتظار الإرسال» meaning the calm ones only', async () => {
    // THE WHOLE POINT OF THE SPLIT: this tile reads 1, not 13. A shop with twelve failing messages
    // must not be able to read this screen as a shop with a queue.
    const { container } = open({ sent_today: 0, waiting: 1, retrying: 12, retrying_reason: 'x' });
    await screen.findByText('بانتظار الإرسال');
    // 13 IS THE OLD ANSWER — the two counts added together. It must appear nowhere on the strip.
    expect(container.textContent).not.toContain('13');
    expect(screen.getAllByText('1').length).toBeGreaterThan(0);
  });

  it('says nothing when an older service does not report the field at all', async () => {
    // A CONSOLE CAN BE NEWER THAN THE SERVICE IT TALKS TO — that is what a rollout is. `undefined`
    // must not render as «0 متعثّرة»: inventing a certainty from a missing field is the same defect
    // as the one this line exists to end, pointed the other way.
    open({ sent_today: 4, waiting: 3 });
    await screen.findByText('بانتظار الإرسال');
    expect(screen.queryByText(/تحاول الخروج/)).toBeNull();
  });
});
