import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { BarCompare } from './BarCompare';

afterEach(cleanup);

describe('rj-ui BarCompare', () => {
  it('says so with no items, rather than drawing an empty grid', () => {
    render(<BarCompare items={[]} />);
    expect(screen.getByText('لا بيانات للمقارنة بعد.')).toBeTruthy();
  });

  it('renders every label and its formatted value', () => {
    render(
      <BarCompare
        items={[{ label: 'فرع العليا', value: 120 }, { label: 'فرع النخيل', value: 45 }]}
        formatValue={(v) => `${v} زيارة`}
      />,
    );
    expect(screen.getByText('فرع العليا')).toBeTruthy();
    expect(screen.getByText('120 زيارة')).toBeTruthy();
    expect(screen.getByText('فرع النخيل')).toBeTruthy();
    expect(screen.getByText('45 زيارة')).toBeTruthy();
  });
});
