/**
 * ط-4: THE SCREEN DRAWS THE BLANKS THE MESSAGE HAS, AND NO OTHERS.
 *
 * Meta approves the words. The numbered blanks are the only thing a shop decides, and each one
 * belongs to somebody — the system, his own service list, or him. The screen used to draw a free
 * text box for every goal under «سطرك في الرسالة», and to decide the three typed fields from
 * `offers`, which is a fact about the GOAL rather than about the message it sends.
 *
 * For four of the six goals that free line reached nothing: `mkt_offer` is «لك خصم {{3}} على
 * {{4}}. ساري حتى {{5}}» — an amount, a service and a date, and nowhere at all for a sentence.
 * The owner typed one, pressed launch, and never saw his words again. Nothing failed.
 */
import { describe, expect, it } from 'vitest';
import { freeBlankLabel, hasBlank } from './Launch';

describe('a blank is drawn only where the message has one', () => {
  it('draws the typed blanks an offer declares, and no free box beside them', () => {
    const offer = { goal: 'service_offer', blanks: ['amount', 'catalogue', 'date'] };
    expect(hasBlank(offer, 'amount')).toBe(true);
    expect(hasBlank(offer, 'catalogue')).toBe(true);
    expect(hasBlank(offer, 'date')).toBe(true);
    // THE ONE THIS FINDING IS ABOUT. A free box here is a box whose contents reach nobody.
    expect(hasBlank(offer, 'owner')).toBe(false);
  });

  it('draws the free blank for the one goal whose content IS that blank', () => {
    const announce = { goal: 'announce', blanks: ['owner'] };
    expect(hasBlank(announce, 'owner')).toBe(true);
    // And nothing else: an announcement has no discount, no service and no end date.
    expect(hasBlank(announce, 'amount')).toBe(false);
    expect(hasBlank(announce, 'date')).toBe(false);
  });

  it('asks for nothing when the server declared nothing', () => {
    // A template we could not resolve — never seeded, still in review, switched off. Drawing a
    // box on that silence is how the wrong one appeared for four goals in the first place.
    expect(hasBlank({ goal: 'announce' }, 'owner')).toBe(false);
    expect(hasBlank({ goal: 'service_offer', blanks: [] }, 'amount')).toBe(false);
  });

  it('names the free blank by what it fills, never by where it lands', () => {
    // «سطرك في الرسالة» was a claim about placement, and it was false wherever there was no
    // `owner` slot. The label now names the CONTENT, which is true wherever the box is drawn.
    expect(freeBlankLabel('announce')).toBe('ما الجديد؟');
    expect(freeBlankLabel('announce')).not.toContain('سطرك');
  });
});
