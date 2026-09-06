/**
 * OperatorLocaleSwitcher — hidden entirely for an account with no Operator row (the owner,
 * chiefly), because `PATCH .../operators/me/locale` structurally 404s for one and the switch
 * used to flip and instantly, silently revert for him with nothing said anywhere. A real
 * operator sees the switch, and a genuine save failure is said out loud, not just rolled back.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { OperatorI18nProvider } from './operator-i18n';
import { OperatorLocaleSwitcher } from './OperatorLocaleSwitcher';
import type { Session } from './session';

const SESSION = { token: 'tok-1' } as Session;

let getMyOperatorMock: ReturnType<typeof vi.fn>;
let setMyOperatorLocaleMock: ReturnType<typeof vi.fn>;

vi.mock('./api', async (importOriginal) => {
  const real = await importOriginal<typeof import('./api')>();
  return {
    ...real,
    getMyOperator: (...args: unknown[]) => getMyOperatorMock(...args),
    setMyOperatorLocale: (...args: unknown[]) => setMyOperatorLocaleMock(...args),
  };
});

afterEach(() => vi.clearAllMocks());

function open() {
  return render(
    <OperatorI18nProvider session={SESSION}><OperatorLocaleSwitcher /></OperatorI18nProvider>,
  );
}

describe('OperatorLocaleSwitcher', () => {
  it('renders nothing for an account with no operator row — the owner', async () => {
    getMyOperatorMock = vi.fn().mockResolvedValue(null);
    open();
    // Give the provider's own read a turn to settle before asserting absence.
    await waitFor(() => expect(getMyOperatorMock).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 0));
    expect(screen.queryByLabelText('Language / اللغة')).toBeNull();
  });

  it('renders the switch for a real operator', async () => {
    getMyOperatorMock = vi.fn().mockResolvedValue({ locale: 'ar' });
    open();
    await waitFor(() => expect(screen.getByLabelText('Language / اللغة')).toBeTruthy());
  });

  it('says the save failed rather than reverting silently with nothing shown', async () => {
    getMyOperatorMock = vi.fn().mockResolvedValue({ locale: 'ar' });
    setMyOperatorLocaleMock = vi.fn().mockRejectedValue(new Error('refused'));
    open();
    await waitFor(() => expect(screen.getByLabelText('Language / اللغة')).toBeTruthy());
    fireEvent.change(screen.getByLabelText('Language / اللغة'), { target: { value: 'en' } });
    await waitFor(() => expect(screen.getByText(/تعذّر حفظ اللغة/)).toBeTruthy());
    // AND IT ROLLED BACK — the account, not the click, is the truth.
    expect((screen.getByLabelText('Language / اللغة') as HTMLSelectElement).value).toBe('ar');
  });
});
