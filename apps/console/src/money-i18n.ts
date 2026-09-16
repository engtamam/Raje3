/** `money.ts`'s own strings — same per-module registration pattern as every screen. */
import { registerOperatorStrings } from './operator-i18n';

registerOperatorStrings({
  ar: { 'money.riyal': 'ريال' },
  en: { 'money.riyal': 'SAR' },
  // MACHINE-ASSISTED, NOT NATIVE-REVIEWED — same flag other cross-cutting i18n files in this
  // repo carry for these same four locales.
  ur: { 'money.riyal': 'ریال' },
  ha: { 'money.riyal': 'Riyal' },
  fil: { 'money.riyal': 'Riyal' },
  bn: { 'money.riyal': 'রিয়াল' },
});
