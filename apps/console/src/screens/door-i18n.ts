/**
 * Door.tsx's own strings — registered once at import time (see operator-i18n.tsx's own header
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
    'door.password.show': 'إظهار كلمة المرور',
    'door.password.hide': 'إخفاء كلمة المرور',

    'door.tab.signIn': 'تسجيل الدخول',
    'door.tab.signUp': 'تسجيل جديد',

    'door.otp.title': 'أكّد رقمك',
    'door.otp.sendFailed': 'تعذّر إرسال الرمز.',
    'door.otp.genericFailed': 'تعذّر إكمال الطلب. حاول مرة أخرى.',

    'door.field.phone': 'رقم الجوال',
    'door.field.password': 'كلمة المرور',

    'door.signIn.missingFields': 'أدخل رقم الجوال وكلمة المرور.',
    'door.signIn.failed': 'تعذّر تسجيل الدخول.',
    'door.signIn.title': 'أهلاً بك',
    'door.signIn.subtitle': 'رقم جوالك وكلمة المرور.',
    'door.signIn.busy': 'جارٍ الدخول…',
    'door.signIn.submit': 'تسجيل الدخول',

    'door.newShop.title': 'افتح محلك',
    'door.newShop.shopNameLabel': 'اسم المحل',
    'door.newShop.ownerNameLabel': 'اسمك (اختياري)',
    'door.newShop.nameIsPasswordError': 'هذا اسم محلّك كما يظهر لعملائك، ويبدو أنه كلمة مرورك — يُرجى كتابة اسم المحل.',
    'door.newShop.busy': 'جارٍ الإنشاء…',
    'door.newShop.submit': 'ابدأ',
    'door.newShop.createFailed': 'تعذّر إنشاء الحساب.',

    'door.terms.agreePrefix': 'أوافق على',
    'door.terms.termsLink': 'شروط الاستخدام',
    'door.terms.and': 'و',
    'door.terms.privacyLink': 'سياسة الخصوصية',

    'door.pwRule.minLength': '12 حرفاً على الأقل',
    'door.pwRule.upper': 'حرف كبير',
    'door.pwRule.digit': 'رقم',
    'door.pwRule.symbol': 'رمز',

    'door.error.phone': 'أدخل رقم جوال سعودي صحيح — مثل 0501234567',
    'door.error.password': 'كلمة المرور لا تحقق الشروط أدناه',
    'door.error.shopName': 'أدخل اسم المحل',
    'door.error.mustAgree': 'يُرجى الموافقة على الشروط وسياسة الخصوصية للمتابعة.',
  },
  en: {
    'door.password.show': 'Show password',
    'door.password.hide': 'Hide password',

    'door.tab.signIn': 'Sign in',
    'door.tab.signUp': 'Sign up',

    'door.otp.title': 'Confirm your number',
    'door.otp.sendFailed': "Couldn't send the code.",
    'door.otp.genericFailed': "Couldn't complete the request. Try again.",

    'door.field.phone': 'Phone number',
    'door.field.password': 'Password',

    'door.signIn.missingFields': 'Enter your phone number and password.',
    'door.signIn.failed': "Couldn't sign in.",
    'door.signIn.title': 'Welcome',
    'door.signIn.subtitle': 'Your phone number and password.',
    'door.signIn.busy': 'Signing in…',
    'door.signIn.submit': 'Sign in',

    'door.newShop.title': 'Open your shop',
    'door.newShop.shopNameLabel': 'Shop name',
    'door.newShop.ownerNameLabel': 'Your name (optional)',
    'door.newShop.nameIsPasswordError': 'This is your shop name as your customers see it, and it looks like your password — please enter the shop name.',
    'door.newShop.busy': 'Creating…',
    'door.newShop.submit': 'Start',
    'door.newShop.createFailed': "Couldn't create the account.",

    'door.terms.agreePrefix': 'I agree to the',
    'door.terms.termsLink': 'Terms of Use',
    'door.terms.and': 'and',
    'door.terms.privacyLink': 'Privacy Policy',

    'door.pwRule.minLength': 'At least 12 characters',
    'door.pwRule.upper': 'An uppercase letter',
    'door.pwRule.digit': 'A number',
    'door.pwRule.symbol': 'A symbol',

    'door.error.phone': 'Enter a valid Saudi mobile number — e.g. 0501234567',
    'door.error.password': "The password doesn't meet the requirements below",
    'door.error.shopName': 'Enter the shop name',
    'door.error.mustAgree': 'Please agree to the Terms and Privacy Policy to continue.',
  },
  ur: {
    'door.password.show': 'پاس ورڈ دکھائیں',
    'door.password.hide': 'پاس ورڈ چھپائیں',

    'door.tab.signIn': 'لاگ ان',
    'door.tab.signUp': 'نیا اکاؤنٹ',

    'door.otp.title': 'اپنا نمبر تصدیق کریں',
    'door.otp.sendFailed': 'کوڈ بھیجا نہیں جا سکا۔',
    'door.otp.genericFailed': 'درخواست مکمل نہیں ہو سکی۔ دوبارہ کوشش کریں۔',

    'door.field.phone': 'موبائل نمبر',
    'door.field.password': 'پاس ورڈ',

    'door.signIn.missingFields': 'اپنا موبائل نمبر اور پاس ورڈ درج کریں۔',
    'door.signIn.failed': 'لاگ ان نہیں ہو سکا۔',
    'door.signIn.title': 'خوش آمدید',
    'door.signIn.subtitle': 'آپ کا موبائل نمبر اور پاس ورڈ۔',
    'door.signIn.busy': 'لاگ ان ہو رہا ہے…',
    'door.signIn.submit': 'لاگ ان',

    'door.newShop.title': 'اپنی دکان کھولیں',
    'door.newShop.shopNameLabel': 'دکان کا نام',
    'door.newShop.ownerNameLabel': 'آپ کا نام (اختیاری)',
    'door.newShop.nameIsPasswordError': 'یہ آپ کی دکان کا نام ہے جو گاہک دیکھتے ہیں، اور یہ آپ کا پاس ورڈ لگتا ہے — براہ کرم دکان کا نام لکھیں۔',
    'door.newShop.busy': 'بنایا جا رہا ہے…',
    'door.newShop.submit': 'شروع کریں',
    'door.newShop.createFailed': 'اکاؤنٹ نہیں بن سکا۔',

    'door.terms.agreePrefix': 'میں اتفاق کرتا ہوں',
    'door.terms.termsLink': 'استعمال کی شرائط',
    'door.terms.and': 'اور',
    'door.terms.privacyLink': 'رازداری کی پالیسی',

    'door.pwRule.minLength': 'کم از کم 12 حروف',
    'door.pwRule.upper': 'ایک بڑا حرف',
    'door.pwRule.digit': 'ایک عدد',
    'door.pwRule.symbol': 'ایک علامت',

    'door.error.phone': 'درست سعودی موبائل نمبر درج کریں — مثلاً 0501234567',
    'door.error.password': 'پاس ورڈ نیچے دی گئی شرائط پوری نہیں کرتا',
    'door.error.shopName': 'دکان کا نام درج کریں',
    'door.error.mustAgree': 'جاری رکھنے کے لیے شرائط اور رازداری کی پالیسی سے اتفاق کریں۔',
  },
  ha: {
    'door.password.show': 'Nuna kalmar sirri',
    'door.password.hide': 'Ɓoye kalmar sirri',

    'door.tab.signIn': 'Shiga',
    'door.tab.signUp': 'Sabon rajista',

    'door.otp.title': 'Tabbatar da lambar wayarka',
    'door.otp.sendFailed': 'Ba a iya aika lambar ba.',
    'door.otp.genericFailed': 'Ba a iya kammala buƙatar ba. Sake gwadawa.',

    'door.field.phone': 'Lambar waya',
    'door.field.password': 'Kalmar sirri',

    'door.signIn.missingFields': 'Shigar da lambar wayarka da kalmar sirri.',
    'door.signIn.failed': 'Ba a iya shiga ba.',
    'door.signIn.title': 'Barka da zuwa',
    'door.signIn.subtitle': 'Lambar wayarka da kalmar sirri.',
    'door.signIn.busy': 'Ana shigarwa…',
    'door.signIn.submit': 'Shiga',

    'door.newShop.title': 'Buɗe shagonka',
    'door.newShop.shopNameLabel': 'Sunan shago',
    'door.newShop.ownerNameLabel': 'Sunanka (na son rai)',
    'door.newShop.nameIsPasswordError': "Wannan sunan shagonka ne kamar yadda abokan cinikinka suke gani, kuma yana kama da kalmar sirrinka — da fatan za a rubuta sunan shagon.",
    'door.newShop.busy': 'Ana ƙirƙira…',
    'door.newShop.submit': 'Fara',
    'door.newShop.createFailed': 'Ba a iya ƙirƙirar asusu ba.',

    'door.terms.agreePrefix': 'Na yarda da',
    'door.terms.termsLink': 'Sharuɗɗan Amfani',
    'door.terms.and': 'da',
    'door.terms.privacyLink': "Manufar Sirri",

    'door.pwRule.minLength': 'Aƙalla haruffa 12',
    'door.pwRule.upper': 'Babban baƙi',
    'door.pwRule.digit': 'Lamba',
    'door.pwRule.symbol': 'Alama',

    'door.error.phone': 'Shigar da ingantacciyar lambar wayar Saudiyya — misali 0501234567',
    'door.error.password': "Kalmar sirri ba ta cika sharuɗɗan da ke ƙasa ba",
    'door.error.shopName': 'Shigar da sunan shago',
    'door.error.mustAgree': "Da fatan za a yarda da Sharuɗɗa da Manufar Sirri domin ci gaba.",
  },
  fil: {
    'door.password.show': 'Ipakita ang password',
    'door.password.hide': 'Itago ang password',

    'door.tab.signIn': 'Mag-sign in',
    'door.tab.signUp': 'Mag-sign up',

    'door.otp.title': 'Kumpirmahin ang numero mo',
    'door.otp.sendFailed': "Hindi maipadala ang code.",
    'door.otp.genericFailed': "Hindi nakumpleto ang kahilingan. Subukan ulit.",

    'door.field.phone': 'Numero ng telepono',
    'door.field.password': 'Password',

    'door.signIn.missingFields': 'Ilagay ang numero ng telepono at password mo.',
    'door.signIn.failed': "Hindi naka-sign in.",
    'door.signIn.title': 'Maligayang pagdating',
    'door.signIn.subtitle': 'Ang numero ng telepono at password mo.',
    'door.signIn.busy': 'Nagsa-sign in…',
    'door.signIn.submit': 'Mag-sign in',

    'door.newShop.title': 'Buksan ang tindahan mo',
    'door.newShop.shopNameLabel': 'Pangalan ng tindahan',
    'door.newShop.ownerNameLabel': 'Pangalan mo (opsyonal)',
    'door.newShop.nameIsPasswordError': 'Ito ang pangalan ng tindahan mo na nakikita ng mga customer, at mukhang ito ang password mo — pakisulat ang pangalan ng tindahan.',
    'door.newShop.busy': 'Ginagawa…',
    'door.newShop.submit': 'Simulan',
    'door.newShop.createFailed': "Hindi magawa ang account.",

    'door.terms.agreePrefix': 'Sumasang-ayon ako sa',
    'door.terms.termsLink': 'Mga Tuntunin sa Paggamit',
    'door.terms.and': 'at',
    'door.terms.privacyLink': 'Patakaran sa Privacy',

    'door.pwRule.minLength': 'Hindi bababa sa 12 na karakter',
    'door.pwRule.upper': 'Isang malaking titik',
    'door.pwRule.digit': 'Isang numero',
    'door.pwRule.symbol': 'Isang simbolo',

    'door.error.phone': 'Maglagay ng wastong numero ng Saudi mobile — hal. 0501234567',
    'door.error.password': "Hindi natutugunan ng password ang mga kinakailangan sa ibaba",
    'door.error.shopName': 'Ilagay ang pangalan ng tindahan',
    'door.error.mustAgree': 'Pakisang-ayunan ang Mga Tuntunin at Patakaran sa Privacy para magpatuloy.',
  },
  bn: {
    'door.password.show': 'পাসওয়ার্ড দেখান',
    'door.password.hide': 'পাসওয়ার্ড লুকান',

    'door.tab.signIn': 'সাইন ইন',
    'door.tab.signUp': 'নতুন নিবন্ধন',

    'door.otp.title': 'আপনার নম্বর নিশ্চিত করুন',
    'door.otp.sendFailed': 'কোড পাঠানো যায়নি।',
    'door.otp.genericFailed': 'অনুরোধ সম্পন্ন করা যায়নি। আবার চেষ্টা করুন।',

    'door.field.phone': 'মোবাইল নম্বর',
    'door.field.password': 'পাসওয়ার্ড',

    'door.signIn.missingFields': 'আপনার মোবাইল নম্বর ও পাসওয়ার্ড লিখুন।',
    'door.signIn.failed': 'সাইন ইন করা যায়নি।',
    'door.signIn.title': 'স্বাগতম',
    'door.signIn.subtitle': 'আপনার মোবাইল নম্বর ও পাসওয়ার্ড।',
    'door.signIn.busy': 'সাইন ইন হচ্ছে…',
    'door.signIn.submit': 'সাইন ইন',

    'door.newShop.title': 'আপনার দোকান খুলুন',
    'door.newShop.shopNameLabel': 'দোকানের নাম',
    'door.newShop.ownerNameLabel': 'আপনার নাম (ঐচ্ছিক)',
    'door.newShop.nameIsPasswordError': 'এটি আপনার দোকানের নাম, যেভাবে আপনার গ্রাহকরা দেখে, এবং এটি আপনার পাসওয়ার্ডের মতো মনে হচ্ছে — দয়া করে দোকানের নাম লিখুন।',
    'door.newShop.busy': 'তৈরি হচ্ছে…',
    'door.newShop.submit': 'শুরু করুন',
    'door.newShop.createFailed': 'অ্যাকাউন্ট তৈরি করা যায়নি।',

    'door.terms.agreePrefix': 'আমি সম্মত',
    'door.terms.termsLink': 'ব্যবহারের শর্তাবলীতে',
    'door.terms.and': 'এবং',
    'door.terms.privacyLink': 'গোপনীয়তা নীতিতে',

    'door.pwRule.minLength': 'কমপক্ষে ১২টি অক্ষর',
    'door.pwRule.upper': 'একটি বড় হাতের অক্ষর',
    'door.pwRule.digit': 'একটি সংখ্যা',
    'door.pwRule.symbol': 'একটি চিহ্ন',

    'door.error.phone': 'একটি সঠিক সৌদি মোবাইল নম্বর লিখুন — যেমন 0501234567',
    'door.error.password': 'পাসওয়ার্ড নিচের শর্তগুলো পূরণ করে না',
    'door.error.shopName': 'দোকানের নাম লিখুন',
    'door.error.mustAgree': 'চালিয়ে যেতে শর্তাবলী ও গোপনীয়তা নীতিতে সম্মত হন।',
  },
});
