/**
 * The one choice that scopes the whole console — and the rule it cannot bend.
 *
 * «يُضيِّق ولا يوسّع أبداً». The switcher moved from the header of «محلّي» to the top of the rail,
 * where it governs every screen instead of one. That makes it worth more and riskier: a control
 * that could offer a branch its owner may not read would produce empty screens for somebody who
 * did nothing wrong, and would look like the product was broken rather than like a filter was set.
 */
import { describe, expect, it } from 'vitest';

import { canSwitch, currentBranch, outsideVisits, scopeQuery } from './branch-scope';

const TWO = [{ id: 'b-1', name: 'الرياض' }, { id: 'b-2', name: 'جدة' }];

describe('the stored choice is only honoured while it is still his', () => {
  it('keeps a branch that is on the list the server just sent', () => {
    expect(currentBranch(TWO, 'b-2')).toBe('b-2');
  });

  it('falls back to everything when the stored branch is no longer his', () => {
    // A CHOICE OUTLIVES THE PERMISSION THAT ALLOWED IT. He narrows to Jeddah on Tuesday; the
    // branch closes, or his scope changes, and the id he stored is one he may not read. A console
    // that kept asking for it would show him empty screens until he thought to look at a control
    // he set last week — «everything» is the state a person understands without being told, and
    // it is never more than he is allowed.
    expect(currentBranch(TWO, 'b-gone')).toBe('');
    expect(currentBranch([], 'b-1')).toBe('');
  });

  it('treats nothing stored, and whitespace, as everything', () => {
    expect(currentBranch(TWO, null)).toBe('');
    expect(currentBranch(TWO, '  ')).toBe('');
  });
});

describe('the control appears only where it means something', () => {
  it('one branch is no choice', () => {
    // Rendering it would ask a single-branch shop — and every manager scoped to one place — to
    // stop and think about a filter that cannot change anything.
    expect(canSwitch([{ id: 'b-1' }])).toBe(false);
    expect(canSwitch([])).toBe(false);
  });

  it('two is the first number at which it does', () => {
    expect(canSwitch(TWO)).toBe(true);
  });
});

describe('what the screens send', () => {
  it('«كل الفروع» sends nothing at all rather than an empty value', () => {
    // An empty `branch_id=` is a value the server would have to decide the meaning of, and the two
    // readings — «the whole shop» and «the branch whose id is empty» — are different questions.
    expect(scopeQuery('')).toEqual({});
    expect(scopeQuery('b-1')).toEqual({ branch_id: 'b-1' });
  });
});

describe('what the view is not showing', () => {
  const rows = [{ branch_id: 'b-1', visits: 10 }, { branch_id: 'b-2', visits: 30 }];

  it('counts every visit outside this branch, including the unbranched ones', () => {
    // They are outside EVERY branch view rather than merely outside this one, so they belong in
    // the number — a manager told «30 outside» who then finds 5 more he was never shown has been
    // given a figure he cannot reconcile.
    expect(outsideVisits(rows, 5, 'b-1')).toBe(35);
  });

  it('says nothing on «كل الفروع», where the sentence would be noise', () => {
    expect(outsideVisits(rows, 5, '')).toBe(0);
  });

  it('never goes negative when a branch was closed since the count was taken', () => {
    // A row can carry more visits than the total the snapshot knows about; «-40 زيارة خارج هذا
    // العرض» is unreadable, and a number that reads as nonsense costs more trust than a missing one.
    expect(outsideVisits([{ branch_id: 'b-1', visits: 50 }], 0, 'b-1')).toBe(0);
  });
});
