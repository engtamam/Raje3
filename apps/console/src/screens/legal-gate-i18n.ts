/**
 * LegalGate.tsx's own strings — registered once at import time (see operator-i18n.tsx's own
 * header for why this is a small per-screen file rather than one giant dictionary).
 *
 * NOTE: this is DISTINCT from `../i18n.ts` (the Arabic-only auth/sign-in kit), which answers
 * `AcceptTerms`'s own internal labels (buttons, document titles) through a separate context. The
 * two strings here are `mapError`'s own text, supplied by this screen itself and never owned by
 * that kit.
 *
 * MACHINE-ASSISTED, NOT NATIVE-REVIEWED. ar/en are the product's own, written with the same care
 * as the screen itself. ur/ha/fil/bn were produced in this pass to unblock the mechanism end to end
 * — get a real operator reading his own language today rather than none at all — but they have
 * NOT been checked by a native speaker. Flagged explicitly rather than shipped silently: a wrong
 * word here is a worse failure than the Arabic fallback it replaces. Review before this reaches a
 * shop that actually has Urdu/Hausa/Filipino/Bengali-speaking staff on the floor.
 */
import { registerOperatorStrings } from '../operator-i18n';

registerOperatorStrings({
  ar: {
    'legalGate.error.saveFailed': 'تعذّر حفظ الموافقة. حاول مرة أخرى.',
    'legalGate.error.notAvailable': 'الموافقة غير متاحة لحسابك — تواصل مع مالك الحساب.',
  },
  en: {
    'legalGate.error.saveFailed': "Couldn't save the acceptance. Try again.",
    'legalGate.error.notAvailable': "Acceptance isn't available for your account — contact the account owner.",
  },
  ur: {
    'legalGate.error.saveFailed': 'رضامندی محفوظ نہیں ہو سکی۔ دوبارہ کوشش کریں۔',
    'legalGate.error.notAvailable': 'آپ کے اکاؤنٹ کے لیے رضامندی دستیاب نہیں — اکاؤنٹ کے مالک سے رابطہ کریں۔',
  },
  ha: {
    'legalGate.error.saveFailed': 'Ba a iya ajiye yardar ba. Sake gwadawa.',
    'legalGate.error.notAvailable': "Yarda ba ta samuwa ga asusunka ba — tuntuɓi mai asusun.",
  },
  fil: {
    'legalGate.error.saveFailed': 'Hindi ma-save ang pagsang-ayon. Subukan muli.',
    'legalGate.error.notAvailable': 'Hindi available ang pagsang-ayon para sa account mo — makipag-ugnayan sa may-ari ng account.',
  },
  bn: {
    'legalGate.error.saveFailed': 'সম্মতি সংরক্ষণ করা যায়নি। আবার চেষ্টা করুন।',
    'legalGate.error.notAvailable': 'আপনার অ্যাকাউন্টের জন্য সম্মতি প্রযোজ্য নয় — অ্যাকাউন্টের মালিকের সাথে যোগাযোগ করুন।',
  },
});
