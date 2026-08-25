import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AdminWhatsAppDiagnostics } from './AdminWhatsAppDiagnostics';
import type { AdminSession } from './api';

const SESSION: AdminSession = { access_token: 'tok-1' };

const CATALOG = {
  services: [{ service: 'operations', actions: [
    { id: 'operations.whatsapp_diagnostics', label: 'x', method: 'GET' as const,
     path: '/api/v1/platform/whatsapp/diagnostics', capability: 'platform.operations' },
  ] }],
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

describe('AdminWhatsAppDiagnostics', () => {
  it('shows nothing before a search, an honest idle state', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    render(<AdminWhatsAppDiagnostics session={SESSION} />);
    await waitFor(() => expect(screen.getByText('ابحث بمعرّف تينانت أو رقم ميتا')).toBeTruthy());
  });

  it('searching by tenant calls the route with a tenant query and renders the reason', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({
      deliveries: [{ id: 'd1', status: 'failed', error: 'template not approved',
                    recipient_masked: '****1234', created: '2026-08-01T00:00:00Z' }],
    });

    render(<AdminWhatsAppDiagnostics session={SESSION} />);
    fireEvent.change(await screen.findByLabelText('معرّف التينانت'), { target: { value: 'tnt_x' } });
    fireEvent.click(screen.getByText('بحث'));

    await waitFor(() => expect(screen.getByText('template not approved')).toBeTruthy());
    expect(reqMock).toHaveBeenCalledWith(
      '/api/v1/platform/whatsapp/diagnostics?tenant=tnt_x', 'GET', undefined, 'tok-1',
    );
  });

  it('an empty result is honest, not blank', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({ deliveries: [] });

    render(<AdminWhatsAppDiagnostics session={SESSION} />);
    fireEvent.change(await screen.findByLabelText('رقم ميتا (phone_number_id)'), { target: { value: '999' } });
    fireEvent.click(screen.getByText('بحث'));

    await waitFor(() => expect(screen.getByText('لا رسائل مسجَّلة لهذا المحل')).toBeTruthy());
  });

  it('an unreachable peer surfaces the error, never a silent empty list', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockRejectedValue(new Error('تعذّر الاتصال بخدمة الإشعارات الآن.'));

    render(<AdminWhatsAppDiagnostics session={SESSION} />);
    fireEvent.change(await screen.findByLabelText('معرّف التينانت'), { target: { value: 'tnt_x' } });
    fireEvent.click(screen.getByText('بحث'));

    await waitFor(() => expect(screen.getByRole('alert')).toBeTruthy());
  });
});
