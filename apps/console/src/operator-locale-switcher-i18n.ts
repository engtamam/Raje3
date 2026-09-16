/** `OperatorLocaleSwitcher.tsx`'s own strings — same per-screen registration pattern as every
 *  other screen. Mounted everywhere (TopBar and now Door), so this file's own locale set matches
 *  the platform-wide six rather than a screen-scoped subset. */
import { registerOperatorStrings } from './operator-i18n';

registerOperatorStrings({
  ar: {
    'localeSwitcher.saveFailed': 'تعذّر حفظ اللغة — حاول مرة أخرى.',
    'localeSwitcher.ariaLabel': 'Language / اللغة',
  },
  en: {
    'localeSwitcher.saveFailed': 'Could not save the language — try again.',
    'localeSwitcher.ariaLabel': 'Language / اللغة',
  },
  // MACHINE-ASSISTED, NOT NATIVE-REVIEWED — same flag other cross-cutting i18n files in this
  // repo carry for these same four locales.
  ur: {
    'localeSwitcher.saveFailed': 'زبان محفوظ نہیں ہو سکی — دوبارہ کوشش کریں۔',
    'localeSwitcher.ariaLabel': 'Language / اللغة',
  },
  ha: {
    'localeSwitcher.saveFailed': 'An kasa ajiye harshen — a sake gwadawa.',
    'localeSwitcher.ariaLabel': 'Language / اللغة',
  },
  fil: {
    'localeSwitcher.saveFailed': 'Hindi na-save ang wika — subukan ulit.',
    'localeSwitcher.ariaLabel': 'Language / اللغة',
  },
  bn: {
    'localeSwitcher.saveFailed': 'ভাষা সংরক্ষণ করা যায়নি — আবার চেষ্টা করুন।',
    'localeSwitcher.ariaLabel': 'Language / اللغة',
  },
});
