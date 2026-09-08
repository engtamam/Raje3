/**
 * The reporter's three rules, pinned — because every one of them is invisible when broken.
 *
 * A reporter that throws, or that reports its own failure to report, does not produce a wrong
 * screen. It produces a browser tab that gets slower and then dies, thousands of requests later,
 * and the only evidence is in somebody else's server logs.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { __resetForTests, installErrorReporter, report } from './errorReporter';

const SHOP_KEY = 'raje3.session';
const ADMIN_KEY = 'raje3.admin.session';

function signInAsShop() {
  localStorage.setItem(SHOP_KEY, JSON.stringify({
    tenant: 't-1', operator: 'op-1', operatorName: 'أحمد', token: 'shop-token',
  }));
}

beforeEach(() => {
  localStorage.clear();
  __resetForTests();
  vi.restoreAllMocks();
});

afterEach(() => {
  localStorage.clear();
  __resetForTests();
});

describe('what it sends', () => {
  it('posts a browser-shaped signal with source and severity set explicitly', async () => {
    signInAsShop();
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    report(new TypeError("Cannot read properties of undefined (reading 'map')"), 'onerror');
    await Promise.resolve();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/signals/report');
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer shop-token');

    const body = JSON.parse(String(init.body));
    // NEVER DEFAULTED BY THE SERVER — a row whose source the server guessed is a row the screen's
    // own filter cannot be trusted about.
    expect(body.source).toBe('browser');
    expect(body.severity).toBe('error');
    expect(body.service).toBe('console');
    expect(body.message).toBe("TypeError: Cannot read properties of undefined (reading 'map')");
    expect(body.detail.kind).toBe('onerror');
    expect(body.context.tenant).toBe('t-1');
    expect(body.context.operator).toBe('op-1');
    expect(typeof body.context.url).toBe('string');
    expect(typeof body.context.user_agent).toBe('string');
  });

  it('never puts the token in the body', async () => {
    signInAsShop();
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    report(new Error('boom'), 'manual');
    await Promise.resolve();

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(String(init.body)).not.toContain('shop-token');
  });

  it('omits request_id entirely rather than sending an empty one', async () => {
    // This console stamps no correlation header on its own requests today. An always-empty column
    // pretending to be a join key is worse than an absent one.
    signInAsShop();
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    report(new Error('boom'), 'manual');
    await Promise.resolve();

    const body = JSON.parse(String((fetchMock.mock.calls[0] as [string, RequestInit])[1].body));
    expect('request_id' in body).toBe(false);
  });

  it('truncates a runaway stack instead of being refused at the door', async () => {
    signInAsShop();
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    const err = new Error('deep');
    err.stack = 'x'.repeat(200_000);
    report(err, 'onerror');
    await Promise.resolve();

    const body = JSON.parse(String((fetchMock.mock.calls[0] as [string, RequestInit])[1].body));
    // Comfortably inside the collector's own 16 KB ceiling on the whole blob.
    expect(body.detail.stack.length).toBeLessThan(9000);
    expect(body.detail.stack.endsWith('(truncated)')).toBe(true);
  });

  it('reports a bare string too — a cross-origin "Script error." is still a signal', async () => {
    signInAsShop();
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    report('Script error.', 'onerror');
    await Promise.resolve();

    const body = JSON.parse(String((fetchMock.mock.calls[0] as [string, RequestInit])[1].body));
    expect(body.message).toBe('Script error.');
    expect('stack' in body.detail).toBe(false);
  });

  it('reads whichever door this person came through', async () => {
    localStorage.setItem(ADMIN_KEY, JSON.stringify({ access_token: 'admin-token' }));
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    report(new Error('boom'), 'manual');
    await Promise.resolve();

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer admin-token');
    // The admin session carries no tenant — the field is omitted, never sent empty.
    expect('tenant' in JSON.parse(String(init.body)).context).toBe(false);
  });

  it('sends nothing at all when nobody is signed in', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    report(new Error('boom'), 'onerror');
    await Promise.resolve();

    // The route requires a session, so an anonymous POST would be a 401 this module would then
    // have to not report.
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe('it cannot make things worse', () => {
  it('a failing report is a true no-op — never a throw, never a rejection', async () => {
    signInAsShop();
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')));

    expect(() => report(new Error('boom'), 'onerror')).not.toThrow();
    // Let the rejection settle. If it were unhandled, vitest would fail the run here.
    await new Promise((r) => setTimeout(r, 0));
  });

  it('a broken localStorage is a no-op, not a second error', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('access denied');
    });
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    expect(() => report(new Error('boom'), 'onerror')).not.toThrow();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('drops a second error while one is in flight — a queue is just a slower loop', async () => {
    signInAsShop();
    let release: (v: unknown) => void = () => {};
    const pending = new Promise((r) => { release = r; });
    const fetchMock = vi.fn().mockReturnValue(pending);
    vi.stubGlobal('fetch', fetchMock);

    report(new Error('first'), 'onerror');
    report(new Error('second'), 'onerror');
    report(new Error('third'), 'unhandledrejection');
    expect(fetchMock).toHaveBeenCalledTimes(1);

    release(new Response('{}', { status: 200 }));
    await new Promise((r) => setTimeout(r, 0));

    // AND THE GATE REOPENS. One failed or slow report must not silence every later one.
    report(new Error('fourth'), 'onerror');
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('the gate reopens even after a rejected fetch', async () => {
    signInAsShop();
    const fetchMock = vi.fn().mockRejectedValue(new Error('network down'));
    vi.stubGlobal('fetch', fetchMock);

    report(new Error('first'), 'onerror');
    await new Promise((r) => setTimeout(r, 0));
    report(new Error('second'), 'onerror');
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});

describe('install', () => {
  it('catches a thrown error and an unhandled rejection, and installs only once', async () => {
    signInAsShop();
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    const addSpy = vi.spyOn(window, 'addEventListener');
    installErrorReporter();
    installErrorReporter();          // a second call must add nothing
    const kinds = addSpy.mock.calls.map((c) => c[0]);
    expect(kinds.filter((k) => k === 'error')).toHaveLength(1);
    expect(kinds.filter((k) => k === 'unhandledrejection')).toHaveLength(1);

    window.dispatchEvent(new ErrorEvent('error', {
      message: 'boom', error: new Error('boom'),
    }));
    await new Promise((r) => setTimeout(r, 0));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(JSON.parse(String((fetchMock.mock.calls[0] as [string, RequestInit])[1].body)).detail.kind)
      .toBe('onerror');

    // ADDITIVE, NOT REPLACING: assigning window.onerror would silently discard the shell's own.
    expect(window.onerror).toBeNull();
  });
});
