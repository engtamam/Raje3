/**
 * Points.tsx's own strings — registered once at import time (see operator-i18n.tsx's own header
 * for why this is a small per-screen file rather than one giant dictionary).
 *
 * MACHINE-ASSISTED, NOT NATIVE-REVIEWED. ar/en are the product's own, written with the same care
 * as the screen itself. ur/ha/fil were produced in this pass to unblock the mechanism end to end
 * — get a real operator reading his own language today rather than none at all — but they have
 * NOT been checked by a native speaker. Flagged explicitly rather than shipped silently: a wrong
 * word in a reward setting is a worse failure than the Arabic fallback it replaces. Review before
 * this reaches a shop that actually has Urdu/Hausa/Filipino-speaking staff on the floor.
 */
import { registerOperatorStrings } from '../operator-i18n';

registerOperatorStrings({
  ar: {
    'points.percentValue': '{n}٪',
    'points.type.service.label': 'من خدماتي',
    'points.type.service.hint': 'يختار ما يحصل عليه مما تقدّمه — خدمةً كان أو منتجاً',
    'points.type.item.label': 'هدية',
    'points.type.item.hint': 'شيء من خارج ما تقدّمه — الاسم يكفي',
    'points.type.discount.label': 'خصم',
    'points.type.discount.hint': 'مبلغ يُخصم من الزيارة',

    'points.error.saveFailed': 'تعذّر الحفظ.',
    'points.error.discountAmount': 'اكتب مبلغ الخصم بالريال — رقمٌ بمنزلتين عشريتين على الأكثر، مثل 2.30',
    'points.error.addFailed': 'تعذّر إضافة المكافأة.',
    'points.error.modeChangeFailed': 'تعذّر تغيير طريقة الاحتساب',

    'points.waiting': 'نقرأ نقاطك وجوائزك',

    'points.kpi.customers': 'عميل يجمع نقاطاً',
    'points.kpi.redemptions': 'استبدال',
    'points.kpi.outstanding': 'نقطة لم تُستبدل بعد',
    'points.kpi.outstanding.hint': 'ما وعدت به ولم يُصرف — وهو التزام على محلّك.',
    'points.kpi.expiredShare': 'من كل نقطة مُنحت، انتهت بلا استبدال',
    'points.kpi.expiredShare.hint': 'نسبة عالية تعني أن حدود مكافآتك بعيدة عن متناول عملائك.',

    'points.topRewards.title': 'أكثر ما يُستبدل',
    'points.noName': 'بلا اسم',

    'points.tabsAriaLabel': 'أقسام النقاط',
    'points.tab.rewards': 'المكافآت',
    'points.tab.earning': 'الكسب',

    'points.table.title': 'جدول المكافآت',
    'points.table.said': 'ما يستبدله عميلك بنقاطه — ويصل معبّأً لقطاعك.',
    'points.addReward': 'إضافة مكافأة',

    'points.form.name.label': 'اسم المكافأة',
    'points.form.name.hint': 'يظهر في رسالة واتساب للعميل — اجعله قصيراً',
    'points.form.cost.label': 'التكلفة بالنقاط',
    'points.form.type.label': 'النوع',
    'points.form.riyals.label': 'مبلغ الخصم بالريال',
    'points.form.service.label': 'ما يحصل عليه',
    'points.form.service.hint': 'مما تقدّمه — خدمةً كان أو منتجاً',
    'points.save': 'حفظ',
    'points.cancel': 'إلغاء',

    'points.loadFailed.title': 'تعذّرت قراءة جدول المكافآت',
    'points.loadFailed.description': 'لم نستطع جلبه الآن، والخلل عندنا. أعد المحاولة بعد قليل.',
    'points.empty.title': 'لا مكافآت بعد',
    'points.empty.description': 'أضف أول مكافأة: اختر خدمة، وكم زيارة تُستحق بها.',

    'points.costAriaLabel': 'تكلفة {name} بالنقاط',
    'points.pointUnit': 'نقطة',
    'points.stoppedBadge': 'موقوفة',
    'points.activate': 'تفعيل',
    'points.deactivate': 'إيقاف — يختفي من قائمة الاستبدال',
    'points.deactivateShort': 'إيقاف',

    'points.settingsWaiting.title': 'نقرأ إعدادات النقاط',
    'points.settingsWaiting.description': 'لحظة واحدة.',
    'points.settingsFailed.title': 'تعذّرت قراءة إعدادات النقاط',
    'points.settingsFailed.description': 'لم نعرضها كي لا تُعدّل رقماً على غير أصله — قواعد محلك كما هي. أعد المحاولة.',

    'points.mode.title': 'طريقة الاحتساب',
    'points.mode.said': 'بالخدمات: كل خدمة نقاطها. بقيمة الفاتورة: نقطة لكل ريال.',
    'points.mode.ariaLabel': 'طريقة احتساب النقاط',
    'points.mode.services': 'بالخدمات',
    'points.mode.invoice': 'بقيمة الفاتورة',
    'points.mode.needsPricedServices': 'الاحتساب بقيمة الفاتورة يحتاج كل خدماتك مسعّرة أولاً — سعّرها كلها في «خدماتي» ثم فعّله.',

    'points.general.label': 'نقاط لكل زيارة (عام)',
    'points.general.hint': 'كل خدمة بلا رقم خاص تأخذ هذا الرقم.',

    'points.threshold.label': 'مكافأة تحتاج اعتماد المدير من',
    'points.threshold.hint': 'أي مكافأة بهذه النقاط فأكثر تحتاج اسم المدير عند الاستبدال. 0 يعني لا اعتماد.',

    'points.group.title': 'نقاط مجموعة',
    'points.group.said': 'تسري على كل خدمة في المجموعة لم تُخصَّص وحدها.',
    'points.group.ariaLabel': 'نقاط مجموعة {group}',

    'points.perService.title': 'نقاط خدمة بعينها',
    'points.perService.said': 'رقمٌ خاص يتقدّم على المجموعة وعلى العام.',
    'points.customSetting': 'إعداد خاص',
    'points.serviceAriaLabel': 'نقاط {name}',
    'points.returnToGeneral': 'العودة إلى العام',
  },
  en: {
    'points.percentValue': '{n}%',
    'points.type.service.label': 'From my services',
    'points.type.service.hint': 'He picks what he gets from what you offer — a service or a product',
    'points.type.item.label': 'Gift',
    'points.type.item.hint': 'Something outside what you offer — the name is enough',
    'points.type.discount.label': 'Discount',
    'points.type.discount.hint': 'An amount deducted from the visit',

    'points.error.saveFailed': 'Could not save.',
    'points.error.discountAmount': 'Enter the discount amount in SAR — a number with at most two decimal places, like 2.30',
    'points.error.addFailed': 'Could not add the reward.',
    'points.error.modeChangeFailed': 'Could not change the earning mode',

    'points.waiting': 'Reading your points and rewards',

    'points.kpi.customers': 'Customers earning points',
    'points.kpi.redemptions': 'Redemptions',
    'points.kpi.outstanding': 'Points not yet redeemed',
    'points.kpi.outstanding.hint': 'What you promised and hasn’t been spent — an obligation on your shop.',
    'points.kpi.expiredShare': 'Of every point granted, expired unredeemed',
    'points.kpi.expiredShare.hint': 'A high share means your reward thresholds sit beyond what your customers actually reach.',

    'points.topRewards.title': 'Most redeemed',
    'points.noName': 'No name',

    'points.tabsAriaLabel': 'Points sections',
    'points.tab.rewards': 'Rewards',
    'points.tab.earning': 'Earning',

    'points.table.title': 'Rewards table',
    'points.table.said': 'What your customer redeems with his points — and it arrives pre-filled for your trade.',
    'points.addReward': 'Add a reward',

    'points.form.name.label': 'Reward name',
    'points.form.name.hint': 'Shown in a WhatsApp message to the customer — keep it short',
    'points.form.cost.label': 'Cost in points',
    'points.form.type.label': 'Type',
    'points.form.riyals.label': 'Discount amount in SAR',
    'points.form.service.label': 'What he gets',
    'points.form.service.hint': 'From what you offer — a service or a product',
    'points.save': 'Save',
    'points.cancel': 'Cancel',

    'points.loadFailed.title': 'Could not read the rewards table',
    'points.loadFailed.description': 'We could not fetch it right now, and the fault is ours. Try again shortly.',
    'points.empty.title': 'No rewards yet',
    'points.empty.description': 'Add your first reward: pick a service, and how many visits earn it.',

    'points.costAriaLabel': 'Cost of {name} in points',
    'points.pointUnit': 'points',
    'points.stoppedBadge': 'Stopped',
    'points.activate': 'Activate',
    'points.deactivate': 'Deactivate — disappears from the redemption list',
    'points.deactivateShort': 'Deactivate',

    'points.settingsWaiting.title': 'Reading points settings',
    'points.settingsWaiting.description': 'One moment.',
    'points.settingsFailed.title': 'Could not read points settings',
    'points.settingsFailed.description': 'We did not show it so you would not edit a number away from its true value — your shop’s rules stay as they are. Try again.',

    'points.mode.title': 'Earning method',
    'points.mode.said': 'By service: each service has its own points. By invoice value: one point per riyal.',
    'points.mode.ariaLabel': 'Points earning method',
    'points.mode.services': 'By service',
    'points.mode.invoice': 'By invoice value',
    'points.mode.needsPricedServices': 'Earning by invoice value needs every service priced first — price them all in «Services», then turn it on.',

    'points.general.label': 'Points per visit (general)',
    'points.general.hint': 'Every service with no number of its own takes this one.',

    'points.threshold.label': 'A reward needs manager approval from',
    'points.threshold.hint': 'Any reward at this many points or more needs the manager’s name at redemption. 0 means no approval.',

    'points.group.title': 'Group points',
    'points.group.said': 'Applies to every service in the group that hasn’t been customized on its own.',
    'points.group.ariaLabel': 'Points for group {group}',

    'points.perService.title': 'Points for a specific service',
    'points.perService.said': 'A number of its own that overrides the group and the general setting.',
    'points.customSetting': 'Custom setting',
    'points.serviceAriaLabel': 'Points of {name}',
    'points.returnToGeneral': 'Return to general',
  },
  ur: {
    'points.percentValue': '{n}٪',
    'points.type.service.label': 'میری خدمات میں سے',
    'points.type.service.hint': 'وہ چیز چنیں جو آپ کی پیشکش میں سے ملے — خدمت ہو یا مصنوعہ',
    'points.type.item.label': 'تحفہ',
    'points.type.item.hint': 'آپ کی پیشکش سے باہر کی کوئی چیز — نام کافی ہے',
    'points.type.discount.label': 'رعایت',
    'points.type.discount.hint': 'وزٹ سے کاٹی جانے والی رقم',

    'points.error.saveFailed': 'محفوظ نہیں ہو سکا۔',
    'points.error.discountAmount': 'رعایت کی رقم ریال میں لکھیں — زیادہ سے زیادہ دو اعشاریہ خانوں والا نمبر، مثلاً 2.30',
    'points.error.addFailed': 'مکافات شامل نہیں ہو سکی۔',
    'points.error.modeChangeFailed': 'احتساب کا طریقہ تبدیل نہیں ہو سکا',

    'points.waiting': 'آپ کے پوائنٹس اور مکافات پڑھی جا رہی ہیں',

    'points.kpi.customers': 'پوائنٹس جمع کرنے والے گاہک',
    'points.kpi.redemptions': 'تبادلے',
    'points.kpi.outstanding': 'ابھی تک نہ بدلے گئے پوائنٹس',
    'points.kpi.outstanding.hint': 'جو آپ نے وعدہ کیا اور خرچ نہیں ہوا — یہ آپ کی دکان پر ذمہ داری ہے۔',
    'points.kpi.expiredShare': 'ہر دیے گئے پوائنٹ میں سے، بغیر بدلے ختم ہوا',
    'points.kpi.expiredShare.hint': 'زیادہ تناسب کا مطلب ہے آپ کی مکافات کی حدیں آپ کے گاہکوں کی پہنچ سے باہر ہیں۔',

    'points.topRewards.title': 'سب سے زیادہ بدلی جانے والی',
    'points.noName': 'بلا نام',

    'points.tabsAriaLabel': 'پوائنٹس کے حصے',
    'points.tab.rewards': 'مکافات',
    'points.tab.earning': 'کمائی',

    'points.table.title': 'مکافات کی فہرست',
    'points.table.said': 'جو آپ کا گاہک اپنے پوائنٹس سے بدلتا ہے — اور آپ کے شعبے کے لیے پہلے سے بھری ہوئی آتی ہے۔',
    'points.addReward': 'مکافات شامل کریں',

    'points.form.name.label': 'مکافات کا نام',
    'points.form.name.hint': 'گاہک کو واٹس ایپ پیغام میں دکھایا جاتا ہے — مختصر رکھیں',
    'points.form.cost.label': 'پوائنٹس میں قیمت',
    'points.form.type.label': 'قسم',
    'points.form.riyals.label': 'رعایت کی رقم ریال میں',
    'points.form.service.label': 'اسے کیا ملتا ہے',
    'points.form.service.hint': 'آپ کی پیشکش میں سے — خدمت ہو یا مصنوعہ',
    'points.save': 'محفوظ کریں',
    'points.cancel': 'منسوخ کریں',

    'points.loadFailed.title': 'مکافات کی فہرست نہیں پڑھی جا سکی',
    'points.loadFailed.description': 'ہم اسے ابھی حاصل نہیں کر سکے، اور خرابی ہماری طرف سے ہے۔ تھوڑی دیر بعد دوبارہ کوشش کریں۔',
    'points.empty.title': 'ابھی کوئی مکافات نہیں',
    'points.empty.description': 'اپنی پہلی مکافات شامل کریں: خدمت چنیں، اور کتنی وزٹس پر یہ ملتی ہے۔',

    'points.costAriaLabel': '{name} کی پوائنٹس میں قیمت',
    'points.pointUnit': 'پوائنٹ',
    'points.stoppedBadge': 'بند',
    'points.activate': 'فعال کریں',
    'points.deactivate': 'بند کریں — تبادلے کی فہرست سے غائب ہو جاتی ہے',
    'points.deactivateShort': 'بند کریں',

    'points.settingsWaiting.title': 'پوائنٹس کی سیٹنگز پڑھی جا رہی ہیں',
    'points.settingsWaiting.description': 'ایک لمحہ۔',
    'points.settingsFailed.title': 'پوائنٹس کی سیٹنگز نہیں پڑھی جا سکیں',
    'points.settingsFailed.description': 'ہم نے یہ نہیں دکھائیں تاکہ آپ کسی نمبر کو اس کی اصل قیمت سے ہٹا کر تبدیل نہ کریں — آپ کی دکان کے قواعد ویسے ہی رہتے ہیں۔ دوبارہ کوشش کریں۔',

    'points.mode.title': 'احتساب کا طریقہ',
    'points.mode.said': 'خدمات کے حساب سے: ہر خدمت کے اپنے پوائنٹس۔ فاتورہ کی قیمت کے حساب سے: ہر ریال پر ایک پوائنٹ۔',
    'points.mode.ariaLabel': 'پوائنٹس کے احتساب کا طریقہ',
    'points.mode.services': 'خدمات کے حساب سے',
    'points.mode.invoice': 'فاتورہ کی قیمت کے حساب سے',
    'points.mode.needsPricedServices': 'فاتورے کی قیمت کے حساب سے احتساب کے لیے پہلے ہر سروس کی قیمت مقرر ہونی چاہیے — سب کی قیمت «میری سروسز» میں مقرر کریں، پھر اسے فعال کریں۔',

    'points.general.label': 'ہر وزٹ پر پوائنٹس (عمومی)',
    'points.general.hint': 'ہر وہ خدمت جس کا اپنا نمبر نہیں یہی نمبر لیتی ہے۔',

    'points.threshold.label': 'مکافات کو مینیجر کی منظوری چاہیے اس سے',
    'points.threshold.hint': 'اس تعداد یا اس سے زیادہ پوائنٹس والی کسی بھی مکافات کو تبادلے پر مینیجر کا نام چاہیے۔ 0 کا مطلب کوئی منظوری نہیں۔',

    'points.group.title': 'گروپ کے پوائنٹس',
    'points.group.said': 'گروپ کی ہر اس خدمت پر لاگو ہوتا ہے جو الگ سے مخصوص نہیں کی گئی۔',
    'points.group.ariaLabel': 'گروپ {group} کے پوائنٹس',

    'points.perService.title': 'ایک مخصوص خدمت کے پوائنٹس',
    'points.perService.said': 'اپنا نمبر جو گروپ اور عمومی سیٹنگ پر مقدم ہوتا ہے۔',
    'points.customSetting': 'مخصوص سیٹنگ',
    'points.serviceAriaLabel': '{name} کے پوائنٹس',
    'points.returnToGeneral': 'عمومی کی طرف واپس جائیں',
  },
  ha: {
    'points.percentValue': '{n}%',
    'points.type.service.label': 'Daga sabis na',
    'points.type.service.hint': 'Yana zaɓar abin da zai samu daga abin da kake bayarwa — sabis ko kaya',
    'points.type.item.label': 'Kyauta',
    'points.type.item.hint': 'Wani abu daga waje abin da kake bayarwa — suna ya isa',
    'points.type.discount.label': 'Rangwame',
    'points.type.discount.hint': 'Adadin da ake cirewa daga ziyara',

    'points.error.saveFailed': 'An kasa ajiyewa.',
    'points.error.discountAmount': 'Rubuta adadin rangwame a riyal — lamba da mafi yawan lambobi biyu bayan aya, kamar 2.30',
    'points.error.addFailed': 'An kasa ƙara lada.',
    'points.error.modeChangeFailed': 'An kasa canza hanyar ƙidayawa',

    'points.waiting': 'Ana karanta maki da ladodinka',

    'points.kpi.customers': 'Abokan ciniki masu tara maki',
    'points.kpi.redemptions': 'Musanya',
    'points.kpi.outstanding': 'Maki da ba a musanya ba tukuna',
    'points.kpi.outstanding.hint': 'Abin da ka yi alkawari kuma ba a kashe ba — hakki ne akan shagonka.',
    'points.kpi.expiredShare': 'Daga kowane makin da aka bayar, ya ƙare ba tare da musanya ba',
    'points.kpi.expiredShare.hint': 'Babban rabo yana nufin iyakokin ladanka sun wuce inda abokan cinikinka za su iya kaiwa.',

    'points.topRewards.title': 'Mafi yawan musanya',
    'points.noName': 'Ba tare da suna ba',

    'points.tabsAriaLabel': 'Sassan maki',
    'points.tab.rewards': 'Lada',
    'points.tab.earning': 'Samu',

    'points.table.title': 'Jerin lada',
    'points.table.said': 'Abin da abokin cinikinka ke musanya da makinsa — kuma ya zo cike da riga don sana’arka.',
    'points.addReward': 'Ƙara lada',

    'points.form.name.label': 'Sunan lada',
    'points.form.name.hint': 'Ana nuna shi a saƙon WhatsApp ga abokin ciniki — ka sanya shi gajere',
    'points.form.cost.label': 'Farashi a maki',
    'points.form.type.label': 'Nau’i',
    'points.form.riyals.label': 'Adadin rangwame a riyal',
    'points.form.service.label': 'Abin da yake samu',
    'points.form.service.hint': 'Daga abin da kake bayarwa — sabis ko kaya',
    'points.save': 'Ajiye',
    'points.cancel': 'Soke',

    'points.loadFailed.title': 'An kasa karanta jerin lada',
    'points.loadFailed.description': 'Ba mu iya samun sa yanzu ba, kuma laifi namu ne. Sake gwadawa nan da nan.',
    'points.empty.title': 'Babu lada tukuna',
    'points.empty.description': 'Ƙara ladarka ta farko: zaɓi sabis, da yawan ziyarar da take buƙata.',

    'points.costAriaLabel': 'Farashin {name} a maki',
    'points.pointUnit': 'maki',
    'points.stoppedBadge': 'An dakatar',
    'points.activate': 'Kunna',
    'points.deactivate': 'Dakatar — za ta ɓace daga jerin musanya',
    'points.deactivateShort': 'Dakatar',

    'points.settingsWaiting.title': 'Ana karanta saitunan maki',
    'points.settingsWaiting.description': 'Jira kaɗan.',
    'points.settingsFailed.title': 'An kasa karanta saitunan maki',
    'points.settingsFailed.description': 'Ba mu nuna su ba don kada ka canza lamba daga ainihinta — dokokin shagonka sun kasance kamar yadda suke. Sake gwadawa.',

    'points.mode.title': 'Hanyar ƙidayawa',
    'points.mode.said': 'Ta sabis: kowace sabis makinta na kanta. Ta darajar sigina: maki ɗaya kowace riyal.',
    'points.mode.ariaLabel': 'Hanyar ƙidayar maki',
    'points.mode.services': 'Ta sabis',
    'points.mode.invoice': 'Ta darajar sigina',
    'points.mode.needsPricedServices': 'Ƙidayawa ta darajar sigina tana buƙatar an sanya farashin kowace sabis tukuna — sanya farashin duka a «Ayyuka», sannan a kunna shi.',

    'points.general.label': 'Maki na kowace ziyara (na gama gari)',
    'points.general.hint': 'Kowace sabis da ba ta da lambar kanta tana ɗaukar wannan lambar.',

    'points.threshold.label': 'Lada na buƙatar amincewar manaja daga',
    'points.threshold.hint': 'Duk wata lada da ke da wannan maki ko fiye tana buƙatar sunan manaja lokacin musanya. 0 yana nufin babu amincewa.',

    'points.group.title': 'Makin rukuni',
    'points.group.said': 'Yana shafar kowace sabis a cikin rukuni da ba a keɓance ita kaɗai ba.',
    'points.group.ariaLabel': 'Makin rukuni {group}',

    'points.perService.title': 'Makin wata sabis ta musamman',
    'points.perService.said': 'Lambar kanta wadda ta fi rukuni da babban saitin muhimmanci.',
    'points.customSetting': 'Saiti na musamman',
    'points.serviceAriaLabel': 'Makin {name}',
    'points.returnToGeneral': 'Koma zuwa na gama gari',
  },
  fil: {
    'points.percentValue': '{n}%',
    'points.type.service.label': 'Mula sa mga serbisyo ko',
    'points.type.service.hint': 'Pipiliin niya kung ano ang makukuha niya mula sa inaalok mo — serbisyo man o produkto',
    'points.type.item.label': 'Regalo',
    'points.type.item.hint': 'Isang bagay na wala sa inaalok mo — sapat na ang pangalan',
    'points.type.discount.label': 'Diskuwento',
    'points.type.discount.hint': 'Halagang ibabawas sa visit',

    'points.error.saveFailed': 'Hindi na-save.',
    'points.error.discountAmount': 'Ilagay ang halaga ng diskuwento sa SAR — numero na may hanggang dalawang decimal place, tulad ng 2.30',
    'points.error.addFailed': 'Hindi naidagdag ang reward.',
    'points.error.modeChangeFailed': 'Hindi napalitan ang paraan ng pagkalkula',

    'points.waiting': 'Binabasa ang iyong mga puntos at reward',

    'points.kpi.customers': 'Kustomer na kumikita ng puntos',
    'points.kpi.redemptions': 'Redemption',
    'points.kpi.outstanding': 'Mga puntos na hindi pa na-redeem',
    'points.kpi.outstanding.hint': 'Ang ipinangako mo at hindi pa nagagastos — isang obligasyon sa shop mo.',
    'points.kpi.expiredShare': 'Sa bawat puntos na ibinigay, na-expire nang hindi na-redeem',
    'points.kpi.expiredShare.hint': 'Ang mataas na porsyento ay nangangahulugang lampas sa maaabot ng iyong mga kustomer ang mga threshold ng reward mo.',

    'points.topRewards.title': 'Pinaka-nire-redeem',
    'points.noName': 'Walang pangalan',

    'points.tabsAriaLabel': 'Mga seksyon ng puntos',
    'points.tab.rewards': 'Mga reward',
    'points.tab.earning': 'Pagkita',

    'points.table.title': 'Talahanayan ng reward',
    'points.table.said': 'Ang ini-redeem ng kustomer mo gamit ang kanyang puntos — at dumarating na naka-preload para sa negosyo mo.',
    'points.addReward': 'Magdagdag ng reward',

    'points.form.name.label': 'Pangalan ng reward',
    'points.form.name.hint': 'Ipinapakita sa mensahe sa WhatsApp para sa kustomer — panatilihing maikli',
    'points.form.cost.label': 'Halaga sa puntos',
    'points.form.type.label': 'Uri',
    'points.form.riyals.label': 'Halaga ng diskuwento sa SAR',
    'points.form.service.label': 'Ang makukuha niya',
    'points.form.service.hint': 'Mula sa inaalok mo — serbisyo man o produkto',
    'points.save': 'I-save',
    'points.cancel': 'Kanselahin',

    'points.loadFailed.title': 'Hindi mabasa ang talahanayan ng reward',
    'points.loadFailed.description': 'Hindi namin ito nakuha ngayon, at kasalanan namin ito. Subukan muli sa ilang sandali.',
    'points.empty.title': 'Wala pang reward',
    'points.empty.description': 'Idagdag ang unang reward mo: pumili ng serbisyo, at ilang visit ang kailangan para makuha ito.',

    'points.costAriaLabel': 'Halaga ng {name} sa puntos',
    'points.pointUnit': 'puntos',
    'points.stoppedBadge': 'Naitigil',
    'points.activate': 'I-activate',
    'points.deactivate': 'I-deactivate — mawawala sa listahan ng redemption',
    'points.deactivateShort': 'I-deactivate',

    'points.settingsWaiting.title': 'Binabasa ang mga setting ng puntos',
    'points.settingsWaiting.description': 'Sandali lang.',
    'points.settingsFailed.title': 'Hindi mabasa ang mga setting ng puntos',
    'points.settingsFailed.description': 'Hindi namin ito ipinakita para hindi mo baguhin ang isang numero mula sa tunay nitong halaga — nananatili ang mga patakaran ng shop mo. Subukan muli.',

    'points.mode.title': 'Paraan ng pagkalkula',
    'points.mode.said': 'Ayon sa serbisyo: bawat serbisyo may sariling puntos. Ayon sa halaga ng invoice: isang puntos kada riyal.',
    'points.mode.ariaLabel': 'Paraan ng pagkalkula ng puntos',
    'points.mode.services': 'Ayon sa serbisyo',
    'points.mode.invoice': 'Ayon sa halaga ng invoice',
    'points.mode.needsPricedServices': 'Ang pagkalkula ayon sa halaga ng invoice ay nangangailangan munang mapresyuhan ang bawat serbisyo — presyuhan lahat sa «Mga Serbisyo», pagkatapos i-on.',

    'points.general.label': 'Puntos kada visit (general)',
    'points.general.hint': 'Kukunin ng bawat serbisyong walang sariling numero ang numerong ito.',

    'points.threshold.label': 'Kailangan ng approval ng manager ang reward mula sa',
    'points.threshold.hint': 'Anumang reward na may ganitong puntos pataas ay nangangailangan ng pangalan ng manager sa redemption. 0 ay walang approval.',

    'points.group.title': 'Puntos ng grupo',
    'points.group.said': 'Nalalapat sa bawat serbisyo sa grupo na hindi pa na-customize nang mag-isa.',
    'points.group.ariaLabel': 'Puntos para sa grupong {group}',

    'points.perService.title': 'Puntos para sa isang partikular na serbisyo',
    'points.perService.said': 'Sariling numero na nauuna sa grupo at sa general setting.',
    'points.customSetting': 'Custom na setting',
    'points.serviceAriaLabel': 'Puntos ng {name}',
    'points.returnToGeneral': 'Bumalik sa general',
  },
});
