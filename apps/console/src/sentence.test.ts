import { describe, expect, it, vi } from 'vitest';
import { ApiError, sentenceFor } from './api';

/** A cashier with a customer in front of him cannot act on a route or a status code.
 *
 *  `ApiError.message` is built for a LOG — `POST /api/v1/loyalty/redeem → 400`. The redemption on
 *  the visit screen rendered exactly that, under a comment promising «the sentence the service
 *  wrote». Loyalty was changed to RETURN its refusals rather than raise them for this moment
 *  precisely; the console then threw the sentence away. */
describe('sentenceFor', () => {
  it('prefers the sentence the service wrote, whichever key it used', () => {
    for (const body of [{ reason: 'رصيد العميل لا يكفي' },
                        { message: 'رصيد العميل لا يكفي' },
                        { detail: 'رصيد العميل لا يكفي' }]) {
      expect(sentenceFor(new ApiError(400, body, 'POST /x → 400'), 'تعذّر'))
        .toBe('رصيد العميل لا يكفي');
    }
  });

  it('NEVER returns the log line, even when the body says nothing', () => {
    const said = sentenceFor(new ApiError(400, null, 'POST /api/v1/loyalty/redeem → 400'),
                             'تعذّر الاستبدال.');
    expect(said).toBe('تعذّر الاستبدال.');
    expect(said).not.toMatch(/[A-Za-z/]|→/);
  });

  it('tells an ended session and an unavailable service apart', () => {
    expect(sentenceFor(new ApiError(401, null, 'x'), 'تعذّر')).toContain('الجلسة');
    expect(sentenceFor(new ApiError(503, null, 'x'), 'تعذّر')).toContain('لا تستجيب');
  });

  it('keeps the site’s own words for anything else, so one act is not confused with another', () => {
    expect(sentenceFor(new Error('boom'), 'تعذّر الحذف')).toBe('تعذّر الحذف');
    expect(sentenceFor(new TypeError('Failed to fetch'), 'تعذّر الحذف')).toContain('اتصال');
  });
});

/** The other two throwers already resolved the service's sentence before throwing — discarding it
 *  would have broken two paths to fix one. */
describe('sentenceFor keeps a sentence written for a person, whoever threw it', () => {
  it('keeps an Arabic message from a plain Error (catalog.call, auth.post)', () => {
    expect(sentenceFor(new Error('رقم الجوال مسجّل مسبقاً'), 'تعذّر تسجيل الدخول.'))
      .toBe('رقم الجوال مسجّل مسبقاً');
  });

  it('still refuses a Latin log line from those same throwers', () => {
    expect(sentenceFor(new Error('POST /api/v1/signup → 409'), 'تعذّر إنشاء الحساب.'))
      .toBe('تعذّر إنشاء الحساب.');
  });
});

/** Embedded Signup v2 AND v3 both die on 15 October 2026. v4 takes no parameters at all: the
 *  version is a property of the Facebook Login for Business configuration behind `config_id`, set
 *  on Meta's side. Anything we put in `extras` is either ignored or rejected, and the two keys we
 *  used to send — `featureType` and `sessionInfoVersion` — are exactly the ones that expire. */
describe('the Embedded Signup extras', () => {
  it('carries nothing, whatever the environment says', async () => {
    vi.resetModules();
    // THE ENVIRONMENT CANNOT PUT THE OLD SHAPE BACK. A leftover build argument on some machine is
    // precisely how a retired parameter survives a migration, so the extras are a constant and
    // read no variable at all.
    vi.stubEnv('VITE_META_SIGNUP_VERSION', 'v3');
    const { SIGNUP_EXTRAS } = await import('./meta');
    expect(SIGNUP_EXTRAS).toEqual({});
    vi.unstubAllEnvs();
  });

  it('falls back to the Graph version the back end speaks, not an older one', async () => {
    // The console pinned v21.0 while the onboarding adapter behind it called v26.0 — one product
    // holding two conversations with Meta. A retired Graph version does not fail loudly: the
    // field you asked for stops appearing, so the shop is «connected» and cannot send. This is
    // the default a deployment inherits when it names none, which is the half that drifted.
    vi.resetModules();
    vi.stubEnv('VITE_META_GRAPH_VERSION', '');
    const { GRAPH_VERSION } = await import('./meta');
    expect(GRAPH_VERSION).toBe('v26.0');
    vi.unstubAllEnvs();
  });
});
