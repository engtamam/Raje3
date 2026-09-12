/**
 * DoorLayout.tsx's own strings — registered once at import time (see operator-i18n.tsx's own
 * header for why this is a small per-screen file rather than one giant dictionary).
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
    'doorLayout.backHome': 'العودة إلى الصفحة الرئيسية',
    'doorLayout.heroTitle': 'عملاؤك يعودون من تلقاء أنفسهم.',
    'doorLayout.heroSubtitle': 'يتذكّر راجِع الموعد المناسب لخدمة كل عميل القادمة، ويُذكّره بها عبر واتساب باسم محلك — دون أن تفتح التطبيق.',
    'doorLayout.heroTag': 'راجِع · السعودية',
    'doorLayout.copyright': '© راجِع — جميع الحقوق محفوظة',
    'doorLayout.terms': 'الشروط',
    'doorLayout.privacy': 'الخصوصية',
  },
  en: {
    'doorLayout.backHome': 'Back to the home page',
    'doorLayout.heroTitle': 'Your customers come back, on their own.',
    'doorLayout.heroSubtitle': "Raje3 remembers when each customer needs his next service, and reminds him on WhatsApp under your shop's name — without you opening the app.",
    'doorLayout.heroTag': 'Raje3 · Saudi Arabia',
    'doorLayout.copyright': '© Raje3 — All rights reserved',
    'doorLayout.terms': 'Terms',
    'doorLayout.privacy': 'Privacy',
  },
  ur: {
    'doorLayout.backHome': 'مرکزی صفحے پر واپس جائیں',
    'doorLayout.heroTitle': 'آپ کے گاہک خود بخود واپس آتے ہیں۔',
    'doorLayout.heroSubtitle': 'راجِع یاد رکھتا ہے کہ ہر گاہک کو اپنی اگلی خدمت کب چاہیے، اور اسے واٹس ایپ پر آپ کی دکان کے نام سے یاد دلاتا ہے — بغیر آپ کے ایپ کھولے۔',
    'doorLayout.heroTag': 'راجِع · سعودی عرب',
    'doorLayout.copyright': '© راجِع — تمام حقوق محفوظ ہیں',
    'doorLayout.terms': 'شرائط',
    'doorLayout.privacy': 'رازداری',
  },
  ha: {
    'doorLayout.backHome': 'Koma zuwa babban shafi',
    'doorLayout.heroTitle': 'Abokan cinikinka suna dawowa da kansu.',
    'doorLayout.heroSubtitle': "Raje3 yana tunawa da lokacin da kowane abokin ciniki yake bukatar sabis na gaba, yana tunatar da shi a WhatsApp da sunan shagonka — ba tare da ka buɗe app ba.",
    'doorLayout.heroTag': 'Raje3 · Saudiyya',
    'doorLayout.copyright': '© Raje3 — Duk haƙƙoƙi an kiyaye su',
    'doorLayout.terms': 'Sharuɗɗa',
    'doorLayout.privacy': 'Sirri',
  },
  fil: {
    'doorLayout.backHome': 'Bumalik sa homepage',
    'doorLayout.heroTitle': 'Bumabalik ang mga customer mo, sa kanilang sarili.',
    'doorLayout.heroSubtitle': 'Naaalala ng Raje3 kung kailan kailangan ng bawat customer ang susunod niyang serbisyo, at pinapaalalahanan siya sa WhatsApp gamit ang pangalan ng tindahan mo — nang hindi mo binubuksan ang app.',
    'doorLayout.heroTag': 'Raje3 · Saudi Arabia',
    'doorLayout.copyright': '© Raje3 — Nakalaan ang lahat ng karapatan',
    'doorLayout.terms': 'Mga Tuntunin',
    'doorLayout.privacy': 'Privacy',
  },
});
