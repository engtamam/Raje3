/**
 * «لوحة الإدارة» — the one property worth a render test at this phase: a wrong credential
 * refuses cleanly, a right one hands the session up, and there is no signup path to find at all.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { AdminDoor } from './AdminDoor';
import { AdminRefused } from './api';

let signInMock: (email: string, password: string, code: string) => Promise<{ access_token: string }>;

vi.mock('./api', async (importOriginal) => {
  const real = await importOriginal<typeof import('./api')>();
  return {
    ...real,
    signIn: (email: string, password: string, code: string) => signInMock(email, password, code),
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

    fireEvent.change(screen.getByLabelText('البريد الإلكتروني', { exact: false }), { target: { value: 'a@raje3.sa' } });
    fireEvent.change(screen.getByLabelText('كلمة المرور', { exact: false }), { target: { value: 'wrong' } });
    fireEvent.click(screen.getByText('تسجيل الدخول'));

    await waitFor(() => expect(screen.getByRole('alert').textContent)
      .toBe('البريد أو كلمة المرور غير صحيحة.'));
  });

  it('a correct sign-in hands the session up', async () => {
    signInMock = () => Promise.resolve({ access_token: 'tok-1' });
    const onSignedIn = vi.fn();
    render(<AdminDoor onSignedIn={onSignedIn} />);

    fireEvent.change(screen.getByLabelText('البريد الإلكتروني', { exact: false }), { target: { value: 'a@raje3.sa' } });
    fireEvent.change(screen.getByLabelText('كلمة المرور', { exact: false }), { target: { value: 'right-password' } });
    fireEvent.click(screen.getByText('تسجيل الدخول'));

    await waitFor(() => expect(onSignedIn).toHaveBeenCalledWith({ access_token: 'tok-1' }));
  });

  it('MFA_REQUIRED opens the code field instead of a dead-end error', async () => {
    signInMock = () => Promise.reject(new AdminRefused('أدخل رمز التحقق.', 'MFA_REQUIRED'));
    render(<AdminDoor onSignedIn={() => {}} />);

    fireEvent.change(screen.getByLabelText('البريد الإلكتروني', { exact: false }), { target: { value: 'a@raje3.sa' } });
    fireEvent.change(screen.getByLabelText('كلمة المرور', { exact: false }), { target: { value: 'right-password' } });
    fireEvent.click(screen.getByText('تسجيل الدخول'));

    await waitFor(() => expect(screen.getByLabelText('رمز التحقق', { exact: false })).toBeTruthy());
  });
});
