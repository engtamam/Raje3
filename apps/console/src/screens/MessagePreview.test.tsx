/**
 * The Bubble's button footer — the visual gap this closes: nothing in the console rendered a
 * WhatsApp button/Flow trigger before, so an owner deciding on a wording had to imagine it.
 */
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Bubble } from './MessagePreview';

describe('Bubble button footer', () => {
  it('renders nothing extra when the message carries no button', () => {
    render(<Bubble text="مرحباً بك" caption="ودّية" />);
    expect(screen.queryByText(/افتح|احجز/)).not.toBeTruthy();
  });

  it('renders a flow button with the Flow icon, not the link icon', () => {
    render(<Bubble text="احجز موعدك الآن" caption="ودّية"
                   buttons={[{ label: 'احجز موعدك', kind: 'flow' }]} />);
    expect(screen.getByText('احجز موعدك')).toBeTruthy();
  });

  it('renders a url button distinctly from a flow button', () => {
    render(<Bubble text="نتطلع لزيارتك" caption="ودّية"
                   buttons={[{ label: 'زر موقعنا', kind: 'url' }]} />);
    expect(screen.getByText('زر موقعنا')).toBeTruthy();
  });

  it('renders every button in a multi-button message, each on its own row', () => {
    render(<Bubble text="اختر ما يناسبك" caption="ودّية"
                   buttons={[{ label: 'احجز الآن', kind: 'flow' },
                             { label: 'تواصل معنا', kind: 'url' }]} />);
    expect(screen.getByText('احجز الآن')).toBeTruthy();
    expect(screen.getByText('تواصل معنا')).toBeTruthy();
  });

  it('still renders the message text and caption unchanged alongside a button', () => {
    render(<Bubble text="يا هلا بك" caption="نصّك"
                   buttons={[{ label: 'احجز الآن', kind: 'flow' }]} />);
    expect(screen.getByText('يا هلا بك')).toBeTruthy();
    expect(screen.getByText('نصّك')).toBeTruthy();
  });
});
