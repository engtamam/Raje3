/**
 * Renewal — the rules that decide whether a session survives the 15-minute bearer.
 *
 * WHY THESE THREE. Each one is a way the fix could look correct and still throw an owner out at
 * the counter, and none of them is visible by reading the code: a session with nothing to renew
 * with, a renewal the server refuses, and two screens meeting the 401 at the same instant.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { renew, SESSION_RENEWED } from './renew';
import { KEY } from './session';

function store(session: Record<string, unknown>): void {
  localStorage.setItem(KEY, JSON.stringify(session));
}

const SIGNED_IN = { tenant: 't1', operator: '', operatorName: '', token: 'old', refresh: 'r1' };

describe('renew', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('gives up immediately when the stored session has no refresh token', async () => {
    /**
     * THE CASE THE OWNER HIT. Sessions minted before the console kept the refresh token hold only
     * a bearer, so there is genuinely nothing to spend — and the right answer is to say so at once
     * rather than fire a request that cannot succeed. Returning '' is what tells the caller the
     * session is really over and expiry may be announced.
     */
    store({ tenant: 't1', operator: '', operatorName: '', token: 'old' });
    const fetchSpy = vi.spyOn(globalThis, 'fetch');

    expect(await renew()).toBe('');
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('stores the new pair and announces it, so no screen keeps using the dead bearer', async () => {
    store(SIGNED_IN);
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ access_token: 'new', refresh_token: 'r2' }), { status: 200 }));
    const heard = vi.fn();
    window.addEventListener(SESSION_RENEWED, heard);

    expect(await renew()).toBe('new');

    const held = JSON.parse(localStorage.getItem(KEY)!);
    expect(held.token).toBe('new');
    // THE ROTATED ONE REPLACES THE OLD. The server kills a refresh token the moment it is spent,
    // so keeping the previous value would work exactly once more and then sign him out.
    expect(held.refresh).toBe('r2');
    expect(heard).toHaveBeenCalled();
  });

  it('spends the refresh token ONCE when several requests meet the 401 together', async () => {
    /**
     * A screen fires several calls at once and they can all fail at the same instant. Renewing per
     * request would present the same refresh token twice — and the second presentation is exactly
     * what the server treats as theft, revoking the whole family and turning a recoverable expiry
     * into a real sign-out.
     */
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
    // The dead bearer is left alone: overwriting storage on a refusal would lose the tenant before
    // anything had decided the session was over.
    expect(JSON.parse(localStorage.getItem(KEY)!).token).toBe('old');

    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('offline'));
    expect(await renew()).toBe('');
  });
});
