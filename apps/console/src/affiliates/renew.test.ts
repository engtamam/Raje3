/**
 * Affiliate-portal renewal — same three cases as `../renew.test.ts`, ported to this door's own
 * storage key and event name (see ./renew.ts's own header for why a marketer hit a wall of 401s
 * that a shop owner never did).
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { renew, AFFILIATE_SESSION_RENEWED } from './renew';
import { KEY } from './session';

function store(session: Record<string, unknown>): void {
  localStorage.setItem(KEY, JSON.stringify(session));
}

const SIGNED_IN = { access_token: 'old', refresh_token: 'r1', tenant: 't1' };

describe('affiliate renew', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('gives up immediately when the stored session has no refresh token', async () => {
    store({ access_token: 'old' });
    const fetchSpy = vi.spyOn(globalThis, 'fetch');

    expect(await renew()).toBe('');
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('stores the new pair and announces it, so no screen keeps using the dead bearer', async () => {
    store(SIGNED_IN);
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ access_token: 'new', refresh_token: 'r2' }), { status: 200 }));
    const heard = vi.fn();
    window.addEventListener(AFFILIATE_SESSION_RENEWED, heard);

    expect(await renew()).toBe('new');

    const held = JSON.parse(localStorage.getItem(KEY)!);
    expect(held.access_token).toBe('new');
    expect(held.refresh_token).toBe('r2');
    expect(heard).toHaveBeenCalled();
  });

  it('spends the refresh token ONCE when several requests meet the 401 together', async () => {
    store(SIGNED_IN);
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ access_token: 'new', refresh_token: 'r2' }), { status: 200 }));

    const [a, b, c] = await Promise.all([renew(), renew(), renew()]);

    expect([a, b, c]).toEqual(['new', 'new', 'new']);
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it('treats a refused renewal as the end, and a network failure as not now', async () => {
    store(SIGNED_IN);
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('', { status: 401 }));
    expect(await renew()).toBe('');
    expect(JSON.parse(localStorage.getItem(KEY)!).access_token).toBe('old');

    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('offline'));
    expect(await renew()).toBe('');
  });
});
