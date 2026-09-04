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

// شاشة البطاقات: كل مزوّد يفتح بضغطة قبل ما تشوف مفاتيحه. الاختبارات تفتح البطاقة أول شي.
async function openProvider(label: string) {
  await waitFor(() => expect(screen.getByText(label)).toBeTruthy());
  fireEvent.click(screen.getByText(label));
}

describe('AdminProviderSecrets', () => {
  it('shows only the last four characters, never a value, for a configured key', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({
      secrets: [{ key: 'META_APP_SECRET', label: 'سر تطبيق ميتا', configured: true,
                 last4: 'ab12', updated_at: '2026-08-01T00:00:00Z', updated_by: 'op-1' }],
    });

    render(<AdminProviderSecrets session={SESSION} />);
    await openProvider('Meta (واتساب)');
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
    await openProvider('Meta (واتساب)');
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
    await openProvider('Gemini');
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

  it('groups keys into one card per provider, collapsed until opened, one open at a time', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({
      secrets: [
        { key: 'META_APP_ID', label: 'معرّف تطبيق ميتا', configured: true, last4: '1234', updated_at: null, updated_by: null },
        { key: 'META_APP_SECRET', label: 'سر تطبيق ميتا', configured: false, last4: null, updated_at: null, updated_by: null },
        { key: 'GEMINI_API_KEY', label: 'مفتاح Gemini', configured: false, last4: null, updated_at: null, updated_by: null },
      ],
    });

    render(<AdminProviderSecrets session={SESSION} />);
    await waitFor(() => expect(screen.getByText('Meta (واتساب)')).toBeTruthy());
    expect(screen.getByText('Gemini')).toBeTruthy();
    // collapsed: individual key labels are not in the DOM yet
    expect(screen.queryByText('معرّف تطبيق ميتا')).toBeNull();
    expect(screen.getByText('1 / 2 مُعدّ')).toBeTruthy();   // Meta's own tally, both its keys counted

    fireEvent.click(screen.getByText('Meta (واتساب)'));
    await waitFor(() => expect(screen.getByText('معرّف تطبيق ميتا')).toBeTruthy());
    expect(screen.getByText('سر تطبيق ميتا')).toBeTruthy();
    expect(screen.queryByText('مفتاح Gemini')).toBeNull();   // the OTHER provider stays collapsed

    // opening a second card closes the first — one open at a time
    fireEvent.click(screen.getByText('Gemini'));
    await waitFor(() => expect(screen.getByText('مفتاح Gemini')).toBeTruthy());
    expect(screen.queryByText('معرّف تطبيق ميتا')).toBeNull();
  });

  it('no capability, no tab that quietly does nothing — the screen says so', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue({ services: [], unreachable: [] });
    render(<AdminProviderSecrets session={SESSION} />);
    await waitFor(() => expect(screen.getByText('هذه الشاشة ليست ضمن صلاحياتك')).toBeTruthy());
  });

  it('shows the env var name under the label, and "؟" reveals where to get the value', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({
      secrets: [{ key: 'GEMINI_API_KEY', label: 'مفتاح Gemini', configured: false,
                 last4: null, updated_at: null, updated_by: null }],
    });

    render(<AdminProviderSecrets session={SESSION} />);
    await openProvider('Gemini');
    await waitFor(() => expect(screen.getByText('GEMINI_API_KEY')).toBeTruthy());

    expect(screen.queryByText(/aistudio\.google\.com/)).toBeNull();   // collapsed by default
    fireEvent.click(screen.getByLabelText(/ايش هذا؟/));
    expect(screen.getByText(/aistudio\.google\.com/)).toBeTruthy();
  });

  it('never renders any "reveal" or "show" control', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({
      secrets: [{ key: 'META_APP_SECRET', label: 'سر تطبيق ميتا', configured: true,
                 last4: 'ab12', updated_at: null, updated_by: null }],
    });

    render(<AdminProviderSecrets session={SESSION} />);
    await openProvider('Meta (واتساب)');
    await waitFor(() => expect(screen.getByText('سر تطبيق ميتا')).toBeTruthy());
    // «تُعرض» legitimately appears in this screen's own reassurance copy ("القيمة لا تُعرض هنا
    // أبداً") — the real assertion is that no CONTROL offers to reveal one.
    expect(screen.queryByRole('button', { name: /عرض|إظهار|show|reveal/i })).toBeNull();
  });
});
