/**
 * «متى نرسل» is a table with two filters — and a filter that finds nothing says which one did it.
 *
 * WHY IT STOPPED BEING A LIST OF CARDS. Thirteen rows, each a title, a sentence and a switch, is a
 * screen that answers «what messages exist» and refuses every other question. An owner arrives
 * with one of two: «أيّها مفعّل؟» and «أيّ التسويقية عندي؟» — the second being the class he is
 * legally answerable for — and both were answered by scanning the whole page with his eye, every
 * time. Tamam's decision: «الشاشة نفسها تسير جدول ويسير فيه فلاتر على أنواع الرسائل وأيضاً على
 * الحالات».
 *
 * WHAT THE TABLE MUST NOT COST: the «when». «بعد تسجيل الزيارة بعشر دقائق» is what makes a name
 * mean something to somebody reading it for the first time, so it stays under the title — a column
 * of bare names would be tidier and less useful.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

/** A row's title appears TWICE by design: once visibly, and once as the switch's accessible name —
 *  `sr-only`, because thirteen identical toggles are indistinguishable to a screen reader without
 *  it. So «is this row shown» is a COUNT, never a single-element lookup. */
const rows = (label: string) => screen.queryAllByText(label).length;

const REASONS = [
  { id: 'visit_recorded', label: 'سُجّلت زيارة', when: 'بعد عشر دقائق',
    cls: 'service', cls_label: 'خدمية', on: true, can_switch: true },
  { id: 'winback', label: 'استرجاع', when: 'بعد 90 يوماً',
    cls: 'marketing', cls_label: 'تسويقية', on: false, can_switch: true },
  { id: 'points_expiring', label: 'نقاطك تنتهي', when: 'قبل الانتهاء بأسبوع',
    cls: 'personal', cls_label: 'شخصية', on: true, can_switch: true },
];

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }) => {
      if (a.id === 'reminders.reasons') return { reasons: REASONS };
      return {};
    },
  };
});

const { MessagesScreen } = await import('./Messages');

afterEach(cleanup);

const session = {} as never;
const catalog = { services: [], unreachable: [] } as never;

function open() {
  // MessagesScreen now reads `useSearchParams` (the «أرسل رسالة رجوع» deep link from محلّي's
  // at-risk card) — it needs a router context even for a test that never touches the query string.
  return render(<MemoryRouter><MessagesScreen session={session} catalog={catalog} /></MemoryRouter>);
}

describe('«متى نرسل» — a table a question can be asked of', () => {
  it('shows every reason, with its class and its «when», before anything is filtered', async () => {
    open();
    await screen.findAllByText('سُجّلت زيارة');
    expect(rows('استرجاع')).toBeGreaterThan(0);
    // THE «WHEN» IS NOT DROPPED FOR TIDINESS.
    expect(screen.getByText('بعد عشر دقائق')).toBeTruthy();
  });

  it('narrows to one class when its pill is pressed', async () => {
    open();
    await screen.findAllByText('سُجّلت زيارة');
    fireEvent.click(screen.getByRole('button', { name: 'تسويقية' }));
    expect(rows('استرجاع')).toBeGreaterThan(0);
    // The one he is answerable for, alone — which is the whole reason this filter exists.
    expect(rows('سُجّلت زيارة')).toBe(0);
    expect(rows('نقاطك تنتهي')).toBe(0);
  });

  it('narrows to what is switched off', async () => {
    open();
    await screen.findAllByText('سُجّلت زيارة');
    fireEvent.click(screen.getByRole('button', { name: 'موقوفة' }));
    expect(rows('استرجاع')).toBeGreaterThan(0);
    expect(rows('سُجّلت زيارة')).toBe(0);
  });

  it('combines both, because that is the question people actually have', async () => {
    open();
    await screen.findAllByText('سُجّلت زيارة');
    fireEvent.click(screen.getByRole('button', { name: 'خدمية' }));
    fireEvent.click(screen.getByRole('button', { name: 'موقوفة' }));
    // A service message that is switched off: none here — and the screen says so rather than
    // showing an empty box under two pressed pills.
    expect(screen.getByText(/لا شيء بهذا الوصف/)).toBeTruthy();
  });

  it('says the state in a word, not only as a switch', async () => {
    open();
    await screen.findAllByText('سُجّلت زيارة');
    // A switch alone is readable to somebody watching for it and invisible to somebody scanning —
    // and «موقوفة» is exactly what the filter above promises to find.
    expect(screen.getAllByText('مفعّلة').length).toBeGreaterThan(0);
    expect(screen.getAllByText('موقوفة').length).toBeGreaterThan(0);
  });
});
