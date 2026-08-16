/**
 * The two rules the customer record turns on, tested where they can be tested cheaply.
 *
 * Not a rendering test — the layout will move. These are the decisions underneath it: what "left"
 * means when an owner is scanning, and which offers belong on WHOSE screen.
 */
import { describe, expect, it } from 'vitest';
import { partitionOffers, remaining } from './offers';

const NOW = Math.floor(Date.now() / 1000);
/**
 * A SECOND OF SLACK, BECAUSE THE CLOCK MOVES BETWEEN THESE TWO LINES. `NOW` is read when this
 * module loads and `remaining()` reads the clock again when it is called; a boundary crossed in
 * between turns «3 أيام» into «يومان» and fails a correct function. It failed exactly that way
 * once in this suite, and a test that fails on the tick is one people re-run rather than read.
 */
const IN = (seconds: number) => NOW + seconds + 30;

describe('how long is left, for somebody scanning rather than timing', () => {
  it('says days while days remain', () => {
    expect(remaining(IN(3 * 86400))).toContain('3');
    expect(remaining(IN(3 * 86400))).toContain('يوم');
  });

  it('drops to hours only under a day, because "0 days" reads as expired', () => {
    expect(remaining(IN(5 * 3600))).toContain('ساعات');
  });

  it('says the last hour plainly rather than counting minutes at him', () => {
    expect(remaining(IN(600))).toBe('ينتهي خلال ساعة');
  });

  it('says nothing at all once it has run out — the badge carries that', () => {
    expect(remaining(NOW - 60)).toBe('');
  });
});

describe('live and expired are separated by the SERVER, never by this screen', () => {
  const live = { text: 'a', expires_at: NOW + 86400, sent_at: NOW, services: [], live: true };
  const dead = { text: 'b', expires_at: NOW - 86400, sent_at: NOW - 2, services: [], live: false };

  it('keeps both, in that order', () => {
    /**
     * The owner asks "did he get last month's offer?" as often as "what is he holding now", and an
     * answer that hides what ran out makes his own history unreadable.
     */
    const [now, past] = partitionOffers([dead, live]);
    expect(now).toEqual([live]);
    expect(past).toEqual([dead]);
  });

  it('trusts `live` rather than recomputing it from the expiry', () => {
    /**
     * Two clocks disagreeing about whether an offer is live is a support call nobody can settle —
     * and the browser's clock is the one that can be wrong on purpose.
     */
    const serverSaysDead = { ...live, live: false };
    const [now] = partitionOffers([serverSaysDead]);
    expect(now).toEqual([]);
  });
});
