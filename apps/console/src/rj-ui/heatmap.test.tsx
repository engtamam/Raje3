import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Heatmap } from './Heatmap';

afterEach(cleanup);

describe('rj-ui Heatmap', () => {
  it('says so with no rows/cols, rather than drawing an empty grid', () => {
    render(<Heatmap rows={[]} cols={[]} cells={[]} />);
    expect(screen.getByText('لا بيانات كافية بعد.')).toBeTruthy();
  });

  it('labels every row and column axis', () => {
    render(
      <Heatmap
        rows={['السبت', 'الأحد']}
        cols={['صباحاً', 'مساءً']}
        cells={[{ row: 'السبت', col: 'مساءً', value: 40 }]}
      />,
    );
    expect(screen.getByText('السبت')).toBeTruthy();
    expect(screen.getByText('الأحد')).toBeTruthy();
    expect(screen.getByText('صباحاً')).toBeTruthy();
    expect(screen.getByText('مساءً')).toBeTruthy();
  });
});
