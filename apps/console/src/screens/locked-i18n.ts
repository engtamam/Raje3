/**
 * Locked.tsx's own strings — registered once at import time (see operator-i18n.tsx's own header
 * for why this is a small per-screen file rather than one giant dictionary).
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
    'locked.featuresReadDenied': 'لا صلاحية لديك لقراءة مميزات هذا التطبيق',
    'locked.addFromStore': 'أضِفه من متجر التطبيقات',
    'locked.checkFailedTitle': 'تعذّر التحقق من اشتراكك',
    'locked.checkFailedDescOurFault': 'والخلل عندنا — أعد المحاولة بعد قليل.',
    'locked.subscribeNow': 'اشترك الآن',
    'locked.subscribing': 'يشترك…',
  },
  en: {
    'locked.featuresReadDenied': "You don't have permission to read this app's features",
    'locked.addFromStore': 'Add it from the App Store',
    'locked.checkFailedTitle': "Couldn't verify your subscription",
    'locked.checkFailedDescOurFault': "The fault is ours — try again shortly.",
    'locked.subscribeNow': 'Subscribe now',
    'locked.subscribing': 'Subscribing…',
  },
  ur: {
    'locked.featuresReadDenied': 'اس ایپ کی خصوصیات پڑھنے کی اجازت آپ کے پاس نہیں',
    'locked.addFromStore': 'ایپ سٹور سے شامل کریں',
    'locked.checkFailedTitle': 'آپ کی سبسکرپشن تصدیق نہیں ہو سکی',
    'locked.checkFailedDescOurFault': 'یہ ہماری خرابی ہے — تھوڑی دیر بعد کوشش کریں۔',
    'locked.subscribeNow': 'ابھی سبسکرائب کریں',
    'locked.subscribing': 'سبسکرائب ہو رہا ہے…',
  },
  ha: {
    'locked.featuresReadDenied': "Ba ka da izinin karanta abubuwan wannan app din",
    'locked.addFromStore': 'Ƙara shi daga App Store',
    'locked.checkFailedTitle': "Ba a iya tabbatar da biyan kuɗinka ba",
    'locked.checkFailedDescOurFault': 'Laifi namu ne — sake gwadawa bayan ɗan lokaci.',
    'locked.subscribeNow': 'Yi biyan kuɗi yanzu',
    'locked.subscribing': 'Ana biyan kuɗi…',
  },
  fil: {
    'locked.featuresReadDenied': 'Wala kang pahintulot na basahin ang mga feature ng app na ito',
    'locked.addFromStore': 'Idagdag mula sa App Store',
    'locked.checkFailedTitle': 'Hindi ma-verify ang subscription mo',
    'locked.checkFailedDescOurFault': 'Kasalanan namin ito — subukan ulit mamaya.',
    'locked.subscribeNow': 'Mag-subscribe ngayon',
    'locked.subscribing': 'Nagsu-subscribe…',
  },
  bn: {
    'locked.featuresReadDenied': 'এই অ্যাপের ফিচার পড়ার অনুমতি আপনার নেই',
    'locked.addFromStore': 'অ্যাপ স্টোর থেকে যোগ করুন',
    'locked.checkFailedTitle': 'আপনার সাবস্ক্রিপশন যাচাই করা যায়নি',
    'locked.checkFailedDescOurFault': 'এটা আমাদের ত্রুটি — একটু পরে আবার চেষ্টা করুন।',
    'locked.subscribeNow': 'এখনই সাবস্ক্রাইব করুন',
    'locked.subscribing': 'সাবস্ক্রাইব হচ্ছে…',
  },
});
