/**
 * قوالب واتساب — الاختبارات تتأكد أن كل حالة (قيد المراجعة/معتمد/مرفوض) تُعرض بوضوح مع سبب الرفض
 * إن وُجد، أن التسجيل يبني {name, language, category, body, variables} صحيحة، أن "إرسال للمراجعة"
 * لا يصير بدون تأكيد، وأن غياب الصلاحية يُقال صراحة.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AdminWhatsAppTemplates } from './AdminWhatsAppTemplates';
import type { AdminSession } from './api';

const SESSION: AdminSession = { access_token: 'tok-1' };

const CATALOG = {
  services: [
    { service: 'notification-service', actions: [
      { id: 'notifications.list_wa_templates', label: 'x', method: 'GET' as const,
       path: '/api/v1/whatsapp/templates', capability: 'notifications.templates' },
      { id: 'notifications.register_wa_template', label: 'x', method: 'POST' as const,
       path: '/api/v1/whatsapp/templates', capability: 'notifications.templates', confirm: true },
      { id: 'notifications.submit_wa_template', label: 'x', method: 'POST' as const,
       path: '/api/v1/whatsapp/templates/{name}/{language}/submit',
       capability: 'notifications.templates', confirm: true },
    ] },
  ],
  unreachable: [],
};

function tpl(over: Partial<Record<string, unknown>> = {}) {
  return {
    id: 't1', tenant: '_platform', name: 'auth.otp', language: 'ar', category: 'AUTHENTICATION',
    body: 'رمزك هو {{code}}', variables: ['code'], examples: ['123456'], status: 'pending',
    provider_template_id: '', rejection_reason: '', created: '2026-09-01T00:00:00Z',
    updated: '2026-09-01T00:00:00Z', ...over,
  };
}

let fetchCatalogMock: ReturnType<typeof vi.fn>;
let reqMock: ReturnType<typeof vi.fn>;

vi.mock('./catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('./catalog')>();
  return { ...real, fetchCatalog: (...args: unknown[]) => fetchCatalogMock(...args) };
});
vi.mock('./api', async (importOriginal) => {
  const real = await importOriginal<typeof import('./api')>();
  return { ...real, req: (...args: unknown[]) => reqMock(...args) };
});

afterEach(() => vi.clearAllMocks());

describe('AdminWhatsAppTemplates', () => {
  it('shows a pending template with a submit-for-review action, no auto-submit', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({ templates: [tpl()] });

    render(<AdminWhatsAppTemplates session={SESSION} />);
    await waitFor(() => expect(screen.getByText('auth.otp')).toBeTruthy());
    expect(screen.getByText('قيد المراجعة')).toBeTruthy();
    expect(screen.getByText('أرسل للمراجعة')).toBeTruthy();
    // never called on its own — only a real click does
    expect(reqMock).not.toHaveBeenCalledWith(
      expect.stringContaining('/submit'), 'POST', expect.anything(), 'tok-1');
  });

  it('shows the rejection reason for a rejected template, plainly, no submit action', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({
      templates: [tpl({ status: 'rejected', provider_template_id: 'meta123',
                       rejection_reason: 'التصنيف لا يطابق المحتوى' })],
    });

    render(<AdminWhatsAppTemplates session={SESSION} />);
    await waitFor(() => expect(screen.getByText('مرفوض')).toBeTruthy());
    expect(screen.getByText(/التصنيف لا يطابق المحتوى/)).toBeTruthy();
    expect(screen.queryByText('أرسل للمراجعة')).toBeNull();
  });

  it('submitting for review requires confirmation, then calls the submit route', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn()
      .mockResolvedValueOnce({ templates: [tpl()] })
      .mockResolvedValueOnce(tpl({ provider_template_id: 'meta123' }))
      .mockResolvedValueOnce({ templates: [tpl({ provider_template_id: 'meta123' })] });

    render(<AdminWhatsAppTemplates session={SESSION} />);
    await waitFor(() => expect(screen.getByText('أرسل للمراجعة')).toBeTruthy());
    fireEvent.click(screen.getByText('أرسل للمراجعة'));

    expect(reqMock).not.toHaveBeenCalledWith(
      '/api/v1/whatsapp/templates/auth.otp/ar/submit', 'POST', undefined, 'tok-1');
    await waitFor(() => expect(screen.getByText(/إرسال "auth.otp" لمراجعة ميتا؟/)).toBeTruthy());

    fireEvent.click(screen.getByText('تأكيد'));
    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      '/api/v1/whatsapp/templates/auth.otp/ar/submit', 'POST', undefined, 'tok-1'));
  });

  it('registering a new template sends name/language/category/body/variables', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn()
      .mockResolvedValueOnce({ templates: [] })
      .mockResolvedValueOnce(tpl())
      .mockResolvedValueOnce({ templates: [tpl()] });

    render(<AdminWhatsAppTemplates session={SESSION} />);
    await waitFor(() => expect(screen.getByText('قالب جديد')).toBeTruthy());
    fireEvent.click(screen.getByText('قالب جديد'));

    fireEvent.change(screen.getByLabelText(/الاسم/), { target: { value: 'auth_otp' } });
    fireEvent.change(screen.getByLabelText(/نص القالب/), { target: { value: 'رمزك هو {{code}}' } });
    fireEvent.change(screen.getByLabelText(/أسماء المتغيّرات/), { target: { value: 'code' } });
    fireEvent.click(screen.getByText('حفظ كمسوّدة'));

    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      '/api/v1/whatsapp/templates', 'POST',
      { name: 'auth_otp', language: 'ar', category: 'AUTHENTICATION',
       body: 'رمزك هو {{code}}', variables: ['code'] },
      'tok-1',
    ));
  });

  it('filtering by status shows only that status', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({
      templates: [tpl(), tpl({ id: 't2', name: 'welcome', status: 'approved' })],
    });

    render(<AdminWhatsAppTemplates session={SESSION} />);
    await waitFor(() => expect(screen.getByText('auth.otp')).toBeTruthy());
    expect(screen.getByText('welcome')).toBeTruthy();

    fireEvent.click(screen.getAllByText(/^معتمد/)[0]);
    await waitFor(() => expect(screen.queryByText('auth.otp')).toBeNull());
    expect(screen.getByText('welcome')).toBeTruthy();
  });

  it('no templates yet, no capability — each says so plainly, never a silent blank screen', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({ templates: [] });
    render(<AdminWhatsAppTemplates session={SESSION} />);
    await waitFor(() => expect(screen.getByText('لا قوالب مسجَّلة بعد')).toBeTruthy());

    fetchCatalogMock = vi.fn().mockResolvedValue({ services: [], unreachable: [] });
    render(<AdminWhatsAppTemplates session={SESSION} />);
    await waitFor(() => expect(screen.getByText('هذه الشاشة ليست ضمن صلاحياتك')).toBeTruthy());
  });
});
