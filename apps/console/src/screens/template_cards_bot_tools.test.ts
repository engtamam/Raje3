import { describe, expect, it } from 'vitest';
import { templateCards } from './Messages';

describe('templateCards — phase 3 bot-tool cards', () => {
  it('appends every bot tool card, tagged بوت, never mixed with auto/manual', () => {
    const cards = templateCards([], []);
    const botCards = cards.filter((c) => c.key.startsWith('bot:'));
    expect(botCards.length).toBeGreaterThan(0);
    for (const c of botCards) {
      expect(c.tags).toEqual(['bot']);
      expect(c.cls).toBe('bot');
      expect(c.reason).toBeUndefined();
      expect(c.goal).toBeUndefined();
      expect(c.botPreview).toBeDefined();
    }
  });

  it('marks the carousel and the booking-flow tools interactive, a plain-text one not', () => {
    const cards = templateCards([], []);
    const byId = (id: string) => cards.find((c) => c.key === `bot:${id}`);
    expect(byId('suggest_services_carousel')?.interactive).toBe(true);
    expect(byId('propose_booking')?.interactive).toBe(true);
    expect(byId('get_customer_points_summary')?.interactive).toBe(false);
  });

  it('never includes a card for the data-only lookup tool check_availability', () => {
    const cards = templateCards([], []);
    expect(cards.some((c) => c.key === 'bot:check_availability')).toBe(false);
  });
});
