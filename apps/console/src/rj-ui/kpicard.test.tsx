import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { KpiCard } from './KpiCard';

describe('rj-ui KpiCard', () => {
  it('renders the label, value and hint', () => {
    render(<KpiCard icon={<span aria-hidden>★</span>} label="عميل يجمع نقاطاً" value="42"
                     hint="ما وعدت به ولم يُصرف." testId="kpi1" />);
    expect(screen.getByTestId('kpi1')).toBeTruthy();
    expect(screen.getByText('عميل يجمع نقاطاً')).toBeTruthy();
    expect(screen.getByText('42')).toBeTruthy();
    expect(screen.getByText('ما وعدت به ولم يُصرف.')).toBeTruthy();
  });

  it('applies the accent tone to the value text when asked', () => {
    render(<KpiCard icon={<span aria-hidden>★</span>} label="نقطة" value="9" tone="accent" testId="kpi2" />);
    expect(screen.getByText('9').className).toContain('text-accent-on-soft');
  });

  it('omits the hint line when none is given', () => {
    render(<KpiCard icon={<span aria-hidden>★</span>} label="استبدال" value="3" testId="kpi3" />);
    expect(screen.queryByText(/وعدت/)).toBeNull();
  });
});
