/**
 * «حسابي» went from eight tabs to four, and four of the old names became sections inside them.
 *
 * THE ONE THING THAT CAN SILENTLY BREAK IS THE DEEP LINK. Every «أضِفه إلى اشتراكي» lock in the
 * product, the expired-subscription screen, and any bookmark or message a shop passed around, all name a
 * tab in a query string. A rename that forgets one of them does not fail loudly — it opens the
 * wrong page, which reads as the button being broken.
 */
import { describe, expect, it } from 'vitest';
import { MOVED, resolvePane } from './Account';

describe('resolvePane', () => {
  it('keeps the four tabs that still exist', () => {
    // «الفواتير» REPLACED «دخولي» IN THIS LIST, and the swap is the whole point of the file: the
    // invoices came out of the app store and became a destination, and the login tab — three
    // cards of prose and one switch — stopped being one.
    for (const p of ['shop', 'billing', 'invoices', 'data'] as const) {
      expect(resolvePane(p)).toBe(p);
    }
  });

  it('sends every name that became a section to the tab now holding it', () => {
    // AND «دخولي» IS NOW ONE OF THEM. Its switch — the weekly report — moved twice since, and now
    // lives in «منشأتي», so a link written when it was a tab must land where the switch actually is.
    expect(resolvePane('login')).toBe('shop');
    expect(resolvePane('whatsapp')).toBe('shop');
    expect(resolvePane('team')).toBe('shop');
    expect(resolvePane('keys')).toBe('shop');
  });

  it('covers every moved name, so a section added to MOVED cannot be forgotten here', () => {
    for (const [from, to] of Object.entries(MOVED)) expect(resolvePane(from)).toBe(to);
  });

  it('lands on the establishment when nothing was asked for', () => {
    expect(resolvePane()).toBe('shop');
    expect(resolvePane('')).toBe('shop');
  });

  it('does not open a tab that does not exist', () => {
    // A URL anybody can type. The old code would have set a pane no tab matches.
    expect(resolvePane('billin')).toBe('shop');
    expect(resolvePane('__proto__')).toBe('shop');
  });
});
