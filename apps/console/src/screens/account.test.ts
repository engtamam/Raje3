/**
 * «حسابي» went from eight tabs to five, and five of the old names became sections inside them.
 *
 * THE ONE THING THAT CAN SILENTLY BREAK IS THE DEEP LINK. Every «أضِفه إلى اشتراكي» lock in the
 * product, the expired-subscription screen, and any bookmark or message a shop passed around, all name a
 * tab in a query string. A rename that forgets one of them does not fail loudly — it opens the
 * wrong page, which reads as the button being broken.
 */
import { describe, expect, it } from 'vitest';
import { MOVED, resolvePane } from './account/AccountScreen';

describe('resolvePane', () => {
  it('keeps the tabs that still exist', () => {
    // «الفروع» IS NEW IN THIS LIST — split out of the old «منشأتي» tab this pass, since "who
    // works where" earned a destination of its own rather than a sub-tab three levels deep.
    for (const p of ['identity', 'branches', 'billing', 'invoices', 'data'] as const) {
      expect(resolvePane(p)).toBe(p);
    }
  });

  it('sends every name that became a section to the tab now holding it', () => {
    // «منشأتي» ITSELF SPLIT IN TWO: shop identity and connection keys stayed on «الهوية», staff/
    // branches/WhatsApp connection moved to the new «الفروع» tab.
    expect(resolvePane('login')).toBe('identity');
    expect(resolvePane('shop')).toBe('identity');
    expect(resolvePane('keys')).toBe('identity');
    expect(resolvePane('whatsapp')).toBe('branches');
    expect(resolvePane('team')).toBe('branches');
  });

  it('covers every moved name, so a section added to MOVED cannot be forgotten here', () => {
    for (const [from, to] of Object.entries(MOVED)) expect(resolvePane(from)).toBe(to);
  });

  it('lands on identity when nothing was asked for', () => {
    expect(resolvePane()).toBe('identity');
    expect(resolvePane('')).toBe('identity');
  });

  it('does not open a tab that does not exist', () => {
    // A URL anybody can type. The old code would have set a pane no tab matches.
    expect(resolvePane('billin')).toBe('identity');
    expect(resolvePane('__proto__')).toBe('identity');
  });
});
