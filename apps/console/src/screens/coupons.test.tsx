/**
 * «كوبونات» — the grant form, the two tabs, and the live phone-check hint. Each backend call is
 * faked at the `catalog.call` boundary, same discipline as `rating.test.tsx`.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render as rtlRender, screen, waitFor } from '@testing-library/react';
import type { ReactElement } from 'react';
import { OperatorI18nProvider } from '../operator-i18n';
import { CouponsScreen } from './Coupons';

const SESSION = { tenant: 't1', operator: '', operatorName: '', token: 'tok' } as never;

const STATS = {
  grants_this_month: 3, current_cap_percent: 20, ceiling_percent: 35,
  next_tier_percent: 30, next_tier_grants_needed: 5,
  history: [
    { month_key: '2026-04', grants: 1 }, { month_key: '2026-05', grants: 2 },
    { month_key: '2026-06', grants: 0 }, { month_key: '2026-07', grants: 4 },
    { month_key: '2026-08', grants: 2 }, { month_key: '2026-09', grants: 3 },
  ],
};

const HISTORY = {
  attempts: [
    { id: 'a1', beneficiary_phone_last4: '4821', percent_requested: 10, scope: 'feature.bookings',
     outcome: 'granted', created: Math.floor(Date.now() / 1000), per_app: { 'feature.bookings': 'attached' } },
    { id: 'a2', beneficiary_phone_last4: '9910', percent_requested: 25, scope: 'all',
     outcome: 'over_cap', created: Math.floor(Date.now() / 1000), per_app: {} },
  ],
};

let grantCalls: Record<string, unknown>[] = [];
let prefsCalls: Record<string, unknown>[] = [];
let sallaInstallCalls = 0;
let sallaDisconnectCalls = 0;
let sallaConnected = false;

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }, params?: Record<string, unknown>) => {
      if (a.id === 'operations.coupon_stats') return STATS;
      if (a.id === 'operations.coupon_history') return HISTORY;
      if (a.id === 'operations.coupon_preferences_get') return { visit_grant_enabled: true };
      if (a.id === 'operations.coupon_preferences_set') {
        prefsCalls.push(params ?? {});
        return { visit_grant_enabled: (params?.visit_grant_enabled as boolean) ?? true };
      }
      if (a.id === 'operations.coupon_check') {
        const phone = String(params?.phone ?? '');
        if (phone.endsWith('99')) return { registered: true, already_granted_this_month: true };
        if (phone.endsWith('00')) return { registered: false, already_granted_this_month: false };
        return { registered: true, already_granted_this_month: false };
      }
      if (a.id === 'operations.grant_coupon') {
        grantCalls.push(params ?? {});
        return { id: 'att1', outcome: 'granted', per_app: { 'feature.bookings': 'attached' } };
      }
      if (a.id === 'operations.salla_status') {
        return sallaConnected
          ? { connected: true, merchant_id: '42', store_name: 'متجر الاختبار' }
          : { connected: false };
      }
      if (a.id === 'operations.salla_install') {
        sallaInstallCalls += 1;
        return { url: 'https://accounts.salla.sa/oauth2/auth?client_id=x' };
      }
      if (a.id === 'operations.salla_disconnect') {
        sallaDisconnectCalls += 1;
        sallaConnected = false;
        return { connected: false };
      }
      return {};
    },
  };
});

const catalog = { services: [], unreachable: [] } as never;

function render(ui: ReactElement) {
  return rtlRender(<OperatorI18nProvider session={SESSION}>{ui}</OperatorI18nProvider>);
}

afterEach(() => {
  cleanup(); grantCalls = []; prefsCalls = [];
  sallaInstallCalls = 0; sallaDisconnectCalls = 0; sallaConnected = false;
});

describe('«تحالف استراتيجي»', () => {
  it('shows the current cap and the grant form', async () => {
    render(<CouponsScreen session={SESSION} catalog={catalog} />);
    await waitFor(() => expect(screen.getByText('20%')).toBeTruthy());
    expect(screen.getByText('كوّن تحالفاً')).toBeTruthy();
  });

  it('shows the log tab by default, with a real refusal reason', async () => {
    render(<CouponsScreen session={SESSION} catalog={catalog} />);
    await waitFor(() => expect(screen.getAllByText('تجاوزت سقفك الحالي').length).toBeGreaterThan(0));
  });

  it('switches to the stats tab and renders the tier ladder', async () => {
    render(<CouponsScreen session={SESSION} catalog={catalog} />);
    fireEvent.click(screen.getByText('الإحصائيات'));
    await waitFor(() => expect(screen.getByTestId('coupon-ladder')).toBeTruthy());
    expect(screen.getByTestId('coupon-kpi-month').textContent).toContain('3');
  });

  it('the live phone hint warns when there is already an alliance with the beneficiary this month', async () => {
    render(<CouponsScreen session={SESSION} catalog={catalog} />);
    const phoneInput = screen.getByPlaceholderText('05xxxxxxxx');
    fireEvent.change(phoneInput, { target: { value: '0512345699' } });
    await waitFor(() => expect(screen.getByText('عندك تحالف معه هذا الشهر بالفعل')).toBeTruthy(),
      { timeout: 1000 });
  });

  it('the live phone hint flags an unregistered number', async () => {
    render(<CouponsScreen session={SESSION} catalog={catalog} />);
    const phoneInput = screen.getByPlaceholderText('05xxxxxxxx');
    fireEvent.change(phoneInput, { target: { value: '0512345600' } });
    await waitFor(() => expect(screen.getByText('هذا الرقم ليس محلاً مسجّلاً عندنا')).toBeTruthy(),
      { timeout: 1000 });
  });

  it('shows the visit-screen switch and toggles it off with one press', async () => {
    render(<CouponsScreen session={SESSION} catalog={catalog} />);
    const toggle = await screen.findByTestId('coupon-prefs-toggle');
    expect(toggle.getAttribute('aria-checked')).toBe('true');
    fireEvent.click(toggle);
    await waitFor(() => expect(prefsCalls).toEqual([{ visit_grant_enabled: false }]));
  });

  describe('Salla connect', () => {
    it('shows a connect button when no store is linked', async () => {
      render(<CouponsScreen session={SESSION} catalog={catalog} />);
      const button = await screen.findByTestId('salla-connect-button');
      expect(button.textContent).toBe('اربط متجر سلة');
      expect(screen.queryByTestId('salla-connected-badge')).toBeNull();
    });

    it('shows the connected badge and store name when already linked', async () => {
      sallaConnected = true;
      render(<CouponsScreen session={SESSION} catalog={catalog} />);
      await waitFor(() => expect(screen.getByTestId('salla-connected-badge')).toBeTruthy());
      expect(screen.getByText('مرتبط بمتجر «متجر الاختبار»')).toBeTruthy();
    });

    it('opens a popup with the real install URL on click', async () => {
      const openSpy = vi.spyOn(window, 'open').mockReturnValue({ closed: false } as Window);
      render(<CouponsScreen session={SESSION} catalog={catalog} />);
      const button = await screen.findByTestId('salla-connect-button');
      fireEvent.click(button);
      await waitFor(() => expect(sallaInstallCalls).toBe(1));
      expect(openSpy).toHaveBeenCalledWith(
        'https://accounts.salla.sa/oauth2/auth?client_id=x', 'salla-connect',
        expect.stringContaining('width=520'));
      openSpy.mockRestore();
    });

    it('falls back to a full-page redirect when the popup is blocked', async () => {
      vi.spyOn(window, 'open').mockReturnValue(null);
      // jsdom's `window.location.href` setter throws on navigation — redefine just that one
      // accessor for this test rather than replacing the whole Location object (which fights
      // its own TS type), and restore it unconditionally afterwards.
      const originalDescriptor = Object.getOwnPropertyDescriptor(window, 'location')!;
      let hrefSet = '';
      Object.defineProperty(window, 'location', {
        configurable: true,
        value: { ...window.location, set href(v: string) { hrefSet = v; }, get href() { return hrefSet; } },
      });

      try {
        render(<CouponsScreen session={SESSION} catalog={catalog} />);
        const button = await screen.findByTestId('salla-connect-button');
        fireEvent.click(button);
        await waitFor(() => expect(hrefSet).toBe(
          'https://accounts.salla.sa/oauth2/auth?client_id=x'));
      } finally {
        Object.defineProperty(window, 'location', originalDescriptor);
        vi.restoreAllMocks();
      }
    });

    it('refreshes to connected when the callback page posts a success message', async () => {
      vi.spyOn(window, 'open').mockReturnValue({ closed: false } as Window);
      sallaConnected = false;
      render(<CouponsScreen session={SESSION} catalog={catalog} />);
      const button = await screen.findByTestId('salla-connect-button');
      fireEvent.click(button);
      await waitFor(() => expect(sallaInstallCalls).toBe(1));

      sallaConnected = true;   // the "backend" now reports connected, once asked again
      act(() => {
        window.dispatchEvent(new MessageEvent('message', {
          data: { source: 'raje3:salla-connect', ok: true, store_name: 'متجر الاختبار' },
        }));
      });

      await waitFor(() => expect(screen.getByTestId('salla-connected-badge')).toBeTruthy());
      vi.restoreAllMocks();
    });

    it('shows the server-sent refusal message when the callback posts a failure', async () => {
      vi.spyOn(window, 'open').mockReturnValue({ closed: false } as Window);
      render(<CouponsScreen session={SESSION} catalog={catalog} />);
      const button = await screen.findByTestId('salla-connect-button');
      fireEvent.click(button);
      await waitFor(() => expect(sallaInstallCalls).toBe(1));

      act(() => {
        window.dispatchEvent(new MessageEvent('message', {
          data: { source: 'raje3:salla-connect', ok: false, message: 'تعذّر إتمام الربط' },
        }));
      });

      await waitFor(() => expect(screen.getByText('تعذّر إتمام الربط')).toBeTruthy());
      vi.restoreAllMocks();
    });

    it('ignores an unrelated postMessage from another script on the page', async () => {
      render(<CouponsScreen session={SESSION} catalog={catalog} />);
      await screen.findByTestId('salla-connect-button');
      window.dispatchEvent(new MessageEvent('message', { data: { source: 'some-other-widget' } }));
      // Nothing throws, nothing changes — still shows the disconnected state.
      expect(screen.getByTestId('salla-connect-button')).toBeTruthy();
    });

    it('shows a disconnect button beside the connected badge, never when disconnected', async () => {
      sallaConnected = true;
      render(<CouponsScreen session={SESSION} catalog={catalog} />);
      await screen.findByTestId('salla-disconnect-button');
      expect(screen.queryByTestId('salla-connect-button')).toBeNull();
    });

    it('does not disconnect when the confirmation is declined', async () => {
      sallaConnected = true;
      vi.spyOn(window, 'confirm').mockReturnValue(false);
      render(<CouponsScreen session={SESSION} catalog={catalog} />);
      const button = await screen.findByTestId('salla-disconnect-button');
      fireEvent.click(button);
      expect(sallaDisconnectCalls).toBe(0);
      expect(screen.getByTestId('salla-connected-badge')).toBeTruthy();
      vi.restoreAllMocks();
    });

    it('disconnects and switches back to the connect button once confirmed', async () => {
      sallaConnected = true;
      vi.spyOn(window, 'confirm').mockReturnValue(true);
      render(<CouponsScreen session={SESSION} catalog={catalog} />);
      const button = await screen.findByTestId('salla-disconnect-button');
      fireEvent.click(button);
      await waitFor(() => expect(sallaDisconnectCalls).toBe(1));
      await waitFor(() => expect(screen.getByTestId('salla-connect-button')).toBeTruthy());
      expect(screen.queryByTestId('salla-connected-badge')).toBeNull();
      vi.restoreAllMocks();
    });
  });
});
