/**
 * فريق الإدارة — لا مسار "اعرض كل الحسابات"، فقط بحث بمعرّف معروف ثم تعديل مصفوفة الأدوار
 * كاملة (لا منح/سحب ذرّي)، وهذا بالضبط سبب أن الشاشة بحث لا قائمة.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AdminTeam } from './AdminTeam';
import type { AdminSession } from './api';

const SESSION: AdminSession = { access_token: 'tok-1' };

const CATALOG = {
  services: [{ service: 'authz-service', actions: [
    { id: 'authz.get_subject_roles', label: 'x', method: 'GET' as const,
     path: '/api/v1/subjects/{subject}/roles', capability: 'platform.authz',
     params: [{ name: 'subject', in: 'path' as const, type: 'string', required: true }] },
    { id: 'authz.assign_roles', label: 'x', method: 'PUT' as const,
     path: '/api/v1/subjects/{subject}/roles', capability: 'platform.authz', confirm: true,
     params: [{ name: 'subject', in: 'path' as const, type: 'string', required: true }] },
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

describe('AdminTeam', () => {
  it('looks up a subject and shows its current roles checked', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({
      subject: 'ops@raje3.sa', tenant: '_platform', roles: ['platform-support'], capabilities: [],
    });

    render(<AdminTeam session={SESSION} />);
    fireEvent.change(await screen.findByPlaceholderText('subject id (بريد أو معرّف الحساب)'),
                     { target: { value: 'ops@raje3.sa' } });
    fireEvent.click(screen.getByText('بحث'));

    await waitFor(() => expect(screen.getByText('ops@raje3.sa')).toBeTruthy());
    const supportBox = screen.getByLabelText(/الدعم/) as HTMLInputElement;
    expect(supportBox.checked).toBe(true);
    const ownerBox = screen.getByLabelText(/مالك المنصّة/) as HTMLInputElement;
    expect(ownerBox.checked).toBe(false);
  });

  it('toggling a role and saving PUTs the whole replaced roles array', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn()
      .mockResolvedValueOnce({ subject: 'ops@raje3.sa', tenant: '_platform', roles: [], capabilities: [] })
      .mockResolvedValueOnce({ subject: 'ops@raje3.sa', tenant: '_platform', roles: ['platform-finance'], capabilities: [] });

    render(<AdminTeam session={SESSION} />);
    fireEvent.change(await screen.findByPlaceholderText('subject id (بريد أو معرّف الحساب)'),
                     { target: { value: 'ops@raje3.sa' } });
    fireEvent.click(screen.getByText('بحث'));
    await waitFor(() => expect(screen.getByText('ops@raje3.sa')).toBeTruthy());

    fireEvent.click(screen.getByLabelText(/المالية/));
    fireEvent.click(screen.getByText('حفظ الأدوار'));
    await screen.findAllByText(/تعديل أدوار/);
    fireEvent.click(screen.getByText('تأكيد'));

    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      '/api/v1/subjects/ops%40raje3.sa/roles', 'PUT',
      { roles: ['platform-finance'], capabilities: [] }, 'tok-1',
    ));
  });

  it('an honest empty state when the caller has no authz capability', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue({ services: [], unreachable: [] });
    render(<AdminTeam session={SESSION} />);
    await waitFor(() => expect(screen.getByText('لا صلاحية لديك لإدارة فريق الإدارة')).toBeTruthy());
  });
});
