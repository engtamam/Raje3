/**
 * operator-i18n.tsx — the fallback chain must land on Arabic (never English, never a blank),
 * direction must be a table (Urdu is RTL too, not just Arabic), and the preference must come
 * from the account's own platform-wide setting, never localStorage — and now reaches the owner
 * too (2026-09-11), not just a hired operator.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import {
  OperatorI18nProvider, useOperatorI18n, isRtl, applyOperatorDir,
  registerOperatorStrings, tf, type OperatorLocale,
} from './operator-i18n';
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

registerOperatorStrings({
  ar: { 'x.only.ar': 'عربي', 'x.both': 'مرحبا {name}' },
  en: { 'x.both': 'hello {name}', 'x.only.en': 'english only' },
});

function Probe() {
  const { t, locale, setLocale, ready, saveError } = useOperatorI18n();
  return (
    <div>
      <span data-testid="locale">{locale}</span>
      <span data-testid="ready">{String(ready)}</span>
      <span data-testid="save-error">{String(saveError)}</span>
      <span data-testid="only-ar">{t('x.only.ar')}</span>
      <span data-testid="both">{t('x.both')}</span>
      <span data-testid="unknown">{t('x.totally.unknown.key')}</span>
      <button onClick={() => setLocale('ur')}>ur</button>
      <button onClick={() => setLocale('en')}>en</button>
    </div>
  );
}

describe('isRtl / applyOperatorDir', () => {
  it('Arabic and Urdu are RTL; English, Hausa, Filipino are LTR', () => {
    expect(isRtl('ar')).toBe(true);
    expect(isRtl('ur')).toBe(true);
    expect(isRtl('en')).toBe(false);
    expect(isRtl('ha')).toBe(false);
    expect(isRtl('fil')).toBe(false);
  });

  it('applies dir/lang as a table lookup, not a ternary hardcoded to one RTL language', () => {
    const el = document.createElement('html');
    applyOperatorDir('ur', el);
    expect(el.getAttribute('dir')).toBe('rtl');
    expect(el.getAttribute('lang')).toBe('ur');
    applyOperatorDir('ha', el);
    expect(el.getAttribute('dir')).toBe('ltr');
  });
});

describe('translate fallback chain', () => {
  it('falls back to Arabic, never English, for a key missing in the current locale', async () => {
    getMyLocaleMock = vi.fn().mockResolvedValue({ locale: 'en' });
    render(<OperatorI18nProvider session={SESSION}><Probe /></OperatorI18nProvider>);
    await waitFor(() => expect(screen.getByTestId('ready').textContent).toBe('true'));
    expect(screen.getByTestId('locale').textContent).toBe('en');
    // 'x.only.ar' has no English entry — must show the Arabic original, not English, not blank.
    expect(screen.getByTestId('only-ar').textContent).toBe('عربي');
    expect(screen.getByTestId('both').textContent).toBe('hello {name}');
  });

  it('an unknown key returns the key itself, never a crash or a blank', async () => {
    getMyLocaleMock = vi.fn().mockResolvedValue({ locale: '' });
    render(<OperatorI18nProvider session={SESSION}><Probe /></OperatorI18nProvider>);
    await waitFor(() => expect(screen.getByTestId('ready').textContent).toBe('true'));
    expect(screen.getByTestId('unknown').textContent).toBe('x.totally.unknown.key');
  });
});

describe('account-backed preference, not localStorage', () => {
  it('reads the locale from the account’s own platform-wide setting on mount', async () => {
    getMyLocaleMock = vi.fn().mockResolvedValue({ locale: 'ur' });
    render(<OperatorI18nProvider session={SESSION}><Probe /></OperatorI18nProvider>);
    await waitFor(() => expect(screen.getByTestId('locale').textContent).toBe('ur'));
    expect(getMyLocaleMock).toHaveBeenCalledWith(SESSION);
  });

  it('an account with no preference saved yet still becomes ready, with Arabic default', async () => {
    getMyLocaleMock = vi.fn().mockResolvedValue({ locale: '' });
    render(<OperatorI18nProvider session={SESSION}><Probe /></OperatorI18nProvider>);
    await waitFor(() => expect(screen.getByTestId('ready').textContent).toBe('true'));
    expect(screen.getByTestId('locale').textContent).toBe('ar');
  });

  it('a failed read still becomes ready, with Arabic default — never a stuck loading screen', async () => {
    getMyLocaleMock = vi.fn().mockRejectedValue(new Error('network'));
    render(<OperatorI18nProvider session={SESSION}><Probe /></OperatorI18nProvider>);
    await waitFor(() => expect(screen.getByTestId('ready').textContent).toBe('true'));
    expect(screen.getByTestId('locale').textContent).toBe('ar');
  });

  it('changing locale writes it to the account, not to localStorage', async () => {
    getMyLocaleMock = vi.fn().mockResolvedValue({ locale: 'ar' });
    setMyLocaleMock = vi.fn().mockResolvedValue(undefined);
    const setItemSpy = vi.spyOn(Storage.prototype, 'setItem');

    render(<OperatorI18nProvider session={SESSION}><Probe /></OperatorI18nProvider>);
    await waitFor(() => expect(screen.getByTestId('ready').textContent).toBe('true'));

    fireEvent.click(screen.getByText('ur'));
    await waitFor(() => expect(screen.getByTestId('locale').textContent).toBe('ur'));
    expect(setMyLocaleMock).toHaveBeenCalledWith(SESSION, 'ur');
    expect(setItemSpy).not.toHaveBeenCalled();
    setItemSpy.mockRestore();
  });

  it('rolls back the optimistic switch if the account write is refused', async () => {
    getMyLocaleMock = vi.fn().mockResolvedValue({ locale: 'ar' });
    setMyLocaleMock = vi.fn().mockRejectedValue(new Error('refused'));

    render(<OperatorI18nProvider session={SESSION}><Probe /></OperatorI18nProvider>);
    await waitFor(() => expect(screen.getByTestId('ready').textContent).toBe('true'));

    fireEvent.click(screen.getByText('ur'));
    // OPTIMISTIC FIRST — the switch feels instant even though the request is in flight.
    await waitFor(() => expect(screen.getByTestId('locale').textContent).toBe('ur'));
    // THEN ROLLS BACK once the account refuses it — the account is the truth, not the click.
    await waitFor(() => expect(screen.getByTestId('locale').textContent).toBe('ar'));
    // AND IT IS SAID, not just reverted silently — the exact defect an owner used to hit.
    expect(screen.getByTestId('save-error').textContent).toBe('true');
  });

  it('a fresh attempt clears a previous save error', async () => {
    getMyLocaleMock = vi.fn().mockResolvedValue({ locale: 'ar' });
    setMyLocaleMock = vi.fn()
      .mockRejectedValueOnce(new Error('refused'))
      .mockResolvedValueOnce(undefined);

    render(<OperatorI18nProvider session={SESSION}><Probe /></OperatorI18nProvider>);
    await waitFor(() => expect(screen.getByTestId('ready').textContent).toBe('true'));

    fireEvent.click(screen.getByText('ur'));
    await waitFor(() => expect(screen.getByTestId('save-error').textContent).toBe('true'));

    fireEvent.click(screen.getByText('en'));
    await waitFor(() => expect(screen.getByTestId('locale').textContent).toBe('en'));
    expect(screen.getByTestId('save-error').textContent).toBe('false');
  });
});

describe('useOperatorI18n outside the provider', () => {
  it('throws loudly rather than silently falling back to raw keys on screen', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => render(<Probe />)).toThrow('useOperatorI18n() outside <OperatorI18nProvider>');
    spy.mockRestore();
  });
});

describe('tf() interpolation', () => {
  it('substitutes named placeholders after translation, regardless of key order', () => {
    const t = (k: string) => (k === 'greet' ? 'hi {name}, you have {n} pts' : k);
    expect(tf(t, 'greet', { name: 'سارة', n: 5 })).toBe('hi سارة, you have 5 pts');
  });

  it('leaves an unmatched placeholder as-is rather than silently dropping it', () => {
    const t = () => 'value: {missing}';
    expect(tf(t, 'x', {})).toBe('value: {missing}');
  });
});
