/**
 * OperatorLocaleSwitcher — visible to any account, the owner included (2026-09-11), since it
 * now reads/writes a platform-wide preference that needs no Operator row at all. A genuine save
 * failure is said out loud, not just rolled back silently.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { OperatorI18nProvider } from './operator-i18n';
import { OperatorLocaleSwitcher } from './OperatorLocaleSwitcher';
import type { Session } from './session';

const SESSION = { token: 'tok-1' } as Session;

let getMyLocaleMock: ReturnType<typeof vi.fn>;
let setMyLocaleMock: ReturnType<typeof vi.fn>;

vi.mock('./api', async (importOriginal) => {
  const real = await importOriginal<typeof import('./api')>();
  return {
    ...real,
    getMyLocale: (...args: unknown[]) => getMyLocaleMock(...args),
    setMyLocale: (...args: unknown[]) => setMyLocaleMock(...args),
  };
});

afterEach(() => vi.clearAllMocks());

function open() {
  return render(
    <OperatorI18nProvider session={SESSION}><OperatorLocaleSwitcher /></OperatorI18nProvider>,
  );
}

describe('OperatorLocaleSwitcher', () => {
  it('renders the switch for an owner account (no operator row, no preference saved yet)', async () => {
    getMyLocaleMock = vi.fn().mockResolvedValue({ locale: '' });
    open();
    await waitFor(() => expect(screen.getByLabelText('Language / اللغة')).toBeTruthy());
  });

  it('renders the switch for a real operator too', async () => {
    getMyLocaleMock = vi.fn().mockResolvedValue({ locale: 'ar' });
    open();
    await waitFor(() => expect(screen.getByLabelText('Language / اللغة')).toBeTruthy());
  });

  it('says the save failed rather than reverting silently with nothing shown', async () => {
    getMyLocaleMock = vi.fn().mockResolvedValue({ locale: 'ar' });
    setMyLocaleMock = vi.fn().mockRejectedValue(new Error('refused'));
    open();
    await waitFor(() => expect(screen.getByLabelText('Language / اللغة')).toBeTruthy());
    fireEvent.change(screen.getByLabelText('Language / اللغة'), { target: { value: 'en' } });
    await waitFor(() => expect(screen.getByText(/تعذّر حفظ اللغة/)).toBeTruthy());
    // AND IT ROLLED BACK — the account, not the click, is the truth.
    expect((screen.getByLabelText('Language / اللغة') as HTMLSelectElement).value).toBe('ar');
  });
});
