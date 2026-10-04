/**
 * `VisitQueue`'s own post-save resolution (2026-10-04): `applyOfferSubject` and `pointsRewardId`
 * are mutually exclusive, and whichever is set is spent only AFTER `recordVisit` actually lands —
 * never raced against it. See queue.ts's own docstrings on both fields for why.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const recordVisit = vi.fn();
const applyOffer = vi.fn();
const redeemVisitPoints = vi.fn();

vi.mock('./api', () => ({
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) { super(message); this.status = status; }
  },
  recordVisit: (...args: unknown[]) => recordVisit(...args),
  applyOffer: (...args: unknown[]) => applyOffer(...args),
  redeemVisitPoints: (...args: unknown[]) => redeemVisitPoints(...args),
}));

const SESSION = { access_token: 'tok-1' } as never;
const DRAFT = { phone: '0500000001', service_ids: ['svc_1'] } as never;

async function flush() {
  await new Promise((r) => setTimeout(r, 0));
  await new Promise((r) => setTimeout(r, 0));
}

describe('VisitQueue points vs offer', () => {
  beforeEach(() => {
    vi.resetModules();
    recordVisit.mockReset();
    applyOffer.mockReset();
    redeemVisitPoints.mockReset();
    localStorage.clear();
  });
  afterEach(() => vi.resetAllMocks());

  it('spends the points reward, not the offer, when pointsRewardId is set', async () => {
    recordVisit.mockResolvedValue({ visit: { id: 'vis_1' } });
    const { queue } = await import('./queue');

    queue.add(DRAFT, SESSION, undefined, 'rwd_1');
    await flush();

    expect(redeemVisitPoints).toHaveBeenCalledWith(SESSION, 'vis_1', 'rwd_1');
    expect(applyOffer).not.toHaveBeenCalled();
  });

  it('applies the offer when only applyOfferSubject is set', async () => {
    recordVisit.mockResolvedValue({ visit: { id: 'vis_2' } });
    const { queue } = await import('./queue');

    queue.add(DRAFT, SESSION, 'sub_1');
    await flush();

    expect(applyOffer).toHaveBeenCalledWith(SESSION, 'sub_1', 'vis_2');
    expect(redeemVisitPoints).not.toHaveBeenCalled();
  });

  it('spends neither when the operator chose neither', async () => {
    recordVisit.mockResolvedValue({ visit: { id: 'vis_3' } });
    const { queue } = await import('./queue');

    queue.add(DRAFT, SESSION);
    await flush();

    expect(applyOffer).not.toHaveBeenCalled();
    expect(redeemVisitPoints).not.toHaveBeenCalled();
  });

  it('a failed points redemption never blocks the visit from draining off the queue', async () => {
    recordVisit.mockResolvedValue({ visit: { id: 'vis_4' } });
    redeemVisitPoints.mockRejectedValue(new Error('insufficient points'));
    const { queue } = await import('./queue');

    queue.add(DRAFT, SESSION, undefined, 'rwd_1');
    await flush();

    expect(queue.pending()).toHaveLength(0);
  });
});
