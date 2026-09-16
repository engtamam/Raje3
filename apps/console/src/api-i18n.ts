/** `api.ts`'s own strings — `sentenceFor`'s generic fallbacks, and the one message this file
 *  itself throws directly. Same per-module registration pattern as every screen. */
import { registerOperatorStrings } from './operator-i18n';

registerOperatorStrings({
  ar: {
    'api.sessionExpired': 'انتهت الجلسة — أعد فتح الشاشة.',
    'api.serviceDown': 'الخدمة لا تستجيب الآن. حاول بعد قليل.',
    'api.noConnection': 'لا يوجد اتصال — تحقّق من الشبكة وحاول مرة أخرى.',
    'api.searchUnavailable': 'تعذّر البحث الآن — حاول بعد لحظات',
  },
  en: {
    'api.sessionExpired': 'Your session expired — reopen this screen.',
    'api.serviceDown': 'The service is not responding right now. Try again shortly.',
    'api.noConnection': 'No connection — check the network and try again.',
    'api.searchUnavailable': 'Search is unavailable right now — try again in a moment.',
  },
  // MACHINE-ASSISTED, NOT NATIVE-REVIEWED — same flag other cross-cutting i18n files in this
  // repo carry for these same four locales.
  ur: {
    'api.sessionExpired': 'سیشن ختم ہو گیا — یہ اسکرین دوبارہ کھولیں۔',
    'api.serviceDown': 'سروس ابھی جواب نہیں دے رہی۔ تھوڑی دیر بعد کوشش کریں۔',
    'api.noConnection': 'کوئی کنکشن نہیں — نیٹ ورک چیک کریں اور دوبارہ کوشش کریں۔',
    'api.searchUnavailable': 'تلاش ابھی دستیاب نہیں — تھوڑی دیر بعد کوشش کریں۔',
  },
  ha: {
    'api.sessionExpired': 'Zaman ya ƙare — sake buɗe wannan allon.',
    'api.serviceDown': 'Sabis ɗin ba ya amsawa yanzu. A sake gwadawa ba da daɗewa ba.',
    'api.noConnection': 'Babu haɗi — duba intanet ɗin ka sake gwadawa.',
    'api.searchUnavailable': 'Bincike ba ya samuwa yanzu — a sake gwadawa bayan ɗan lokaci.',
  },
  fil: {
    'api.sessionExpired': 'Nag-expire ang session mo — buksan muli ang screen na ito.',
    'api.serviceDown': 'Hindi tumutugon ang serbisyo ngayon. Subukan ulit sandali.',
    'api.noConnection': 'Walang koneksyon — tingnan ang network at subukan ulit.',
    'api.searchUnavailable': 'Hindi available ang paghahanap ngayon — subukan ulit sandali.',
  },
  bn: {
    'api.sessionExpired': 'সেশন শেষ হয়ে গেছে — এই স্ক্রিনটি আবার খুলুন।',
    'api.serviceDown': 'পরিষেবা এখন সাড়া দিচ্ছে না। কিছুক্ষণ পর আবার চেষ্টা করুন।',
    'api.noConnection': 'সংযোগ নেই — নেটওয়ার্ক পরীক্ষা করে আবার চেষ্টা করুন।',
    'api.searchUnavailable': 'অনুসন্ধান এখন উপলব্ধ নয় — কিছুক্ষণ পর আবার চেষ্টা করুন।',
  },
});
