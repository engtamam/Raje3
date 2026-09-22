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
  String get navAppsLabel => 'تطبيقاتي';

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
  String get branchesRoleManager => 'مدير';

  @override
  String get branchesSeatLimit => 'باقتك الحالية لا تسمح بإضافة موظف آخر.';

  @override
  String get branchesHireFailed => 'تعذّر إضافة الموظف، حاول مرة ثانية.';

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
  String visitPointsRedeemedMessage(Object name) {
    return 'تم استبدال $name ✓';
  }

  @override
  String get visitPointsRedeemFailed => 'تعذّر الاستبدال، حاول مرة ثانية.';
}
