/**
 * payment.ts — Moyasar tokenisation, mocked at the fetch boundary. `canMintToken` is computed
 * from `import.meta.env` at module load, so every test here stubs the env and imports the module
 * fresh (`vi.resetModules`) rather than importing once at the top of the file.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

beforeEach(() => {
  vi.resetModules();
  vi.stubEnv('VITE_MOYASAR_PUBLISHABLE_KEY', 'pk_test_abc123');
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const CARD = { name: 'Ahmed Ali', number: '4111111111111111', month: '09', year: '2030', cvc: '123' };

describe('canMintToken', () => {
  it('is true once a publishable key is configured', async () => {
    const { canMintToken } = await import('./payment');
    expect(canMintToken).toBe(true);
  });

  it('is false with no key — the honest default until Ops sets one', async () => {
    vi.stubEnv('VITE_MOYASAR_PUBLISHABLE_KEY', '');
    vi.resetModules();
    const { canMintToken, tokenizeCard, NO_CARD_FORM } = await import('./payment');
    expect(canMintToken).toBe(false);
    const result = await tokenizeCard(CARD, 'https://x/');
    expect(result).toEqual({ kind: 'error', message: NO_CARD_FORM });
  });
});

describe('tokenizeCard', () => {
  it('returns a redirect when Moyasar asks for 3DS — the ordinary case (save_only always triggers it)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true, json: async () => ({ id: 'token_abc', status: 'initiated',
                                     verification_url: 'https://verify.moyasar.com/x' }),
    }));
    const { tokenizeCard } = await import('./payment');
    const result = await tokenizeCard(CARD, 'https://console.raje3/return');
    expect(result).toEqual({ kind: 'redirect', url: 'https://verify.moyasar.com/x' });
  });

  it('returns a usable token directly for the rare card that skips 3DS', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true, json: async () => ({ id: 'token_xyz', status: 'active' }),
    }));
    const { tokenizeCard } = await import('./payment');
    const result = await tokenizeCard(CARD, 'https://x/');
    expect(result).toEqual({ kind: 'token', token: 'token_xyz' });
  });

  it('surfaces Moyasar\'s own refusal sentence, never a guessed one', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false, json: async () => ({ message: 'Invalid card number.' }),
    }));
    const { tokenizeCard } = await import('./payment');
    const result = await tokenizeCard(CARD, 'https://x/');
    expect(result).toEqual({ kind: 'error', message: 'Invalid card number.' });
  });

  it('tells a network failure apart from a declined card', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    const { tokenizeCard } = await import('./payment');
    const result = await tokenizeCard(CARD, 'https://x/');
    expect(result.kind).toBe('error');
    expect((result as { message: string }).message).toMatch(/الاتصال/);
  });

  it('authenticates with Basic auth using the publishable key, never a token in the URL', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: 't', status: 'active' }) });
    vi.stubGlobal('fetch', fetchMock);
    const { tokenizeCard } = await import('./payment');
    await tokenizeCard(CARD, 'https://x/');
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('https://api.moyasar.com/v1/tokens');
    expect((init.headers as Record<string, string>).Authorization).toBe(`Basic ${btoa('pk_test_abc123:')}`);
    expect(JSON.parse(init.body as string).save_only).toBe(true);
  });
});

describe('confirmToken', () => {
  it('accepts an active/verified token', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true, json: async () => ({ id: 'token_abc', status: 'active' }),
    }));
    const { confirmToken } = await import('./payment');
    expect(await confirmToken('token_abc')).toEqual({ kind: 'token', token: 'token_abc' });
  });

  it('refuses a token still stuck at "initiated" — the bank declined 3DS', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true, json: async () => ({ id: 'token_abc', status: 'initiated' }),
    }));
    const { confirmToken } = await import('./payment');
    const result = await confirmToken('token_abc');
    expect(result.kind).toBe('error');
  });
});
