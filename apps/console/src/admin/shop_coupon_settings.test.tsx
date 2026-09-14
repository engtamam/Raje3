/**
 * «كوبونات محل لمحل» admin settings — a different engine from billing's own ad-hoc coupon codes
 * (CouponCards.tsx), so it gets its own dedicated test rather than admin_apps.test.tsx's own.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ShopCouponSettings } from './ShopCouponSettings';
import type { AdminSession } from './api';

const SESSION: AdminSession = { access_token: 'tok-1' };

const GET_SETTINGS = { id: 'operations.coupon_settings_get', label: '', method: 'GET' as const,
  path: '/api/v1/platform/coupons/settings', capability: 'platform.operations' };
const SET_SETTINGS = { id: 'operations.coupon_settings_set', label: '', method: 'PATCH' as const,
  path: '/api/v1/platform/coupons/settings', capability: 'platform.operations' };
const LOOKUP = { id: 'operations.coupon_tenant_lookup', label: '', method: 'GET' as const,
  path: '/api/v1/platform/coupons/tenant-lookup', capability: 'platform.operations' };
const OVERRIDE_GET = { id: 'operations.coupon_override_get', label: '', method: 'GET' as const,
  path: '/api/v1/platform/coupons/tenants/{tenant_id}', capability: 'platform.operations',
  params: [{ name: 'tenant_id', in: 'path' as const, type: 'string', required: true }] };
const OVERRIDE_SET = { id: 'operations.coupon_override_set', label: '', method: 'PATCH' as const,
  path: '/api/v1/platform/coupons/tenants/{tenant_id}', capability: 'platform.operations',
  params: [{ name: 'tenant_id', in: 'path' as const, type: 'string', required: true }] };

let reqMock: ReturnType<typeof vi.fn>;
vi.mock('./api', async (importOriginal) => {
  const real = await importOriginal<typeof import('./api')>();
  return { ...real, req: (...args: unknown[]) => reqMock(...args) };
});

afterEach(() => vi.clearAllMocks());

describe('ShopCouponSettings', () => {
  it('loads and shows the global ceiling, base percent and tiers', async () => {
    reqMock = vi.fn().mockResolvedValue(
      { ceiling_percent: 35, base_percent: 10, tiers: [{ max_grants: 50, percent: 20 }] });
    render(<ShopCouponSettings session={SESSION} settingsGetAction={GET_SETTINGS}
                               settingsSetAction={SET_SETTINGS} />);
    await waitFor(() => expect(screen.getByDisplayValue('35')).toBeTruthy());
    expect(screen.getByDisplayValue('10')).toBeTruthy();
    expect(screen.getByDisplayValue('50')).toBeTruthy();
    expect(screen.getByDisplayValue('20')).toBeTruthy();
  });

  it('adding a tier and saving sends the full tier list to the settings action', async () => {
    reqMock = vi.fn()
      .mockResolvedValueOnce({ ceiling_percent: 35, base_percent: 10, tiers: [] })
      .mockResolvedValueOnce({ ceiling_percent: 35, base_percent: 10, tiers: [{ max_grants: 100, percent: 30 }] });
    render(<ShopCouponSettings session={SESSION} settingsGetAction={GET_SETTINGS}
                               settingsSetAction={SET_SETTINGS} />);
    await waitFor(() => expect(screen.getByText('+ شريحة جديدة')).toBeTruthy());
    fireEvent.click(screen.getByText('+ شريحة جديدة'));
    const grantsInput = screen.getByLabelText('عدد الخصومات');
    const percentInput = screen.getByLabelText('النسبة');
    fireEvent.change(grantsInput, { target: { value: '100' } });
    fireEvent.change(percentInput, { target: { value: '30' } });
    fireEvent.click(screen.getByText('حفظ الإعدادات'));
    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      '/api/v1/platform/coupons/settings', 'PATCH',
      { ceiling_percent: 35, base_percent: 10, tiers: [{ max_grants: 100, percent: 30 }] },
      'tok-1'));
  });

  it('searching a phone that is not a registered tenant shows the real reason', async () => {
    reqMock = vi.fn()
      .mockResolvedValueOnce({ ceiling_percent: 35, base_percent: 10, tiers: [] })
      .mockResolvedValueOnce({ tenant: '' });
    render(<ShopCouponSettings session={SESSION} settingsGetAction={GET_SETTINGS}
                               lookupAction={LOOKUP} overrideGetAction={OVERRIDE_GET}
                               overrideSetAction={OVERRIDE_SET} />);
    await waitFor(() => expect(screen.getByPlaceholderText('05xxxxxxxx')).toBeTruthy());
    fireEvent.change(screen.getByPlaceholderText('05xxxxxxxx'), { target: { value: '0501234567' } });
    fireEvent.click(screen.getByText('بحث'));
    await waitFor(() => expect(screen.getByText('لا يوجد محل مسجّل بهذا الرقم.')).toBeTruthy());
  });

  it('searching a registered phone shows its override, and saving a raised cap works', async () => {
    reqMock = vi.fn()
      .mockResolvedValueOnce({ ceiling_percent: 35, base_percent: 10, tiers: [] })
      .mockResolvedValueOnce({ tenant: 'tnt_found' })
      .mockResolvedValueOnce({ percent: null, note: '' })
      .mockResolvedValueOnce({ percent: 25, note: 'مكافأة' });
    render(<ShopCouponSettings session={SESSION} settingsGetAction={GET_SETTINGS}
                               lookupAction={LOOKUP} overrideGetAction={OVERRIDE_GET}
                               overrideSetAction={OVERRIDE_SET} />);
    await waitFor(() => expect(screen.getByPlaceholderText('05xxxxxxxx')).toBeTruthy());
    fireEvent.change(screen.getByPlaceholderText('05xxxxxxxx'), { target: { value: '0501234567' } });
    fireEvent.click(screen.getByText('بحث'));
    await waitFor(() => expect(screen.getByText('tnt_found')).toBeTruthy());

    fireEvent.change(screen.getByLabelText('السقف الخاص (%)'), { target: { value: '25' } });
    fireEvent.change(screen.getByLabelText('ملاحظة'), { target: { value: 'مكافأة' } });
    fireEvent.click(screen.getByText('حفظ'));
    await waitFor(() => expect(reqMock).toHaveBeenLastCalledWith(
      '/api/v1/platform/coupons/tenants/tnt_found', 'PATCH',
      { tenant: 'tnt_found', percent: 25, note: 'مكافأة' }, 'tok-1'));
  });

  it('the block button sends percent 0 with one click, no typing required', async () => {
    reqMock = vi.fn()
      .mockResolvedValueOnce({ ceiling_percent: 35, base_percent: 10, tiers: [] })
      .mockResolvedValueOnce({ tenant: 'tnt_found' })
      .mockResolvedValueOnce({ percent: null, note: '' })
      .mockResolvedValueOnce({ percent: 0, note: '' });
    render(<ShopCouponSettings session={SESSION} settingsGetAction={GET_SETTINGS}
                               lookupAction={LOOKUP} overrideGetAction={OVERRIDE_GET}
                               overrideSetAction={OVERRIDE_SET} />);
    await waitFor(() => expect(screen.getByPlaceholderText('05xxxxxxxx')).toBeTruthy());
    fireEvent.change(screen.getByPlaceholderText('05xxxxxxxx'), { target: { value: '0501234567' } });
    fireEvent.click(screen.getByText('بحث'));
    await waitFor(() => expect(screen.getByText('tnt_found')).toBeTruthy());

    fireEvent.click(screen.getByText('حظر المحل من هذا التطبيق'));
    await waitFor(() => expect(reqMock).toHaveBeenLastCalledWith(
      '/api/v1/platform/coupons/tenants/tnt_found', 'PATCH',
      { tenant: 'tnt_found', percent: 0, note: '' }, 'tok-1'));
    await waitFor(() => expect(screen.getByText('محظور من التطبيق')).toBeTruthy());
  });

  it('a blocked tenant shows the badge and an unblock button instead of the block one', async () => {
    reqMock = vi.fn()
      .mockResolvedValueOnce({ ceiling_percent: 35, base_percent: 10, tiers: [] })
      .mockResolvedValueOnce({ tenant: 'tnt_blocked' })
      .mockResolvedValueOnce({ percent: 0, note: 'محظور مسبقاً' });
    render(<ShopCouponSettings session={SESSION} settingsGetAction={GET_SETTINGS}
                               lookupAction={LOOKUP} overrideGetAction={OVERRIDE_GET}
                               overrideSetAction={OVERRIDE_SET} />);
    fireEvent.change(await screen.findByPlaceholderText('05xxxxxxxx'), { target: { value: '0501234567' } });
    fireEvent.click(screen.getByText('بحث'));

    await waitFor(() => expect(screen.getByText('محظور من التطبيق')).toBeTruthy());
    expect(screen.getByText('رفع الحظر')).toBeTruthy();
    expect(screen.queryByText('حظر المحل من هذا التطبيق')).toBeNull();
  });

  it('unblocking clears the override entirely (percent: null), not just to some other number', async () => {
    reqMock = vi.fn()
      .mockResolvedValueOnce({ ceiling_percent: 35, base_percent: 10, tiers: [] })
      .mockResolvedValueOnce({ tenant: 'tnt_blocked' })
      .mockResolvedValueOnce({ percent: 0, note: '' })
      .mockResolvedValueOnce({ percent: null, note: '' });
    render(<ShopCouponSettings session={SESSION} settingsGetAction={GET_SETTINGS}
                               lookupAction={LOOKUP} overrideGetAction={OVERRIDE_GET}
                               overrideSetAction={OVERRIDE_SET} />);
    fireEvent.change(await screen.findByPlaceholderText('05xxxxxxxx'), { target: { value: '0501234567' } });
    fireEvent.click(screen.getByText('بحث'));
    await screen.findByText('رفع الحظر');

    fireEvent.click(screen.getByText('رفع الحظر'));
    await waitFor(() => expect(reqMock).toHaveBeenLastCalledWith(
      '/api/v1/platform/coupons/tenants/tnt_blocked', 'PATCH',
      { tenant: 'tnt_blocked', percent: null, note: '' }, 'tok-1'));
    await waitFor(() => expect(screen.queryByText('محظور من التطبيق')).toBeNull());
  });
});
