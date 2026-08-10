/**
 * The rules that cost money if they are wrong.
 *
 * Not a rendering test — the layout will change a dozen times before a shop sees it. These are the
 * three behaviours underneath it that a redesign must not quietly break: the visit survives the
 * network, a retry does not become a second visit, and a failure that retrying cannot fix is held
 * rather than dropped.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { VisitQueue, newIdempotencyKey } from './queue';
import type { Session } from './session';

const SESSION: Session = {
  tenant: 't1', operator: 'op1', operatorName: 'أحمد', token: 'tok', sector: 'tyres',
};

function draft(key: string) {
  return { phone: '0501234567', service_ids: ['s1'], idempotency_key: key };
}

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe('the key that stops a double charge', () => {
  it('is different for every visit', () => {
    const keys = new Set(Array.from({ length: 200 }, () => newIdempotencyKey()));
    expect(keys.size).toBe(200);
  });

  it('is the SAME on every retry of one visit — which is the whole point', async () => {
    const seen: string[] = [];
    vi.stubGlobal('fetch', vi.fn(async (_u: string, init: RequestInit) => {
      seen.push(JSON.parse(String(init.body)).idempotency_key);
      // Fail once, succeed on the retry: the case where a lost ANSWER, not a lost request, would
      // otherwise create a second visit, a second reminder and a second billable message.
      return seen.length === 1
        ? new Response('{}', { status: 503 })
        : new Response('{}', { status: 201 });
    }));

    const q = new VisitQueue();
    q.add(draft('key-1'), SESSION);
    await q.drain(SESSION);
    await q.drain(SESSION);

    expect(seen.length).toBeGreaterThanOrEqual(2);
    expect(new Set(seen)).toEqual(new Set(['key-1']));
  });
});

describe('the visit survives the network', () => {
  it('is kept when the request fails, so the operator loses nothing', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('offline'); }));
    const q = new VisitQueue();
    q.add(draft('k'), SESSION);
    await q.drain(SESSION);
    expect(q.pending()).toHaveLength(1);
  });

  it('is gone once it has actually been recorded', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 201 })));
    const q = new VisitQueue();
    q.add(draft('k'), SESSION);
    await q.drain(SESSION);
    expect(q.pending()).toHaveLength(0);
  });

  it('outlives the tab — a tablet that slept all night still owes those visits', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('offline'); }));
    const first = new VisitQueue();
    first.add(draft('k'), SESSION);
    await first.drain(SESSION);

    const reopened = new VisitQueue();          // as if the app had been closed and started again
    expect(reopened.pending()).toHaveLength(1);
  });
});

describe('a failure retrying cannot fix', () => {
  it('is held and surfaced, never silently dropped', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{"message":"لا"}', { status: 400 })));
    const q = new VisitQueue();
    q.add(draft('k'), SESSION);
    await q.drain(SESSION);
    // Dropping it would tell the shop a visit was recorded that was not — the one outcome worse
    // than an error, because nobody investigates a success.
    expect(q.pending()).toHaveLength(0);
    expect(q.stuck()).toHaveLength(1);
  });

  it('does not hold a 401, because a refreshed token fixes exactly that', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 401 })));
    const q = new VisitQueue();
    q.add(draft('k'), SESSION);
    await q.drain(SESSION);
    expect(q.stuck()).toHaveLength(0);
    expect(q.pending()).toHaveLength(1);
  });
});

describe('the queue does not run over itself', () => {
  it('sends one visit once even when three signals fire together', async () => {
    let calls = 0;
    vi.stubGlobal('fetch', vi.fn(async () => {
      calls += 1;
      await new Promise((r) => setTimeout(r, 5));
      return new Response('{}', { status: 201 });
    }));
    const q = new VisitQueue();
    q.add(draft('k'), SESSION);
    await Promise.all([q.drain(SESSION), q.drain(SESSION), q.drain(SESSION)]);
    expect(calls).toBe(1);
  });
});
