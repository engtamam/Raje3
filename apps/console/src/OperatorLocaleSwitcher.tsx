/**
 * The switch itself — a plain `<select>`, deliberately not a fancier picker. Five options, no
 * search, no icons to learn; a control an operator taps once a shift at most does not earn a
 * custom widget. Mounted once, in the shell's own `railSlot` (App.tsx) — it used to live inside
 * Visit.tsx alone, back when Visit was the only screen reading operator-i18n; Bookings, Points
 * and Services all read it now too, so one shared control in the rail replaced four separate
 * copies (or three screens silently missing it).
 *
 * HIDDEN FOR AN ACCOUNT WITH NO Operator ROW — the owner, chiefly. It used to render for him
 * too: he picked a language, the screen flipped for an instant, and reverted straight back with
 * nothing said anywhere, because `PATCH .../operators/me/locale` structurally 404s for an
 * account that is not an `Operator` (see operator-i18n.tsx's own `hasOperatorRow` note). A
 * control that can only ever fail for him is worse than no control.
 */
import { OPERATOR_LOCALES, useOperatorI18n } from './operator-i18n';

export function OperatorLocaleSwitcher() {
  const { locale, setLocale, ready, hasOperatorRow, saveError } = useOperatorI18n();
  if (!ready || !hasOperatorRow) return null;
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
