/**
 * أسرار المشغّل — لا قراءة قيمة أبداً، فقط تلميح؛ الاختبارات تتأكد أن الشاشة لا تعرض القيمة
 * ولا تطلبها إلا كتابةً عبر `operator.set_secret`. مجمّعة بتطبيقات — دخول شاشة خدمة يمر أولاً
 * بضغطة على بطاقة تطبيقها.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AdminSecrets } from './AdminSecrets';
import type { AdminSession } from './api';

const SESSION: AdminSession = { access_token: 'tok-1' };

const CATALOG = {
  services: [
    { service: 'notification-service', actions: [
      { id: 'operator.list_secrets', label: 'x', method: 'GET' as const,
       path: '/api/v1/operator/secrets', capability: 'platform.secrets' },
      { id: 'operator.set_secret', label: 'x', method: 'PUT' as const,
       path: '/api/v1/operator/secrets', capability: 'platform.secrets', confirm: true },
      { id: 'operator.clear_secret', label: 'x', method: 'DELETE' as const,
       path: '/api/v1/operator/secrets/{name}', capability: 'platform.secrets', confirm: true,
       params: [{ name: 'name', in: 'path' as const, type: 'string', required: true }] },
    ] },
  ],
  unreachable: [],
};

// A service that DECLARES `choices` on its set_secret's `name` param — whatsapp-assistant's own
// real shape, used to test the picker + impact-message path independently of free-text services.
const CATALOG_WITH_CHOICES = {
  services: [
    { service: 'whatsapp-assistant', actions: [
      { id: 'operator.list_secrets', label: 'x', method: 'GET' as const,
       path: '/api/v1/operator/secrets', capability: 'platform.secrets' },
      { id: 'operator.set_secret', label: 'x', method: 'PUT' as const,
       path: '/api/v1/operator/secrets', capability: 'platform.secrets', confirm: true,
       params: [{ name: 'name', in: 'body' as const, type: 'string', required: true,
         choices: [{ value: 'ASSISTANT_MODEL_CREDENTIAL', label: 'مفتاح الذكاء الاصطناعي', impact: 'المساعد يتوقف مؤقتاً.' }] }] },
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

describe('AdminSecrets', () => {
  it('lists apps first, then opens a service on click', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({
      secrets: [{ name: 'meta_app_secret', hint: 'ab12', set_at: '2026-08-01T00:00:00Z', rotating: false }],
    });

    render(<AdminSecrets session={SESSION} />);
    // notification-service maps to the "واتساب" app card, not shown as a raw service name.
    await waitFor(() => expect(screen.getByText('واتساب')).toBeTruthy());
    expect(screen.queryByText('meta_app_secret')).toBeNull();

    fireEvent.click(screen.getByText('واتساب'));
    await waitFor(() => expect(screen.getByText('meta_app_secret')).toBeTruthy());
    expect(screen.getByText('····ab12')).toBeTruthy();
  });

  it('setting a secret arms a confirm dialog before calling set_secret', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn()
      .mockResolvedValueOnce({ secrets: [] })
      .mockResolvedValueOnce({ name: 'stripe_key', hint: 'xy99', rotating: false })
      .mockResolvedValueOnce({ secrets: [{ name: 'stripe_key', hint: 'xy99', set_at: 'x', rotating: false }] });

    render(<AdminSecrets session={SESSION} />);
    await waitFor(() => expect(screen.getByText('واتساب')).toBeTruthy());
    fireEvent.click(screen.getByText('واتساب'));
    await waitFor(() => expect(screen.getByText('لا أسرار مضبوطة بهذي الخدمة.')).toBeTruthy());

    fireEvent.change(screen.getByLabelText('الاعتماد'), { target: { value: 'stripe_key' } });
    fireEvent.change(screen.getByLabelText('القيمة الجديدة'), { target: { value: 'sk_live_x' } });
    fireEvent.click(screen.getByText('ضبط / تدوير'));

    expect(reqMock).not.toHaveBeenCalledWith(
      '/api/v1/operator/secrets', 'PUT', expect.anything(), 'tok-1',
    );
    await waitFor(() => expect(screen.getByText(/^ضبط "stripe_key"؟$/)).toBeTruthy());
  });

  it('a service with declared choices renders a picker, and its impact text on confirm', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG_WITH_CHOICES);
    reqMock = vi.fn().mockResolvedValue({ secrets: [] });

    render(<AdminSecrets session={SESSION} />);
    // whatsapp-assistant is grouped under the same "واتساب" app as notification-service.
    await waitFor(() => expect(screen.getByText('واتساب')).toBeTruthy());
    fireEvent.click(screen.getByText('واتساب'));
    await waitFor(() => expect(screen.getByLabelText('الاعتماد')).toBeTruthy());

    // A <select>, not a free-text input — its only option is the declared label, not the raw name.
    expect(screen.getByText('مفتاح الذكاء الاصطناعي')).toBeTruthy();
    fireEvent.change(screen.getByLabelText('القيمة الجديدة'), { target: { value: 'sk-real' } });
    fireEvent.click(screen.getByText('ضبط / تدوير'));

    await waitFor(() => expect(screen.getByText('المساعد يتوقف مؤقتاً.')).toBeTruthy());
  });

  it('an honest empty state when no service exposes secrets', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue({ services: [], unreachable: [] });
    render(<AdminSecrets session={SESSION} />);
    await waitFor(() => expect(screen.getByText('لا أسرار متاحة لصلاحياتك')).toBeTruthy());
  });
});
