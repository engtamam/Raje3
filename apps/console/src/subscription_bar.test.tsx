/**
 * The screen says what the services now enforce — and stays quiet about what it does not know.
 *
 * WHAT THIS PINS. `owned.base` — a whole subscription row (plan_id/status/renews_at), never a
 * boolean flag — is what `baseState`/`daysLeft`/`SubscriptionBar` read. NO PLAN POPULATES IT AT
 * ALL any more (الأساس retired 2026-09-10, المؤسسات — the one row still carrying the base-shaped
 * `messages.monthly` meter — retired 2026-09-11, "غير مناسب لوضعنا"): every shop's `owned.base`
 * now reads `null` forever. The mechanism this test pins is exactly what that needs: a shop
 * holding no base-shaped subscription simply reads `baseState → 'none'` and the bar stays silent
 * — this file tests the fixtures below directly rather than assume a real plan still exercises it.
 *
 * THE COUNTDOWN IS READ, NEVER COMPUTED. Thirty days is a number on a subscription; a screen that
 * derived «30 - days since signup» would disagree with billing the first time anybody changed the
 * subscription or extended a trial by hand.
 */
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it } from 'vitest';

import { SubscriptionBar } from './SubscriptionBar';
import { baseState, daysLeft, type Owned } from './apps';
import { DENIED } from './loading';

const NOW = 1_760_000_000_000;                       // a fixed instant, so no test waits for a day
const DAY = 86_400;

function owned(status: string, renewsInDays: number): Owned {
  return {
    checked: true,
    message: '',
    keys: [],
    apps: [],
    base: { plan_id: 'plan_1', status, renews_at: Math.floor(NOW / 1000) + renewsInDays * DAY },
  };
}

// NO GLOBAL SETUP FILE IN THIS SUITE, so the DOM is torn down here rather than assumed. A
// leftover bar from a previous case would make «says nothing» pass for the wrong reason.
afterEach(cleanup);

function bar(o: Parameters<typeof SubscriptionBar>[0]['owned']) {
  render(<MemoryRouter><SubscriptionBar owned={o} now={NOW} /></MemoryRouter>);
}

describe('what the base subscription is', () => {
  it('reads trialing, active and cancelled apart', () => {
    expect(baseState(owned('trialing', 12))).toBe('trial');
    expect(baseState(owned('active', 20))).toBe('active');
    expect(baseState(owned('canceled', -3))).toBe('lapsed');
    // PAST DUE IS NOT LAPSED. A late bank transfer must not lock a shop out of its own till —
    // billing counts it as billable and so does this.
    expect(baseState(owned('past_due', 4))).toBe('active');
  });

  it('is «unknown» while billing has not answered, and when it could not be asked', () => {
    expect(baseState(undefined)).toBe('unknown');
    expect(baseState(null)).toBe('unknown');
    expect(baseState(DENIED)).toBe('unknown');
    expect(baseState({ ...owned('active', 5), checked: false })).toBe('unknown');
  });

  it('says «none» for a shop that never activated, which is not the same as lapsed', () => {
    expect(baseState({ ...owned('active', 5), base: null })).toBe('none');
  });

  it('counts the days left from the row, and refuses to count a period already over', () => {
    expect(daysLeft(owned('trialing', 12), NOW)).toBe(12);
    expect(daysLeft(owned('canceled', -1), NOW)).toBeNull();
    expect(daysLeft(undefined, NOW)).toBeNull();
  });
});

describe('the bar an owner reads before he presses anything', () => {
  it('names what still works when the month has lapsed', () => {
    bar(owned('canceled', -2));
    const said = screen.getByRole('status').textContent ?? '';
    expect(said).toContain('انتهى اشتراكك');
    // THE HALF THAT STOPS PEOPLE PANICKING, and the half a shorter sentence would drop.
    expect(said).toContain('محفوظة');
    expect(screen.getByRole('link').textContent).toBe('جدّد الآن');
  });

  it('counts a trial down as it nears its end, and says nothing while it is far off', () => {
    bar(owned('trialing', 3));
    expect(screen.getByRole('status').textContent).toContain('3');
    cleanup();

    bar(owned('trialing', 25));
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('stays silent when the answer is unknown — never «you have not paid» to a paying shop', () => {
    bar(undefined);
    expect(screen.queryByRole('status')).toBeNull();
    cleanup();
    bar(DENIED);
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('does not nag a shop that has not activated yet — the app store already asks', () => {
    bar({ ...owned('active', 5), base: null });
    expect(screen.queryByRole('status')).toBeNull();
  });
});

// ── and the refusal a screen shows when he presses anyway ───────────────────────────────────────
//
// THE BAR IS THE WARNING; THIS IS THE FALLBACK. He may have the screen open from before the month
// lapsed, or ignore a line at the top — and then the services answer 402 with the sentence the
// licence chose. What must never happen is that he reads a status code, or a generic «تعذّر
// الحفظ», at the one moment he needs to know that his data is safe and what to press.
describe('the sentence he reads when the write is refused', () => {
  it('shows the licence’s own words rather than a code or a fallback', async () => {
    const { ApiError, sentenceFor } = await import('./api');
    // What operations and reminders actually answer: 402 with `detail` (api/subscribed.py).
    const refusal = new ApiError(402, {
      detail: 'انتهى اشتراكك — بياناتك محفوظة وتقدر تتصفّحها كلها، وتسجيل الزيارات يرجع فور التجديد من «اشتراكي».',
    }, 'POST /api/v1/field/visits → 402');
    const said = sentenceFor(refusal, 'تعذّر تسجيل الزيارة');
    expect(said).toContain('محفوظة');
    // NOT THE CALL SITE'S FALLBACK, which would drop the half that stops him panicking.
    expect(said).not.toBe('تعذّر تسجيل الزيارة');
    // AND NOT A ROUTE AND A NUMBER, which is what a log wants and a person cannot act on.
    expect(said).not.toContain('402');
  });

  it('keeps «could not ask» apart from «you have not paid»', async () => {
    const { ApiError, sentenceFor } = await import('./api');
    const outage = new ApiError(402, {
      detail: 'تعذّر التحقق من اشتراكك الآن — حاول بعد قليل.',
    }, 'POST /api/v1/field/visits → 402');
    expect(sentenceFor(outage, 'تعذّر تسجيل الزيارة')).toContain('حاول بعد قليل');
  });
});
