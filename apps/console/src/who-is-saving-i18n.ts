/**
 * WhoIsSaving.tsx's own strings — registered once at import time (see operator-i18n.tsx's own
 * header for why this is a small per-screen file rather than one giant dictionary).
 *
 * MACHINE-ASSISTED, NOT NATIVE-REVIEWED. ar/en are the product's own, written with the same care
 * as the component itself. ur/ha/fil were produced in this pass to unblock the mechanism end to
 * end but have NOT been checked by a native speaker. Review before this reaches a shop that
 * actually has Urdu/Hausa/Filipino-speaking staff on the floor.
 */
import { registerOperatorStrings } from './operator-i18n';

registerOperatorStrings({
  ar: {
    'whoIsSaving.title': 'من يحفظ هذه الزيارة؟',
    'whoIsSaving.subtitle': 'أدخل رمزك المكوَّن من أربعة أرقام لتُسجَّل هذه الزيارة باسمك وفرعك.',
    'whoIsSaving.readFailed': 'تعذّرت قراءة أسماء الفريق الآن.',
    'whoIsSaving.pinAriaLabel': 'رمز العامل',
    'whoIsSaving.wrongPin': 'الرمز غير صحيح.',
    'whoIsSaving.skip': 'تخطّي',
    'whoIsSaving.confirm': 'تأكيد وحفظ',
  },
  en: {
    'whoIsSaving.title': 'Who is saving this visit?',
    'whoIsSaving.subtitle': 'Enter your 4-digit PIN so this visit is recorded under your name and branch.',
    'whoIsSaving.readFailed': "Couldn't read the team's names right now.",
    'whoIsSaving.pinAriaLabel': 'Staff PIN',
    'whoIsSaving.wrongPin': 'Incorrect PIN.',
    'whoIsSaving.skip': 'Skip',
    'whoIsSaving.confirm': 'Confirm and save',
  },
  ur: {
    'whoIsSaving.title': 'یہ وزٹ کون محفوظ کر رہا ہے؟',
    'whoIsSaving.subtitle': 'اپنا چار ہندسوں کا کوڈ درج کریں تاکہ یہ وزٹ آپ کے نام اور شاخ سے ریکارڈ ہو۔',
    'whoIsSaving.readFailed': 'ابھی ٹیم کے نام نہیں پڑھے جا سکے۔',
    'whoIsSaving.pinAriaLabel': 'عملے کا کوڈ',
    'whoIsSaving.wrongPin': 'کوڈ درست نہیں۔',
    'whoIsSaving.skip': 'نظرانداز کریں',
    'whoIsSaving.confirm': 'تصدیق اور محفوظ کریں',
  },
  ha: {
    'whoIsSaving.title': 'Wane ne yake ajiye wannan ziyarar?',
    'whoIsSaving.subtitle': "Shigar da lambar sirrinka mai lambobi 4 domin a rubuta wannan ziyarar da sunanka da reshenka.",
    'whoIsSaving.readFailed': "Ba a iya karanta sunayen ƙungiya a yanzu ba.",
    'whoIsSaving.pinAriaLabel': 'Lambar sirrin ma\'aikaci',
    'whoIsSaving.wrongPin': 'Lambar sirri ba daidai ba ce.',
    'whoIsSaving.skip': 'Tsallake',
    'whoIsSaving.confirm': 'Tabbatar kuma ajiye',
  },
  fil: {
    'whoIsSaving.title': 'Sino ang nagse-save ng bisitang ito?',
    'whoIsSaving.subtitle': 'Ilagay ang iyong 4-digit na PIN para marekord ang bisitang ito sa ilalim ng iyong pangalan at branch.',
    'whoIsSaving.readFailed': 'Hindi mabasa ngayon ang mga pangalan ng team.',
    'whoIsSaving.pinAriaLabel': 'PIN ng staff',
    'whoIsSaving.wrongPin': 'Maling PIN.',
    'whoIsSaving.skip': 'Laktawan',
    'whoIsSaving.confirm': 'Kumpirmahin at i-save',
  },
});
