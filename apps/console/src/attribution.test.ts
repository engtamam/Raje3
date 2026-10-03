/**
 * The value the field screen knew and never sent (أ-3).
 *
 * The defect was invisible from either end alone. The queue recorded `at`; the screen sent
 * nothing, and nothing failed — the visit saved, the screen said «تم», while every visit taken
 * through an outage claimed to have happened at the moment the network came back.
 *
 * This asserts the WIRE, because the wire is what was missing.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { VisitQueue } from './queue';
import type { Session } from './session';

const SESSION: Session = { tenant: 't1', operator: '', operatorName: '', token: 'tok' };

function sent(): Record<string, unknown>[] {
  const calls = (globalThis.fetch as unknown as { mock: { calls: [string, RequestInit][] } })
    .mock.calls;
  return calls.map(([, init]) => JSON.parse(String(init.body)) as Record<string, unknown>);
}

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  vi.restoreAllMocks();
  vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 201 })));
});

// Without this, a stubbed fetch survives past this file's last test — invisible under the default
// `isolate: true` (each file gets its own global scope), but a real leak into whichever test file
// runs next in the same worker if isolation is ever turned off.
afterEach(() => {
  vi.unstubAllGlobals();
});

describe('أ-3 · the moment of the save leaves the device', () => {
  it('a visit carries when it was taken, not when it drained', async () => {
    const q = new VisitQueue();
    const before = Math.floor(Date.now() / 1000);
    q.add({ phone: '0501234567', service_ids: ['s1'], idempotency_key: 'k1' }, SESSION);
    await q.drain(SESSION);

    const body = sent()[0];
    // THE DEFECT: no `occurred_at` at all, so `_sane_occurred_at` read 0 and answered «now» — for
    // a value that was known on the device the whole time.
    expect(typeof body.occurred_at).toBe('number');
    expect(body.occurred_at as number).toBeGreaterThanOrEqual(before);
  });
});
