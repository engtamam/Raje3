/**
 * The app registry, and the lock that reads it.
 *
 * THE DEFECT THESE CLOSE. Every screen decided on its own whether to lock a paid surface, and it
 * decided from the CAPABILITY — a question about the person's role. An owner holds every
 * capability whatever apps the shop has bought, so the lock never appeared for the one person who
 * would have paid to remove it: he pressed «أطلق الحملة» on an app he had not bought and it went
 * out.
 */
import { describe, expect, it } from 'vitest';
import { APP_ROWS, keyForSection, owns, type Owned } from './apps';
import { SECTIONS } from './nav';

function answered(keys: string[]): Owned {
  return { checked: true, message: '', keys, apps: [] };
}

describe('the registry', () => {
  it('gives every app a sentence about his shop rather than about our price list', () => {
    for (const a of APP_ROWS) {
      expect(a.name.length).toBeGreaterThan(0);
      expect(a.what.length).toBeGreaterThan(0);
      // "this is a different app you haven't bought" is a fact about us. Nothing here may say it.
      expect(a.what).not.toContain('باقة');
    }
  });

  it('has exactly one base row, and it is not for sale', () => {
    const base = APP_ROWS.filter((a) => a.key === null);
    expect(base).toHaveLength(1);
    expect(base[0].id).toBe('base');
  });

  it('names no section that the nav does not have', () => {
    // A row pointing at a section that does not exist locks nothing, silently — the same shape of
    // failure as a key with a typo in it.
    const ids = SECTIONS.map((s) => s.id);
    for (const a of APP_ROWS) {
      if (a.section) expect(ids).toContain(a.section);
    }
  });

  it('lets two apps never claim the same section', () => {
    const claimed = APP_ROWS.filter((a) => a.section).map((a) => a.section);
    expect(new Set(claimed).size).toBe(claimed.length);
  });

  it('answers which key locks a section, and null for the base', () => {
    expect(keyForSection('messages')).toBe('feature.campaigns');
    expect(keyForSection('points')).toBe('feature.loyalty');
    // «عملائي» and «تسجيل زيارة» are the base and are never locked, whatever he stopped paying.
    expect(keyForSection('customers')).toBeNull();
    expect(keyForSection('visit')).toBeNull();
  });

  it('leaves «محلّي» to the base even though the engine is sold', () => {
    // The indicators are free — they are what sells everything else. The engine locks three cards
    // INSIDE the section; hiding the section would hide the argument for buying it.
    expect(keyForSection('shop')).toBeNull();
    const engine = APP_ROWS.find((a) => a.key === 'feature.insights.engine');
    expect(engine?.section).toBe('');
  });
});

describe('owns', () => {
  it('says yes to what billing listed', () => {
    expect(owns(answered(['feature.loyalty']), 'feature.loyalty')).toBe(true);
  });

  it('says no to what it did not', () => {
    expect(owns(answered(['feature.loyalty']), 'feature.campaigns')).toBe(false);
  });

  it('never locks the base', () => {
    expect(owns(answered([]), null)).toBe(true);
  });

  it('answers neither while the read is still in flight', () => {
    // NOT FALSE. A lock drawn before the answer arrives flashes «لم تشترِ» at a paying shop on
    // every single navigation.
    expect(owns(null, 'feature.campaigns')).toBeNull();
  });

  it('answers neither when billing could not be asked', () => {
    // THE WHOLE REASON `checked` IS A SEPARATE FIELD. An outage reported as "not bought" tells
    // every paying shop at once that it has not paid.
    const outage: Owned = { checked: false, message: 'تعذّر', keys: [], apps: [] };
    expect(owns(outage, 'feature.campaigns')).toBeNull();
  });

  it('does not read an empty answer as an outage', () => {
    // A shop that genuinely bought nothing must see buy buttons, not a retry banner.
    expect(owns(answered([]), 'feature.campaigns')).toBe(false);
  });
});

describe('the rating row', () => {
  const rating = APP_ROWS.find((a) => a.id === 'rating');

  it('exists, with its own key', () => {
    expect(rating?.key).toBe('feature.rating');
  });

  it('answers owns() correctly', () => {
    expect(owns(answered(['feature.rating']), 'feature.rating')).toBe(true);
    expect(owns(answered([]), 'feature.rating')).toBe(false);
  });

  it('owns its own rail section — nav.ts\'s own «التقييم» row', () => {
    expect(rating?.section).toBe('rating');
  });
});
