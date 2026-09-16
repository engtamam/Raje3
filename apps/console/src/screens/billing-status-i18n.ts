/** `BillingStatusPane.tsx`'s own strings — same per-screen registration pattern as every other
 *  screen. Wording carried over verbatim from the retired `plans-i18n.ts` (the old شاشة الاشتراك
 *  screen)'s own past-due/update-card keys — nothing reworded, only renamed to this pane's own key
 *  namespace. */
import { registerOperatorStrings } from '../operator-i18n';

registerOperatorStrings({
  ar: {
    'billingStatus.pastDue': 'آخر محاولة سحب لم تنجح. حدّث بطاقتك حتى لا يتوقف اشتراكك.',
    'billingStatus.updatePaymentMethod': 'تحديث بطاقة الدفع',
    'billingStatus.verifyingCard': 'نتحقق من بطاقتك…',
    'billingStatus.updated': 'تم تحديث بطاقة الدفع.',
    'billingStatus.updateFailed': 'تعذّر تحديث البطاقة.',
    'billingStatus.allGood': 'لا يوجد ما يستدعي انتباهك — الفوترة على ما يرام.',
  },
  en: {
    'billingStatus.pastDue': "The last charge attempt failed. Update your card so your subscription doesn't stop.",
    'billingStatus.updatePaymentMethod': 'Update payment card',
    'billingStatus.verifyingCard': 'Verifying your card…',
    'billingStatus.updated': 'Payment card updated.',
    'billingStatus.updateFailed': "Couldn't update the card.",
    'billingStatus.allGood': "Nothing needs your attention — billing is in good shape.",
  },
  ur: {
    'billingStatus.pastDue': 'آخری ادائیگی کی کوشش ناکام ہو گئی۔ اپنا کارڈ اپڈیٹ کریں تاکہ آپ کی سبسکرپشن نہ رکے۔',
    'billingStatus.updatePaymentMethod': 'ادائیگی کارڈ اپڈیٹ کریں',
    'billingStatus.verifyingCard': 'آپ کے کارڈ کی تصدیق ہو رہی ہے…',
    'billingStatus.updated': 'ادائیگی کارڈ اپڈیٹ ہو گیا۔',
    'billingStatus.updateFailed': 'کارڈ اپڈیٹ نہیں ہو سکا۔',
    'billingStatus.allGood': 'کسی توجہ کی ضرورت نہیں — بلنگ ٹھیک ہے۔',
  },
  ha: {
    'billingStatus.pastDue': 'Ƙoƙarin caji na ƙarshe bai yi nasara ba. Sabunta katinka don biyan kuɗinka kada ya tsaya.',
    'billingStatus.updatePaymentMethod': 'Sabunta katin biya',
    'billingStatus.verifyingCard': 'Muna tabbatar da katinka…',
    'billingStatus.updated': 'An sabunta katin biya.',
    'billingStatus.updateFailed': 'Ba a iya sabunta katin ba.',
    'billingStatus.allGood': 'Babu abin da yake buƙatar hankalinka — biyan kuɗi na lafiya.',
  },
  fil: {
    'billingStatus.pastDue': 'Nabigo ang huling pagsingil. I-update ang card mo para hindi huminto ang subscription mo.',
    'billingStatus.updatePaymentMethod': 'I-update ang payment card',
    'billingStatus.verifyingCard': 'Vinereverify ang card mo…',
    'billingStatus.updated': 'Na-update ang payment card.',
    'billingStatus.updateFailed': 'Hindi ma-update ang card.',
    'billingStatus.allGood': 'Walang kailangan ng atensyon mo — maayos ang billing.',
  },
  bn: {
    'billingStatus.pastDue': 'শেষ পেমেন্ট চেষ্টা ব্যর্থ হয়েছে। আপনার সাবস্ক্রিপশন বন্ধ না হতে আপনার কার্ড আপডেট করুন।',
    'billingStatus.updatePaymentMethod': 'পেমেন্ট কার্ড আপডেট করুন',
    'billingStatus.verifyingCard': 'আপনার কার্ড যাচাই করা হচ্ছে…',
    'billingStatus.updated': 'পেমেন্ট কার্ড আপডেট হয়েছে।',
    'billingStatus.updateFailed': 'কার্ড আপডেট করা যায়নি।',
    'billingStatus.allGood': 'মনোযোগ দেওয়ার কিছু নেই — বিলিং ঠিক আছে।',
  },
});
