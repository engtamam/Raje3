/**
 * ط-4: «سطرك في الرسالة» promised his one free line would be IN the WhatsApp text. For an offer
 * goal that was never true — the approved offer templates compose their sentence from the amount,
 * the services and the date, with no `owner` slot in `fills` — so the line silently went nowhere.
 * It does reach the entitlement the till and his own offer page show back to him (أ-6); the label
 * must say that instead of promising a placement that never happens.
 */
import { describe, expect, it } from 'vitest';
import { ownerLineLabel } from './Launch';

describe('the one free line is named for where it actually lands', () => {
  it('names the message for a goal that is not an offer — the label was already true there', () => {
    expect(ownerLineLabel({ offers: false })).toBe('سطرك في الرسالة');
    expect(ownerLineLabel({})).toBe('سطرك في الرسالة');
  });

  it('names the till, not the message, for a goal that offers something', () => {
    // NOT «سطرك في الرسالة» — that is the claim ط-4 catches as false for these three goals.
    const label = ownerLineLabel({ offers: true });
    expect(label).not.toBe('سطرك في الرسالة');
    expect(label).toBe('سطرك عند الصندوق');
  });
});
