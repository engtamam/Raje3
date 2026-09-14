import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { TierLadder } from './TierLadder';

describe('rj-ui TierLadder', () => {
  it('renders one rung per tier, with its own label', () => {
    render(<TierLadder testId="ladder1" rungs={[
      { label: '10%', done: true },
      { label: '20%', done: true, current: true },
      { label: '30%', done: false },
    ]} />);
    expect(screen.getByTestId('ladder1')).toBeTruthy();
    expect(screen.getByText('10%')).toBeTruthy();
    expect(screen.getByText('20%')).toBeTruthy();
    expect(screen.getByText('30%')).toBeTruthy();
  });

  it('renders nothing for an empty ladder rather than a bare row', () => {
    const { container } = render(<TierLadder rungs={[]} />);
    expect(container.firstChild).toBeNull();
  });
});
