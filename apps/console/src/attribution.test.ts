/**
 * The two values the field screen knew and never sent (أ-2, أ-3).
 *
 * Both defects were invisible from either end alone. The door declared `operator_id` and the queue
 * recorded `at`; the screen sent neither, and nothing failed — the visit saved, the screen said
 * «تم», and the branch table stayed at zero while every visit taken through an outage claimed to
 * have happened at the moment the network came back.
 *
 * These assert the WIRE, because the wire is what was missing.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { VisitQueue } from './queue';
import { forget, proof, remember } from './operator';
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
  forget();
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

describe('أ-2 · the visit says who saved it, with the proof', () => {
  it('a live ticket is attached to the visit', async () => {
    remember('op_7', 'أحمد', '1000.1300.abc', 300);
    const q = new VisitQueue();
    const who = proof();
    q.add({
      phone: '0501234567', service_ids: ['s1'], idempotency_key: 'k2',
      operator_id: who?.id, operator_ticket: who?.ticket,
    }, SESSION);
    await q.drain(SESSION);

    const body = sent()[0];
    expect(body.operator_id).toBe('op_7');
    // THE TICKET IS THE HALF THAT MATTERS. `operator_id` alone was always accepted and always a
    // free string: a device could file its work against any name in the shop, and `_branch_for`
    // reads that field to decide which BRANCH the work belongs to.
    expect(body.operator_ticket).toBe('1000.1300.abc');
  });

  it('an expired proof is not offered — the visit is filed under nobody instead', () => {
    remember('op_7', 'أحمد', '1000.1300.abc', 300);
    // Five minutes and a second later. The sheet reopens; what must never happen is the screen
    // sending a name whose proof has run out and having the attribution silently dropped, or
    // worse, attaching the last operator's name to somebody else's work.
    expect(proof(Date.now() + 301_000)).toBeNull();
  });

  it('but his NAME outlives the ticket, so re-proving is four digits and no picking', async () => {
    remember('op_7', 'أحمد', '1000.1300.abc', 300);
    const { lastSeen } = await import('./operator');
    expect(lastSeen()?.id).toBe('op_7');
  });
});
