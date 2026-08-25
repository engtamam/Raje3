import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { AreaTrend } from './AreaTrend';

afterEach(cleanup);

describe('rj-ui AreaTrend', () => {
  it('says so honestly with fewer than two real points, rather than drawing a broken line', () => {
    render(<AreaTrend points={[{ label: 'يناير', value: 10 }, { label: 'فبراير', value: null }]} />);
    expect(screen.getByText('لا بيانات كافية لرسم اتجاه بعد.')).toBeTruthy();
  });

  it('labels both ends and the newest real value', () => {
    render(<AreaTrend
      points={[{ label: 'يناير', value: 10 }, { label: 'فبراير', value: 15 }, { label: 'مارس', value: 22 }]}
      formatValue={(v) => `${v}%`}
    />);
    expect(screen.getByText('يناير')).toBeTruthy();
    expect(screen.getByText('مارس')).toBeTruthy();
    expect(screen.getByText('22%')).toBeTruthy();
  });
});
