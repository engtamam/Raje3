import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Button } from './Button';

describe('rj-ui Button', () => {
  it('renders its children and fires onClick', () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>احفظ</Button>);
    fireEvent.click(screen.getByText('احفظ'));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('does not fire onClick while disabled', () => {
    const onClick = vi.fn();
    render(<Button disabled onClick={onClick}>احفظ</Button>);
    fireEvent.click(screen.getByText('احفظ'));
    expect(onClick).not.toHaveBeenCalled();
  });

  it('defaults to the solid variant and md size, both overridable', () => {
    render(<Button>افتراضي</Button>);
    expect(screen.getByText('افتراضي').className).toContain('bg-accent');

    render(<Button variant="ghost" size="sm">صغير</Button>);
    // A real resting shape, not bare coloured text (2026-08-22 fix — see the variant's own comment).
    expect(screen.getByText('صغير').className).toContain('bg-surface-2');
  });

  it('forwards a ref to the underlying <button>', () => {
    let el: HTMLButtonElement | null = null;
    render(<Button ref={(r) => { el = r; }}>مرجع</Button>);
    expect(el).toBeInstanceOf(HTMLButtonElement);
  });
});
