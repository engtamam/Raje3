import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { WaCarousel, type WaCarouselCard } from './WhatsAppPreview';

const CARDS: WaCarouselCard[] = [
  { id: 'c1', kind: 'service', name: 'قص شعر', priceMinor: 5000, buttonLabel: 'احجز الآن' },
  { id: 'c2', kind: 'package', name: 'باقة العناية', priceMinor: 12000, buttonLabel: 'احجز الآن' },
];

describe('WaCarousel', () => {
  it('renders the intro text and every card, each with its own real price', () => {
    render(<WaCarousel intro="شوف بعض خدماتنا:" cards={CARDS} />);
    expect(screen.getByText('شوف بعض خدماتنا:')).toBeTruthy();
    expect(screen.getByText(/قص شعر/)).toBeTruthy();
    expect(screen.getByText(/باقة العناية/)).toBeTruthy();
    // two cards → two "احجز الآن" buttons, one per card, never merged into one
    expect(screen.getAllByText('احجز الآن')).toHaveLength(2);
  });

  it('shows the swipe arrows only when there is more than one card to swipe between', () => {
    render(<WaCarousel cards={[CARDS[0]!]} />);
    expect(screen.queryByLabelText('البطاقة التالية')).toBeNull();

    render(<WaCarousel cards={CARDS} />);
    expect(screen.getByLabelText('البطاقة التالية')).toBeTruthy();
    expect(screen.getByLabelText('البطاقة السابقة')).toBeTruthy();
  });
});
