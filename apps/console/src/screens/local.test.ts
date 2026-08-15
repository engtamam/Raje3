/**
 * The branch switch, and the one number that keeps it honest.
 *
 * A branch scope looks exactly like the whole shop — same cards, same ring — so the line naming
 * what is OUTSIDE the view is the only thing standing between an owner and reading one branch's
 * return rate as his business's.
 */
import { describe, expect, it } from 'vitest';
import { outsideVisits } from './Local';

const ROWS = [
  { branch_id: 'riyadh', visits: 340 },
  { branch_id: 'jeddah', visits: 280 },
];

describe('outsideVisits', () => {
  it('says nothing on «كل الفروع» — nothing is outside that view', () => {
    expect(outsideVisits(ROWS, 380, '')).toBe(0);
  });

  it('counts the other branches AND the unspecified visits', () => {
    // 280 at the other branch + 380 nobody labelled = 660 the Riyadh view cannot see.
    expect(outsideVisits(ROWS, 380, 'riyadh')).toBe(660);
  });

  it('never goes negative when the table and the scope disagree', () => {
    // A branch whose snapshot exists and whose row does not — a table read a moment before a
    // branch was closed. A negative count would print «-40 زيارة خارج هذا العرض».
    expect(outsideVisits(ROWS, 0, 'unknown-branch')).toBe(620);
    expect(outsideVisits([], 0, 'riyadh')).toBe(0);
  });
});
