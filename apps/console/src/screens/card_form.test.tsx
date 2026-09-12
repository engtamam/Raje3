import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render as rtlRender, screen } from '@testing-library/react';
import type { ReactElement } from 'react';

// OperatorI18nProvider (wrapped in around every render below) reads the account's locale on
// mount via `getMyLocale` — a real network call this file's own tests stub `fetch`/count network
// calls against (e.g. "«إلغاء» ... without touching the network"). Rejected here so the provider
// falls back to its own Arabic default instead of hitting the network at all — same pattern
// bookings.test.tsx already uses for the same reason.
vi.mock('../api', async (importOriginal) => {
  const real = await importOriginal<typeof import('../api')>();
  return { ...real, getMyLocale: async () => { throw new Error('not mocked'); } };
});

// CardForm now reads `useOperatorI18n()`. `vi.resetModules()` below re-imports CardForm fresh
// per test (needed so it re-reads the stubbed VITE_MOYASAR_PUBLISHABLE_KEY at import time) — a
// STATICALLY imported `OperatorI18nProvider` would then wrap it in a DIFFERENT module instance's
// React Context than the one CardForm's own freshly re-imported `useOperatorI18n` reads, which
// `useContext` treats as "no provider at all". So the provider is imported dynamically here too,
// from the same post-reset module registry as `CardForm` itself.
const SESSION_FOR_I18N = { tenant: 't1', operator: '', operatorName: '', token: 'tok' } as never;
async function render(ui: ReactElement) {
  const { OperatorI18nProvider } = await import('../operator-i18n');
  return rtlRender(<OperatorI18nProvider session={SESSION_FOR_I18N}>{ui}</OperatorI18nProvider>);
}

beforeEach(() => {
  vi.resetModules();
  vi.stubEnv('VITE_MOYASAR_PUBLISHABLE_KEY', 'pk_test_abc');
});

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function fill(el: HTMLElement, value: string) {
  fireEvent.change(el, { target: { value } });
}

describe('CardForm', () => {
  it('refuses an incomplete card number rather than submitting it', async () => {
    const { CardForm } = await import('./CardForm');
    const onToken = vi.fn();
    await render(<CardForm pending={{ kind: 'subscribe', planId: 'p1' }} onToken={onToken} onCancel={() => {}} />);

    fill(screen.getByLabelText('الاسم كما على البطاقة'), 'Ahmed Ali');
    fill(screen.getByLabelText('رقم البطاقة'), '4111');
    fill(screen.getByLabelText('الشهر'), '09');
    fill(screen.getByLabelText('السنة'), '2030');
    fill(screen.getByLabelText('رمز الأمان (CVC)'), '123');
    fireEvent.click(screen.getByRole('button', { name: 'تأكيد البطاقة' }));

    expect(await screen.findByText('رقم البطاقة غير مكتمل.')).toBeTruthy();
    expect(onToken).not.toHaveBeenCalled();
  });

  it('formats the card number into groups of four for display, digits only underneath', async () => {
    const { CardForm } = await import('./CardForm');
    await render(<CardForm pending={{ kind: 'subscribe', planId: 'p1' }} onToken={() => {}} onCancel={() => {}} />);
    const numberField = screen.getByLabelText('رقم البطاقة') as HTMLInputElement;
    fill(numberField, '4111111111111111');
    expect(numberField.value).toBe('4111 1111 1111 1111');
  });

  it('tokenises straight to Moyasar (never our own backend) and hands back the token when 3DS is skipped', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true, json: async () => ({ id: 'token_ok', status: 'active' }),
    }));
    const { CardForm } = await import('./CardForm');
    const onToken = vi.fn();
    await render(<CardForm pending={{ kind: 'subscribe', planId: 'p1' }} onToken={onToken} onCancel={() => {}} />);

    fill(screen.getByLabelText('الاسم كما على البطاقة'), 'Ahmed Ali');
    fill(screen.getByLabelText('رقم البطاقة'), '4111111111111111');
    fill(screen.getByLabelText('الشهر'), '09');
    fill(screen.getByLabelText('السنة'), '2030');
    fill(screen.getByLabelText('رمز الأمان (CVC)'), '123');
    fireEvent.click(screen.getByRole('button', { name: 'تأكيد البطاقة' }));

    await vi.waitFor(() => expect(onToken).toHaveBeenCalledWith('token_ok'));
    const [calledUrl] = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0] as [string];
    expect(calledUrl).toBe('https://api.moyasar.com/v1/tokens');
  });

  it('«إلغاء» calls onCancel without touching the network', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    const { CardForm } = await import('./CardForm');
    const onCancel = vi.fn();
    await render(<CardForm pending={{ kind: 'subscribe', planId: 'p1' }} onToken={() => {}} onCancel={onCancel} />);
    fireEvent.click(screen.getByRole('button', { name: 'إلغاء' }));
    expect(onCancel).toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
