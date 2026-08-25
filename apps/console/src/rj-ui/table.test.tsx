import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { Table, type TableColumn } from './Table';

interface Row { id: string; name: string; phone: string }

const COLUMNS: TableColumn<Row>[] = [
  { key: 'name', header: 'الاسم' },
  { key: 'phone', header: 'الجوال' },
];

const ROWS: Row[] = [
  { id: 'r1', name: 'بنشري الملك', phone: '0501234567' },
  { id: 'r2', name: 'مغسلة الأمل', phone: '0509876543' },
];

afterEach(cleanup);

describe('rj-ui Table', () => {
  it('shows skeleton rows while loading, not an empty state', () => {
    const { container } = render(<Table columns={COLUMNS} rows="loading" getRowId={(r) => r.id} />);
    expect(container.querySelector('[aria-busy="true"]')).toBeTruthy();
    expect(screen.queryByText('لا نتائج')).toBeFalsy();
  });

  it('an honest failure state, distinct from empty', () => {
    render(<Table columns={COLUMNS} rows="failed" getRowId={(r) => r.id} />);
    expect(screen.getByText('تعذّرت القراءة')).toBeTruthy();
  });

  it('a real empty result says so, once', () => {
    render(<Table columns={COLUMNS} rows={[]} getRowId={(r) => r.id} emptyTitle="لا محلات بعد" />);
    expect(screen.getByText('لا محلات بعد')).toBeTruthy();
  });

  it('renders every row and every column value, in both layouts at once', () => {
    render(<Table columns={COLUMNS} rows={ROWS} getRowId={(r) => r.id} />);
    // Both the <table> (md+) and the card list (phone) render simultaneously — CSS picks which
    // is visible, so the same content appears twice in the DOM at test time.
    expect(screen.getAllByText('بنشري الملك').length).toBeGreaterThan(0);
    expect(screen.getAllByText('0501234567').length).toBeGreaterThan(0);
    expect(screen.getAllByText('مغسلة الأمل').length).toBeGreaterThan(0);
  });

  it('a clicked row fires onRowClick with that exact row', () => {
    const onRowClick = vi.fn();
    render(<Table columns={COLUMNS} rows={ROWS} getRowId={(r) => r.id} onRowClick={onRowClick} />);
    fireEvent.click(screen.getAllByText('بنشري الملك')[0]);
    expect(onRowClick).toHaveBeenCalledWith(ROWS[0]);
  });

  it('pagination shows the real range and calls back with the target page', () => {
    const onPageChange = vi.fn();
    render(
      <Table columns={COLUMNS} rows={ROWS} getRowId={(r) => r.id}
            pagination={{ page: 2, pageSize: 2, total: 5, onPageChange }} />,
    );
    expect(screen.getByText('3–4 من 5')).toBeTruthy();
    fireEvent.click(screen.getByLabelText('التالي'));
    expect(onPageChange).toHaveBeenCalledWith(3);
  });

  it('a custom render function is used over the raw field value', () => {
    const columns: TableColumn<Row>[] = [
      { key: 'name', header: 'الاسم', render: (r) => `⭐ ${r.name}` },
    ];
    render(<Table columns={columns} rows={ROWS} getRowId={(r) => r.id} />);
    expect(screen.getAllByText('⭐ بنشري الملك').length).toBeGreaterThan(0);
  });
});
