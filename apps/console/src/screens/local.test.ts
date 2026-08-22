/**
 * The branch switch, and the one number that keeps it honest.
 *
 * A branch scope looks exactly like the whole shop — same cards, same ring — so the line naming
 * what is OUTSIDE the view is the only thing standing between an owner and reading one branch's
 * return rate as his business's.
 */
import { describe, expect, it } from 'vitest';
import { blockedSentence, outsideVisits, retentionStreak, topEntitiesByDay } from './Shop';

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

/**
 * The "game-like" element that is actually computed — a real, honest streak, or nothing.
 */
describe('retentionStreak', () => {
  it('says nothing on fewer than three drawn points', () => {
    expect(retentionStreak([{ value: 0.4 }, { value: 0.5 }])).toBeNull();
    expect(retentionStreak(undefined)).toBeNull();
  });

  it('counts a rising run ending at the newest point', () => {
    const points = [{ value: 0.3 }, { value: 0.35 }, { value: 0.4 }, { value: 0.5 }];
    expect(retentionStreak(points)).toEqual({ length: 4, rising: true });
  });

  it('counts a falling run the same way, and says so', () => {
    const points = [{ value: 0.6 }, { value: 0.5 }, { value: 0.4 }];
    expect(retentionStreak(points)).toEqual({ length: 3, rising: false });
  });

  it('stops the count the moment the direction reverses or goes flat', () => {
    // Rising, then flat — the streak the newest point actually belongs to is length 1, below the
    // floor, so this is silence rather than a stale streak from two points ago.
    expect(retentionStreak([{ value: 0.3 }, { value: 0.4 }, { value: 0.4 }])).toBeNull();
    // Rising twice, then a reversal — the newest point is now falling, alone.
    expect(retentionStreak([{ value: 0.3 }, { value: 0.4 }, { value: 0.5 }, { value: 0.45 }])).toBeNull();
  });

  it('skips null gaps rather than bridging across them', () => {
    // The middle point is unset (too few customers that period) — only the drawn points count,
    // and here that is still just two, below the floor.
    const points = [{ value: 0.3 }, { value: null }, { value: 0.4 }];
    expect(retentionStreak(points)).toBeNull();
  });
});

describe('topEntitiesByDay', () => {
  it('sums a flat "id:day" grid into a 7-slot day array per entity, named', () => {
    const grid = { 'svc1:0': 3, 'svc1:5': 7, 'svc2:2': 1 };
    const got = topEntitiesByDay(grid, { svc1: 'قص شعر', svc2: 'تلميع' }, 5);
    expect(got).toEqual([
      { label: 'قص شعر', days: [3, 0, 0, 0, 0, 7, 0] },
      { label: 'تلميع', days: [0, 0, 1, 0, 0, 0, 0] },
    ]);
  });

  it('sorts by total demand, highest first, and caps at the limit', () => {
    const grid = { 'a:0': 1, 'b:0': 9, 'c:0': 5 };
    const got = topEntitiesByDay(grid, {}, 2);
    expect(got.map((r) => r.label)).toEqual(['b', 'c']);
  });

  it('falls back to the raw id when no name is known, and handles an empty grid', () => {
    expect(topEntitiesByDay({ 'x:1': 1 }, {}, 5)[0].label).toBe('x');
    expect(topEntitiesByDay(undefined, {}, 5)).toEqual([]);
    expect(topEntitiesByDay({}, {}, 5)).toEqual([]);
  });
});
