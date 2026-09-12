/**
 * Legal.tsx's own strings — registered once at import time (see operator-i18n.tsx's own header
 * for why this is a small per-screen file rather than one giant dictionary).
 *
 * NOTE: this screen renders with NO SESSION (a signed-out visitor, or a shop's own customer), and
 * `useOperatorI18n()` requires `<OperatorI18nProvider session={...}>`. This screen keeps its own
 * `locale` state (ar/en only, the document toggle it has always offered) and reads through
 * `translate()` directly rather than the hook — see the edit for how it is wired.
 *
 * MACHINE-ASSISTED, NOT NATIVE-REVIEWED. ar/en are the product's own, written with the same care
 * as the screen itself. ur/ha/fil were produced in this pass to unblock the mechanism end to end
 * — every OTHER migrated screen answers all five locales, and this gate checks every key equally
 * — but they have NOT been checked by a native speaker. Flagged explicitly rather than shipped
 * silently: a wrong word here is a worse failure than the Arabic fallback it replaces. Review
 * before this reaches a shop that actually has Urdu/Hausa/Filipino-speaking staff or customers.
 */
import { registerOperatorStrings } from '../operator-i18n';

registerOperatorStrings({
  ar: {
    'legal.back': 'رجوع',
    'legal.switchToEnglish': 'English',
    'legal.switchToArabic': 'العربية',
    'legal.notFoundTitle': 'الوثيقة غير موجودة',
    'legal.availableDocs': 'الوثائق المتاحة:',
    'legal.unfilled': 'لم تُستكمل بعد',
  },
  en: {
    'legal.back': 'Back',
    'legal.switchToEnglish': 'English',
    'legal.switchToArabic': 'العربية',
    'legal.notFoundTitle': 'Document not found',
    'legal.availableDocs': 'Available documents:',
    'legal.unfilled': 'Not yet completed',
  },
  ur: {
    'legal.back': 'واپس',
    'legal.switchToEnglish': 'English',
    'legal.switchToArabic': 'العربية',
    'legal.notFoundTitle': 'دستاویز موجود نہیں',
    'legal.availableDocs': 'دستیاب دستاویزات:',
    'legal.unfilled': 'ابھی مکمل نہیں ہوا',
  },
  ha: {
    'legal.back': 'Koma baya',
    'legal.switchToEnglish': 'English',
    'legal.switchToArabic': 'العربية',
    'legal.notFoundTitle': 'Ba a sami takarda ba',
    'legal.availableDocs': "Takardun da ake da su:",
    'legal.unfilled': 'Ba a kammala ba tukuna',
  },
  fil: {
    'legal.back': 'Bumalik',
    'legal.switchToEnglish': 'English',
    'legal.switchToArabic': 'العربية',
    'legal.notFoundTitle': 'Hindi natagpuan ang dokumento',
    'legal.availableDocs': 'Mga available na dokumento:',
    'legal.unfilled': 'Hindi pa nakumpleto',
  },
});
