import { describe, expect, it } from 'vitest';
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
