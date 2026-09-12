/**
 * SubscriptionBar.tsx's own strings — registered once at import time (see operator-i18n.tsx's own
 * header for why this is a small per-screen file rather than one giant dictionary).
 *
 * MACHINE-ASSISTED, NOT NATIVE-REVIEWED. ar/en are the product's own, written with the same care
 * as the screen itself. ur/ha/fil were produced in this pass to unblock the mechanism end to end
 * — get a real operator reading his own language today rather than none at all — but they have
 * NOT been checked by a native speaker. Flagged explicitly rather than shipped silently: a wrong
 * word here is a worse failure than the Arabic fallback it replaces. Review before this reaches a
 * shop that actually has Urdu/Hausa/Filipino-speaking staff on the floor.
 */
import { registerOperatorStrings } from './operator-i18n';

registerOperatorStrings({
  ar: {
    'subscriptionBar.baseDefaultName': 'الأساس',
    'subscriptionBar.appRenewsIn': 'اشتراكك في {name} يتجدَّد خلال {days}.',
    'subscriptionBar.storeLink': 'متجر التطبيقات',
    'subscriptionBar.lapsed': 'انتهى اشتراكك — بياناتك محفوظة ويمكنك تصفّحها، وتسجيل الزيارات يعود فور التجديد.',
    'subscriptionBar.trialEnding': 'تنتهي تجربتك المجانية خلال {days} — فعِّل {name} ليستمر عملك بلا انقطاع.',
    'subscriptionBar.renewsIn': 'اشتراكك يتجدَّد خلال {days}.',
    'subscriptionBar.renewNow': 'جدِّد الآن',
    'subscriptionBar.day.one': 'يوم واحد',
    'subscriptionBar.day.other': '{n} أيام',
  },
  en: {
    'subscriptionBar.baseDefaultName': 'the Base',
    'subscriptionBar.appRenewsIn': 'Your {name} subscription renews in {days}.',
    'subscriptionBar.storeLink': 'App Store',
    'subscriptionBar.lapsed': "Your subscription has ended — your data is safe and you can browse it, and recording visits comes back the moment you renew.",
    'subscriptionBar.trialEnding': 'Your free trial ends in {days} — activate {name} so your work continues without interruption.',
    'subscriptionBar.renewsIn': 'Your subscription renews in {days}.',
    'subscriptionBar.renewNow': 'Renew now',
    'subscriptionBar.day.one': '1 day',
    'subscriptionBar.day.other': '{n} days',
  },
  ur: {
    'subscriptionBar.baseDefaultName': 'بنیادی پیکج',
    'subscriptionBar.appRenewsIn': 'آپ کا {name} سبسکرپشن {days} میں تجدید ہوگا۔',
    'subscriptionBar.storeLink': 'ایپ سٹور',
    'subscriptionBar.lapsed': 'آپ کا سبسکرپشن ختم ہو گیا ہے — آپ کا ڈیٹا محفوظ ہے اور آپ اسے دیکھ سکتے ہیں، تجدید ہوتے ہی وزٹس ریکارڈ کرنا واپس آ جائے گا۔',
    'subscriptionBar.trialEnding': 'آپ کی مفت آزمائش {days} میں ختم ہو رہی ہے — {name} فعال کریں تاکہ آپ کا کام بلاتعطل جاری رہے۔',
    'subscriptionBar.renewsIn': 'آپ کا سبسکرپشن {days} میں تجدید ہوگا۔',
    'subscriptionBar.renewNow': 'ابھی تجدید کریں',
    'subscriptionBar.day.one': '1 دن',
    'subscriptionBar.day.other': '{n} دن',
  },
  ha: {
    'subscriptionBar.baseDefaultName': 'Tsarin Asali',
    'subscriptionBar.appRenewsIn': 'Biyan kuɗin {name} zai sabunta a cikin {days}.',
    'subscriptionBar.storeLink': 'App Store',
    'subscriptionBar.lapsed': "Biyan kuɗin ka ya ƙare — bayananka suna nan lafiya kuma kana iya duba su, kuma rubuta ziyara zai dawo nan take da sabuntawa.",
    'subscriptionBar.trialEnding': 'Gwajin ka na kyauta zai ƙare a cikin {days} — kunna {name} domin aikinka ya ci gaba ba tare da tsayawa ba.',
    'subscriptionBar.renewsIn': 'Biyan kuɗin ka zai sabunta a cikin {days}.',
    'subscriptionBar.renewNow': 'Sabunta yanzu',
    'subscriptionBar.day.one': 'kwana 1',
    'subscriptionBar.day.other': 'kwanaki {n}',
  },
  fil: {
    'subscriptionBar.baseDefaultName': 'ang Base',
    'subscriptionBar.appRenewsIn': 'Ang subscription mong {name} ay mare-renew sa loob ng {days}.',
    'subscriptionBar.storeLink': 'App Store',
    'subscriptionBar.lapsed': "Natapos na ang subscription mo — ligtas ang data mo at maaari mo pa itong tingnan, at babalik ang pagrekord ng bisita sa sandaling mag-renew ka.",
    'subscriptionBar.trialEnding': 'Ang libreng trial mo ay matatapos sa loob ng {days} — i-activate ang {name} para tuloy-tuloy ang trabaho mo.',
    'subscriptionBar.renewsIn': 'Ang subscription mo ay mare-renew sa loob ng {days}.',
    'subscriptionBar.renewNow': 'I-renew ngayon',
    'subscriptionBar.day.one': '1 araw',
    'subscriptionBar.day.other': '{n} araw',
  },
});
