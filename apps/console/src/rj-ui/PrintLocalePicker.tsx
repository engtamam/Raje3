/**
 * A compact language pick sitting NEXT TO a print/export button, never a modal — printing is a
 * one-click action today and this must not turn it into a two-step flow for the common case
 * (print in my own language). The caller seeds `value` from the operator's own current locale
 * (`useOperatorI18n().locale`) on first mount only; changing it here never touches the console's
 * own language switcher in الإعدادات — it is the PRINT'S OWN choice, because an operator reading
 * the console in Arabic may still need to hand a technician (or a customer) a copy in their own
 * language. Shared by every export surface (procedure checklists, staff performance, …) rather
 * than copied per screen, so a seventh operator locale is one edit, not N.
 */
import { Select } from './Field';
import { OPERATOR_LOCALES, type OperatorLocale } from '../operator-i18n';

export function PrintLocalePicker({ value, onChange, label }: {
  value: OperatorLocale; onChange: (l: OperatorLocale) => void; label: string;
}) {
  return (
    <Select
      aria-label={label}
      value={value}
      onChange={(e) => onChange(e.target.value as OperatorLocale)}
      className="w-32"
    >
      {OPERATOR_LOCALES.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
    </Select>
  );
}
