/**
 * Home.tsx's own strings — registered once at import time (see operator-i18n.tsx's own header
 * for why this is a small per-screen file rather than one giant dictionary).
 *
 * MACHINE-ASSISTED, NOT NATIVE-REVIEWED. ar/en are the product's own, written with the same care
 * as the screen itself. ur/ha/fil were produced in this pass to unblock the mechanism end to end
 * — get a real operator reading his own language today rather than none at all — but they have
 * NOT been checked by a native speaker. Flagged explicitly rather than shipped silently: a wrong
 * word here is a worse failure than the Arabic fallback it replaces. Review before this reaches a
 * shop that actually has Urdu/Hausa/Filipino-speaking staff on the floor.
 */
import { registerOperatorStrings } from '../operator-i18n';

registerOperatorStrings({
  ar: {
    'home.noSections.title': 'لا تتوفر أقسام لحسابك',
    'home.noSections.description': 'تواصل مع مالك الحساب لضبط صلاحياتك.',
  },
  en: {
    'home.noSections.title': 'No sections available for your account',
    'home.noSections.description': "Contact the account owner to set your permissions.",
  },
  ur: {
    'home.noSections.title': 'آپ کے اکاؤنٹ کے لیے کوئی سیکشن دستیاب نہیں',
    'home.noSections.description': 'اپنی اجازتیں طے کرنے کے لیے اکاؤنٹ کے مالک سے رابطہ کریں۔',
  },
  ha: {
    'home.noSections.title': 'Babu wani sashi da ake samu ga asusunka',
    'home.noSections.description': 'Tuntuɓi mai asusun domin ya saita izininka.',
  },
  fil: {
    'home.noSections.title': 'Walang available na seksyon para sa account mo',
    'home.noSections.description': 'Makipag-ugnayan sa may-ari ng account para itakda ang mga pahintulot mo.',
  },
});
