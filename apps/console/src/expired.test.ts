/**
 * The rule that decides whether a dead token ends the session or hangs the screen.
 *
 * This is not about a message an operator reads — it is about the state the app is left in. The
 * failure it locks down was live: a token expired, every screen's fetch answered 401, each one
 * caught its own error into a console nobody has open, and the person kept looking at a skeleton
 * that would never fill. He was signed out on the server and still holding an application.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SESSION_EXPIRED } from './expired';
import { recentCustomers } from './api';
import type { Session } from './session';

const SESSION: Session = { tenant: 't1', operator: 'op1', operatorName: 'أحمد', token: 'tok' };

function heard(): { count: () => number; stop: () => void } {
  let n = 0;
  const on = () => { n += 1; };
  window.addEventListener(SESSION_EXPIRED, on);
  return { count: () => n, stop: () => window.removeEventListener(SESSION_EXPIRED, on) };
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('a refused token ends the session from wherever it was refused', () => {
  it('announces on 401', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 401 })));
    const ear = heard();
    await expect(recentCustomers(SESSION)).rejects.toThrow();
    expect(ear.count()).toBe(1);
    ear.stop();
  });

  /**
   * 403 IS NOT AN EXPIRED SESSION, and conflating them is how an operator gets thrown to the door
   * for opening a section his role does not reach. The token is perfectly good; the answer is
   * about the capability, and the app must stay exactly where it is.
   */
  it('stays silent on 403', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 403 })));
    const ear = heard();
    await expect(recentCustomers(SESSION)).rejects.toThrow();
    expect(ear.count()).toBe(0);
    ear.stop();
  });

  it('stays silent on an outage, which is not about this person at all', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 503 })));
    const ear = heard();
    await expect(recentCustomers(SESSION)).rejects.toThrow();
    expect(ear.count()).toBe(0);
    ear.stop();
  });
});
