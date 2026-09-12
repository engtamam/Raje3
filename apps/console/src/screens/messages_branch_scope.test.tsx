/**
 * «الحملات»'s delivery log must default to the rail's own «الفرع المعروض» — an owner who already
 * narrowed the whole console to one branch must not land here reading every branch's log by
 * default (BranchSwitch.tsx's own «comparing two different shops» warning), and switching the
 * rail's branch while already on this screen must re-narrow the log the same way, live.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { DENIED } from '../loading';
import { OperatorI18nProvider } from '../operator-i18n';

const logCalls: Array<{ branch_id?: string }> = [];

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }, body?: { branch_id?: string }) => {
      if (a.id === 'reminders.log') {
        logCalls.push({ branch_id: body?.branch_id });
        return { log: [] };
      }
      if (a.id === 'operations.list_branches') {
        return { branches: [{ id: 'b1', name: 'فرع 1' }, { id: 'b2', name: 'فرع 2' }] };
      }
      return {};
    },
  };
});

const { MessagesScreen } = await import('./Messages');

afterEach(() => {
  cleanup();
  logCalls.length = 0;
});

const session = {} as never;
const catalog = { services: [], unreachable: [] } as never;

function openLogTab(branch?: string) {
  const result = render(
    <OperatorI18nProvider session={session}>
      <MemoryRouter initialEntries={['/']}>
        <MessagesScreen session={session} catalog={catalog} owned={DENIED} branch={branch} />
      </MemoryRouter>
    </OperatorI18nProvider>,
  );
  // `?tab=log` is never read on mount (only `?tab=campaigns` is special-cased) — a real click on
  // the tab itself is what actually opens it, same as an owner would.
  fireEvent.click(screen.getByRole('radio', { name: 'ماذا حدث؟' }));
  return result;
}

describe('«الحملات»\'s log tab respects the rail\'s own branch scope', () => {
  it('defaults the log filter to the rail\'s narrowed branch, not "كل الفروع"', async () => {
    openLogTab('b1');
    await screen.findByText('لم تخرج');   // the tab has rendered and its own effect has run
    expect(logCalls.some((c) => c.branch_id === 'b1')).toBe(true);
    expect(logCalls.some((c) => c.branch_id === undefined)).toBe(false);
  });

  it('shows every branch\'s log when the rail itself is on "كل الفروع"', async () => {
    openLogTab('');
    await screen.findByText('لم تخرج');
    expect(logCalls.some((c) => c.branch_id === undefined)).toBe(true);
  });

  it('still lets him widen back to every branch locally, even while the rail is narrowed', async () => {
    openLogTab('b1');
    await screen.findByLabelText('تصفية السجل حسب الفرع');
    const select = screen.getByLabelText('تصفية السجل حسب الفرع') as HTMLSelectElement;
    expect(select.value).toBe('b1');   // starts following the rail
  });
});
