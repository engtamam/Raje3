/** `offers.ts`'s own strings — its `remaining()` countdown labels. Same per-module registration
 *  pattern as every screen. */
import { registerOperatorStrings } from './operator-i18n';

registerOperatorStrings({
  ar: {
    'offers.remaining.days': 'يبقى {days} يوماً',
    'offers.remaining.hours': 'تبقّى {hours} ساعات',
    'offers.remaining.hour': 'ينتهي خلال ساعة',
  },
  en: {
    'offers.remaining.days': '{days} day(s) left',
    'offers.remaining.hours': '{hours} hour(s) left',
    'offers.remaining.hour': 'Ends within an hour',
  },
  // MACHINE-ASSISTED, NOT NATIVE-REVIEWED — same flag other cross-cutting i18n files in this
  // repo carry for these same four locales.
  ur: {
    'offers.remaining.days': '{days} دن باقی',
    'offers.remaining.hours': '{hours} گھنٹے باقی',
    'offers.remaining.hour': 'ایک گھنٹے میں ختم ہو جائے گا',
  },
  ha: {
    'offers.remaining.days': 'Kwana {days} sun rage',
    'offers.remaining.hours': "Sa'o'i {hours} sun rage",
    'offers.remaining.hour': "Zai ƙare cikin sa'a ɗaya",
  },
  fil: {
    'offers.remaining.days': '{days} araw na lang',
    'offers.remaining.hours': '{hours} oras na lang',
    'offers.remaining.hour': 'Matatapos sa loob ng isang oras',
  },
  bn: {
    'offers.remaining.days': '{days} দিন বাকি',
    'offers.remaining.hours': '{hours} ঘণ্টা বাকি',
    'offers.remaining.hour': 'এক ঘণ্টার মধ্যে শেষ হবে',
  },
});
