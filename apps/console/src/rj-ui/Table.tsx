/**
 * Our own Table — component #13, and the admin panel's own reason for existing: no table
 * component exists anywhere in this codebase yet (every list on the shop console is hand-built
 * per screen). Built for the admin panel's own needs (§١-٥ of the plan: customer lists,
 * invoices, audit log, coupons) but generic enough for `ActionRenderer`'s auto-rendered GET
 * actions too.
 *
 * TWO RENDERINGS, ONE DATA MODEL, PICKED BY CSS — same dual-layout idiom as `AdminNav.tsx`'s own
 * sidebar/bottom-bar split (`md:hidden`/`hidden md:flex`): a real `<table>` at `md` and up, and a
 * stack of cards below it. A wide table squeezed onto a phone is unreadable regardless of how
 * carefully the columns are chosen; a list of cards is the honest phone-first shape, not a
 * fallback.
 */
import type { ReactNode } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Skeleton } from './Skeleton';
import { EmptyState } from './EmptyState';
import { Button } from './Button';

export interface TableColumn<T> {
  key: string;
  header: ReactNode;
  /** Defaults to reading `row[key]` directly when omitted. */
  render?: (row: T) => ReactNode;
  className?: string;
  /** Hidden on the phone card layout — for columns only useful at a glance on a wide screen
   *  (an internal id, a raw timestamp already shown elsewhere as a relative label). */
  hideOnCard?: boolean;
}

export interface TablePagination {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}

export interface TableProps<T> {
  columns: TableColumn<T>[];
  rows: T[] | 'loading' | 'failed';
  getRowId: (row: T) => string;
  onRowClick?: (row: T) => void;
  emptyTitle?: ReactNode;
  emptyDescription?: ReactNode;
  failedTitle?: ReactNode;
  pagination?: TablePagination;
  /** Rows shown while `rows === 'loading'`. */
  skeletonRows?: number;
}

export function Table<T>({
  columns, rows, getRowId, onRowClick,
  emptyTitle = 'لا نتائج', emptyDescription,
  failedTitle = 'تعذّرت القراءة',
  pagination, skeletonRows = 5,
}: TableProps<T>) {
  if (rows === 'loading') {
    return (
      <div className="flex flex-col gap-2" aria-busy="true">
        {Array.from({ length: skeletonRows }, (_, i) => (
          <Skeleton key={i} height={48} radius="md" />
        ))}
      </div>
    );
  }

  if (rows === 'failed') {
    return <EmptyState title={failedTitle} />;
  }

  if (rows.length === 0) {
    return <EmptyState title={emptyTitle} description={emptyDescription} />;
  }

  const cell = (col: TableColumn<T>, row: T): ReactNode =>
    col.render ? col.render(row) : String((row as Record<string, unknown>)[col.key] ?? '');

  return (
    <div className="flex flex-col gap-3">
      {/* DESKTOP/TABLET — a real table, md and up. */}
      <div className="hidden overflow-x-auto rounded-card border border-border-subtle md:block">
        <table className="w-full min-w-full text-start text-sm">
          <thead>
            <tr className="border-b border-border-subtle bg-surface-1 text-text-secondary">
              {columns.map((col) => (
                <th key={col.key} className={`px-3 py-2.5 text-start font-medium ${col.className ?? ''}`}>
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={getRowId(row)}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                className={`border-b border-border-subtle last:border-0 ${
                  onRowClick ? 'cursor-pointer hover:bg-surface-1' : ''
                }`}
              >
                {columns.map((col) => (
                  <td key={col.key} className={`px-3 py-2.5 text-text-primary ${col.className ?? ''}`}>
                    {cell(col, row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* PHONE — a stack of cards, below md. Every column becomes a label:value row, unless
          marked hideOnCard (a column only meaningful at a glance in a wide row). */}
      <ul className="flex flex-col gap-2 md:hidden">
        {rows.map((row) => {
          const visible = columns.filter((c) => !c.hideOnCard);
          return (
            <li key={getRowId(row)}>
              <button
                type="button"
                disabled={!onRowClick}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                className={`flex w-full flex-col gap-1.5 rounded-card border border-border-subtle bg-surface-1 p-3 text-start ${
                  onRowClick ? 'cursor-pointer active:bg-surface-2' : ''
                }`}
              >
                {visible.map((col) => (
                  <div key={col.key} className="flex items-center justify-between gap-3 text-sm">
                    <span className="text-text-secondary">{col.header}</span>
                    <span className="text-text-primary">{cell(col, row)}</span>
                  </div>
                ))}
              </button>
            </li>
          );
        })}
      </ul>

      {pagination ? <TablePager {...pagination} /> : null}
    </div>
  );
}

function TablePager({ page, pageSize, total, onPageChange }: TablePagination) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);
  return (
    <div className="flex items-center justify-between gap-3 text-sm text-text-secondary">
      <span>{from}–{to} من {total}</span>
      <div className="flex items-center gap-1">
        <Button variant="ghost" size="icon" aria-label="السابق" disabled={page <= 1}
               onClick={() => onPageChange(page - 1)}>
          <ChevronRight size={16} />
        </Button>
        <span className="tabular-nums">{page} / {pageCount}</span>
        <Button variant="ghost" size="icon" aria-label="التالي" disabled={page >= pageCount}
               onClick={() => onPageChange(page + 1)}>
          <ChevronLeft size={16} />
        </Button>
      </div>
    </div>
  );
}
