/**
 * فريق الإدارة — أُعيد بناؤها فوق دليل أعضاء حقيقي (`identity.list_members` وما حوله)، تينانت
 * المستدعي نفسه (`_platform`) لا معامِل صريح — القائمة كاملة، لا بحث بمعرّف معروف مسبقاً.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AdminTeam } from './AdminTeam';
import type { AdminSession } from './api';

const SESSION: AdminSession = { access_token: 'tok-1' };

const CATALOG = {
  services: [{ service: 'identity-service', actions: [
    { id: 'identity.list_members', label: 'x', method: 'GET' as const,
     path: '/api/v1/tenancy/members', capability: 'members:read' },
    { id: 'identity.add_member', label: 'x', method: 'POST' as const,
     path: '/api/v1/tenancy/members', capability: 'members:write', confirm: true },
    { id: 'identity.update_member', label: 'x', method: 'PUT' as const,
     path: '/api/v1/tenancy/members/{person_id}', capability: 'members:write', confirm: true },
    { id: 'identity.set_member_status', label: 'x', method: 'POST' as const,
     path: '/api/v1/tenancy/members/{person_id}/status', capability: 'members:write', confirm: true },
    { id: 'identity.remove_member', label: 'x', method: 'DELETE' as const,
     path: '/api/v1/tenancy/members/{person_id}', capability: 'members:write', danger: true, confirm: true },
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
  it('lists the whole roster with roles and status badges', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({
      tenant: '_platform', next: null,
      members: [
        { person_id: 'p1', identifier: 'ops@raje3.sa', roles: ['platform-support'], caps: [], status: 'active', since: 0 },
        { person_id: 'p2', identifier: 'fin@raje3.sa', roles: ['platform-finance'], caps: [], status: 'suspended', since: 0 },
      ],
    });

    render(<AdminTeam session={SESSION} />);
    await waitFor(() => expect(screen.getAllByText('ops@raje3.sa').length).toBeGreaterThan(0));
    expect(screen.getAllByText('fin@raje3.sa').length).toBeGreaterThan(0);
    expect(screen.getAllByText('الدعم (قراءة فقط)').length).toBeGreaterThan(0);
    expect(screen.getAllByText('موقوف').length).toBeGreaterThan(0);
  });

  it('suspending an active member posts status=suspended after confirm', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn()
      .mockResolvedValueOnce({
        tenant: '_platform', next: null,
        members: [{ person_id: 'p1', identifier: 'ops@raje3.sa', roles: [], caps: [], status: 'active', since: 0 }],
      })
      .mockResolvedValueOnce({ member: { person_id: 'p1', status: 'suspended' } })
      .mockResolvedValueOnce({ tenant: '_platform', next: null, members: [] });

    render(<AdminTeam session={SESSION} />);
    await waitFor(() => expect(screen.getAllByText('ops@raje3.sa').length).toBeGreaterThan(0));

    fireEvent.click(screen.getAllByText('إيقاف')[0]);
    await screen.findByText(/إيقاف "ops@raje3.sa"؟/);
    fireEvent.click(screen.getByText('تأكيد'));

    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      '/api/v1/tenancy/members/p1/status', 'POST', { status: 'suspended' }, 'tok-1',
    ));
  });

  it('editing roles PUTs the full replaced roles array', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn()
      .mockResolvedValueOnce({
        tenant: '_platform', next: null,
        members: [{ person_id: 'p1', identifier: 'ops@raje3.sa', roles: ['platform-support'], caps: [], status: 'active', since: 0 }],
      })
      .mockResolvedValueOnce({ member: { person_id: 'p1', roles: ['platform-support', 'platform-finance'] } })
      .mockResolvedValueOnce({ tenant: '_platform', next: null, members: [] });

    render(<AdminTeam session={SESSION} />);
    await waitFor(() => expect(screen.getAllByText('ops@raje3.sa').length).toBeGreaterThan(0));

    fireEvent.click(screen.getAllByText('تعديل الأدوار')[0]);
    fireEvent.click(await screen.findByLabelText(/المالية/));
    fireEvent.click(screen.getByText('حفظ الأدوار'));

    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      '/api/v1/tenancy/members/p1', 'PUT',
      { roles: ['platform-support', 'platform-finance'] }, 'tok-1',
    ));
  });

  it('adding a member posts identifier and roles, and shows an invite token once', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn()
      .mockResolvedValueOnce({ tenant: '_platform', next: null, members: [] })
      .mockResolvedValueOnce({ member: { person_id: 'p9' }, invite_token: 'inv_abc123' });

    render(<AdminTeam session={SESSION} />);
    await waitFor(() => expect(screen.getByText('لا أعضاء بفريق الإدارة بعد')).toBeTruthy());

    fireEvent.click(screen.getByText('دعوة عضو'));
    fireEvent.change(await screen.findByLabelText('البريد الإلكتروني'), { target: { value: 'new@raje3.sa' } });
    fireEvent.click(screen.getByText('دعوة'));

    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      '/api/v1/tenancy/members', 'POST', { identifier: 'new@raje3.sa', roles: [] }, 'tok-1',
    ));
    await waitFor(() => expect(screen.getByText('inv_abc123')).toBeTruthy());
  });

  it('removing a member is armed by typing their identifier', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn()
      .mockResolvedValueOnce({
        tenant: '_platform', next: null,
        members: [{ person_id: 'p1', identifier: 'ops@raje3.sa', roles: [], caps: [], status: 'active', since: 0 }],
      })
      .mockResolvedValueOnce({ removed: true, person_id: 'p1', tenant: '_platform' })
      .mockResolvedValueOnce({ tenant: '_platform', next: null, members: [] });

    render(<AdminTeam session={SESSION} />);
    await waitFor(() => expect(screen.getAllByText('ops@raje3.sa').length).toBeGreaterThan(0));

    fireEvent.click(screen.getAllByText('إزالة')[0]);
    const armInput = await screen.findByLabelText(/اكتب/);
    const confirmBtn = screen.getByText('تأكيد').closest('button') as HTMLButtonElement;
    expect(confirmBtn.disabled).toBe(true);
    fireEvent.change(armInput, { target: { value: 'ops@raje3.sa' } });
    fireEvent.click(confirmBtn);

    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      '/api/v1/tenancy/members/p1', 'DELETE', undefined, 'tok-1',
    ));
  });

  it('an honest empty state when the caller has no members:read capability', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue({ services: [], unreachable: [] });
    render(<AdminTeam session={SESSION} />);
    await waitFor(() => expect(screen.getByText('لا صلاحية لديك لإدارة فريق الإدارة')).toBeTruthy());
  });
});
