/**
 * The branch switch, and the one number that keeps it honest.
 *
 * A branch scope looks exactly like the whole shop — same cards, same ring — so the line naming
 * what is OUTSIDE the view is the only thing standing between an owner and reading one branch's
 * return rate as his business's.
 */
import { describe, expect, it } from 'vitest';
import { blockedSentence, outsideVisits } from './Local';

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

/**
 * ي-5 — the one sentence on this screen that tells the owner what to DO.
 *
 * `coverage.blocked()` answers `{indicator, why, owner, request}`. The list rendered
 * `{b.message || b.reason}` — two fields that exist on neither side of the wire — so every row was
 * a bullet with nothing beside it. «نظام الكاشير لا يرسل الفرع مع العملية», and the text he
 * forwards to his POS vendor to get it fixed, never reached him once.
 *
 * The fields are asserted BY NAME here, against the shape services/insights/app/core/coverage.py
 * actually returns. That join is where the defect lived.
 */
describe('blockedSentence', () => {
  it('names the cause in the words the service sends', () => {
    expect(blockedSentence({
      indicator: 'branch_comparison',
      why: 'نظام الكاشير لا يرسل الفرع مع العملية',
      owner: 'pos_vendor',
      request: 'نرجو إرسال حقل branch_id مع كل عملية في طلب تسجيل الزيارة.',
    })).toBe('نظام الكاشير لا يرسل الفرع مع العملية');
  });

  it('appends how far along the learning is, so waiting does not read as never', () => {
    expect(blockedSentence({
      indicator: 'associations',
      why: 'لم تكتمل بيانات التعلّم بعد',
      owner: 'time',
      progress: { have: 120, need: 200 },
    })).toBe('لم تكتمل بيانات التعلّم بعد — 120 من 200.');
  });

  it('draws nothing at all rather than an empty bullet', () => {
    // An empty bullet reads as an indicator we could not even name, and he can do nothing with it.
    expect(blockedSentence({ indicator: 'branch_comparison' })).toBe('');
    expect(blockedSentence({ indicator: 'x', why: '   ' })).toBe('');
  });

  it('does not read the fields the screen used to guess at', () => {
    // `message` and `reason` are what the old render looked for. Neither exists on the wire, and a
    // row carrying only those must still draw nothing rather than resurrect the guess.
    expect(blockedSentence({ indicator: 'x', message: 'م', reason: 'ر' } as never)).toBe('');
  });
});
