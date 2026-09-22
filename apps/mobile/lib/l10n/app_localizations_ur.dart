// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Urdu (`ur`).
class SUr extends S {
  SUr([String locale = 'ur']) : super(locale);

  @override
  String get appName => 'راجِع';

  @override
  String get ok => 'ٹھیک ہے';

  @override
  String get cancel => 'منسوخ کریں';

  @override
  String get save => 'محفوظ کریں';

  @override
  String get close => 'بند کریں';

  @override
  String get back => 'واپس';

  @override
  String get next => 'اگلا';

  @override
  String get done => 'مکمل';

  @override
  String get loading => 'لوڈ ہو رہا ہے...';

  @override
  String get retry => 'دوبارہ کوشش کریں';

  @override
  String get error => 'ایک خرابی پیش آگئی';

  @override
  String get success => 'کامیابی سے انجام دیا گیا';

  @override
  String get search => 'تلاش';

  @override
  String get login => 'لاگ ان';

  @override
  String get logout => 'لاگ آؤٹ';

  @override
  String get homeDashboardTitle => 'ڈیش بورڈ';

  @override
  String get homeShopSectionLabel => 'میری دکان';

  @override
  String get homeLoadErrorTitle => 'لوڈ نہیں ہو سکا';

  @override
  String get homeLoadErrorMessage =>
      'آج کا ڈیٹا لوڈ نہیں ہو سکا۔ دوبارہ کوشش کریں۔';

  @override
  String get homeTodaySectionTitle => 'آج';

  @override
  String get homeStatSent => 'بھیجے گئے';

  @override
  String get homeStatWaiting => 'انتظار میں';

  @override
  String get homeStatRetrying => 'دوبارہ کوشش';

  @override
  String get homeDashboardComputing =>
      'آپ کی دکان کے اعداد و شمار تیار ہو رہے ہیں — تھوڑی دیر بعد صفحہ ریفریش کریں۔';

  @override
  String get homeDashboardSectionTitle => 'دکان کے اعداد و شمار';

  @override
  String get homeDashboardEmpty => 'ابھی کافی ڈیٹا موجود نہیں۔';

  @override
  String get themeDarkMode => 'تاریک موڈ';

  @override
  String get themeLightMode => 'روشن موڈ';

  @override
  String get validatorFieldRequiredGeneric => 'یہ خانہ درکار ہے';

  @override
  String validatorFieldRequiredNamed(String field) {
    return '$field درکار ہے';
  }

  @override
  String get validatorEmailRequired => 'ای میل درکار ہے';

  @override
  String get validatorEmailInvalid => 'ای میل درست نہیں ہے';

  @override
  String get validatorPhoneRequired => 'فون نمبر درکار ہے';

  @override
  String get validatorPhoneInvalid =>
      'فون نمبر درست نہیں — یہ 05 سے شروع ہونا چاہیے';

  @override
  String get validatorPasswordRequired => 'پاس ورڈ درکار ہے';

  @override
  String get validatorPasswordTooShort =>
      'پاس ورڈ کم از کم 8 حروف کا ہونا چاہیے';

  @override
  String get validatorPasswordNeedsUppercase =>
      'پاس ورڈ میں ایک بڑا حرف ہونا چاہیے';

  @override
  String get validatorPasswordNeedsLowercase =>
      'پاس ورڈ میں ایک چھوٹا حرف ہونا چاہیے';

  @override
  String get validatorPasswordNeedsDigit => 'پاس ورڈ میں ایک ہندسہ ہونا چاہیے';

  @override
  String get validatorConfirmPasswordFieldName => 'پاس ورڈ کی تصدیق';

  @override
  String get validatorPasswordMismatch => 'پاس ورڈ مماثل نہیں ہیں';

  @override
  String get validatorOtpRequired => 'تصدیقی کوڈ درکار ہے';

  @override
  String get validatorOtpLength => 'تصدیقی کوڈ 6 ہندسوں کا ہونا چاہیے';

  @override
  String get validatorOtpDigitsOnly => 'تصدیقی کوڈ میں صرف ہندسے ہونے چاہئیں';

  @override
  String get validatorNameRequired => 'نام درکار ہے';

  @override
  String get validatorNameTooShort => 'نام کم از کم 2 حروف کا ہونا چاہیے';

  @override
  String get validatorNameTooLong => 'نام 100 حروف سے زیادہ نہیں ہونا چاہیے';

  @override
  String get validatorNameInvalidChars => 'نام میں غیر مجاز حروف شامل ہیں';

  @override
  String get validatorGenericFieldName => 'یہ خانہ';

  @override
  String validatorMinLengthNamed(String field, int minLength) {
    return '$field کم از کم $minLength حروف کا ہونا چاہیے';
  }

  @override
  String validatorMaxLengthNamed(String field, int maxLength) {
    return '$field $maxLength حروف سے زیادہ نہیں ہونا چاہیے';
  }

  @override
  String get validatorGenericValueName => 'قدر';

  @override
  String validatorNotANumberNamed(String field) {
    return '$field ایک عدد ہونا چاہیے';
  }

  @override
  String validatorMinValueNamed(String field, String min) {
    return '$field کم از کم $min ہونا چاہیے';
  }

  @override
  String validatorMaxValueNamed(String field, String max) {
    return '$field $max سے زیادہ نہیں ہونا چاہیے';
  }

  @override
  String get validatorUrlRequired => 'لنک درکار ہے';

  @override
  String get validatorUrlInvalid => 'لنک درست نہیں ہے';

  @override
  String get urlHelperUnavailable => 'لنک دستیاب نہیں ہے';

  @override
  String get urlHelperOpenFailed => 'لنک کھولنا ممکن نہیں ہوا';

  @override
  String get routerScreenNotOnMobileYet =>
      'یہ اسکرین ابھی موبائل ایپ پر دستیاب نہیں ہے۔';

  @override
  String get kbHintNoEntry => 'ابھی اس کی کوئی وضاحت موجود نہیں ہے۔';

  @override
  String get assistantChatTitle => 'معاون';

  @override
  String get assistantInputHint => 'اپنا سوال لکھیں...';

  @override
  String get assistantSend => 'بھیجیں';

  @override
  String get assistantUnavailable => 'معاون ابھی دستیاب نہیں ہے۔';

  @override
  String get assistantPreparing => 'معاون تیار کیا جا رہا ہے...';

  @override
  String get assistantSpeak => 'جواب سنیں';

  @override
  String get assistantStopSpeaking => 'آواز روکیں';

  @override
  String get assistantActionUnavailable => 'آپ ابھی یہ نہیں کر سکتے۔';

  @override
  String get assistantConfirm => 'تصدیق کریں';

  @override
  String get assistantCancel => 'منسوخ کریں';

  @override
  String get authLoginSubtitle => 'جاری رکھنے کے لیے سائن ان کریں';

  @override
  String get authPhoneLabel => 'موبائل نمبر';

  @override
  String get authPasswordLabel => 'پاس ورڈ';

  @override
  String get authNoShopYetLabel => 'ابھی تک آپ کی دکان نہیں ہے؟';

  @override
  String get authOpenNewShopCta => 'نئی دکان کھولیں';

  @override
  String get authOpenShopTitle => 'نئی دکان کھولیں';

  @override
  String get authSignupSubtitle => 'آپ کی دکان کھولنے کے لیے صرف تین مراحل';

  @override
  String get authShopNameLabel => 'دکان کا نام';

  @override
  String get authOwnerNameLabel => 'آپ کا نام (اختیاری)';

  @override
  String get authAlreadyHaveShopCta => 'پہلے سے دکان ہے؟ سائن ان کریں';

  @override
  String get authOpenShopCta => 'دکان کھولیں';

  @override
  String get authVerifyPhoneTitle => 'موبائل نمبر کی تصدیق';

  @override
  String authVerifyCodeSentTo(String phone) {
    return 'ہم نے $phone پر ایک تصدیقی کوڈ بھیجا ہے';
  }

  @override
  String get authVerifying => 'تصدیق ہو رہی ہے...';

  @override
  String get authConfirmCta => 'تصدیق کریں';

  @override
  String get authResendCodeCta => 'کوڈ دوبارہ بھیجیں';

  @override
  String get authSendCodeCta => 'کوڈ بھیجیں';

  @override
  String get authCodeSendFailedFallback => 'کوڈ بھیجنا ممکن نہیں ہوا۔';

  @override
  String get authOtpIncorrectFallback => 'تصدیقی کوڈ غلط ہے۔';

  @override
  String get visitCatalogueLoadErrorFallback =>
      'سروسز لوڈ نہیں ہو سکیں۔ دوبارہ کوشش کے لیے نیچے کھینچیں۔';

  @override
  String get visitEnterCustomerPhone => 'گاہک کا موبائل نمبر درج کریں';

  @override
  String get visitSelectAtLeastOneService => 'کم از کم ایک سروس منتخب کریں';

  @override
  String get visitSavedMessage => 'وزٹ ریکارڈ ہو گئی ہے۔';

  @override
  String get visitSaveErrorFallback => 'وزٹ ریکارڈ نہیں ہو سکی۔';

  @override
  String get visitSaveErrorNetworkFallback =>
      'وزٹ ریکارڈ نہیں ہو سکی۔ اپنا کنکشن چیک کریں اور دوبارہ کوشش کریں۔';

  @override
  String get visitTitle => 'وزٹ ریکارڈ کریں';

  @override
  String get visitCustomerSectionTitle => 'گاہک';

  @override
  String get visitCustomerPhoneFieldLabel => 'گاہک کا موبائل نمبر';

  @override
  String get visitPlateFieldLabel => 'پلیٹ نمبر';

  @override
  String get visitPlateRequired =>
      'درست پلیٹ درج کریں (کم از کم ایک حرف اور ایک ہندسہ)';

  @override
  String visitKnownVehicle(String name) {
    return 'معروف گاڑی: $name';
  }

  @override
  String get visitNewVehicle => 'نئی گاڑی';

  @override
  String visitKnownCustomer(String name) {
    return 'معروف گاہک: $name';
  }

  @override
  String get visitNewCustomer => 'نیا گاہک';

  @override
  String get visitServicesSectionTitle => 'سروسز';

  @override
  String get visitNoServicesYet => 'ابھی تک کوئی سروس نہیں ہے۔';

  @override
  String get visitNoteSectionTitle => 'نوٹ (اختیاری)';

  @override
  String get visitSaveButtonLabel => 'وزٹ محفوظ کریں';

  @override
  String get navAppsLabel => 'میری ایپس';

  @override
  String get navHomeLabel => 'ہوم';

  @override
  String get navAccountLabel => 'میرا اکاؤنٹ';

  @override
  String get homeGreetingMorning => 'صبح بخیر';

  @override
  String get homeGreetingEvening => 'شام بخیر';

  @override
  String homeGreetingMorningNamed(String name) {
    return 'صبح بخیر، $name';
  }

  @override
  String homeGreetingEveningNamed(String name) {
    return 'شام بخیر، $name';
  }

  @override
  String get homeAppsSectionTitle => 'آپ کی ایپس';

  @override
  String get homeFeaturedStartNow => 'ابھی شروع کریں';

  @override
  String get homeEmptyStateTitle => 'ابھی کوئی ایپ دستیاب نہیں';

  @override
  String get homeEmptyStateBody =>
      'اپنی اجازتیں شامل کروانے کے لیے دکان کے مالک سے رابطہ کریں۔';

  @override
  String get appsScreenTitle => 'میری ایپس';

  @override
  String get appsScreenHint =>
      'نیچے کی پٹی کی 5ویں جگہ پر ایپ لگانے کے لیے پن آئیکن دبائیں';

  @override
  String get appsPinnedBadge => 'پٹی پر لگا ہوا';

  @override
  String get appsPinAction => 'یہاں لگائیں';

  @override
  String get homeLauncherEmptyTitle => 'کوئی ایپ دستیاب نہیں';

  @override
  String get homeLauncherEmptyMessage =>
      'اپنی دکان کے لیے ایپ فعال کروانے کے لیے سپورٹ سے رابطہ کریں';

  @override
  String get accountScreenTitle => 'میرا اکاؤنٹ';

  @override
  String get accountPhoneLabel => 'موبائل نمبر';

  @override
  String get accountLogoutAction => 'لاگ آؤٹ';

  @override
  String get accountLogoutConfirmTitle => 'لاگ آؤٹ';

  @override
  String get accountLogoutConfirmMessage =>
      'کیا آپ اپنے اکاؤنٹ سے لاگ آؤٹ کرنا چاہتے ہیں؟';

  @override
  String get notificationsUnavailable => 'اطلاعات ابھی دستیاب نہیں';

  @override
  String get notificationsTitle => 'اطلاعات';

  @override
  String get notificationsEmptyState => 'ابھی کوئی اطلاع نہیں';

  @override
  String get notificationsAgoJustNow => 'ابھی';

  @override
  String notificationsAgoMinutes(int n) {
    return '$n منٹ پہلے';
  }

  @override
  String notificationsAgoHours(int n) {
    return '$n گھنٹے پہلے';
  }

  @override
  String get notificationsAgoYesterday => 'کل';

  @override
  String notificationsAgoDays(int n) {
    return '$n دن پہلے';
  }

  @override
  String get accountPageTitle => 'میرا اکاؤنٹ';

  @override
  String get accountLegalSectionTitle => 'قانونی';

  @override
  String get accountTermsRow => 'شرائط و ضوابط';

  @override
  String get accountPrivacyRow => 'پرائیویسی پالیسی';

  @override
  String get accountSignOutRow => 'سائن آؤٹ';

  @override
  String get accountSignOutConfirmTitle => 'سائن آؤٹ کریں؟';

  @override
  String get accountSignOutConfirmBody =>
      'جاری رکھنے کے لیے آپ کو دوبارہ سائن ان کرنا ہوگا۔';

  @override
  String get accountSignOutCancel => 'منسوخ کریں';

  @override
  String get accountSignOutConfirm => 'سائن آؤٹ';

  @override
  String get accountNameFieldHint => 'آپ کا نام';

  @override
  String get accountSaveNameFailed =>
      'نام محفوظ نہیں ہو سکا، دوبارہ کوشش کریں۔';

  @override
  String get accountShopSectionTitle => 'میری دکان';

  @override
  String get accountShopIdentityRow => 'میری دکان';

  @override
  String get shopIdentityPageTitle => 'میری دکان';

  @override
  String get shopIdentityVehicleTitle => 'گاڑیوں پر کام';

  @override
  String get shopIdentityVehicleDesc =>
      'اس دکان کے لیے وزٹ اسکرین پر لائسنس پلیٹ فیلڈ فعال کرتا ہے۔';

  @override
  String get shopIdentityVehicleSaveFailed =>
      'محفوظ نہیں ہو سکا، دوبارہ کوشش کریں۔';

  @override
  String get shopIdentityBrandTitle => 'آپ کی دکان کا نام اور لوگو';

  @override
  String get shopIdentityCustomerPagePreview => 'یہ آپ کے گاہک کو نظر آتا ہے';

  @override
  String get shopIdentityNameLabel => 'دکان کا نام';

  @override
  String get shopIdentityUploadLogo => 'لوگو اپ لوڈ کریں';

  @override
  String get shopIdentityChangeLogo => 'لوگو تبدیل کریں';

  @override
  String get shopIdentityRemoveLogo => 'ہٹائیں';

  @override
  String get shopIdentityColorLabel => 'آپ کی دکان کا رنگ';

  @override
  String get shopIdentityResetColor => 'ڈیفالٹ استعمال کریں';

  @override
  String get shopIdentitySave => 'محفوظ کریں';

  @override
  String get shopIdentityDefaultName => 'آپ کی دکان';

  @override
  String get shopIdentityLogoPickFailed =>
      'تصویر پڑھی نہیں جا سکی، دوسری تصویر آزمائیں۔';

  @override
  String get shopIdentityInvalidColor => 'ایک درست رنگ درج کریں، جیسے #B08A3E';

  @override
  String get shopIdentitySaveFailed => 'محفوظ نہیں ہو سکا، دوبارہ کوشش کریں۔';

  @override
  String get shopIdentitySaved => 'محفوظ ہو گیا۔';

  @override
  String get shopIdentityBranchesRow => 'شاخیں';

  @override
  String get branchesPageTitle => 'شاخیں';

  @override
  String get branchesAddBranch => 'شاخ شامل کریں';

  @override
  String get branchesActiveChip => 'فعال';

  @override
  String get branchesClosedChip => 'بند';

  @override
  String get branchesLoadFailed =>
      'شاخیں لوڈ نہیں ہو سکیں، دوبارہ کوشش کے لیے نیچے کھینچیں۔';

  @override
  String get branchesLimitReached =>
      'آپ کا موجودہ پلان مزید شاخ کی اجازت نہیں دیتا۔';

  @override
  String get branchesNameRequired => 'شاخ کا نام ضروری ہے';

  @override
  String get branchesNameLabel => 'شاخ کا نام';

  @override
  String get branchesCityLabel => 'شہر';

  @override
  String get branchesLocationHint =>
      'گوگل میپس کا لنک پیسٹ کریں (پہلی شاخ پر اختیاری، دوسری سے لازمی)';

  @override
  String get branchesMapsLinkLabel => 'گوگل میپس لنک';

  @override
  String get branchesMapsLinkInvalid =>
      'لنک پڑھا نہیں جا سکا — یقینی بنائیں کہ یہ گوگل میپس کا لنک ہے۔';

  @override
  String get branchesMapsLinkShort =>
      'مکمل گوگل میپس لنک پیسٹ کریں، مختصر لنک نہیں۔';

  @override
  String get branchesLocationRequired =>
      'نقشے پر شاخ کا مقام مقرر کریں — دوسری شاخ سے لازمی ہے۔';

  @override
  String get branchesSaveFailed => 'محفوظ نہیں ہو سکا، دوبارہ کوشش کریں۔';

  @override
  String get branchesStatusLabel => 'شاخ کی حالت';

  @override
  String get branchesMainCannotClose =>
      'مرکزی شاخ بند نہیں ہو سکتی — صرف نام تبدیل کر سکتے ہیں۔';

  @override
  String get branchesWhatsappTitle => 'واٹس ایپ کنکشن';

  @override
  String get branchesWhatsappNotStarted => 'ابھی تک منسلک نہیں';

  @override
  String get branchesWhatsappConnected => 'منسلک اور کام کر رہا ہے';

  @override
  String get branchesWhatsappCannotSend => 'منسلک ہے لیکن بھیجنے میں مسئلہ ہے';

  @override
  String get branchesTeamTitle => 'شاخ کی ٹیم';

  @override
  String get branchesTeamEmpty => 'اس شاخ میں ابھی کوئی رکن نہیں۔';

  @override
  String get branchesAddMember => 'رکن شامل کریں';

  @override
  String get branchesMemberNameLabel => 'ملازم کا نام';

  @override
  String get branchesMemberPhoneLabel => 'اس کا فون نمبر';

  @override
  String get branchesMemberPasswordLabel => 'اس کا لاگ ان پاس ورڈ';

  @override
  String get branchesMemberRoleLabel => 'کردار';

  @override
  String get branchesRoleOperator => 'فیلڈ آپریٹر';

  @override
  String get branchesRoleSupervisor => 'شفٹ سپروائزر';

  @override
  String get branchesRoleManager => 'مینیجر';

  @override
  String get branchesSeatLimit =>
      'آپ کا موجودہ پلان مزید ملازم کی اجازت نہیں دیتا۔';

  @override
  String get branchesHireFailed => 'ملازم شامل نہیں ہو سکا، دوبارہ کوشش کریں۔';

  @override
  String get accountSecuritySectionTitle => 'سیکیورٹی';

  @override
  String get accountChangePasswordRow => 'پاس ورڈ تبدیل کریں';

  @override
  String get accountChangePasswordFailed =>
      'پاس ورڈ تبدیل نہیں ہو سکا، دوبارہ کوشش کریں۔';

  @override
  String get accountChangePasswordSuccess => 'پاس ورڈ تبدیل ہو گیا۔';

  @override
  String get accountCurrentPasswordLabel => 'موجودہ پاس ورڈ';

  @override
  String get accountNewPasswordLabel => 'نیا پاس ورڈ';

  @override
  String get accountConfirmNewPasswordLabel => 'نئے پاس ورڈ کی تصدیق';

  @override
  String get branchesIncreaseCapacity => 'گنجائش بڑھائیں';

  @override
  String get accountBillingSectionTitle => 'بلنگ';

  @override
  String get accountBillingRow => 'سبسکرپشن اور انوائسز';

  @override
  String get billingPageTitle => 'بلنگ';

  @override
  String get billingLoadFailed =>
      'بلنگ ڈیٹا لوڈ نہیں ہو سکا۔ دوبارہ کوشش کے لیے نیچے کھینچیں۔';

  @override
  String get billingAllGood =>
      'آپ کی بلنگ ٹھیک ہے، فی الحال کسی توجہ کی ضرورت نہیں۔';

  @override
  String get billingPastDue =>
      'آپ کا ایک بل واجب الادا ہے — اپنی سروسز رکنے سے بچنے کے لیے ادا کریں۔';

  @override
  String get billingUsageSectionTitle => 'آپ کا استعمال';

  @override
  String get billingUsageStaffSeats => 'اسٹاف سیٹیں';

  @override
  String get billingUsageBranches => 'شاخیں';

  @override
  String get billingUsageUnlimited => 'لامحدود';

  @override
  String get billingMyAppsSectionTitle => 'میری سبسکرائب کردہ ایپس';

  @override
  String get billingStatusActive => 'فعال';

  @override
  String get billingStatusStopping => 'بند ہو رہا ہے';

  @override
  String billingRenewsOn(Object date) {
    return '$date کو تجدید ہوگی';
  }

  @override
  String get billingStopRenewal => 'تجدید روکیں';

  @override
  String get billingUndoStopRenewal => 'روکنا واپس لیں';

  @override
  String get billingRenewNow => 'ابھی تجدید کریں';

  @override
  String get billingActionFailed =>
      'یہ کارروائی مکمل نہیں ہو سکی۔ دوبارہ کوشش کریں۔';

  @override
  String get billingRenewalPreviewSectionTitle => 'اگلی تجدید کا جائزہ';

  @override
  String billingRenewalPreviewNextChargeOn(Object date) {
    return 'اگلا چارج $date کو';
  }

  @override
  String get billingRenewalPreviewNoDate =>
      'ابھی تک کوئی آنے والی تجدید کی تاریخ نہیں۔';

  @override
  String get billingRenewalPreviewSubtotal => 'ذیلی مجموعہ';

  @override
  String get billingRenewalPreviewSavings => 'بچت';

  @override
  String get billingRenewalPreviewTax => 'ٹیکس';

  @override
  String get billingRenewalPreviewTotal => 'کل';

  @override
  String get billingInvoicesSectionTitle => 'انوائسز';

  @override
  String get billingInvoicesEmpty => 'ابھی تک کوئی انوائس نہیں۔';

  @override
  String get billingInvoiceStatusPaid => 'ادا شدہ';

  @override
  String get billingInvoiceStatusOpen => 'غیر ادا شدہ';

  @override
  String get billingInvoiceStatusPartiallyPaid => 'جزوی طور پر ادا شدہ';

  @override
  String get billingInvoiceStatusVoid => 'منسوخ';

  @override
  String get billingInvoiceStatusUncollectible => 'ناقابل وصول';

  @override
  String get billingInvoiceStatusDraft => 'ڈرافٹ';

  @override
  String get billingPayNow => 'ابھی ادا کریں';

  @override
  String get billingPayLinkFailed =>
      'ادائیگی کا لنک نہیں بن سکا۔ دوبارہ کوشش کریں۔';

  @override
  String get billingCancelConfirmTitle => 'تجدید روکیں؟';

  @override
  String get billingCancelConfirmBody =>
      'سروس موجودہ مدت کے اختتام تک کام کرتی رہے گی، پھر تجدید نہیں ہوگی۔';

  @override
  String get billingCancelConfirmAction => 'تجدید روکیں';

  @override
  String get visitOfferApplyLabel => 'یہ آفر اس وزٹ پر لاگو کریں';

  @override
  String visitPointsRedeemCost(Object cost) {
    return '$cost پوائنٹس';
  }

  @override
  String visitPointsRedeemedMessage(Object name) {
    return '$name کیش ہو گیا ✓';
  }

  @override
  String get visitPointsRedeemFailed => 'کیش نہیں ہو سکا۔ دوبارہ کوشش کریں۔';

  @override
  String readBillingActiveCount(Object count) {
    return 'آپ کے پاس $count فعال سبسکرپشن ہیں۔';
  }

  @override
  String get readBillingNone =>
      'آپ کے پاس فی الحال کوئی فعال سبسکرپشن نہیں ہے۔';

  @override
  String readBillingRenewsSoon(Object date) {
    return 'اگلی تجدید $date کو ہے۔';
  }

  @override
  String get readBillingFailed =>
      'بلنگ کی صورتحال ابھی حاصل نہیں ہو سکی، دوبارہ کوشش کریں۔';

  @override
  String readBranchCount(Object count) {
    return 'آپ کی $count شاخیں ہیں۔';
  }

  @override
  String get readBranchFailed =>
      'شاخوں کی تعداد ابھی حاصل نہیں ہو سکی، دوبارہ کوشش کریں۔';

  @override
  String get readVehicleTrackingOn => 'گاڑیوں کی ٹریکنگ ابھی فعال ہے۔';

  @override
  String get readVehicleTrackingOff => 'گاڑیوں کی ٹریکنگ ابھی غیر فعال ہے۔';

  @override
  String get readVehicleTrackingFailed =>
      'گاڑیوں کی ٹریکنگ کی صورتحال ابھی معلوم نہیں ہو سکی، دوبارہ کوشش کریں۔';

  @override
  String get writeVehicleTrackingEnabledConfirm =>
      'اس دکان کی وزٹ رجسٹریشن اسکرین پر پلیٹ نمبر کا خانہ فعال کرے گا۔ تصدیق کریں؟';

  @override
  String get writeVehicleTrackingDisabledConfirm =>
      'اس دکان کی وزٹ رجسٹریشن اسکرین پر پلیٹ نمبر کا خانہ غیر فعال کرے گا۔ تصدیق کریں؟';

  @override
  String get writeVehicleTrackingEnabledDone =>
      'گاڑیوں کی ٹریکنگ فعال کر دی گئی ✓';

  @override
  String get writeVehicleTrackingDisabledDone =>
      'گاڑیوں کی ٹریکنگ بند کر دی گئی ✓';

  @override
  String get writeVehicleTrackingFailed =>
      'گاڑیوں کی ٹریکنگ کی ترتیب تبدیل نہیں ہو سکی، دوبارہ کوشش کریں۔';
}
