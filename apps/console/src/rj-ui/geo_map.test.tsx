import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { GeoMap } from './GeoMap';

afterEach(cleanup);

describe('rj-ui GeoMap', () => {
  it('says so honestly with no points, rather than drawing an empty box', () => {
    render(<GeoMap points={[]} />);
    expect(screen.getByText('لا مواقع لعرضها بعد.')).toBeTruthy();
  });

  it('names the count of points in the map itself', () => {
    render(<GeoMap points={[
      { id: 'p1', lat: 24.7, lng: 46.7, label: 'الرياض', group: 'نشِط' },
      { id: 'p2', lat: 21.5, lng: 39.2, label: 'جدّة', group: 'محتمل' },
    ]} />);
    expect(screen.getByLabelText('خريطة توزيع 2 موقعاً')).toBeTruthy();
  });

  it('shows a legend entry for every distinct group, once each', () => {
    render(<GeoMap points={[
      { id: 'p1', lat: 24.7, lng: 46.7, label: 'الرياض', group: 'نشِط' },
      { id: 'p2', lat: 24.6, lng: 46.6, label: 'الرياض 2', group: 'نشِط' },
      { id: 'p3', lat: 21.5, lng: 39.2, label: 'جدّة', group: 'محتمل' },
    ]} />);
    expect(screen.getByText('نشِط')).toBeTruthy();
    expect(screen.getByText('محتمل')).toBeTruthy();
  });

  it('shows no legend when no point carries a group', () => {
    render(<GeoMap points={[{ id: 'p1', lat: 24.7, lng: 46.7, label: 'الرياض' }]} />);
    expect(screen.queryByRole('list')).toBeFalsy();
  });
});
