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

// `tenant` MATTERS NOW, NOT JUST `token` — `isSignedIn()` (session.ts) requires both, and
// `setLocale` (operator-i18n.tsx) reads it to decide whether a failed save is a real account's
// refusal (revert + show the error) or a pre-login pick with no account to persist against yet
// (keep the local choice, say nothing). This fixture represents a genuine signed-in account, so
// it needs both fields the same way a real session always carries them.
const SESSION = { tenant: 't1', token: 'tok-1' } as Session;

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
    // A REAL MENU, NOT A NATIVE `<select>` — the toggle button opens a floating listbox of
    // per-language option buttons (OperatorLocaleSwitcher.tsx's own 2026-09-16 rebuild); picking
    // a language is a click on one of those, not a `change` event on the toggle itself.
    await waitFor(() => expect(screen.getByLabelText('Language / اللغة')).toBeTruthy());
    fireEvent.click(screen.getByLabelText('Language / اللغة'));
    fireEvent.click(screen.getByRole('option', { name: 'English' }));
    await waitFor(() => expect(screen.getByText(/تعذّر حفظ اللغة/)).toBeTruthy());
    // AND IT ROLLED BACK — the account, not the click, is the truth. Picking a menu option closes
    // it, so the toggle button's own displayed label (never translated — each language names
    // itself, in its own script) is what still shows the real, reverted locale.
    expect(screen.getByLabelText('Language / اللغة').textContent).toContain('العربية');
  });
});
