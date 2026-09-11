/**
 * The switch itself — a plain `<select>`, deliberately not a fancier picker. Five options, no
 * search, no icons to learn; a control an operator taps once a shift at most does not earn a
 * custom widget. Mounted once, in the shell's own `railSlot` (App.tsx) — it used to live inside
 * Visit.tsx alone, back when Visit was the only screen reading operator-i18n; Bookings, Points,
 * Services and «الاشتراك» all read it now too, so one shared control in the rail replaced
 * several separate copies (or screens silently missing it).
 *
 * VISIBLE TO EVERY LOGGED-IN ACCOUNT NOW, THE OWNER INCLUDED (2026-09-11). It used to hide
 * itself for an account with no `Operator` row — the owner, chiefly — because the old,
 * Operator-only save route structurally 404d for him. `useOperatorI18n()` now reads/writes a
 * platform-wide preference (`/api/v1/account/me/locale`) that needs no Operator row at all, so
 * the one thing left to wait on is the initial read (`ready`).
 */
import { OPERATOR_LOCALES, useOperatorI18n } from './operator-i18n';

export function OperatorLocaleSwitcher() {
  const { locale, setLocale, ready, saveError } = useOperatorI18n();
  if (!ready) return null;
  return (
    <div className="flex items-center gap-2">
      {saveError ? (
        <span role="alert" className="text-xs text-danger">تعذّر حفظ اللغة — حاول مرة أخرى.</span>
      ) : null}
      <select
        value={locale}
        onChange={(e) => setLocale(e.target.value as typeof locale)}
        aria-label="Language / اللغة"
        dir="ltr"
        className="h-9 rounded-lg border border-border-subtle bg-surface-1 px-2 text-sm"
      >
        {OPERATOR_LOCALES.map((l) => (
          <option key={l.value} value={l.value}>{l.label}</option>
        ))}
      </select>
    </div>
  );
}
