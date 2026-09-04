/**
 * The switch itself — a plain `<select>`, deliberately not a fancier picker. Five options, no
 * search, no icons to learn; a control an operator taps once a shift at most does not earn a
 * custom widget. Placed on the screen itself for now (not the shared shell chrome) because only
 * Visit.tsx reads operator-i18n today — lift it to the shell once a second screen migrates, so
 * it is not duplicated per screen.
 */
import { OPERATOR_LOCALES, useOperatorI18n } from './operator-i18n';

export function OperatorLocaleSwitcher() {
  const { locale, setLocale, ready } = useOperatorI18n();
  return (
    <select
      value={locale}
      onChange={(e) => setLocale(e.target.value as typeof locale)}
      disabled={!ready}
      aria-label="Language / اللغة"
      dir="ltr"
      className="h-9 rounded-lg border border-border-subtle bg-surface-1 px-2 text-sm"
    >
      {OPERATOR_LOCALES.map((l) => (
        <option key={l.value} value={l.value}>{l.label}</option>
      ))}
    </select>
  );
}
