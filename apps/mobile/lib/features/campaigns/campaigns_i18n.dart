import 'package:flutter/widgets.dart';

/// «الحملات»'s own translation table — a real six-locale map, same six locales the app's own
/// `l10n/app_{ar,en,bn,ur,ha,fil}.arb` files cover, kept LOCAL to this feature rather than routed
/// through the generated `S.of(context)` pipeline.
///
/// WHY LOCAL, NOT THE ARB PIPELINE (documented, not silent): this feature's strings were written
/// against the real backend contract first and need to keep changing fast across the next few
/// passes (KPI cards, the trend chart, the reward-type picker, etc. are all still ahead — see
/// parity/messages.md's own remaining-gap list); regenerating `app_localizations.dart` on every
/// pass adds real friction for no benefit yet. Every string below IS a genuine, deliberate
/// translation in all six languages — never a placeholder or left-as-Arabic fallback — so a
/// non-Arabic-reading shop gets a real screen today. Folding this table into the generated ARB
/// pipeline once the feature's copy stabilises is a reasonable follow-up, not a requirement of
/// this pass.
///
/// `{n}`/`{remaining}`/`{limit}`/`{sent}`/`{suppressed}` are plain substring placeholders, filled
/// by [ct] — no ICU plural rules (same scope call `tf()` in the console's own `operator-i18n.tsx`
/// makes: a straight substitution is enough for the counts this feature ever shows).
const Map<String, Map<String, String>> _kCampaignsStrings = {
  'title': {
    'ar': 'الحملات', 'en': 'Campaigns', 'bn': 'ক্যাম্পেইন', 'ur': 'مہمات', 'ha': 'Yaƙin talla',
    'fil': 'Mga Kampanya',
  },
  'launchNew': {
    'ar': 'أطلق رسالة جديدة', 'en': 'Launch a new message', 'bn': 'নতুন বার্তা পাঠান',
    'ur': 'نیا پیغام بھیجیں', 'ha': 'Aika sabon saƙo', 'fil': 'Maglunsad ng bagong mensahe',
  },
  'tabTemplates': {
    'ar': 'القوالب', 'en': 'Templates', 'bn': 'টেমপ্লেট', 'ur': 'سانچے', 'ha': 'Samfura',
    'fil': 'Mga Template',
  },
  'tabQueue': {
    'ar': 'القادمة', 'en': 'Upcoming', 'bn': 'আসন্ন', 'ur': 'آنے والے', 'ha': 'Masu zuwa',
    'fil': 'Paparating',
  },
  'tabLog': {
    'ar': 'السجل', 'en': 'Log', 'bn': 'লগ', 'ur': 'لاگ', 'ha': 'Bayanan tarihi', 'fil': 'Log',
  },
  'todayReadFailed': {
    'ar': 'تعذّرت قراءة حالة اليوم.', 'en': "Couldn't read today's status.",
    'bn': 'আজকের অবস্থা পড়া যায়নি।', 'ur': 'آج کی صورتحال پڑھی نہیں جا سکی۔',
    'ha': 'An kasa karanta halin yau.', 'fil': 'Hindi nabasa ang katayuan ngayon.',
  },
  'blockedTitle': {
    'ar': 'الإرسال متوقف اليوم', 'en': 'Sending is paused today', 'bn': 'আজ পাঠানো বন্ধ আছে',
    'ur': 'آج بھیجنا رکا ہوا ہے', 'ha': 'An dakatar da aikawa a yau', 'fil': 'Naka-pause ang pagpapadala ngayon',
  },
  'heroQuestion': {
    'ar': 'هل كل شيء يعمل اليوم؟', 'en': 'Is everything working today?',
    'bn': 'আজ সবকিছু ঠিক আছে কি?', 'ur': 'کیا آج سب کچھ ٹھیک کام کر رہا ہے؟',
    'ha': 'Duk abu na aiki daidai yau?', 'fil': 'Maayos ba lahat ngayon?',
  },
  'statSent': {
    'ar': 'أُرسل', 'en': 'Sent', 'bn': 'পাঠানো হয়েছে', 'ur': 'بھیجا گیا', 'ha': 'An aika', 'fil': 'Naipadala',
  },
  'statWaiting': {
    'ar': 'بالانتظار', 'en': 'Waiting', 'bn': 'অপেক্ষমাণ', 'ur': 'زیرِ انتظار', 'ha': 'Jira',
    'fil': 'Naghihintay',
  },
  'statRetrying': {
    'ar': 'يُعاد المحاولة', 'en': 'Retrying', 'bn': 'পুনরায় চেষ্টা করা হচ্ছে', 'ur': 'دوبارہ کوشش جاری ہے',
    'ha': 'Ana sake gwadawa', 'fil': 'Sinusubukang muli',
  },
  'ceilingLine': {
    'ar': 'المتبقي اليوم لدى واتساب: {remaining} من {limit}',
    'en': 'Remaining today on WhatsApp: {remaining} of {limit}',
    'bn': 'হোয়াটসঅ্যাপে আজ অবশিষ্ট: {limit} এর মধ্যে {remaining}',
    'ur': 'واٹس ایپ پر آج باقی: {limit} میں سے {remaining}',
    'ha': 'Sauran yau akan WhatsApp: {remaining} daga cikin {limit}',
    'fil': 'Natitira ngayon sa WhatsApp: {remaining} sa {limit}',
  },
  'sectionService': {
    'ar': 'خدمية', 'en': 'Service', 'bn': 'সার্ভিস', 'ur': 'سروس', 'ha': 'Sabis', 'fil': 'Serbisyo',
  },
  'sectionPersonal': {
    'ar': 'شخصية', 'en': 'Personal', 'bn': 'ব্যক্তিগত', 'ur': 'ذاتی', 'ha': 'Na kansa', 'fil': 'Personal',
  },
  'sectionMarketing': {
    'ar': 'تسويقية', 'en': 'Marketing', 'bn': 'মার্কেটিং', 'ur': 'مارکیٹنگ', 'ha': 'Talla', 'fil': 'Marketing',
  },
  'sectionOffers': {
    'ar': 'عروض', 'en': 'Offers', 'bn': 'অফার', 'ur': 'پیشکشیں', 'ha': 'Tayi', 'fil': 'Mga Alok',
  },
  'templatesEmpty': {
    'ar': 'لا رسائل مُعرَّفة بعد', 'en': 'No messages defined yet', 'bn': 'এখনও কোনো বার্তা নির্ধারিত হয়নি',
    'ur': 'ابھی کوئی پیغام متعین نہیں', 'ha': 'Babu wani saƙo da aka bayyana tukuna',
    'fil': 'Wala pang natukoy na mensahe',
  },
  'tagBoth': {
    'ar': 'آلي ويدوي', 'en': 'Auto & manual', 'bn': 'স্বয়ংক্রিয় ও নিজে থেকে', 'ur': 'خودکار اور دستی',
    'ha': 'Ta atomatik da ta hannu', 'fil': 'Awtomatiko at manu-mano',
  },
  'tagAuto': {
    'ar': 'آلي', 'en': 'Auto', 'bn': 'স্বয়ংক্রিয়', 'ur': 'خودکار', 'ha': 'Atomatik', 'fil': 'Awtomatiko',
  },
  'tagManual': {
    'ar': 'يدوي', 'en': 'Manual', 'bn': 'নিজে থেকে', 'ur': 'دستی', 'ha': 'Da hannu', 'fil': 'Manu-mano',
  },
  'queueOverdue': {
    'ar': 'متأخّرة', 'en': 'Overdue', 'bn': 'বিলম্বিত', 'ur': 'تاخیر شدہ', 'ha': 'Ya wuce lokaci',
    'fil': 'Overdue na',
  },
  'dueToday': {
    'ar': 'اليوم', 'en': 'Today', 'bn': 'আজ', 'ur': 'آج', 'ha': 'Yau', 'fil': 'Ngayon',
  },
  'dueTomorrow': {
    'ar': 'غدًا', 'en': 'Tomorrow', 'bn': 'আগামীকাল', 'ur': 'کل', 'ha': 'Gobe', 'fil': 'Bukas',
  },
  'dueInDays': {
    'ar': 'خلال {n} أيام', 'en': 'In {n} days', 'bn': '{n} দিনের মধ্যে', 'ur': '{n} دن میں',
    'ha': 'Cikin kwana {n}', 'fil': 'Sa loob ng {n} araw',
  },
  'occasionReminder': {
    'ar': 'تذكير موعد', 'en': 'Appointment reminder', 'bn': 'অ্যাপয়েন্টমেন্ট স্মরণিকা',
    'ur': 'اپائنٹمنٹ یاد دہانی', 'ha': 'Tunatarwar alƙawari', 'fil': 'Paalala ng appointment',
  },
  'occasionFollowUp': {
    'ar': 'متابعة بعد الزيارة', 'en': 'Follow-up after the visit', 'bn': 'পরিদর্শনের পর ফলো-আপ',
    'ur': 'وزٹ کے بعد فالو اپ', 'ha': 'Bibiya bayan ziyara', 'fil': 'Follow-up matapos ang pagbisita',
  },
  'occasionReview': {
    'ar': 'طلب تقييم', 'en': 'Review request', 'bn': 'রিভিউ অনুরোধ', 'ur': 'ریویو کی درخواست',
    'ha': 'Neman ra\'ayi', 'fil': 'Kahilingan ng review',
  },
  'occasionCampaign': {
    'ar': 'حملة', 'en': 'Campaign', 'bn': 'ক্যাম্পেইন', 'ur': 'مہم', 'ha': 'Yaƙin talla', 'fil': 'Kampanya',
  },
  'occasionFallback': {
    'ar': 'رسالة', 'en': 'Message', 'bn': 'বার্তা', 'ur': 'پیغام', 'ha': 'Saƙo', 'fil': 'Mensahe',
  },
  'queueEmpty': {
    'ar': 'لا رسائل بانتظار الخروج الآن', 'en': 'No messages waiting to go out right now',
    'bn': 'এই মুহূর্তে পাঠানোর জন্য কোনো বার্তা অপেক্ষমাণ নেই', 'ur': 'اس وقت بھیجنے کے لیے کوئی پیغام زیرِ انتظار نہیں',
    'ha': 'Babu wani saƙo da ke jiran fita a yanzu', 'fil': 'Walang naghihintay na mensahe ngayon',
  },
  'customerFallback': {
    'ar': 'عميل', 'en': 'Customer', 'bn': 'গ্রাহক', 'ur': 'گاہک', 'ha': 'Abokin ciniki', 'fil': 'Kustomer',
  },
  'goalWinBack': {
    'ar': 'رجّع اللي غابوا', 'en': 'Bring back who left', 'bn': 'যারা চলে গেছে তাদের ফিরিয়ে আনুন',
    'ur': 'جو چلے گئے انہیں واپس لائیں', 'ha': 'Dawo da waɗanda suka rasa', 'fil': 'Ibalik ang umalis',
  },
  'goalRewardLoyal': {
    'ar': 'كافئ المخلصين', 'en': 'Reward loyal customers', 'bn': 'অনুগত গ্রাহকদের পুরস্কৃত করুন',
    'ur': 'وفادار گاہکوں کو انعام دیں', 'ha': 'Ba wa amintattun abokan ciniki lada',
    'fil': 'Gantimpalaan ang tapat na kustomer',
  },
  'goalAnnounce': {
    'ar': 'أعلن جديدك', 'en': "Announce what's new", 'bn': 'নতুন কিছু ঘোষণা করুন',
    'ur': 'اپنی نئی چیز کا اعلان کریں', 'ha': 'Sanar da sabon abu', 'fil': 'Ipaalam ang bago',
  },
  'goalOccasion': {
    'ar': 'هنّئ في مناسبة', 'en': 'Greet on an occasion', 'bn': 'উপলক্ষ্যে শুভেচ্ছা জানান',
    'ur': 'موقع پر مبارکباد دیں', 'ha': 'Yi murna a wani lokaci', 'fil': 'Batiin sa okasyon',
  },
  'goalServiceOffer': {
    'ar': 'عرض على خدمة', 'en': 'Offer on a service', 'bn': 'একটি সার্ভিসে অফার',
    'ur': 'کسی سروس پر آفر', 'ha': 'Tayi akan sabis', 'fil': 'Alok sa serbisyo',
  },
  'goalPackageOffer': {
    'ar': 'عرض على باقة', 'en': 'Offer on a package', 'bn': 'একটি প্যাকেজে অফার',
    'ur': 'کسی پیکج پر آفر', 'ha': 'Tayi akan fakiti', 'fil': 'Alok sa package',
  },
  'campaignsEmptyTitle': {
    'ar': 'لم تُطلق حملة بعد', 'en': "You haven't launched a campaign yet",
    'bn': 'এখনও কোনো ক্যাম্পেইন চালু করেননি', 'ur': 'ابھی تک کوئی مہم شروع نہیں کی',
    'ha': 'Ba a kaddamar da wani yaƙin talla ba tukuna', 'fil': 'Wala ka pang nailunsad na kampanya',
  },
  'campaignsEmptyMsg': {
    'ar': 'اضغط «أطلق رسالة جديدة» بالأعلى للبدء',
    'en': 'Tap "Launch a new message" above to start',
    'bn': 'শুরু করতে উপরে "নতুন বার্তা পাঠান" চাপুন',
    'ur': 'شروع کرنے کے لیے اوپر "نیا پیغام بھیجیں" دبائیں',
    'ha': 'Danna "Aika sabon saƙo" a sama don farawa',
    'fil': 'Pindutin ang "Maglunsad ng bagong mensahe" sa itaas',
  },
  'stateActive': {
    'ar': 'نشطة', 'en': 'Active', 'bn': 'সক্রিয়', 'ur': 'فعال', 'ha': 'Mai aiki', 'fil': 'Aktibo',
  },
  'statePaused': {
    'ar': 'متوقفة', 'en': 'Paused', 'bn': 'বিরতি দেওয়া', 'ur': 'رکی ہوئی', 'ha': 'An dakatar', 'fil': 'Naka-pause',
  },
  'stateScheduled': {
    'ar': 'مجدولة', 'en': 'Scheduled', 'bn': 'নির্ধারিত', 'ur': 'شیڈول شدہ', 'ha': 'An tsara', 'fil': 'Naka-schedule',
  },
  'stateDone': {
    'ar': 'انتهت', 'en': 'Finished', 'bn': 'সমাপ্ত', 'ur': 'مکمل', 'ha': 'Ta ƙare', 'fil': 'Tapos na',
  },
  'reachedCount': {
    'ar': 'وصلت {n} عميلاً', 'en': 'Reached {n} customers', 'bn': '{n} জন গ্রাহকের কাছে পৌঁছেছে',
    'ur': '{n} گاہکوں تک پہنچی', 'ha': 'Ya kai ga abokan ciniki {n}', 'fil': 'Umabot sa {n} kustomer',
  },
  'lockedTitle': {
    'ar': 'تطبيق الحملات غير مفعّل بعد', 'en': 'The Campaigns app isn\'t active yet',
    'bn': 'ক্যাম্পেইন অ্যাপ এখনও সক্রিয় নয়', 'ur': 'کیمپینز ایپ ابھی فعال نہیں',
    'ha': 'Aikace-aikacen Yaƙin talla bai kunna ba tukuna', 'fil': 'Hindi pa aktibo ang Campaigns app',
  },
  'lockedDesc': {
    'ar': 'يعيد إليك عملاءك على وشك مغادرتك، ويكبر إيرادك من قاعدة عملائك الحالية.',
    'en': 'Brings back customers about to leave you, and grows your revenue from your existing base.',
    'bn': 'যেসব গ্রাহক চলে যাওয়ার পথে তাদের ফিরিয়ে আনে, এবং আপনার বর্তমান গ্রাহকদের থেকে আয় বাড়ায়।',
    'ur': 'ان گاہکوں کو واپس لاتا ہے جو جانے والے ہیں، اور آپ کے موجودہ گاہکوں سے آمدنی بڑھاتا ہے۔',
    'ha': 'Yana dawo da abokan cinikin da suke kusa barin ka, kuma yana ƙara kuɗin shiga daga abokan cinikin ka.',
    'fil': 'Ibinabalik ang mga kustomer na aalis na, at pinapalago ang kita mula sa kasalukuyang customer base mo.',
  },
  'subscribeNow': {
    'ar': 'فعّل التطبيق الآن', 'en': 'Activate the app now', 'bn': 'এখনই অ্যাপ সক্রিয় করুন',
    'ur': 'ابھی ایپ فعال کریں', 'ha': 'Kunna aikace-aikacen yanzu', 'fil': 'I-activate ang app ngayon',
  },
  'whatHappened': {
    'ar': 'ماذا حدث', 'en': 'What happened', 'bn': 'কী ঘটেছে', 'ur': 'کیا ہوا', 'ha': 'Me ya faru',
    'fil': 'Ano ang nangyari',
  },
  'runSummary': {
    'ar': 'أُرسل {sent} · امتنع {suppressed}', 'en': 'Sent {sent} · suppressed {suppressed}',
    'bn': 'পাঠানো {sent} · বাতিল {suppressed}', 'ur': 'بھیجا {sent} · روکا گیا {suppressed}',
    'ha': 'An aika {sent} · an dakatar {suppressed}', 'fil': 'Naipadala {sent} · natigil {suppressed}',
  },
  'noRunsYet': {
    'ar': 'لا سجل إرسال بعد', 'en': 'No send history yet', 'bn': 'এখনও কোনো পাঠানোর ইতিহাস নেই',
    'ur': 'ابھی بھیجنے کی کوئی تاریخ نہیں', 'ha': 'Babu tarihin aikawa tukuna', 'fil': 'Wala pang history ng pagpapadala',
  },
  'filterAll': {
    'ar': 'الكل', 'en': 'All', 'bn': 'সব', 'ur': 'تمام', 'ha': 'Duka', 'fil': 'Lahat',
  },
  'filterSuppressed': {
    'ar': 'امتنع', 'en': 'Suppressed', 'bn': 'বাতিল হয়েছে', 'ur': 'روک دیا گیا', 'ha': 'An dakatar',
    'fil': 'Natigil',
  },
  'outcomeSuppressed': {
    'ar': 'امتنعت', 'en': 'Suppressed', 'bn': 'বাতিল হয়েছে', 'ur': 'روک دیا گیا', 'ha': 'An dakatar',
    'fil': 'Natigil',
  },
  'outcomeRead': {
    'ar': 'قرأها', 'en': 'Read', 'bn': 'পড়েছে', 'ur': 'پڑھ لیا', 'ha': 'Ya karanta', 'fil': 'Nabasa',
  },
  'outcomeDelivered': {
    'ar': 'وصلت', 'en': 'Delivered', 'bn': 'পৌঁছেছে', 'ur': 'پہنچ گیا', 'ha': 'Ya isa', 'fil': 'Naihatid',
  },
  'outcomeSent': {
    'ar': 'خرجت', 'en': 'Sent out', 'bn': 'পাঠানো হয়েছে', 'ur': 'بھیج دیا گیا', 'ha': 'An aika',
    'fil': 'Naipadala na',
  },
  'previewFailed': {
    'ar': 'تعذّرت معاينة الرسالة الآن.', 'en': "Couldn't preview the message right now.",
    'bn': 'এই মুহূর্তে বার্তা প্রিভিউ করা যায়নি।', 'ur': 'ابھی پیغام کا پیش منظر نہیں دیکھا جا سکا۔',
    'ha': 'An kasa duba saƙon a yanzu.', 'fil': 'Hindi na-preview ang mensahe ngayon.',
  },
  'lockedWizardMsg': {
    'ar': 'فعّل تطبيق الحملات أولاً من متجر التطبيقات.', 'en': 'Activate the Campaigns app first from the app store.',
    'bn': 'প্রথমে অ্যাপ স্টোর থেকে ক্যাম্পেইন অ্যাপ সক্রিয় করুন।', 'ur': 'پہلے ایپ اسٹور سے کیمپینز ایپ فعال کریں۔',
    'ha': 'Kunna aikace-aikacen Yaƙin talla tukuna daga kantin app.',
    'fil': 'I-activate muna ang Campaigns app mula sa app store.',
  },
  'stepGoalTitle': {
    'ar': 'اختر الهدف', 'en': 'Choose a goal', 'bn': 'লক্ষ্য বেছে নিন', 'ur': 'مقصد چنیں', 'ha': 'Zaɓi manufa',
    'fil': 'Pumili ng layunin',
  },
  'stepPreviewTitle': {
    'ar': 'قبل الإرسال', 'en': 'Before sending', 'bn': 'পাঠানোর আগে', 'ur': 'بھیجنے سے پہلے',
    'ha': 'Kafin aikawa', 'fil': 'Bago ipadala',
  },
  'noGoalsAvailable': {
    'ar': 'لا أهداف متاحة الآن', 'en': 'No goals available right now', 'bn': 'এই মুহূর্তে কোনো লক্ষ্য উপলব্ধ নেই',
    'ur': 'اس وقت کوئی مقصد دستیاب نہیں', 'ha': 'Babu wata manufa a yanzu', 'fil': 'Walang available na layunin ngayon',
  },
  'whichService': {
    'ar': 'أي خدمة؟', 'en': 'Which service?', 'bn': 'কোন সার্ভিস?', 'ur': 'کون سی سروس؟', 'ha': 'Wane sabis?',
    'fil': 'Aling serbisyo?',
  },
  'discountAmount': {
    'ar': 'مقدار الخصم', 'en': 'Discount amount', 'bn': 'ছাড়ের পরিমাণ', 'ur': 'رعایت کی مقدار',
    'ha': 'Adadin rangwame', 'fil': 'Halaga ng diskwento',
  },
  'discountHint': {
    'ar': 'مثال: 20% أو 15 ريال', 'en': 'e.g. 20% or 15 SAR', 'bn': 'যেমন: ২০% বা ১৫ রিয়াল',
    'ur': 'مثلاً: 20% یا 15 ریال', 'ha': 'Misali: 20% ko 15 riyal', 'fil': 'hal. 20% o 15 SAR',
  },
  'endsOnLabel': {
    'ar': 'ينتهي العرض', 'en': 'Offer ends on', 'bn': 'অফার শেষ হবে', 'ur': 'آفر ختم ہو گی',
    'ha': 'Tayin zai ƙare', 'fil': 'Matatapos ang alok sa',
  },
  'pickEndDate': {
    'ar': 'اختر تاريخ الانتهاء', 'en': 'Pick an end date', 'bn': 'শেষ তারিখ বেছে নিন', 'ur': 'اختتامی تاریخ چنیں',
    'ha': 'Zaɓi ranar ƙarewa', 'fil': 'Pumili ng petsa ng pagtatapos',
  },
  'whatsNew': {
    'ar': 'ما الجديد؟', 'en': "What's new?", 'bn': 'নতুন কী?', 'ur': 'کیا نیا ہے؟', 'ha': 'Me sabo?',
    'fil': 'Ano ang bago?',
  },
  'ownerTextHint': {
    'ar': 'اكتب سطرك هنا', 'en': 'Write your line here', 'bn': 'এখানে আপনার লাইন লিখুন',
    'ur': 'یہاں اپنی سطر لکھیں', 'ha': 'Rubuta layin ka a nan', 'fil': 'Isulat ang iyong linya dito',
  },
  'nextPreview': {
    'ar': 'التالي: المعاينة', 'en': 'Next: Preview', 'bn': 'পরবর্তী: প্রিভিউ', 'ur': 'اگلا: پیش منظر',
    'ha': 'Na gaba: Dubawa', 'fil': 'Susunod: Preview',
  },
  'previewGenericFailed': {
    'ar': 'تعذّرت المعاينة.', 'en': "Couldn't load the preview.", 'bn': 'প্রিভিউ লোড করা যায়নি।',
    'ur': 'پیش منظر لوڈ نہیں ہو سکا۔', 'ha': 'An kasa lodin dubawa.', 'fil': 'Hindi na-load ang preview.',
  },
  'reachesLine': {
    'ar': 'ستصل إلى {n} عميلاً', 'en': 'Will reach {n} customers', 'bn': '{n} জন গ্রাহকের কাছে পৌঁছাবে',
    'ur': '{n} گاہکوں تک پہنچے گی', 'ha': 'Zai kai ga abokan ciniki {n}', 'fil': 'Aabot sa {n} kustomer',
  },
  'excludedLine': {
    'ar': '{n} تم استبعادهم', 'en': '{n} excluded', 'bn': '{n} জনকে বাদ দেওয়া হয়েছে', 'ur': '{n} کو خارج کیا گیا',
    'ha': 'An cire {n}', 'fil': '{n} ang na-exclude',
  },
  'tooRecentLine': {
    'ar': '{n} أخذوا هذه الخدمة مؤخرًا', 'en': '{n} took this service recently',
    'bn': '{n} জন সম্প্রতি এই সার্ভিস নিয়েছেন', 'ur': '{n} نے حال ہی میں یہ سروس لی',
    'ha': '{n} sun karɓi wannan sabis kwanan nan', 'fil': '{n} ang kararating lang kumuha ng serbisyong ito',
  },
  'launchNowButton': {
    'ar': 'أطلق الحملة الآن', 'en': 'Launch the campaign now', 'bn': 'এখনই ক্যাম্পেইন চালু করুন',
    'ur': 'ابھی مہم شروع کریں', 'ha': 'Kaddamar da yaƙin yanzu', 'fil': 'Ilunsad ang kampanya ngayon',
  },
  'previewLoadFailed': {
    'ar': 'تعذّرت قراءة الرسالة الآن.', 'en': "Couldn't read the message right now.",
    'bn': 'এই মুহূর্তে বার্তা পড়া যায়নি।', 'ur': 'ابھی پیغام پڑھا نہیں جا سکا۔', 'ha': 'An kasa karanta saƙon yanzu.',
    'fil': 'Hindi nabasa ang mensahe ngayon.',
  },
  'noWordingAvailable': {
    'ar': 'لا صيغة متاحة لهذه الرسالة الآن.', 'en': 'No wording available for this message right now.',
    'bn': 'এই বার্তার জন্য এখন কোনো ভাষা উপলব্ধ নেই।', 'ur': 'اس پیغام کے لیے ابھی کوئی عبارت دستیاب نہیں۔',
    'ha': 'Babu wata magana da ta dace da wannan saƙo a yanzu.', 'fil': 'Walang available na pagkakasabi para sa mensaheng ito ngayon.',
  },
  'statusRejected': {
    'ar': 'رفضها واتساب', 'en': 'Rejected by WhatsApp', 'bn': 'হোয়াটসঅ্যাপ প্রত্যাখ্যান করেছে',
    'ur': 'واٹس ایپ نے مسترد کر دیا', 'ha': 'WhatsApp ta ƙi', 'fil': 'Tinanggihan ng WhatsApp',
  },
  'statusPending': {
    'ar': 'عند واتساب للمراجعة', 'en': 'With WhatsApp for review', 'bn': 'পর্যালোচনার জন্য হোয়াটসঅ্যাপে আছে',
    'ur': 'واٹس ایپ کے پاس جائزے کے لیے', 'ha': 'Yana WhatsApp don dubawa', 'fil': 'Nasa WhatsApp para sa review',
  },
  'statusDraft': {
    'ar': 'لم تُرفَع بعد', 'en': 'Not submitted yet', 'bn': 'এখনও জমা দেওয়া হয়নি', 'ur': 'ابھی جمع نہیں کیا گیا',
    'ha': 'Ba a mika ba tukuna', 'fil': 'Hindi pa naisumite',
  },
  'statusReady': {
    'ar': 'جاهزة للإرسال', 'en': 'Ready to send', 'bn': 'পাঠানোর জন্য প্রস্তুত', 'ur': 'بھیجنے کے لیے تیار',
    'ha': 'A shirye don aikawa', 'fil': 'Handa nang ipadala',
  },
  'statusAwaiting': {
    'ar': 'بانتظار اعتماد واتساب', 'en': "Awaiting WhatsApp's approval", 'bn': 'হোয়াটসঅ্যাপের অনুমোদনের অপেক্ষায়',
    'ur': 'واٹس ایپ کی منظوری کا انتظار', 'ha': 'Ana jiran amincewar WhatsApp', 'fil': 'Naghihintay ng aprubal ng WhatsApp',
  },
  'yourText': {
    'ar': 'نصّك أنت', 'en': 'Your own text', 'bn': 'আপনার নিজের লেখা', 'ur': 'آپ کا اپنا متن',
    'ha': 'Rubutunku', 'fil': 'Sarili mong teksto',
  },
  'toneMasculine': {
    'ar': 'مذكر', 'en': 'Masculine', 'bn': 'পুংলিঙ্গ', 'ur': 'مذکر', 'ha': 'Namiji', 'fil': 'Panlalaki',
  },
  'toneFeminine': {
    'ar': 'مؤنث', 'en': 'Feminine', 'bn': 'স্ত্রীলিঙ্গ', 'ur': 'مؤنث', 'ha': 'Mace', 'fil': 'Pambabae',
  },
  'tplApproved': {
    'ar': 'جاهزة', 'en': 'Approved', 'bn': 'অনুমোদিত', 'ur': 'منظور شدہ', 'ha': 'An amince', 'fil': 'Aprubado',
  },
  'tplPending': {
    'ar': 'بانتظار المراجعة', 'en': 'Under review', 'bn': 'পর্যালোচনাধীন', 'ur': 'زیرِ جائزہ',
    'ha': 'Ana dubawa', 'fil': 'Sinusuri pa',
  },
  'tplPaused': {
    'ar': 'جودتها منخفضة', 'en': 'Low quality', 'bn': 'নিম্নমানের', 'ur': 'کم معیار', 'ha': 'Ƙarancin inganci',
    'fil': 'Mababang kalidad',
  },
  'tplDisabled': {
    'ar': 'معطّلة', 'en': 'Disabled', 'bn': 'নিষ্ক্রিয়', 'ur': 'غیر فعال', 'ha': 'An kashe', 'fil': 'Naka-disable',
  },
  'tplRejected': {
    'ar': 'مرفوضة', 'en': 'Rejected', 'bn': 'প্রত্যাখ্যাত', 'ur': 'مسترد', 'ha': 'An ƙi', 'fil': 'Tinanggihan',
  },
  'tplNotRegistered': {
    'ar': 'لم تُرفع بعد', 'en': 'Not submitted', 'bn': 'জমা হয়নি', 'ur': 'ابھی جمع نہیں',
    'ha': 'Ba a mika ba', 'fil': 'Hindi pa naisumite',
  },
  'afterPurchase': {
    'ar': 'بعد الشراء', 'en': 'After purchase', 'bn': 'কেনার পরে', 'ur': 'خریداری کے بعد',
    'ha': 'Bayan siyan', 'fil': 'Pagkatapos bumili',
  },
  'customerRight': {
    'ar': 'حق العميل', 'en': "Customer's own choice", 'bn': 'গ্রাহকের নিজস্ব অধিকার', 'ur': 'گاہک کا اپنا حق',
    'ha': 'Zaɓin abokin ciniki', 'fil': 'Sariling pili ng kustomer',
  },
  'crossLink': {
    'ar': 'أطلقها كحملة: {goal}', 'en': 'Launch as a campaign: {goal}', 'bn': 'ক্যাম্পেইন হিসেবে চালু করুন: {goal}',
    'ur': 'مہم کے طور پر شروع کریں: {goal}', 'ha': 'Kaddamar da shi a matsayin yaƙin talla: {goal}',
    'fil': 'Ilunsad bilang kampanya: {goal}',
  },
  'templatesFootnote': {
    'ar': 'كل رسالة هنا يرسلها النظام باسم محلك — تلقائيًا حين يحين وقتها، أو حين تطلقها بنفسك.',
    'en': 'Every message here is sent in your shop\'s name — automatically when its moment comes, or when you launch it yourself.',
    'bn': 'এখানে প্রতিটি বার্তা আপনার দোকানের নামে পাঠানো হয় — সময় হলে স্বয়ংক্রিয়ভাবে, অথবা আপনি নিজে চালু করলে।',
    'ur': 'یہاں ہر پیغام آپ کی دکان کے نام پر بھیجا جاتا ہے — وقت آنے پر خودکار طور پر، یا جب آپ خود شروع کریں۔',
    'ha': 'Kowane saƙo a nan ana aikawa da sunan shagon ku — ta atomatik lokacin da lokacinsa ya yi, ko lokacin da ku kanku kuka kaddamar da shi.',
    'fil': 'Bawat mensahe dito ay ipinapadala sa pangalan ng iyong tindahan — awtomatiko pagdating ng oras nito, o kapag ikaw mismo ang naglunsad.',
  },
  'classAll': {
    'ar': 'الكل', 'en': 'All', 'bn': 'সব', 'ur': 'تمام', 'ha': 'Duka', 'fil': 'Lahat',
  },
  'sendingNow': {
    'ar': 'تُرسَل الآن', 'en': 'Sending now', 'bn': 'এখন পাঠানো হচ্ছে', 'ur': 'ابھی بھیجی جا رہی ہے',
    'ha': 'Ana aikawa yanzu', 'fil': 'Ipinapadala ngayon',
  },
  'emptyUnread': {
    'ar': 'القوالب تُراجَع لدى واتساب، وقد تستغرق ساعات.',
    'en': 'Templates are under WhatsApp\'s review, which can take hours.',
    'bn': 'টেমপ্লেটগুলো হোয়াটসঅ্যাপের পর্যালোচনাধীন, যা ঘন্টা লাগতে পারে।',
    'ur': 'سانچے واٹس ایپ کے پاس زیرِ جائزہ ہیں، جس میں گھنٹے لگ سکتے ہیں۔',
    'ha': 'Samfura suna hannun WhatsApp don dubawa, wanda zai iya ɗaukar sa\'o\'i.',
    'fil': 'Nasa ilalim ng review ng WhatsApp ang mga template, na maaaring tumagal ng ilang oras.',
  },
  'emptyPending': {
    'ar': 'لم تُرفع أي صيغة لهذه الرسالة بعد.', 'en': 'No wording has been submitted for this message yet.',
    'bn': 'এই বার্তার জন্য এখনও কোনো ভাষা জমা দেওয়া হয়নি।', 'ur': 'اس پیغام کے لیے ابھی تک کوئی عبارت جمع نہیں ہوئی۔',
    'ha': 'Ba a mika wata magana da ta dace da wannan saƙo ba tukuna.',
    'fil': 'Wala pang naisumiteng pagkakasabi para sa mensaheng ito.',
  },
  'emptyNone': {
    'ar': 'لا صيغة متاحة لهذه الرسالة الآن.', 'en': 'No wording is available for this message right now.',
    'bn': 'এই বার্তার জন্য এখন কোনো ভাষা উপলব্ধ নেই।', 'ur': 'اس پیغام کے لیے ابھی کوئی عبارت دستیاب نہیں۔',
    'ha': 'Babu wata magana da ta dace da wannan saƙo a yanzu.',
    'fil': 'Walang available na pagkakasabi para sa mensaheng ito ngayon.',
  },
  'makeMyTone': {
    'ar': 'اجعل هذا صوت المحل', 'en': 'Make this my shop\'s voice', 'bn': 'এটিকে আমার দোকানের কণ্ঠ বানান',
    'ur': 'اسے میری دکان کی آواز بنائیں', 'ha': 'Mai da wannan muryar shagona',
    'fil': 'Gawing tinig ng aking tindahan ito',
  },
  'useIt': {
    'ar': 'استخدم هذا النص', 'en': 'Use this text', 'bn': 'এই লেখাটি ব্যবহার করুন', 'ur': 'یہ متن استعمال کریں',
    'ha': 'Yi amfani da wannan rubutu', 'fil': 'Gamitin ang tekstong ito',
  },
  'qualityGreen': {
    'ar': 'جودة عالية', 'en': 'High quality', 'bn': 'উচ্চ মান', 'ur': 'اعلیٰ معیار', 'ha': 'Babban inganci',
    'fil': 'Mataas na kalidad',
  },
  'qualityYellow': {
    'ar': 'جودة متوسطة', 'en': 'Medium quality', 'bn': 'মাঝারি মান', 'ur': 'درمیانہ معیار', 'ha': 'Matsakaicin inganci',
    'fil': 'Katamtamang kalidad',
  },
  'qualityRed': {
    'ar': 'جودة منخفضة', 'en': 'Low quality', 'bn': 'নিম্ন মান', 'ur': 'کم معیار', 'ha': 'Ƙarancin inganci',
    'fil': 'Mababang kalidad',
  },
  'logDenied': {
    'ar': 'لا صلاحية لديك لقراءة السجل.', 'en': "You don't have permission to read the log.",
    'bn': 'লগ পড়ার অনুমতি আপনার নেই।', 'ur': 'آپ کے پاس لاگ پڑھنے کی اجازت نہیں۔',
    'ha': 'Ba ku da izinin karanta bayanan tarihi.', 'fil': 'Wala kang pahintulot na basahin ang log.',
  },
  'logFailed': {
    'ar': 'تعذّرت قراءة السجل الآن.', 'en': "Couldn't read the log right now.",
    'bn': 'এই মুহূর্তে লগ পড়া যায়নি।', 'ur': 'ابھی لاگ پڑھا نہیں جا سکا۔', 'ha': 'An kasa karanta bayanan tarihi a yanzu.',
    'fil': 'Hindi nabasa ang log ngayon.',
  },
  'goalSearchHint': {
    'ar': 'ابحث عن هدف…', 'en': 'Search goals…', 'bn': 'লক্ষ্য খুঁজুন…', 'ur': 'مقاصد تلاش کریں…',
    'ha': 'Bincika manufa…', 'fil': 'Maghanap ng layunin…',
  },
  'whichPackage': {
    'ar': 'أي باقة؟', 'en': 'Which package?', 'bn': 'কোন প্যাকেজ?', 'ur': 'کون سا پیکج؟', 'ha': 'Wane fakiti?',
    'fil': 'Aling package?',
  },
  'rewardTitle': {
    'ar': 'نوع المكافأة', 'en': 'Reward type', 'bn': 'পুরস্কারের ধরন', 'ur': 'انعام کی قسم', 'ha': "Nau'in lada",
    'fil': 'Uri ng gantimpala',
  },
  'rewardDiscount': {
    'ar': 'خصم', 'en': 'Discount', 'bn': 'ছাড়', 'ur': 'رعایت', 'ha': 'Rangwame', 'fil': 'Diskwento',
  },
  'rewardGift': {
    'ar': 'هدية', 'en': 'Gift', 'bn': 'উপহার', 'ur': 'تحفہ', 'ha': 'Kyauta', 'fil': 'Regalo',
  },
  'rewardPoints': {
    'ar': 'نقاط', 'en': 'Points', 'bn': 'পয়েন্ট', 'ur': 'پوائنٹس', 'ha': 'Maki', 'fil': 'Puntos',
  },
  'rewardPointsHint': {
    'ar': 'كم نقطة؟', 'en': 'How many points?', 'bn': 'কত পয়েন্ট?', 'ur': 'کتنے پوائنٹس؟', 'ha': 'Maki nawa?',
    'fil': 'Ilang puntos?',
  },
  'rewardGiftHint': {
    'ar': 'الهدية هي الخدمة أو الباقة التي اخترتها أعلاه، مجانًا.',
    'en': 'The gift is the service or package you picked above, free.',
    'bn': 'উপহার হলো উপরে বেছে নেওয়া সার্ভিস বা প্যাকেজ, বিনামূল্যে।',
    'ur': 'تحفہ وہ سروس یا پیکج ہے جو آپ نے اوپر منتخب کیا، مفت۔',
    'ha': 'Kyautar ita ce sabis ko fakitin da kuka zaɓa a sama, kyauta.',
    'fil': 'Ang regalo ay ang serbisyo o package na pinili mo sa itaas, libre.',
  },
  'loyaltyTitle': {
    'ar': 'من هم عملاؤك المخلصون؟', 'en': 'Who are your loyal customers?', 'bn': 'আপনার অনুগত গ্রাহক কারা?',
    'ur': 'آپ کے وفادار گاہک کون ہیں؟', 'ha': 'Su waye amintattun abokan cinikin ku?',
    'fil': 'Sino ang mga tapat mong kustomer?',
  },
  'loyaltyWindowLabel': {
    'ar': 'خلال {n} يوم', 'en': 'Within {n} days', 'bn': '{n} দিনের মধ্যে', 'ur': '{n} دن کے اندر',
    'ha': 'Cikin kwana {n}', 'fil': 'Sa loob ng {n} araw',
  },
  'loyaltyMinVisitsLabel': {
    'ar': '{n} زيارات على الأقل', 'en': 'At least {n} visits', 'bn': 'কমপক্ষে {n} ভিজিট',
    'ur': 'کم از کم {n} وزٹ', 'ha': 'Aƙalla ziyara {n}', 'fil': 'Kahit {n} beses bumisita',
  },
  'occasionDayLabel': {
    'ar': 'يوم المناسبة', 'en': 'The occasion day', 'bn': 'উপলক্ষ্যের দিন', 'ur': 'موقع کا دن',
    'ha': 'Ranar taron', 'fil': 'Araw ng okasyon',
  },
  'milestoneTitle': {
    'ar': 'الهدف الجماعي', 'en': 'Community goal', 'bn': 'সামষ্টিক লক্ষ্য', 'ur': 'اجتماعی ہدف',
    'ha': "Manufar al'umma", 'fil': 'Layunin ng komunidad',
  },
  'milestoneThresholdLabel': {
    'ar': 'كم عميل لازم يوصلوا؟', 'en': 'How many customers must reach it?',
    'bn': 'কতজন গ্রাহক পৌঁছাতে হবে?', 'ur': 'کتنے گاہکوں کا پہنچنا ضروری ہے؟',
    'ha': 'Nawa abokan ciniki dole su kai?', 'fil': 'Ilang customer ang dapat umabot?',
  },
  'milestoneThresholdHint': {
    'ar': 'العرض يفتح لكل من ساهم، دفعة واحدة، أول ما يوصلون هذا العدد.',
    'en': 'The offer opens for everyone who contributed, all at once, the moment this number is reached.',
    'bn': 'যারা অবদান রেখেছেন তাদের সবার জন্য একসাথে অফারটি খুলে যায়, এই সংখ্যায় পৌঁছানোর সাথে সাথে।',
    'ur': 'یہ پیشکش ہر اس شخص کے لیے کھلتی ہے جس نے حصہ لیا، ایک ساتھ، جیسے ہی یہ تعداد پوری ہو جائے۔',
    'ha': 'Tayin yana buɗewa ga duk wanda ya ba da gudummawa, lokaci ɗaya, da zarar an kai wannan adadin.',
    'fil': 'Bubukas ang alok para sa lahat ng nag-ambag, sabay-sabay, sa sandaling maabot ang bilang na ito.',
  },
  'milestoneRecurringLabel': {
    'ar': 'يتكرر تلقائياً', 'en': 'Repeats automatically', 'bn': 'স্বয়ংক্রিয়ভাবে পুনরাবৃত্তি হবে',
    'ur': 'خودکار طور پر دہرائیں', 'ha': 'Yana maimaitawa kansa', 'fil': 'Awtomatikong uulitin',
  },
  'milestoneRecurringHint': {
    'ar': 'يبدأ عدّاد جديد بنفس المدة أول ما تنتهي كل جولة. فعّل «متى تُطلق» بتاريخ محدد ليكون هذا واضحاً.',
    'en': 'A new round starts with the same length the moment each one ends. Turn on "When does it launch?" with a set date to make this clear.',
    'bn': 'প্রতিটি রাউন্ড শেষ হওয়ার সাথে সাথে একই দৈর্ঘ্যের নতুন রাউন্ড শুরু হবে। এটি স্পষ্ট রাখতে "কখন চালু হবে?"-এ একটি নির্দিষ্ট তারিখ চালু করুন।',
    'ur': 'ہر دور ختم ہوتے ہی اسی مدت کے ساتھ نیا دور شروع ہوگا۔ اسے واضح رکھنے کے لیے "کب شروع ہوگی؟" میں مقررہ تاریخ آن کریں۔',
    'ha': 'Sabon zagaye yana farawa da tsawon lokaci iri ɗaya da zarar kowanne ya ƙare. Kunna "Yaushe za a kaddamar?" da takamaiman rana don wannan ya bayyana.',
    'fil': 'Magsisimula ang bagong round nang parehong haba sa sandaling matapos ang bawat isa. I-on ang "Kailan ilulunsad?" na may nakatakdang petsa para malinaw ito.',
  },
  'whenTitle': {
    'ar': 'متى تُطلق؟', 'en': 'When does it launch?', 'bn': 'কখন চালু হবে?', 'ur': 'کب شروع ہوگی؟',
    'ha': 'Yaushe za a kaddamar?', 'fil': 'Kailan ilulunsad?',
  },
  'whenNow': {
    'ar': 'الآن', 'en': 'Now', 'bn': 'এখন', 'ur': 'ابھی', 'ha': 'Yanzu', 'fil': 'Ngayon',
  },
  'whenLater': {
    'ar': 'لاحقًا', 'en': 'Later', 'bn': 'পরে', 'ur': 'بعد میں', 'ha': 'Daga baya', 'fil': 'Mamaya',
  },
  'windowTitle': {
    'ar': 'نافذة تكرار (اختياري)', 'en': 'Recurring window (optional)', 'bn': 'পুনরাবৃত্তি উইন্ডো (ঐচ্ছিক)',
    'ur': 'تکراری ونڈو (اختیاری)', 'ha': 'Taga maimaitawa (na zaɓi)', 'fil': 'Umuulit na window (opsyonal)',
  },
  'windowHoursLabel': {
    'ar': 'من الساعة {start} إلى {end}', 'en': 'From {start} to {end}', 'bn': '{start} থেকে {end} পর্যন্ত',
    'ur': '{start} سے {end} تک', 'ha': 'Daga karfe {start} zuwa {end}', 'fil': 'Mula {start} hanggang {end}',
  },
  'weekdayMon': {'ar': 'إثنين', 'en': 'Mon', 'bn': 'সোম', 'ur': 'پیر', 'ha': 'Lit', 'fil': 'Lun'},
  'weekdayTue': {'ar': 'ثلاثاء', 'en': 'Tue', 'bn': 'মঙ্গল', 'ur': 'منگل', 'ha': 'Tal', 'fil': 'Mar'},
  'weekdayWed': {'ar': 'أربعاء', 'en': 'Wed', 'bn': 'বুধ', 'ur': 'بدھ', 'ha': 'Lar', 'fil': 'Miy'},
  'weekdayThu': {'ar': 'خميس', 'en': 'Thu', 'bn': 'বৃহস্পতি', 'ur': 'جمعرات', 'ha': 'Alh', 'fil': 'Huw'},
  'weekdayFri': {'ar': 'جمعة', 'en': 'Fri', 'bn': 'শুক্র', 'ur': 'جمعہ', 'ha': 'Jum', 'fil': 'Biy'},
  'weekdaySat': {'ar': 'سبت', 'en': 'Sat', 'bn': 'শনি', 'ur': 'ہفتہ', 'ha': 'Asa', 'fil': 'Sab'},
  'weekdaySun': {'ar': 'أحد', 'en': 'Sun', 'bn': 'রবি', 'ur': 'اتوار', 'ha': 'Lah', 'fil': 'Lin'},
  'branchLabel': {
    'ar': 'الفرع المستهدف', 'en': 'Target branch', 'bn': 'লক্ষ্য শাখা', 'ur': 'ہدف شاخ', 'ha': 'Rukunin da aka nufa',
    'fil': 'Target na sangay',
  },
  'viewOrEditMessage': {
    'ar': 'اعرض/عدّل الرسالة الآلية', 'en': 'View/edit the automatic message', 'bn': 'স্বয়ংক্রিয় বার্তা দেখুন/সম্পাদনা করুন',
    'ur': 'خودکار پیغام دیکھیں/ترمیم کریں', 'ha': 'Duba/gyara saƙon atomatik', 'fil': 'Tingnan/i-edit ang awtomatikong mensahe',
  },
  'urgencySoon': {
    'ar': 'قريب', 'en': 'Soon', 'bn': 'শীঘ্রই', 'ur': 'جلد', 'ha': 'Nan gaba kadan', 'fil': 'Malapit na',
  },
  'urgencyToday': {
    'ar': 'اليوم', 'en': 'Today', 'bn': 'আজ', 'ur': 'آج', 'ha': 'Yau', 'fil': 'Ngayon',
  },
  'urgencyLater': {
    'ar': 'لاحقًا', 'en': 'Later', 'bn': 'পরে', 'ur': 'بعد میں', 'ha': 'Daga baya', 'fil': 'Mamaya',
  },
  'allBranches': {
    'ar': 'كل الفروع', 'en': 'All branches', 'bn': 'সব শাখা', 'ur': 'تمام شاخیں', 'ha': 'Duk rassa',
    'fil': 'Lahat ng sangay',
  },
  'noBranch': {
    'ar': 'بلا فرع محدَّد', 'en': 'No branch specified', 'bn': 'কোনো শাখা নির্দিষ্ট নেই', 'ur': 'کوئی شاخ متعین نہیں',
    'ha': 'Ba a ƙayyade reshe ba', 'fil': 'Walang tinukoy na sangay',
  },
  'interactive': {
    'ar': 'تفاعلي', 'en': 'Interactive', 'bn': 'ইন্টারেক্টিভ', 'ur': 'انٹرایکٹو', 'ha': 'Mai hulɗa',
    'fil': 'Interactive',
  },
  'filterInteractive': {
    'ar': 'تفاعلي فقط', 'en': 'Interactive only', 'bn': 'শুধু ইন্টারেক্টিভ', 'ur': 'صرف انٹرایکٹو',
    'ha': 'Masu hulɗa kaɗai', 'fil': 'Interactive lang',
  },
  'filterAutoOnly': {
    'ar': 'آلي فقط', 'en': 'Automatic only', 'bn': 'শুধু স্বয়ংক্রিয়', 'ur': 'صرف خودکار', 'ha': 'Atomatik kaɗai',
    'fil': 'Awtomatiko lang',
  },
  'yesterday': {
    'ar': 'أمس', 'en': 'Yesterday', 'bn': 'গতকাল', 'ur': 'کل', 'ha': 'Jiya', 'fil': 'Kahapon',
  },
  'daysAgo': {
    'ar': 'قبل {n} أيام', 'en': '{n} days ago', 'bn': '{n} দিন আগে', 'ur': '{n} دن پہلے',
    'ha': 'Kwana {n} da suka wuce', 'fil': '{n} araw ang nakalipas',
  },
  'trendLabel': {
    'ar': 'الإرسال عبر الأيام', 'en': 'Sends over time', 'bn': 'সময়ের সাথে পাঠানো', 'ur': 'وقت کے ساتھ بھیجنا',
    'ha': 'Aikawa a kan lokaci', 'fil': 'Mga pagpapadala sa paglipas ng panahon',
  },
  'kpiReach': {
    'ar': 'الوصول الكلي', 'en': 'Total reach', 'bn': 'মোট পৌঁছানো', 'ur': 'کل رسائی', 'ha': 'Jimlar isarwa',
    'fil': 'Kabuuang naabot',
  },
  'flowFetchFailed': {
    'ar': 'تعذّر جلب الفلو.', 'en': "Couldn't fetch the Flow.", 'bn': 'ফ্লো আনা যায়নি।', 'ur': 'فلو حاصل نہیں ہو سکا۔',
    'ha': 'An kasa samo Flow.', 'fil': 'Hindi nakuha ang Flow.',
  },
  'backToMessage': {
    'ar': 'رجوع للرسالة', 'en': 'Back to the message', 'bn': 'বার্তায় ফিরে যান', 'ur': 'پیغام پر واپس جائیں',
    'ha': 'Koma zuwa saƙon', 'fil': 'Bumalik sa mensahe',
  },
  'writeYourText': {
    'ar': 'اكتب نصّك الخاص', 'en': 'Write your own text', 'bn': 'নিজের লেখা লিখুন', 'ur': 'اپنا متن لکھیں',
    'ha': 'Rubuta rubutunku', 'fil': 'Isulat ang sarili mong teksto',
  },
  'cannotWriteNote': {
    'ar': 'هذه الرسالة حقّ للعميل، فلا يمكن تخصيص نصّها.', 'en': "This message is the customer's own right — its text cannot be customised.",
    'bn': 'এই বার্তা গ্রাহকের নিজস্ব অধিকার — এর লেখা কাস্টমাইজ করা যায় না।',
    'ur': 'یہ پیغام گاہک کا اپنا حق ہے — اس کا متن حسبِ ضرورت نہیں بنایا جا سکتا۔',
    'ha': 'Wannan saƙo hakkin abokin ciniki ne — ba za a iya gyara rubutunsa ba.',
    'fil': 'Ang mensaheng ito ay sariling karapatan ng kustomer — hindi maaaring i-customize ang teksto nito.',
  },
  'submitToWhatsapp': {
    'ar': 'ارفعه لواتساب', 'en': 'Submit to WhatsApp', 'bn': 'হোয়াটসঅ্যাপে জমা দিন', 'ur': 'واٹس ایپ کو جمع کریں',
    'ha': 'Mika zuwa WhatsApp', 'fil': 'Isumite sa WhatsApp',
  },
  'helpMe': {
    'ar': 'ساعدوني', 'en': 'Help me', 'bn': 'আমাকে সাহায্য করুন', 'ur': 'میری مدد کریں', 'ha': 'Ku taimake ni',
    'fil': 'Tulungan ako',
  },
  'requestReceived': {
    'ar': 'وصلنا طلبك، سنتواصل معك قريبًا.', 'en': "We got your request — we'll be in touch soon.",
    'bn': 'আপনার অনুরোধ পেয়েছি — শীঘ্রই যোগাযোগ করবো।', 'ur': 'آپ کی درخواست موصول ہوگئی — جلد رابطہ کریں گے۔',
    'ha': 'Mun karɓi buƙatarku — za mu tuntuɓe ku nan ba da jimawa ba.',
    'fil': 'Natanggap namin ang kahilingan mo — makikipag-ugnayan kami sa lalong madaling panahon.',
  },
  'textEditorTitle': {
    'ar': 'اكتب نصّك — {label}', 'en': 'Write your text — {label}', 'bn': 'আপনার লেখা লিখুন — {label}',
    'ur': 'اپنا متن لکھیں — {label}', 'ha': 'Rubuta rubutunku — {label}', 'fil': 'Isulat ang teksto mo — {label}',
  },
  'textEditorSubtitle': {
    'ar': 'اختر الفراغات من الأزرار، والترقيم يُولَّد تلقائيًا.',
    'en': 'Pick blanks from the buttons above — the numbering is generated automatically.',
    'bn': 'উপরের বোতাম থেকে ফাঁকা স্থান বাছাই করুন — নম্বরিং স্বয়ংক্রিয়ভাবে তৈরি হয়।',
    'ur': 'اوپر بٹنوں سے خالی جگہیں چنیں — نمبرنگ خودکار بنتی ہے۔',
    'ha': 'Zaɓi wuraren fanko daga maɓallan — ana ƙirƙirar lambobi ta atomatik.',
    'fil': 'Pumili ng mga blangko mula sa mga button sa itaas — awtomatikong bubuo ang numbering.',
  },
  'textEditorEmptyError': {
    'ar': 'اكتب نصًا قبل الحفظ.', 'en': 'Write some text before saving.', 'bn': 'সংরক্ষণের আগে কিছু লিখুন।',
    'ur': 'محفوظ کرنے سے پہلے کچھ لکھیں۔', 'ha': 'Rubuta wani abu kafin ajiyewa.', 'fil': 'Sumulat muna bago mag-save.',
  },
  'textEditorContinueHint': {
    'ar': 'أكمل الكتابة هنا…', 'en': 'Keep typing here…', 'bn': 'এখানে লিখতে থাকুন…', 'ur': 'یہاں لکھتے رہیں…',
    'ha': 'Ci gaba da rubutu a nan…', 'fil': 'Magpatuloy sa pagsulat dito…',
  },
  'textEditorMandatoryLine': {
    'ar': 'ستُضاف تلقائيًا:', 'en': 'Automatically added:', 'bn': 'স্বয়ংক্রিয়ভাবে যোগ হবে:', 'ur': 'خودکار طور پر شامل ہوگا:',
    'ha': 'Za a ƙara ta atomatik:', 'fil': 'Awtomatikong idadagdag:',
  },
  'textEditorPreviewTitle': {
    'ar': 'كما يصل عميلك', 'en': 'As your customer receives it', 'bn': 'আপনার গ্রাহক যেভাবে পান',
    'ur': 'جیسا آپ کے گاہک کو پہنچتا ہے', 'ha': 'Kamar yadda abokin cinikinku ke karɓa', 'fil': 'Gaya ng matatanggap ng iyong kustomer',
  },
  'textEditorApprovalNote': {
    'ar': 'تراجعه واتساب بعد الرفع، وقد يستغرق يومًا.', 'en': 'WhatsApp reviews it after you submit — can take a day.',
    'bn': 'জমা দেওয়ার পর হোয়াটসঅ্যাপ এটি পর্যালোচনা করে — এক দিন লাগতে পারে।',
    'ur': 'جمع کرانے کے بعد واٹس ایپ اس کا جائزہ لیتا ہے — ایک دن لگ سکتا ہے۔',
    'ha': 'WhatsApp na duba shi bayan mikawa — zai iya ɗaukar kwana ɗaya.',
    'fil': 'Sinusuri ito ng WhatsApp pagkatapos mong isumite — maaaring tumagal ng isang araw.',
  },
  'textEditorSave': {
    'ar': 'حفظ', 'en': 'Save', 'bn': 'সংরক্ষণ', 'ur': 'محفوظ کریں', 'ha': 'Ajiye', 'fil': 'I-save',
  },
  'sar': {
    'ar': 'ريال', 'en': 'SAR', 'bn': 'রিয়াল', 'ur': 'ریال', 'ha': 'Riyal', 'fil': 'SAR',
  },
  'backToOurs': {
    'ar': 'ارجع لنصّنا', 'en': 'Go back to ours', 'bn': 'আমাদেরটায় ফিরে যান', 'ur': 'ہمارے پر واپس جائیں',
    'ha': 'Koma zuwa namu', 'fil': 'Bumalik sa amin',
  },
};

/// Looks up [key] in the current [BuildContext]'s locale, falling back to Arabic (this feature's
/// own source-of-truth language) if the locale is somehow missing from the table — never a raw
/// key, which would read as an obvious bug rather than a missing translation.
String ct(BuildContext context, String key, [Map<String, String>? params]) {
  final code = Localizations.maybeLocaleOf(context)?.languageCode ?? 'ar';
  final table = _kCampaignsStrings[key];
  var text = table?[code] ?? table?['ar'] ?? key;
  if (params != null) {
    for (final entry in params.entries) {
      text = text.replaceAll('{${entry.key}}', entry.value);
    }
  }
  return text;
}
