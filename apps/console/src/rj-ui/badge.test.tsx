import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Badge } from './Badge';

describe('rj-ui Badge', () => {
  it('renders its children', () => {
    render(<Badge>أوقف التسويق</Badge>);
    expect(screen.getByText('أوقف التسويق')).toBeTruthy();
  });

  it('defaults to the neutral tone, and a different tone is overridable', () => {
    render(<Badge>افتراضي</Badge>);
    expect(screen.getByText('افتراضي').className).toContain('bg-surface-2');

    render(<Badge tone="danger">خطر</Badge>);
    expect(screen.getByText('خطر').className).toContain('bg-danger-soft');
  });
});
