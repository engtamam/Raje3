/**
 * Customers.tsx's own strings — registered once at import time (see operator-i18n.tsx's own
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
    'customers.ago.today': 'اليوم',
    'customers.ago.yesterday': 'أمس',
    'customers.ago.twoDaysAgo': 'قبل يومين',
    'customers.ago.daysAgo': 'قبل {n} أيام',

    'customers.title': 'عملائي',

    'customers.asks.title': 'طلبات على البيانات ({n})',
    'customers.asks.body': 'عملاء طلبوا نسخة من بياناتهم أو حذفها من صفحاتهم. الرد عليهم مسؤوليتك نظاماً، خلال ثلاثين يوماً من تاريخ الطلب.',

    'customers.tabsAriaLabel': 'أقسام العملاء',
    'customers.tab.all': 'عملائي',
    'customers.tab.overdue': 'من تأخّر',
    'customers.overdueHint': 'من تأخّر عن موعده المعتاد',

    'customers.searchPlaceholder': 'ابحث برقم الجوال أو الاسم',

    'customers.addCustomer': 'إضافة عميل',
    'customers.addCustomer.title': 'إضافة عميل جديد',
    'customers.addCustomer.phone': 'رقم الجوال',
    'customers.addCustomer.name': 'الاسم (اختياري)',
    'customers.addCustomer.submit': 'إضافة',
    'customers.addCustomer.cancel': 'تراجع',
    'customers.addCustomer.genericError': 'تعذّرت الإضافة. حاول بعد قليل.',

    'customers.readError.title': 'تعذّرت القراءة',
    'customers.readError.desc': 'لم نستطع جلب القائمة الآن — والخلل عندنا لا في محلك. أعد المحاولة بعد قليل.',
    'customers.denied.overdueTitle': 'لا يشمل دورك متابعة المتأخرين',
    'customers.denied.allTitle': 'لا يشمل دورك قائمة العملاء',
    'customers.denied.desc': 'راجع صاحب المحل إن كنت تحتاج هذا القسم.',
    'customers.emptyOverdue.title': 'لا أحد متأخر',
    'customers.emptyOverdue.desc': 'كل عميل إما زار في وقته أو تذكيره لم يحن بعد.',
    'customers.emptySearch.title': 'لا نتائج',
    'customers.emptySearch.desc': 'تأكد من الرقم، أو سجّل زيارة جديدة لهذا العميل.',
    'customers.emptyNone.title': 'لا يوجد عملاء بعد',
    'customers.emptyNone.desc': 'سجّل أول زيارة من «تسجيل زيارة» — العميل يُنشأ بزيارته.',

    'customers.legend.overdue': 'الوسم في القائمة يعني: متأخر عن موعده المعتاد',
    'customers.legend.marketingOff': 'الوسم في القائمة يعني: أوقف استقبال التسويق',

    'customers.noName': 'بلا اسم',
    'customers.lastVisit': 'آخر زيارة {ago}',
    'customers.visitCount': '· {n} زيارة',
    'customers.overdueBadge': 'متأخر',
    'customers.marketingOffBadge': 'أوقف التسويق',

    'customers.ask.erasureType': 'طلب حذف بياناته',
    'customers.ask.copyType': 'طلب نسخة من بياناته',
    'customers.ask.lookupFailed': 'تعذّر التعرّف على صاحب الطلب',
    'customers.ask.noSuchCustomer': 'لا يوجد عميل بهذا المرجع في سجلاتك',
    'customers.ask.resolving': '…',
    'customers.ask.openForErasure': 'افتح سجله لتنفيذ الحذف',
    'customers.ask.open': 'افتح سجله',
    'customers.ask.markAnswered': 'تم الرد',
    'customers.ask.erasureNote': '«تم الرد» يسجّل أنك أجبته، ولا يحذف شيئاً. الحذف من صفحة العميل نفسه.',
  },
  en: {
    'customers.ago.today': 'Today',
    'customers.ago.yesterday': 'Yesterday',
    'customers.ago.twoDaysAgo': 'Two days ago',
    'customers.ago.daysAgo': '{n} days ago',

    'customers.title': 'My Customers',

    'customers.asks.title': 'Data requests ({n})',
    'customers.asks.body': "Customers requested a copy of their data or its deletion, from their own pages. Answering them is your legal responsibility, within thirty days of the request.",

    'customers.tabsAriaLabel': 'Customer sections',
    'customers.tab.all': 'My Customers',
    'customers.tab.overdue': 'Overdue',
    'customers.overdueHint': 'Overdue on their usual cycle',

    'customers.searchPlaceholder': 'Search by phone number or name',

    'customers.addCustomer': 'Add customer',
    'customers.addCustomer.title': 'Add a new customer',
    'customers.addCustomer.phone': 'Phone number',
    'customers.addCustomer.name': 'Name (optional)',
    'customers.addCustomer.submit': 'Add',
    'customers.addCustomer.cancel': 'Cancel',
    'customers.addCustomer.genericError': "Couldn't add the customer. Try again shortly.",

    'customers.readError.title': "Couldn't read",
    'customers.readError.desc': "We couldn't fetch the list right now — the fault is ours, not your shop's. Try again shortly.",
    'customers.denied.overdueTitle': "Your role doesn't include tracking overdue customers",
    'customers.denied.allTitle': "Your role doesn't include the customer list",
    'customers.denied.desc': 'Ask the shop owner if you need this section.',
    'customers.emptyOverdue.title': 'No one is overdue',
    'customers.emptyOverdue.desc': "Every customer either visited on time or their reminder hasn't come due yet.",
    'customers.emptySearch.title': 'No results',
    'customers.emptySearch.desc': "Check the number, or record a new visit for this customer.",
    'customers.emptyNone.title': 'No customers yet',
    'customers.emptyNone.desc': 'Record the first visit from "Record Visit" — the customer is created by their visit.',

    'customers.legend.overdue': 'The tag on the list means: overdue on their usual cycle',
    'customers.legend.marketingOff': 'The tag on the list means: opted out of marketing',

    'customers.noName': 'No name',
    'customers.lastVisit': 'Last visit {ago}',
    'customers.visitCount': '· {n} visits',
    'customers.overdueBadge': 'Overdue',
    'customers.marketingOffBadge': 'Marketing off',

    'customers.ask.erasureType': 'Requested their data deleted',
    'customers.ask.copyType': 'Requested a copy of their data',
    'customers.ask.lookupFailed': "Couldn't identify who made the request",
    'customers.ask.noSuchCustomer': 'No customer with this reference in your records',
    'customers.ask.resolving': '…',
    'customers.ask.openForErasure': 'Open their record to carry out the deletion',
    'customers.ask.open': 'Open their record',
    'customers.ask.markAnswered': 'Mark answered',
    'customers.ask.erasureNote': '"Mark answered" records that you replied, and deletes nothing. Deletion happens on the customer\'s own page.',
  },
  ur: {
    'customers.ago.today': 'آج',
    'customers.ago.yesterday': 'کل',
    'customers.ago.twoDaysAgo': 'دو دن پہلے',
    'customers.ago.daysAgo': '{n} دن پہلے',

    'customers.title': 'میرے گاہک',

    'customers.asks.title': 'ڈیٹا کی درخواستیں ({n})',
    'customers.asks.body': 'گاہکوں نے اپنے صفحات سے اپنے ڈیٹا کی کاپی یا حذف کی درخواست کی۔ ان کا جواب دینا آپ کی قانونی ذمہ داری ہے، درخواست کی تاریخ سے تیس دن کے اندر۔',

    'customers.tabsAriaLabel': 'گاہکوں کے حصے',
    'customers.tab.all': 'میرے گاہک',
    'customers.tab.overdue': 'تاخیر والے',
    'customers.overdueHint': 'اپنے معمول کے چکر سے تاخیر میں',

    'customers.searchPlaceholder': 'موبائل نمبر یا نام سے تلاش کریں',

    'customers.addCustomer': 'نیا کسٹمر شامل کریں',
    'customers.addCustomer.title': 'نیا کسٹمر شامل کریں',
    'customers.addCustomer.phone': 'موبائل نمبر',
    'customers.addCustomer.name': 'نام (اختیاری)',
    'customers.addCustomer.submit': 'شامل کریں',
    'customers.addCustomer.cancel': 'واپس',
    'customers.addCustomer.genericError': 'شامل نہیں ہو سکا۔ تھوڑی دیر بعد کوشش کریں۔',

    'customers.readError.title': 'نہیں پڑھ سکے',
    'customers.readError.desc': 'ابھی فہرست حاصل نہیں کر سکے — یہ ہماری خرابی ہے، آپ کی دکان کی نہیں۔ تھوڑی دیر بعد کوشش کریں۔',
    'customers.denied.overdueTitle': 'آپ کے کردار میں تاخیر والوں کی نگرانی شامل نہیں',
    'customers.denied.allTitle': 'آپ کے کردار میں گاہکوں کی فہرست شامل نہیں',
    'customers.denied.desc': 'اگر آپ کو یہ حصہ چاہیے تو دکان کے مالک سے رابطہ کریں۔',
    'customers.emptyOverdue.title': 'کوئی تاخیر میں نہیں',
    'customers.emptyOverdue.desc': 'ہر گاہک یا تو وقت پر آیا، یا اس کی یاددہانی کا وقت ابھی نہیں آیا۔',
    'customers.emptySearch.title': 'کوئی نتیجہ نہیں',
    'customers.emptySearch.desc': 'نمبر چیک کریں، یا اس گاہک کے لیے نئی وزٹ ریکارڈ کریں۔',
    'customers.emptyNone.title': 'ابھی کوئی گاہک نہیں',
    'customers.emptyNone.desc': '"وزٹ ریکارڈ کریں" سے پہلی وزٹ ریکارڈ کریں — گاہک اس کی وزٹ سے بنتا ہے۔',

    'customers.legend.overdue': 'فہرست میں یہ نشان کا مطلب: اپنے معمول کے چکر سے تاخیر میں',
    'customers.legend.marketingOff': 'فہرست میں یہ نشان کا مطلب: مارکیٹنگ موصول کرنا بند کر دیا',

    'customers.noName': 'بلا نام',
    'customers.lastVisit': 'آخری وزٹ {ago}',
    'customers.visitCount': '· {n} وزٹس',
    'customers.overdueBadge': 'تاخیر میں',
    'customers.marketingOffBadge': 'مارکیٹنگ بند',

    'customers.ask.erasureType': 'اپنا ڈیٹا حذف کرنے کی درخواست',
    'customers.ask.copyType': 'اپنے ڈیٹا کی کاپی کی درخواست',
    'customers.ask.lookupFailed': 'درخواست کنندہ کی شناخت نہیں ہو سکی',
    'customers.ask.noSuchCustomer': 'آپ کے ریکارڈز میں اس حوالے سے کوئی گاہک نہیں',
    'customers.ask.resolving': '…',
    'customers.ask.openForErasure': 'حذف کرنے کے لیے اس کا ریکارڈ کھولیں',
    'customers.ask.open': 'اس کا ریکارڈ کھولیں',
    'customers.ask.markAnswered': 'جواب دے دیا',
    'customers.ask.erasureNote': '"جواب دے دیا" ریکارڈ کرتا ہے کہ آپ نے جواب دیا، کچھ حذف نہیں کرتا۔ حذف کرنا گاہک کے اپنے صفحے سے ہوتا ہے۔',
  },
  ha: {
    'customers.ago.today': 'Yau',
    'customers.ago.yesterday': 'Jiya',
    'customers.ago.twoDaysAgo': 'Kwana biyu da suka wuce',
    'customers.ago.daysAgo': 'Kwanaki {n} da suka wuce',

    'customers.title': 'Abokan Cinikina',

    'customers.asks.title': 'Buƙatun bayanai ({n})',
    'customers.asks.body': "Abokan ciniki sun nemi kwafin bayanansu ko sharewa daga shafukansu. Amsa musu alhaki ne naka bisa doka, cikin kwanaki talatin daga ranar buƙatar.",

    'customers.tabsAriaLabel': 'Sassan abokan ciniki',
    'customers.tab.all': 'Abokan Cinikina',
    'customers.tab.overdue': 'Waɗanda suka makara',
    'customers.overdueHint': 'Ya makara a kan zagayensa na yau da kullum',

    'customers.searchPlaceholder': 'Nemi ta lambar waya ko suna',

    'customers.addCustomer': 'Ƙara abokin ciniki',
    'customers.addCustomer.title': 'Ƙara sabon abokin ciniki',
    'customers.addCustomer.phone': 'Lambar waya',
    'customers.addCustomer.name': 'Suna (na zaɓi)',
    'customers.addCustomer.submit': 'Ƙara',
    'customers.addCustomer.cancel': 'Koma',
    'customers.addCustomer.genericError': "Ba a iya ƙarawa ba. Gwada nan da ɗan lokaci.",

    'customers.readError.title': 'Ba a iya karantawa ba',
    'customers.readError.desc': 'Ba mu iya samun jerin yanzu ba — laifi namu ne, ba na shagonka ba. Sake gwadawa bayan ɗan lokaci.',
    'customers.denied.overdueTitle': "Matsayinka ba ya haɗa da bin waɗanda suka makara",
    'customers.denied.allTitle': 'Matsayinka ba ya haɗa da jerin abokan ciniki',
    'customers.denied.desc': 'Tuntuɓi mai shagon idan kana buƙatar wannan sashen.',
    'customers.emptyOverdue.title': 'Babu wanda ya makara',
    'customers.emptyOverdue.desc': 'Kowane abokin ciniki ko dai ya ziyarta a lokaci ko tunatarwarsa bata kai ba tukuna.',
    'customers.emptySearch.title': 'Babu sakamako',
    'customers.emptySearch.desc': 'Duba lambar, ko rubuta sabuwar ziyara ga wannan abokin ciniki.',
    'customers.emptyNone.title': 'Babu abokan ciniki tukuna',
    'customers.emptyNone.desc': 'Rubuta ziyara ta farko daga "Rubuta Ziyara" — ana ƙirƙirar abokin ciniki ta ziyararsa.',

    'customers.legend.overdue': 'Alamar a jerin tana nufin: ya makara a kan zagayensa na yau da kullum',
    'customers.legend.marketingOff': 'Alamar a jerin tana nufin: ya dakatar da karɓar talla',

    'customers.noName': 'Ba sunan',
    'customers.lastVisit': 'Ziyara ta ƙarshe {ago}',
    'customers.visitCount': '· ziyara {n}',
    'customers.overdueBadge': 'Ya makara',
    'customers.marketingOffBadge': 'Talla an kashe',

    'customers.ask.erasureType': 'Ya nemi a share bayanansa',
    'customers.ask.copyType': 'Ya nemi kwafin bayanansa',
    'customers.ask.lookupFailed': 'Ba a iya gano wanda ya nema ba',
    'customers.ask.noSuchCustomer': 'Babu abokin ciniki da wannan lambar a rikodinka',
    'customers.ask.resolving': '…',
    'customers.ask.openForErasure': 'Buɗe rikodinsa don aiwatar da sharewa',
    'customers.ask.open': 'Buɗe rikodinsa',
    'customers.ask.markAnswered': 'An amsa',
    'customers.ask.erasureNote': '"An amsa" yana rikodin cewa ka amsa masa, kuma baya share komai. Sharewa daga shafin abokin ciniki kansa.',
  },
  fil: {
    'customers.ago.today': 'Ngayon',
    'customers.ago.yesterday': 'Kahapon',
    'customers.ago.twoDaysAgo': 'Dalawang araw ang nakalipas',
    'customers.ago.daysAgo': '{n} araw ang nakalipas',

    'customers.title': 'Aking Mga Customer',

    'customers.asks.title': 'Mga hiling sa data ({n})',
    'customers.asks.body': "Humiling ang mga customer ng kopya ng data nila o pagbura nito, mula sa sarili nilang page. Ang pagsagot sa kanila ay legal mong responsibilidad, sa loob ng tatlumpung araw mula sa petsa ng hiling.",

    'customers.tabsAriaLabel': 'Mga seksyon ng customer',
    'customers.tab.all': 'Aking Mga Customer',
    'customers.tab.overdue': 'Huli',
    'customers.overdueHint': 'Huli sa karaniwang cycle nila',

    'customers.searchPlaceholder': 'Maghanap gamit ang numero o pangalan',

    'customers.addCustomer': 'Magdagdag ng customer',
    'customers.addCustomer.title': 'Magdagdag ng bagong customer',
    'customers.addCustomer.phone': 'Numero ng telepono',
    'customers.addCustomer.name': 'Pangalan (opsyonal)',
    'customers.addCustomer.submit': 'Idagdag',
    'customers.addCustomer.cancel': 'Bumalik',
    'customers.addCustomer.genericError': 'Hindi maidagdag. Subukan ulit sandali.',

    'customers.readError.title': 'Hindi mabasa',
    'customers.readError.desc': "Hindi namin makuha ang listahan ngayon — kasalanan namin ito, hindi ng tindahan mo. Subukan ulit mamaya.",
    'customers.denied.overdueTitle': "Hindi kasama sa role mo ang pagsubaybay sa mga huli",
    'customers.denied.allTitle': 'Hindi kasama sa role mo ang listahan ng customer',
    'customers.denied.desc': 'Kausapin ang may-ari ng tindahan kung kailangan mo ang seksyong ito.',
    'customers.emptyOverdue.title': 'Walang huli',
    'customers.emptyOverdue.desc': "Bawat customer ay bumisita sa tamang oras o hindi pa dumadating ang paalala nila.",
    'customers.emptySearch.title': 'Walang resulta',
    'customers.emptySearch.desc': 'Tiyakin ang numero, o magrehistro ng bagong bisita para sa customer na ito.',
    'customers.emptyNone.title': 'Wala pang customer',
    'customers.emptyNone.desc': 'Irehistro ang unang bisita mula sa "Record Visit" — nagagawa ang customer sa pamamagitan ng bisita nila.',

    'customers.legend.overdue': 'Ang tag sa listahan ay nangangahulugan: huli sa karaniwang cycle nila',
    'customers.legend.marketingOff': 'Ang tag sa listahan ay nangangahulugan: tumanggi sa marketing',

    'customers.noName': 'Walang pangalan',
    'customers.lastVisit': 'Huling bisita {ago}',
    'customers.visitCount': '· {n} bisita',
    'customers.overdueBadge': 'Huli',
    'customers.marketingOffBadge': 'Naka-off ang marketing',

    'customers.ask.erasureType': 'Humiling na burahin ang data niya',
    'customers.ask.copyType': 'Humiling ng kopya ng data niya',
    'customers.ask.lookupFailed': "Hindi makilala kung sino ang humiling",
    'customers.ask.noSuchCustomer': 'Walang customer na may ganitong reference sa mga record mo',
    'customers.ask.resolving': '…',
    'customers.ask.openForErasure': 'Buksan ang record niya para isagawa ang pagbura',
    'customers.ask.open': 'Buksan ang record niya',
    'customers.ask.markAnswered': 'Markahang nasagot',
    'customers.ask.erasureNote': 'Ang "Markahang nasagot" ay nagrerekord na sumagot ka, at walang binubura. Ang pagbura ay nasa sariling page ng customer.',
  },
});
