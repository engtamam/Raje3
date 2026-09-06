/**
 * «حد كلمات رسالة العميل» — how many words a customer's single WhatsApp message may be before the
 * assistant refuses it outright without ever calling the model. Absent entirely whenever
 * `operations.msg_word_limit` is missing from the catalogue (the feature's own kill switch hides
 * it this way, with no code path here that assumes it exists).
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

let callImpl: (session: unknown, a: { id: string }, body?: unknown) => Promise<unknown>;
let actionIds: Set<string>;

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) =>
      actionIds.has(id) ? { id, label: id, method: id.startsWith('operations.set_') ? 'PUT' : 'GET', path: `/${id}` } : undefined,
    call: async (session: unknown, a: { id: string }, body?: unknown) => callImpl(session, a, body),
  };
});

const { ShopPane } = await import('./AccountPanes');

afterEach(() => { cleanup(); });

const catalog = { services: [], unreachable: [] } as never;
const session = {} as never;

function withLimitActions(extra: string[] = []) {
  actionIds = new Set(['tenant.view_self', 'operations.msg_word_limit',
                       'operations.set_msg_word_limit', ...extra]);
}

describe('MsgWordLimitCard', () => {
  it('is absent entirely when operations.msg_word_limit is not in the catalogue (the kill switch)', async () => {
    actionIds = new Set(['tenant.view_self']);
    callImpl = async (_s, a) => (a.id === 'tenant.view_self' ? { id: 't1', name: 'محل الأناقة' } : {});
    render(<ShopPane session={session} catalog={catalog} />);
    await screen.findByText('محل الأناقة');
    expect(screen.queryByText('حد كلمات رسالة العميل')).toBeFalsy();
  });

  it('loads the existing limit into the field', async () => {
    withLimitActions();
    callImpl = async (_s, a) => {
      if (a.id === 'tenant.view_self') return { id: 't1', name: 'محل الأناقة' };
      if (a.id === 'operations.msg_word_limit') return { limit: 60 };
      return {};
    };
    render(<ShopPane session={session} catalog={catalog} />);
    const box = await screen.findByLabelText('حد كلمات رسالة العميل') as HTMLInputElement;
    await waitFor(() => expect(box.value).toBe('60'));
  });

  it('the save button stays disabled until the value actually changes', async () => {
    withLimitActions();
    callImpl = async (_s, a) => {
      if (a.id === 'tenant.view_self') return { id: 't1', name: 'محل الأناقة' };
      if (a.id === 'operations.msg_word_limit') return { limit: 100 };
      return {};
    };
    render(<ShopPane session={session} catalog={catalog} />);
    await screen.findByLabelText('حد كلمات رسالة العميل');
    const saveBtn = screen.getByText('حفظ').closest('button') as HTMLButtonElement;
    expect(saveBtn.disabled).toBe(true);
  });

  it('saving posts the draft limit and shows a confirmation', async () => {
    withLimitActions();
    let posted: unknown;
    callImpl = async (_s, a, body) => {
      if (a.id === 'tenant.view_self') return { id: 't1', name: 'محل الأناقة' };
      if (a.id === 'operations.msg_word_limit') return { limit: 100 };
      if (a.id === 'operations.set_msg_word_limit') { posted = body; return { limit: 60 }; }
      return {};
    };
    render(<ShopPane session={session} catalog={catalog} />);
    const box = await screen.findByLabelText('حد كلمات رسالة العميل');
    fireEvent.change(box, { target: { value: '60' } });
    fireEvent.click(screen.getByText('حفظ'));

    await screen.findByText('تم الحفظ.');
    expect(posted).toEqual({ limit: 60 });
  });

  it('refuses to save a value below the minimum, client-side', async () => {
    withLimitActions();
    callImpl = async (_s, a) => {
      if (a.id === 'tenant.view_self') return { id: 't1', name: 'محل الأناقة' };
      if (a.id === 'operations.msg_word_limit') return { limit: 100 };
      return {};
    };
    render(<ShopPane session={session} catalog={catalog} />);
    const box = await screen.findByLabelText('حد كلمات رسالة العميل');
    fireEvent.change(box, { target: { value: '5' } });

    await screen.findByText(/يجب أن تكون بين 20 و300/);
    const saveBtn = screen.getByText('حفظ').closest('button') as HTMLButtonElement;
    expect(saveBtn.disabled).toBe(true);
  });

  it('refuses to save a value above the maximum, client-side', async () => {
    withLimitActions();
    callImpl = async (_s, a) => {
      if (a.id === 'tenant.view_self') return { id: 't1', name: 'محل الأناقة' };
      if (a.id === 'operations.msg_word_limit') return { limit: 100 };
      return {};
    };
    render(<ShopPane session={session} catalog={catalog} />);
    const box = await screen.findByLabelText('حد كلمات رسالة العميل');
    fireEvent.change(box, { target: { value: '5000' } });

    await screen.findByText(/يجب أن تكون بين 20 و300/);
    const saveBtn = screen.getByText('حفظ').closest('button') as HTMLButtonElement;
    expect(saveBtn.disabled).toBe(true);
  });

  it('shows a read-only notice when the owner can read but not write', async () => {
    actionIds = new Set(['tenant.view_self', 'operations.msg_word_limit']);
    callImpl = async (_s, a) => {
      if (a.id === 'tenant.view_self') return { id: 't1', name: 'محل الأناقة' };
      if (a.id === 'operations.msg_word_limit') return { limit: 100 };
      return {};
    };
    render(<ShopPane session={session} catalog={catalog} />);
    await screen.findByText('حد كلمات رسالة العميل');
    await screen.findByText('لا تملك صلاحية تعديل هذا الحد.');
    expect(screen.queryByText('حفظ')).toBeFalsy();
  });
});
