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
