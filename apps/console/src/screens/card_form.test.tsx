import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

beforeEach(() => {
  vi.resetModules();
  vi.stubEnv('VITE_MOYASAR_PUBLISHABLE_KEY', 'pk_test_abc');
});

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

function fill(el: HTMLElement, value: string) {
  fireEvent.change(el, { target: { value } });
}

describe('CardForm', () => {
  it('refuses an incomplete card number rather than submitting it', async () => {
    const { CardForm } = await import('./CardForm');
    const onToken = vi.fn();
    render(<CardForm pending={{ kind: 'subscribe', planId: 'p1' }} onToken={onToken} onCancel={() => {}} />);

    fill(screen.getByLabelText('الاسم كما على البطاقة'), 'Ahmed Ali');
    fill(screen.getByLabelText('رقم البطاقة'), '4111');
    fill(screen.getByLabelText('الشهر'), '09');
    fill(screen.getByLabelText('السنة'), '2030');
    fill(screen.getByLabelText('CVC'), '123');
    fireEvent.click(screen.getByRole('button', { name: 'تأكيد البطاقة' }));

    expect(await screen.findByText('رقم البطاقة غير مكتمل.')).toBeTruthy();
    expect(onToken).not.toHaveBeenCalled();
  });

  it('formats the card number into groups of four for display, digits only underneath', async () => {
    const { CardForm } = await import('./CardForm');
    render(<CardForm pending={{ kind: 'subscribe', planId: 'p1' }} onToken={() => {}} onCancel={() => {}} />);
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
    render(<CardForm pending={{ kind: 'subscribe', planId: 'p1' }} onToken={onToken} onCancel={() => {}} />);

    fill(screen.getByLabelText('الاسم كما على البطاقة'), 'Ahmed Ali');
    fill(screen.getByLabelText('رقم البطاقة'), '4111111111111111');
    fill(screen.getByLabelText('الشهر'), '09');
    fill(screen.getByLabelText('السنة'), '2030');
    fill(screen.getByLabelText('CVC'), '123');
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
    render(<CardForm pending={{ kind: 'subscribe', planId: 'p1' }} onToken={() => {}} onCancel={onCancel} />);
    fireEvent.click(screen.getByRole('button', { name: 'إلغاء' }));
    expect(onCancel).toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
