/**
 * «لوحة الإدارة» — the one property worth a render test at this phase: a wrong credential
 * refuses cleanly, a right one hands the session up, and there is no signup path to find at all.
 * Plus «نسيت كلمة المرور؟»: request-code-and-reset is ONE call (never verify-then-reset), and
 * the identifier field is labelled for what this deployment actually logs in with (a phone).
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { AdminDoor } from './AdminDoor';
import { AdminRefused } from './api';

let signInMock: (id: string, password: string, code: string) => Promise<{ access_token: string }>;
let requestResetMock: (id: string) => Promise<void>;
let resetMock: (id: string, code: string, newPassword: string) => Promise<void>;

vi.mock('./api', async (importOriginal) => {
  const real = await importOriginal<typeof import('./api')>();
  return {
    ...real,
    signIn: (id: string, password: string, code: string) => signInMock(id, password, code),
    requestPasswordResetOtp: (id: string) => requestResetMock(id),
    resetPassword: (id: string, code: string, newPassword: string) => resetMock(id, code, newPassword),
  };
});

afterEach(() => vi.clearAllMocks());

describe('AdminDoor', () => {
  it('has no signup path anywhere on the door', () => {
    render(<AdminDoor onSignedIn={() => {}} />);
    expect(screen.queryByText(/تسجيل حساب|إنشاء حساب|طلب جديد/)).toBeFalsy();
  });

  it('a wrong credential shows the real refusal, not a generic one', async () => {
    signInMock = () => Promise.reject(new AdminRefused('البريد أو كلمة المرور غير صحيحة.'));
    render(<AdminDoor onSignedIn={() => {}} />);

    fireEvent.change(screen.getByLabelText('رقم الجوال', { exact: false }), { target: { value: '0500000001' } });
    fireEvent.change(screen.getByLabelText('كلمة المرور', { exact: false }), { target: { value: 'wrong' } });
    fireEvent.click(screen.getByText('تسجيل الدخول'));

    await waitFor(() => expect(screen.getByRole('alert').textContent)
      .toBe('البريد أو كلمة المرور غير صحيحة.'));
  });

  it('a correct sign-in hands the session up', async () => {
    signInMock = () => Promise.resolve({ access_token: 'tok-1' });
    const onSignedIn = vi.fn();
    render(<AdminDoor onSignedIn={onSignedIn} />);

    fireEvent.change(screen.getByLabelText('رقم الجوال', { exact: false }), { target: { value: '0500000001' } });
    fireEvent.change(screen.getByLabelText('كلمة المرور', { exact: false }), { target: { value: 'right-password' } });
    fireEvent.click(screen.getByText('تسجيل الدخول'));

    await waitFor(() => expect(onSignedIn).toHaveBeenCalledWith({ access_token: 'tok-1' }));
  });

  it('MFA_REQUIRED opens the code field instead of a dead-end error', async () => {
    signInMock = () => Promise.reject(new AdminRefused('أدخل رمز التحقق.', 'MFA_REQUIRED'));
    render(<AdminDoor onSignedIn={() => {}} />);

    fireEvent.change(screen.getByLabelText('رقم الجوال', { exact: false }), { target: { value: '0500000001' } });
    fireEvent.change(screen.getByLabelText('كلمة المرور', { exact: false }), { target: { value: 'right-password' } });
    fireEvent.click(screen.getByText('تسجيل الدخول'));

    await waitFor(() => expect(screen.getByLabelText('رمز التحقق', { exact: false })).toBeTruthy());
  });

  it('forgot-password requests a code, then resets in ONE call with both code and new password', async () => {
    requestResetMock = vi.fn().mockResolvedValue(undefined);
    resetMock = vi.fn().mockResolvedValue(undefined);
    render(<AdminDoor onSignedIn={() => {}} />);

    fireEvent.click(screen.getByText('نسيت كلمة المرور؟'));
    fireEvent.change(screen.getByLabelText('رقم الجوال', { exact: false }), { target: { value: '0500000001' } });
    fireEvent.click(screen.getByText('إرسال رمز التحقق'));

    await waitFor(() => expect(requestResetMock).toHaveBeenCalledWith('0500000001'));
    // The screen never calls a separate "verify" — code and new password are collected together
    // and sent in ONE resetPassword call, matching identity-service's own single-route shape.
    await waitFor(() => expect(screen.getByLabelText('رمز التحقق', { exact: false })).toBeTruthy());

    fireEvent.change(screen.getByLabelText('رمز التحقق', { exact: false }), { target: { value: '123456' } });
    fireEvent.change(screen.getByLabelText('كلمة المرور الجديدة', { exact: false }),
                     { target: { value: 'a-strong-new-password' } });
    fireEvent.click(screen.getByText('تعيين كلمة المرور'));

    await waitFor(() => expect(resetMock)
      .toHaveBeenCalledWith('0500000001', '123456', 'a-strong-new-password'));
  });

  it('a wrong or expired code on reset shows the real refusal', async () => {
    requestResetMock = vi.fn().mockResolvedValue(undefined);
    resetMock = vi.fn().mockRejectedValue(new AdminRefused('الرمز غير صحيح أو منتهٍ.', 'INVALID_RESET'));
    render(<AdminDoor onSignedIn={() => {}} />);

    fireEvent.click(screen.getByText('نسيت كلمة المرور؟'));
    fireEvent.change(screen.getByLabelText('رقم الجوال', { exact: false }), { target: { value: '0500000001' } });
    fireEvent.click(screen.getByText('إرسال رمز التحقق'));
    await waitFor(() => expect(screen.getByLabelText('رمز التحقق', { exact: false })).toBeTruthy());

    fireEvent.change(screen.getByLabelText('رمز التحقق', { exact: false }), { target: { value: '000000' } });
    fireEvent.change(screen.getByLabelText('كلمة المرور الجديدة', { exact: false }),
                     { target: { value: 'a-strong-new-password' } });
    fireEvent.click(screen.getByText('تعيين كلمة المرور'));

    await waitFor(() => expect(screen.getByRole('alert').textContent).toBe('الرمز غير صحيح أو منتهٍ.'));
  });
});
