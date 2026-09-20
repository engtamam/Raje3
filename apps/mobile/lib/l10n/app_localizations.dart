import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_ar.dart';
import 'app_localizations_bn.dart';
import 'app_localizations_en.dart';
import 'app_localizations_fil.dart';
import 'app_localizations_ha.dart';
import 'app_localizations_ur.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of S
/// returned by `S.of(context)`.
///
/// Applications need to include `S.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: S.localizationsDelegates,
///   supportedLocales: S.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the S.supportedLocales
/// property.
abstract class S {
  S(String locale)
      : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static S? of(BuildContext context) {
    return Localizations.of<S>(context, S);
  }

  static const LocalizationsDelegate<S> delegate = _SDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
    delegate,
    GlobalMaterialLocalizations.delegate,
    GlobalCupertinoLocalizations.delegate,
    GlobalWidgetsLocalizations.delegate,
  ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('ar'),
    Locale('en'),
    Locale('ur'),
    Locale('ha'),
    Locale('fil'),
    Locale('bn')
  ];

  /// App name shown in app bar and about page
  ///
  /// In ar, this message translates to:
  /// **'راجِع'**
  String get appName;

  /// No description provided for @ok.
  ///
  /// In ar, this message translates to:
  /// **'موافق'**
  String get ok;

  /// No description provided for @cancel.
  ///
  /// In ar, this message translates to:
  /// **'إلغاء'**
  String get cancel;

  /// No description provided for @save.
  ///
  /// In ar, this message translates to:
  /// **'حفظ'**
  String get save;

  /// No description provided for @close.
  ///
  /// In ar, this message translates to:
  /// **'إغلاق'**
  String get close;

  /// No description provided for @back.
  ///
  /// In ar, this message translates to:
  /// **'رجوع'**
  String get back;

  /// No description provided for @next.
  ///
  /// In ar, this message translates to:
  /// **'التالي'**
  String get next;

  /// No description provided for @done.
  ///
  /// In ar, this message translates to:
  /// **'تم'**
  String get done;

  /// No description provided for @loading.
  ///
  /// In ar, this message translates to:
  /// **'جاري التحميل...'**
  String get loading;

  /// No description provided for @retry.
  ///
  /// In ar, this message translates to:
  /// **'إعادة المحاولة'**
  String get retry;

  /// No description provided for @error.
  ///
  /// In ar, this message translates to:
  /// **'حدث خطأ'**
  String get error;

  /// No description provided for @success.
  ///
  /// In ar, this message translates to:
  /// **'تمت العملية بنجاح'**
  String get success;

  /// No description provided for @search.
  ///
  /// In ar, this message translates to:
  /// **'بحث'**
  String get search;

  /// No description provided for @login.
  ///
  /// In ar, this message translates to:
  /// **'تسجيل الدخول'**
  String get login;

  /// No description provided for @logout.
  ///
  /// In ar, this message translates to:
  /// **'تسجيل الخروج'**
  String get logout;

  /// No description provided for @homeDashboardTitle.
  ///
  /// In ar, this message translates to:
  /// **'لوحة التحكم'**
  String get homeDashboardTitle;

  /// No description provided for @homeShopSectionLabel.
  ///
  /// In ar, this message translates to:
  /// **'محلّي'**
  String get homeShopSectionLabel;

  /// No description provided for @homeLoadErrorTitle.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر التحميل'**
  String get homeLoadErrorTitle;

  /// No description provided for @homeLoadErrorMessage.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تحميل بيانات اليوم. حاول مرة أخرى.'**
  String get homeLoadErrorMessage;

  /// No description provided for @homeTodaySectionTitle.
  ///
  /// In ar, this message translates to:
  /// **'اليوم'**
  String get homeTodaySectionTitle;

  /// No description provided for @homeStatSent.
  ///
  /// In ar, this message translates to:
  /// **'أُرسلت'**
  String get homeStatSent;

  /// No description provided for @homeStatWaiting.
  ///
  /// In ar, this message translates to:
  /// **'في الانتظار'**
  String get homeStatWaiting;

  /// No description provided for @homeStatRetrying.
  ///
  /// In ar, this message translates to:
  /// **'تعيد المحاولة'**
  String get homeStatRetrying;

  /// No description provided for @homeDashboardComputing.
  ///
  /// In ar, this message translates to:
  /// **'أحسب مؤشرات محلك الآن — حدّث الصفحة بعد قليل'**
  String get homeDashboardComputing;

  /// No description provided for @homeDashboardSectionTitle.
  ///
  /// In ar, this message translates to:
  /// **'مؤشرات المحل'**
  String get homeDashboardSectionTitle;

  /// No description provided for @homeDashboardEmpty.
  ///
  /// In ar, this message translates to:
  /// **'لا توجد بيانات كافية بعد.'**
  String get homeDashboardEmpty;

  /// No description provided for @themeDarkMode.
  ///
  /// In ar, this message translates to:
  /// **'الوضع الداكن'**
  String get themeDarkMode;

  /// No description provided for @themeLightMode.
  ///
  /// In ar, this message translates to:
  /// **'الوضع الفاتح'**
  String get themeLightMode;

  /// Generic required-field validation error, no field name known
  ///
  /// In ar, this message translates to:
  /// **'هذا الحقل مطلوب'**
  String get validatorFieldRequiredGeneric;

  /// Required-field validation error naming the field
  ///
  /// In ar, this message translates to:
  /// **'{field} مطلوب'**
  String validatorFieldRequiredNamed(String field);

  /// Email validation: empty value
  ///
  /// In ar, this message translates to:
  /// **'البريد الإلكتروني مطلوب'**
  String get validatorEmailRequired;

  /// Email validation: malformed value
  ///
  /// In ar, this message translates to:
  /// **'البريد الإلكتروني غير صالح'**
  String get validatorEmailInvalid;

  /// Phone validation: empty value
  ///
  /// In ar, this message translates to:
  /// **'رقم الهاتف مطلوب'**
  String get validatorPhoneRequired;

  /// Phone validation: not a valid Saudi mobile number
  ///
  /// In ar, this message translates to:
  /// **'رقم الهاتف غير صالح - يجب أن يبدأ بـ 05'**
  String get validatorPhoneInvalid;

  /// Password validation: empty value
  ///
  /// In ar, this message translates to:
  /// **'كلمة المرور مطلوبة'**
  String get validatorPasswordRequired;

  /// Password validation: below minimum length
  ///
  /// In ar, this message translates to:
  /// **'كلمة المرور يجب أن تكون 8 أحرف على الأقل'**
  String get validatorPasswordTooShort;

  /// Password validation: missing uppercase letter
  ///
  /// In ar, this message translates to:
  /// **'كلمة المرور يجب أن تحتوي على حرف كبير'**
  String get validatorPasswordNeedsUppercase;

  /// Password validation: missing lowercase letter
  ///
  /// In ar, this message translates to:
  /// **'كلمة المرور يجب أن تحتوي على حرف صغير'**
  String get validatorPasswordNeedsLowercase;

  /// Password validation: missing a digit
  ///
  /// In ar, this message translates to:
  /// **'كلمة المرور يجب أن تحتوي على رقم'**
  String get validatorPasswordNeedsDigit;

  /// Field-name label used both as a form label and as the fieldName passed into validateRequired for the confirm-password field
  ///
  /// In ar, this message translates to:
  /// **'تأكيد كلمة المرور'**
  String get validatorConfirmPasswordFieldName;

  /// Confirm-password validation: values differ
  ///
  /// In ar, this message translates to:
  /// **'كلمة المرور غير متطابقة'**
  String get validatorPasswordMismatch;

  /// OTP validation: empty value
  ///
  /// In ar, this message translates to:
  /// **'رمز التحقق مطلوب'**
  String get validatorOtpRequired;

  /// OTP validation: wrong digit count
  ///
  /// In ar, this message translates to:
  /// **'رمز التحقق يجب أن يكون 6 أرقام'**
  String get validatorOtpLength;

  /// OTP validation: contains non-digit characters
  ///
  /// In ar, this message translates to:
  /// **'رمز التحقق يجب أن يحتوي على أرقام فقط'**
  String get validatorOtpDigitsOnly;

  /// Name validation: empty value
  ///
  /// In ar, this message translates to:
  /// **'الاسم مطلوب'**
  String get validatorNameRequired;

  /// Name validation: below minimum length
  ///
  /// In ar, this message translates to:
  /// **'الاسم يجب أن يكون حرفين على الأقل'**
  String get validatorNameTooShort;

  /// Name validation: above maximum length
  ///
  /// In ar, this message translates to:
  /// **'الاسم يجب أن لا يتجاوز 100 حرف'**
  String get validatorNameTooLong;

  /// Name validation: disallowed characters
  ///
  /// In ar, this message translates to:
  /// **'الاسم يحتوي على أحرف غير مسموحة'**
  String get validatorNameInvalidChars;

  /// Fallback field-name used inside other validator messages when no fieldName was given
  ///
  /// In ar, this message translates to:
  /// **'هذا الحقل'**
  String get validatorGenericFieldName;

  /// Minimum-length validation error naming the field and the minimum
  ///
  /// In ar, this message translates to:
  /// **'{field} يجب أن يكون {minLength} أحرف على الأقل'**
  String validatorMinLengthNamed(String field, int minLength);

  /// Maximum-length validation error naming the field and the maximum
  ///
  /// In ar, this message translates to:
  /// **'{field} يجب أن لا يتجاوز {maxLength} حرف'**
  String validatorMaxLengthNamed(String field, int maxLength);

  /// Fallback subject name for numeric-range validation messages
  ///
  /// In ar, this message translates to:
  /// **'القيمة'**
  String get validatorGenericValueName;

  /// Numeric validation error naming the field
  ///
  /// In ar, this message translates to:
  /// **'{field} يجب أن يكون رقم'**
  String validatorNotANumberNamed(String field);

  /// Numeric-range validation error: below minimum
  ///
  /// In ar, this message translates to:
  /// **'{field} يجب أن يكون {min} على الأقل'**
  String validatorMinValueNamed(String field, String min);

  /// Numeric-range validation error: above maximum
  ///
  /// In ar, this message translates to:
  /// **'{field} يجب أن لا يتجاوز {max}'**
  String validatorMaxValueNamed(String field, String max);

  /// URL validation: empty value
  ///
  /// In ar, this message translates to:
  /// **'الرابط مطلوب'**
  String get validatorUrlRequired;

  /// URL validation: malformed value
  ///
  /// In ar, this message translates to:
  /// **'الرابط غير صالح'**
  String get validatorUrlInvalid;

  /// Snackbar shown when openUrl is called with no URL
  ///
  /// In ar, this message translates to:
  /// **'الرابط غير متوفر'**
  String get urlHelperUnavailable;

  /// Snackbar shown when launching a URL throws
  ///
  /// In ar, this message translates to:
  /// **'تعذر فتح الرابط'**
  String get urlHelperOpenFailed;

  /// Placeholder body for a nav section the catalogue exposes but mobile has no screen for yet
  ///
  /// In ar, this message translates to:
  /// **'هذه الشاشة غير متاحة على تطبيق الجوال بعد.'**
  String get routerScreenNotOnMobileYet;

  /// No description provided for @kbHintNoEntry.
  ///
  /// In ar, this message translates to:
  /// **'ما فيه شرح لهذا بعد.'**
  String get kbHintNoEntry;

  /// No description provided for @assistantChatTitle.
  ///
  /// In ar, this message translates to:
  /// **'المساعد'**
  String get assistantChatTitle;

  /// No description provided for @assistantInputHint.
  ///
  /// In ar, this message translates to:
  /// **'اكتب سؤالك...'**
  String get assistantInputHint;

  /// No description provided for @assistantSend.
  ///
  /// In ar, this message translates to:
  /// **'إرسال'**
  String get assistantSend;

  /// No description provided for @assistantUnavailable.
  ///
  /// In ar, this message translates to:
  /// **'المساعد غير متاح حالياً.'**
  String get assistantUnavailable;

  /// No description provided for @assistantPreparing.
  ///
  /// In ar, this message translates to:
  /// **'جاري تجهيز المساعد...'**
  String get assistantPreparing;

  /// Subtitle under the wordmark on the login screen
  ///
  /// In ar, this message translates to:
  /// **'سجّل دخولك للمتابعة'**
  String get authLoginSubtitle;

  /// Mobile-number field label, used on login and signup
  ///
  /// In ar, this message translates to:
  /// **'رقم الجوال'**
  String get authPhoneLabel;

  /// Password field label, used on login and signup, and as the fieldName passed to validateRequired
  ///
  /// In ar, this message translates to:
  /// **'كلمة المرور'**
  String get authPasswordLabel;

  /// Divider label above the open-a-new-shop button on login
  ///
  /// In ar, this message translates to:
  /// **'ليس لديك محل؟'**
  String get authNoShopYetLabel;

  /// Button label on login that opens signup
  ///
  /// In ar, this message translates to:
  /// **'افتح محلاً جديداً'**
  String get authOpenNewShopCta;

  /// Signup screen app bar title
  ///
  /// In ar, this message translates to:
  /// **'فتح محل جديد'**
  String get authOpenShopTitle;

  /// Subtitle under the wordmark on signup
  ///
  /// In ar, this message translates to:
  /// **'ثلاث خطوات فقط لفتح محلك'**
  String get authSignupSubtitle;

  /// Shop-name field label on signup
  ///
  /// In ar, this message translates to:
  /// **'اسم المحل'**
  String get authShopNameLabel;

  /// Button label on signup that goes back to login
  ///
  /// In ar, this message translates to:
  /// **'لديك محل بالفعل؟ سجّل الدخول'**
  String get authAlreadyHaveShopCta;

  /// Signup submit-button label
  ///
  /// In ar, this message translates to:
  /// **'فتح المحل'**
  String get authOpenShopCta;

  /// Verify-phone screen app bar title
  ///
  /// In ar, this message translates to:
  /// **'تأكيد رقم الجوال'**
  String get authVerifyPhoneTitle;

  /// Tells the user a code was sent to their phone number
  ///
  /// In ar, this message translates to:
  /// **'أرسلنا رمز تحقق إلى {phone}'**
  String authVerifyCodeSentTo(String phone);

  /// Busy-state label on the verify-code submit button
  ///
  /// In ar, this message translates to:
  /// **'جارٍ التحقق...'**
  String get authVerifying;

  /// Verify-code submit-button label
  ///
  /// In ar, this message translates to:
  /// **'تأكيد'**
  String get authConfirmCta;

  /// Resend-code button label, shown after a code was already requested
  ///
  /// In ar, this message translates to:
  /// **'إعادة إرسال الرمز'**
  String get authResendCodeCta;

  /// Send-code button label, shown before a code has been requested
  ///
  /// In ar, this message translates to:
  /// **'إرسال الرمز'**
  String get authSendCodeCta;

  /// Fallback message when requesting an OTP code fails with no server message
  ///
  /// In ar, this message translates to:
  /// **'تعذّر إرسال الرمز.'**
  String get authCodeSendFailedFallback;

  /// Fallback message when OTP verification fails with no server message
  ///
  /// In ar, this message translates to:
  /// **'رمز التحقق غير صحيح.'**
  String get authOtpIncorrectFallback;

  /// Shown when the visit screen's service catalogue fails to load
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تحميل الخدمات. اسحب للأسفل لإعادة المحاولة.'**
  String get visitCatalogueLoadErrorFallback;

  /// Inline validation message when saving a visit with no customer phone entered
  ///
  /// In ar, this message translates to:
  /// **'أدخل رقم جوال العميل'**
  String get visitEnterCustomerPhone;

  /// Inline validation message when saving a visit with no service selected
  ///
  /// In ar, this message translates to:
  /// **'اختر خدمة واحدة على الأقل'**
  String get visitSelectAtLeastOneService;

  /// Success message after a visit is recorded
  ///
  /// In ar, this message translates to:
  /// **'تم تسجيل الزيارة.'**
  String get visitSavedMessage;

  /// Fallback message when saving a visit is refused with no server reason
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تسجيل الزيارة.'**
  String get visitSaveErrorFallback;

  /// Message when saving a visit fails with a network/Dio exception
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تسجيل الزيارة. تحقق من الاتصال وحاول مرة أخرى.'**
  String get visitSaveErrorNetworkFallback;

  /// Visit-recording screen app bar title
  ///
  /// In ar, this message translates to:
  /// **'تسجيل زيارة'**
  String get visitTitle;

  /// Section title for the customer-lookup card
  ///
  /// In ar, this message translates to:
  /// **'العميل'**
  String get visitCustomerSectionTitle;

  /// Label above the customer phone-lookup field
  ///
  /// In ar, this message translates to:
  /// **'رقم جوال العميل'**
  String get visitCustomerPhoneFieldLabel;

  /// Shown after a phone lookup matches an existing customer
  ///
  /// In ar, this message translates to:
  /// **'عميل معروف: {name}'**
  String visitKnownCustomer(String name);

  /// Shown after a phone lookup finds no existing customer
  ///
  /// In ar, this message translates to:
  /// **'عميل جديد'**
  String get visitNewCustomer;

  /// Section title for the service-selection card
  ///
  /// In ar, this message translates to:
  /// **'الخدمات'**
  String get visitServicesSectionTitle;

  /// Shown when the shop's catalogue has no services
  ///
  /// In ar, this message translates to:
  /// **'لا توجد خدمات بعد.'**
  String get visitNoServicesYet;

  /// Section title for the optional note field
  ///
  /// In ar, this message translates to:
  /// **'ملاحظة (اختياري)'**
  String get visitNoteSectionTitle;

  /// Bottom-bar save button on the visit screen
  ///
  /// In ar, this message translates to:
  /// **'حفظ الزيارة'**
  String get visitSaveButtonLabel;

  /// No description provided for @navAppsLabel.
  ///
  /// In ar, this message translates to:
  /// **'تطبيقاتي'**
  String get navAppsLabel;

  /// No description provided for @navAnalyticsLabel.
  ///
  /// In ar, this message translates to:
  /// **'التحليلات'**
  String get navAnalyticsLabel;

  /// No description provided for @navHomeLabel.
  ///
  /// In ar, this message translates to:
  /// **'الرئيسية'**
  String get navHomeLabel;

  /// No description provided for @navAccountLabel.
  ///
  /// In ar, this message translates to:
  /// **'حسابي'**
  String get navAccountLabel;

  /// No description provided for @appsScreenTitle.
  ///
  /// In ar, this message translates to:
  /// **'تطبيقاتي'**
  String get appsScreenTitle;

  /// No description provided for @appsScreenHint.
  ///
  /// In ar, this message translates to:
  /// **'اضغط على أيقونة الدبّوس لتثبيت تطبيق بالخانة الخامسة بالشريط السفلي'**
  String get appsScreenHint;

  /// No description provided for @appsPinnedBadge.
  ///
  /// In ar, this message translates to:
  /// **'مثبّت بالشريط'**
  String get appsPinnedBadge;

  /// No description provided for @appsPinAction.
  ///
  /// In ar, this message translates to:
  /// **'تثبيت هنا'**
  String get appsPinAction;

  /// No description provided for @homeLauncherEmptyTitle.
  ///
  /// In ar, this message translates to:
  /// **'لا توجد تطبيقات متاحة'**
  String get homeLauncherEmptyTitle;

  /// No description provided for @homeLauncherEmptyMessage.
  ///
  /// In ar, this message translates to:
  /// **'تواصل مع الدعم لتفعيل تطبيق على محلّك'**
  String get homeLauncherEmptyMessage;

  /// No description provided for @accountScreenTitle.
  ///
  /// In ar, this message translates to:
  /// **'حسابي'**
  String get accountScreenTitle;

  /// No description provided for @accountPhoneLabel.
  ///
  /// In ar, this message translates to:
  /// **'رقم الجوال'**
  String get accountPhoneLabel;

  /// No description provided for @accountLogoutAction.
  ///
  /// In ar, this message translates to:
  /// **'تسجيل الخروج'**
  String get accountLogoutAction;

  /// No description provided for @accountLogoutConfirmTitle.
  ///
  /// In ar, this message translates to:
  /// **'تسجيل الخروج'**
  String get accountLogoutConfirmTitle;

  /// No description provided for @accountLogoutConfirmMessage.
  ///
  /// In ar, this message translates to:
  /// **'هل تريد تسجيل الخروج من حسابك؟'**
  String get accountLogoutConfirmMessage;

  /// No description provided for @notificationsUnavailable.
  ///
  /// In ar, this message translates to:
  /// **'الإشعارات غير متاحة بعد'**
  String get notificationsUnavailable;
}

class _SDelegate extends LocalizationsDelegate<S> {
  const _SDelegate();

  @override
  Future<S> load(Locale locale) {
    return SynchronousFuture<S>(lookupS(locale));
  }

  @override
  bool isSupported(Locale locale) => <String>[
        'ar',
        'bn',
        'en',
        'fil',
        'ha',
        'ur'
      ].contains(locale.languageCode);

  @override
  bool shouldReload(_SDelegate old) => false;
}

S lookupS(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'ar':
      return SAr();
    case 'bn':
      return SBn();
    case 'en':
      return SEn();
    case 'fil':
      return SFil();
    case 'ha':
      return SHa();
    case 'ur':
      return SUr();
  }

  throw FlutterError(
      'S.delegate failed to load unsupported locale "$locale". This is likely '
      'an issue with the localizations generation tool. Please file an issue '
      'on GitHub with a reproducible sample app and the gen-l10n configuration '
      'that was used.');
}
