/**
 * مفاتيح المزوّدين الخارجيين — الاختبارات تتأكد أن الشاشة لا تعرض قيمة أبداً (آخر أربعة أحرف
 * فقط)، وأن التحديث يمرّ عبر تأكيد قبل استدعاء secrets.update، وأن غياب الصلاحية يُقال صراحة.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AdminProviderSecrets } from './AdminProviderSecrets';
import type { AdminSession } from './api';

const SESSION: AdminSession = { access_token: 'tok-1' };

const CATALOG = {
  services: [
    { service: 'secrets-admin', actions: [
      { id: 'secrets.list', label: 'x', method: 'GET' as const,
       path: '/api/v1/secrets', capability: 'platform.secrets_manage' },
      { id: 'secrets.update', label: 'x', method: 'POST' as const,
       path: '/api/v1/secrets/{key}', capability: 'platform.secrets_manage', confirm: true,
       params: [{ name: 'key', in: 'path' as const, type: 'string', required: true }] },
    ] },
  ],
  unreachable: [],
};

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

describe('AdminProviderSecrets', () => {
  it('shows only the last four characters, never a value, for a configured key', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({
      secrets: [{ key: 'META_APP_SECRET', label: 'سر تطبيق ميتا', configured: true,
                 last4: 'ab12', updated_at: '2026-08-01T00:00:00Z', updated_by: 'op-1' }],
    });

    render(<AdminProviderSecrets session={SESSION} />);
    await waitFor(() => expect(screen.getByText('سر تطبيق ميتا')).toBeTruthy());
    expect(screen.getByText('····ab12')).toBeTruthy();
    // NEVER THE RAW VALUE, NOT EVEN AS A KEY NAME IN A DATA ATTRIBUTE THE DOM WOULD EXPOSE.
    expect(screen.queryByText(/value/i)).toBeNull();
  });

  it('an unreadable row says so, never a false "غير مُعدّ"', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({
      secrets: [{ key: 'META_APP_SECRET', label: 'سر تطبيق ميتا', configured: null,
                 last4: null, updated_at: null, updated_by: null, unreadable: true }],
    });

    render(<AdminProviderSecrets session={SESSION} />);
    await waitFor(() => expect(screen.getByText(/تعذّر الاتصال بالعنقود/)).toBeTruthy());
  });

  it('updating a key arms a confirm dialog before calling secrets.update, and clears the field', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn()
      .mockResolvedValueOnce({
        secrets: [{ key: 'GEMINI_API_KEY', label: 'مفتاح Gemini', configured: false,
                   last4: null, updated_at: null, updated_by: null }],
      })
      .mockResolvedValueOnce({ key: 'GEMINI_API_KEY', last4: 'zz99', updated_at: 'x' })
      .mockResolvedValueOnce({
        secrets: [{ key: 'GEMINI_API_KEY', label: 'مفتاح Gemini', configured: true,
                   last4: 'zz99', updated_at: 'x', updated_by: 'op-1' }],
      });

    render(<AdminProviderSecrets session={SESSION} />);
    await waitFor(() => expect(screen.getByText('غير مُعدّ')).toBeTruthy());

    const input = screen.getByLabelText('القيمة الجديدة') as HTMLInputElement;
    expect(input.type).toBe('password');
    fireEvent.change(input, { target: { value: 'AQ.new-real-key' } });
    fireEvent.click(screen.getByText('تحديث'));

    // NOT CALLED YET — the confirm dialog must gate the actual write.
    expect(reqMock).not.toHaveBeenCalledWith(
      '/api/v1/secrets/GEMINI_API_KEY', 'POST', expect.anything(), 'tok-1',
    );
    await waitFor(() => expect(screen.getByText(/تحديث "مفتاح Gemini"؟/)).toBeTruthy());

    fireEvent.click(screen.getByText('تأكيد'));
    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      '/api/v1/secrets/GEMINI_API_KEY', 'POST', { value: 'AQ.new-real-key' }, 'tok-1',
    ));
    // THE FIELD IS EMPTY AGAIN — nothing typed here survives past the request.
    await waitFor(() => expect((screen.getByLabelText('القيمة الجديدة') as HTMLInputElement).value).toBe(''));
  });

  it('no capability, no tab that quietly does nothing — the screen says so', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue({ services: [], unreachable: [] });
    render(<AdminProviderSecrets session={SESSION} />);
    await waitFor(() => expect(screen.getByText('هذه الشاشة ليست ضمن صلاحياتك')).toBeTruthy());
  });

  it('never renders any "reveal" or "show" control', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({
      secrets: [{ key: 'META_APP_SECRET', label: 'سر تطبيق ميتا', configured: true,
                 last4: 'ab12', updated_at: null, updated_by: null }],
    });

    render(<AdminProviderSecrets session={SESSION} />);
    await waitFor(() => expect(screen.getByText('سر تطبيق ميتا')).toBeTruthy());
    // «تُعرض» legitimately appears in this screen's own reassurance copy ("القيمة لا تُعرض هنا
    // أبداً") — the real assertion is that no CONTROL offers to reveal one.
    expect(screen.queryByRole('button', { name: /عرض|إظهار|show|reveal/i })).toBeNull();
  });
});
