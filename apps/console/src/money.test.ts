/**
 * ح-9 و ح-10 — the two directions money crosses this boundary, and what each one used to lose.
 *
 * Every case here is a real amount from the defects: 26950 was an invoice rounded UP past what was
 * charged, 9950 was a plan advertised fifty halalas above its price, and 2.3 is the input whose
 * float multiply produced 229.99999999999997.
 */
import { describe, expect, it } from 'vitest';
import { halalas, riyals, riyalsLabel } from './money';

describe('halalas → riyals on the screen', () => {
  it('keeps the fraction an invoice was actually charged', () => {
    // ح-9: `Math.round(26950 / 100)` was 270 — more than the card was debited.
    expect(riyals(26950)).toBe('269.50');
    expect(riyals(26910)).toBe('269.10');
  });

  it('does not advertise a plan above its price', () => {
    // ح-9: a plan at 9950 was shown as «100 ريال» on the screen that states the price.
    expect(riyals(9950)).toBe('99.50');
  });

  it('shows a round amount without a pointless «.00»', () => {
    expect(riyals(700)).toBe('7');
    expect(riyals(0)).toBe('0');
  });

  it('keeps a single-digit fraction padded, so 269.05 is never read as 269.5', () => {
    expect(riyals(26905)).toBe('269.05');
  });

  it('keeps the sign outside the fraction for a credit or refund', () => {
    expect(riyals(-26950)).toBe('-269.50');
  });

  it('labels an absent amount rather than printing «0 ريال» for it', () => {
    expect(riyalsLabel(null)).toBe('—');
    expect(riyalsLabel(undefined)).toBe('—');
    expect(riyalsLabel(26950)).toBe('269.50 ريال');
  });
});

describe('what he typed → halalas on the wire', () => {
  it('converts the amount that float arithmetic got wrong', () => {
    // ح-10: `2.3 * 100` is 229.99999999999997, truncated to 229 — one halala short forever.
    expect(halalas('2.3')).toBe(230);
    expect(2.3 * 100).not.toBe(230);          // the reason this function exists
  });

  it('handles the amounts that survive a float too, so nothing changes for them', () => {
    expect(halalas('50')).toBe(5000);
    expect(halalas('2.50')).toBe(250);
    expect(halalas('0.05')).toBe(5);
  });

  it('accepts the Arabic decimal separator, because a phone keyboard produces it', () => {
    expect(halalas('2٫3')).toBe(230);
  });

  it('refuses a third decimal place rather than silently rounding his money', () => {
    expect(halalas('2.305')).toBeNull();
  });

  it('refuses what is not a price at all', () => {
    expect(halalas('')).toBeNull();
    expect(halalas('abc')).toBeNull();
    expect(halalas('2.3.4')).toBeNull();
  });

  it('round-trips: what he typed is what the screen shows back', () => {
    for (const typed of ['2.3', '99.50', '0.05', '1000']) {
      const minor = halalas(typed);
      expect(minor).not.toBeNull();
      expect(halalas(riyals(minor as number))).toBe(minor);
    }
  });
});
