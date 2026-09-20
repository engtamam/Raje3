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
  String get homeDashboardComputing => 'أحسب مؤشرات محلك الآن — حدّث الصفحة بعد قليل';

  @override
  String get homeDashboardSectionTitle => 'مؤشرات المحل';

  @override
  String get homeDashboardEmpty => 'لا توجد بيانات كافية بعد.';

  @override
  String get moreSectionsTitle => 'المزيد';

  @override
  String get themeDarkMode => 'الوضع الداكن';

  @override
  String get themeLightMode => 'الوضع الفاتح';

  @override
  String get search => 'بحث';

  @override
  String get login => 'تسجيل الدخول';

  @override
  String get logout => 'تسجيل الخروج';

  @override
  String get validatorFieldRequiredGeneric => 'هذا الحقل مطلوب';

  @override
  String validatorFieldRequiredNamed(String field) => '$field مطلوب';

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
  String get validatorPasswordTooShort => 'كلمة المرور يجب أن تكون 8 أحرف على الأقل';

  @override
  String get validatorPasswordNeedsUppercase => 'كلمة المرور يجب أن تحتوي على حرف كبير';

  @override
  String get validatorPasswordNeedsLowercase => 'كلمة المرور يجب أن تحتوي على حرف صغير';

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
  String validatorMinLengthNamed(String field, int minLength) => '$field يجب أن يكون $minLength أحرف على الأقل';

  @override
  String validatorMaxLengthNamed(String field, int maxLength) => '$field يجب أن لا يتجاوز $maxLength حرف';

  @override
  String get validatorGenericValueName => 'القيمة';

  @override
  String validatorNotANumberNamed(String field) => '$field يجب أن يكون رقم';

  @override
  String validatorMinValueNamed(String field, String min) => '$field يجب أن يكون $min على الأقل';

  @override
  String validatorMaxValueNamed(String field, String max) => '$field يجب أن لا يتجاوز $max';

  @override
  String get validatorUrlRequired => 'الرابط مطلوب';

  @override
  String get validatorUrlInvalid => 'الرابط غير صالح';

  @override
  String get urlHelperUnavailable => 'الرابط غير متوفر';

  @override
  String get urlHelperOpenFailed => 'تعذر فتح الرابط';

  @override
  String get routerScreenNotOnMobileYet => 'هذه الشاشة غير متاحة على تطبيق الجوال بعد.';

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
  String get authAlreadyHaveShopCta => 'لديك محل بالفعل؟ سجّل الدخول';

  @override
  String get authOpenShopCta => 'فتح المحل';

  @override
  String get authVerifyPhoneTitle => 'تأكيد رقم الجوال';

  @override
  String authVerifyCodeSentTo(String phone) => 'أرسلنا رمز تحقق إلى $phone';

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
  String get visitCatalogueLoadErrorFallback => 'تعذّر تحميل الخدمات. اسحب للأسفل لإعادة المحاولة.';

  @override
  String get visitEnterCustomerPhone => 'أدخل رقم جوال العميل';

  @override
  String get visitSelectAtLeastOneService => 'اختر خدمة واحدة على الأقل';

  @override
  String get visitSavedMessage => 'تم تسجيل الزيارة.';

  @override
  String get visitSaveErrorFallback => 'تعذّر تسجيل الزيارة.';

  @override
  String get visitSaveErrorNetworkFallback => 'تعذّر تسجيل الزيارة. تحقق من الاتصال وحاول مرة أخرى.';

  @override
  String get visitTitle => 'تسجيل زيارة';

  @override
  String get visitCustomerSectionTitle => 'العميل';

  @override
  String get visitCustomerPhoneFieldLabel => 'رقم جوال العميل';

  @override
  String visitKnownCustomer(String name) => 'عميل معروف: $name';

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
}
