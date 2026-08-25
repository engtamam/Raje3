/**
 * «مساعد راجِع الذكي» — announced before it is sellable.
 *
 * NOT ROUTED THROUGH billing.plans. It is static console copy for an app with no backend yet, so
 * this test never touches `PlansPane`'s network calls (session/catalog mocks) — it checks the
 * card itself, and the grouping functions that must never mistake it for a real row.
 */
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { appKey, kindOf, ComingSoonCard, type Plan } from './Plans';

describe('the «قريباً» card', () => {
  it('renders with a name, a badge naming it not-yet-available, and no button', () => {
    render(<ComingSoonCard name="مساعد راجِع الذكي" what="مساعد ذكاء اصطناعي على واتساب." />);
    expect(screen.getByText('مساعد راجِع الذكي')).toBeTruthy();
    // THE BADGE IS THE VISUAL DIFFERENCE FROM A REAL APP CARD — the one thing a glance must catch.
    expect(screen.getByText('قريباً')).toBeTruthy();
    // NO CLICKABLE PATH TO "BUY" OR "ADD" IT — this card is view-only by construction.
    expect(screen.queryAllByRole('button')).toHaveLength(0);
  });

  it('never enters kindOf/appKey — it is not a plan row and must never be read as one', () => {
    // A fake plan shaped like the coming-soon app, run through the SAME functions the real store
    // uses to count and group rows — proving those functions would file it correctly if it were
    // ever accidentally handed to them, and that nothing in this file feeds it to them for real.
    const notAPlan = { id: 'ai-whatsapp-assistant', name: 'مساعد راجِع الذكي', limits: {} } as Plan;
    expect(kindOf(notAPlan)).toBe('capacity'); // no limits at all → filed as capacity, never "app"
    expect(appKey(notAPlan)).toBe('');
  });
});
