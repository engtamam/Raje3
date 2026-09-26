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
  String get assistantReplySettingsTooltip => 'جواب کی ترتیبات';

  @override
  String get assistantReplyModeTitle => 'معاون کیسے جواب دے';

  @override
  String get assistantReplyModeSubtitle =>
      'ہر جواب پر لاگو ہوتا ہے، چاہے آپ نے آواز سے پوچھا ہو';

  @override
  String get assistantReplyModeVoice => 'آواز';

  @override
  String get assistantReplyModeText => 'تحریری متن';

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
  String get branchesRoleMarketer => 'مارکیٹنگ انچارج';

  @override
  String get branchesRoleManager => 'مینیجر';

  @override
  String get branchesSeatLimit =>
      'آپ کا موجودہ پلان مزید ملازم کی اجازت نہیں دیتا۔';

  @override
  String get branchesHireFailed => 'ملازم شامل نہیں ہو سکا، دوبارہ کوشش کریں۔';

  @override
  String get branchesVisibleAllHint => 'تمام شاخیں دیکھتا ہے';

  @override
  String branchesVisibleSomeHint(int count) {
    return '$count شاخیں دیکھتا ہے';
  }

  @override
  String get branchesEditMember => 'ملازم میں ترمیم';

  @override
  String get branchesMemberStopped => 'روکا گیا';

  @override
  String get branchesMemberStationLabel => 'کس شاخ میں کام کرتا ہے';

  @override
  String get branchesMemberVisibilityLabel => 'کون سی شاخیں دیکھ سکتا ہے';

  @override
  String get branchesVisibilityOwnOnly => 'صرف اپنی شاخ';

  @override
  String get branchesVisibilitySome => 'مخصوص شاخیں';

  @override
  String get branchesVisibilityAll => 'تمام شاخیں';

  @override
  String get branchesWorkingHours => 'اوقات کار';

  @override
  String get branchesStopMember => 'ملازم روکیں';

  @override
  String get branchesStopMemberTitle => 'اس ملازم کو روکیں؟';

  @override
  String branchesStopMemberBody(String name) {
    return '$name فوراً ایپ تک رسائی کھو دے گا۔ اس کی وزٹ کی تاریخ محفوظ رہے گی۔';
  }

  @override
  String get branchesStopMemberConfirm => 'روکیں';

  @override
  String get branchesReactivateMember => 'دوبارہ فعال کریں';

  @override
  String get branchesRehireRequired =>
      'یہ ملازم مکمل طور پر روکا گیا ہے — دوبارہ فعال کرنے کے لیے دوبارہ ملازمت دینا ضروری ہے، صرف آن کرنا کافی نہیں۔';

  @override
  String get branchesHoursSaved => 'اوقات کار محفوظ ہو گئے۔';

  @override
  String get branchesHoursExceedsShop =>
      'یہ اوقات دکان کے اپنے اوقات سے زیادہ ہیں — درست کریں۔';

  @override
  String get branchesHoursHint =>
      'اگر آپ کچھ نہیں بدلیں گے، تو وہ خودکار طور پر دکان کے اپنے اوقات کی پیروی کرے گا۔';

  @override
  String get branchesHoursClear => 'دکان کے ڈیفالٹ اوقات پر واپس کریں';

  @override
  String get branchesDayMonday => 'پیر';

  @override
  String get branchesDayTuesday => 'منگل';

  @override
  String get branchesDayWednesday => 'بدھ';

  @override
  String get branchesDayThursday => 'جمعرات';

  @override
  String get branchesDayFriday => 'جمعہ';

  @override
  String get branchesDaySaturday => 'ہفتہ';

  @override
  String get branchesDaySunday => 'اتوار';

  @override
  String get branchesDayClosed => 'بند';

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
  String get billingPaymentConfirming =>
      'ہمیں آپ کی ادائیگی کی کوشش موصول ہو گئی ہے اور ہم اس کی تصدیق کر رہے ہیں — اس میں 20 منٹ تک لگ سکتے ہیں۔';

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
  String get paymentPageLoadFailed =>
      'ادائیگی کا صفحہ لوڈ نہیں ہو سکا۔ اپنا کنکشن چیک کریں اور دوبارہ کوشش کریں۔';

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

  @override
  String get mobileRequestsTitle => 'موبائل درخواستیں';

  @override
  String get mobileRequestsSubtitle =>
      'ایسی درخواستیں جو خدمت کو گاہک تک پہنچاتی ہیں، وصولی سے تکمیل تک۔';

  @override
  String get mobileRequestsKpiPending => 'فیصلے کا منتظر';

  @override
  String get mobileRequestsKpiNeedsDecision => 'فیصلہ درکار';

  @override
  String get mobileRequestsKpiCompletedMonth => 'اس ماہ مکمل ہوئیں';

  @override
  String get mobileRequestsBannerGo => 'دیکھیں';

  @override
  String get mobileRequestsFilterAll => 'تمام';

  @override
  String get mobileRequestsFilterPending => 'زیر التوا';

  @override
  String get mobileRequestsFilterAccepted => 'قبول شدہ';

  @override
  String get mobileRequestsFilterNeedsDecision => 'فیصلہ درکار';

  @override
  String get mobileRequestsFilterCompleted => 'مکمل';

  @override
  String get mobileRequestsFilterClosed => 'بند';

  @override
  String get mobileRequestsSearchHint => 'نام یا فون سے تلاش کریں';

  @override
  String get mobileRequestsLoadFailedTitle => 'درخواستیں لوڈ نہیں ہو سکیں';

  @override
  String get mobileRequestsLoadFailedBody =>
      'اپنا کنکشن چیک کریں اور دوبارہ کوشش کریں۔';

  @override
  String get mobileRequestsRetry => 'دوبارہ کوشش کریں';

  @override
  String get mobileRequestsEmptyTitle => 'ابھی تک کوئی درخواست نہیں';

  @override
  String get mobileRequestsEmptyBody =>
      'آپ کے گاہکوں کی موبائل سروس کی درخواستیں یہاں ظاہر ہوں گی۔';

  @override
  String get mobileRequestsStatusPending => 'زیر التوا';

  @override
  String get mobileRequestsStatusAccepted => 'قبول شدہ';

  @override
  String get mobileRequestsStatusNeedsDecision => 'فیصلہ درکار';

  @override
  String get mobileRequestsStatusCompleted => 'مکمل';

  @override
  String get mobileRequestsStatusNoShow => 'حاضر نہیں ہوا';

  @override
  String get mobileRequestsStatusRejected => 'مسترد';

  @override
  String get mobileRequestsUnnamed => 'بلا نام';

  @override
  String get mobileRequestsOpenMap => 'مقام';

  @override
  String get mobileRequestsPhoneCopied => 'فون نمبر کاپی ہو گیا';

  @override
  String get mobileRequestsRiskyCustomer => 'زیادہ رسک والا گاہک';

  @override
  String mobileRequestsRejectReasonLine(Object reason) {
    return 'مسترد کرنے کی وجہ: $reason';
  }

  @override
  String get mobileRequestsActionAccept => 'قبول کریں';

  @override
  String get mobileRequestsActionReject => 'مسترد کریں';

  @override
  String get mobileRequestsActionComplete => 'مکمل';

  @override
  String get mobileRequestsActionNoShow => 'حاضر نہیں ہوا';

  @override
  String get mobileRequestsAssignUnassigned => 'غیر تفویض شدہ';

  @override
  String get mobileRequestsActionFailed =>
      'کارروائی مکمل نہیں ہو سکی، دوبارہ کوشش کریں۔';

  @override
  String get mobileRequestsRejectTitle => 'مسترد کرنے کی وجہ';

  @override
  String get mobileRequestsRejectHint => 'اختیاری';

  @override
  String get mobileRequestsRejectCancel => 'منسوخ کریں';

  @override
  String get mobileRequestsRejectConfirm => 'درخواست مسترد کریں';

  @override
  String get mobileRequestsAddOpen => 'درخواست شامل کریں';

  @override
  String get mobileRequestsAddTitle => 'موبائل سروس کی درخواست شامل کریں';

  @override
  String get mobileRequestsAddPhoneLabel => 'گاہک کا فون';

  @override
  String get mobileRequestsAddNameLabel => 'گاہک کا نام (اختیاری)';

  @override
  String get mobileRequestsAddServicesLabel => 'خدمات';

  @override
  String get mobileRequestsAddServicesEmpty => 'ابھی تک کوئی خدمت دستیاب نہیں۔';

  @override
  String get mobileRequestsAddDayLabel => 'دن';

  @override
  String get mobileRequestsAddTimeLabel => 'وقت';

  @override
  String get mobileRequestsAddMapsLinkLabel => 'گوگل میپس لوکیشن لنک';

  @override
  String get mobileRequestsAddMapsLinkHint =>
      'مکمل یا مختصر گوگل میپس لنک قبول کرتا ہے۔';

  @override
  String get mobileRequestsAddMapsLinkShort =>
      'یہ ایک مختصر لنک ہے — مکمل گوگل میپس لنک پیسٹ کریں۔';

  @override
  String get mobileRequestsAddMapsLinkInvalid =>
      'اس لنک سے مقام نہیں پڑھا جا سکا۔';

  @override
  String get mobileRequestsAddAssignLabel => 'تفویض کریں (اختیاری)';

  @override
  String get mobileRequestsAddCancel => 'منسوخ کریں';

  @override
  String get mobileRequestsAddSubmit => 'درخواست شامل کریں';

  @override
  String get mobileRequestsAddSubmitting => 'شامل ہو رہا ہے...';

  @override
  String get mobileRequestsAddError =>
      'درخواست شامل نہیں ہو سکی، دوبارہ کوشش کریں۔';

  @override
  String mobileRequestsBannerText(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count درخواستیں ابھی آپ کے فیصلے کی منتظر ہیں',
    );
    return '$_temp0';
  }

  @override
  String get mobileRequestsAddMapsLinkResolving =>
      'لنک سے مقام پڑھا جا رہا ہے...';

  @override
  String get customersTitle => 'رابطے';

  @override
  String get customersAddOpen => 'گاہک شامل کریں';

  @override
  String get customersSearchHint => 'نام یا فون سے تلاش کریں';

  @override
  String get customersTabAll => 'تمام';

  @override
  String get customersTabOverdue => 'تاخیر زدہ';

  @override
  String get customersSearchFailedTitle => 'ابھی تلاش دستیاب نہیں';

  @override
  String get customersSearchFailedBody => 'تھوڑی دیر بعد دوبارہ کوشش کریں۔';

  @override
  String get customersSearchEmpty => 'کوئی نتیجہ نہیں';

  @override
  String get customersLoadFailedTitle => 'لوڈ نہیں ہو سکا';

  @override
  String get customersEmptyTitle => 'ابھی تک کوئی گاہک نہیں';

  @override
  String get customersOverdueEmpty => 'فی الحال کوئی تاخیر زدہ نہیں';

  @override
  String get customersUnnamed => 'بلا نام';

  @override
  String customersVisitCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count وزٹس',
    );
    return '$_temp0';
  }

  @override
  String get customersOverdueBadge => 'تاخیر';

  @override
  String customersStatEveryDays(int days) {
    String _temp0 = intl.Intl.pluralLogic(
      days,
      locale: localeName,
      other: 'ہر $days دن',
    );
    return '$_temp0';
  }

  @override
  String customersOverdueBanner(int every, int since) {
    return 'اپنی معمول کی وزٹ میں تاخیر — عام طور پر ہر $every دن، آخری وزٹ کو $since دن ہو چکے ہیں';
  }

  @override
  String customersVisitMeter(int n) {
    return 'میٹر ریڈنگ: $n';
  }

  @override
  String get customersOfferExpiredBadge => 'ختم ہو گیا';

  @override
  String get customersDeniedAllTitle =>
      'آپ کو گاہکوں کی فہرست دیکھنے کی اجازت نہیں';

  @override
  String get customersDeniedOverdueTitle =>
      'آپ کو تاخیر والوں کو دیکھنے کی اجازت نہیں';

  @override
  String get customersDeniedDesc => 'دکان کے مالک سے یہ اجازت طلب کریں۔';

  @override
  String get customersAddTitle => 'نیا گاہک شامل کریں';

  @override
  String get customersAddPhoneLabel => 'گاہک کا فون';

  @override
  String get customersAddNameLabel => 'گاہک کا نام';

  @override
  String get customersAddPhoneInvalid => 'فون نمبر درست نہیں۔';

  @override
  String get customersAddFailed => 'گاہک شامل نہیں ہو سکا، دوبارہ کوشش کریں۔';

  @override
  String get customersAddSubmitting => 'شامل ہو رہا ہے...';

  @override
  String get customersAddSubmit => 'شامل کریں';

  @override
  String get customersActionFailed =>
      'کارروائی مکمل نہیں ہو سکی، دوبارہ کوشش کریں۔';

  @override
  String get customersRepeatedIssuesTitle => 'بار بار شکایات';

  @override
  String get customersVehiclesTitle => 'گاڑیاں';

  @override
  String get customersLoyaltyTitle => 'وفاداری';

  @override
  String get customersLoyaltyLoading => 'لوڈ ہو رہا ہے...';

  @override
  String customersLoyaltyPoints(int count) {
    return '$count پوائنٹس';
  }

  @override
  String get customersLoyaltyAdjust => 'ترمیم کریں';

  @override
  String get customersOffersTitle => 'جاری آفرز';

  @override
  String customersOfferExpires(String date) {
    return '$date کو ختم';
  }

  @override
  String get customersVisitsTitle => 'وزٹ کی تاریخ';

  @override
  String get customersVisitsEmpty => 'ابھی تک کوئی وزٹ نہیں';

  @override
  String get customersVisitNoServices => 'کوئی خدمت درج نہیں';

  @override
  String get customersRenameTitle => 'گاہک کا نام تبدیل کریں';

  @override
  String get customersRenameSubmit => 'محفوظ کریں';

  @override
  String get customersLoyaltyAdjustTitle => 'وفاداری پوائنٹس ترمیم کریں';

  @override
  String get customersLoyaltyAdjustNoteLabel => 'ترمیم کی وجہ';

  @override
  String get customersLoyaltyAdjustNoteRequired =>
      'ایک حقیقی وجہ لکھیں (کم از کم 3 حروف)، اور غیر صفر تعداد منتخب کریں۔';

  @override
  String get customersLoyaltyAdjustSubmit => 'ترمیم محفوظ کریں';

  @override
  String get customersEraseButton => 'اس گاہک کا ڈیٹا حذف کریں';

  @override
  String get customersEraseTitle => 'گاہک کا ڈیٹا حذف کریں';

  @override
  String get customersEraseWarning =>
      'یہ پلیٹ فارم سے گاہک کا تمام ڈیٹا مستقل طور پر حذف کر دیتا ہے — اسے واپس نہیں لیا جا سکتا۔';

  @override
  String customersEraseTypeNameLabel(String name) {
    return 'تصدیق کے لیے، گاہک کا نام لکھیں: $name';
  }

  @override
  String get customersEraseConfirm => 'مستقل حذف کریں';

  @override
  String get customersBookingsTitle => 'بکنگز';

  @override
  String customersAttendanceRate(int rate) {
    return '$rate٪ حاضری';
  }

  @override
  String get customersBookingsNoneUpcoming => 'کوئی آئندہ بکنگ نہیں';

  @override
  String get customersCyclesTitle => 'یاد دہانی کے چکر';

  @override
  String customersCyclesEveryDays(int days) {
    return 'ہر $days دن';
  }

  @override
  String get customersCyclesEditHint =>
      'وقفہ مقرر کریں، اور اس گاہک کے ساتھ اس خدمت کے لیے خودکار سیکھنا رک جائے گا۔';

  @override
  String get customersCyclesSave => 'محفوظ کریں';

  @override
  String get customersLogTitle => 'ہم نے کیا کہا';

  @override
  String get customersLogEmpty => 'ہم نے ابھی تک کچھ نہیں بھیجا';

  @override
  String get customersCyclesUnknownService => 'نامعلوم خدمت';

  @override
  String customersVisitGapDays(int days) {
    String _temp0 = intl.Intl.pluralLogic(
      days,
      locale: localeName,
      other: '$days دن بعد',
      zero: 'اسی دن',
    );
    return '$_temp0';
  }

  @override
  String customersCountLabel(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count گاہک',
      zero: 'ابھی تک کوئی گاہک نہیں',
    );
    return '$_temp0';
  }

  @override
  String get ratingTitle => 'ریٹنگ';

  @override
  String get pointsTitle => 'وفاداری پوائنٹس';

  @override
  String get pointsAddReward => 'نیا انعام';

  @override
  String get pointsEditReward => 'انعام میں ترمیم';

  @override
  String get pointsTabRewards => 'انعامات';

  @override
  String get pointsTabLeaderboard => 'سب سے زیادہ حاصل شدہ';

  @override
  String get pointsOutstandingHint =>
      'پوائنٹس جو دکان ابھی تک گاہکوں کے ذمہ ہیں';

  @override
  String pointsRedemptionsCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count تبادلے',
    );
    return '$_temp0';
  }

  @override
  String pointsCustomersCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count گاہکوں نے تبادلہ کیا',
    );
    return '$_temp0';
  }

  @override
  String pointsExpiredWarning(int percent) {
    return 'دیے گئے پوائنٹس کا %$percent بغیر تبادلے کے ختم ہو گیا — اپنے انعامات کی قیمتیں دیکھیں';
  }

  @override
  String get pointsLoadFailedTitle => 'انعامات لوڈ نہیں ہو سکے';

  @override
  String get pointsRewardsEmpty =>
      'ابھی کوئی انعام نہیں — اپنے گاہکوں کا پہلا انعام شامل کریں';

  @override
  String get pointsLeaderboardEmpty =>
      'ابھی کوئی تبادلہ نہیں — گاہک کے تبادلہ کرتے ہی یہاں ظاہر ہوگا';

  @override
  String get pointsLeaderboardTitle => 'سب سے زیادہ حاصل شدہ';

  @override
  String get pointsLeaderboardHint =>
      'آپ کے گاہکوں کے حاصل کردہ پانچ سب سے زیادہ انعامات';

  @override
  String pointsTimesRedeemed(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count بار',
    );
    return '$_temp0';
  }

  @override
  String get pointsRewardRetired => 'بند';

  @override
  String pointsRewardServiceHint(String name) {
    return 'سروس: $name';
  }

  @override
  String pointsRewardDiscountHint(String amount) {
    return '$amount ریال رعایت';
  }

  @override
  String get pointsRewardItemHint => 'تحفہ، کیٹلاگ سے منسلک نہیں';

  @override
  String get pointsRewardNameLabel => 'انعام کا نام';

  @override
  String get pointsRewardTypeLabel => 'انعام کی قسم';

  @override
  String get pointsTypeService => 'آپ کے کیٹلاگ سے ایک سروس';

  @override
  String get pointsTypeItem => 'ایک تحفہ';

  @override
  String get pointsTypeDiscount => 'نقد رعایت';

  @override
  String get pointsRewardServiceLabel => 'کون سی سروس';

  @override
  String get pointsRewardDiscountLabel => 'رعایت کی رقم، ریال';

  @override
  String get pointsRewardCostLabel => 'پوائنٹس میں قیمت';

  @override
  String get pointsRewardActiveLabel => 'فعال — گاہک اسے حاصل کر سکتے ہیں';

  @override
  String get pointsRewardInvalid =>
      'ایک نام اور صفر سے زیادہ حقیقی پوائنٹس قیمت درج کریں';

  @override
  String get pointsSaveFailed => 'محفوظ نہیں ہو سکا، دوبارہ کوشش کریں';

  @override
  String get pointsModeTitle => 'احتساب کا طریقہ';

  @override
  String get pointsModeHint =>
      'خدمات کے حساب سے: ہر خدمت کے اپنے پوائنٹس۔ فاتورہ کی قیمت کے حساب سے: ہر ریال پر ایک پوائنٹ۔';

  @override
  String get pointsModeServices => 'خدمات کے حساب سے';

  @override
  String get pointsModeInvoice => 'فاتورہ کی قیمت کے حساب سے';

  @override
  String get pointsModeNeedsPricedServices =>
      'فاتورے کی قیمت کے حساب سے احتساب کے لیے پہلے ہر سروس کی قیمت مقرر ہونی چاہیے — سب کی قیمت میری سروسز میں مقرر کریں، پھر اسے فعال کریں۔';

  @override
  String get pointsOpenEarnSettings => 'ہر سروس کے پوائنٹس کی سیٹنگز';

  @override
  String get ratingLeaderboardTitle => 'سب سے زیادہ ریٹیڈ';

  @override
  String get ratingCardNoName => 'بلا نام';

  @override
  String get ratingMetricVisits => 'سب سے زیادہ وزٹس';

  @override
  String get ratingMetricRatings => 'سب سے زیادہ ریٹنگز';

  @override
  String get ratingMetricAvg => 'سب سے زیادہ ریٹیڈ';

  @override
  String ratingStaffCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count ملازمین',
    );
    return '$_temp0';
  }

  @override
  String get ratingTableTitle => 'ہر ملازم';

  @override
  String ratingTableVisitsValue(int n) {
    return '$n وزٹس';
  }

  @override
  String ratingTableRatingsValue(int n) {
    return '$n ریٹنگز';
  }

  @override
  String ratingTableEngagementValue(int n) {
    return 'شمولیت %$n';
  }

  @override
  String ratingTableNoShowValue(int n) {
    return 'غیر حاضر %$n';
  }

  @override
  String get ratingPeriodWeek => 'ہفتہ';

  @override
  String get ratingPeriodMonth => 'مہینہ';

  @override
  String get ratingPeriodQuarter => 'سہ ماہی';

  @override
  String get ratingPeriodCustom => 'مخصوص';

  @override
  String ratingCustomSince(String date) {
    return 'سے: $date';
  }

  @override
  String ratingCustomUntil(String date) {
    return 'تک: $date';
  }

  @override
  String get ratingCustomRangeInvalid =>
      'مدت درست نہیں — یقینی بنائیں شروع کی تاریخ اختتام سے پہلے ہو';

  @override
  String get ratingExportLocaleLabel => 'رپورٹ کی زبان';

  @override
  String get localeNameAr => 'العربية';

  @override
  String get localeNameEn => 'English';

  @override
  String get localeNameUr => 'اردو';

  @override
  String get localeNameHa => 'Hausa';

  @override
  String get localeNameFil => 'Filipino';

  @override
  String get localeNameBn => 'বাংলা';

  @override
  String get ratingTopIssuesTitle => 'سب سے زیادہ دہرائے جانے والے مسائل';

  @override
  String get ratingFilterUnhandled => 'زیر التوا';

  @override
  String get ratingFilterAll => 'تمام';

  @override
  String get ratingFilterHandled => 'حل شدہ';

  @override
  String get ratingStarsAll => 'تمام ستارے';

  @override
  String get ratingLoadFailedTitle => 'ریٹنگز لوڈ نہیں ہو سکیں';

  @override
  String get ratingEmptyTitle => 'ابھی تک کوئی ریٹنگ نہیں';

  @override
  String get ratingLoadMore => 'مزید دکھائیں';

  @override
  String get ratingHandledPlain => 'حل ہو گیا';

  @override
  String get ratingMarkHandled => 'حل شدہ نشان زد کریں';

  @override
  String get ratingMarkHandledHint =>
      'یہ مستقل طور پر ریکارڈ ہوتا ہے — بعد میں واپس نہیں لیا جا سکتا۔';

  @override
  String get ratingHandledNoteLabel => 'نوٹ (اختیاری)';

  @override
  String get ratingMarkHandledConfirm => 'تصدیق کریں';

  @override
  String get ratingActionFailed =>
      'کارروائی مکمل نہیں ہو سکی، دوبارہ کوشش کریں۔';

  @override
  String ratingWeightedAvgHint(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'پچھلے 30 دنوں میں $count ریٹنگز سے',
      zero: 'پچھلے 30 دنوں میں کوئی ریٹنگ نہیں',
    );
    return '$_temp0';
  }

  @override
  String ratingUnhandledCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count ریٹنگز زیر التوا',
    );
    return '$_temp0';
  }

  @override
  String ratingVisitsShort(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count وزٹس',
    );
    return '$_temp0';
  }

  @override
  String ratingIssueFilterLabel(String label) {
    return 'مسئلہ: $label';
  }

  @override
  String ratingByOperator(String name) {
    return '$name نے خدمت دی';
  }

  @override
  String ratingHandledWithNote(String note) {
    return 'حل ہوگیا: $note';
  }

  @override
  String get ratingQuadrantTitle => 'کارکردگی کواڈرینٹ';

  @override
  String get ratingQuadrantHint =>
      'معیار بمقابلہ مصروفیت کی شرح — تربیتی ریکارڈ کے لیے کسی بھی نقطے کو دبائیں۔';

  @override
  String get ratingQuadrantStars => 'ستارے';

  @override
  String get ratingQuadrantUnderused => 'کم استعمال شدہ';

  @override
  String get ratingQuadrantNeedsCoaching => 'تربیت درکار';

  @override
  String get ratingQuadrantAtRisk => 'توجہ درکار';

  @override
  String get ratingTrainingTitle => 'تربیتی ریکارڈ';

  @override
  String get ratingTrainingNoAccess => 'آپ کو یہ دیکھنے کی اجازت نہیں ہے۔';

  @override
  String get ratingTrainingClean =>
      'صاف ریکارڈ — کوئی دہرائے جانے والے مسائل نہیں۔';

  @override
  String ratingEngagementPercent(int percent) {
    return '$percent٪ مصروفیت';
  }

  @override
  String get ratingTabOverview => 'جائزہ';

  @override
  String get ratingTabFeed => 'تمام ریٹنگز';

  @override
  String get ratingOverviewEmpty =>
      'پچھلے 30 دنوں کے لیے ابھی تک کارکردگی کا کوئی ڈیٹا نہیں۔';

  @override
  String get ratingExportTitle => 'رپورٹ برآمد کریں';

  @override
  String get ratingExportHint =>
      'ٹیم کی کارکردگی کی رپورٹ منتخب کردہ مدت کی، شیئر کرنے کے لیے تیار۔';

  @override
  String get ratingExportFailed => 'رپورٹ برآمد نہیں ہو سکی، دوبارہ کوشش کریں۔';

  @override
  String get customersPrivacyRequestsTitle => 'رازداری کی درخواستیں';

  @override
  String get customersPrivacyRequestErase => 'ڈیٹا حذف کرنے کی درخواست';

  @override
  String get customersPrivacyRequestCopy => 'ڈیٹا کاپی کی درخواست';

  @override
  String customersPrivacyRequestGeneric(String type) {
    return 'درخواست: $type';
  }

  @override
  String get customersPrivacyRequestClose => 'بند کریں';

  @override
  String get customersLoyaltyHistoryTitle => 'پوائنٹس کی تاریخ';

  @override
  String get customersLoyaltyHistoryNoReason => 'کوئی وجہ نہیں بتائی گئی';

  @override
  String get customersLoyaltyReasonRedeem => 'انعام کا استعمال';

  @override
  String get customersLoyaltyReasonAdjust => 'دستی ترمیم';

  @override
  String get customersLoyaltyReasonEarn => 'وزٹ سے پوائنٹس';

  @override
  String get customersLoyaltyReasonExpire => 'میعاد ختم';

  @override
  String get readCustomersFailed =>
      'ابھی گاہک کا ڈیٹا حاصل نہیں ہو سکا، دوبارہ کوشش کریں۔';

  @override
  String readCustomersTotal(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'آپ کے پاس $count رجسٹرڈ گاہک ہیں۔',
      zero: 'ابھی تک کوئی گاہک رجسٹرڈ نہیں۔',
    );
    return '$_temp0';
  }

  @override
  String readCustomersOverdueCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'آپ کے $count گاہک اپنے چکر میں تاخیر کا شکار ہیں۔',
      zero: 'فی الحال کوئی گاہک اپنے چکر میں تاخیر کا شکار نہیں۔',
    );
    return '$_temp0';
  }

  @override
  String get readMobileRequestsFailed =>
      'ابھی موبائل درخواستیں حاصل نہیں ہو سکیں، دوبارہ کوشش کریں۔';

  @override
  String readMobileRequestsPendingCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'آپ کی $count درخواستیں فیصلے کی منتظر ہیں۔',
      zero: 'کوئی موبائل درخواست فیصلے کی منتظر نہیں۔',
    );
    return '$_temp0';
  }

  @override
  String readMobileRequestsNeedsDecisionCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count درخواستیں ابھی آپ کے فیصلے کی منتظر ہیں۔',
      zero: 'فی الحال کوئی موبائل درخواست آپ کے فیصلے کی منتظر نہیں۔',
    );
    return '$_temp0';
  }

  @override
  String get readRatingFailed =>
      'ابھی ریٹنگ کا ڈیٹا حاصل نہیں ہو سکا، دوبارہ کوشش کریں۔';

  @override
  String get readRatingNone => 'پچھلے 30 دنوں میں ابھی تک کوئی ریٹنگ نہیں۔';

  @override
  String readRatingAverage(String avg, int count) {
    return 'پچھلے 30 دنوں میں آپ کی اوسط ریٹنگ 5 میں سے $avg ہے، $count ریٹنگز سے۔';
  }

  @override
  String readRatingUnhandledCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'آپ کی $count ریٹنگز زیر التوا ہیں۔',
      zero: 'کوئی ریٹنگ زیر التوا نہیں۔',
    );
    return '$_temp0';
  }

  @override
  String readRatingTopStaff(String name, String avg) {
    return 'پچھلے 30 دنوں میں سب سے بہتر ریٹیڈ عملہ $name ہے، اوسط $avg از 5۔';
  }

  @override
  String readMobileRequestsCompletedCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'اس مہینے آپ نے $count مکمل کیں۔',
      zero: 'اس مہینے ابھی تک کوئی موبائل درخواست مکمل نہیں ہوئی۔',
    );
    return '$_temp0';
  }

  @override
  String readMobileRequestsTodayCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'آج $count درخواستیں آئیں۔',
      zero: 'آج تک کوئی موبائل درخواست نہیں آئی۔',
    );
    return '$_temp0';
  }

  @override
  String get readOperatorsFailed =>
      'ابھی عملے کی تعداد حاصل نہیں ہو سکی، دوبارہ کوشش کریں۔';

  @override
  String readOperatorsCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'آپ کی ٹیم میں $count افراد ہیں۔',
      zero: 'ابھی تک کوئی عملہ رجسٹرڈ نہیں۔',
    );
    return '$_temp0';
  }

  @override
  String readBranchesDisconnectedCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'آپ کی $count شاخوں کا واٹس ایپ کام نہیں کر رہا۔',
      zero: 'آپ کی تمام فعال شاخوں کا واٹس ایپ مربوط اور کام کر رہا ہے۔',
    );
    return '$_temp0';
  }

  @override
  String get readCustomersRecentNone =>
      'ابھی تک آپ کے پاس کوئی گاہک رجسٹرڈ نہیں۔';

  @override
  String readCustomersRecentName(String name) {
    return 'آپ کا تازہ ترین گاہک $name ہے۔';
  }

  @override
  String readRatingCriticalIssuesCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'آپ کی $count زیر التوا ریٹنگز میں سنگین مسائل ہیں۔',
      zero: 'کوئی زیر التوا ریٹنگ میں سنگین مسئلہ نہیں۔',
    );
    return '$_temp0';
  }

  @override
  String get readPerBranchModeOn =>
      'جی ہاں، آپ کی دکان ملٹی برانچ موڈ میں چلتی ہے۔';

  @override
  String get readPerBranchModeOff =>
      'نہیں، آپ کی دکان صرف ایک شاخ کے طور پر چلتی ہے۔';

  @override
  String get readBillingOverdueYes =>
      'جی ہاں، آپ کا ایک زیر التوا انوائس ہے — خدمات بند ہونے سے بچنے کے لیے ادا کریں۔';

  @override
  String get readBillingOverdueNo =>
      'نہیں، آپ کی بلنگ ٹھیک ہے، کوئی زیر التوا انوائس نہیں۔';

  @override
  String get readServicesFailed =>
      'ابھی خدمات کی تعداد حاصل نہیں ہو سکی، دوبارہ کوشش کریں۔';

  @override
  String readServicesCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'آپ کی فہرست میں $count خدمات ہیں۔',
      zero: 'ابھی تک آپ کی فہرست میں کوئی خدمت نہیں۔',
    );
    return '$_temp0';
  }

  @override
  String readCustomersTodayCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'آج $count نئے گاہک آئے۔',
      zero: 'آج تک کوئی نیا گاہک نہیں آیا۔',
    );
    return '$_temp0';
  }

  @override
  String readMobileRequestsRejectedCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'اس مہینے آپ نے $count مسترد کیں۔',
      zero: 'اس مہینے آپ نے کوئی موبائل درخواست مسترد نہیں کی۔',
    );
    return '$_temp0';
  }

  @override
  String readMobileRequestsNoShowCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'اس مہینے $count گاہک غیر حاضر ہوئے۔',
      zero: 'اس مہینے کوئی گاہک غیر حاضر نہیں ہوا۔',
    );
    return '$_temp0';
  }

  @override
  String readRatingFiveStarCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'آپ کی $count پانچ ستارہ ریٹنگز ہیں۔',
      zero: 'ابھی تک آپ کی کوئی 5 ستارہ ریٹنگ نہیں۔',
    );
    return '$_temp0';
  }

  @override
  String readBranchesActiveCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'آپ کی $count فعال شاخیں ہیں۔',
      zero: 'فی الحال آپ کی کوئی فعال شاخ نہیں۔',
    );
    return '$_temp0';
  }

  @override
  String get servicesTitle => 'میری خدمات';

  @override
  String get servicesUnnamedGlyph => '?';

  @override
  String get servicesSearchHint => 'خدمت کے نام سے تلاش کریں';

  @override
  String get servicesTabActive => 'فعال';

  @override
  String get servicesTabStopped => 'بند';

  @override
  String get servicesLoadFailedTitle => 'خدمات لوڈ نہیں ہو سکیں';

  @override
  String get servicesEmptyActive => 'ابھی تک کوئی فعال خدمت نہیں';

  @override
  String get servicesEmptyStopped => 'کوئی بند خدمت نہیں';

  @override
  String get servicesAddOpen => 'خدمت شامل کریں';

  @override
  String get servicesNoPrice => 'کوئی قیمت مقرر نہیں';

  @override
  String get servicesNoDuration => 'غیر متعین';

  @override
  String get servicesNoCycle => 'کوئی دور نہیں';

  @override
  String get servicesStopTitle => 'خدمت بند کریں';

  @override
  String get servicesStopConfirm => 'بند کریں';

  @override
  String get servicesActionFailed =>
      'کارروائی مکمل نہیں ہو سکی، دوبارہ کوشش کریں۔';

  @override
  String get servicesEditTitle => 'خدمت میں ترمیم کریں';

  @override
  String get servicesAddTitle => 'نئی خدمت شامل کریں';

  @override
  String get servicesNameLabel => 'خدمت کا نام';

  @override
  String get servicesPriceLabel => 'قیمت (اختیاری)';

  @override
  String get servicesDurationLabel => 'منٹوں میں دورانیہ (اختیاری)';

  @override
  String get servicesCycleLabel => 'یاد دہانی کا دور دنوں میں (اختیاری)';

  @override
  String get servicesDescriptionLabel => 'مختصر تفصیل (اختیاری)';

  @override
  String get servicesSaving => 'محفوظ ہو رہا ہے...';

  @override
  String get servicesSave => 'محفوظ کریں';

  @override
  String get servicesNameRequired => 'خدمت کا نام درکار ہے';

  @override
  String servicesActiveCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'آپ کی $count فعال خدمات ہیں۔',
      zero: 'ابھی تک کوئی فعال خدمت نہیں۔',
    );
    return '$_temp0';
  }

  @override
  String servicesDurationMinutes(int count) {
    return '$count منٹ';
  }

  @override
  String servicesCycleDays(int count) {
    return 'ہر $count دن';
  }

  @override
  String servicesStopWarning(String name) {
    return 'یہ \"$name\" کو بند کر دے گا — نئی وزٹ میں نہیں دکھے گی، اور یاد دہانیاں رک جائیں گی۔ ڈیٹا کبھی حذف نہیں ہوتا۔';
  }

  @override
  String get servicesPhotoPickFailed => 'تصویر منتخب نہیں ہو سکی';

  @override
  String get servicesPhotoUploadFailed =>
      'محفوظ ہو گیا، لیکن تصویر اپ لوڈ نہیں ہو سکی';

  @override
  String get servicesPhotoLabel => 'خدمت کی تصویر (اختیاری)';

  @override
  String get servicesUploadPhoto => 'تصویر اپ لوڈ کریں';

  @override
  String get servicesChangePhoto => 'تصویر تبدیل کریں';

  @override
  String get servicesRemovePhoto => 'ہٹائیں';

  @override
  String get servicesAssignmentLabel => 'یہ خدمت کون فراہم کرتا ہے؟';

  @override
  String get servicesAssignmentAuto => 'کوئی بھی دستیاب اسٹاف';

  @override
  String get servicesAssignmentNamed => 'مخصوص اسٹاف';

  @override
  String get servicesChecklistLabel => 'طریقہ کار کے مراحل';

  @override
  String get servicesChecklistEmpty =>
      'ابھی تک کوئی مرحلہ نہیں — پہلا شامل کریں';

  @override
  String get servicesStepAddTitle => 'مرحلہ شامل کریں';

  @override
  String get servicesGeneralSettingsTitle => 'عمومی سیٹنگ';

  @override
  String get servicesGeneralSettingsHint =>
      'وہ قدر جس کی پیروی ہر وہ خدمت کرتی ہے جو ابھی تک مخصوص نہیں کی گئی';

  @override
  String get servicesFollowUpLabel => 'زیارت کے بعد فالو اپ کے دن';

  @override
  String get servicesPointsLabel => 'فی وزٹ پوائنٹس';

  @override
  String get servicesGroupThem => 'انہیں گروپ کریں';

  @override
  String get servicesGroupNameHint => 'گروپ کا نام';

  @override
  String get servicesAllGroups => 'سب';

  @override
  String get servicesStepEditTitle => 'مرحلہ میں ترمیم کریں';

  @override
  String get servicesStepCriticalLabel => 'نازک مرحلہ';

  @override
  String get servicesStepRetire => 'یہ مرحلہ بند کریں';

  @override
  String get servicesStepEditHint =>
      'کسی بھی مرحلے کو دیر تک دبائیں تاکہ اسے تبدیل یا بند کریں';

  @override
  String get servicesAdvancedTitle => 'اعلیٰ ترتیبات';

  @override
  String get servicesAdvancedHint =>
      'اس خدمت کو عمومی سیٹنگ سے مختلف بنائیں — دور، پوائنٹس، اور گروپنگ';

  @override
  String get servicesGroupLabel => 'گروپ';

  @override
  String get servicesNoGroup => 'کوئی گروپ نہیں';

  @override
  String get servicesNewGroup => 'نیا گروپ';

  @override
  String get servicesFollowGeneralAction => 'عمومی کی پیروی کریں';

  @override
  String get servicesCustomizeAction => 'مخصوص بنائیں';

  @override
  String servicesFollowUpDays(int n) {
    return '$n دن بعد فالو اپ';
  }

  @override
  String servicesPointsPerVisit(int n) {
    return '$n پوائنٹس';
  }

  @override
  String servicesSuggestionText(int n) {
    return '$n خدمات ایک ہی قدر رکھتی ہیں — انہیں ایک گروپ میں جمع کرنا بعد میں ترمیم آسان بناتا ہے۔';
  }

  @override
  String servicesFollowsGeneral(String hint) {
    return 'عمومی کی پیروی کرتا ہے — $hint';
  }

  @override
  String get servicesPageTabServices => 'خدمات';

  @override
  String get servicesPageTabPackages => 'پیکجز';

  @override
  String get servicesPackageAdd => 'پیکج شامل کریں';

  @override
  String get servicesPackageNeedsTwoServices =>
      'پیکج کے لیے کم از کم دو فعال خدمات درکار ہیں';

  @override
  String get servicesPackageEmpty => 'ابھی تک کوئی پیکج نہیں';

  @override
  String get servicesPackageEditTitle => 'پیکج میں ترمیم کریں';

  @override
  String get servicesPackageAddTitle => 'نیا پیکج شامل کریں';

  @override
  String get servicesPackageNameLabel => 'پیکج کا نام';

  @override
  String get servicesPackagePriceRequired =>
      'پیکج کی قیمت درکار ہے، صفر سے زیادہ';

  @override
  String get servicesPackageServicesLabel => 'شامل خدمات';

  @override
  String get servicesImportTitle => 'فائل سے خدمات درآمد کریں';

  @override
  String get servicesImportHint =>
      'کالموں والی CSV فائل: name, price, duration_minutes, cycle_days, description';

  @override
  String get servicesImportPickFile => 'CSV فائل منتخب کریں';

  @override
  String get servicesImportReadFailed => 'فائل پڑھی نہیں جا سکی';

  @override
  String get servicesImportParseFailed =>
      'فائل میں name کالم نہیں، یا اس کی فارمیٹنگ غلط ہے';

  @override
  String get servicesImportDeactivateMissing =>
      'فائل میں موجود نہ خدمات کو بند کریں';

  @override
  String get servicesImportDeactivateMissingHint =>
      'کوئی بھی موجودہ خدمت جو اس فائل میں نہیں وہ خودکار بند ہو جائے گی';

  @override
  String get servicesImportConfirm => 'درآمد کریں';

  @override
  String get servicesImportClose => 'ہو گیا';

  @override
  String servicesImportRowCount(int n) {
    return '$n قطاریں درآمد کے لیے تیار ہیں';
  }

  @override
  String servicesImportDone(int created, int updated, int reactivated) {
    return '$created شامل، $updated اپ ڈیٹ، $reactivated دوبارہ فعال۔';
  }

  @override
  String get visitPackagesSectionTitle => 'نمایاں پیکجز';

  @override
  String get visitNameFieldHint => 'گاہک کا نام (اختیاری)';

  @override
  String get visitMeterFieldHint => 'میٹر ریڈنگ';

  @override
  String get visitQuantityDialogTitle => 'مقدار';

  @override
  String get visitCouponCheckboxLabel => 'دوسرے دکان کو ڈسکاؤنٹ کوپن دیں';

  @override
  String get visitCouponPhoneHint => 'دکان کے مالک کا فون';

  @override
  String get visitClearAllButton => 'سب صاف کریں';

  @override
  String visitServicesSelectedCount(int n) {
    return '$n خدمات منتخب';
  }

  @override
  String get visitTodayBookingsTitle => 'آج کی ملاقاتیں';

  @override
  String get visitBookingAttendFailed =>
      'حاضری کی تصدیق نہیں ہو سکی، دوبارہ کوشش کریں';

  @override
  String get branchSwitcherChooseBranch => 'برانچ منتخب کریں';

  @override
  String get branchSwitcherTitle => 'موجودہ برانچ';

  @override
  String get branchSwitcherHint =>
      'اس کے بعد آپ جو کچھ کھولیں گے وہ اسی برانچ سے متعلق ہوگا';

  @override
  String get proceduresPrintFailed => 'دستاویز نہیں بن سکی';

  @override
  String get proceduresTitle => 'طریقہ کار';

  @override
  String get proceduresSubtitle =>
      'ہر خدمت کے لیے طریقہ کار کی فہرست سیٹ کریں، یا پوری مشترکہ لائبریری کا انتظام کریں۔ پرنٹ کے لیے منتخب کرنے کے لیے دبائے رکھیں';

  @override
  String get proceduresLibraryLink => 'طریقہ کار کی لائبریری';

  @override
  String get proceduresPrint => 'پرنٹ کریں';

  @override
  String get proceduresEmptyTitle => 'ابھی تک کوئی فعال خدمت نہیں';

  @override
  String get servicesStepSeverityNormal => 'عام';

  @override
  String get servicesStepSeverityCritical => 'اہم';

  @override
  String get proceduresSaveFailed => 'محفوظ نہیں ہو سکا';

  @override
  String get proceduresDrawerSubtitle =>
      'ترتیب بدلنے کے لیے گھسیٹیں، یا لائبریری سے مرحلہ شامل کریں';

  @override
  String get proceduresDrawerEmpty => 'اس خدمت کے لیے ابھی تک کوئی مرحلہ نہیں';

  @override
  String get proceduresDrawerAddButton => 'لائبریری سے شامل کریں';

  @override
  String get proceduresPickTitle => 'مرحلہ منتخب کریں';

  @override
  String get proceduresPickClose => 'بند کریں';

  @override
  String get proceduresPickApply => 'شامل کریں';

  @override
  String get proceduresPickSearch => 'مراحل تلاش کریں';

  @override
  String get proceduresPickEmpty => 'کوئی نتیجہ نہیں';

  @override
  String get proceduresPickCreatePlaceholder => 'نیا مرحلہ...';

  @override
  String get proceduresLibrarySaveFailed => 'محفوظ نہیں ہو سکا';

  @override
  String get proceduresLibraryTitle => 'طریقہ کار کی لائبریری';

  @override
  String get proceduresLibrarySubtitle =>
      'یہاں ہر مرحلہ اسے استعمال کرنے والی ہر خدمت میں مشترک ہے - اسے تبدیل کرنے سے ہر جگہ تبدیلی آتی ہے';

  @override
  String get proceduresLibraryNewPlaceholder => 'نئے مرحلے کا متن';

  @override
  String get proceduresLibraryAdd => 'شامل کریں';

  @override
  String get proceduresLibraryShowRetired => 'منسوخ شدہ دکھائیں';

  @override
  String get proceduresLibraryEmpty => 'ابھی تک کوئی مرحلہ نہیں';

  @override
  String get proceduresLibraryRetired => 'منسوخ';

  @override
  String get proceduresLibraryRetire => 'منسوخ کریں';

  @override
  String get proceduresLibraryReactivate => 'دوبارہ فعال کریں';

  @override
  String get proceduresSeverityHint =>
      'اہم مرحلہ عملے کے لیے مختلف رنگ میں نمایاں ہوتا ہے اور خدمت کی انجام دہی کے دوران اسے چھوڑا نہیں جا سکتا';

  @override
  String proceduresSelectedCount(int n) {
    return '$n منتخب';
  }

  @override
  String proceduresStepCount(int n) {
    return '$n مراحل';
  }

  @override
  String proceduresUsedIn(int n) {
    return '$n خدمات میں استعمال ہوتا ہے';
  }

  @override
  String get referralProposeButton => 'شراکت کی تجویز دیں';

  @override
  String get referralTitle => 'اسٹریٹجک شراکت';

  @override
  String get referralSubtitle =>
      'باہمی رضامندی سے اپنے اور دیگر دکانوں کے درمیان حقیقی گاہک منتقل کریں';

  @override
  String get referralRoleAll => 'سب';

  @override
  String get referralRoleReferrer => 'بطور ریفرر';

  @override
  String get referralRoleBeneficiary => 'بطور مستفید';

  @override
  String get referralLoadFailed => 'شراکتیں لوڈ نہیں ہو سکیں';

  @override
  String get referralEmptyTitle => 'ابھی تک کوئی شراکت نہیں';

  @override
  String get referralKpiAsReferrer => 'بطور ریفرر';

  @override
  String get referralKpiAsBeneficiary => 'بطور مستفید';

  @override
  String get referralKpiSent => 'بھیجی گئیں';

  @override
  String get referralKpiRedeemed => 'استعمال ہوئیں';

  @override
  String get referralKpiRate => 'استعمال کی شرح';

  @override
  String get referralConfirm => 'تصدیق کریں';

  @override
  String get referralGrantDiscountBlanket => 'پوری وزٹ پر رعایت';

  @override
  String get referralStatusProposed => 'تجویز کردہ';

  @override
  String get referralStatusActive => 'فعال';

  @override
  String get referralStatusPaused => 'عارضی طور پر روکا گیا';

  @override
  String get referralStatusCancelRequested => 'منسوخی کی درخواست دی گئی';

  @override
  String get referralStatusEnded => 'ختم شدہ';

  @override
  String get referralStatusRejected => 'مسترد';

  @override
  String get referralStatusExpiredUnanswered => 'بغیر جواب ختم ہوگئی';

  @override
  String get referralEventProposed => 'شراکت کی تجویز';

  @override
  String get referralEventAccepted => 'شراکت قبول';

  @override
  String get referralEventRejected => 'شراکت مسترد';

  @override
  String get referralEventActivated => 'شراکت فعال';

  @override
  String get referralEventCancelRequested => 'منسوخی کی درخواست';

  @override
  String get referralEventCancelConfirmed => 'منسوخی کی تصدیق';

  @override
  String get referralEventExpiredUnanswered => 'بغیر جواب میعاد ختم';

  @override
  String get referralEventPaused => 'عارضی توقف';

  @override
  String get referralEventResumed => 'دوبارہ شروع';

  @override
  String get referralEventEndedTerm => 'مدت ختم';

  @override
  String get referralEventGrantCreated => 'نئی مراعات';

  @override
  String get referralEventGrantRedeemed => 'مراعات استعمال ہوئی';

  @override
  String get referralActivityActive => 'فعال';

  @override
  String get referralActivityPaused => 'عارضی طور پر روکا گیا';

  @override
  String get referralActivityPending => 'جواب کا انتظار';

  @override
  String get referralActivityInactive => 'غیر فعال';

  @override
  String get referralScorecardTitle => 'کارکردگی';

  @override
  String get referralScorecardFailed => 'کارکردگی لوڈ نہیں ہو سکی';

  @override
  String get referralActivityTitle => 'حالیہ سرگرمی';

  @override
  String get referralActivityEmpty => 'ابھی تک کوئی سرگرمی نہیں';

  @override
  String get referralAgreementsTitle => 'معاہدے';

  @override
  String get referralConfirmCancel => 'اس شراکت کو مستقل طور پر ختم کریں؟';

  @override
  String get referralActionAccept => 'قبول کریں';

  @override
  String get referralActionReject => 'مسترد کریں';

  @override
  String get referralActionWaitingThem => 'دوسری جانب کا انتظار';

  @override
  String get referralActionCancelRequest => 'ختم کرنے کی درخواست';

  @override
  String get referralActionCancelConfirm => 'ختم کرنے کی تصدیق';

  @override
  String get referralProposeTitle => 'نئی شراکت کی تجویز دیں';

  @override
  String get referralProposePhoneLabel => 'دوسری دکان کا فون';

  @override
  String get referralProposeConditionLabel => 'آپ کی دکان پر اہلیت کی شرط';

  @override
  String get referralConditionMinTotal => 'کم از کم رقم';

  @override
  String get referralConditionServiceId => 'مخصوص خدمت';

  @override
  String get referralProposeConditionValueRiyals => 'رقم (ریال)';

  @override
  String get referralProposeConditionValueService => 'خدمت';

  @override
  String get referralProposeValidityLabel => 'مدت (دن)';

  @override
  String get referralProposeDurationLabel => 'مدت معاہدہ (دن)';

  @override
  String get referralProposeCapLabel => 'حد / 30 دن';

  @override
  String get referralProposeGrantTypeLabel => 'مراعات کی قسم';

  @override
  String get referralGrantTypeDiscount => 'رعایت';

  @override
  String get referralGrantTypeGift => 'تحفہ';

  @override
  String get referralScopeBlanket => 'پوری وزٹ';

  @override
  String get referralScopeItem => 'مخصوص خدمت';

  @override
  String get referralScopeGroup => 'گروپ/پیکج';

  @override
  String get referralProposeServiceLabel => 'خدمت';

  @override
  String get referralProposeGroupLabel => 'گروپ';

  @override
  String get referralProposeImmutableNote =>
      'بھیجنے کے بعد مراعات کی شرائط طے شدہ ہیں — مختلف پیشکش کے لیے نیا معاہدہ درکار ہے';

  @override
  String get referralProposeSubmitting => 'بھیجا جا رہا ہے...';

  @override
  String get referralProposeSubmit => 'تجویز بھیجیں';

  @override
  String referralGrantGift(String name) {
    return 'تحفہ: $name';
  }

  @override
  String referralGrantDiscountItem(String name) {
    return 'رعایت: $name';
  }

  @override
  String referralGrantDiscountGroup(String name) {
    return 'گروپ پر رعایت: $name';
  }

  @override
  String referralPartnerCount(int n) {
    return '$n معاہدے';
  }

  @override
  String get referralProposeResultFail => 'تجویز نہیں بھیجی جا سکی';

  @override
  String get referralRefusal402 =>
      'آپ کی دکان اسٹریٹجک شراکت ایپ کی سبسکرائبر نہیں — پہلے ایپ اسٹور سے سبسکرائب کریں';

  @override
  String get referralRefusal403 => 'آپ کے پاس اس عمل کی اجازت نہیں';

  @override
  String get referralRefusal400 =>
      'تجویز کا ڈیٹا درست نہیں — شرط چیک کریں، یا یقینی بنائیں کہ آپ اپنی دکان کے ساتھ شراکت تجویز نہیں کر رہے';

  @override
  String get referralRefusal404 =>
      'اس نمبر پر کوئی دکان نہیں ملی، یا منتخب کردہ خدمت/گروپ دوسری دکان کے کیٹلاگ میں موجود نہیں';

  @override
  String get referralRefusal409 =>
      'آپ فعال شراکتوں کی حد (3) تک پہنچ گئے ہیں، یا شراکت کی حالت تبدیل ہو گئی ہے';

  @override
  String get referralRefusal503 =>
      'بلنگ عارضی طور پر دستیاب نہیں، بعد میں دوبارہ کوشش کریں';

  @override
  String get appStoreTitle => 'ایپ اسٹور';

  @override
  String get appStoreSubtitle =>
      'اپنی دکان کو حقیقی ایپس سے بڑھائیں، ایک ایک کر کے';

  @override
  String get appStoreTabMine => 'میری ایپس';

  @override
  String get appStoreTabAll => 'ایپ اسٹور';

  @override
  String get appStoreDetails => 'تفصیلات';

  @override
  String get appStorePerMonth => 'ماہانہ';

  @override
  String get appStorePerMonthShort => '/ماہ';

  @override
  String get appStoreActive => 'فعال';

  @override
  String get appStoreTrialing => 'آزمائشی';

  @override
  String get appStoreSubscribe => 'ابھی سبسکرائب کریں';

  @override
  String get appStoreCancelRenewal => 'تجدید روکیں';

  @override
  String get appStoreUndoCancel => 'منسوخی واپس لیں';

  @override
  String get appStoreConfirmCancel =>
      'اس ایپ کی تجدید روکنا چاہتے ہیں؟ یہ ادا شدہ مدت ختم ہونے تک فعال رہے گی';

  @override
  String appStoreCartCount(int n) {
    return 'کارٹ میں $n';
  }

  @override
  String get appStoreCheckout => 'چیک آؤٹ';

  @override
  String get appStoreCheckingOut => 'چیک آؤٹ ہو رہا ہے...';

  @override
  String get appStoreRefusal402 =>
      'آپ کے اکاؤنٹ پر ابھی ادائیگی فعال نہیں ہے — فعال کرنے کے لیے رابطہ کریں';

  @override
  String get appStoreRefusal403 => 'آپ کو یہ خریداری مکمل کرنے کی اجازت نہیں';

  @override
  String get appStoreRefusal404 =>
      'مطلوبہ پلان نہیں ملا — ریفریش کر کے دوبارہ کوشش کریں';

  @override
  String get appStoreRefusal409 =>
      'یہ ایپ پہلے سے آپ کی ملکیت ہے، یا خریداری کے دوران اس کی حالت بدل گئی';

  @override
  String get appStoreRefusalGeneric =>
      'خریداری مکمل نہیں ہو سکی، دوبارہ کوشش کریں';

  @override
  String get appStoreCapacityTitle => 'گنجائش';

  @override
  String appStoreCapacityConfirmRemove(String name) {
    return '\"$name\" کی آخری یونٹ ہٹانا چاہتے ہیں؟ یہ اس کی تجدید مکمل طور پر روک دے گا';
  }

  @override
  String get whatsappAssistantTitle => 'اے آئی اسسٹنٹ';

  @override
  String get whatsappAssistantSubtitle =>
      'آپ کی جانب سے واٹس ایپ پر آپ کے گاہکوں کو جواب دیتا ہے، صحیح وقت پر آپ کے پلانز اور ان کے پوائنٹس تجویز کرتا ہے۔';

  @override
  String get whatsappAssistantLoadFailed =>
      'اسسٹنٹ کی ترتیبات لوڈ نہیں ہو سکیں۔';

  @override
  String get whatsappAssistantConfirm => 'تصدیق کریں';

  @override
  String get whatsappAssistantSaveFailed =>
      'محفوظ نہیں ہو سکا، دوبارہ کوشش کریں۔';

  @override
  String get whatsappAssistantToggleTitle => 'اسسٹنٹ جواب دے رہا ہے';

  @override
  String get whatsappAssistantToggleDesc =>
      'اسے بند کرنے سے اسسٹنٹ مکمل طور پر بند ہو جاتا ہے، بغیر سبسکرپشن منسوخ کیے — کسی بھی وقت دوبارہ چالو کریں۔';

  @override
  String get whatsappAssistantToggleConfirmEnableTitle =>
      'اے آئی اسسٹنٹ چالو کریں؟';

  @override
  String get whatsappAssistantToggleConfirmEnableBody =>
      'یہ فوراً آپ کے گاہکوں کو واٹس ایپ پر جواب دینا شروع کر دے گا۔';

  @override
  String get whatsappAssistantToggleConfirmDisableTitle =>
      'اے آئی اسسٹنٹ بند کریں؟';

  @override
  String get whatsappAssistantToggleConfirmDisableBody =>
      'یہ مکمل طور پر جواب دینا بند کر دے گا، جیسے آپ سبسکرائب ہی نہیں ہیں — بغیر سبسکرپشن منسوخ کیے۔';

  @override
  String get whatsappAssistantNotesTitle => 'دکان کے نوٹس';

  @override
  String get whatsappAssistantNotesDesc =>
      'یہاں جو لکھیں گے وہ اسسٹنٹ کو آپ کی دکان کے بارے میں اضافی معلومات کے ساتھ گاہکوں کی خدمت میں مدد دیتا ہے۔';

  @override
  String get whatsappAssistantWordLimitTitle => 'گاہک کے پیغام کی الفاظ کی حد';

  @override
  String get whatsappAssistantWordLimitDesc =>
      'سب سے لمبا پیغام جو اسسٹنٹ گاہک سے قبول کرتا ہے، مختصر کرنے کی درخواست سے پہلے۔';

  @override
  String get whatsappAssistantAutoRegisterTitle => 'خودکار رابطہ رجسٹریشن';

  @override
  String get whatsappAssistantAutoRegisterDesc =>
      'کوئی بھی نیا نمبر جو آپ کے واٹس ایپ پر پیغام بھیجے خودکار طور پر ایک حقیقی رابطے کے طور پر محفوظ ہو جاتا ہے۔';

  @override
  String get whatsappAssistantAutoRegisterConfirmEnableTitle =>
      'خودکار رجسٹریشن چالو کریں؟';

  @override
  String get whatsappAssistantAutoRegisterConfirmEnableBody =>
      'آپ کے واٹس ایپ نمبر پر پیغام بھیجنے والا ہر شخص خودکار طور پر رابطے کے طور پر محفوظ ہو جائے گا، ایک ہی پیغام سے بھی۔';

  @override
  String get whatsappAssistantAutoRegisterConfirmDisableTitle =>
      'خودکار رجسٹریشن بند کریں؟';

  @override
  String get whatsappAssistantAutoRegisterConfirmDisableBody =>
      'نئے نمبرز اب خودکار طور پر رابطوں کے طور پر محفوظ نہیں ہوں گے۔';

  @override
  String get partnerLoyaltyTitle => 'پارٹنر وفاداری';

  @override
  String get partnerLoyaltySubtitle =>
      'ہمارے ہاں رجسٹرڈ کسی اور دکان کے ساتھ اتحاد بنائیں اور اسے اس کی سبسکرپشن پر مراعات دیں';

  @override
  String get partnerLoyaltyCapLabel => 'آپ کی موجودہ حد';

  @override
  String get partnerLoyaltyPrefsTitle =>
      'وزٹ ریکارڈ کرتے وقت اتحاد بنانے کا خانہ';

  @override
  String get partnerLoyaltyPrefsDesc =>
      'اسے آن کرنے سے وزٹ ریکارڈ کرنے والا کوئی بھی عملہ اسی لمحے اتحاد بنا سکتا ہے۔';

  @override
  String get partnerLoyaltyGrantTitle => 'اتحاد بنائیں';

  @override
  String get partnerLoyaltyPhoneLabel => 'شریک دکان کا فون نمبر';

  @override
  String get partnerLoyaltyPhoneHintOk => 'اس ماہ ان کے ساتھ کوئی اتحاد نہیں';

  @override
  String get partnerLoyaltyPhoneHintAlready =>
      'اس ماہ آپ کا ان کے ساتھ پہلے ہی اتحاد موجود ہے';

  @override
  String get partnerLoyaltyPhoneHintUnregistered =>
      'یہ نمبر ہمارے ہاں رجسٹرڈ دکان نہیں ہے';

  @override
  String get partnerLoyaltyPercentLabel => 'مراعات کا فیصد';

  @override
  String partnerLoyaltyCapLine(int p) {
    return 'اب زیادہ سے زیادہ فیصد جو آپ دے سکتے ہیں: $p%';
  }

  @override
  String get partnerLoyaltyScopeLabel => 'شامل ہے';

  @override
  String get partnerLoyaltyScopeAll => 'سب';

  @override
  String get partnerLoyaltySubmit => 'اتحاد بنائیں';

  @override
  String get partnerLoyaltySubmitting => 'بھیجا جا رہا ہے…';

  @override
  String get partnerLoyaltyResultSuccess =>
      'اتحاد بن گیا — دکان کی اگلی تجدید پر خودکار طور پر لاگو ہوگا۔';

  @override
  String get partnerLoyaltyResultPartial =>
      'جزوی طور پر بنا — کچھ ایپس مسترد ہوئیں، تفصیل کے لیے «لاگ» دیکھیں۔';

  @override
  String get partnerLoyaltyOutcomeGranted => 'کامیاب';

  @override
  String get partnerLoyaltyOutcomeInvalidPercent => 'مراعات کا فیصد غلط ہے';

  @override
  String get partnerLoyaltyOutcomeInvalidScope => 'ایک حقیقی ایپ چنیں';

  @override
  String get partnerLoyaltyOutcomeOverCap => 'آپ کی موجودہ حد سے زیادہ ہے';

  @override
  String get partnerLoyaltyOutcomeNoAccount =>
      'یہ نمبر ہمارے ہاں رجسٹرڈ دکان نہیں ہے';

  @override
  String get partnerLoyaltyOutcomeNotSubscribed =>
      'اس دکان کے پاس آپ کی چنی ہوئی کوئی ایپ نہیں';

  @override
  String get partnerLoyaltyOutcomeBillingUnavailable =>
      'مکمل نہ ہو سکا، دوبارہ کوشش کریں';

  @override
  String get partnerLoyaltyOutcomeAlreadyHasBetterCoupon =>
      'اس کے پاس پہلے سے بہتر مراعات موجود ہیں';

  @override
  String get partnerLoyaltyOutcomeCouponExpired => 'مراعات ختم ہو چکی ہیں';

  @override
  String get partnerLoyaltyOutcomeCouponExhausted =>
      'مراعات استعمال ہو چکی ہیں';

  @override
  String get partnerLoyaltyOutcomeCouponUnknown => 'نامعلوم مراعات';

  @override
  String get partnerLoyaltyOutcomePlanMismatch =>
      'مراعات اس ایپ سے مطابقت نہیں رکھتیں';

  @override
  String get partnerLoyaltyOutcomeCouponDisabled => 'مراعات غیر فعال ہیں';

  @override
  String get partnerLoyaltyOutcomeCouponScheduled =>
      'مراعات ابھی شروع نہیں ہوئیں';

  @override
  String get partnerLoyaltyTabLog => 'لاگ';

  @override
  String get partnerLoyaltyTabStats => 'اعداد و شمار';

  @override
  String get partnerLoyaltyLogSearchHint => 'آخری 4 ہندسوں سے تلاش کریں';

  @override
  String get partnerLoyaltyLogFilterAll => 'تمام حالتیں';

  @override
  String get partnerLoyaltyLogFilterOk => 'صرف کامیاب';

  @override
  String get partnerLoyaltyLogFilterFail => 'صرف ناکام';

  @override
  String get partnerLoyaltyLogEmptyTitle => 'ابھی تک کوئی اتحاد نہیں';

  @override
  String get partnerLoyaltyLogEmptyDesc => 'آپ کا پہلا اتحاد یہاں ظاہر ہوگا۔';

  @override
  String get partnerLoyaltyLogReadFailed => 'لاگ پڑھا نہیں جا سکا';

  @override
  String get partnerLoyaltyStatsKpiMonth => 'اس ماہ کے اتحاد';

  @override
  String get partnerLoyaltyStatsKpiCap => 'آپ کی موجودہ حد';

  @override
  String get partnerLoyaltyStatsKpiCeiling => 'پلیٹ فارم کی زیادہ سے زیادہ حد';

  @override
  String get partnerLoyaltyStatsLadderTitle => 'سیڑھی پر آپ کا مقام';

  @override
  String partnerLoyaltyStatsLadderNote(int n, int left, int p) {
    return 'اس ماہ $n اتحاد — $p% سطح تک $left مزید باقی';
  }

  @override
  String partnerLoyaltyStatsLadderAtTop(int n) {
    return 'اس ماہ $n اتحاد — آپ سب سے اوپر والی سطح پر ہیں';
  }

  @override
  String partnerLoyaltyStatsCeilingNote(int p) {
    return 'پلیٹ فارم کی زیادہ سے زیادہ حد $p% — کوئی دکان اس سے تجاوز نہیں کرتی';
  }

  @override
  String get partnerLoyaltyStatsChartTitle => 'پچھلے 6 مہینوں کے اتحاد';

  @override
  String get partnerLoyaltyReadFailedTitle => 'آپ کا ڈیٹا پڑھا نہیں جا سکا';

  @override
  String get partnerLoyaltyReadFailedDesc => 'تھوڑی دیر بعد دوبارہ کوشش کریں۔';

  @override
  String get shopReadFailed => 'آپ کی دکان کے اشارے پڑھے نہیں جا سکے';

  @override
  String get shopMultiBranchTitle => 'ایک شاخ منتخب کریں';

  @override
  String get shopMultiBranchDesc =>
      'آپ کی ایک سے زیادہ شاخیں ہیں — اشارے دیکھنے کے لیے ایک منتخب کریں۔';

  @override
  String get shopEmptyBranchTitle => 'اس شاخ کے لیے ابھی کوئی ڈیٹا نہیں';

  @override
  String get shopRetentionTitle => 'آپ کے گاہکوں کی واپسی کی شرح';

  @override
  String get shopRetentionMutedNote =>
      'اسے شمار کرنے کے لیے کافی وزٹ نہیں ہیں۔';

  @override
  String get shopRetentionBrandNew =>
      'واپسی کی شرح دیکھنے کے لیے پہلی وزٹ درج کریں۔';

  @override
  String get shopRegisterFirstVisit => 'پہلی وزٹ درج کریں';

  @override
  String get shopRetentionPrefix10 => 'ہر ١٠ گاہکوں میں سے جو آپ کے پاس آئے،';

  @override
  String get shopRetentionSuffix => 'واپس آتے ہیں';

  @override
  String get shopOneCustomer => 'ایک گاہک نے آپ کے پاس وزٹ کیا';

  @override
  String shopNCustomers(int n) {
    return '$n گاہکوں نے آپ کے پاس وزٹ کیا';
  }

  @override
  String shopRetentionSmallPrefix(String base) {
    return '$base، جن میں سے';
  }

  @override
  String shopOverNMonths(int n) {
    return '$n مہینوں میں';
  }

  @override
  String get shopUnlimited => 'لامحدود';

  @override
  String get shopTileSentToday => 'آج بھیجے گئے';

  @override
  String get shopTileWaiting => 'زیرِ انتظار';

  @override
  String get shopTileCeilingRemaining => 'آج باقی';

  @override
  String get shopNextStepLabel => 'اگلا قدم';

  @override
  String get shopNotNow => 'ابھی نہیں';

  @override
  String get shopDeckUrgent => 'فوری';

  @override
  String get shopDeckWeek => 'اس ہفتے';

  @override
  String get shopDeckOpportunities => 'مواقع';

  @override
  String get shopComputedNow => 'ابھی شمار کیا گیا';

  @override
  String shopComputedHoursAgo(int n) {
    return '$n گھنٹے پہلے شمار کیا گیا';
  }

  @override
  String get shopStale => 'پرانا';

  @override
  String get shopRefreshAction => 'تازہ کریں';

  @override
  String get shopComputingTitle => 'آپ کے اشارے شمار کیے جا رہے ہیں';

  @override
  String get shopComputeLoading => 'شمار کیا جا رہا ہے…';

  @override
  String get shopComputeAction => 'ابھی شمار کریں';

  @override
  String get shopAtRiskTitle => 'جانے کے قریب گاہک';

  @override
  String get shopAtRiskMutedNote => 'ابھی کافی ڈیٹا نہیں۔';

  @override
  String get shopAtRiskAllGood => 'ابھی کوئی تاخیر شدہ گاہک نہیں — سب ٹھیک ہے';

  @override
  String get shopWaNotConnected => 'آپ کی دکان کا واٹس ایپ ابھی منسلک نہیں';

  @override
  String get shopWaNotVerified =>
      'آپ کی دکان کا واٹس ایپ نمبر ابھی تصدیق شدہ نہیں';

  @override
  String get shopCeilingReached => 'آپ آج کی پیغام کی حد تک پہنچ گئے';

  @override
  String shopDaysOverdue(int n) {
    return '$n دن تاخیر';
  }

  @override
  String get shopAtRiskCta => 'واپسی مہم بھیجیں';

  @override
  String get shopAiImpactTitle => 'واٹس ایپ اے آئی اسسٹنٹ کا اثر';

  @override
  String get shopAiConversations => 'گفتگو';

  @override
  String get shopAiBookings => 'بکنگز';

  @override
  String get shopAiUpsellRate => 'اضافی پیشکش کی قبولیت';

  @override
  String get shopWeekMutedTitle => 'اس ہفتے کی وزٹس';

  @override
  String get shopWeekMutedNote => 'ابھی کافی ڈیٹا نہیں۔';

  @override
  String get shopNewReturningMutedTitle => 'نئے بمقابلہ واپس آنے والے گاہک';

  @override
  String get shopNewReturningMutedNote => 'ابھی کافی ڈیٹا نہیں۔';

  @override
  String get shopBranchCompareTitle => 'شاخوں کا موازنہ';

  @override
  String get shopBranchCompareMutedNote =>
      'موازنے کے لیے کم از کم دو شاخیں درکار ہیں۔';

  @override
  String get shopStaffCompareTitle => 'عملے کا موازنہ';

  @override
  String get shopStaffCompareMutedNote =>
      'موازنے کے لیے کم از کم دو عملے کے افراد درکار ہیں۔';

  @override
  String get shopWeekTitle => 'اس ہفتے کی وزٹس';

  @override
  String get shopNewReturningTitle => 'نئے بمقابلہ واپس آنے والے';

  @override
  String get shopNewLabel => 'نئے:';

  @override
  String get shopReturningLabel => 'واپس آنے والے:';

  @override
  String get shopServicesTitle => 'آپ کی سروسز';

  @override
  String get shopServicesMutedNote => 'ابھی کافی ڈیٹا نہیں۔';

  @override
  String get shopMessageFlowTitle => 'یاد دہانی پیغام کا اثر';

  @override
  String get shopMutedMessageFlowNote => 'ابھی کافی ڈیٹا نہیں۔';

  @override
  String get shopHoldoutTitle =>
      'پیغام بھیجے گئے بمقابلہ نہ بھیجے گئے کا موازنہ';

  @override
  String get shopMutedHoldoutNote => 'ابھی ناپا جا رہا ہے۔';

  @override
  String shopReturnedAfterReminder(int visits, int days) {
    return 'یاد دہانی کے بعد $days دنوں میں $visits وزٹس';
  }

  @override
  String shopOptOutRate(String p) {
    return '$p% نے پیغامات بند کرنے کو کہا';
  }

  @override
  String get shopHoldoutNoMessages => 'بلا پیغام';

  @override
  String get shopHoldoutReached => 'پیغام بھیجا گیا';

  @override
  String get shopHoldoutOff =>
      'پیغامات کے اثر کی پیمائش بند ہے — سب گاہکوں کو سب کچھ پہنچتا ہے، تو موازنے کے لیے کوئی گروہ نہیں۔';

  @override
  String shopHoldoutMeasuring(int min, int need) {
    return 'ہم ابھی بھی آپ کی دکان پر پیغامات کا اثر ماپ رہے ہیں — چھوٹے گروہ میں $need میں سے $min۔';
  }

  @override
  String shopTodayRetrying(int n) {
    return '$n پیغام(ات) اب بھی بھیجنے کی کوشش میں';
  }

  @override
  String get shopTrendUp => 'بہتر ہو رہا ہے';

  @override
  String get shopTrendDown => 'گر رہا ہے';

  @override
  String shopRetentionSincePeriods(int n) {
    return '$n ادوار سے';
  }

  @override
  String get shopAtLeastSuffix => ' — کم از کم';

  @override
  String get shopRegisterFirstVisitArrow => 'پہلی وزٹ درج کریں ←';

  @override
  String get shopWeekNoCompare => 'موازنے کے لیے ابھی مکمل ہفتہ نہیں';

  @override
  String shopNextStepAlso(String msg) {
    return 'اور یہ بھی: $msg';
  }

  @override
  String shopBranchCompareUnassigned(int n) {
    return '$n وزٹ بغیر شاخ کے — کسی شاخ میں شمار نہیں۔';
  }

  @override
  String get shopBranchCompareNeedTwo =>
      'ابھی شاخوں کا موازنہ نہیں کرتے — حقیقی وزٹس کے ساتھ دو یا زیادہ شاخیں درکار ہیں۔';

  @override
  String get shopBranchCompareNeedSecond =>
      'ابھی تک ایک فعال شاخ — موازنے کے لیے حقیقی وزٹس والی دوسری شاخ درکار ہے۔';

  @override
  String get shopBranchCompareTooShort =>
      'ابھی شاخوں کی درجہ بندی نہیں کرتے — مدت بہت مختصر ہے، اور ابھی موازنہ نئی شاخ کے ساتھ ناانصافی ہوگا۔';

  @override
  String shopStaffCompareUnassigned(int n) {
    return '$n وزٹ بغیر عملے کے — کسی کے کھاتے میں شمار نہیں۔';
  }

  @override
  String get shopStaffCompareNeedTwo =>
      'ابھی عملے کا موازنہ نہیں کرتے — منسوب وزٹس کے ساتھ دو یا زیادہ عملہ درکار ہے۔';

  @override
  String get shopStaffCompareNeedSecond =>
      'ابھی تک ایک عملہ منسوب — موازنے کے لیے حقیقی وزٹس والا دوسرا درکار ہے۔';

  @override
  String get shopStaffCompareTooShort =>
      'ابھی عملے کی درجہ بندی نہیں کرتے — مدت بہت مختصر ہے، اور ابھی موازنہ نئے فرد کے ساتھ ناانصافی ہوگا۔';
}
