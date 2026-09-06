/**
 * «ملاحظات المساعد الذكي عبر واتساب» — the shop owner's own free-text instructions to the
 * WhatsApp AI assistant, on «منشأتي». Explicit save button (not autosave-on-blur — see the
 * card's own comment), a live character counter, and absent entirely whenever
 * `operations.ai_notes` is missing from the catalogue (the feature's own kill switch hides it
 * this way, with no code path here that assumes it exists).
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

function withNotesActions(extra: string[] = []) {
  actionIds = new Set(['tenant.view_self', 'operations.ai_notes', 'operations.set_ai_notes', ...extra]);
}

describe('AiNotesCard', () => {
  it('is absent entirely when operations.ai_notes is not in the catalogue (the kill switch)', async () => {
    actionIds = new Set(['tenant.view_self']);
    callImpl = async (_s, a) => (a.id === 'tenant.view_self' ? { id: 't1', name: 'محل الأناقة' } : {});
    render(<ShopPane session={session} catalog={catalog} />);
    await screen.findByText('محل الأناقة');
    expect(screen.queryByText('ملاحظات المساعد الذكي عبر واتساب')).toBeFalsy();
  });

  it('loads existing notes into the textarea', async () => {
    withNotesActions();
    callImpl = async (_s, a) => {
      if (a.id === 'tenant.view_self') return { id: 't1', name: 'محل الأناقة' };
      if (a.id === 'operations.ai_notes') return { text: 'نفتح من السبت للخميس' };
      return {};
    };
    render(<ShopPane session={session} catalog={catalog} />);
    const box = await screen.findByLabelText('ملاحظات المساعد الذكي عبر واتساب') as HTMLTextAreaElement;
    await waitFor(() => expect(box.value).toBe('نفتح من السبت للخميس'));
  });

  it('the save button stays disabled until the text actually changes', async () => {
    withNotesActions();
    callImpl = async (_s, a) => {
      if (a.id === 'tenant.view_self') return { id: 't1', name: 'محل الأناقة' };
      if (a.id === 'operations.ai_notes') return { text: 'نص أصلي' };
      return {};
    };
    render(<ShopPane session={session} catalog={catalog} />);
    await screen.findByDisplayValue('نص أصلي');
    const saveBtn = screen.getByText('حفظ').closest('button') as HTMLButtonElement;
    expect(saveBtn.disabled).toBe(true);
  });

  it('saving posts the draft text and shows a confirmation', async () => {
    withNotesActions();
    let posted: unknown;
    callImpl = async (_s, a, body) => {
      if (a.id === 'tenant.view_self') return { id: 't1', name: 'محل الأناقة' };
      if (a.id === 'operations.ai_notes') return { text: '' };
      if (a.id === 'operations.set_ai_notes') { posted = body; return { text: 'نفتح من السبت للخميس', redacted: [] }; }
      return {};
    };
    render(<ShopPane session={session} catalog={catalog} />);
    const box = await screen.findByLabelText('ملاحظات المساعد الذكي عبر واتساب');
    fireEvent.change(box, { target: { value: 'نفتح من السبت للخميس' } });
    fireEvent.click(screen.getByText('حفظ'));

    await screen.findByText('تم الحفظ.');
    expect(posted).toEqual({ text: 'نفتح من السبت للخميس' });
  });

  it('tells the owner which category was redacted after a save', async () => {
    withNotesActions();
    callImpl = async (_s, a) => {
      if (a.id === 'tenant.view_self') return { id: 't1', name: 'محل الأناقة' };
      if (a.id === 'operations.ai_notes') return { text: '' };
      if (a.id === 'operations.set_ai_notes') return { text: 'اتصل بنا [phone]', redacted: ['phone'] };
      return {};
    };
    render(<ShopPane session={session} catalog={catalog} />);
    const box = await screen.findByLabelText('ملاحظات المساعد الذكي عبر واتساب');
    fireEvent.change(box, { target: { value: 'اتصل بنا 0501234567' } });
    fireEvent.click(screen.getByText('حفظ'));

    await screen.findByText(/حذفنا تلقائياً: رقم جوال/);
  });

  it('refuses to save text over the character cap, client-side', async () => {
    withNotesActions();
    callImpl = async (_s, a) => {
      if (a.id === 'tenant.view_self') return { id: 't1', name: 'محل الأناقة' };
      if (a.id === 'operations.ai_notes') return { text: '' };
      return {};
    };
    render(<ShopPane session={session} catalog={catalog} />);
    const box = await screen.findByLabelText('ملاحظات المساعد الذكي عبر واتساب');
    fireEvent.change(box, { target: { value: 'x'.repeat(2001) } });

    await screen.findByText(/النص أطول من 2000 حرفاً/);
    const saveBtn = screen.getByText('حفظ').closest('button') as HTMLButtonElement;
    expect(saveBtn.disabled).toBe(true);
  });

  it('shows a read-only notice when the owner can read but not write', async () => {
    actionIds = new Set(['tenant.view_self', 'operations.ai_notes']);
    callImpl = async (_s, a) => {
      if (a.id === 'tenant.view_self') return { id: 't1', name: 'محل الأناقة' };
      if (a.id === 'operations.ai_notes') return { text: 'نص' };
      return {};
    };
    render(<ShopPane session={session} catalog={catalog} />);
    await screen.findByText('ملاحظات المساعد الذكي عبر واتساب');
    await screen.findByText('لا تملك صلاحية تعديل هذه الملاحظات.');
    expect(screen.queryByText('حفظ')).toBeFalsy();
  });
});
