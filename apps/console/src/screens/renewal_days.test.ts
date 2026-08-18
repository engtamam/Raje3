/**
 * A shop is charged on as many days as it has subscriptions — #347.
 *
 * WHY THIS COUNTS DAYS AND NOT ROWS. billing starts each subscription's period at the moment of
 * purchase, so a shop that added «الحملات» two weeks after the base is charged twice a month on
 * two different days. The screen printed the base's date and nothing else, so the second charge
 * arrived unannounced. Aligning them onto one day — with the first cycle prorated — is
 * billing-service's `subscribe`, which is read-only to us; saying the truth we already hold is not.
 */
import { describe, expect, it } from 'vitest';
import { distinctRenewalDays, unreadSentence } from './Plans';
import type { Owned } from '../apps';

const DAY = 86_400;
const JAN_3 = Date.UTC(2026, 0, 3) / 1000;
const JAN_17 = Date.UTC(2026, 0, 17) / 1000;

const shop = (over: Partial<Owned>): Owned => ({
  checked: true,
  message: '',
  keys: [],
  apps: [],
  base: null,
  ...over,
});

const app = (key: string, owned: boolean | null, renews_at: number | null) =>
  ({ key, name: key, what: '', screen: '', owned, renews_at });

describe('how many days a month the shop is charged', () => {
  it('counts the base and each owned app separately when they fall on different days', () => {
    const days = distinctRenewalDays(shop({
      base: { plan_id: 'base', status: 'active', renews_at: JAN_3 },
      apps: [app('feature.campaigns', true, JAN_17)],
    }));
    expect(days.size).toBe(2);
  });

  it('counts two subscriptions bought hours apart on one date as ONE day', () => {
    // The person paying sees one date on his statement; a clock difference is not a second bill.
    const days = distinctRenewalDays(shop({
      base: { plan_id: 'base', status: 'active', renews_at: JAN_3 },
      apps: [app('feature.campaigns', true, JAN_3 + 3 * 3600)],
    }));
    expect(days.size).toBe(1);
  });

  it('ignores an app the shop does not own', () => {
    const days = distinctRenewalDays(shop({
      base: { plan_id: 'base', status: 'active', renews_at: JAN_3 },
      apps: [app('feature.loyalty', false, JAN_3 + 5 * DAY)],
    }));
    expect(days.size).toBe(1);
  });

  it('counts nothing at all when billing could not be read', () => {
    // «لا أعرف» must never be rendered as «يتجدّد في …» — the screen would be inventing a date.
    const days = distinctRenewalDays(shop({
      checked: false,
      base: { plan_id: 'base', status: 'active', renews_at: JAN_3 },
      apps: [app('feature.campaigns', true, JAN_17)],
    }));
    expect(days.size).toBe(0);
  });
});

describe('«ما زلنا نقرأ» is not «سألنا ولم نصل»', () => {
  it('carries the server\'s own sentence when billing was asked and could not answer', () => {
    // The card used to print «جارٍ التحقق…» for this, which reads as a spinner rather than an
    // outage — on the one screen an owner opens to buy, with nothing to retry.
    expect(unreadSentence(shop({ checked: false, message: 'تعذّر التحقق من اشتراكك الآن.' })))
      .toBe('تعذّر التحقق من اشتراكك الآن.');
  });

  it('says nothing while the read is still in flight', () => {
    expect(unreadSentence(undefined)).toBe('');
    expect(unreadSentence(null)).toBe('');
  });

  it('says nothing once billing answered', () => {
    expect(unreadSentence(shop({ checked: true, message: '' }))).toBe('');
  });
});
