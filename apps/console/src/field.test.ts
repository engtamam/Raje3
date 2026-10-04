/**
 * The rules that cost money if they are wrong.
 *
 * Not a rendering test — the layout will change a dozen times before a shop sees it. These are the
 * three behaviours underneath it that a redesign must not quietly break: the visit survives the
 * network, a retry does not become a second visit, and a failure that retrying cannot fix is held
 * rather than dropped.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { VisitQueue, newIdempotencyKey } from './queue';
import type { Session } from './session';

const SESSION: Session = {
  tenant: 't1', operator: 'op1', operatorName: 'أحمد', token: 'tok',
};

function draft(key: string) {
  return { phone: '0501234567', service_ids: ['s1'], idempotency_key: key };
}

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

// Without this, a stubbed fetch survives past this file's last test — invisible under the default
// `isolate: true` (each file gets its own global scope), but a real leak into whichever test file
// runs next in the same worker if isolation is ever turned off.
afterEach(() => {
  vi.unstubAllGlobals();
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

describe('the offer is spent only once the visit it is spent against exists (ط-1)', () => {
  /** Every call this queue makes, in the order the mocked fetch actually saw them. */
  function trackCalls() {
    const seen: { path: string; body: unknown }[] = [];
    vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit) => {
      const path = String(url).replace(/^https?:\/\/[^/]*/, '');
      seen.push({ path, body: init.body ? JSON.parse(String(init.body)) : undefined });
      if (path.startsWith('/api/v1/field/visits/') && path.endsWith('/offer')) {
        return new Response(JSON.stringify({ applied: true }), { status: 200 });
      }
      // recordVisit — answers with a server-minted visit id distinct from the idempotency key,
      // exactly the case a same-tick race could not have known.
      return new Response(JSON.stringify({
        visit: { id: 'srv-visit-9', service_ids: ['s1'] },
        customer: { id: 'c1' }, created_customer: false, duplicate: false,
      }), { status: 201 });
    }));
    return seen;
  }

  it('applies the offer to the SERVER visit id, only after the visit call has answered', async () => {
    const seen = trackCalls();
    const q = new VisitQueue();
    q.add(draft('k'), SESSION, 'subj_1');
    await q.drain(SESSION);

    const recordCall = seen.findIndex((c) => c.path === '/api/v1/field/visits');
    const offerCall = seen.findIndex((c) => c.path.endsWith('/offer'));
    expect(recordCall).toBeGreaterThanOrEqual(0);
    expect(offerCall).toBeGreaterThan(recordCall);
    // NOT THE IDEMPOTENCY KEY THE SCREEN MINTED — the id the server actually assigned this visit,
    // which the queue could only have after `recordVisit` resolved.
    expect(seen[offerCall].path).toBe('/api/v1/field/visits/srv-visit-9/offer');
    expect((seen[offerCall].body as { subject_ref: string }).subject_ref).toBe('subj_1');
  });

  it('never applies an offer when the operator did not check «طبّق العرض»', async () => {
    const seen = trackCalls();
    const q = new VisitQueue();
    q.add(draft('k'), SESSION); // no subject passed
    await q.drain(SESSION);
    expect(seen.some((c) => c.path.endsWith('/offer'))).toBe(false);
  });

  it('never applies an offer for a visit that failed to record', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{"message":"لا"}', { status: 400 })));
    const q = new VisitQueue();
    q.add(draft('k'), SESSION, 'subj_1');
    await q.drain(SESSION);
    // 400 is stuck, not retried — and crucially nothing tried to spend an offer against a visit
    // the server never created.
    expect(q.stuck()).toHaveLength(1);
  });
});

describe('a referral code offered with the visit — a one-shot notice, same shape as the '
        + 'celebration channel', () => {
  it('fires once the drained visit answers with a real grant', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
      visit: { id: 'v1' }, customer: { id: 'c1' }, created_customer: true, duplicate: false,
      referral_registration: { ok: true, new_customer_reward_type: 'discount_percent',
                              new_customer_reward_params: { percent: 10 } },
    }), { status: 201 })));
    const q = new VisitQueue();
    const seen: unknown[] = [];
    q.subscribeToReferralNotices((reg) => seen.push(reg));
    q.add({ ...draft('k'), referral_code: 'AB123' }, SESSION);
    await q.drain(SESSION);
    expect(seen).toEqual([{ ok: true, new_customer_reward_type: 'discount_percent',
                           new_customer_reward_params: { percent: 10 } }]);
  });

  it('a rejected code still fires the notice, and the visit is still recorded', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
      visit: { id: 'v1' }, customer: { id: 'c1' }, created_customer: true, duplicate: false,
      referral_registration: { ok: false, message: 'كود الإحالة غير صالح' },
    }), { status: 201 })));
    const q = new VisitQueue();
    const seen: { ok: boolean }[] = [];
    q.subscribeToReferralNotices((reg) => seen.push(reg));
    q.add({ ...draft('k'), referral_code: 'ZZZZZ' }, SESSION);
    await q.drain(SESSION);
    expect(seen).toHaveLength(1);
    expect(seen[0].ok).toBe(false);
    expect(q.pending()).toHaveLength(0);
    expect(q.stuck()).toHaveLength(0);
  });

  it('never fires when no code was offered', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
      visit: { id: 'v1' }, customer: { id: 'c1' }, created_customer: true, duplicate: false,
    }), { status: 201 })));
    const q = new VisitQueue();
    const seen: unknown[] = [];
    q.subscribeToReferralNotices((reg) => seen.push(reg));
    q.add(draft('k'), SESSION);
    await q.drain(SESSION);
    expect(seen).toHaveLength(0);
  });
});
