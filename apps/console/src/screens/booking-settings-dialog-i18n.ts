/**
 * BookingSettingsDialog.tsx's own strings — registered once at import time (see
 * operator-i18n.tsx's own header for why this is a small per-screen file rather than one giant
 * dictionary).
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
    'bookingSettings.title': 'إعدادات الحجوزات',
    'bookingSettings.tabsAriaLabel': 'تبويب الإعدادات',
    'bookingSettings.tab.hours': 'أوقات الدوام',
    'bookingSettings.tab.assignment': 'طريقة التوزيع',
    'bookingSettings.cancel': 'إلغاء',
    'bookingSettings.saving': 'جارٍ الحفظ…',
    'bookingSettings.save': 'حفظ',

    'bookingSettings.day.0': 'الاثنين', 'bookingSettings.day.1': 'الثلاثاء',
    'bookingSettings.day.2': 'الأربعاء', 'bookingSettings.day.3': 'الخميس',
    'bookingSettings.day.4': 'الجمعة', 'bookingSettings.day.5': 'السبت',
    'bookingSettings.day.6': 'الأحد',

    'bookingSettings.hours.open': 'مفتوح',
    'bookingSettings.hours.to': 'إلى',
    'bookingSettings.hours.closed': 'مغلق',
    'bookingSettings.hours.policyHint': 'سياسة واحدة تسري على جميع الفروع — تُضبط هنا مرة واحدة، وتُعدَّل متى دعت الحاجة.',
    'bookingSettings.hours.saveFailed': 'تعذّر حفظ أوقات الدوام.',

    'bookingSettings.assignment.algoAriaLabel': 'خوارزمية التوزيع',
    'bookingSettings.assignment.hint': 'لخدمات «تلقائي» فقط — تحدد الموظف الذي يُسنَد إليه الموعد عند توفر أكثر من موظف مؤهَّل في الوقت نفسه.',
    'bookingSettings.assignment.noStaff': 'لا يوجد موظفون ميدانيون نشطون بعد.',
    'bookingSettings.assignment.moveUp': 'نقل {name} لأعلى',
    'bookingSettings.assignment.moveDown': 'نقل {name} لأسفل',
    'bookingSettings.assignment.saveFailed': 'تعذّر حفظ طريقة التوزيع.',

    'bookingSettings.algo.nearest.label': 'أقرب موعد',
    'bookingSettings.algo.nearest.hint': 'أول موظف مؤهَّل يتوفر لديه موعد فارغ — بلا أي إعداد إضافي، وهو السلوك المعتمد حالياً بالضبط.',
    'bookingSettings.algo.leastLoaded.label': 'الأقل حِملاً',
    'bookingSettings.algo.leastLoaded.hint': 'يُوزَّع بالتساوي — يُفضَّل الموظف الذي لديه حجوزات أقل في الفترة نفسها.',
    'bookingSettings.algo.manualOrder.label': 'ترتيب يدوي',
    'bookingSettings.algo.manualOrder.hint': 'ترتّب الموظفين مرة واحدة، ويُفضَّل الأول في الترتيب دائماً عند التعادل.',
  },
  en: {
    'bookingSettings.title': 'Booking settings',
    'bookingSettings.tabsAriaLabel': 'Settings tab',
    'bookingSettings.tab.hours': 'Working hours',
    'bookingSettings.tab.assignment': 'Assignment method',
    'bookingSettings.cancel': 'Cancel',
    'bookingSettings.saving': 'Saving…',
    'bookingSettings.save': 'Save',

    'bookingSettings.day.0': 'Monday', 'bookingSettings.day.1': 'Tuesday',
    'bookingSettings.day.2': 'Wednesday', 'bookingSettings.day.3': 'Thursday',
    'bookingSettings.day.4': 'Friday', 'bookingSettings.day.5': 'Saturday',
    'bookingSettings.day.6': 'Sunday',

    'bookingSettings.hours.open': 'Open',
    'bookingSettings.hours.to': 'to',
    'bookingSettings.hours.closed': 'Closed',
    'bookingSettings.hours.policyHint': 'One policy for every branch — set once here, and changed whenever needed.',
    'bookingSettings.hours.saveFailed': "Couldn't save the working hours.",

    'bookingSettings.assignment.algoAriaLabel': 'Assignment algorithm',
    'bookingSettings.assignment.hint': 'For "automatic" services only — decides who gets the appointment when more than one qualified staff member is free at the same time.',
    'bookingSettings.assignment.noStaff': 'No active field staff yet.',
    'bookingSettings.assignment.moveUp': 'Move {name} up',
    'bookingSettings.assignment.moveDown': 'Move {name} down',
    'bookingSettings.assignment.saveFailed': "Couldn't save the assignment method.",

    'bookingSettings.algo.nearest.label': 'Nearest appointment',
    'bookingSettings.algo.nearest.hint': 'The first qualified staff member with a free slot — no extra setup, exactly today\'s behavior.',
    'bookingSettings.algo.leastLoaded.label': 'Least loaded',
    'bookingSettings.algo.leastLoaded.hint': 'Distributes evenly — the staff member with fewer bookings in the same period is preferred.',
    'bookingSettings.algo.manualOrder.label': 'Manual order',
    'bookingSettings.algo.manualOrder.hint': 'You order the staff once, and the first in that order is always preferred on a tie.',
  },
  ur: {
    'bookingSettings.title': 'بکنگ کی ترتیبات',
    'bookingSettings.tabsAriaLabel': 'ترتیبات کا ٹیب',
    'bookingSettings.tab.hours': 'کام کے اوقات',
    'bookingSettings.tab.assignment': 'تفویض کا طریقہ',
    'bookingSettings.cancel': 'منسوخ کریں',
    'bookingSettings.saving': 'محفوظ ہو رہا ہے…',
    'bookingSettings.save': 'محفوظ کریں',

    'bookingSettings.day.0': 'پیر', 'bookingSettings.day.1': 'منگل',
    'bookingSettings.day.2': 'بدھ', 'bookingSettings.day.3': 'جمعرات',
    'bookingSettings.day.4': 'جمعہ', 'bookingSettings.day.5': 'ہفتہ',
    'bookingSettings.day.6': 'اتوار',

    'bookingSettings.hours.open': 'کھلا',
    'bookingSettings.hours.to': 'تک',
    'bookingSettings.hours.closed': 'بند',
    'bookingSettings.hours.policyHint': 'ہر شاخ کے لیے ایک ہی پالیسی — یہاں ایک بار طے کریں، اور جب ضرورت ہو تبدیل کریں۔',
    'bookingSettings.hours.saveFailed': 'کام کے اوقات محفوظ نہیں ہو سکے۔',

    'bookingSettings.assignment.algoAriaLabel': 'تفویض کا الگورتھم',
    'bookingSettings.assignment.hint': 'صرف "خودکار" خدمات کے لیے — طے کرتا ہے کہ اگر ایک ہی وقت میں ایک سے زیادہ اہل عملہ خالی ہو تو موعد کس کو ملے گا۔',
    'bookingSettings.assignment.noStaff': 'ابھی تک کوئی فعال فیلڈ عملہ نہیں۔',
    'bookingSettings.assignment.moveUp': '{name} کو اوپر منتقل کریں',
    'bookingSettings.assignment.moveDown': '{name} کو نیچے منتقل کریں',
    'bookingSettings.assignment.saveFailed': 'تفویض کا طریقہ محفوظ نہیں ہو سکا۔',

    'bookingSettings.algo.nearest.label': 'قریب ترین موعد',
    'bookingSettings.algo.nearest.hint': 'پہلا اہل عملہ جس کا سلاٹ خالی ہو — کسی اضافی ترتیب کے بغیر، بالکل آج کے طرزِ عمل کی طرح۔',
    'bookingSettings.algo.leastLoaded.label': 'کم ترین بوجھ',
    'bookingSettings.algo.leastLoaded.hint': 'برابر تقسیم کرتا ہے — اسی مدت میں کم بکنگز والے عملے کو ترجیح دی جاتی ہے۔',
    'bookingSettings.algo.manualOrder.label': 'دستی ترتیب',
    'bookingSettings.algo.manualOrder.hint': 'آپ عملے کو ایک بار ترتیب دیتے ہیں، اور برابری کی صورت میں ترتیب میں پہلے کو ہمیشہ ترجیح ملتی ہے۔',
  },
  ha: {
    'bookingSettings.title': 'Saitunan ajiye lokaci',
    'bookingSettings.tabsAriaLabel': 'Shafin saituna',
    'bookingSettings.tab.hours': 'Lokutan aiki',
    'bookingSettings.tab.assignment': 'Hanyar rabawa',
    'bookingSettings.cancel': 'Soke',
    'bookingSettings.saving': 'Ana ajiyewa…',
    'bookingSettings.save': 'Ajiye',

    'bookingSettings.day.0': 'Litinin', 'bookingSettings.day.1': 'Talata',
    'bookingSettings.day.2': 'Laraba', 'bookingSettings.day.3': 'Alhamis',
    'bookingSettings.day.4': "Jumma'a", 'bookingSettings.day.5': 'Asabar',
    'bookingSettings.day.6': 'Lahadi',

    'bookingSettings.hours.open': 'Buɗe',
    'bookingSettings.hours.to': 'zuwa',
    'bookingSettings.hours.closed': 'Rufe',
    'bookingSettings.hours.policyHint': "Manufa ɗaya ga dukkan rassa — a saita ta anan sau ɗaya, a canza ta duk lokacin da ake bukata.",
    'bookingSettings.hours.saveFailed': 'Ba a iya ajiye lokutan aiki ba.',

    'bookingSettings.assignment.algoAriaLabel': 'Algorithm na rabawa',
    'bookingSettings.assignment.hint': "Ga ayyukan 'atomatik' kawai — yana tantance wanda za a bai wa alƙawari idan fiye da ma'aikaci ɗaya mai cancanta suke a bude a lokaci guda.",
    'bookingSettings.assignment.noStaff': "Babu ma'aikatan filin masu aiki tukuna.",
    'bookingSettings.assignment.moveUp': 'Matsar da {name} sama',
    'bookingSettings.assignment.moveDown': 'Matsar da {name} ƙasa',
    'bookingSettings.assignment.saveFailed': 'Ba a iya ajiye hanyar rabawa ba.',

    'bookingSettings.algo.nearest.label': 'Alƙawari mafi kusa',
    'bookingSettings.algo.nearest.hint': "Ma'aikaci na farko mai cancanta wanda yake da lokaci a bude — babu wani ƙarin saiti, daidai da abin da ake yi a yau.",
    'bookingSettings.algo.leastLoaded.label': 'Mafi ƙarancin nauyi',
    'bookingSettings.algo.leastLoaded.hint': "Ana rabawa daidai — ana fifita ma'aikacin da ke da alƙawura kaɗan a lokaci guda.",
    'bookingSettings.algo.manualOrder.label': 'Tsari na hannu',
    'bookingSettings.algo.manualOrder.hint': "Kana tsara ma'aikata sau ɗaya, kuma ana fifita na farko a tsarin koyaushe idan akwai daidaito.",
  },
  fil: {
    'bookingSettings.title': 'Mga setting ng booking',
    'bookingSettings.tabsAriaLabel': 'Tab ng mga setting',
    'bookingSettings.tab.hours': 'Oras ng trabaho',
    'bookingSettings.tab.assignment': 'Paraan ng pagtalaga',
    'bookingSettings.cancel': 'Kanselahin',
    'bookingSettings.saving': 'Sine-save…',
    'bookingSettings.save': 'I-save',

    'bookingSettings.day.0': 'Lunes', 'bookingSettings.day.1': 'Martes',
    'bookingSettings.day.2': 'Miyerkules', 'bookingSettings.day.3': 'Huwebes',
    'bookingSettings.day.4': 'Biyernes', 'bookingSettings.day.5': 'Sabado',
    'bookingSettings.day.6': 'Linggo',

    'bookingSettings.hours.open': 'Bukas',
    'bookingSettings.hours.to': 'hanggang',
    'bookingSettings.hours.closed': 'Sarado',
    'bookingSettings.hours.policyHint': 'Iisang patakaran para sa lahat ng branch — itakda dito nang isang beses, at baguhin tuwing kinakailangan.',
    'bookingSettings.hours.saveFailed': "Hindi ma-save ang oras ng trabaho.",

    'bookingSettings.assignment.algoAriaLabel': 'Algorithm ng pagtalaga',
    'bookingSettings.assignment.hint': 'Para lang sa mga "automatic" na serbisyo — tinutukoy kung sino ang mabibigyan ng appointment kapag may higit sa isang kwalipikadong staff na libre sa parehong oras.',
    'bookingSettings.assignment.noStaff': 'Wala pang aktibong field staff.',
    'bookingSettings.assignment.moveUp': 'Ilipat pataas si {name}',
    'bookingSettings.assignment.moveDown': 'Ilipat pababa si {name}',
    'bookingSettings.assignment.saveFailed': "Hindi ma-save ang paraan ng pagtalaga.",

    'bookingSettings.algo.nearest.label': 'Pinakamalapit na appointment',
    'bookingSettings.algo.nearest.hint': 'Ang unang kwalipikadong staff na may bakanteng slot — walang karagdagang setup, eksaktong kasalukuyang gawi.',
    'bookingSettings.algo.leastLoaded.label': 'Pinakamababang load',
    'bookingSettings.algo.leastLoaded.hint': 'Pantay na ipinapamahagi — mas pinipili ang staff na may mas kaunting booking sa parehong yugto ng panahon.',
    'bookingSettings.algo.manualOrder.label': 'Manu-manong ayos',
    'bookingSettings.algo.manualOrder.hint': 'Inaayos mo ang staff nang isang beses, at ang una sa ayos ay laging pinipili kapag pantay ang puntos.',
  },
  bn: {
    'bookingSettings.title': 'বুকিং সেটিংস',
    'bookingSettings.tabsAriaLabel': 'সেটিংস ট্যাব',
    'bookingSettings.tab.hours': 'কাজের সময়',
    'bookingSettings.tab.assignment': 'বণ্টন পদ্ধতি',
    'bookingSettings.cancel': 'বাতিল',
    'bookingSettings.saving': 'সংরক্ষণ হচ্ছে…',
    'bookingSettings.save': 'সংরক্ষণ করুন',

    'bookingSettings.day.0': 'সোমবার', 'bookingSettings.day.1': 'মঙ্গলবার',
    'bookingSettings.day.2': 'বুধবার', 'bookingSettings.day.3': 'বৃহস্পতিবার',
    'bookingSettings.day.4': 'শুক্রবার', 'bookingSettings.day.5': 'শনিবার',
    'bookingSettings.day.6': 'রবিবার',

    'bookingSettings.hours.open': 'খোলা',
    'bookingSettings.hours.to': 'পর্যন্ত',
    'bookingSettings.hours.closed': 'বন্ধ',
    'bookingSettings.hours.policyHint': 'সব শাখার জন্য একটাই নীতি — এখানে একবার সেট করুন, প্রয়োজন হলে যেকোনো সময় বদলান।',
    'bookingSettings.hours.saveFailed': 'কাজের সময় সংরক্ষণ করা যায়নি।',

    'bookingSettings.assignment.algoAriaLabel': 'বণ্টন অ্যালগরিদম',
    'bookingSettings.assignment.hint': 'শুধু "স্বয়ংক্রিয়" সেবার জন্য — একই সময়ে একাধিক যোগ্য স্টাফ খালি থাকলে অ্যাপয়েন্টমেন্ট কাকে দেওয়া হবে তা ঠিক করে।',
    'bookingSettings.assignment.noStaff': 'এখনো কোনো সক্রিয় ফিল্ড স্টাফ নেই।',
    'bookingSettings.assignment.moveUp': '{name} কে উপরে সরান',
    'bookingSettings.assignment.moveDown': '{name} কে নিচে সরান',
    'bookingSettings.assignment.saveFailed': 'বণ্টন পদ্ধতি সংরক্ষণ করা যায়নি।',

    'bookingSettings.algo.nearest.label': 'নিকটতম অ্যাপয়েন্টমেন্ট',
    'bookingSettings.algo.nearest.hint': 'খালি সময় আছে এমন প্রথম যোগ্য স্টাফ — কোনো অতিরিক্ত সেটআপ ছাড়াই, ঠিক আজকের চলমান নিয়ম অনুযায়ী।',
    'bookingSettings.algo.leastLoaded.label': 'সবচেয়ে কম ব্যস্ত',
    'bookingSettings.algo.leastLoaded.hint': 'সমানভাবে বণ্টন করা হয় — একই সময়ে যার বুকিং কম, তাকেই প্রাধান্য দেওয়া হয়।',
    'bookingSettings.algo.manualOrder.label': 'নিজে ক্রম ঠিক করুন',
    'bookingSettings.algo.manualOrder.hint': 'আপনি একবার স্টাফদের ক্রম ঠিক করে দেন, এবং সমতা হলে সবসময় ক্রমে প্রথম জনকেই প্রাধান্য দেওয়া হয়।',
  },
});
