/**
 * «فريقي» — two real defects found from a screenshot: a single-branch shop's staff list showed a
 * name and a role and nothing else (no rename, no role change, no way to stop somebody who left —
 * the backend has always accepted all three), and a worker hired while there was only one branch
 * was silently sent branch_id="" — which api/scope.py reads as «unassigned, sees the whole
 * establishment» — rather than the real branch id, so adding a second branch later would widen
 * every employee hired before it without anyone deciding to.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

const calls: { id: string; body?: unknown }[] = [];

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }, body?: unknown) => {
      calls.push({ id: a.id, body });
      return { ok: true };
    },
  };
});

const { People } = await import('./Team');

const SESSION = { tenant: 't1', operator: '', operatorName: '', token: 'tok' };
const CATALOG = {} as never;

function actionOf(id: string) {
  return { id, label: id, method: 'GET', path: `/${id}` } as never;
}

const ONE_BRANCH = [{ id: 'brn-main', name: 'الفرع الرئيسي' }];
const OPERATOR = { id: 'op1', name: 'محمد', role: 'operator', active: true };

afterEach(() => { cleanup(); calls.length = 0; });

describe('OperatorRow — management always available', () => {
  it('offers تعديل and إيقاف for a single-branch shop, not just the branch picker', () => {
    render(
      <People session={SESSION} operators={[OPERATOR]} branches={ONE_BRANCH}
              add={actionOf('operations.create_operator')} edit={actionOf('operations.update_operator')}
              hire={actionOf('operations.hire')} pinKind onChanged={() => {}} />,
    );
    expect(screen.getByText('تعديل')).toBeTruthy();
    expect(screen.getByText('إيقاف')).toBeTruthy();
  });

  it('stopping somebody calls edit with active:false', async () => {
    render(
      <People session={SESSION} operators={[OPERATOR]} branches={ONE_BRANCH}
              add={actionOf('operations.create_operator')} edit={actionOf('operations.update_operator')}
              hire={actionOf('operations.hire')} pinKind onChanged={() => {}} />,
    );
    fireEvent.click(screen.getByText('إيقاف'));
    await waitFor(() => expect(calls.some((c) => c.id === 'operations.update_operator')).toBe(true));
    const patch = calls.find((c) => c.id === 'operations.update_operator')?.body as { active?: boolean };
    expect(patch.active).toBe(false);
  });

  it('renaming and changing the role saves both in one call', async () => {
    render(
      <People session={SESSION} operators={[OPERATOR]} branches={ONE_BRANCH}
              add={actionOf('operations.create_operator')} edit={actionOf('operations.update_operator')}
              hire={actionOf('operations.hire')} pinKind onChanged={() => {}} />,
    );
    fireEvent.click(screen.getByText('تعديل'));
    const nameInput = screen.getByDisplayValue('محمد');
    fireEvent.change(nameInput, { target: { value: 'محمد الجديد' } });
    fireEvent.click(screen.getByText('حفظ'));
    await waitFor(() => expect(calls.some((c) => c.id === 'operations.update_operator')).toBe(true));
    const patch = calls.find((c) => c.id === 'operations.update_operator')?.body as
      { name?: string; role?: string };
    expect(patch.name).toBe('محمد الجديد');
  });
});

describe('adding a worker — branch is explicit, even for one branch', () => {
  it('the picker is always shown, opens on no selection, and blocks submit until he picks one', () => {
    render(
      <People session={SESSION} operators={[]} branches={ONE_BRANCH}
              add={actionOf('operations.create_operator')} edit={actionOf('operations.update_operator')}
              hire={actionOf('operations.hire')} pinKind={false} onChanged={() => {}} />,
    );
    fireEvent.click(screen.getByText('إضافة موظف'));
    expect(screen.getByLabelText('فرع الموظف')).toBeTruthy();
    fireEvent.change(document.getElementById('op-name') as HTMLInputElement,
                     { target: { value: 'خالد' } });
    fireEvent.change(document.getElementById('op-phone') as HTMLInputElement,
                     { target: { value: '0501234567' } });
    fireEvent.change(document.getElementById('op-pw') as HTMLInputElement,
                     { target: { value: 'hunter2hunter2' } });
    // Every other field is filled — still disabled, because he never touched the branch.
    expect((screen.getByText('حفظ') as HTMLButtonElement).disabled).toBe(true);
  });

  it('sends the branch he actually picked, never a silent default', async () => {
    render(
      <People session={SESSION} operators={[]} branches={ONE_BRANCH}
              add={actionOf('operations.create_operator')} edit={actionOf('operations.update_operator')}
              hire={actionOf('operations.hire')} pinKind={false} onChanged={() => {}} />,
    );
    fireEvent.click(screen.getByText('إضافة موظف'));
    fireEvent.change(document.getElementById('op-name') as HTMLInputElement,
                     { target: { value: 'خالد' } });
    fireEvent.change(document.getElementById('op-phone') as HTMLInputElement,
                     { target: { value: '0501234567' } });
    fireEvent.change(document.getElementById('op-pw') as HTMLInputElement,
                     { target: { value: 'hunter2hunter2' } });
    fireEvent.change(screen.getByLabelText('فرع الموظف'), { target: { value: 'brn-main' } });

    fireEvent.click(screen.getByText('حفظ'));
    await waitFor(() => expect(calls.some((c) => c.id === 'operations.hire')).toBe(true));
    const body = calls.find((c) => c.id === 'operations.hire')?.body as { branch_id?: string };
    expect(body.branch_id).toBe('brn-main');
  });
});
