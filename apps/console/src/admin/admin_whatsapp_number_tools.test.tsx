import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AdminWhatsAppDiagnostics } from './AdminWhatsAppDiagnostics';
import { AdminRefused } from './api';
import type { AdminSession } from './api';

const SESSION: AdminSession = { access_token: 'tok-1' };

const CATALOG = {
  services: [{ service: 'operations', actions: [
    { id: 'operations.whatsapp_diagnostics', label: 'x', method: 'GET' as const,
     path: '/api/v1/platform/whatsapp/diagnostics', capability: 'platform.operations' },
    { id: 'operations.whatsapp_messaging_limit', label: 'x', method: 'GET' as const,
     path: '/api/v1/platform/whatsapp/messaging-limit', capability: 'platform.operations' },
    { id: 'operations.whatsapp_subscribed_fields', label: 'x', method: 'GET' as const,
     path: '/api/v1/platform/whatsapp/subscribed-fields', capability: 'platform.operations' },
    { id: 'operations.whatsapp_business_verification', label: 'x', method: 'GET' as const,
     path: '/api/v1/platform/whatsapp/business-verification', capability: 'platform.operations' },
    { id: 'operations.whatsapp_set_two_step_pin', label: 'x', method: 'POST' as const,
     path: '/api/v1/platform/whatsapp/two-step-pin', capability: 'platform.operations' },
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

async function searchByTenant() {
  fireEvent.change(await screen.findByLabelText('معرّف التينانت'), { target: { value: 'tnt_x' } });
  fireEvent.click(screen.getByText('بحث'));
}

describe('WhatsApp number-management cards (platform v0.19.9)', () => {
  it('renders the messaging-limit tier and quality rating after a search', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockImplementation((path: string) => {
      if (path.includes('/diagnostics')) return Promise.resolve({ deliveries: [], tenant: 'tnt_x' });
      if (path.includes('/messaging-limit')) {
        return Promise.resolve({ ok: true, limit: 10000, tier: 'TIER_10K', quality_rating: 'GREEN',
          display_phone_number: '', verified_name: '', name_status: '' });
      }
      return Promise.resolve({});
    });

    render(<AdminWhatsAppDiagnostics session={SESSION} />);
    await searchByTenant();

    await waitFor(() => expect(screen.getByText('TIER_10K')).toBeTruthy());
    expect(screen.getByText('GREEN')).toBeTruthy();
  });

  it('a NOT-connected business-verification answers honestly, never a fabricated status', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockImplementation((path: string) => {
      if (path.includes('/diagnostics')) return Promise.resolve({ deliveries: [], tenant: 'tnt_x' });
      if (path.includes('/business-verification')) return Promise.reject(new AdminRefused('تعذّر', 'NOT_CONNECTED'));
      return Promise.resolve({});
    });

    render(<AdminWhatsAppDiagnostics session={SESSION} />);
    await searchByTenant();

    await waitFor(() => expect(screen.getAllByRole('alert').length).toBeGreaterThan(0));
  });

  it('subscribed webhook fields are shown as a real read-only list, with a real note on where to change them', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockImplementation((path: string) => {
      if (path.includes('/diagnostics')) return Promise.resolve({ deliveries: [], tenant: 'tnt_x' });
      if (path.includes('/subscribed-fields')) {
        return Promise.resolve({ apps: [{ whatsapp_business_api_data: { id: '1', name: 'Raje3 App' },
          subscribed_fields: ['messages', 'message_template_status_update'] }] });
      }
      return Promise.resolve({});
    });

    render(<AdminWhatsAppDiagnostics session={SESSION} />);
    await searchByTenant();

    await waitFor(() => expect(screen.getByText('Raje3 App')).toBeTruthy());
    expect(screen.getByText('messages')).toBeTruthy();
    expect(screen.getByText(/لوحة مطوّري ميتا/)).toBeTruthy();
  });

  it('the two-step PIN never renders back after a successful set — success text only', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockImplementation((path: string, method: string) => {
      if (path.includes('/diagnostics')) return Promise.resolve({ deliveries: [], tenant: 'tnt_x' });
      if (path.includes('/two-step-pin') && method === 'POST') return Promise.resolve({ ok: true });
      return Promise.resolve({});
    });

    render(<AdminWhatsAppDiagnostics session={SESSION} />);
    await searchByTenant();

    fireEvent.click(await screen.findByText('تعيين/تدوير'));
    const input = await screen.findByLabelText('الرمز (6 أرقام)');
    fireEvent.change(input, { target: { value: '135790' } });
    fireEvent.click(screen.getByText('التالي'));
    fireEvent.click(await screen.findByText('تأكيد التعيين'));

    await waitFor(() => expect(screen.getByText(/تم تعيين الرمز بنجاح/)).toBeTruthy());
    expect(screen.queryByText('135790')).toBeNull();
  });

  it('a wrong PIN shows the peer\'s own distinct reason, not a generic failure', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockImplementation((path: string, method: string) => {
      if (path.includes('/diagnostics')) return Promise.resolve({ deliveries: [], tenant: 'tnt_x' });
      if (path.includes('/two-step-pin') && method === 'POST') {
        return Promise.reject(new AdminRefused('تعذّر', 'WRONG_PIN'));
      }
      return Promise.resolve({});
    });

    render(<AdminWhatsAppDiagnostics session={SESSION} />);
    await searchByTenant();

    fireEvent.click(await screen.findByText('تعيين/تدوير'));
    fireEvent.change(await screen.findByLabelText('الرمز (6 أرقام)'), { target: { value: '111111' } });
    fireEvent.click(screen.getByText('التالي'));
    fireEvent.click(await screen.findByText('تأكيد التعيين'));

    await waitFor(() => expect(screen.getByText(/الرمز غير صحيح/)).toBeTruthy());
  });
});
