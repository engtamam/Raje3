/**
 * `req()`'s own half of the renewal fix — ./renew.test.ts proves `renew()` itself; this proves
 * `req()` actually reaches for it: a 401 gets ONE retry with a freshly renewed bearer before the
 * caller ever sees a failure, matching `../api.ts`'s own `call()`.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('./renew', () => ({
  fresh: vi.fn(async (token: string) => token),
  renew: vi.fn(async () => 'renewed-token'),
}));

import { me } from './api';
import { renew } from './renew';

describe('affiliate api req()', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
  });

  it('retries once with a renewed bearer after a 401, and the caller never sees it', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: 'expired' }), { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ affiliate_id: 'a1', name: 'x' }), { status: 200 }));

    const out = await me({ access_token: 'old-token' });

    expect(out).toEqual({ affiliate_id: 'a1', name: 'x' });
    expect(renew).toHaveBeenCalledTimes(1);
    expect(fetchSpy).toHaveBeenCalledTimes(2);
    const secondCallHeaders = fetchSpy.mock.calls[1]![1]!.headers as Record<string, string>;
    expect(secondCallHeaders.Authorization).toBe('Bearer renewed-token');
  });

  it('still refuses if renewal itself cannot recover the 401', async () => {
    vi.mocked(renew).mockResolvedValueOnce('');
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ message: 'انتهت الجلسة' }), { status: 401 }));

    await expect(me({ access_token: 'old-token' })).rejects.toThrow('انتهت الجلسة');
  });
});
