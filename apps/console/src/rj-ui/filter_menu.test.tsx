import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { FilterMenu } from './FilterMenu';

const OPTIONS = [
  { value: 'a', label: 'صالونات' },
  { value: 'b', label: 'عيادات' },
  { value: 'c', label: 'مطاعم' },
];

describe('FilterMenu', () => {
  it('shows no count badge and no chips with nothing selected', () => {
    render(<FilterMenu label="القطاع" options={OPTIONS} selected={[]} onChange={vi.fn()} />);
    expect(screen.queryByText('مسح الكل')).toBeFalsy();
  });

  it('opens the menu and selecting an option calls onChange with it added', () => {
    const onChange = vi.fn();
    render(<FilterMenu label="القطاع" options={OPTIONS} selected={[]} onChange={onChange} />);
    fireEvent.click(screen.getByText('القطاع'));
    fireEvent.click(screen.getByText('صالونات'));
    expect(onChange).toHaveBeenCalledWith(['a']);
  });

  it('supports selecting more than one value at once', () => {
    const onChange = vi.fn();
    render(<FilterMenu label="القطاع" options={OPTIONS} selected={['a']} onChange={onChange} />);
    fireEvent.click(screen.getByText('القطاع'));
    fireEvent.click(screen.getByText('عيادات'));
    expect(onChange).toHaveBeenCalledWith(['a', 'b']);
  });

  it('renders a removable chip per selection, and removing one keeps the rest', () => {
    const onChange = vi.fn();
    render(<FilterMenu label="القطاع" options={OPTIONS} selected={['a', 'b']} onChange={onChange} />);
    expect(screen.getByText('صالونات')).toBeTruthy();
    expect(screen.getByText('عيادات')).toBeTruthy();
    fireEvent.click(screen.getByLabelText('إزالة صالونات'));
    expect(onChange).toHaveBeenCalledWith(['b']);
  });

  it('"مسح الكل" clears every selection at once', () => {
    const onChange = vi.fn();
    render(<FilterMenu label="القطاع" options={OPTIONS} selected={['a', 'b']} onChange={onChange} />);
    fireEvent.click(screen.getByText('مسح الكل'));
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it('closes on Escape', () => {
    render(<FilterMenu label="القطاع" options={OPTIONS} selected={[]} onChange={vi.fn()} />);
    fireEvent.click(screen.getByText('القطاع'));
    expect(screen.getByRole('listbox')).toBeTruthy();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('listbox')).toBeFalsy();
  });

  it('shows the count badge matching the number selected', () => {
    render(<FilterMenu label="القطاع" options={OPTIONS} selected={['a', 'b']} onChange={vi.fn()} />);
    expect(screen.getByText('2')).toBeTruthy();
  });

  it('only shows a search box once the option count crosses the threshold', () => {
    render(<FilterMenu label="القطاع" options={OPTIONS} selected={[]} onChange={vi.fn()} searchThreshold={2} />);
    fireEvent.click(screen.getByText('القطاع'));
    expect(screen.getByPlaceholderText('ابحث...')).toBeTruthy();
  });

  it('hides the search box below the threshold', () => {
    render(<FilterMenu label="القطاع" options={OPTIONS} selected={[]} onChange={vi.fn()} />);
    fireEvent.click(screen.getByText('القطاع'));
    expect(screen.queryByPlaceholderText('ابحث...')).toBeFalsy();
  });
});
