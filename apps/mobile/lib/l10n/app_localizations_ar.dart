// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Arabic (`ar`).
class SAr extends S {
  SAr([String locale = 'ar']) : super(locale);

  @override
  String get appName => 'راجِع';

  @override
  String get ok => 'موافق';

  @override
  String get cancel => 'إلغاء';

  @override
  String get save => 'حفظ';

  @override
  String get close => 'إغلاق';

  @override
  String get back => 'رجوع';

  @override
  String get next => 'التالي';

  @override
  String get done => 'تم';

  @override
  String get loading => 'جاري التحميل...';

  @override
  String get retry => 'إعادة المحاولة';

  @override
  String get error => 'حدث خطأ';

  @override
  String get success => 'تمت العملية بنجاح';

  @override
  String get search => 'بحث';

  @override
  String get login => 'تسجيل الدخول';

  @override
  String get logout => 'تسجيل الخروج';

  @override
  String get homeDashboardTitle => 'لوحة التحكم';

  @override
  String get homeShopSectionLabel => 'محلّي';

  @override
  String get homeLoadErrorTitle => 'تعذّر التحميل';

  @override
  String get homeLoadErrorMessage => 'تعذّر تحميل بيانات اليوم. حاول مرة أخرى.';

  @override
  String get homeTodaySectionTitle => 'اليوم';

  @override
  String get homeStatSent => 'أُرسلت';

  @override
  String get homeStatWaiting => 'في الانتظار';

  @override
  String get homeStatRetrying => 'تعيد المحاولة';

  @override
  String get homeDashboardComputing =>
      'أحسب مؤشرات محلك الآن — حدّث الصفحة بعد قليل';

  @override
  String get homeDashboardSectionTitle => 'مؤشرات المحل';

  @override
  String get homeDashboardEmpty => 'لا توجد بيانات كافية بعد.';

  @override
  String get themeDarkMode => 'الوضع الداكن';

  @override
  String get themeLightMode => 'الوضع الفاتح';

  @override
  String get validatorFieldRequiredGeneric => 'هذا الحقل مطلوب';

  @override
  String validatorFieldRequiredNamed(String field) {
    return '$field مطلوب';
  }

  @override
  String get validatorEmailRequired => 'البريد الإلكتروني مطلوب';

  @override
  String get validatorEmailInvalid => 'البريد الإلكتروني غير صالح';

  @override
  String get validatorPhoneRequired => 'رقم الهاتف مطلوب';

  @override
  String get validatorPhoneInvalid => 'رقم الهاتف غير صالح - يجب أن يبدأ بـ 05';

  @override
  String get validatorPasswordRequired => 'كلمة المرور مطلوبة';

  @override
  String get validatorPasswordTooShort =>
      'كلمة المرور يجب أن تكون 8 أحرف على الأقل';

  @override
  String get validatorPasswordNeedsUppercase =>
      'كلمة المرور يجب أن تحتوي على حرف كبير';

  @override
  String get validatorPasswordNeedsLowercase =>
      'كلمة المرور يجب أن تحتوي على حرف صغير';

  @override
  String get validatorPasswordNeedsDigit => 'كلمة المرور يجب أن تحتوي على رقم';

  @override
  String get validatorConfirmPasswordFieldName => 'تأكيد كلمة المرور';

  @override
  String get validatorPasswordMismatch => 'كلمة المرور غير متطابقة';

  @override
  String get validatorOtpRequired => 'رمز التحقق مطلوب';

  @override
  String get validatorOtpLength => 'رمز التحقق يجب أن يكون 6 أرقام';

  @override
  String get validatorOtpDigitsOnly => 'رمز التحقق يجب أن يحتوي على أرقام فقط';

  @override
  String get validatorNameRequired => 'الاسم مطلوب';

  @override
  String get validatorNameTooShort => 'الاسم يجب أن يكون حرفين على الأقل';

  @override
  String get validatorNameTooLong => 'الاسم يجب أن لا يتجاوز 100 حرف';

  @override
  String get validatorNameInvalidChars => 'الاسم يحتوي على أحرف غير مسموحة';

  @override
  String get validatorGenericFieldName => 'هذا الحقل';

  @override
  String validatorMinLengthNamed(String field, int minLength) {
    return '$field يجب أن يكون $minLength أحرف على الأقل';
  }

  @override
  String validatorMaxLengthNamed(String field, int maxLength) {
    return '$field يجب أن لا يتجاوز $maxLength حرف';
  }

  @override
  String get validatorGenericValueName => 'القيمة';

  @override
  String validatorNotANumberNamed(String field) {
    return '$field يجب أن يكون رقم';
  }

  @override
  String validatorMinValueNamed(String field, String min) {
    return '$field يجب أن يكون $min على الأقل';
  }

  @override
  String validatorMaxValueNamed(String field, String max) {
    return '$field يجب أن لا يتجاوز $max';
  }

  @override
  String get validatorUrlRequired => 'الرابط مطلوب';

  @override
  String get validatorUrlInvalid => 'الرابط غير صالح';

  @override
  String get urlHelperUnavailable => 'الرابط غير متوفر';

  @override
  String get urlHelperOpenFailed => 'تعذر فتح الرابط';

  @override
  String get routerScreenNotOnMobileYet =>
      'هذه الشاشة غير متاحة على تطبيق الجوال بعد.';

  @override
  String get kbHintNoEntry => 'ما فيه شرح لهذا بعد.';

  @override
  String get assistantChatTitle => 'المساعد';

  @override
  String get assistantInputHint => 'اكتب سؤالك...';

  @override
  String get assistantSend => 'إرسال';

  @override
  String get assistantUnavailable => 'المساعد غير متاح حالياً.';

  @override
  String get assistantPreparing => 'جاري تجهيز المساعد...';

  @override
  String get assistantRetryDownload => 'إعادة المحاولة';

  @override
  String get assistantSpeak => 'استمع للرد';

  @override
  String get assistantStopSpeaking => 'إيقاف الصوت';

  @override
  String get assistantActionUnavailable => 'ما تقدر تسوي هذا الآن.';

  @override
  String get assistantConfirm => 'تأكيد';

  @override
  String get assistantCancel => 'إلغاء';

  @override
  String get assistantReplySettingsTooltip => 'إعدادات الرد';

  @override
  String get assistantReplyModeTitle => 'طريقة رد المساعد';

  @override
  String get assistantReplyModeSubtitle => 'يحكم هذا كل رد، حتى لو سألته بصوتك';

  @override
  String get assistantReplyModeVoice => 'صوت';

  @override
  String get assistantReplyModeText => 'نص مكتوب';

  @override
  String get authLoginSubtitle => 'سجّل دخولك للمتابعة';

  @override
  String get authPhoneLabel => 'رقم الجوال';

  @override
  String get authPasswordLabel => 'كلمة المرور';

  @override
  String get authNoShopYetLabel => 'ليس لديك محل؟';

  @override
  String get authOpenNewShopCta => 'افتح محلاً جديداً';

  @override
  String get authOpenShopTitle => 'فتح محل جديد';

  @override
  String get authSignupSubtitle => 'ثلاث خطوات فقط لفتح محلك';

  @override
  String get authShopNameLabel => 'اسم المحل';

  @override
  String get authOwnerNameLabel => 'اسمك (اختياري)';

  @override
  String get authAlreadyHaveShopCta => 'لديك محل بالفعل؟ سجّل الدخول';

  @override
  String get authOpenShopCta => 'فتح المحل';

  @override
  String get authVerifyPhoneTitle => 'تأكيد رقم الجوال';

  @override
  String authVerifyCodeSentTo(String phone) {
    return 'أرسلنا رمز تحقق إلى $phone';
  }

  @override
  String get authVerifying => 'جارٍ التحقق...';

  @override
  String get authConfirmCta => 'تأكيد';

  @override
  String get authResendCodeCta => 'إعادة إرسال الرمز';

  @override
  String get authSendCodeCta => 'إرسال الرمز';

  @override
  String get authCodeSendFailedFallback => 'تعذّر إرسال الرمز.';

  @override
  String get authOtpIncorrectFallback => 'رمز التحقق غير صحيح.';

  @override
  String get visitCatalogueLoadErrorFallback =>
      'تعذّر تحميل الخدمات. اسحب للأسفل لإعادة المحاولة.';

  @override
  String get visitEnterCustomerPhone => 'أدخل رقم جوال العميل';

  @override
  String get visitSelectAtLeastOneService => 'اختر خدمة واحدة على الأقل';

  @override
  String get visitSavedMessage => 'تم تسجيل الزيارة.';

  @override
  String get visitSaveErrorFallback => 'تعذّر تسجيل الزيارة.';

  @override
  String get visitSaveErrorNetworkFallback =>
      'تعذّر تسجيل الزيارة. تحقق من الاتصال وحاول مرة أخرى.';

  @override
  String get visitTitle => 'تسجيل زيارة';

  @override
  String get visitCustomerSectionTitle => 'العميل';

  @override
  String get visitCustomerPhoneFieldLabel => 'رقم جوال العميل';

  @override
  String get visitPlateFieldLabel => 'رقم اللوحة';

  @override
  String get visitPlateRequired =>
      'أدخل رقم لوحة صحيحاً (حرف ورقم واحد على الأقل)';

  @override
  String visitKnownVehicle(String name) {
    return 'سيارة معروفة: $name';
  }

  @override
  String get visitNewVehicle => 'سيارة جديدة';

  @override
  String visitKnownCustomer(String name) {
    return 'عميل معروف: $name';
  }

  @override
  String get visitNewCustomer => 'عميل جديد';

  @override
  String get visitServicesSectionTitle => 'الخدمات';

  @override
  String get visitNoServicesYet => 'لا توجد خدمات بعد.';

  @override
  String get visitNoteSectionTitle => 'ملاحظة (اختياري)';

  @override
  String get visitSaveButtonLabel => 'حفظ الزيارة';

  @override
  String get navAppsLabel => 'متجر التطبيقات';

  @override
  String get navHomeLabel => 'الرئيسية';

  @override
  String get navAccountLabel => 'حسابي';

  @override
  String get homeGreetingMorning => 'صباح الخير';

  @override
  String get homeGreetingEvening => 'مساء الخير';

  @override
  String homeGreetingMorningNamed(String name) {
    return 'صباح الخير، $name';
  }

  @override
  String homeGreetingEveningNamed(String name) {
    return 'مساء الخير، $name';
  }

  @override
  String get homeAppsSectionTitle => 'تطبيقاتك';

  @override
  String get homeFeaturedStartNow => 'ابدأ الآن';

  @override
  String get homeEmptyStateTitle => 'لا توجد تطبيقات متاحة بعد';

  @override
  String get homeEmptyStateBody => 'تواصل مع صاحب المحل لإضافة صلاحياتك.';

  @override
  String get appsScreenTitle => 'تطبيقاتي';

  @override
  String get appsScreenHint =>
      'اضغط على أيقونة الدبّوس لتثبيت تطبيق بالخانة الخامسة بالشريط السفلي';

  @override
  String get appsPinnedBadge => 'مثبّت بالشريط';

  @override
  String get appsPinAction => 'تثبيت هنا';

  @override
  String get homeLauncherEmptyTitle => 'لا توجد تطبيقات متاحة';

  @override
  String get homeLauncherEmptyMessage =>
      'تواصل مع الدعم لتفعيل تطبيق على محلّك';

  @override
  String get accountScreenTitle => 'حسابي';

  @override
  String get accountPhoneLabel => 'رقم الجوال';

  @override
  String get accountLogoutAction => 'تسجيل الخروج';

  @override
  String get accountLogoutConfirmTitle => 'تسجيل الخروج';

  @override
  String get accountLogoutConfirmMessage => 'هل تريد تسجيل الخروج من حسابك؟';

  @override
  String get notificationsUnavailable => 'الإشعارات غير متاحة بعد';

  @override
  String get notificationsTitle => 'الإشعارات';

  @override
  String get notificationsEmptyState => 'لا توجد إشعارات بعد';

  @override
  String get notificationsAgoJustNow => 'الآن';

  @override
  String notificationsAgoMinutes(int n) {
    return 'قبل $n دقيقة';
  }

  @override
  String notificationsAgoHours(int n) {
    return 'قبل $n ساعة';
  }

  @override
  String get notificationsAgoYesterday => 'أمس';

  @override
  String notificationsAgoDays(int n) {
    return 'قبل $n يوم';
  }

  @override
  String get accountPageTitle => 'حسابي';

  @override
  String get accountLegalSectionTitle => 'قانوني';

  @override
  String get accountTermsRow => 'الشروط والأحكام';

  @override
  String get accountPrivacyRow => 'سياسة الخصوصية';

  @override
  String get accountSignOutRow => 'تسجيل الخروج';

  @override
  String get accountSignOutConfirmTitle => 'تسجيل الخروج؟';

  @override
  String get accountSignOutConfirmBody =>
      'بتحتاج تسجّل الدخول مرة ثانية للمتابعة.';

  @override
  String get accountSignOutCancel => 'إلغاء';

  @override
  String get accountSignOutConfirm => 'تسجيل الخروج';

  @override
  String get accountNameFieldHint => 'اسمك';

  @override
  String get accountSaveNameFailed => 'تعذّر حفظ الاسم، حاول مرة ثانية.';

  @override
  String get accountShopSectionTitle => 'منشأتي';

  @override
  String get accountShopIdentityRow => 'منشأتي';

  @override
  String get shopIdentityPageTitle => 'منشأتي';

  @override
  String get shopIdentityVehicleTitle => 'العمل على السيارات';

  @override
  String get shopIdentityVehicleDesc =>
      'يفعّل حقل رقم اللوحة بشاشة تسجيل الزيارة لهذا المحل.';

  @override
  String get shopIdentityVehicleSaveFailed => 'تعذّر الحفظ، حاول مرة ثانية.';

  @override
  String get shopIdentityBrandTitle => 'اسم محلك وشعاره';

  @override
  String get shopIdentityCustomerPagePreview => 'هذا يظهر لعميلك';

  @override
  String get shopIdentityNameLabel => 'اسم المحل';

  @override
  String get shopIdentityUploadLogo => 'رفع شعار';

  @override
  String get shopIdentityChangeLogo => 'تغيير الشعار';

  @override
  String get shopIdentityRemoveLogo => 'إزالة';

  @override
  String get shopIdentityColorLabel => 'لون محلك';

  @override
  String get shopIdentityResetColor => 'استخدام الافتراضي';

  @override
  String get shopIdentitySave => 'حفظ';

  @override
  String get shopIdentityDefaultName => 'محلك';

  @override
  String get shopIdentityLogoPickFailed =>
      'تعذّر قراءة الصورة، جرّب صورة ثانية.';

  @override
  String get shopIdentityInvalidColor => 'أدخل لوناً صحيحاً، مثل #B08A3E';

  @override
  String get shopIdentitySaveFailed => 'تعذّر الحفظ، حاول مرة ثانية.';

  @override
  String get shopIdentitySaved => 'تم الحفظ.';

  @override
  String get shopIdentityBranchesRow => 'الفروع';

  @override
  String get branchesPageTitle => 'الفروع';

  @override
  String get branchesAddBranch => 'إضافة فرع';

  @override
  String get branchesActiveChip => 'نشط';

  @override
  String get branchesClosedChip => 'مغلق';

  @override
  String get branchesLoadFailed =>
      'تعذّر تحميل الفروع، اسحب للأسفل لإعادة المحاولة.';

  @override
  String get branchesLimitReached => 'باقتك الحالية لا تسمح بإضافة فرع آخر.';

  @override
  String get branchesNameRequired => 'اسم الفرع مطلوب';

  @override
  String get branchesNameLabel => 'اسم الفرع';

  @override
  String get branchesCityLabel => 'المدينة';

  @override
  String get branchesLocationHint =>
      'الصق رابط الموقع من خرائط جوجل (اختياري بالفرع الأول، إلزامي من الفرع الثاني)';

  @override
  String get branchesMapsLinkLabel => 'رابط خرائط جوجل';

  @override
  String get branchesMapsLinkInvalid =>
      'تعذّر قراءة الرابط، تأكد إنه رابط من خرائط جوجل.';

  @override
  String get branchesMapsLinkShort =>
      'الصق الرابط الكامل من خرائط جوجل، لا الرابط المختصر.';

  @override
  String get branchesLocationRequired =>
      'حدّد موقع الفرع على الخريطة — لازم من الفرع الثاني فأكثر.';

  @override
  String get branchesSaveFailed => 'تعذّر الحفظ، حاول مرة ثانية.';

  @override
  String get branchesStatusLabel => 'حالة الفرع';

  @override
  String get branchesMainCannotClose =>
      'الفرع الرئيسي لا يُغلق، يمكنك تغيير اسمه فقط.';

  @override
  String get branchesWhatsappTitle => 'ربط واتساب';

  @override
  String get branchesWhatsappNotStarted => 'لم تبدأ الربط بعد';

  @override
  String get branchesWhatsappConnected => 'مربوط ويعمل';

  @override
  String get branchesWhatsappCannotSend => 'مربوط لكن فيه مشكلة بالإرسال';

  @override
  String get branchesTeamTitle => 'فريق الفرع';

  @override
  String get branchesTeamEmpty => 'لا يوجد أعضاء بهذا الفرع بعد.';

  @override
  String get branchesAddMember => 'إضافة عضو';

  @override
  String get branchesMemberNameLabel => 'اسم الموظف';

  @override
  String get branchesMemberPhoneLabel => 'رقم جواله';

  @override
  String get branchesMemberPasswordLabel => 'كلمة مرور دخوله';

  @override
  String get branchesMemberRoleLabel => 'الصلاحية';

  @override
  String get branchesRoleOperator => 'موظف ميداني';

  @override
  String get branchesRoleSupervisor => 'مشرف وردية';

  @override
  String get branchesRoleMarketer => 'مسؤول التسويق';

  @override
  String get branchesRoleManager => 'مدير';

  @override
  String get branchesSeatLimit => 'باقتك الحالية لا تسمح بإضافة موظف آخر.';

  @override
  String get branchesHireFailed => 'تعذّر إضافة الموظف، حاول مرة ثانية.';

  @override
  String get branchesVisibleAllHint => 'يشوف كل الفروع';

  @override
  String branchesVisibleSomeHint(int count) {
    return 'يشوف $count فروع';
  }

  @override
  String get branchesEditMember => 'تعديل الموظف';

  @override
  String get branchesMemberStopped => 'متوقف';

  @override
  String get branchesMemberStationLabel => 'الفرع اللي يشتغل فيه';

  @override
  String get branchesMemberVisibilityLabel => 'أي فروع يقدر يشوفها';

  @override
  String get branchesVisibilityOwnOnly => 'فرعه بس';

  @override
  String get branchesVisibilitySome => 'فروع محددة';

  @override
  String get branchesVisibilityAll => 'كل الفروع';

  @override
  String get branchesWorkingHours => 'ساعات العمل';

  @override
  String get branchesStopMember => 'إيقاف الموظف';

  @override
  String get branchesStopMemberTitle => 'إيقاف هذا الموظف؟';

  @override
  String branchesStopMemberBody(String name) {
    return 'بيفقد $name القدرة على الدخول للتطبيق فورًا. سجل زياراته وتاريخه يبقى محفوظًا.';
  }

  @override
  String get branchesStopMemberConfirm => 'إيقاف';

  @override
  String get branchesReactivateMember => 'إعادة تفعيل';

  @override
  String get branchesRehireRequired =>
      'هذا الموظف متوقف تمامًا — التفعيل يحتاج توظيفه من جديد، مو مجرد تشغيل.';

  @override
  String get branchesHoursSaved => 'تم حفظ ساعات العمل.';

  @override
  String get branchesHoursExceedsShop =>
      'هذي الساعات أوسع من ساعات عمل المحل نفسه — عدّلها.';

  @override
  String get branchesHoursHint =>
      'لو ما عدّلت شي، يشتغل بنفس ساعات المحل تلقائيًا.';

  @override
  String get branchesHoursClear => 'رجّعه لساعات المحل الافتراضية';

  @override
  String get branchesDayMonday => 'الاثنين';

  @override
  String get branchesDayTuesday => 'الثلاثاء';

  @override
  String get branchesDayWednesday => 'الأربعاء';

  @override
  String get branchesDayThursday => 'الخميس';

  @override
  String get branchesDayFriday => 'الجمعة';

  @override
  String get branchesDaySaturday => 'السبت';

  @override
  String get branchesDaySunday => 'الأحد';

  @override
  String get branchesDayClosed => 'مغلق';

  @override
  String get accountLanguageSectionTitle => 'اللغة';

  @override
  String get accountLanguageRow => 'لغة التطبيق';

  @override
  String get accountLanguageSheetTitle => 'اختر لغة التطبيق';

  @override
  String get accountSecuritySectionTitle => 'الأمان';

  @override
  String get accountChangePasswordRow => 'تغيير كلمة المرور';

  @override
  String get accountChangePasswordFailed =>
      'تعذّر تغيير كلمة المرور، حاول مرة ثانية.';

  @override
  String get accountChangePasswordSuccess => 'تم تغيير كلمة المرور.';

  @override
  String get accountCurrentPasswordLabel => 'كلمة المرور الحالية';

  @override
  String get accountNewPasswordLabel => 'كلمة المرور الجديدة';

  @override
  String get accountConfirmNewPasswordLabel => 'تأكيد كلمة المرور الجديدة';

  @override
  String get branchesIncreaseCapacity => 'زيادة السعة';

  @override
  String get accountBillingSectionTitle => 'الفوترة';

  @override
  String get accountBillingRow => 'الاشتراك والفواتير';

  @override
  String get billingPageTitle => 'الفوترة';

  @override
  String get billingLoadFailed =>
      'تعذّر تحميل بيانات الفوترة، اسحب للأسفل للمحاولة.';

  @override
  String get billingAllGood => 'فوترتك بحالة جيدة، لا شيء يحتاج انتباهك الآن.';

  @override
  String get billingPastDue =>
      'عندك فاتورة متأخرة السداد — سدّدها لتفادي إيقاف خدماتك.';

  @override
  String get billingPaymentConfirming =>
      'استلمنا محاولة دفعك ونتأكد منها الآن — قد يستغرق هذا حتى 20 دقيقة.';

  @override
  String get billingUsageSectionTitle => 'استخدامك';

  @override
  String get billingUsageStaffSeats => 'مقاعد الموظفين';

  @override
  String get billingUsageBranches => 'الفروع';

  @override
  String get billingUsageUnlimited => 'غير محدود';

  @override
  String get billingMyAppsSectionTitle => 'تطبيقاتي المشتركة';

  @override
  String get billingStatusActive => 'نشط';

  @override
  String get billingStatusStopping => 'سيتوقف التجديد';

  @override
  String billingRenewsOn(Object date) {
    return 'يتجدد في $date';
  }

  @override
  String get billingStopRenewal => 'إيقاف التجديد';

  @override
  String get billingUndoStopRenewal => 'تراجع عن الإيقاف';

  @override
  String get billingRenewNow => 'جدّد الآن';

  @override
  String get billingActionFailed => 'تعذّر تنفيذ الطلب، حاول مرة أخرى.';

  @override
  String get billingRenewalPreviewSectionTitle => 'معاينة التجديد القادم';

  @override
  String billingRenewalPreviewNextChargeOn(Object date) {
    return 'أقرب خصم في $date';
  }

  @override
  String get billingRenewalPreviewNoDate => 'لا يوجد تاريخ تجديد قادم بعد.';

  @override
  String get billingRenewalPreviewSubtotal => 'المجموع الفرعي';

  @override
  String get billingRenewalPreviewSavings => 'التوفير';

  @override
  String get billingRenewalPreviewTax => 'الضريبة';

  @override
  String get billingRenewalPreviewTotal => 'الإجمالي';

  @override
  String get billingInvoicesSectionTitle => 'الفواتير';

  @override
  String get billingInvoicesEmpty => 'لا توجد فواتير بعد.';

  @override
  String get billingInvoiceStatusPaid => 'مسدّدة';

  @override
  String get billingInvoiceStatusOpen => 'غير مسدّدة';

  @override
  String get billingInvoiceStatusPartiallyPaid => 'مسدّدة جزئيًا';

  @override
  String get billingInvoiceStatusVoid => 'ملغاة';

  @override
  String get billingInvoiceStatusUncollectible => 'غير قابلة للتحصيل';

  @override
  String get billingInvoiceStatusDraft => 'مسودة';

  @override
  String get billingPayNow => 'ادفع الآن';

  @override
  String get billingPayLinkFailed => 'تعذّر إنشاء رابط الدفع، حاول مرة أخرى.';

  @override
  String get paymentPageLoadFailed =>
      'تعذّر تحميل صفحة الدفع. تحقق من اتصالك ثم أعد المحاولة.';

  @override
  String get billingCancelConfirmTitle => 'إيقاف التجديد؟';

  @override
  String get billingCancelConfirmBody =>
      'ستستمر الخدمة حتى نهاية الفترة الحالية، ثم لن تتجدد.';

  @override
  String get billingCancelConfirmAction => 'إيقاف التجديد';

  @override
  String get visitOfferApplyLabel => 'طبّق هذا العرض على هذي الزيارة';

  @override
  String visitPointsRedeemCost(Object cost) {
    return '$cost نقطة';
  }

  @override
  String get visitPointsOneBenefitOnly =>
      'فائدة واحدة لكل زيارة — اختيار النقاط يلغي العرض التلقائي.';

  @override
  String visitPointsRedeemedMessage(Object name) {
    return 'تم استبدال $name ✓';
  }

  @override
  String visitPointsChosenMessage(Object name) {
    return 'اخترت: $name — سيُستخدم بدل العرض عند الحفظ';
  }

  @override
  String get visitPointsRedeemFailed => 'تعذّر الاستبدال، حاول مرة ثانية.';

  @override
  String readBillingActiveCount(Object count) {
    return 'عندك $count اشتراك نشط.';
  }

  @override
  String get readBillingNone => 'ما عندك أي اشتراك نشط حاليًا.';

  @override
  String readBillingRenewsSoon(Object date) {
    return 'أقرب تجديد يوم $date.';
  }

  @override
  String get readBillingFailed =>
      'تعذّر جلب حالة الفوترة الآن، حاول مرة ثانية.';

  @override
  String readBranchCount(Object count) {
    return 'عندك $count فرع.';
  }

  @override
  String get readBranchFailed => 'تعذّر جلب عدد الفروع الآن، حاول مرة ثانية.';

  @override
  String get readVehicleTrackingOn => 'العمل على السيارات مفعّل الآن.';

  @override
  String get readVehicleTrackingOff => 'العمل على السيارات غير مفعّل حاليًا.';

  @override
  String get readVehicleTrackingFailed =>
      'تعذّر التأكد من حالة تتبع السيارات الآن، حاول مرة ثانية.';

  @override
  String get writeVehicleTrackingEnabledConfirm =>
      'بيفعّل خانة رقم اللوحة بشاشة تسجيل الزيارة لهذا المحل. تأكيد؟';

  @override
  String get writeVehicleTrackingDisabledConfirm =>
      'بيوقف خانة رقم اللوحة بشاشة تسجيل الزيارة لهذا المحل. تأكيد؟';

  @override
  String get writeVehicleTrackingEnabledDone => 'تم تفعيل العمل على السيارات ✓';

  @override
  String get writeVehicleTrackingDisabledDone =>
      'تم إيقاف العمل على السيارات ✓';

  @override
  String get writeVehicleTrackingFailed =>
      'تعذّر تغيير إعداد تتبع السيارات، حاول مرة ثانية.';

  @override
  String get mobileRequestsTitle => 'خدمات متنقلة';

  @override
  String get mobileRequestsSubtitle =>
      'طلبات خدمة تصل للعميل، من الاستلام للتنفيذ.';

  @override
  String get mobileRequestsKpiPending => 'بانتظار قرار';

  @override
  String get mobileRequestsKpiNeedsDecision => 'تحتاج قرار';

  @override
  String get mobileRequestsKpiCompletedMonth => 'تمّت هذا الشهر';

  @override
  String get mobileRequestsBannerGo => 'عرضها';

  @override
  String get mobileRequestsFilterAll => 'الكل';

  @override
  String get mobileRequestsFilterPending => 'بانتظار قرار';

  @override
  String get mobileRequestsFilterAccepted => 'مقبولة';

  @override
  String get mobileRequestsFilterNeedsDecision => 'تحتاج قرار';

  @override
  String get mobileRequestsFilterCompleted => 'تمّت';

  @override
  String get mobileRequestsFilterClosed => 'مغلقة';

  @override
  String get mobileRequestsSearchHint => 'ابحث بالاسم أو الجوال';

  @override
  String get mobileRequestsLoadFailedTitle => 'تعذّر تحميل الطلبات';

  @override
  String get mobileRequestsLoadFailedBody => 'تحقّق من اتصالك وحاول مرة أخرى.';

  @override
  String get mobileRequestsRetry => 'إعادة المحاولة';

  @override
  String get mobileRequestsEmptyTitle => 'لا طلبات بعد';

  @override
  String get mobileRequestsEmptyBody =>
      'طلبات الخدمة المتنقلة من عملائك تظهر هنا.';

  @override
  String get mobileRequestsStatusPending => 'بانتظار قرار';

  @override
  String get mobileRequestsStatusAccepted => 'مقبول';

  @override
  String get mobileRequestsStatusNeedsDecision => 'تحتاج قرار';

  @override
  String get mobileRequestsStatusCompleted => 'تمّ';

  @override
  String get mobileRequestsStatusNoShow => 'لم يحضر';

  @override
  String get mobileRequestsStatusRejected => 'مرفوض';

  @override
  String get mobileRequestsUnnamed => 'بدون اسم';

  @override
  String get mobileRequestsOpenMap => 'الموقع';

  @override
  String get mobileRequestsPhoneCopied => 'تم نسخ رقم الجوال';

  @override
  String get mobileRequestsRiskyCustomer => 'عميل عالي خطر عدم الحضور';

  @override
  String mobileRequestsRejectReasonLine(Object reason) {
    return 'سبب الرفض: $reason';
  }

  @override
  String get mobileRequestsActionAccept => 'قبول';

  @override
  String get mobileRequestsActionReject => 'رفض';

  @override
  String get mobileRequestsActionComplete => 'تمّ';

  @override
  String get mobileRequestsActionNoShow => 'لم يحضر';

  @override
  String get mobileRequestsAssignUnassigned => 'غير مُسنَد';

  @override
  String get mobileRequestsActionFailed =>
      'تعذّر تنفيذ الإجراء، حاول مرة أخرى.';

  @override
  String get mobileRequestsRejectTitle => 'سبب الرفض';

  @override
  String get mobileRequestsRejectHint => 'اختياري';

  @override
  String get mobileRequestsRejectCancel => 'إلغاء';

  @override
  String get mobileRequestsRejectConfirm => 'رفض الطلب';

  @override
  String get mobileRequestsAddOpen => 'إضافة طلب';

  @override
  String get mobileRequestsAddTitle => 'إضافة طلب خدمة متنقلة';

  @override
  String get mobileRequestsAddPhoneLabel => 'جوال العميل';

  @override
  String get mobileRequestsAddNameLabel => 'اسم العميل (اختياري)';

  @override
  String get mobileRequestsAddServicesLabel => 'الخدمات';

  @override
  String get mobileRequestsAddServicesEmpty => 'لا خدمات متاحة بعد.';

  @override
  String get mobileRequestsAddDayLabel => 'اليوم';

  @override
  String get mobileRequestsAddTimeLabel => 'الوقت';

  @override
  String get mobileRequestsAddMapsLinkLabel => 'رابط الموقع من خرائط جوجل';

  @override
  String get mobileRequestsAddMapsLinkHint =>
      'يقبل الرابط الكامل أو المختصر من خرائط جوجل.';

  @override
  String get mobileRequestsAddMapsLinkShort =>
      'هذا رابط مختصر — الصق الرابط الكامل من خرائط جوجل.';

  @override
  String get mobileRequestsAddMapsLinkInvalid =>
      'تعذّر قراءة موقع من هذا الرابط.';

  @override
  String get mobileRequestsAddAssignLabel => 'إسناد إلى (اختياري)';

  @override
  String get mobileRequestsAddCancel => 'إلغاء';

  @override
  String get mobileRequestsAddSubmit => 'إضافة الطلب';

  @override
  String get mobileRequestsAddSubmitting => 'جارٍ الإضافة...';

  @override
  String get mobileRequestsAddError => 'تعذّرت إضافة الطلب، حاول مرة أخرى.';

  @override
  String mobileRequestsBannerText(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count طلبات تحتاج قرارك الآن',
      one: 'طلب واحد يحتاج قرارك الآن',
    );
    return '$_temp0';
  }

  @override
  String get mobileRequestsAddMapsLinkResolving =>
      'جارٍ قراءة الموقع من الرابط...';

  @override
  String get customersTitle => 'جهات الاتصال';

  @override
  String get customersAddOpen => 'إضافة عميل';

  @override
  String get customersSearchHint => 'ابحث بالاسم أو الجوال';

  @override
  String get customersTabAll => 'الكل';

  @override
  String get customersTabOverdue => 'من تأخّر';

  @override
  String get customersSearchFailedTitle => 'تعذّر البحث الآن';

  @override
  String get customersSearchFailedBody => 'حاول مرة أخرى بعد قليل.';

  @override
  String get customersSearchEmpty => 'لا نتائج';

  @override
  String get customersLoadFailedTitle => 'تعذّر التحميل';

  @override
  String get customersEmptyTitle => 'لا عملاء بعد';

  @override
  String get customersOverdueEmpty => 'لا أحد متأخر حالياً';

  @override
  String get customersUnnamed => 'بلا اسم';

  @override
  String customersVisitCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count زيارة',
      two: 'زيارتان',
      one: 'زيارة واحدة',
    );
    return '$_temp0';
  }

  @override
  String get customersOverdueBadge => 'متأخر';

  @override
  String customersStatEveryDays(int days) {
    String _temp0 = intl.Intl.pluralLogic(
      days,
      locale: localeName,
      other: 'كل $days يوم',
      two: 'كل يومين',
      one: 'كل يوم',
    );
    return '$_temp0';
  }

  @override
  String customersOverdueBanner(int every, int since) {
    return 'متأخر عن موعده المعتاد — عادة يزور كل $every يوم، ومضى $since يوم منذ آخر زيارة';
  }

  @override
  String customersVisitMeter(int n) {
    return 'قراءة العدّاد: $n';
  }

  @override
  String get customersOfferExpiredBadge => 'منتهي';

  @override
  String get customersDeniedAllTitle => 'لا تملك صلاحية عرض قائمة العملاء';

  @override
  String get customersDeniedOverdueTitle => 'لا تملك صلاحية عرض من تأخّر';

  @override
  String get customersDeniedDesc => 'اطلب من مالك المحل يمنحك هذي الصلاحية.';

  @override
  String get customersAddTitle => 'إضافة عميل جديد';

  @override
  String get customersAddPhoneLabel => 'جوال العميل';

  @override
  String get customersAddNameLabel => 'اسم العميل';

  @override
  String get customersAddPhoneInvalid => 'رقم الجوال غير صحيح.';

  @override
  String get customersAddFailed => 'تعذّرت إضافة العميل، حاول مرة أخرى.';

  @override
  String get customersAddSubmitting => 'جارٍ الإضافة...';

  @override
  String get customersAddSubmit => 'إضافة';

  @override
  String get customersActionFailed => 'تعذّر تنفيذ الإجراء، حاول مرة أخرى.';

  @override
  String get customersRepeatedIssuesTitle => 'شكاوى متكررة';

  @override
  String get customersVehiclesTitle => 'المركبات';

  @override
  String get customersLoyaltyTitle => 'الولاء';

  @override
  String get customersLoyaltyLoading => 'جارٍ التحميل...';

  @override
  String customersLoyaltyPoints(int count) {
    return '$count نقطة';
  }

  @override
  String get customersLoyaltyAdjust => 'تعديل';

  @override
  String get customersOffersTitle => 'العروض السارية';

  @override
  String customersOfferExpires(String date) {
    return 'ينتهي $date';
  }

  @override
  String get customersVisitsTitle => 'سجل الزيارات';

  @override
  String get customersVisitsEmpty => 'لا زيارات بعد';

  @override
  String get customersVisitNoServices => 'بدون خدمات مسجّلة';

  @override
  String get customersRenameTitle => 'تعديل اسم العميل';

  @override
  String get customersRenameSubmit => 'حفظ';

  @override
  String get customersLoyaltyAdjustTitle => 'تعديل نقاط الولاء';

  @override
  String get customersLoyaltyAdjustNoteLabel => 'سبب التعديل';

  @override
  String get customersLoyaltyAdjustNoteRequired =>
      'اكتب سبباً حقيقياً (3 أحرف على الأقل)، واختر عدداً غير صفر.';

  @override
  String get customersLoyaltyAdjustSubmit => 'حفظ التعديل';

  @override
  String get customersEraseButton => 'حذف بيانات هذا العميل';

  @override
  String get customersEraseTitle => 'حذف بيانات العميل';

  @override
  String get customersEraseWarning =>
      'هذا حذف نهائي لكل بيانات العميل من المنصة، ولا يمكن التراجع عنه.';

  @override
  String customersEraseTypeNameLabel(String name) {
    return 'للتأكيد، اكتب اسم العميل: $name';
  }

  @override
  String get customersEraseConfirm => 'حذف نهائي';

  @override
  String get customersBookingsTitle => 'الحجوزات';

  @override
  String customersAttendanceRate(int rate) {
    return '$rate٪ حضور';
  }

  @override
  String get customersBookingsNoneUpcoming => 'لا حجوزات قادمة';

  @override
  String get customersCyclesTitle => 'دورات التذكير';

  @override
  String customersCyclesEveryDays(int days) {
    return 'كل $days يوم';
  }

  @override
  String get customersCyclesEditHint =>
      'اضبط الفترة، وسيتوقف التعلّم التلقائي لهذه الخدمة مع هذا العميل.';

  @override
  String get customersCyclesSave => 'حفظ';

  @override
  String get customersLogTitle => 'سجل الرسائل';

  @override
  String get customersLogEmpty => 'لم نرسل له شيئاً بعد';

  @override
  String get customersLogOutcomeSent => 'أُرسلت';

  @override
  String get customersLogOutcomeSuppressed => 'لم تُرسل';

  @override
  String get customersTemplateVisitConfirmation => 'تأكيد زيارة';

  @override
  String get customersTemplateVisitConfirmationRating =>
      'طلب تقييم بعد الزيارة';

  @override
  String get customersTemplateBookingConfirmation => 'تأكيد حجز';

  @override
  String get customersTemplateVisitRedeemed => 'إشعار استبدال مكافأة';

  @override
  String get customersTemplateServiceReminder => 'تذكير بموعد الخدمة';

  @override
  String get customersTemplateFollowUp => 'متابعة بعد الزيارة';

  @override
  String get customersTemplateAccountNotice => 'إشعار بخصوص حسابه';

  @override
  String get customersTemplatePointsExpiring => 'تنبيه انتهاء نقاط';

  @override
  String get customersTemplateLoyaltyActivation => 'تفعيل برنامج الولاء';

  @override
  String get customersTemplateWinback => 'استرجاع عميل غائب';

  @override
  String get customersTemplatePersonalOccasion => 'تهنئة بمناسبة';

  @override
  String customersShowAll(int count) {
    return 'عرض الكل ($count)';
  }

  @override
  String get customersCyclesUnknownService => 'خدمة غير معروفة';

  @override
  String customersVisitGapDays(int days) {
    String _temp0 = intl.Intl.pluralLogic(
      days,
      locale: localeName,
      other: 'بعد $days يوم',
      two: 'بعد يومين',
      one: 'بعد يوم واحد',
      zero: 'بنفس اليوم',
    );
    return '$_temp0';
  }

  @override
  String customersCountLabel(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count عميل',
      two: 'عميلان',
      one: 'عميل واحد',
      zero: 'لا عملاء بعد',
    );
    return '$_temp0';
  }

  @override
  String get ratingTitle => 'التقييم';

  @override
  String get pointsTitle => 'نقاط الولاء';

  @override
  String get pointsAddReward => 'مكافأة جديدة';

  @override
  String get pointsEditReward => 'تعديل المكافأة';

  @override
  String get pointsTabRewards => 'المكافآت';

  @override
  String get pointsTabLeaderboard => 'الأكثر طلبًا';

  @override
  String get pointsOutstandingHint => 'نقطة لسه بذمة المحل لعملائه';

  @override
  String pointsRedemptionsCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count استبدال',
      two: 'استبدالان',
      one: 'استبدال واحد',
    );
    return '$_temp0';
  }

  @override
  String pointsCustomersCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count عميل استبدل',
      two: 'عميلان استبدلا',
      one: 'عميل واحد استبدل',
    );
    return '$_temp0';
  }

  @override
  String pointsExpiredWarning(int percent) {
    return '%$percent من النقاط الممنوحة انتهت بلا استبدال — راجع أسعار مكافآتك';
  }

  @override
  String get pointsLoadFailedTitle => 'تعذّر تحميل المكافآت';

  @override
  String get pointsRewardsEmpty => 'لا مكافآت بعد — أضف أول مكافأة لعملائك';

  @override
  String get pointsLeaderboardEmpty =>
      'لا استبدالات بعد — بتظهر هنا أول ما عميل يستبدل مكافأة';

  @override
  String get pointsLeaderboardTitle => 'الأعلى طلبًا';

  @override
  String get pointsLeaderboardHint => 'أكثر خمس مكافآت استبدلها عملاؤك';

  @override
  String pointsTimesRedeemed(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count مرة',
      two: 'مرتان',
      one: 'مرة واحدة',
    );
    return '$_temp0';
  }

  @override
  String get pointsRewardRetired => 'متوقفة';

  @override
  String pointsRewardServiceHint(String name) {
    return 'خدمة: $name';
  }

  @override
  String pointsRewardDiscountHint(String amount) {
    return 'خصم $amount ريال';
  }

  @override
  String get pointsRewardItemHint => 'هدية غير مرتبطة بالكتالوج';

  @override
  String get pointsRewardNameLabel => 'اسم المكافأة';

  @override
  String get pointsRewardTypeLabel => 'نوع المكافأة';

  @override
  String get pointsTypeService => 'خدمة من كتالوجك';

  @override
  String get pointsTypeItem => 'هدية';

  @override
  String get pointsTypeDiscount => 'خصم مبلغ';

  @override
  String get pointsRewardServiceLabel => 'أي خدمة';

  @override
  String get pointsRewardDiscountLabel => 'قيمة الخصم بالريال';

  @override
  String get pointsRewardCostLabel => 'ثمنها بالنقاط';

  @override
  String get pointsRewardActiveLabel => 'فعّالة ويقدر العملاء يستبدلونها';

  @override
  String get pointsRewardInvalid => 'اكتب اسم ونقاط صحيحة أكبر من صفر';

  @override
  String get pointsSaveFailed => 'تعذّر الحفظ، حاول مرة ثانية';

  @override
  String get pointsModeTitle => 'طريقة الاحتساب';

  @override
  String get pointsModeHint =>
      'بالخدمات: كل خدمة نقاطها. بقيمة الفاتورة: نقطة لكل ريال.';

  @override
  String get pointsModeServices => 'بالخدمات';

  @override
  String get pointsModeInvoice => 'بقيمة الفاتورة';

  @override
  String get pointsModeNeedsPricedServices =>
      'الاحتساب بقيمة الفاتورة يحتاج كل خدماتك مسعّرة أولاً — سعّرها كلها بخدماتي ومنتجاتي ثم فعّله.';

  @override
  String get pointsOpenEarnSettings => 'إعدادات نقاط كل خدمة';

  @override
  String get ratingLeaderboardTitle => 'الأعلى تقييماً';

  @override
  String get ratingCardNoName => 'بلا اسم';

  @override
  String get ratingMetricVisits => 'الأكثر زيارات';

  @override
  String get ratingMetricRatings => 'الأكثر تقييمات';

  @override
  String get ratingMetricAvg => 'الأعلى تقييماً';

  @override
  String ratingStaffCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count موظف',
      two: 'موظفان',
      one: 'موظف واحد',
    );
    return '$_temp0';
  }

  @override
  String get ratingTableTitle => 'كل موظف';

  @override
  String ratingTableVisitsValue(int n) {
    return '$n زيارة';
  }

  @override
  String ratingTableRatingsValue(int n) {
    return '$n تقييم';
  }

  @override
  String ratingTableEngagementValue(int n) {
    return 'تفاعل %$n';
  }

  @override
  String ratingTableNoShowValue(int n) {
    return 'لم يحضر %$n';
  }

  @override
  String get ratingPeriodWeek => 'أسبوع';

  @override
  String get ratingPeriodMonth => 'شهر';

  @override
  String get ratingPeriodQuarter => 'ربع سنة';

  @override
  String get ratingPeriodCustom => 'مخصّص';

  @override
  String ratingCustomSince(String date) {
    return 'من: $date';
  }

  @override
  String ratingCustomUntil(String date) {
    return 'إلى: $date';
  }

  @override
  String get ratingCustomRangeInvalid =>
      'المدى غير صالح — تأكد إن تاريخ البداية قبل النهاية';

  @override
  String get ratingExportLocaleLabel => 'لغة التقرير';

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
  String get ratingTopIssuesTitle => 'أكثر المشاكل تكراراً';

  @override
  String get ratingFilterUnhandled => 'بانتظار المعالجة';

  @override
  String get ratingFilterAll => 'الكل';

  @override
  String get ratingFilterHandled => 'معالَجة';

  @override
  String get ratingStarsAll => 'كل النجوم';

  @override
  String get ratingLoadFailedTitle => 'تعذّر تحميل التقييمات';

  @override
  String get ratingEmptyTitle => 'لا تقييمات بعد';

  @override
  String get ratingLoadMore => 'عرض المزيد';

  @override
  String get ratingHandledPlain => 'تمّت معالجته';

  @override
  String get ratingMarkHandled => 'تمّت المعالجة';

  @override
  String get ratingMarkHandledHint =>
      'يُسجَّل هذا نهائياً — لا يمكن التراجع عنه لاحقاً.';

  @override
  String get ratingHandledNoteLabel => 'ملاحظة (اختياري)';

  @override
  String get ratingMarkHandledConfirm => 'تأكيد المعالجة';

  @override
  String get ratingActionFailed => 'تعذّر تنفيذ الإجراء، حاول مرة أخرى.';

  @override
  String ratingWeightedAvgHint(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'من $count تقييم آخر 30 يوم',
      one: 'من تقييم واحد آخر 30 يوم',
      zero: 'لا تقييمات بعد آخر 30 يوم',
    );
    return '$_temp0';
  }

  @override
  String ratingUnhandledCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count تقييم بانتظار المعالجة',
      two: 'تقييمان بانتظار المعالجة',
      one: 'تقييم واحد بانتظار المعالجة',
    );
    return '$_temp0';
  }

  @override
  String ratingVisitsShort(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count زيارة',
      two: 'زيارتان',
      one: 'زيارة واحدة',
    );
    return '$_temp0';
  }

  @override
  String ratingIssueFilterLabel(String label) {
    return 'المشكلة: $label';
  }

  @override
  String ratingByOperator(String name) {
    return 'خدمه $name';
  }

  @override
  String ratingHandledWithNote(String note) {
    return 'تمّت المعالجة: $note';
  }

  @override
  String get ratingQuadrantTitle => 'رباعية الأداء';

  @override
  String get ratingQuadrantHint =>
      'الجودة مقابل معدل التفاعل — اضغط على أي نقطة لسجل تدريب الموظف.';

  @override
  String get ratingQuadrantStars => 'نجوم';

  @override
  String get ratingQuadrantUnderused => 'غير مُستغَل';

  @override
  String get ratingQuadrantNeedsCoaching => 'يحتاج تدريب';

  @override
  String get ratingQuadrantAtRisk => 'يحتاج متابعة';

  @override
  String get ratingTrainingTitle => 'سجل التدريب';

  @override
  String get ratingTrainingNoAccess => 'ما عندك صلاحية عرض هذا.';

  @override
  String get ratingTrainingClean => 'سجل نظيف — ما فيه ملاحظات متكررة.';

  @override
  String ratingEngagementPercent(int percent) {
    return '$percent٪ تفاعل';
  }

  @override
  String get ratingTabOverview => 'نظرة عامة';

  @override
  String get ratingTabFeed => 'كل التقييمات';

  @override
  String get ratingOverviewEmpty => 'لا بيانات أداء بعد آخر 30 يوم.';

  @override
  String get ratingExportTitle => 'تصدير التقرير';

  @override
  String get ratingExportHint =>
      'تقرير أداء الفريق للمدة المختارة، جاهز للمشاركة.';

  @override
  String get ratingExportFailed => 'تعذّر تصدير التقرير، حاول مرة أخرى.';

  @override
  String get customersPrivacyRequestsTitle => 'طلبات حماية البيانات';

  @override
  String get customersPrivacyRequestErase => 'طلب حذف بيانات';

  @override
  String get customersPrivacyRequestCopy => 'طلب نسخة من البيانات';

  @override
  String customersPrivacyRequestGeneric(String type) {
    return 'طلب: $type';
  }

  @override
  String get customersPrivacyRequestClose => 'إغلاق';

  @override
  String get customersLoyaltyHistoryTitle => 'سجل نقاط الولاء';

  @override
  String get customersLoyaltyHistoryNoReason => 'بدون سبب مذكور';

  @override
  String get customersLoyaltyReasonRedeem => 'استبدال مكافأة';

  @override
  String get customersLoyaltyReasonAdjust => 'تعديل يدوي';

  @override
  String get customersLoyaltyReasonEarn => 'نقاط من زيارة';

  @override
  String get customersLoyaltyReasonExpire => 'انتهت صلاحيتها';

  @override
  String get readCustomersFailed =>
      'تعذّر جلب بيانات العملاء الآن، حاول مرة ثانية.';

  @override
  String readCustomersTotal(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'عندك $count عميل مسجّل.',
      one: 'عندك عميل واحد مسجّل.',
      zero: 'ما عندك أي عميل مسجّل بعد.',
    );
    return '$_temp0';
  }

  @override
  String readCustomersOverdueCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'عندك $count عميل متأخر عن دورتهم.',
      one: 'عندك عميل واحد متأخر عن دورته.',
      zero: 'ما فيه عميل متأخر عن دورته حالياً.',
    );
    return '$_temp0';
  }

  @override
  String get readMobileRequestsFailed =>
      'تعذّر جلب طلبات الخدمة المتنقلة الآن، حاول مرة ثانية.';

  @override
  String readMobileRequestsPendingCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'عندك $count طلب بانتظار قرار.',
      one: 'عندك طلب واحد بانتظار قرار.',
      zero: 'ما فيه طلبات خدمة متنقلة بانتظار قرار.',
    );
    return '$_temp0';
  }

  @override
  String readMobileRequestsNeedsDecisionCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'عندك $count طلبات تحتاج قرارك الآن.',
      one: 'عندك طلب واحد يحتاج قرارك الآن.',
      zero: 'ما فيه طلبات متنقلة تحتاج قرارك الآن.',
    );
    return '$_temp0';
  }

  @override
  String get readRatingFailed =>
      'تعذّر جلب بيانات التقييم الآن، حاول مرة ثانية.';

  @override
  String get readRatingNone => 'ما عندك تقييمات آخر 30 يوم بعد.';

  @override
  String readRatingAverage(String avg, int count) {
    return 'متوسط تقييمك آخر 30 يوم $avg من 5، من $count تقييم.';
  }

  @override
  String readRatingUnhandledCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'عندك $count تقييم بانتظار المعالجة.',
      one: 'عندك تقييم واحد بانتظار المعالجة.',
      zero: 'ما فيه تقييمات بانتظار المعالجة.',
    );
    return '$_temp0';
  }

  @override
  String readRatingTopStaff(String name, String avg) {
    return 'أفضل موظف تقييماً آخر 30 يوم هو $name، بمتوسط $avg من 5.';
  }

  @override
  String readMobileRequestsCompletedCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'خلّصت $count طلب هذا الشهر.',
      one: 'خلّصت طلب واحد هذا الشهر.',
      zero: 'ما خلّصت أي طلب متنقل هذا الشهر بعد.',
    );
    return '$_temp0';
  }

  @override
  String readMobileRequestsTodayCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'جاك $count طلب اليوم.',
      one: 'جاك طلب واحد اليوم.',
      zero: 'ما جاك أي طلب خدمة متنقلة اليوم بعد.',
    );
    return '$_temp0';
  }

  @override
  String get readOperatorsFailed =>
      'تعذّر جلب عدد الموظفين الآن، حاول مرة ثانية.';

  @override
  String readOperatorsCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'عندك $count موظف بفريقك.',
      one: 'عندك موظف واحد بفريقك.',
      zero: 'ما عندك أي موظف مسجّل بعد.',
    );
    return '$_temp0';
  }

  @override
  String readBranchesDisconnectedCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'عندك $count فروع واتسابها مو شغّال.',
      one: 'عندك فرع واحد واتسابه مو شغّال.',
      zero: 'كل فروعك النشطة واتسابها مربوط ويشتغل.',
    );
    return '$_temp0';
  }

  @override
  String get readCustomersRecentNone => 'ما عندك أي عميل مسجّل بعد.';

  @override
  String readCustomersRecentName(String name) {
    return 'آخر عميل سجّلته هو $name.';
  }

  @override
  String readRatingCriticalIssuesCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'عندك $count تقييمات فيها ملاحظات خطيرة ما رديت عليها.',
      one: 'عندك تقييم واحد فيه ملاحظة خطيرة ما رديت عليه.',
      zero: 'ما فيه تقييمات فيها ملاحظة خطيرة ما رديت عليها.',
    );
    return '$_temp0';
  }

  @override
  String get readPerBranchModeOn => 'أيوه، محلك يشتغل بنظام تعدد الفروع.';

  @override
  String get readPerBranchModeOff => 'لا، محلك يشتغل كفرع واحد فقط.';

  @override
  String get readBillingOverdueYes =>
      'أيوه، عندك فاتورة متأخرة السداد — سدّدها لتفادي إيقاف خدماتك.';

  @override
  String get readBillingOverdueNo =>
      'لا، فوترتك بحالة جيدة، ما فيه فواتير متأخرة.';

  @override
  String get readServicesFailed =>
      'تعذّر جلب عدد الخدمات الآن، حاول مرة ثانية.';

  @override
  String readServicesCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'عندك $count خدمة بقائمتك.',
      one: 'عندك خدمة واحدة بقائمتك.',
      zero: 'ما عندك أي خدمة بقائمتك بعد.',
    );
    return '$_temp0';
  }

  @override
  String readCustomersTodayCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'جاك $count عميل جديد اليوم.',
      one: 'جاك عميل جديد واحد اليوم.',
      zero: 'ما جاك عميل جديد اليوم بعد.',
    );
    return '$_temp0';
  }

  @override
  String readMobileRequestsRejectedCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'رفضت $count طلب هذا الشهر.',
      one: 'رفضت طلب واحد هذا الشهر.',
      zero: 'ما رفضت أي طلب خدمة متنقلة هذا الشهر.',
    );
    return '$_temp0';
  }

  @override
  String readMobileRequestsNoShowCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'عندك $count عملاء ما حضروا هذا الشهر.',
      one: 'عندك عميل واحد ما حضر هذا الشهر.',
      zero: 'ما فيه عميل ما حضر هذا الشهر.',
    );
    return '$_temp0';
  }

  @override
  String readRatingFiveStarCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'عندك $count تقييم خماسي.',
      one: 'عندك تقييم خماسي واحد.',
      zero: 'ما عندك أي تقييم خماسي بعد.',
    );
    return '$_temp0';
  }

  @override
  String readBranchesActiveCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'عندك $count فروع نشطة.',
      one: 'عندك فرع واحد نشط.',
      zero: 'ما عندك أي فرع نشط حالياً.',
    );
    return '$_temp0';
  }

  @override
  String get servicesTitle => 'خدماتي ومنتجاتي';

  @override
  String get servicesUnnamedGlyph => '؟';

  @override
  String get servicesSearchHint => 'ابحث باسم الخدمة';

  @override
  String get servicesTabActive => 'نشطة';

  @override
  String get servicesTabStopped => 'متوقفة';

  @override
  String get servicesLoadFailedTitle => 'تعذّر تحميل الخدمات';

  @override
  String get servicesEmptyActive => 'لا خدمات نشطة بعد';

  @override
  String get servicesEmptyStopped => 'لا خدمات متوقفة';

  @override
  String get servicesAddOpen => 'إضافة خدمة';

  @override
  String get servicesNoPrice => 'بدون سعر';

  @override
  String get servicesNoDuration => 'غير محدّدة';

  @override
  String get servicesNoCycle => 'بدون دورة';

  @override
  String get servicesStopTitle => 'إيقاف الخدمة';

  @override
  String get servicesStopConfirm => 'إيقاف';

  @override
  String get servicesActionFailed => 'تعذّر تنفيذ الإجراء، حاول مرة أخرى.';

  @override
  String get servicesEditTitle => 'تعديل الخدمة';

  @override
  String get servicesAddTitle => 'إضافة خدمة جديدة';

  @override
  String get servicesNameLabel => 'اسم الخدمة';

  @override
  String get servicesPriceLabel => 'السعر (اختياري)';

  @override
  String get servicesDurationLabel => 'المدة بالدقائق (اختياري)';

  @override
  String get servicesCycleLabel => 'دورة التذكير بالأيام (اختياري)';

  @override
  String get servicesDescriptionLabel => 'وصف مختصر (اختياري)';

  @override
  String get servicesSaving => 'جارٍ الحفظ...';

  @override
  String get servicesSave => 'حفظ';

  @override
  String get servicesNameRequired => 'اسم الخدمة مطلوب';

  @override
  String servicesActiveCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'عندك $count خدمة نشطة.',
      one: 'عندك خدمة نشطة واحدة.',
      zero: 'ما عندك أي خدمة نشطة بعد.',
    );
    return '$_temp0';
  }

  @override
  String servicesDurationMinutes(int count) {
    return '$count دقيقة';
  }

  @override
  String servicesCycleDays(int count) {
    return 'كل $count يوم';
  }

  @override
  String servicesStopWarning(String name) {
    return 'بيوقف خدمة «$name» — ما راح تظهر لعميل جديد بتسجيل الزيارة، وتذكيراتها تتوقف. ما تُحذف بياناتها.';
  }

  @override
  String get servicesPhotoPickFailed => 'تعذّر اختيار الصورة';

  @override
  String get servicesPhotoUploadFailed => 'تم الحفظ لكن تعذّر رفع الصورة';

  @override
  String get servicesPhotoLabel => 'صورة الخدمة (اختياري)';

  @override
  String get servicesUploadPhoto => 'رفع صورة';

  @override
  String get servicesChangePhoto => 'تغيير الصورة';

  @override
  String get servicesRemovePhoto => 'إزالة';

  @override
  String get servicesAssignmentLabel => 'من يقدّم هذه الخدمة؟';

  @override
  String get servicesAssignmentAuto => 'أي موظف متاح';

  @override
  String get servicesAssignmentNamed => 'موظفون محدّدون';

  @override
  String get servicesChecklistLabel => 'خطوات الإجراء';

  @override
  String get servicesChecklistEmpty => 'لا خطوات بعد — أضف أول خطوة';

  @override
  String get servicesStepAddTitle => 'إضافة خطوة';

  @override
  String get servicesGeneralSettingsTitle => 'الإعداد العام';

  @override
  String get servicesGeneralSettingsHint =>
      'القيمة التي تتبعها كل خدمة لم تُخصَّص بعد';

  @override
  String get servicesFollowUpLabel => 'أيام المتابعة بعد الزيارة';

  @override
  String get servicesPointsLabel => 'نقاط لكل زيارة';

  @override
  String get servicesGroupThem => 'تجميعها';

  @override
  String get servicesGroupNameHint => 'اسم المجموعة';

  @override
  String get servicesAllGroups => 'الكل';

  @override
  String get servicesStepEditTitle => 'تعديل الخطوة';

  @override
  String get servicesStepCriticalLabel => 'خطوة حرجة';

  @override
  String get servicesStepRetire => 'إيقاف هذه الخطوة';

  @override
  String get servicesStepEditHint =>
      'اضغط مطوّلاً على أي خطوة لتعديلها أو إيقافها';

  @override
  String get servicesAdvancedTitle => 'إعدادات متقدمة';

  @override
  String get servicesAdvancedHint =>
      'تخصيص هذه الخدمة عن الإعداد العام — لدورة التذكير والنقاط والتجميع';

  @override
  String get servicesGroupLabel => 'المجموعة';

  @override
  String get servicesNoGroup => 'بدون مجموعة';

  @override
  String get servicesNewGroup => 'مجموعة جديدة';

  @override
  String get servicesFollowGeneralAction => 'اتّباع العام';

  @override
  String get servicesCustomizeAction => 'تخصيص';

  @override
  String servicesFollowUpDays(int n) {
    return 'متابعة بعد $n يوم';
  }

  @override
  String servicesPointsPerVisit(int n) {
    return '$n نقطة';
  }

  @override
  String servicesSuggestionText(int n) {
    return '$n خدمات تتشارك نفس القيمة — تجميعها في مجموعة واحدة يسهّل تعديلها معاً لاحقاً.';
  }

  @override
  String servicesFollowsGeneral(String hint) {
    return 'يتبع العام — $hint';
  }

  @override
  String get servicesPageTabServices => 'الخدمات';

  @override
  String get servicesPageTabPackages => 'الباقات';

  @override
  String get servicesPackageAdd => 'إضافة باقة';

  @override
  String get servicesPackageNeedsTwoServices =>
      'الباقة تحتاج خدمتين نشطتين على الأقل';

  @override
  String get servicesPackageEmpty => 'لا باقات بعد';

  @override
  String get servicesPackageEditTitle => 'تعديل الباقة';

  @override
  String get servicesPackageAddTitle => 'إضافة باقة جديدة';

  @override
  String get servicesPackageNameLabel => 'اسم الباقة';

  @override
  String get servicesPackagePriceRequired => 'سعر الباقة مطلوب، أكبر من صفر';

  @override
  String get servicesPackageServicesLabel => 'الخدمات المشمولة';

  @override
  String get servicesImportTitle => 'استيراد خدمات من ملف';

  @override
  String get servicesImportHint =>
      'ملف CSV بأعمدة: name, price, duration_minutes, cycle_days, description';

  @override
  String get servicesImportPickFile => 'اختيار ملف CSV';

  @override
  String get servicesImportReadFailed => 'تعذّرت قراءة الملف';

  @override
  String get servicesImportParseFailed =>
      'الملف لا يحتوي عمود name، أو تنسيقه غير صحيح';

  @override
  String get servicesImportDeactivateMissing =>
      'إيقاف الخدمات غير الموجودة بالملف';

  @override
  String get servicesImportDeactivateMissingHint =>
      'أي خدمة عندك حاليًا ولم تظهر بهذا الملف تُوقَف تلقائيًا';

  @override
  String get servicesImportConfirm => 'استيراد';

  @override
  String get servicesImportClose => 'تم';

  @override
  String servicesImportRowCount(int n) {
    String _temp0 = intl.Intl.pluralLogic(
      n,
      locale: localeName,
      other: '$n صف',
      one: 'صف واحد',
      zero: 'لا صفوف',
    );
    return '$_temp0 جاهزة للاستيراد';
  }

  @override
  String servicesImportDone(int created, int updated, int reactivated) {
    return 'أُضيفت $created، وحُدّثت $updated، وأُعيد تفعيل $reactivated.';
  }

  @override
  String get visitPackagesSectionTitle => 'باقات مميّزة';

  @override
  String get visitNameFieldHint => 'اسم العميل (اختياري)';

  @override
  String get visitMeterFieldHint => 'قراءة العدّاد';

  @override
  String get visitQuantityDialogTitle => 'الكمية';

  @override
  String get visitCouponCheckboxLabel => 'منح كوبون خصم لمحل آخر';

  @override
  String get visitCouponPhoneHint => 'جوال صاحب المحل';

  @override
  String get visitClearAllButton => 'مسح الكل';

  @override
  String visitServicesSelectedCount(int n) {
    String _temp0 = intl.Intl.pluralLogic(
      n,
      locale: localeName,
      other: '$n خدمة مختارة',
      one: 'خدمة واحدة مختارة',
    );
    return '$_temp0';
  }

  @override
  String get visitTodayBookingsTitle => 'مواعيد اليوم';

  @override
  String get visitBookingAttendFailed => 'تعذّر تسجيل الحضور، حاول مرة أخرى';

  @override
  String get branchSwitcherChooseBranch => 'اختر الفرع';

  @override
  String get branchSwitcherTitle => 'الفرع الحالي';

  @override
  String get branchSwitcherHint => 'كل ما تفتحه بعدها يخص هذا الفرع';

  @override
  String get proceduresPrintFailed => 'تعذّر إنشاء المستند';

  @override
  String get proceduresTitle => 'الإجراءات';

  @override
  String get proceduresSubtitle =>
      'اضبط قائمة الإجراءات لكل خدمة، أو أدر المكتبة المشتركة كاملة. اضغط مطوّلًا على خدمة لتحديدها للطباعة';

  @override
  String get proceduresLibraryLink => 'مكتبة الإجراءات';

  @override
  String get proceduresPrint => 'طباعة';

  @override
  String get proceduresEmptyTitle => 'لا خدمات نشطة بعد';

  @override
  String get servicesStepSeverityNormal => 'عادي';

  @override
  String get servicesStepSeverityCritical => 'حرج';

  @override
  String get proceduresSaveFailed => 'تعذّر الحفظ';

  @override
  String get proceduresDrawerSubtitle =>
      'رتّب الإجراءات بالسحب، أو أضف إجراءً من المكتبة';

  @override
  String get proceduresDrawerEmpty => 'لا إجراءات لهذه الخدمة بعد';

  @override
  String get proceduresDrawerAddButton => 'إضافة من المكتبة';

  @override
  String get proceduresPickTitle => 'اختيار إجراء';

  @override
  String get proceduresPickClose => 'إغلاق';

  @override
  String get proceduresPickApply => 'إضافة';

  @override
  String get proceduresPickSearch => 'ابحث بالإجراءات';

  @override
  String get proceduresPickEmpty => 'لا نتائج';

  @override
  String get proceduresPickCreatePlaceholder => 'إجراء جديد...';

  @override
  String get proceduresLibrarySaveFailed => 'تعذّر الحفظ';

  @override
  String get proceduresLibraryTitle => 'مكتبة الإجراءات';

  @override
  String get proceduresLibrarySubtitle =>
      'كل إجراء هنا مشترك بين كل الخدمات اللي تستخدمه — تعديله يغيّره بكل مكان';

  @override
  String get proceduresLibraryNewPlaceholder => 'نص الإجراء الجديد';

  @override
  String get proceduresLibraryAdd => 'إضافة';

  @override
  String get proceduresLibraryShowRetired => 'إظهار الملغاة';

  @override
  String get proceduresLibraryEmpty => 'لا إجراءات بعد';

  @override
  String get proceduresLibraryRetired => 'ملغى';

  @override
  String get proceduresLibraryRetire => 'إلغاء';

  @override
  String get proceduresLibraryReactivate => 'إعادة تفعيل';

  @override
  String get proceduresSeverityHint =>
      'الإجراء الحرج يُبرَز للموظف بلون مختلف، ولا يجوز تخطّيه أثناء تنفيذ الخدمة';

  @override
  String proceduresSelectedCount(int n) {
    return '$n محددة';
  }

  @override
  String proceduresStepCount(int n) {
    return '$n إجراء';
  }

  @override
  String proceduresUsedIn(int n) {
    return 'مستخدم بـ$n خدمة';
  }

  @override
  String get mutualBenefitProposeButton => 'اقتراح شراكة';

  @override
  String get mutualBenefitTitle => 'تبادل منافع';

  @override
  String get mutualBenefitSubtitle =>
      'انقل عملاء حقيقيين بينك وبين محلات أخرى، باتفاق متبادل';

  @override
  String get mutualBenefitRoleAll => 'الكل';

  @override
  String get mutualBenefitRoleReferrer => 'كمُحيل';

  @override
  String get mutualBenefitRoleBeneficiary => 'كمستفيد';

  @override
  String get mutualBenefitLoadFailed => 'تعذّر تحميل الشراكات';

  @override
  String get mutualBenefitEmptyTitle => 'لا شراكات بعد';

  @override
  String get mutualBenefitKpiAsReferrer => 'كمُحيل';

  @override
  String get mutualBenefitKpiAsBeneficiary => 'كمستفيد';

  @override
  String get mutualBenefitKpiSent => 'أُحيل';

  @override
  String get mutualBenefitKpiRedeemed => 'استُبدل';

  @override
  String get mutualBenefitKpiRate => 'نسبة الاستبدال';

  @override
  String get mutualBenefitConfirm => 'تأكيد';

  @override
  String get mutualBenefitGrantDiscountBlanket => 'خصم على كامل الزيارة';

  @override
  String get mutualBenefitStatusProposed => 'مقترحة';

  @override
  String get mutualBenefitStatusActive => 'نشطة';

  @override
  String get mutualBenefitStatusPaused => 'متوقفة مؤقتًا';

  @override
  String get mutualBenefitStatusCancelRequested => 'طُلب إنهاؤها';

  @override
  String get mutualBenefitStatusEnded => 'منتهية';

  @override
  String get mutualBenefitStatusRejected => 'مرفوضة';

  @override
  String get mutualBenefitStatusExpiredUnanswered => 'انتهت بلا رد';

  @override
  String get mutualBenefitEventProposed => 'اقتراح الشراكة';

  @override
  String get mutualBenefitEventAccepted => 'قبول الشراكة';

  @override
  String get mutualBenefitEventRejected => 'رفض الشراكة';

  @override
  String get mutualBenefitEventActivated => 'تفعيل الشراكة';

  @override
  String get mutualBenefitEventCancelRequested => 'طلب إنهاء';

  @override
  String get mutualBenefitEventCancelConfirmed => 'تأكيد الإنهاء';

  @override
  String get mutualBenefitEventExpiredUnanswered => 'انتهت المهلة بلا رد';

  @override
  String get mutualBenefitEventPaused => 'إيقاف مؤقت';

  @override
  String get mutualBenefitEventResumed => 'استئناف';

  @override
  String get mutualBenefitEventEndedTerm => 'انتهت المدة';

  @override
  String get mutualBenefitEventGrantCreated => 'منحة جديدة';

  @override
  String get mutualBenefitEventGrantRedeemed => 'استبدال منحة';

  @override
  String get mutualBenefitActivityActive => 'نشطة';

  @override
  String get mutualBenefitActivityPaused => 'متوقفة مؤقتًا';

  @override
  String get mutualBenefitActivityPending => 'بانتظار الرد';

  @override
  String get mutualBenefitActivityInactive => 'غير نشطة';

  @override
  String get mutualBenefitScorecardTitle => 'الأداء';

  @override
  String get mutualBenefitScorecardFailed => 'تعذّر تحميل الأداء';

  @override
  String get mutualBenefitActivityTitle => 'النشاط الأخير';

  @override
  String get mutualBenefitActivityEmpty => 'لا نشاط بعد';

  @override
  String get mutualBenefitAgreementsTitle => 'الاتفاقيات';

  @override
  String get mutualBenefitConfirmCancel => 'تأكيد إنهاء هذه الشراكة نهائيًا؟';

  @override
  String get mutualBenefitActionAccept => 'قبول';

  @override
  String get mutualBenefitActionReject => 'رفض';

  @override
  String get mutualBenefitActionWaitingThem => 'بانتظار الطرف الآخر';

  @override
  String get mutualBenefitActionCancelRequest => 'طلب إنهاء';

  @override
  String get mutualBenefitActionCancelConfirm => 'تأكيد الإنهاء';

  @override
  String get mutualBenefitProposeTitle => 'اقتراح شراكة جديدة';

  @override
  String get mutualBenefitProposePhoneLabel => 'جوال المحل الآخر';

  @override
  String get mutualBenefitProposeConditionLabel => 'شرط الاستحقاق عندك';

  @override
  String get mutualBenefitConditionMinTotal => 'حد أدنى للفاتورة';

  @override
  String get mutualBenefitConditionServiceId => 'خدمة معينة';

  @override
  String get mutualBenefitProposeConditionValueRiyals => 'المبلغ (ريال)';

  @override
  String get mutualBenefitProposeConditionValueService => 'الخدمة';

  @override
  String get mutualBenefitProposeValidityLabel => 'الصلاحية (يوم)';

  @override
  String get mutualBenefitProposeDurationLabel => 'المدة (يوم)';

  @override
  String get mutualBenefitProposeCapLabel => 'الحد كل 30 يوم';

  @override
  String get mutualBenefitProposeGrantTypeLabel => 'نوع المنحة';

  @override
  String get mutualBenefitGrantTypeDiscount => 'خصم';

  @override
  String get mutualBenefitGrantTypeGift => 'هدية';

  @override
  String get mutualBenefitScopeBlanket => 'كامل الزيارة';

  @override
  String get mutualBenefitScopeItem => 'خدمة معينة';

  @override
  String get mutualBenefitScopeGroup => 'مجموعة/باقة';

  @override
  String get mutualBenefitProposeServiceLabel => 'الخدمة';

  @override
  String get mutualBenefitProposeGroupLabel => 'المجموعة';

  @override
  String get mutualBenefitProposeImmutableNote =>
      'شروط المنحة ثابتة بعد الإرسال — أي تغيير يحتاج اتفاقية جديدة';

  @override
  String get mutualBenefitProposeSubmitting => 'جارٍ الإرسال...';

  @override
  String get mutualBenefitProposeSubmit => 'إرسال الاقتراح';

  @override
  String mutualBenefitGrantGift(String name) {
    return 'هدية: $name';
  }

  @override
  String mutualBenefitGrantDiscountItem(String name) {
    return 'خصم على: $name';
  }

  @override
  String mutualBenefitGrantDiscountGroup(String name) {
    return 'خصم على مجموعة: $name';
  }

  @override
  String mutualBenefitPartnerCount(int n) {
    return '$n اتفاقية';
  }

  @override
  String get mutualBenefitProposeResultFail => 'تعذّر إرسال الاقتراح';

  @override
  String get mutualBenefitRefusal402 =>
      'محلك غير مشترك بتطبيق تبادل منافع — اشترك من متجر التطبيقات أولًا';

  @override
  String get mutualBenefitRefusal403 => 'لا تملك صلاحية كافية لهذا الإجراء';

  @override
  String get mutualBenefitRefusal400 =>
      'بيانات الاقتراح غير صحيحة — تأكد من الشرط، أو أنك لا تقترح شراكة على محلك نفسه';

  @override
  String get mutualBenefitRefusal404 =>
      'لم يُعثر على محل بهذا الرقم، أو على الخدمة/المجموعة المختارة بكتالوج الطرف الآخر';

  @override
  String get mutualBenefitRefusal409 =>
      'تجاوزت الحد الأقصى للشراكات النشطة (3)، أو حالة الشراكة تغيّرت';

  @override
  String get mutualBenefitRefusal503 =>
      'خدمة الفوترة غير متاحة حاليًا، حاول لاحقًا';

  @override
  String get appStoreTitle => 'متجر التطبيقات';

  @override
  String get appStoreSubtitle => 'طوّر محلك بتطبيقات حقيقية، واحد واحد';

  @override
  String get appStoreTabMine => 'تطبيقاتي';

  @override
  String get appStoreTabAll => 'متجر التطبيقات';

  @override
  String get appStoreDetails => 'التفاصيل';

  @override
  String get appStorePerMonth => 'شهريًا';

  @override
  String get appStorePerMonthShort => '/شهر';

  @override
  String get appStoreActive => 'نشط';

  @override
  String get appStoreTrialing => 'تجريبي';

  @override
  String get appStoreSubscribe => 'اشترك الآن';

  @override
  String get appStoreCancelRenewal => 'إيقاف التجديد';

  @override
  String get appStoreUndoCancel => 'تراجع عن الإيقاف';

  @override
  String get appStoreConfirmCancel =>
      'هل تريد إيقاف تجديد هذا التطبيق؟ يستمر لين نهاية الفترة المدفوعة';

  @override
  String appStoreCartCount(int n) {
    return '$n بالسلة';
  }

  @override
  String get appStoreCheckout => 'إتمام الشراء';

  @override
  String get appStoreCheckingOut => 'جاري الشراء...';

  @override
  String get appStoreRefusal402 =>
      'الدفع غير مفعّل على حسابك حاليًا — تواصل معنا لتفعيله';

  @override
  String get appStoreRefusal403 => 'لا صلاحية لك لإتمام عملية الشراء هذه';

  @override
  String get appStoreRefusal404 =>
      'لم يُعثر على الباقة المطلوبة — أعد المحاولة بعد تحديث الشاشة';

  @override
  String get appStoreRefusal409 =>
      'هذا التطبيق مملوك مسبقًا أو تغيّرت حالته أثناء الشراء';

  @override
  String get appStoreRefusalGeneric => 'تعذّر إتمام الشراء، حاول مرة أخرى';

  @override
  String get appStoreCapacityTitle => 'السعة';

  @override
  String appStoreCapacityConfirmRemove(String name) {
    return 'هل تريد إزالة آخر وحدة من \"$name\"؟ هذا يوقف تجديده بالكامل';
  }

  @override
  String get appStoreCartSubtotal => 'الإجمالي الفرعي';

  @override
  String get appStoreCartDiscount => 'الخصم';

  @override
  String get appStoreCartTax => 'الضريبة';

  @override
  String get appStoreCartTotal => 'الإجمالي';

  @override
  String get appStoreCartDiscountCaveat =>
      'السعر المعروض قبل الخصم والضريبة؛ المبلغ الفعلي يُحسب ويظهر عند الدفع.';

  @override
  String appStoreCartItemDiscount(int percent) {
    return '(خصم $percent٪)';
  }

  @override
  String appStoreAutoAdded(String added, String trigger) {
    return 'أُضيف \"$added\" تلقائيًا لأن \"$trigger\" يحتاج إليه.';
  }

  @override
  String appStoreMissingRequirement(String names) {
    return 'يحتاج تفعيل $names أولاً.';
  }

  @override
  String get appStoreRequiresAnyVisit => 'تسجيل زيارة';

  @override
  String get appStoreRequiresAnyBookings => 'الحجوزات';

  @override
  String get appStoreRequiresAnyContacts => 'جهات الاتصال';

  @override
  String get appStoreRequiresAnyMobileRequests => 'خدمات متنقلة';

  @override
  String get appStoreRequiresOr => 'أو';

  @override
  String get appStoreOr => 'أو';

  @override
  String appStoreCascadeWarning(String names) {
    return 'سيتوقف معه أيضًا: $names';
  }

  @override
  String appStoreDiscountBadge(int percent) {
    return 'خصم $percent٪ مطبَّق';
  }

  @override
  String appStoreDiscountBadgeWithApp(int percent, String app) {
    return 'خصم $percent٪ مطبَّق من $app';
  }

  @override
  String appStoreDiscountedShort(int percent) {
    return 'خصم $percent٪';
  }

  @override
  String appStoreOfferTitle(int percent) {
    return 'خصم $percent٪ بانتظارك';
  }

  @override
  String appStoreOfferDesc(String app) {
    return 'فعّله تلقائياً باشتراكك في $app';
  }

  @override
  String appStoreAiUnitsCount(int units) {
    return '$units وحدة';
  }

  @override
  String get appStoreAiUnitsIncluded => 'ذكاء اصطناعي مجاناً كل شهر';

  @override
  String get whatsappAssistantTitle => 'المساعد الذكي';

  @override
  String get whatsappAssistantSubtitle =>
      'يرد على عملائك بواتساب نيابة عنك، ويقترح عليهم باقاتك ونقاطهم في الوقت المناسب.';

  @override
  String get whatsappAssistantLoadFailed =>
      'تعذّر تحميل إعدادات المساعد الذكي.';

  @override
  String get whatsappAssistantConfirm => 'تأكيد';

  @override
  String get whatsappAssistantSaveFailed => 'تعذّر الحفظ، حاول مرة أخرى.';

  @override
  String get whatsappAssistantToggleTitle => 'المساعد يرد الآن';

  @override
  String get whatsappAssistantToggleDesc =>
      'إيقافه يقفل المساعد تمامًا، بدون إلغاء اشتراكك — ترجعه متى شئت.';

  @override
  String get whatsappAssistantToggleConfirmEnableTitle =>
      'تشغيل المساعد الذكي؟';

  @override
  String get whatsappAssistantToggleConfirmEnableBody =>
      'بيبدأ يرد على عملائك بواتساب فورًا.';

  @override
  String get whatsappAssistantToggleConfirmDisableTitle =>
      'إيقاف المساعد الذكي؟';

  @override
  String get whatsappAssistantToggleConfirmDisableBody =>
      'بيتوقف عن الرد تمامًا، وكأنك غير مشترك فيه — بدون إلغاء الاشتراك نفسه.';

  @override
  String get whatsappAssistantNotesTitle => 'ملاحظات المحل';

  @override
  String get whatsappAssistantNotesDesc =>
      'ما تكتبه هنا يساعد المساعد الذكي يخدم عملاءك بمعلومات إضافية عن محلك.';

  @override
  String get whatsappAssistantWordLimitTitle => 'حد كلمات رسالة العميل';

  @override
  String get whatsappAssistantWordLimitDesc =>
      'أطول رسالة يقبلها المساعد من العميل قبل ما يطلب منه اختصارها.';

  @override
  String get whatsappAssistantAutoRegisterTitle =>
      'تسجيل جهات الاتصال تلقائيًا';

  @override
  String get whatsappAssistantAutoRegisterDesc =>
      'أي رقم جديد يراسل واتسابك يُسجَّل تلقائيًا كجهة اتصال حقيقية.';

  @override
  String get whatsappAssistantAutoRegisterConfirmEnableTitle =>
      'تفعيل التسجيل التلقائي؟';

  @override
  String get whatsappAssistantAutoRegisterConfirmEnableBody =>
      'كل من يراسل رقمك بواتساب راح يُسجَّل تلقائيًا كجهة اتصال، حتى لو رسالة وحدة.';

  @override
  String get whatsappAssistantAutoRegisterConfirmDisableTitle =>
      'إيقاف التسجيل التلقائي؟';

  @override
  String get whatsappAssistantAutoRegisterConfirmDisableBody =>
      'الأرقام الجديدة ما راح تُسجَّل كجهات اتصال تلقائيًا بعد الآن.';

  @override
  String get partnerLoyaltyTitle => 'ولاء الشركاء';

  @override
  String get partnerLoyaltySubtitle =>
      'كوّن تحالفاً مع محل آخر مسجّل عندنا وامنحه امتيازاً على اشتراكه معنا';

  @override
  String get partnerLoyaltyCapLabel => 'سقفك الحالي';

  @override
  String get partnerLoyaltyPrefsTitle =>
      'خانة تكوين التحالف أثناء تسجيل الزيارة';

  @override
  String get partnerLoyaltyPrefsDesc =>
      'تشغيلها يسمح لأي موظف يسجّل زيارة إنه يكوّن تحالفاً بنفس اللحظة.';

  @override
  String get partnerLoyaltyGrantTitle => 'كوّن تحالفاً';

  @override
  String get partnerLoyaltyPhoneLabel => 'رقم جوال المحل الشريك';

  @override
  String get partnerLoyaltyPhoneHintOk => 'لا تحالف بينكما هذا الشهر';

  @override
  String get partnerLoyaltyPhoneHintAlready =>
      'عندك تحالف معه هذا الشهر بالفعل';

  @override
  String get partnerLoyaltyPhoneHintUnregistered =>
      'هذا الرقم ليس محلاً مسجّلاً عندنا';

  @override
  String get partnerLoyaltyPercentLabel => 'نسبة الامتياز';

  @override
  String partnerLoyaltyCapLine(int p) {
    return 'أقصى نسبة تقدر تمنحها الآن: $p%';
  }

  @override
  String get partnerLoyaltyScopeLabel => 'يشمل';

  @override
  String get partnerLoyaltyScopeAll => 'الكل';

  @override
  String get partnerLoyaltySubmit => 'كوّن التحالف';

  @override
  String get partnerLoyaltySubmitting => 'يُرسَل…';

  @override
  String get partnerLoyaltyResultSuccess =>
      'تم تكوين التحالف — سيُطبَّق تلقائياً عند تجديد اشتراك المحل القادم.';

  @override
  String get partnerLoyaltyResultPartial =>
      'تحالف جزئي — بعض التطبيقات رُفضت، افتح «السجل» للتفاصيل.';

  @override
  String get partnerLoyaltyOutcomeGranted => 'نجح';

  @override
  String get partnerLoyaltyOutcomeInvalidPercent => 'نسبة الامتياز غير صحيحة';

  @override
  String get partnerLoyaltyOutcomeInvalidScope => 'اختر تطبيقاً حقيقياً';

  @override
  String get partnerLoyaltyOutcomeOverCap => 'تجاوزت سقفك الحالي';

  @override
  String get partnerLoyaltyOutcomeNoAccount =>
      'هذا الرقم ليس محلاً مسجّلاً عندنا';

  @override
  String get partnerLoyaltyOutcomeNotSubscribed =>
      'المحل لا يملك أي تطبيق ضمن ما اخترته';

  @override
  String get partnerLoyaltyOutcomeBillingUnavailable =>
      'تعذّر إتمام العملية، حاول مرة أخرى';

  @override
  String get partnerLoyaltyOutcomeAlreadyHasBetterCoupon =>
      'عنده امتياز أقوى بالفعل';

  @override
  String get partnerLoyaltyOutcomeCouponExpired => 'الامتياز منتهٍ';

  @override
  String get partnerLoyaltyOutcomeCouponExhausted => 'الامتياز استُنفد';

  @override
  String get partnerLoyaltyOutcomeCouponUnknown => 'امتياز غير معروف';

  @override
  String get partnerLoyaltyOutcomePlanMismatch =>
      'الامتياز لا يطابق هذا التطبيق';

  @override
  String get partnerLoyaltyOutcomeCouponDisabled => 'الامتياز معطّل';

  @override
  String get partnerLoyaltyOutcomeCouponScheduled => 'الامتياز لم يبدأ بعد';

  @override
  String get partnerLoyaltyTabLog => 'السجل';

  @override
  String get partnerLoyaltyTabStats => 'الإحصائيات';

  @override
  String get partnerLoyaltyLogSearchHint => 'بحث بآخر 4 أرقام';

  @override
  String get partnerLoyaltyLogFilterAll => 'كل الحالات';

  @override
  String get partnerLoyaltyLogFilterOk => 'ناجح فقط';

  @override
  String get partnerLoyaltyLogFilterFail => 'فاشل فقط';

  @override
  String get partnerLoyaltyLogEmptyTitle => 'لا تحالفات بعد';

  @override
  String get partnerLoyaltyLogEmptyDesc => 'أول تحالف تكوّنه يظهر هنا.';

  @override
  String get partnerLoyaltyLogReadFailed => 'تعذّرت قراءة السجل';

  @override
  String get partnerLoyaltyStatsKpiMonth => 'تحالفات هذا الشهر';

  @override
  String get partnerLoyaltyStatsKpiCap => 'سقفك الحالي';

  @override
  String get partnerLoyaltyStatsKpiCeiling => 'السقف الأقصى بالمنصة';

  @override
  String get partnerLoyaltyStatsLadderTitle => 'مكانك بالسلّم';

  @override
  String partnerLoyaltyStatsLadderNote(int n, int left, int p) {
    return '$n تحالفاً هذا الشهر — باقي $left عشان توصل لشريحة الـ$p%';
  }

  @override
  String partnerLoyaltyStatsLadderAtTop(int n) {
    return '$n تحالفاً هذا الشهر — أنت بأعلى شريحة';
  }

  @override
  String partnerLoyaltyStatsCeilingNote(int p) {
    return 'السقف الأقصى بالمنصة $p% — ما يتجاوزه أي محل بأي حال';
  }

  @override
  String get partnerLoyaltyStatsChartTitle => 'عدد التحالفات آخر 6 أشهر';

  @override
  String get partnerLoyaltyReadFailedTitle => 'تعذّرت قراءة بياناتك';

  @override
  String get partnerLoyaltyReadFailedDesc => 'حاول بعد قليل.';

  @override
  String get shopReadFailed => 'تعذّرت قراءة مؤشرات محلّك';

  @override
  String get shopMultiBranchTitle => 'اختر فرعًا';

  @override
  String get shopMultiBranchDesc =>
      'عندك أكثر من فرع — اختر واحدًا لعرض مؤشراته.';

  @override
  String get shopEmptyBranchTitle => 'ما فيه بيانات لهذا الفرع بعد';

  @override
  String get shopRetentionTitle => 'نسبة رجوع عملائك';

  @override
  String get shopRetentionMutedNote =>
      'لسا ما فيه زيارات كافية لحساب هذا الرقم.';

  @override
  String get shopRetentionBrandNew =>
      'سجّل أول زيارة عشان تبدأ نشوف نسبة رجوع عملائك.';

  @override
  String get shopRegisterFirstVisit => 'سجّل أول زيارة';

  @override
  String get shopRetentionPrefix10 => 'من كل 10 عملاء زاروك،';

  @override
  String get shopRetentionSuffix => 'يرجعون لك';

  @override
  String get shopOneCustomer => 'عميل واحد زارك';

  @override
  String shopNCustomers(int n) {
    return '$n عميل زاروك';
  }

  @override
  String shopRetentionSmallPrefix(String base) {
    return '$base، منهم';
  }

  @override
  String shopOverNMonths(int n) {
    return 'خلال $n أشهر';
  }

  @override
  String get shopUnlimited => 'بلا حد';

  @override
  String get shopTileSentToday => 'أُرسلت اليوم';

  @override
  String get shopTileWaiting => 'بالانتظار';

  @override
  String get shopTileCeilingRemaining => 'المتبقي اليوم';

  @override
  String get shopNextStepLabel => 'الخطوة التالية';

  @override
  String get shopNotNow => 'ليس الآن';

  @override
  String get shopDeckUrgent => 'عاجل';

  @override
  String get shopDeckWeek => 'الأسبوع';

  @override
  String get shopDeckOpportunities => 'فرص';

  @override
  String get shopComputedNow => 'احتُسبت الآن';

  @override
  String shopComputedHoursAgo(int n) {
    return 'احتُسبت قبل $n ساعة';
  }

  @override
  String get shopStale => 'قديمة';

  @override
  String get shopRefreshAction => 'تحديث';

  @override
  String get shopComputingTitle => 'جاري احتساب مؤشراتك';

  @override
  String get shopComputeLoading => 'يُحتسب…';

  @override
  String get shopComputeAction => 'احتسب الآن';

  @override
  String get shopAtRiskTitle => 'عملاء على وشك الابتعاد';

  @override
  String get shopAtRiskMutedNote => 'لسا ما فيه بيانات كافية.';

  @override
  String get shopAtRiskAllGood => 'ما فيه عميل متأخر عن موعده الآن — كله تمام';

  @override
  String get shopWaNotConnected => 'واتساب محلك غير مربوط بعد';

  @override
  String get shopWaNotVerified => 'رقم واتساب محلك غير موثّق بعد';

  @override
  String get shopCeilingReached => 'وصلت الحد الأقصى للرسائل اليوم';

  @override
  String shopDaysOverdue(int n) {
    return 'متأخر $n يوم';
  }

  @override
  String get shopAtRiskCta => 'أرسل حملة استرجاع';

  @override
  String get shopAiImpactTitle => 'أثر المساعد الذكي عبر واتساب';

  @override
  String get shopAiConversations => 'محادثات';

  @override
  String get shopAiBookings => 'حجوزات';

  @override
  String get shopAiUpsellRate => 'قبول العروض';

  @override
  String get shopWeekMutedTitle => 'زيارات الأسبوع';

  @override
  String get shopWeekMutedNote => 'لسا ما فيه بيانات كافية.';

  @override
  String get shopNewReturningMutedTitle => 'عملاء جدد مقابل عائدين';

  @override
  String get shopNewReturningMutedNote => 'لسا ما فيه بيانات كافية.';

  @override
  String get shopBranchCompareTitle => 'مقارنة الفروع';

  @override
  String get shopBranchCompareMutedNote => 'تحتاج فرعين على الأقل عشان تقارن.';

  @override
  String get shopStaffCompareTitle => 'مقارنة الموظفين';

  @override
  String get shopStaffCompareMutedNote => 'تحتاج موظفين على الأقل عشان تقارن.';

  @override
  String get shopWeekTitle => 'زيارات هذا الأسبوع';

  @override
  String get shopNewReturningTitle => 'جدد مقابل عائدين';

  @override
  String get shopNewLabel => 'جدد:';

  @override
  String get shopReturningLabel => 'عائدين:';

  @override
  String get shopServicesTitle => 'خدماتك';

  @override
  String get shopServicesMutedNote => 'لسا ما فيه بيانات كافية.';

  @override
  String get shopMessageFlowTitle => 'أثر رسائل التذكير';

  @override
  String get shopMutedMessageFlowNote => 'لسا ما فيه بيانات كافية.';

  @override
  String get shopHoldoutTitle => 'مقارنة: من راسلناه مقابل من لا';

  @override
  String get shopMutedHoldoutNote => 'لسا يُقاس.';

  @override
  String shopReturnedAfterReminder(int visits, int days) {
    return '$visits زيارة خلال $days يوم بعد التذكير';
  }

  @override
  String shopOptOutRate(String p) {
    return '$p% طلبوا التوقف عن الرسائل';
  }

  @override
  String get shopHoldoutNoMessages => 'بلا رسائل';

  @override
  String get shopHoldoutReached => 'راسلناهم';

  @override
  String get shopHoldoutOff =>
      'قياس أثر الرسائل غير مُفعَّل — كل عملائك يصلهم كل شيء، فلا مجموعة نقارن بها.';

  @override
  String shopHoldoutMeasuring(int min, int need) {
    return 'ما زلنا نقيس أثر الرسائل على محلّك — $min من $need في أصغر المجموعتين.';
  }

  @override
  String shopTodayRetrying(int n) {
    return '$n رسالة تحاول الخروج';
  }

  @override
  String get shopTrendUp => 'تتحسّن';

  @override
  String get shopTrendDown => 'تتراجع';

  @override
  String shopRetentionSincePeriods(int n) {
    return 'منذ $n فترات';
  }

  @override
  String get shopAtLeastSuffix => ' — على الأقل';

  @override
  String get shopRegisterFirstVisitArrow => 'سجّل أول زيارة ←';

  @override
  String get shopWeekNoCompare => 'لسه ما عندنا أسبوع كامل نقارنه';

  @override
  String shopNextStepAlso(String msg) {
    return 'وأيضاً: $msg';
  }

  @override
  String shopBranchCompareUnassigned(int n) {
    return '$n زيارة بلا فرع محدَّد — لا تُحتسب لأي فرع.';
  }

  @override
  String get shopBranchCompareNeedTwo =>
      'لا نقارن الفروع بعد — يحتاج فرعان فأكثر بزيارات حقيقية.';

  @override
  String get shopBranchCompareNeedSecond =>
      'فرع واحد فعّال حتى الآن — المقارنة تحتاج فرعاً ثانياً بزيارات حقيقية.';

  @override
  String get shopBranchCompareTooShort =>
      'لا نرتّب الفروع بعد — الفترة قصيرة، والمقارنة الآن تظلم الأحدث.';

  @override
  String shopStaffCompareUnassigned(int n) {
    return '$n زيارة بلا موظف محدَّد — لا تُحتسب لأحد.';
  }

  @override
  String get shopStaffCompareNeedTwo =>
      'لا نقارن الموظفين بعد — يحتاج موظفان فأكثر بزيارات منسوبة لهم.';

  @override
  String get shopStaffCompareNeedSecond =>
      'موظف واحد منسوب حتى الآن — المقارنة تحتاج موظفاً ثانياً بزيارات حقيقية.';

  @override
  String get shopStaffCompareTooShort =>
      'لا نرتّب الموظفين بعد — الفترة قصيرة، والمقارنة الآن تظلم الأحدث.';

  @override
  String get shopPeakTitle => 'أكثر أوقاتك ازدحامًا';

  @override
  String get shopPeakMutedNote =>
      'تحتاج زياراتٍ موزّعة على أيام وساعات كافية لنرسمها.';

  @override
  String shopPeakBusiestTime(String day, int h) {
    return '$day حوالي الساعة $h:00';
  }

  @override
  String shopPeakBusiestNote(String name) {
    return 'أكثر وقت زحمة عندك: $name.';
  }

  @override
  String get shopEntityDayServicesTitle => 'خدماتك حسب يوم الأسبوع';

  @override
  String get shopEntityDayServicesHint =>
      'أي خدمة تُطلب بيوم معيّن أكثر — يساعدك تجهّز الطاقم المناسب ذاك اليوم.';

  @override
  String get shopEntityDayServicesMutedNote =>
      'تحتاج زياراتٍ موزّعة على أيام كافية لنرسمها.';

  @override
  String get shopEntityDayBranchesTitle => 'فروعك حسب يوم الأسبوع';

  @override
  String get shopEntityDayBranchesHint =>
      'فروعك ما تشترك بالضرورة بنفس الإيقاع — فرع بمول يزدحم بعطلة، وفرع حيّ يزدحم بعد الدوام.';

  @override
  String get shopEntityDayBranchesMutedNote =>
      'تحتاج فرعاً ثانياً وزياراتٍ موزّعة على أيام كافية لنرسمها.';

  @override
  String get shopBundlesTitle => 'باقات مقترحة';

  @override
  String get shopBundlesMutedNote =>
      'ما فيه اقترانات كافية بعد لنقترح باقة منها.';

  @override
  String shopBundlesOpportunity(int n) {
    return '$n فرصة';
  }

  @override
  String get shopAssociationsTitle => 'ما يُطلب معًا';

  @override
  String get shopAssociationsMutedNote => 'ما فيه اقترانات كافية بعد.';

  @override
  String shopAssociationsLearningNote(int have, int need) {
    return 'ما نعرف بعد ما الذي يُطلب مع ماذا — التعرّف على الاقترانات يحتاج زياراتٍ أكثر ليصير الاستنتاج صحيحاً لا صدفة. ($have/$need)';
  }

  @override
  String shopCustomersCount(int n) {
    return '$n عميلاً';
  }

  @override
  String get shopDay0Short => 'ح';

  @override
  String get shopDay1Short => 'ن';

  @override
  String get shopDay2Short => 'ث';

  @override
  String get shopDay3Short => 'ر';

  @override
  String get shopDay4Short => 'خ';

  @override
  String get shopDay5Short => 'ج';

  @override
  String get shopDay6Short => 'س';

  @override
  String get shopDay0Full => 'الأحد';

  @override
  String get shopDay1Full => 'الإثنين';

  @override
  String get shopDay2Full => 'الثلاثاء';

  @override
  String get shopDay3Full => 'الأربعاء';

  @override
  String get shopDay4Full => 'الخميس';

  @override
  String get shopDay5Full => 'الجمعة';

  @override
  String get shopDay6Full => 'السبت';

  @override
  String get shopMissedTitle => 'عملاء ما جرّبوا كل اللي يناسبهم';

  @override
  String get shopMissedMutedNote =>
      'لا عملاء واضحين بعد ناقصين خدمة تُشترى عادة مع خدماتهم.';

  @override
  String get shopCustomerFallback => 'عميل';

  @override
  String get shopKpiActiveCustomers => 'عملاء نشطون';

  @override
  String get shopKpiReturnCycle => 'دورة العودة';

  @override
  String shopDaysSuffix(int n) {
    return '$n يومًا';
  }

  @override
  String get shopKpiChurnRate => 'التسرّب';

  @override
  String get shopTileServicesPerVisit => 'خدمات لكل زيارة';

  @override
  String get shopTileExpectedNextWeek => 'متوقّع الأسبوع الجاي';

  @override
  String get shopTileCycleCompletion => 'التزام الدورة الدورية';

  @override
  String get shopPerVisitMutedTitle => 'خدماتك لكل زيارة، والالتزام بالدورة';

  @override
  String get shopPerVisitMutedNote => 'تحتاج زياراتٍ حقيقية أولاً لتُحسب.';

  @override
  String get shopLeadConversionTitle => 'تحوّل من تواصلوا معك أول مرة';

  @override
  String shopLeadConversionDetail(int converted, int total) {
    return '$converted من $total تحوّل لزيارة حقيقية';
  }

  @override
  String get whatsappOrdersTitle => 'طلبات التوصيل عبر الواتساب';

  @override
  String get whatsappOrdersSubtitle =>
      'طلبات يطلبها عملاؤك من كتالوجك عبر واتساب، من الاستلام للتسليم.';

  @override
  String get whatsappOrdersKpiWaiting => 'بانتظار المراجعة';

  @override
  String get whatsappOrdersKpiStuck => 'متأخرة';

  @override
  String get whatsappOrdersKpiDeliveredToday => 'سُلِّمت اليوم';

  @override
  String get whatsappOrdersFilterAll => 'الكل';

  @override
  String get whatsappOrdersFilterIncoming => 'جديدة';

  @override
  String get whatsappOrdersFilterConfirmed => 'مؤكَّدة';

  @override
  String get whatsappOrdersFilterPreparing => 'قيد التجهيز';

  @override
  String get whatsappOrdersFilterReady => 'جاهزة';

  @override
  String get whatsappOrdersFilterDelivery => 'في الطريق';

  @override
  String get whatsappOrdersFilterClosed => 'مكتملة';

  @override
  String get whatsappOrdersLoadFailedTitle => 'تعذّر تحميل الطلبات';

  @override
  String get whatsappOrdersLoadFailedBody => 'تحقّق من اتصالك وحاول مرة أخرى.';

  @override
  String get whatsappOrdersRetry => 'إعادة المحاولة';

  @override
  String get whatsappOrdersEmptyTitle => 'لا طلبات بعد';

  @override
  String get whatsappOrdersEmptyBody => 'أي طلب يصل عبر واتساب يظهر هنا فوراً.';

  @override
  String get whatsappOrdersUnnamed => 'عميل';

  @override
  String get whatsappOrdersStatusReceived => 'جديد';

  @override
  String get whatsappOrdersStatusPaymentMismatch => 'خلل بمطابقة الدفع';

  @override
  String get whatsappOrdersStatusConfirmed => 'مؤكَّد';

  @override
  String get whatsappOrdersStatusPreparing => 'قيد التجهيز';

  @override
  String get whatsappOrdersStatusReady => 'جاهز';

  @override
  String get whatsappOrdersStatusOutForDelivery => 'في الطريق';

  @override
  String get whatsappOrdersStatusDelivered => 'تم التسليم';

  @override
  String get whatsappOrdersStatusCancelled => 'ملغى';

  @override
  String get whatsappOrdersStuckBadge => 'متأخر';

  @override
  String get whatsappOrdersOpenMap => 'فتح الموقع بالخرائط';

  @override
  String get whatsappOrdersPhoneCopied => 'تم نسخ رقم الجوال';

  @override
  String get whatsappOrdersActionStartPreparing => 'بدء التجهيز';

  @override
  String get whatsappOrdersActionMarkReady => 'الطلب جاهز';

  @override
  String get whatsappOrdersActionStartDelivery => 'خرج للتوصيل';

  @override
  String get whatsappOrdersActionMarkDelivered => 'تم التسليم';

  @override
  String get whatsappOrdersActionResolveMismatch => 'تأكيد الدفع يدوياً';

  @override
  String get whatsappOrdersActionCancel => 'إلغاء الطلب';

  @override
  String get whatsappOrdersActionFailed =>
      'تعذّر تنفيذ الإجراء، حاول مرة أخرى.';

  @override
  String get whatsappOrdersCancelReasonPrompt => 'سبب الإلغاء (اختياري)';

  @override
  String get whatsappOrdersCancelReasonCancel => 'تراجع';

  @override
  String get whatsappOrdersCancelReasonConfirm => 'تأكيد الإلغاء';

  @override
  String get whatsappOrdersPauseLabel => 'إيقاف استقبال الطلبات';

  @override
  String whatsappOrdersPauseBannerText(String reason) {
    return 'هذا الفرع متوقف عن استقبال طلبات واتساب الجديدة — $reason';
  }

  @override
  String get whatsappOrdersPauseDefaultReason =>
      'أُوقف الاستقبال مؤقتاً من الكاشير';

  @override
  String get whatsappOrdersDrawerSubtotal => 'المجموع قبل الخصم';

  @override
  String get whatsappOrdersDrawerDiscount => 'الخصم';

  @override
  String get whatsappOrdersDrawerPointsReward => 'مكافأة نقاط الولاء';

  @override
  String get whatsappOrdersDrawerTotal => 'الإجمالي المطلوب';

  @override
  String whatsappOrdersDrawerMismatchHint(String paid) {
    return 'المبلغ المستلم من بوابة الدفع ($paid) لا يطابق المطلوب — تحقق يدوياً قبل التأكيد.';
  }

  @override
  String whatsappOrdersDrawerCancelReason(String reason) {
    return 'سبب الإلغاء: $reason';
  }

  @override
  String whatsappOrdersDrawerNote(String note) {
    return 'ملاحظة: $note';
  }
}
