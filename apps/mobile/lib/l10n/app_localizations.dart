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

  /// No description provided for @assistantSpeak.
  ///
  /// In ar, this message translates to:
  /// **'استمع للرد'**
  String get assistantSpeak;

  /// No description provided for @assistantStopSpeaking.
  ///
  /// In ar, this message translates to:
  /// **'إيقاف الصوت'**
  String get assistantStopSpeaking;

  /// No description provided for @assistantActionUnavailable.
  ///
  /// In ar, this message translates to:
  /// **'ما تقدر تسوي هذا الآن.'**
  String get assistantActionUnavailable;

  /// No description provided for @assistantConfirm.
  ///
  /// In ar, this message translates to:
  /// **'تأكيد'**
  String get assistantConfirm;

  /// No description provided for @assistantCancel.
  ///
  /// In ar, this message translates to:
  /// **'إلغاء'**
  String get assistantCancel;

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

  /// No description provided for @authOwnerNameLabel.
  ///
  /// In ar, this message translates to:
  /// **'اسمك (اختياري)'**
  String get authOwnerNameLabel;

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

  /// Label above the vehicle plate field, shown only when this shop tracks vehicles
  ///
  /// In ar, this message translates to:
  /// **'رقم اللوحة'**
  String get visitPlateFieldLabel;

  /// Inline validation message when saving a visit with no plausible plate, for a shop that tracks vehicles
  ///
  /// In ar, this message translates to:
  /// **'أدخل رقم لوحة صحيحاً (حرف ورقم واحد على الأقل)'**
  String get visitPlateRequired;

  /// Shown after a plate lookup matches an existing customer
  ///
  /// In ar, this message translates to:
  /// **'سيارة معروفة: {name}'**
  String visitKnownVehicle(String name);

  /// Shown after a plate lookup finds no existing customer
  ///
  /// In ar, this message translates to:
  /// **'سيارة جديدة'**
  String get visitNewVehicle;

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

  /// No description provided for @homeGreetingMorning.
  ///
  /// In ar, this message translates to:
  /// **'صباح الخير'**
  String get homeGreetingMorning;

  /// No description provided for @homeGreetingEvening.
  ///
  /// In ar, this message translates to:
  /// **'مساء الخير'**
  String get homeGreetingEvening;

  /// Morning greeting with the account holder's own name
  ///
  /// In ar, this message translates to:
  /// **'صباح الخير، {name}'**
  String homeGreetingMorningNamed(String name);

  /// Evening greeting with the account holder's own name
  ///
  /// In ar, this message translates to:
  /// **'مساء الخير، {name}'**
  String homeGreetingEveningNamed(String name);

  /// No description provided for @homeAppsSectionTitle.
  ///
  /// In ar, this message translates to:
  /// **'تطبيقاتك'**
  String get homeAppsSectionTitle;

  /// No description provided for @homeFeaturedStartNow.
  ///
  /// In ar, this message translates to:
  /// **'ابدأ الآن'**
  String get homeFeaturedStartNow;

  /// No description provided for @homeEmptyStateTitle.
  ///
  /// In ar, this message translates to:
  /// **'لا توجد تطبيقات متاحة بعد'**
  String get homeEmptyStateTitle;

  /// No description provided for @homeEmptyStateBody.
  ///
  /// In ar, this message translates to:
  /// **'تواصل مع صاحب المحل لإضافة صلاحياتك.'**
  String get homeEmptyStateBody;

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

  /// No description provided for @notificationsTitle.
  ///
  /// In ar, this message translates to:
  /// **'الإشعارات'**
  String get notificationsTitle;

  /// No description provided for @notificationsEmptyState.
  ///
  /// In ar, this message translates to:
  /// **'لا توجد إشعارات بعد'**
  String get notificationsEmptyState;

  /// No description provided for @notificationsAgoJustNow.
  ///
  /// In ar, this message translates to:
  /// **'الآن'**
  String get notificationsAgoJustNow;

  /// Minutes since a notification arrived
  ///
  /// In ar, this message translates to:
  /// **'قبل {n} دقيقة'**
  String notificationsAgoMinutes(int n);

  /// Hours since a notification arrived
  ///
  /// In ar, this message translates to:
  /// **'قبل {n} ساعة'**
  String notificationsAgoHours(int n);

  /// No description provided for @notificationsAgoYesterday.
  ///
  /// In ar, this message translates to:
  /// **'أمس'**
  String get notificationsAgoYesterday;

  /// Days since a notification arrived
  ///
  /// In ar, this message translates to:
  /// **'قبل {n} يوم'**
  String notificationsAgoDays(int n);

  /// No description provided for @accountPageTitle.
  ///
  /// In ar, this message translates to:
  /// **'حسابي'**
  String get accountPageTitle;

  /// No description provided for @accountLegalSectionTitle.
  ///
  /// In ar, this message translates to:
  /// **'قانوني'**
  String get accountLegalSectionTitle;

  /// No description provided for @accountTermsRow.
  ///
  /// In ar, this message translates to:
  /// **'الشروط والأحكام'**
  String get accountTermsRow;

  /// No description provided for @accountPrivacyRow.
  ///
  /// In ar, this message translates to:
  /// **'سياسة الخصوصية'**
  String get accountPrivacyRow;

  /// No description provided for @accountSignOutRow.
  ///
  /// In ar, this message translates to:
  /// **'تسجيل الخروج'**
  String get accountSignOutRow;

  /// No description provided for @accountSignOutConfirmTitle.
  ///
  /// In ar, this message translates to:
  /// **'تسجيل الخروج؟'**
  String get accountSignOutConfirmTitle;

  /// No description provided for @accountSignOutConfirmBody.
  ///
  /// In ar, this message translates to:
  /// **'بتحتاج تسجّل الدخول مرة ثانية للمتابعة.'**
  String get accountSignOutConfirmBody;

  /// No description provided for @accountSignOutCancel.
  ///
  /// In ar, this message translates to:
  /// **'إلغاء'**
  String get accountSignOutCancel;

  /// No description provided for @accountSignOutConfirm.
  ///
  /// In ar, this message translates to:
  /// **'تسجيل الخروج'**
  String get accountSignOutConfirm;

  /// No description provided for @accountNameFieldHint.
  ///
  /// In ar, this message translates to:
  /// **'اسمك'**
  String get accountNameFieldHint;

  /// No description provided for @accountSaveNameFailed.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر حفظ الاسم، حاول مرة ثانية.'**
  String get accountSaveNameFailed;

  /// No description provided for @accountShopSectionTitle.
  ///
  /// In ar, this message translates to:
  /// **'منشأتي'**
  String get accountShopSectionTitle;

  /// No description provided for @accountShopIdentityRow.
  ///
  /// In ar, this message translates to:
  /// **'منشأتي'**
  String get accountShopIdentityRow;

  /// No description provided for @shopIdentityPageTitle.
  ///
  /// In ar, this message translates to:
  /// **'منشأتي'**
  String get shopIdentityPageTitle;

  /// No description provided for @shopIdentityVehicleTitle.
  ///
  /// In ar, this message translates to:
  /// **'العمل على السيارات'**
  String get shopIdentityVehicleTitle;

  /// No description provided for @shopIdentityVehicleDesc.
  ///
  /// In ar, this message translates to:
  /// **'يفعّل حقل رقم اللوحة بشاشة تسجيل الزيارة لهذا المحل.'**
  String get shopIdentityVehicleDesc;

  /// No description provided for @shopIdentityVehicleSaveFailed.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر الحفظ، حاول مرة ثانية.'**
  String get shopIdentityVehicleSaveFailed;

  /// No description provided for @shopIdentityBrandTitle.
  ///
  /// In ar, this message translates to:
  /// **'اسم محلك وشعاره'**
  String get shopIdentityBrandTitle;

  /// No description provided for @shopIdentityCustomerPagePreview.
  ///
  /// In ar, this message translates to:
  /// **'هذا يظهر لعميلك'**
  String get shopIdentityCustomerPagePreview;

  /// No description provided for @shopIdentityNameLabel.
  ///
  /// In ar, this message translates to:
  /// **'اسم المحل'**
  String get shopIdentityNameLabel;

  /// No description provided for @shopIdentityUploadLogo.
  ///
  /// In ar, this message translates to:
  /// **'رفع شعار'**
  String get shopIdentityUploadLogo;

  /// No description provided for @shopIdentityChangeLogo.
  ///
  /// In ar, this message translates to:
  /// **'تغيير الشعار'**
  String get shopIdentityChangeLogo;

  /// No description provided for @shopIdentityRemoveLogo.
  ///
  /// In ar, this message translates to:
  /// **'إزالة'**
  String get shopIdentityRemoveLogo;

  /// No description provided for @shopIdentityColorLabel.
  ///
  /// In ar, this message translates to:
  /// **'لون محلك'**
  String get shopIdentityColorLabel;

  /// No description provided for @shopIdentityResetColor.
  ///
  /// In ar, this message translates to:
  /// **'استخدام الافتراضي'**
  String get shopIdentityResetColor;

  /// No description provided for @shopIdentitySave.
  ///
  /// In ar, this message translates to:
  /// **'حفظ'**
  String get shopIdentitySave;

  /// No description provided for @shopIdentityDefaultName.
  ///
  /// In ar, this message translates to:
  /// **'محلك'**
  String get shopIdentityDefaultName;

  /// No description provided for @shopIdentityLogoPickFailed.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر قراءة الصورة، جرّب صورة ثانية.'**
  String get shopIdentityLogoPickFailed;

  /// No description provided for @shopIdentityInvalidColor.
  ///
  /// In ar, this message translates to:
  /// **'أدخل لوناً صحيحاً، مثل #B08A3E'**
  String get shopIdentityInvalidColor;

  /// No description provided for @shopIdentitySaveFailed.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر الحفظ، حاول مرة ثانية.'**
  String get shopIdentitySaveFailed;

  /// No description provided for @shopIdentitySaved.
  ///
  /// In ar, this message translates to:
  /// **'تم الحفظ.'**
  String get shopIdentitySaved;

  /// No description provided for @shopIdentityBranchesRow.
  ///
  /// In ar, this message translates to:
  /// **'الفروع'**
  String get shopIdentityBranchesRow;

  /// No description provided for @branchesPageTitle.
  ///
  /// In ar, this message translates to:
  /// **'الفروع'**
  String get branchesPageTitle;

  /// No description provided for @branchesAddBranch.
  ///
  /// In ar, this message translates to:
  /// **'إضافة فرع'**
  String get branchesAddBranch;

  /// No description provided for @branchesActiveChip.
  ///
  /// In ar, this message translates to:
  /// **'نشط'**
  String get branchesActiveChip;

  /// No description provided for @branchesClosedChip.
  ///
  /// In ar, this message translates to:
  /// **'مغلق'**
  String get branchesClosedChip;

  /// No description provided for @branchesLoadFailed.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تحميل الفروع، اسحب للأسفل لإعادة المحاولة.'**
  String get branchesLoadFailed;

  /// No description provided for @branchesLimitReached.
  ///
  /// In ar, this message translates to:
  /// **'باقتك الحالية لا تسمح بإضافة فرع آخر.'**
  String get branchesLimitReached;

  /// No description provided for @branchesNameRequired.
  ///
  /// In ar, this message translates to:
  /// **'اسم الفرع مطلوب'**
  String get branchesNameRequired;

  /// No description provided for @branchesNameLabel.
  ///
  /// In ar, this message translates to:
  /// **'اسم الفرع'**
  String get branchesNameLabel;

  /// No description provided for @branchesCityLabel.
  ///
  /// In ar, this message translates to:
  /// **'المدينة'**
  String get branchesCityLabel;

  /// No description provided for @branchesLocationHint.
  ///
  /// In ar, this message translates to:
  /// **'الصق رابط الموقع من خرائط جوجل (اختياري بالفرع الأول، إلزامي من الفرع الثاني)'**
  String get branchesLocationHint;

  /// No description provided for @branchesMapsLinkLabel.
  ///
  /// In ar, this message translates to:
  /// **'رابط خرائط جوجل'**
  String get branchesMapsLinkLabel;

  /// No description provided for @branchesMapsLinkInvalid.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر قراءة الرابط، تأكد إنه رابط من خرائط جوجل.'**
  String get branchesMapsLinkInvalid;

  /// No description provided for @branchesMapsLinkShort.
  ///
  /// In ar, this message translates to:
  /// **'الصق الرابط الكامل من خرائط جوجل، لا الرابط المختصر.'**
  String get branchesMapsLinkShort;

  /// No description provided for @branchesLocationRequired.
  ///
  /// In ar, this message translates to:
  /// **'حدّد موقع الفرع على الخريطة — لازم من الفرع الثاني فأكثر.'**
  String get branchesLocationRequired;

  /// No description provided for @branchesSaveFailed.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر الحفظ، حاول مرة ثانية.'**
  String get branchesSaveFailed;

  /// No description provided for @branchesStatusLabel.
  ///
  /// In ar, this message translates to:
  /// **'حالة الفرع'**
  String get branchesStatusLabel;

  /// No description provided for @branchesMainCannotClose.
  ///
  /// In ar, this message translates to:
  /// **'الفرع الرئيسي لا يُغلق، يمكنك تغيير اسمه فقط.'**
  String get branchesMainCannotClose;

  /// No description provided for @branchesWhatsappTitle.
  ///
  /// In ar, this message translates to:
  /// **'ربط واتساب'**
  String get branchesWhatsappTitle;

  /// No description provided for @branchesWhatsappNotStarted.
  ///
  /// In ar, this message translates to:
  /// **'لم تبدأ الربط بعد'**
  String get branchesWhatsappNotStarted;

  /// No description provided for @branchesWhatsappConnected.
  ///
  /// In ar, this message translates to:
  /// **'مربوط ويعمل'**
  String get branchesWhatsappConnected;

  /// No description provided for @branchesWhatsappCannotSend.
  ///
  /// In ar, this message translates to:
  /// **'مربوط لكن فيه مشكلة بالإرسال'**
  String get branchesWhatsappCannotSend;

  /// No description provided for @branchesTeamTitle.
  ///
  /// In ar, this message translates to:
  /// **'فريق الفرع'**
  String get branchesTeamTitle;

  /// No description provided for @branchesTeamEmpty.
  ///
  /// In ar, this message translates to:
  /// **'لا يوجد أعضاء بهذا الفرع بعد.'**
  String get branchesTeamEmpty;

  /// No description provided for @branchesAddMember.
  ///
  /// In ar, this message translates to:
  /// **'إضافة عضو'**
  String get branchesAddMember;

  /// No description provided for @branchesMemberNameLabel.
  ///
  /// In ar, this message translates to:
  /// **'اسم الموظف'**
  String get branchesMemberNameLabel;

  /// No description provided for @branchesMemberPhoneLabel.
  ///
  /// In ar, this message translates to:
  /// **'رقم جواله'**
  String get branchesMemberPhoneLabel;

  /// No description provided for @branchesMemberPasswordLabel.
  ///
  /// In ar, this message translates to:
  /// **'كلمة مرور دخوله'**
  String get branchesMemberPasswordLabel;

  /// No description provided for @branchesMemberRoleLabel.
  ///
  /// In ar, this message translates to:
  /// **'الصلاحية'**
  String get branchesMemberRoleLabel;

  /// No description provided for @branchesRoleOperator.
  ///
  /// In ar, this message translates to:
  /// **'موظف ميداني'**
  String get branchesRoleOperator;

  /// No description provided for @branchesRoleSupervisor.
  ///
  /// In ar, this message translates to:
  /// **'مشرف وردية'**
  String get branchesRoleSupervisor;

  /// No description provided for @branchesRoleManager.
  ///
  /// In ar, this message translates to:
  /// **'مدير'**
  String get branchesRoleManager;

  /// No description provided for @branchesSeatLimit.
  ///
  /// In ar, this message translates to:
  /// **'باقتك الحالية لا تسمح بإضافة موظف آخر.'**
  String get branchesSeatLimit;

  /// No description provided for @branchesHireFailed.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر إضافة الموظف، حاول مرة ثانية.'**
  String get branchesHireFailed;

  /// No description provided for @accountSecuritySectionTitle.
  ///
  /// In ar, this message translates to:
  /// **'الأمان'**
  String get accountSecuritySectionTitle;

  /// No description provided for @accountChangePasswordRow.
  ///
  /// In ar, this message translates to:
  /// **'تغيير كلمة المرور'**
  String get accountChangePasswordRow;

  /// No description provided for @accountChangePasswordFailed.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تغيير كلمة المرور، حاول مرة ثانية.'**
  String get accountChangePasswordFailed;

  /// No description provided for @accountChangePasswordSuccess.
  ///
  /// In ar, this message translates to:
  /// **'تم تغيير كلمة المرور.'**
  String get accountChangePasswordSuccess;

  /// No description provided for @accountCurrentPasswordLabel.
  ///
  /// In ar, this message translates to:
  /// **'كلمة المرور الحالية'**
  String get accountCurrentPasswordLabel;

  /// No description provided for @accountNewPasswordLabel.
  ///
  /// In ar, this message translates to:
  /// **'كلمة المرور الجديدة'**
  String get accountNewPasswordLabel;

  /// No description provided for @accountConfirmNewPasswordLabel.
  ///
  /// In ar, this message translates to:
  /// **'تأكيد كلمة المرور الجديدة'**
  String get accountConfirmNewPasswordLabel;

  /// No description provided for @branchesIncreaseCapacity.
  ///
  /// In ar, this message translates to:
  /// **'زيادة السعة'**
  String get branchesIncreaseCapacity;

  /// No description provided for @accountBillingSectionTitle.
  ///
  /// In ar, this message translates to:
  /// **'الفوترة'**
  String get accountBillingSectionTitle;

  /// No description provided for @accountBillingRow.
  ///
  /// In ar, this message translates to:
  /// **'الاشتراك والفواتير'**
  String get accountBillingRow;

  /// No description provided for @billingPageTitle.
  ///
  /// In ar, this message translates to:
  /// **'الفوترة'**
  String get billingPageTitle;

  /// No description provided for @billingLoadFailed.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تحميل بيانات الفوترة، اسحب للأسفل للمحاولة.'**
  String get billingLoadFailed;

  /// No description provided for @billingAllGood.
  ///
  /// In ar, this message translates to:
  /// **'فوترتك بحالة جيدة، لا شيء يحتاج انتباهك الآن.'**
  String get billingAllGood;

  /// No description provided for @billingPastDue.
  ///
  /// In ar, this message translates to:
  /// **'عندك فاتورة متأخرة السداد — سدّدها لتفادي إيقاف خدماتك.'**
  String get billingPastDue;

  /// No description provided for @billingUsageSectionTitle.
  ///
  /// In ar, this message translates to:
  /// **'استخدامك'**
  String get billingUsageSectionTitle;

  /// No description provided for @billingUsageStaffSeats.
  ///
  /// In ar, this message translates to:
  /// **'مقاعد الموظفين'**
  String get billingUsageStaffSeats;

  /// No description provided for @billingUsageBranches.
  ///
  /// In ar, this message translates to:
  /// **'الفروع'**
  String get billingUsageBranches;

  /// No description provided for @billingUsageUnlimited.
  ///
  /// In ar, this message translates to:
  /// **'غير محدود'**
  String get billingUsageUnlimited;

  /// No description provided for @billingMyAppsSectionTitle.
  ///
  /// In ar, this message translates to:
  /// **'تطبيقاتي المشتركة'**
  String get billingMyAppsSectionTitle;

  /// No description provided for @billingStatusActive.
  ///
  /// In ar, this message translates to:
  /// **'نشط'**
  String get billingStatusActive;

  /// No description provided for @billingStatusStopping.
  ///
  /// In ar, this message translates to:
  /// **'سيتوقف التجديد'**
  String get billingStatusStopping;

  /// No description provided for @billingRenewsOn.
  ///
  /// In ar, this message translates to:
  /// **'يتجدد في {date}'**
  String billingRenewsOn(Object date);

  /// No description provided for @billingStopRenewal.
  ///
  /// In ar, this message translates to:
  /// **'إيقاف التجديد'**
  String get billingStopRenewal;

  /// No description provided for @billingUndoStopRenewal.
  ///
  /// In ar, this message translates to:
  /// **'تراجع عن الإيقاف'**
  String get billingUndoStopRenewal;

  /// No description provided for @billingRenewNow.
  ///
  /// In ar, this message translates to:
  /// **'جدّد الآن'**
  String get billingRenewNow;

  /// No description provided for @billingActionFailed.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تنفيذ الطلب، حاول مرة أخرى.'**
  String get billingActionFailed;

  /// No description provided for @billingRenewalPreviewSectionTitle.
  ///
  /// In ar, this message translates to:
  /// **'معاينة التجديد القادم'**
  String get billingRenewalPreviewSectionTitle;

  /// No description provided for @billingRenewalPreviewNextChargeOn.
  ///
  /// In ar, this message translates to:
  /// **'أقرب خصم في {date}'**
  String billingRenewalPreviewNextChargeOn(Object date);

  /// No description provided for @billingRenewalPreviewNoDate.
  ///
  /// In ar, this message translates to:
  /// **'لا يوجد تاريخ تجديد قادم بعد.'**
  String get billingRenewalPreviewNoDate;

  /// No description provided for @billingRenewalPreviewSubtotal.
  ///
  /// In ar, this message translates to:
  /// **'المجموع الفرعي'**
  String get billingRenewalPreviewSubtotal;

  /// No description provided for @billingRenewalPreviewSavings.
  ///
  /// In ar, this message translates to:
  /// **'التوفير'**
  String get billingRenewalPreviewSavings;

  /// No description provided for @billingRenewalPreviewTax.
  ///
  /// In ar, this message translates to:
  /// **'الضريبة'**
  String get billingRenewalPreviewTax;

  /// No description provided for @billingRenewalPreviewTotal.
  ///
  /// In ar, this message translates to:
  /// **'الإجمالي'**
  String get billingRenewalPreviewTotal;

  /// No description provided for @billingInvoicesSectionTitle.
  ///
  /// In ar, this message translates to:
  /// **'الفواتير'**
  String get billingInvoicesSectionTitle;

  /// No description provided for @billingInvoicesEmpty.
  ///
  /// In ar, this message translates to:
  /// **'لا توجد فواتير بعد.'**
  String get billingInvoicesEmpty;

  /// No description provided for @billingInvoiceStatusPaid.
  ///
  /// In ar, this message translates to:
  /// **'مسدّدة'**
  String get billingInvoiceStatusPaid;

  /// No description provided for @billingInvoiceStatusOpen.
  ///
  /// In ar, this message translates to:
  /// **'غير مسدّدة'**
  String get billingInvoiceStatusOpen;

  /// No description provided for @billingInvoiceStatusPartiallyPaid.
  ///
  /// In ar, this message translates to:
  /// **'مسدّدة جزئيًا'**
  String get billingInvoiceStatusPartiallyPaid;

  /// No description provided for @billingInvoiceStatusVoid.
  ///
  /// In ar, this message translates to:
  /// **'ملغاة'**
  String get billingInvoiceStatusVoid;

  /// No description provided for @billingInvoiceStatusUncollectible.
  ///
  /// In ar, this message translates to:
  /// **'غير قابلة للتحصيل'**
  String get billingInvoiceStatusUncollectible;

  /// No description provided for @billingInvoiceStatusDraft.
  ///
  /// In ar, this message translates to:
  /// **'مسودة'**
  String get billingInvoiceStatusDraft;

  /// No description provided for @billingPayNow.
  ///
  /// In ar, this message translates to:
  /// **'ادفع الآن'**
  String get billingPayNow;

  /// No description provided for @billingPayLinkFailed.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر إنشاء رابط الدفع، حاول مرة أخرى.'**
  String get billingPayLinkFailed;

  /// No description provided for @billingCancelConfirmTitle.
  ///
  /// In ar, this message translates to:
  /// **'إيقاف التجديد؟'**
  String get billingCancelConfirmTitle;

  /// No description provided for @billingCancelConfirmBody.
  ///
  /// In ar, this message translates to:
  /// **'ستستمر الخدمة حتى نهاية الفترة الحالية، ثم لن تتجدد.'**
  String get billingCancelConfirmBody;

  /// No description provided for @billingCancelConfirmAction.
  ///
  /// In ar, this message translates to:
  /// **'إيقاف التجديد'**
  String get billingCancelConfirmAction;

  /// No description provided for @visitOfferApplyLabel.
  ///
  /// In ar, this message translates to:
  /// **'طبّق هذا العرض على هذي الزيارة'**
  String get visitOfferApplyLabel;

  /// No description provided for @visitPointsRedeemCost.
  ///
  /// In ar, this message translates to:
  /// **'{cost} نقطة'**
  String visitPointsRedeemCost(Object cost);

  /// No description provided for @visitPointsRedeemedMessage.
  ///
  /// In ar, this message translates to:
  /// **'تم استبدال {name} ✓'**
  String visitPointsRedeemedMessage(Object name);

  /// No description provided for @visitPointsRedeemFailed.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر الاستبدال، حاول مرة ثانية.'**
  String get visitPointsRedeemFailed;

  /// No description provided for @readBillingActiveCount.
  ///
  /// In ar, this message translates to:
  /// **'عندك {count} اشتراك نشط.'**
  String readBillingActiveCount(Object count);

  /// No description provided for @readBillingNone.
  ///
  /// In ar, this message translates to:
  /// **'ما عندك أي اشتراك نشط حاليًا.'**
  String get readBillingNone;

  /// No description provided for @readBillingRenewsSoon.
  ///
  /// In ar, this message translates to:
  /// **'أقرب تجديد يوم {date}.'**
  String readBillingRenewsSoon(Object date);

  /// No description provided for @readBillingFailed.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر جلب حالة الفوترة الآن، حاول مرة ثانية.'**
  String get readBillingFailed;

  /// No description provided for @readBranchCount.
  ///
  /// In ar, this message translates to:
  /// **'عندك {count} فرع.'**
  String readBranchCount(Object count);

  /// No description provided for @readBranchFailed.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر جلب عدد الفروع الآن، حاول مرة ثانية.'**
  String get readBranchFailed;

  /// No description provided for @readVehicleTrackingOn.
  ///
  /// In ar, this message translates to:
  /// **'العمل على السيارات مفعّل الآن.'**
  String get readVehicleTrackingOn;

  /// No description provided for @readVehicleTrackingOff.
  ///
  /// In ar, this message translates to:
  /// **'العمل على السيارات غير مفعّل حاليًا.'**
  String get readVehicleTrackingOff;

  /// No description provided for @readVehicleTrackingFailed.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر التأكد من حالة تتبع السيارات الآن، حاول مرة ثانية.'**
  String get readVehicleTrackingFailed;

  /// No description provided for @writeVehicleTrackingEnabledConfirm.
  ///
  /// In ar, this message translates to:
  /// **'بيفعّل خانة رقم اللوحة بشاشة تسجيل الزيارة لهذا المحل. تأكيد؟'**
  String get writeVehicleTrackingEnabledConfirm;

  /// No description provided for @writeVehicleTrackingDisabledConfirm.
  ///
  /// In ar, this message translates to:
  /// **'بيوقف خانة رقم اللوحة بشاشة تسجيل الزيارة لهذا المحل. تأكيد؟'**
  String get writeVehicleTrackingDisabledConfirm;

  /// No description provided for @writeVehicleTrackingEnabledDone.
  ///
  /// In ar, this message translates to:
  /// **'تم تفعيل العمل على السيارات ✓'**
  String get writeVehicleTrackingEnabledDone;

  /// No description provided for @writeVehicleTrackingDisabledDone.
  ///
  /// In ar, this message translates to:
  /// **'تم إيقاف العمل على السيارات ✓'**
  String get writeVehicleTrackingDisabledDone;

  /// No description provided for @writeVehicleTrackingFailed.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تغيير إعداد تتبع السيارات، حاول مرة ثانية.'**
  String get writeVehicleTrackingFailed;
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
