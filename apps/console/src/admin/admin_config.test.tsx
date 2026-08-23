/**
 * الإعدادات الحيّة — `operator.get_config` يرجع `{config: {...}}` كائناً، لا مصفوفة صفوف، وهذا
 * بالضبط سبب أن هذي الشاشة مبنية يدوياً لا عبر `ActionListGroup` العام.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AdminConfig } from './AdminConfig';
import type { AdminSession } from './api';

const SESSION: AdminSession = { access_token: 'tok-1' };

const CATALOG = {
  services: [
    { service: 'notification-service', actions: [
      { id: 'operator.get_config', label: 'x', method: 'GET' as const,
       path: '/api/v1/operator/config', capability: 'platform.config' },
      { id: 'operator.set_config', label: 'x', method: 'PUT' as const,
       path: '/api/v1/operator/config', capability: 'platform.config', confirm: true },
      { id: 'operator.clear_config', label: 'x', method: 'DELETE' as const,
       path: '/api/v1/operator/config/{key}', capability: 'platform.config', confirm: true,
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

describe('AdminConfig', () => {
  it('renders every service that declares operator.get_config, with its own keys', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({ config: { rate_limit_per_min: 60, retries: 3 } });

    render(<AdminConfig session={SESSION} />);
    await waitFor(() => expect(screen.getByText('rate_limit_per_min')).toBeTruthy());
    expect(screen.getByText('retries')).toBeTruthy();
  });

  it('saving a key calls set_config with {key, value} and reloads', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn()
      .mockResolvedValueOnce({ config: { retries: 3 } })
      .mockResolvedValueOnce({ key: 'retries', value: '5' })
      .mockResolvedValueOnce({ config: { retries: 5 } });

    render(<AdminConfig session={SESSION} />);
    const input = await screen.findByLabelText('retries') as HTMLInputElement;
    fireEvent.change(input, { target: { value: '5' } });
    fireEvent.click(screen.getByText('حفظ'));

    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      '/api/v1/operator/config', 'PUT', { key: 'retries', value: '5' }, 'tok-1',
    ));
  });

  it('an honest empty state when no service exposes config', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue({ services: [], unreachable: [] });
    render(<AdminConfig session={SESSION} />);
    await waitFor(() => expect(screen.getByText('لا إعدادات حيّة متاحة لصلاحياتك')).toBeTruthy());
  });
});
