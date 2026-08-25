/**
 * أسرار المشغّل — لا قراءة قيمة أبداً، فقط تلميح؛ الاختبارات تتأكد أن الشاشة لا تعرض القيمة
 * ولا تطلبها إلا كتابةً عبر `operator.set_secret`.
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
  it('shows only the hint, never a value, for each set secret', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({
      secrets: [{ name: 'meta_app_secret', hint: 'ab12', set_at: '2026-08-01T00:00:00Z', rotating: false }],
    });

    render(<AdminSecrets session={SESSION} />);
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
    await waitFor(() => expect(screen.getByText('لا أسرار مضبوطة بهذي الخدمة.')).toBeTruthy());

    fireEvent.change(screen.getByLabelText('اسم السرّ'), { target: { value: 'stripe_key' } });
    fireEvent.change(screen.getByLabelText('القيمة'), { target: { value: 'sk_live_x' } });
    fireEvent.click(screen.getByText('ضبط / تدوير'));

    expect(reqMock).not.toHaveBeenCalledWith(
      '/api/v1/operator/secrets', 'PUT', expect.anything(), 'tok-1',
    );
    await waitFor(() => expect(screen.getByText(/ضبط السرّ/)).toBeTruthy());
  });

  it('an honest empty state when no service exposes secrets', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue({ services: [], unreachable: [] });
    render(<AdminSecrets session={SESSION} />);
    await waitFor(() => expect(screen.getByText('لا أسرار متاحة لصلاحياتك')).toBeTruthy());
  });
});
