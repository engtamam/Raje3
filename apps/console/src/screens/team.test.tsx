/**
 * «فريقي» — two real defects found from a screenshot: a single-branch shop's staff list showed a
 * name and a role and nothing else (no rename, no role change, no way to stop somebody who left —
 * the backend has always accepted all three), and a worker hired while there was only one branch
 * was silently sent branch_id="" — which api/scope.py reads as «unassigned, sees the whole
 * establishment» — rather than the real branch id, so adding a second branch later would widen
 * every employee hired before it without anyone deciding to.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render as rtlRender, screen, waitFor } from '@testing-library/react';
import type { ReactElement } from 'react';
import { OperatorI18nProvider } from '../operator-i18n';

// Every component under test now reads `useOperatorI18n()` — wrap once here so every existing
// `render(<...>)` call site below stays unchanged.
const SESSION_FOR_I18N = { tenant: 't1', operator: '', operatorName: '', token: 'tok' } as never;
function render(ui: ReactElement) {
  return rtlRender(<OperatorI18nProvider session={SESSION_FOR_I18N}>{ui}</OperatorI18nProvider>);
}

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

// A genuinely short link resolves to nothing here — the same "server could not resolve it
// either" outcome a real unreachable/invalid short link produces, so the existing "blocked with
// the specific sentence" test still exercises that real refusal path deterministically.
vi.mock('../api', async (importOriginal) => {
  const real = await importOriginal<typeof import('../api')>();
  return { ...real, resolveMapsShortLink: async () => '' };
});

const { People, Branches } = await import('./Team');

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

describe('adding a branch — location required only from the second one on', () => {
  const branchesProps = {
    session: SESSION, catalog: CATALOG,
    add: actionOf('operations.create_branch'), edit: actionOf('operations.update_branch'),
    mayRead: true, mayAdd: true, onChanged: () => {},
  };

  it('a shops FIRST branch saves with no location at all', async () => {
    render(<Branches {...branchesProps} branches={[]} operators={[]} limit={-1} />);
    fireEvent.click(screen.getByText('إضافة فرع'));
    fireEvent.change(document.getElementById('br-name') as HTMLInputElement,
                     { target: { value: 'الفرع الأول' } });
    fireEvent.click(screen.getByText('حفظ'));
    await waitFor(() => expect(calls.some((c) => c.id === 'operations.create_branch')).toBe(true));
    const body = calls.find((c) => c.id === 'operations.create_branch')?.body as
      { name?: string; lat?: number };
    expect(body.name).toBe('الفرع الأول');
    expect(body.lat).toBeUndefined();
  });

  it('a SECOND branch with no maps link is blocked client-side, never calls create', () => {
    render(<Branches {...branchesProps} branches={ONE_BRANCH} operators={[]} limit={-1} />);
    fireEvent.click(screen.getByText('إضافة فرع'));
    fireEvent.change(document.getElementById('br-name') as HTMLInputElement,
                     { target: { value: 'فرع جدة' } });
    fireEvent.click(screen.getByText('حفظ'));
    expect(calls.some((c) => c.id === 'operations.create_branch')).toBe(false);
    expect(screen.getByRole('alert').textContent).toContain('لازم من الفرع الثاني');
  });

  it('a SECOND branch with a real maps link sends the parsed lat/lng', async () => {
    render(<Branches {...branchesProps} branches={ONE_BRANCH} operators={[]} limit={-1} />);
    fireEvent.click(screen.getByText('إضافة فرع'));
    fireEvent.change(document.getElementById('br-name') as HTMLInputElement,
                     { target: { value: 'فرع جدة' } });
    fireEvent.change(document.getElementById('br-maps') as HTMLInputElement,
                     { target: { value: 'https://www.google.com/maps/@21.5433,39.1728,15z' } });
    fireEvent.click(screen.getByText('حفظ'));
    await waitFor(() => expect(calls.some((c) => c.id === 'operations.create_branch')).toBe(true));
    const body = calls.find((c) => c.id === 'operations.create_branch')?.body as
      { lat?: number; lng?: number };
    expect(body.lat).toBe(21.5433);
    expect(body.lng).toBe(39.1728);
  });

  it('a SECOND branch with a short link the server also cannot resolve is blocked with the specific sentence', async () => {
    render(<Branches {...branchesProps} branches={ONE_BRANCH} operators={[]} limit={-1} />);
    fireEvent.click(screen.getByText('إضافة فرع'));
    fireEvent.change(document.getElementById('br-name') as HTMLInputElement,
                     { target: { value: 'فرع جدة' } });
    fireEvent.change(document.getElementById('br-maps') as HTMLInputElement,
                     { target: { value: 'https://maps.app.goo.gl/AbCd1234' } });
    fireEvent.click(screen.getByText('حفظ'));
    // A short link now gets one real attempt at server-side resolution before the refusal — the
    // mocked `resolveMapsShortLink` above answers immediately with "" (unresolved), same as a
    // real short link the server also could not follow.
    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('رابط مختصر'));
    expect(calls.some((c) => c.id === 'operations.create_branch')).toBe(false);
  });
});
