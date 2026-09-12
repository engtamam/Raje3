/**
 * CardForm.tsx's own strings — registered once at import time (see operator-i18n.tsx's own
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
    'cardForm.invalidNumber': 'رقم البطاقة غير مكتمل.',
    'cardForm.invalidMonth': 'شهر الانتهاء غير صحيح.',
    'cardForm.invalidYear': 'سنة الانتهاء غير صحيحة.',
    'cardForm.invalidCvc': 'رمز الأمان (CVC) غير مكتمل.',
    'cardForm.nameRequired': 'يُرجى كتابة الاسم كما هو مطبوع على البطاقة.',
    'cardForm.name': 'الاسم كما على البطاقة',
    'cardForm.number': 'رقم البطاقة',
    'cardForm.month': 'الشهر',
    'cardForm.year': 'السنة',
    'cardForm.cvc': 'رمز الأمان (CVC)',
    'cardForm.disclosure': 'تُرسَل بياناتك مباشرة إلى بوابة الدفع، ولا تمر على خوادمنا إطلاقاً — قد يُطلب منك تأكيد العملية من تطبيق بنكك.',
    'cardForm.verifying': 'يجري التحقق…',
    'cardForm.confirm': 'تأكيد البطاقة',
    'cardForm.cancel': 'إلغاء',
  },
  en: {
    'cardForm.invalidNumber': "The card number is incomplete.",
    'cardForm.invalidMonth': 'Invalid expiry month.',
    'cardForm.invalidYear': 'Invalid expiry year.',
    'cardForm.invalidCvc': "The security code (CVC) is incomplete.",
    'cardForm.nameRequired': "Enter the name exactly as printed on the card.",
    'cardForm.name': 'Name as on card',
    'cardForm.number': 'Card number',
    'cardForm.month': 'Month',
    'cardForm.year': 'Year',
    'cardForm.cvc': 'CVC',
    'cardForm.disclosure': "Your details go straight to the payment gateway and never pass through our servers — your bank's app may ask you to confirm the transaction.",
    'cardForm.verifying': 'Verifying…',
    'cardForm.confirm': 'Confirm card',
    'cardForm.cancel': 'Cancel',
  },
  ur: {
    'cardForm.invalidNumber': 'کارڈ نمبر نامکمل ہے۔',
    'cardForm.invalidMonth': 'انقضا کا مہینہ درست نہیں۔',
    'cardForm.invalidYear': 'انقضا کا سال درست نہیں۔',
    'cardForm.invalidCvc': 'سیکیورٹی کوڈ (CVC) نامکمل ہے۔',
    'cardForm.nameRequired': 'براہ کرم نام بالکل ویسے لکھیں جیسا کارڈ پر چھپا ہے۔',
    'cardForm.name': 'کارڈ پر درج نام',
    'cardForm.number': 'کارڈ نمبر',
    'cardForm.month': 'مہینہ',
    'cardForm.year': 'سال',
    'cardForm.cvc': 'CVC',
    'cardForm.disclosure': 'آپ کی تفصیلات براہ راست ادائیگی کے گیٹ وے کو بھیجی جاتی ہیں اور ہمارے سرورز سے کبھی نہیں گزرتیں — آپ کے بینک کی ایپ آپ سے لین دین کی تصدیق مانگ سکتی ہے۔',
    'cardForm.verifying': 'تصدیق ہو رہی ہے…',
    'cardForm.confirm': 'کارڈ کی تصدیق کریں',
    'cardForm.cancel': 'منسوخ کریں',
  },
  ha: {
    'cardForm.invalidNumber': 'Lambar katin bai cika ba.',
    'cardForm.invalidMonth': 'Watan ƙarewa ba daidai ba ne.',
    'cardForm.invalidYear': 'Shekarar ƙarewa ba daidai ba ce.',
    'cardForm.invalidCvc': 'Lambar tsaro (CVC) bai cika ba.',
    'cardForm.nameRequired': "Rubuta suna daidai kamar yadda yake a buga a kan katin.",
    'cardForm.name': 'Sunan kamar yadda yake a kati',
    'cardForm.number': 'Lambar kati',
    'cardForm.month': 'Wata',
    'cardForm.year': 'Shekara',
    'cardForm.cvc': 'CVC',
    'cardForm.disclosure': "Bayananka suna zuwa kai tsaye ga mahaɗin biyan kuɗi, kuma ba sa taɓa sabobinmu ko-ta-kwana — aikace-aikacen bankinka na iya tambayarka ka tabbatar da mu'amalar.",
    'cardForm.verifying': 'Ana tabbatarwa…',
    'cardForm.confirm': 'Tabbatar da kati',
    'cardForm.cancel': 'Soke',
  },
  fil: {
    'cardForm.invalidNumber': 'Hindi kumpleto ang numero ng card.',
    'cardForm.invalidMonth': 'Hindi wasto ang buwan ng expiry.',
    'cardForm.invalidYear': 'Hindi wasto ang taon ng expiry.',
    'cardForm.invalidCvc': 'Hindi kumpleto ang security code (CVC).',
    'cardForm.nameRequired': "Ilagay ang pangalan nang eksakto gaya ng nakalimbag sa card.",
    'cardForm.name': 'Pangalan gaya ng nasa card',
    'cardForm.number': 'Numero ng card',
    'cardForm.month': 'Buwan',
    'cardForm.year': 'Taon',
    'cardForm.cvc': 'CVC',
    'cardForm.disclosure': "Direktang napupunta ang detalye mo sa payment gateway at hindi ito dumadaan sa aming mga server — maaaring hilingin ng app ng bangko mo na kumpirmahin ang transaksyon.",
    'cardForm.verifying': 'Vine-verify…',
    'cardForm.confirm': 'Kumpirmahin ang card',
    'cardForm.cancel': 'Kanselahin',
  },
});
