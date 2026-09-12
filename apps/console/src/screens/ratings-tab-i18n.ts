/**
 * RatingsTab.tsx's own strings — registered once at import time (see operator-i18n.tsx's own
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
    'ratings.filter.allStars': 'كل التقييمات',
    'ratings.filter.star5': '5 نجوم',
    'ratings.filter.star4': '4 نجوم',
    'ratings.filter.star3': '3 نجوم',
    'ratings.filter.star2': 'نجمتان',
    'ratings.filter.star1': 'نجمة واحدة',
    'ratings.filter.unhandled': 'غير معالَجة',
    'ratings.filter.all': 'الكل',
    'ratings.filter.handled': 'معالَجة',

    'ratings.ago.today': 'اليوم',
    'ratings.ago.yesterday': 'أمس',
    'ratings.ago.twoDaysAgo': 'قبل يومين',
    'ratings.ago.daysAgo': 'قبل {n} أيام',

    'ratings.readFailedTitle': 'تعذّرت القراءة',
    'ratings.readFailedDesc': 'لم نستطع جلب التقييمات الآن، والخلل عندنا لا في محلك. أعد المحاولة بعد قليل.',
    'ratings.emptyUnhandledTitle': 'لا تقييمات بانتظار المعالجة',
    'ratings.emptyTitle': 'لا تقييمات بعد',
    'ratings.emptyUnhandledDesc': 'كل تقييم وصل تمت معالجته، أو لم يصل تقييم جديد بعد.',
    'ratings.emptyDesc': 'التقييمات تصل تلقائياً بعد الزيارة، عبر تطبيق التقييم.',

    'ratings.handledBadge': 'معالَجة',
    'ratings.unhandledBadge': 'بانتظار المعالجة',
    'ratings.noteLabel': 'ملاحظتك: {note}',
    'ratings.notePlaceholder': 'ملاحظة (اختياري) — مثال: تواصلنا معه واعتذرنا',
    'ratings.markHandled': 'تمت المعالجة',
  },
  en: {
    'ratings.filter.allStars': 'All ratings',
    'ratings.filter.star5': '5 stars',
    'ratings.filter.star4': '4 stars',
    'ratings.filter.star3': '3 stars',
    'ratings.filter.star2': '2 stars',
    'ratings.filter.star1': '1 star',
    'ratings.filter.unhandled': 'Unhandled',
    'ratings.filter.all': 'All',
    'ratings.filter.handled': 'Handled',

    'ratings.ago.today': 'Today',
    'ratings.ago.yesterday': 'Yesterday',
    'ratings.ago.twoDaysAgo': 'Two days ago',
    'ratings.ago.daysAgo': '{n} days ago',

    'ratings.readFailedTitle': "Couldn't read",
    'ratings.readFailedDesc': "We couldn't fetch the ratings right now — the fault is ours, not your shop's. Try again shortly.",
    'ratings.emptyUnhandledTitle': 'No ratings awaiting a reply',
    'ratings.emptyTitle': 'No ratings yet',
    'ratings.emptyUnhandledDesc': 'Every rating that came in has been handled, or none has arrived yet.',
    'ratings.emptyDesc': 'Ratings arrive automatically after a visit, through the rating app.',

    'ratings.handledBadge': 'Handled',
    'ratings.unhandledBadge': 'Awaiting a reply',
    'ratings.noteLabel': 'Your note: {note}',
    'ratings.notePlaceholder': 'Note (optional) — e.g. we reached out and apologized',
    'ratings.markHandled': 'Mark handled',
  },
  ur: {
    'ratings.filter.allStars': 'تمام تقییمات',
    'ratings.filter.star5': '5 ستارے',
    'ratings.filter.star4': '4 ستارے',
    'ratings.filter.star3': '3 ستارے',
    'ratings.filter.star2': '2 ستارے',
    'ratings.filter.star1': '1 ستارہ',
    'ratings.filter.unhandled': 'غیر حل شدہ',
    'ratings.filter.all': 'سب',
    'ratings.filter.handled': 'حل شدہ',

    'ratings.ago.today': 'آج',
    'ratings.ago.yesterday': 'کل',
    'ratings.ago.twoDaysAgo': 'دو دن پہلے',
    'ratings.ago.daysAgo': '{n} دن پہلے',

    'ratings.readFailedTitle': 'پڑھ نہیں سکے',
    'ratings.readFailedDesc': 'ابھی تقییمات حاصل نہیں کر سکے — یہ ہماری خرابی ہے، آپ کی دکان کی نہیں۔ تھوڑی دیر بعد کوشش کریں۔',
    'ratings.emptyUnhandledTitle': 'کوئی تقییم جواب کا منتظر نہیں',
    'ratings.emptyTitle': 'ابھی کوئی تقییم نہیں',
    'ratings.emptyUnhandledDesc': 'ہر آنے والی تقییم حل ہو چکی ہے، یا ابھی کوئی نئی تقییم نہیں آئی۔',
    'ratings.emptyDesc': 'تقییمات وزٹ کے بعد خودکار طور پر آتی ہیں، تقییم ایپ کے ذریعے۔',

    'ratings.handledBadge': 'حل شدہ',
    'ratings.unhandledBadge': 'جواب کا منتظر',
    'ratings.noteLabel': 'آپ کا نوٹ: {note}',
    'ratings.notePlaceholder': 'نوٹ (اختیاری) — مثال: ہم نے رابطہ کیا اور معذرت کی',
    'ratings.markHandled': 'حل شدہ کے طور پر نشان زد کریں',
  },
  ha: {
    'ratings.filter.allStars': 'Duk ƙima',
    'ratings.filter.star5': 'Taurari 5',
    'ratings.filter.star4': 'Taurari 4',
    'ratings.filter.star3': 'Taurari 3',
    'ratings.filter.star2': 'Taurari 2',
    'ratings.filter.star1': 'Tauraro 1',
    'ratings.filter.unhandled': 'Ba a magance ba',
    'ratings.filter.all': 'Duka',
    'ratings.filter.handled': 'An magance',

    'ratings.ago.today': 'Yau',
    'ratings.ago.yesterday': 'Jiya',
    'ratings.ago.twoDaysAgo': 'Kwana biyu da suka wuce',
    'ratings.ago.daysAgo': 'Kwanaki {n} da suka wuce',

    'ratings.readFailedTitle': 'Ba a iya karantawa ba',
    'ratings.readFailedDesc': "Ba mu iya samun ƙimomin yanzu ba — laifi namu ne, ba na shagonka ba. Sake gwadawa bayan ɗan lokaci.",
    'ratings.emptyUnhandledTitle': "Babu ƙima da ke jiran amsa",
    'ratings.emptyTitle': 'Babu ƙima tukuna',
    'ratings.emptyUnhandledDesc': "Kowace ƙimar da ta zo an magance ta, ko babu sabuwar ƙima da ta zo tukuna.",
    'ratings.emptyDesc': 'Ƙima suna zuwa kai tsaye bayan ziyara, ta hanyar app na ƙima.',

    'ratings.handledBadge': 'An magance',
    'ratings.unhandledBadge': 'Yana jiran amsa',
    'ratings.noteLabel': 'Bayaninka: {note}',
    'ratings.notePlaceholder': 'Bayani (na zaɓi) — misali: mun tuntuɓe shi kuma mun nemi gafara',
    'ratings.markHandled': 'Yi alama an magance',
  },
  fil: {
    'ratings.filter.allStars': 'Lahat ng rating',
    'ratings.filter.star5': '5 bituin',
    'ratings.filter.star4': '4 bituin',
    'ratings.filter.star3': '3 bituin',
    'ratings.filter.star2': '2 bituin',
    'ratings.filter.star1': '1 bituin',
    'ratings.filter.unhandled': 'Hindi pa naaayos',
    'ratings.filter.all': 'Lahat',
    'ratings.filter.handled': 'Naayos na',

    'ratings.ago.today': 'Ngayon',
    'ratings.ago.yesterday': 'Kahapon',
    'ratings.ago.twoDaysAgo': 'Dalawang araw ang nakalipas',
    'ratings.ago.daysAgo': '{n} araw ang nakalipas',

    'ratings.readFailedTitle': 'Hindi mabasa',
    'ratings.readFailedDesc': "Hindi namin makuha ang mga rating ngayon — kasalanan namin ito, hindi ng tindahan mo. Subukan ulit mamaya.",
    'ratings.emptyUnhandledTitle': 'Walang rating na naghihintay ng sagot',
    'ratings.emptyTitle': 'Wala pang rating',
    'ratings.emptyUnhandledDesc': 'Naayos na ang bawat rating na dumating, o wala pang bagong rating na dumating.',
    'ratings.emptyDesc': 'Awtomatikong dumarating ang mga rating pagkatapos ng bisita, sa pamamagitan ng rating app.',

    'ratings.handledBadge': 'Naayos na',
    'ratings.unhandledBadge': 'Naghihintay ng sagot',
    'ratings.noteLabel': 'Ang tala mo: {note}',
    'ratings.notePlaceholder': 'Tala (opsyonal) — hal.: nakipag-ugnayan kami at humingi ng paumanhin',
    'ratings.markHandled': 'Markahan bilang naayos',
  },
});
