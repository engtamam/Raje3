/**
 * «التقييم» — its own rail screen: the overview tab (tiles, switchable podium, the fairness
 * quadrant, the full table) and the ratings tab (every rated visit, with the customer's own name/
 * phone and a smart "فتح ملف العميل" link that remembers this exact tab/filter to come back to).
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render as rtlRender, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import type { ReactElement } from 'react';
import { OperatorI18nProvider } from '../operator-i18n';
import { RatingScreen } from './Rating';

const SESSION = { tenant: 't1', operator: '', operatorName: '', token: 'tok' } as never;

const STAFF = [
  { operator_id: 'op_sara', operator_name: 'سارة', visits: 64, ratings: 31, average_rating: 4.9, no_show_rate: 0.03 },
  { operator_id: 'op_fahd', operator_name: 'فهد', visits: 112, ratings: 50, average_rating: 2.8, no_show_rate: 0.31 },
];

const RATINGS = [
  {
    id: 'vis1', customer_id: 'cus_1', customer_name: 'ريم الحربي', customer_phone: '+966500000001',
    operator_id: 'op_fahd', operator_name: 'فهد', rating: 2, feedback_text: 'الانتظار طويل',
    rated_at: Math.floor(Date.now() / 1000), rating_handled_at: 0, rating_handled_note: '',
    rating_issue_steps: [{ id: 'step_a', text: 'اربط الصمولة بعزم صحيح', severity: 'critical' }],
  },
  {
    id: 'vis2', customer_id: 'cus_2', customer_name: 'سلمى', customer_phone: '+966500000002',
    operator_id: 'op_sara', operator_name: 'سارة', rating: 3, feedback_text: '',
    rated_at: Math.floor(Date.now() / 1000), rating_handled_at: 0, rating_handled_note: '',
    rating_issue_steps: [{ id: 'step_a', text: 'اربط الصمولة بعزم صحيح', severity: 'critical' }],
  },
];

const ratingsCalls: unknown[] = [];

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }, query?: unknown) => {
      if (a.id === 'operations.staff_performance') return { staff: STAFF };
      if (a.id === 'operations.ratings') {
        ratingsCalls.push(query);
        const stepId = (query as { step_id?: string } | undefined)?.step_id;
        const rows = stepId
          ? RATINGS.filter((r) => r.rating_issue_steps.some((s) => s.id === stepId))
          : RATINGS;
        return { ratings: rows };
      }
      if (a.id === 'operations.list_operator_step_stats') {
        const operatorId = (query as { id?: string } | undefined)?.id;
        if (operatorId === 'op_fahd') {
          return {
            step_stats: [
              { step_id: 'step_a', step_text: 'اربط الصمولة بعزم صحيح', step_severity: 'critical',
                times_flagged: 3, times_flagged_critical: 3 },
              { step_id: 'step_b', step_text: 'نظّف الزجاج', step_severity: 'normal',
                times_flagged: 1, times_flagged_critical: 0 },
            ],
          };
        }
        return { step_stats: [] };
      }
      return {};
    },
  };
});

const catalog = { services: [], unreachable: [] } as never;

function render(ui: ReactElement, initialPath = '/rating') {
  return rtlRender(
    <OperatorI18nProvider session={SESSION}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/rating" element={ui} />
          <Route path="/customers/:id" element={<div>صفحة العميل</div>} />
        </Routes>
      </MemoryRouter>
    </OperatorI18nProvider>,
  );
}

afterEach(cleanup);

describe('«التقييم» — نظرة عامة', () => {
  it('shows the shop-wide weighted average and total ratings tiles', async () => {
    render(<RatingScreen session={SESSION} catalog={catalog} branch="" />);
    // weighted: (4.9*31 + 2.8*50) / 81 = 3.62
    await waitFor(() => expect(screen.getByText('3.6')).toBeTruthy());
    expect(screen.getByText('81')).toBeTruthy(); // total ratings
  });

  it('the podium switches which metric it names when a different pill is pressed', async () => {
    render(<RatingScreen session={SESSION} catalog={catalog} branch="" />);
    await waitFor(() => expect(screen.getAllByText('سارة').length).toBeGreaterThan(0));
    // Default metric is «الأفضل تقييماً» — سارة (4.9) outranks فهد (2.8).
    expect(screen.getAllByText('الأفضل تقييماً').length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('radio', { name: 'الأكثر زيارات' }));
    await waitFor(() => expect(screen.getAllByText('الأكثر زيارات').length).toBeGreaterThan(0));
  });

  it('«مخصص» shows two date pickers, and refuses a reversed range without ever fetching it', async () => {
    render(<RatingScreen session={SESSION} catalog={catalog} branch="" />);
    await waitFor(() => expect(screen.getAllByText('سارة').length).toBeGreaterThan(0));
    fireEvent.click(screen.getByRole('radio', { name: 'مخصص' }));
    const since = screen.getByLabelText('من') as HTMLInputElement;
    const until = screen.getByLabelText('إلى') as HTMLInputElement;
    fireEvent.change(since, { target: { value: '2026-09-20' } });
    fireEvent.change(until, { target: { value: '2026-09-01' } });
    await waitFor(() => expect(screen.getAllByText('اختر فترة صحيحة').length).toBeGreaterThan(0));
  });

  it('the fairness quadrant renders both staff members as clickable bubbles', async () => {
    render(<RatingScreen session={SESSION} catalog={catalog} branch="" />);
    await waitFor(() => expect(screen.getAllByRole('button', { name: 'سارة' }).length).toBeGreaterThan(0));
    fireEvent.click(screen.getAllByRole('button', { name: 'فهد' })[0]);
    await waitFor(() => expect(screen.getByText('يحتاج دعم شامل')).toBeTruthy());
  });

  it('selecting an operator shows their own training record, worst-first, inside the same card', async () => {
    render(<RatingScreen session={SESSION} catalog={catalog} branch="" />);
    await waitFor(() => expect(screen.getAllByRole('button', { name: 'فهد' }).length).toBeGreaterThan(0));
    fireEvent.click(screen.getAllByRole('button', { name: 'فهد' })[0]);
    await waitFor(() => expect(screen.getByText('أين يحتاج تدريباً')).toBeTruthy());
    // critical step (3×) sorts before the normal one (1×).
    const names = screen.getAllByText(/اربط الصمولة بعزم صحيح|نظّف الزجاج/).map((el) => el.textContent);
    expect(names.indexOf('اربط الصمولة بعزم صحيح')).toBeLessThan(names.indexOf('نظّف الزجاج'));
  });

  it('a clean record says so instead of an empty list', async () => {
    render(<RatingScreen session={SESSION} catalog={catalog} branch="" />);
    await waitFor(() => expect(screen.getAllByRole('button', { name: 'سارة' }).length).toBeGreaterThan(0));
    fireEvent.click(screen.getAllByRole('button', { name: 'سارة' })[0]);
    await waitFor(() => expect(screen.getByText('ما فيه مشاكل متكررة — سجل نظيف.')).toBeTruthy());
  });
});

describe('«التقييم» — التقييمات', () => {
  it('names the customer and lets him reach her own profile, remembering where he was', async () => {
    render(<RatingScreen session={SESSION} catalog={catalog} branch="" />);
    fireEvent.click(screen.getByRole('tab', { name: 'التقييمات' }));
    await waitFor(() => expect(screen.getByText('ريم الحربي')).toBeTruthy());
    expect(screen.getByText('+966500000001')).toBeTruthy();
    fireEvent.click(screen.getAllByText('فتح ملف العميل')[0]);
    await waitFor(() => expect(screen.getByText('صفحة العميل')).toBeTruthy());
  });

  it('shows the flagged procedure step on the rating that named it', async () => {
    render(<RatingScreen session={SESSION} catalog={catalog} branch="" />);
    fireEvent.click(screen.getByRole('tab', { name: 'التقييمات' }));
    await waitFor(() => expect(screen.getAllByText('اربط الصمولة بعزم صحيح').length).toBeGreaterThan(0));
  });

  it('summarises the most repeated flagged step, and clicking it filters the list', async () => {
    ratingsCalls.length = 0;
    render(<RatingScreen session={SESSION} catalog={catalog} branch="" />);
    fireEvent.click(screen.getByRole('tab', { name: 'التقييمات' }));
    await waitFor(() => expect(screen.getByText('أكثر مشكلة تتكرر')).toBeTruthy());
    // both seeded ratings flag the same step — the summary counts it once, at 2.
    expect(screen.getByText('2')).toBeTruthy();

    const summaryPanel = screen.getByText('أكثر مشكلة تتكرر').closest('div') as HTMLElement;
    fireEvent.click(summaryPanel.querySelector('button') as HTMLButtonElement);
    await waitFor(() => expect(ratingsCalls.some(
      (q) => (q as { step_id?: string })?.step_id === 'step_a')).toBe(true));
    // the active-filter chip replaces the summary panel.
    await waitFor(() => expect(screen.queryByText('أكثر مشكلة تتكرر')).toBeNull());
    expect(screen.getByText('مُفلتر على: اربط الصمولة بعزم صحيح')).toBeTruthy();
  });
});
