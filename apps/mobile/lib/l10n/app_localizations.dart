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

  /// No description provided for @assistantRetryDownload.
  ///
  /// In ar, this message translates to:
  /// **'إعادة المحاولة'**
  String get assistantRetryDownload;

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

  /// No description provided for @assistantReplySettingsTooltip.
  ///
  /// In ar, this message translates to:
  /// **'إعدادات الرد'**
  String get assistantReplySettingsTooltip;

  /// No description provided for @assistantReplyModeTitle.
  ///
  /// In ar, this message translates to:
  /// **'طريقة رد المساعد'**
  String get assistantReplyModeTitle;

  /// No description provided for @assistantReplyModeSubtitle.
  ///
  /// In ar, this message translates to:
  /// **'يحكم هذا كل رد، حتى لو سألته بصوتك'**
  String get assistantReplyModeSubtitle;

  /// No description provided for @assistantReplyModeVoice.
  ///
  /// In ar, this message translates to:
  /// **'صوت'**
  String get assistantReplyModeVoice;

  /// No description provided for @assistantReplyModeText.
  ///
  /// In ar, this message translates to:
  /// **'نص مكتوب'**
  String get assistantReplyModeText;

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
  /// **'متجر التطبيقات'**
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

  /// No description provided for @branchesRoleMarketer.
  ///
  /// In ar, this message translates to:
  /// **'مسؤول التسويق'**
  String get branchesRoleMarketer;

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

  /// No description provided for @branchesVisibleAllHint.
  ///
  /// In ar, this message translates to:
  /// **'يشوف كل الفروع'**
  String get branchesVisibleAllHint;

  /// branchesVisibleSomeHint
  ///
  /// In ar, this message translates to:
  /// **'يشوف {count} فروع'**
  String branchesVisibleSomeHint(int count);

  /// No description provided for @branchesEditMember.
  ///
  /// In ar, this message translates to:
  /// **'تعديل الموظف'**
  String get branchesEditMember;

  /// No description provided for @branchesMemberStopped.
  ///
  /// In ar, this message translates to:
  /// **'متوقف'**
  String get branchesMemberStopped;

  /// No description provided for @branchesMemberStationLabel.
  ///
  /// In ar, this message translates to:
  /// **'الفرع اللي يشتغل فيه'**
  String get branchesMemberStationLabel;

  /// No description provided for @branchesMemberVisibilityLabel.
  ///
  /// In ar, this message translates to:
  /// **'أي فروع يقدر يشوفها'**
  String get branchesMemberVisibilityLabel;

  /// No description provided for @branchesVisibilityOwnOnly.
  ///
  /// In ar, this message translates to:
  /// **'فرعه بس'**
  String get branchesVisibilityOwnOnly;

  /// No description provided for @branchesVisibilitySome.
  ///
  /// In ar, this message translates to:
  /// **'فروع محددة'**
  String get branchesVisibilitySome;

  /// No description provided for @branchesVisibilityAll.
  ///
  /// In ar, this message translates to:
  /// **'كل الفروع'**
  String get branchesVisibilityAll;

  /// No description provided for @branchesWorkingHours.
  ///
  /// In ar, this message translates to:
  /// **'ساعات العمل'**
  String get branchesWorkingHours;

  /// No description provided for @branchesStopMember.
  ///
  /// In ar, this message translates to:
  /// **'إيقاف الموظف'**
  String get branchesStopMember;

  /// No description provided for @branchesStopMemberTitle.
  ///
  /// In ar, this message translates to:
  /// **'إيقاف هذا الموظف؟'**
  String get branchesStopMemberTitle;

  /// branchesStopMemberBody
  ///
  /// In ar, this message translates to:
  /// **'بيفقد {name} القدرة على الدخول للتطبيق فورًا. سجل زياراته وتاريخه يبقى محفوظًا.'**
  String branchesStopMemberBody(String name);

  /// No description provided for @branchesStopMemberConfirm.
  ///
  /// In ar, this message translates to:
  /// **'إيقاف'**
  String get branchesStopMemberConfirm;

  /// No description provided for @branchesReactivateMember.
  ///
  /// In ar, this message translates to:
  /// **'إعادة تفعيل'**
  String get branchesReactivateMember;

  /// No description provided for @branchesRehireRequired.
  ///
  /// In ar, this message translates to:
  /// **'هذا الموظف متوقف تمامًا — التفعيل يحتاج توظيفه من جديد، مو مجرد تشغيل.'**
  String get branchesRehireRequired;

  /// No description provided for @branchesHoursSaved.
  ///
  /// In ar, this message translates to:
  /// **'تم حفظ ساعات العمل.'**
  String get branchesHoursSaved;

  /// No description provided for @branchesHoursExceedsShop.
  ///
  /// In ar, this message translates to:
  /// **'هذي الساعات أوسع من ساعات عمل المحل نفسه — عدّلها.'**
  String get branchesHoursExceedsShop;

  /// No description provided for @branchesHoursHint.
  ///
  /// In ar, this message translates to:
  /// **'لو ما عدّلت شي، يشتغل بنفس ساعات المحل تلقائيًا.'**
  String get branchesHoursHint;

  /// No description provided for @branchesHoursClear.
  ///
  /// In ar, this message translates to:
  /// **'رجّعه لساعات المحل الافتراضية'**
  String get branchesHoursClear;

  /// No description provided for @branchesDayMonday.
  ///
  /// In ar, this message translates to:
  /// **'الاثنين'**
  String get branchesDayMonday;

  /// No description provided for @branchesDayTuesday.
  ///
  /// In ar, this message translates to:
  /// **'الثلاثاء'**
  String get branchesDayTuesday;

  /// No description provided for @branchesDayWednesday.
  ///
  /// In ar, this message translates to:
  /// **'الأربعاء'**
  String get branchesDayWednesday;

  /// No description provided for @branchesDayThursday.
  ///
  /// In ar, this message translates to:
  /// **'الخميس'**
  String get branchesDayThursday;

  /// No description provided for @branchesDayFriday.
  ///
  /// In ar, this message translates to:
  /// **'الجمعة'**
  String get branchesDayFriday;

  /// No description provided for @branchesDaySaturday.
  ///
  /// In ar, this message translates to:
  /// **'السبت'**
  String get branchesDaySaturday;

  /// No description provided for @branchesDaySunday.
  ///
  /// In ar, this message translates to:
  /// **'الأحد'**
  String get branchesDaySunday;

  /// No description provided for @branchesDayClosed.
  ///
  /// In ar, this message translates to:
  /// **'مغلق'**
  String get branchesDayClosed;

  /// No description provided for @accountLanguageSectionTitle.
  ///
  /// In ar, this message translates to:
  /// **'اللغة'**
  String get accountLanguageSectionTitle;

  /// No description provided for @accountLanguageRow.
  ///
  /// In ar, this message translates to:
  /// **'لغة التطبيق'**
  String get accountLanguageRow;

  /// No description provided for @accountLanguageSheetTitle.
  ///
  /// In ar, this message translates to:
  /// **'اختر لغة التطبيق'**
  String get accountLanguageSheetTitle;

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

  /// No description provided for @billingPaymentConfirming.
  ///
  /// In ar, this message translates to:
  /// **'استلمنا محاولة دفعك ونتأكد منها الآن — قد يستغرق هذا حتى 20 دقيقة.'**
  String get billingPaymentConfirming;

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

  /// No description provided for @paymentPageLoadFailed.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تحميل صفحة الدفع. تحقق من اتصالك ثم أعد المحاولة.'**
  String get paymentPageLoadFailed;

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

  /// No description provided for @visitPointsOneBenefitOnly.
  ///
  /// In ar, this message translates to:
  /// **'فائدة واحدة لكل زيارة — اختيار النقاط يلغي العرض التلقائي.'**
  String get visitPointsOneBenefitOnly;

  /// No description provided for @visitPointsRedeemedMessage.
  ///
  /// In ar, this message translates to:
  /// **'تم استبدال {name} ✓'**
  String visitPointsRedeemedMessage(Object name);

  /// No description provided for @visitPointsChosenMessage.
  ///
  /// In ar, this message translates to:
  /// **'اخترت: {name} — سيُستخدم بدل العرض عند الحفظ'**
  String visitPointsChosenMessage(Object name);

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

  /// mobileRequestsTitle
  ///
  /// In ar, this message translates to:
  /// **'خدمات متنقلة'**
  String get mobileRequestsTitle;

  /// mobileRequestsSubtitle
  ///
  /// In ar, this message translates to:
  /// **'طلبات خدمة تصل للعميل، من الاستلام للتنفيذ.'**
  String get mobileRequestsSubtitle;

  /// mobileRequestsKpiPending
  ///
  /// In ar, this message translates to:
  /// **'بانتظار قرار'**
  String get mobileRequestsKpiPending;

  /// mobileRequestsKpiNeedsDecision
  ///
  /// In ar, this message translates to:
  /// **'تحتاج قرار'**
  String get mobileRequestsKpiNeedsDecision;

  /// mobileRequestsKpiCompletedMonth
  ///
  /// In ar, this message translates to:
  /// **'تمّت هذا الشهر'**
  String get mobileRequestsKpiCompletedMonth;

  /// mobileRequestsBannerGo
  ///
  /// In ar, this message translates to:
  /// **'عرضها'**
  String get mobileRequestsBannerGo;

  /// mobileRequestsFilterAll
  ///
  /// In ar, this message translates to:
  /// **'الكل'**
  String get mobileRequestsFilterAll;

  /// mobileRequestsFilterPending
  ///
  /// In ar, this message translates to:
  /// **'بانتظار قرار'**
  String get mobileRequestsFilterPending;

  /// mobileRequestsFilterAccepted
  ///
  /// In ar, this message translates to:
  /// **'مقبولة'**
  String get mobileRequestsFilterAccepted;

  /// mobileRequestsFilterNeedsDecision
  ///
  /// In ar, this message translates to:
  /// **'تحتاج قرار'**
  String get mobileRequestsFilterNeedsDecision;

  /// mobileRequestsFilterCompleted
  ///
  /// In ar, this message translates to:
  /// **'تمّت'**
  String get mobileRequestsFilterCompleted;

  /// mobileRequestsFilterClosed
  ///
  /// In ar, this message translates to:
  /// **'مغلقة'**
  String get mobileRequestsFilterClosed;

  /// mobileRequestsSearchHint
  ///
  /// In ar, this message translates to:
  /// **'ابحث بالاسم أو الجوال'**
  String get mobileRequestsSearchHint;

  /// mobileRequestsLoadFailedTitle
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تحميل الطلبات'**
  String get mobileRequestsLoadFailedTitle;

  /// mobileRequestsLoadFailedBody
  ///
  /// In ar, this message translates to:
  /// **'تحقّق من اتصالك وحاول مرة أخرى.'**
  String get mobileRequestsLoadFailedBody;

  /// mobileRequestsRetry
  ///
  /// In ar, this message translates to:
  /// **'إعادة المحاولة'**
  String get mobileRequestsRetry;

  /// mobileRequestsEmptyTitle
  ///
  /// In ar, this message translates to:
  /// **'لا طلبات بعد'**
  String get mobileRequestsEmptyTitle;

  /// mobileRequestsEmptyBody
  ///
  /// In ar, this message translates to:
  /// **'طلبات الخدمة المتنقلة من عملائك تظهر هنا.'**
  String get mobileRequestsEmptyBody;

  /// mobileRequestsStatusPending
  ///
  /// In ar, this message translates to:
  /// **'بانتظار قرار'**
  String get mobileRequestsStatusPending;

  /// mobileRequestsStatusAccepted
  ///
  /// In ar, this message translates to:
  /// **'مقبول'**
  String get mobileRequestsStatusAccepted;

  /// mobileRequestsStatusNeedsDecision
  ///
  /// In ar, this message translates to:
  /// **'تحتاج قرار'**
  String get mobileRequestsStatusNeedsDecision;

  /// mobileRequestsStatusCompleted
  ///
  /// In ar, this message translates to:
  /// **'تمّ'**
  String get mobileRequestsStatusCompleted;

  /// mobileRequestsStatusNoShow
  ///
  /// In ar, this message translates to:
  /// **'لم يحضر'**
  String get mobileRequestsStatusNoShow;

  /// mobileRequestsStatusRejected
  ///
  /// In ar, this message translates to:
  /// **'مرفوض'**
  String get mobileRequestsStatusRejected;

  /// mobileRequestsUnnamed
  ///
  /// In ar, this message translates to:
  /// **'بدون اسم'**
  String get mobileRequestsUnnamed;

  /// mobileRequestsOpenMap
  ///
  /// In ar, this message translates to:
  /// **'الموقع'**
  String get mobileRequestsOpenMap;

  /// mobileRequestsPhoneCopied
  ///
  /// In ar, this message translates to:
  /// **'تم نسخ رقم الجوال'**
  String get mobileRequestsPhoneCopied;

  /// mobileRequestsRiskyCustomer
  ///
  /// In ar, this message translates to:
  /// **'عميل عالي خطر عدم الحضور'**
  String get mobileRequestsRiskyCustomer;

  /// mobileRequestsRejectReasonLine
  ///
  /// In ar, this message translates to:
  /// **'سبب الرفض: {reason}'**
  String mobileRequestsRejectReasonLine(Object reason);

  /// mobileRequestsActionAccept
  ///
  /// In ar, this message translates to:
  /// **'قبول'**
  String get mobileRequestsActionAccept;

  /// mobileRequestsActionReject
  ///
  /// In ar, this message translates to:
  /// **'رفض'**
  String get mobileRequestsActionReject;

  /// mobileRequestsActionComplete
  ///
  /// In ar, this message translates to:
  /// **'تمّ'**
  String get mobileRequestsActionComplete;

  /// mobileRequestsActionNoShow
  ///
  /// In ar, this message translates to:
  /// **'لم يحضر'**
  String get mobileRequestsActionNoShow;

  /// mobileRequestsAssignUnassigned
  ///
  /// In ar, this message translates to:
  /// **'غير مُسنَد'**
  String get mobileRequestsAssignUnassigned;

  /// mobileRequestsActionFailed
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تنفيذ الإجراء، حاول مرة أخرى.'**
  String get mobileRequestsActionFailed;

  /// mobileRequestsRejectTitle
  ///
  /// In ar, this message translates to:
  /// **'سبب الرفض'**
  String get mobileRequestsRejectTitle;

  /// mobileRequestsRejectHint
  ///
  /// In ar, this message translates to:
  /// **'اختياري'**
  String get mobileRequestsRejectHint;

  /// mobileRequestsRejectCancel
  ///
  /// In ar, this message translates to:
  /// **'إلغاء'**
  String get mobileRequestsRejectCancel;

  /// mobileRequestsRejectConfirm
  ///
  /// In ar, this message translates to:
  /// **'رفض الطلب'**
  String get mobileRequestsRejectConfirm;

  /// mobileRequestsAddOpen
  ///
  /// In ar, this message translates to:
  /// **'إضافة طلب'**
  String get mobileRequestsAddOpen;

  /// mobileRequestsAddTitle
  ///
  /// In ar, this message translates to:
  /// **'إضافة طلب خدمة متنقلة'**
  String get mobileRequestsAddTitle;

  /// mobileRequestsAddPhoneLabel
  ///
  /// In ar, this message translates to:
  /// **'جوال العميل'**
  String get mobileRequestsAddPhoneLabel;

  /// mobileRequestsAddNameLabel
  ///
  /// In ar, this message translates to:
  /// **'اسم العميل (اختياري)'**
  String get mobileRequestsAddNameLabel;

  /// mobileRequestsAddServicesLabel
  ///
  /// In ar, this message translates to:
  /// **'الخدمات'**
  String get mobileRequestsAddServicesLabel;

  /// mobileRequestsAddServicesEmpty
  ///
  /// In ar, this message translates to:
  /// **'لا خدمات متاحة بعد.'**
  String get mobileRequestsAddServicesEmpty;

  /// mobileRequestsAddDayLabel
  ///
  /// In ar, this message translates to:
  /// **'اليوم'**
  String get mobileRequestsAddDayLabel;

  /// mobileRequestsAddTimeLabel
  ///
  /// In ar, this message translates to:
  /// **'الوقت'**
  String get mobileRequestsAddTimeLabel;

  /// mobileRequestsAddMapsLinkLabel
  ///
  /// In ar, this message translates to:
  /// **'رابط الموقع من خرائط جوجل'**
  String get mobileRequestsAddMapsLinkLabel;

  /// mobileRequestsAddMapsLinkHint
  ///
  /// In ar, this message translates to:
  /// **'يقبل الرابط الكامل أو المختصر من خرائط جوجل.'**
  String get mobileRequestsAddMapsLinkHint;

  /// mobileRequestsAddMapsLinkShort
  ///
  /// In ar, this message translates to:
  /// **'هذا رابط مختصر — الصق الرابط الكامل من خرائط جوجل.'**
  String get mobileRequestsAddMapsLinkShort;

  /// mobileRequestsAddMapsLinkInvalid
  ///
  /// In ar, this message translates to:
  /// **'تعذّر قراءة موقع من هذا الرابط.'**
  String get mobileRequestsAddMapsLinkInvalid;

  /// mobileRequestsAddAssignLabel
  ///
  /// In ar, this message translates to:
  /// **'إسناد إلى (اختياري)'**
  String get mobileRequestsAddAssignLabel;

  /// mobileRequestsAddCancel
  ///
  /// In ar, this message translates to:
  /// **'إلغاء'**
  String get mobileRequestsAddCancel;

  /// mobileRequestsAddSubmit
  ///
  /// In ar, this message translates to:
  /// **'إضافة الطلب'**
  String get mobileRequestsAddSubmit;

  /// mobileRequestsAddSubmitting
  ///
  /// In ar, this message translates to:
  /// **'جارٍ الإضافة...'**
  String get mobileRequestsAddSubmitting;

  /// mobileRequestsAddError
  ///
  /// In ar, this message translates to:
  /// **'تعذّرت إضافة الطلب، حاول مرة أخرى.'**
  String get mobileRequestsAddError;

  /// Warning banner: N requests overdue a decision
  ///
  /// In ar, this message translates to:
  /// **'{count, plural, one{طلب واحد يحتاج قرارك الآن} other{{count} طلبات تحتاج قرارك الآن}}'**
  String mobileRequestsBannerText(int count);

  /// mobileRequestsAddMapsLinkResolving
  ///
  /// In ar, this message translates to:
  /// **'جارٍ قراءة الموقع من الرابط...'**
  String get mobileRequestsAddMapsLinkResolving;

  /// customersTitle
  ///
  /// In ar, this message translates to:
  /// **'جهات الاتصال'**
  String get customersTitle;

  /// customersAddOpen
  ///
  /// In ar, this message translates to:
  /// **'إضافة عميل'**
  String get customersAddOpen;

  /// customersSearchHint
  ///
  /// In ar, this message translates to:
  /// **'ابحث بالاسم أو الجوال'**
  String get customersSearchHint;

  /// customersTabAll
  ///
  /// In ar, this message translates to:
  /// **'الكل'**
  String get customersTabAll;

  /// customersTabOverdue
  ///
  /// In ar, this message translates to:
  /// **'من تأخّر'**
  String get customersTabOverdue;

  /// customersSearchFailedTitle
  ///
  /// In ar, this message translates to:
  /// **'تعذّر البحث الآن'**
  String get customersSearchFailedTitle;

  /// customersSearchFailedBody
  ///
  /// In ar, this message translates to:
  /// **'حاول مرة أخرى بعد قليل.'**
  String get customersSearchFailedBody;

  /// customersSearchEmpty
  ///
  /// In ar, this message translates to:
  /// **'لا نتائج'**
  String get customersSearchEmpty;

  /// customersLoadFailedTitle
  ///
  /// In ar, this message translates to:
  /// **'تعذّر التحميل'**
  String get customersLoadFailedTitle;

  /// customersEmptyTitle
  ///
  /// In ar, this message translates to:
  /// **'لا عملاء بعد'**
  String get customersEmptyTitle;

  /// customersOverdueEmpty
  ///
  /// In ar, this message translates to:
  /// **'لا أحد متأخر حالياً'**
  String get customersOverdueEmpty;

  /// customersUnnamed
  ///
  /// In ar, this message translates to:
  /// **'بلا اسم'**
  String get customersUnnamed;

  /// customersVisitCount
  ///
  /// In ar, this message translates to:
  /// **'{count, plural, one{زيارة واحدة} two{زيارتان} other{{count} زيارة}}'**
  String customersVisitCount(int count);

  /// customersOverdueBadge
  ///
  /// In ar, this message translates to:
  /// **'متأخر'**
  String get customersOverdueBadge;

  /// customersStatEveryDays
  ///
  /// In ar, this message translates to:
  /// **'{days, plural, one{كل يوم} two{كل يومين} other{كل {days} يوم}}'**
  String customersStatEveryDays(int days);

  /// customersOverdueBanner
  ///
  /// In ar, this message translates to:
  /// **'متأخر عن موعده المعتاد — عادة يزور كل {every} يوم، ومضى {since} يوم منذ آخر زيارة'**
  String customersOverdueBanner(int every, int since);

  /// customersVisitMeter
  ///
  /// In ar, this message translates to:
  /// **'قراءة العدّاد: {n}'**
  String customersVisitMeter(int n);

  /// customersOfferExpiredBadge
  ///
  /// In ar, this message translates to:
  /// **'منتهي'**
  String get customersOfferExpiredBadge;

  /// customersDeniedAllTitle
  ///
  /// In ar, this message translates to:
  /// **'لا تملك صلاحية عرض قائمة العملاء'**
  String get customersDeniedAllTitle;

  /// customersDeniedOverdueTitle
  ///
  /// In ar, this message translates to:
  /// **'لا تملك صلاحية عرض من تأخّر'**
  String get customersDeniedOverdueTitle;

  /// customersDeniedDesc
  ///
  /// In ar, this message translates to:
  /// **'اطلب من مالك المحل يمنحك هذي الصلاحية.'**
  String get customersDeniedDesc;

  /// customersAddTitle
  ///
  /// In ar, this message translates to:
  /// **'إضافة عميل جديد'**
  String get customersAddTitle;

  /// customersAddPhoneLabel
  ///
  /// In ar, this message translates to:
  /// **'جوال العميل'**
  String get customersAddPhoneLabel;

  /// customersAddNameLabel
  ///
  /// In ar, this message translates to:
  /// **'اسم العميل'**
  String get customersAddNameLabel;

  /// customersAddPhoneInvalid
  ///
  /// In ar, this message translates to:
  /// **'رقم الجوال غير صحيح.'**
  String get customersAddPhoneInvalid;

  /// customersAddFailed
  ///
  /// In ar, this message translates to:
  /// **'تعذّرت إضافة العميل، حاول مرة أخرى.'**
  String get customersAddFailed;

  /// customersAddSubmitting
  ///
  /// In ar, this message translates to:
  /// **'جارٍ الإضافة...'**
  String get customersAddSubmitting;

  /// customersAddSubmit
  ///
  /// In ar, this message translates to:
  /// **'إضافة'**
  String get customersAddSubmit;

  /// customersActionFailed
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تنفيذ الإجراء، حاول مرة أخرى.'**
  String get customersActionFailed;

  /// customersRepeatedIssuesTitle
  ///
  /// In ar, this message translates to:
  /// **'شكاوى متكررة'**
  String get customersRepeatedIssuesTitle;

  /// customersVehiclesTitle
  ///
  /// In ar, this message translates to:
  /// **'المركبات'**
  String get customersVehiclesTitle;

  /// customersLoyaltyTitle
  ///
  /// In ar, this message translates to:
  /// **'الولاء'**
  String get customersLoyaltyTitle;

  /// customersLoyaltyLoading
  ///
  /// In ar, this message translates to:
  /// **'جارٍ التحميل...'**
  String get customersLoyaltyLoading;

  /// customersLoyaltyPoints
  ///
  /// In ar, this message translates to:
  /// **'{count} نقطة'**
  String customersLoyaltyPoints(int count);

  /// customersLoyaltyAdjust
  ///
  /// In ar, this message translates to:
  /// **'تعديل'**
  String get customersLoyaltyAdjust;

  /// customersOffersTitle
  ///
  /// In ar, this message translates to:
  /// **'العروض السارية'**
  String get customersOffersTitle;

  /// customersOfferExpires
  ///
  /// In ar, this message translates to:
  /// **'ينتهي {date}'**
  String customersOfferExpires(String date);

  /// customersVisitsTitle
  ///
  /// In ar, this message translates to:
  /// **'سجل الزيارات'**
  String get customersVisitsTitle;

  /// customersVisitsEmpty
  ///
  /// In ar, this message translates to:
  /// **'لا زيارات بعد'**
  String get customersVisitsEmpty;

  /// customersVisitNoServices
  ///
  /// In ar, this message translates to:
  /// **'بدون خدمات مسجّلة'**
  String get customersVisitNoServices;

  /// customersRenameTitle
  ///
  /// In ar, this message translates to:
  /// **'تعديل اسم العميل'**
  String get customersRenameTitle;

  /// customersRenameSubmit
  ///
  /// In ar, this message translates to:
  /// **'حفظ'**
  String get customersRenameSubmit;

  /// customersLoyaltyAdjustTitle
  ///
  /// In ar, this message translates to:
  /// **'تعديل نقاط الولاء'**
  String get customersLoyaltyAdjustTitle;

  /// customersLoyaltyAdjustNoteLabel
  ///
  /// In ar, this message translates to:
  /// **'سبب التعديل'**
  String get customersLoyaltyAdjustNoteLabel;

  /// customersLoyaltyAdjustNoteRequired
  ///
  /// In ar, this message translates to:
  /// **'اكتب سبباً حقيقياً (3 أحرف على الأقل)، واختر عدداً غير صفر.'**
  String get customersLoyaltyAdjustNoteRequired;

  /// customersLoyaltyAdjustSubmit
  ///
  /// In ar, this message translates to:
  /// **'حفظ التعديل'**
  String get customersLoyaltyAdjustSubmit;

  /// customersEraseButton
  ///
  /// In ar, this message translates to:
  /// **'حذف بيانات هذا العميل'**
  String get customersEraseButton;

  /// customersEraseTitle
  ///
  /// In ar, this message translates to:
  /// **'حذف بيانات العميل'**
  String get customersEraseTitle;

  /// customersEraseWarning
  ///
  /// In ar, this message translates to:
  /// **'هذا حذف نهائي لكل بيانات العميل من المنصة، ولا يمكن التراجع عنه.'**
  String get customersEraseWarning;

  /// customersEraseTypeNameLabel
  ///
  /// In ar, this message translates to:
  /// **'للتأكيد، اكتب اسم العميل: {name}'**
  String customersEraseTypeNameLabel(String name);

  /// customersEraseConfirm
  ///
  /// In ar, this message translates to:
  /// **'حذف نهائي'**
  String get customersEraseConfirm;

  /// customersBookingsTitle
  ///
  /// In ar, this message translates to:
  /// **'الحجوزات'**
  String get customersBookingsTitle;

  /// customersAttendanceRate
  ///
  /// In ar, this message translates to:
  /// **'{rate}٪ حضور'**
  String customersAttendanceRate(int rate);

  /// customersBookingsNoneUpcoming
  ///
  /// In ar, this message translates to:
  /// **'لا حجوزات قادمة'**
  String get customersBookingsNoneUpcoming;

  /// customersCyclesTitle
  ///
  /// In ar, this message translates to:
  /// **'دورات التذكير'**
  String get customersCyclesTitle;

  /// customersCyclesEveryDays
  ///
  /// In ar, this message translates to:
  /// **'كل {days} يوم'**
  String customersCyclesEveryDays(int days);

  /// customersCyclesEditHint
  ///
  /// In ar, this message translates to:
  /// **'اضبط الفترة، وسيتوقف التعلّم التلقائي لهذه الخدمة مع هذا العميل.'**
  String get customersCyclesEditHint;

  /// customersCyclesSave
  ///
  /// In ar, this message translates to:
  /// **'حفظ'**
  String get customersCyclesSave;

  /// customersLogTitle
  ///
  /// In ar, this message translates to:
  /// **'سجل الرسائل'**
  String get customersLogTitle;

  /// customersLogEmpty
  ///
  /// In ar, this message translates to:
  /// **'لم نرسل له شيئاً بعد'**
  String get customersLogEmpty;

  /// customersLogOutcomeSent
  ///
  /// In ar, this message translates to:
  /// **'أُرسلت'**
  String get customersLogOutcomeSent;

  /// customersLogOutcomeSuppressed
  ///
  /// In ar, this message translates to:
  /// **'لم تُرسل'**
  String get customersLogOutcomeSuppressed;

  /// customersTemplateVisitConfirmation
  ///
  /// In ar, this message translates to:
  /// **'تأكيد زيارة'**
  String get customersTemplateVisitConfirmation;

  /// customersTemplateVisitConfirmationRating
  ///
  /// In ar, this message translates to:
  /// **'طلب تقييم بعد الزيارة'**
  String get customersTemplateVisitConfirmationRating;

  /// customersTemplateBookingConfirmation
  ///
  /// In ar, this message translates to:
  /// **'تأكيد حجز'**
  String get customersTemplateBookingConfirmation;

  /// customersTemplateVisitRedeemed
  ///
  /// In ar, this message translates to:
  /// **'إشعار استبدال مكافأة'**
  String get customersTemplateVisitRedeemed;

  /// customersTemplateServiceReminder
  ///
  /// In ar, this message translates to:
  /// **'تذكير بموعد الخدمة'**
  String get customersTemplateServiceReminder;

  /// customersTemplateFollowUp
  ///
  /// In ar, this message translates to:
  /// **'متابعة بعد الزيارة'**
  String get customersTemplateFollowUp;

  /// customersTemplateAccountNotice
  ///
  /// In ar, this message translates to:
  /// **'إشعار بخصوص حسابه'**
  String get customersTemplateAccountNotice;

  /// customersTemplatePointsExpiring
  ///
  /// In ar, this message translates to:
  /// **'تنبيه انتهاء نقاط'**
  String get customersTemplatePointsExpiring;

  /// customersTemplateLoyaltyActivation
  ///
  /// In ar, this message translates to:
  /// **'تفعيل برنامج الولاء'**
  String get customersTemplateLoyaltyActivation;

  /// customersTemplateWinback
  ///
  /// In ar, this message translates to:
  /// **'استرجاع عميل غائب'**
  String get customersTemplateWinback;

  /// customersTemplatePersonalOccasion
  ///
  /// In ar, this message translates to:
  /// **'تهنئة بمناسبة'**
  String get customersTemplatePersonalOccasion;

  /// customersShowAll
  ///
  /// In ar, this message translates to:
  /// **'عرض الكل ({count})'**
  String customersShowAll(int count);

  /// customersCyclesUnknownService
  ///
  /// In ar, this message translates to:
  /// **'خدمة غير معروفة'**
  String get customersCyclesUnknownService;

  /// customersVisitGapDays
  ///
  /// In ar, this message translates to:
  /// **'{days, plural, =0{بنفس اليوم} one{بعد يوم واحد} two{بعد يومين} other{بعد {days} يوم}}'**
  String customersVisitGapDays(int days);

  /// customersCountLabel
  ///
  /// In ar, this message translates to:
  /// **'{count, plural, =0{لا عملاء بعد} one{عميل واحد} two{عميلان} other{{count} عميل}}'**
  String customersCountLabel(int count);

  /// ratingTitle
  ///
  /// In ar, this message translates to:
  /// **'التقييم'**
  String get ratingTitle;

  /// pointsTitle
  ///
  /// In ar, this message translates to:
  /// **'نقاط الولاء'**
  String get pointsTitle;

  /// pointsAddReward
  ///
  /// In ar, this message translates to:
  /// **'مكافأة جديدة'**
  String get pointsAddReward;

  /// pointsEditReward
  ///
  /// In ar, this message translates to:
  /// **'تعديل المكافأة'**
  String get pointsEditReward;

  /// pointsTabRewards
  ///
  /// In ar, this message translates to:
  /// **'المكافآت'**
  String get pointsTabRewards;

  /// pointsTabLeaderboard
  ///
  /// In ar, this message translates to:
  /// **'الأكثر طلبًا'**
  String get pointsTabLeaderboard;

  /// pointsOutstandingHint
  ///
  /// In ar, this message translates to:
  /// **'نقطة لسه بذمة المحل لعملائه'**
  String get pointsOutstandingHint;

  /// pointsRedemptionsCount
  ///
  /// In ar, this message translates to:
  /// **'{count, plural, one{استبدال واحد} two{استبدالان} other{{count} استبدال}}'**
  String pointsRedemptionsCount(int count);

  /// pointsCustomersCount
  ///
  /// In ar, this message translates to:
  /// **'{count, plural, one{عميل واحد استبدل} two{عميلان استبدلا} other{{count} عميل استبدل}}'**
  String pointsCustomersCount(int count);

  /// pointsExpiredWarning
  ///
  /// In ar, this message translates to:
  /// **'%{percent} من النقاط الممنوحة انتهت بلا استبدال — راجع أسعار مكافآتك'**
  String pointsExpiredWarning(int percent);

  /// pointsLoadFailedTitle
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تحميل المكافآت'**
  String get pointsLoadFailedTitle;

  /// pointsRewardsEmpty
  ///
  /// In ar, this message translates to:
  /// **'لا مكافآت بعد — أضف أول مكافأة لعملائك'**
  String get pointsRewardsEmpty;

  /// pointsLeaderboardEmpty
  ///
  /// In ar, this message translates to:
  /// **'لا استبدالات بعد — بتظهر هنا أول ما عميل يستبدل مكافأة'**
  String get pointsLeaderboardEmpty;

  /// pointsLeaderboardTitle
  ///
  /// In ar, this message translates to:
  /// **'الأعلى طلبًا'**
  String get pointsLeaderboardTitle;

  /// pointsLeaderboardHint
  ///
  /// In ar, this message translates to:
  /// **'أكثر خمس مكافآت استبدلها عملاؤك'**
  String get pointsLeaderboardHint;

  /// pointsTimesRedeemed
  ///
  /// In ar, this message translates to:
  /// **'{count, plural, one{مرة واحدة} two{مرتان} other{{count} مرة}}'**
  String pointsTimesRedeemed(int count);

  /// pointsRewardRetired
  ///
  /// In ar, this message translates to:
  /// **'متوقفة'**
  String get pointsRewardRetired;

  /// pointsRewardServiceHint
  ///
  /// In ar, this message translates to:
  /// **'خدمة: {name}'**
  String pointsRewardServiceHint(String name);

  /// pointsRewardDiscountHint
  ///
  /// In ar, this message translates to:
  /// **'خصم {amount} ريال'**
  String pointsRewardDiscountHint(String amount);

  /// pointsRewardItemHint
  ///
  /// In ar, this message translates to:
  /// **'هدية غير مرتبطة بالكتالوج'**
  String get pointsRewardItemHint;

  /// pointsRewardNameLabel
  ///
  /// In ar, this message translates to:
  /// **'اسم المكافأة'**
  String get pointsRewardNameLabel;

  /// pointsRewardTypeLabel
  ///
  /// In ar, this message translates to:
  /// **'نوع المكافأة'**
  String get pointsRewardTypeLabel;

  /// pointsTypeService
  ///
  /// In ar, this message translates to:
  /// **'خدمة من كتالوجك'**
  String get pointsTypeService;

  /// pointsTypeItem
  ///
  /// In ar, this message translates to:
  /// **'هدية'**
  String get pointsTypeItem;

  /// pointsTypeDiscount
  ///
  /// In ar, this message translates to:
  /// **'خصم مبلغ'**
  String get pointsTypeDiscount;

  /// pointsRewardServiceLabel
  ///
  /// In ar, this message translates to:
  /// **'أي خدمة'**
  String get pointsRewardServiceLabel;

  /// pointsRewardDiscountLabel
  ///
  /// In ar, this message translates to:
  /// **'قيمة الخصم بالريال'**
  String get pointsRewardDiscountLabel;

  /// pointsRewardCostLabel
  ///
  /// In ar, this message translates to:
  /// **'ثمنها بالنقاط'**
  String get pointsRewardCostLabel;

  /// pointsRewardActiveLabel
  ///
  /// In ar, this message translates to:
  /// **'فعّالة ويقدر العملاء يستبدلونها'**
  String get pointsRewardActiveLabel;

  /// pointsRewardInvalid
  ///
  /// In ar, this message translates to:
  /// **'اكتب اسم ونقاط صحيحة أكبر من صفر'**
  String get pointsRewardInvalid;

  /// pointsSaveFailed
  ///
  /// In ar, this message translates to:
  /// **'تعذّر الحفظ، حاول مرة ثانية'**
  String get pointsSaveFailed;

  /// pointsModeTitle
  ///
  /// In ar, this message translates to:
  /// **'طريقة الاحتساب'**
  String get pointsModeTitle;

  /// pointsModeHint
  ///
  /// In ar, this message translates to:
  /// **'بالخدمات: كل خدمة نقاطها. بقيمة الفاتورة: نقطة لكل ريال.'**
  String get pointsModeHint;

  /// pointsModeServices
  ///
  /// In ar, this message translates to:
  /// **'بالخدمات'**
  String get pointsModeServices;

  /// pointsModeInvoice
  ///
  /// In ar, this message translates to:
  /// **'بقيمة الفاتورة'**
  String get pointsModeInvoice;

  /// pointsModeNeedsPricedServices
  ///
  /// In ar, this message translates to:
  /// **'الاحتساب بقيمة الفاتورة يحتاج كل خدماتك مسعّرة أولاً — سعّرها كلها بخدماتي ومنتجاتي ثم فعّله.'**
  String get pointsModeNeedsPricedServices;

  /// pointsOpenEarnSettings
  ///
  /// In ar, this message translates to:
  /// **'إعدادات نقاط كل خدمة'**
  String get pointsOpenEarnSettings;

  /// ratingLeaderboardTitle
  ///
  /// In ar, this message translates to:
  /// **'الأعلى تقييماً'**
  String get ratingLeaderboardTitle;

  /// ratingCardNoName
  ///
  /// In ar, this message translates to:
  /// **'بلا اسم'**
  String get ratingCardNoName;

  /// ratingMetricVisits
  ///
  /// In ar, this message translates to:
  /// **'الأكثر زيارات'**
  String get ratingMetricVisits;

  /// ratingMetricRatings
  ///
  /// In ar, this message translates to:
  /// **'الأكثر تقييمات'**
  String get ratingMetricRatings;

  /// ratingMetricAvg
  ///
  /// In ar, this message translates to:
  /// **'الأعلى تقييماً'**
  String get ratingMetricAvg;

  /// ratingStaffCount
  ///
  /// In ar, this message translates to:
  /// **'{count, plural, one{موظف واحد} two{موظفان} other{{count} موظف}}'**
  String ratingStaffCount(int count);

  /// ratingTableTitle
  ///
  /// In ar, this message translates to:
  /// **'كل موظف'**
  String get ratingTableTitle;

  /// ratingTableVisitsValue
  ///
  /// In ar, this message translates to:
  /// **'{n} زيارة'**
  String ratingTableVisitsValue(int n);

  /// ratingTableRatingsValue
  ///
  /// In ar, this message translates to:
  /// **'{n} تقييم'**
  String ratingTableRatingsValue(int n);

  /// ratingTableEngagementValue
  ///
  /// In ar, this message translates to:
  /// **'تفاعل %{n}'**
  String ratingTableEngagementValue(int n);

  /// ratingTableNoShowValue
  ///
  /// In ar, this message translates to:
  /// **'لم يحضر %{n}'**
  String ratingTableNoShowValue(int n);

  /// ratingPeriodWeek
  ///
  /// In ar, this message translates to:
  /// **'أسبوع'**
  String get ratingPeriodWeek;

  /// ratingPeriodMonth
  ///
  /// In ar, this message translates to:
  /// **'شهر'**
  String get ratingPeriodMonth;

  /// ratingPeriodQuarter
  ///
  /// In ar, this message translates to:
  /// **'ربع سنة'**
  String get ratingPeriodQuarter;

  /// ratingPeriodCustom
  ///
  /// In ar, this message translates to:
  /// **'مخصّص'**
  String get ratingPeriodCustom;

  /// ratingCustomSince
  ///
  /// In ar, this message translates to:
  /// **'من: {date}'**
  String ratingCustomSince(String date);

  /// ratingCustomUntil
  ///
  /// In ar, this message translates to:
  /// **'إلى: {date}'**
  String ratingCustomUntil(String date);

  /// ratingCustomRangeInvalid
  ///
  /// In ar, this message translates to:
  /// **'المدى غير صالح — تأكد إن تاريخ البداية قبل النهاية'**
  String get ratingCustomRangeInvalid;

  /// ratingExportLocaleLabel
  ///
  /// In ar, this message translates to:
  /// **'لغة التقرير'**
  String get ratingExportLocaleLabel;

  /// localeNameAr
  ///
  /// In ar, this message translates to:
  /// **'العربية'**
  String get localeNameAr;

  /// localeNameEn
  ///
  /// In ar, this message translates to:
  /// **'English'**
  String get localeNameEn;

  /// localeNameUr
  ///
  /// In ar, this message translates to:
  /// **'اردو'**
  String get localeNameUr;

  /// localeNameHa
  ///
  /// In ar, this message translates to:
  /// **'Hausa'**
  String get localeNameHa;

  /// localeNameFil
  ///
  /// In ar, this message translates to:
  /// **'Filipino'**
  String get localeNameFil;

  /// localeNameBn
  ///
  /// In ar, this message translates to:
  /// **'বাংলা'**
  String get localeNameBn;

  /// ratingTopIssuesTitle
  ///
  /// In ar, this message translates to:
  /// **'أكثر المشاكل تكراراً'**
  String get ratingTopIssuesTitle;

  /// ratingFilterUnhandled
  ///
  /// In ar, this message translates to:
  /// **'بانتظار المعالجة'**
  String get ratingFilterUnhandled;

  /// ratingFilterAll
  ///
  /// In ar, this message translates to:
  /// **'الكل'**
  String get ratingFilterAll;

  /// ratingFilterHandled
  ///
  /// In ar, this message translates to:
  /// **'معالَجة'**
  String get ratingFilterHandled;

  /// ratingStarsAll
  ///
  /// In ar, this message translates to:
  /// **'كل النجوم'**
  String get ratingStarsAll;

  /// ratingLoadFailedTitle
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تحميل التقييمات'**
  String get ratingLoadFailedTitle;

  /// ratingEmptyTitle
  ///
  /// In ar, this message translates to:
  /// **'لا تقييمات بعد'**
  String get ratingEmptyTitle;

  /// ratingLoadMore
  ///
  /// In ar, this message translates to:
  /// **'عرض المزيد'**
  String get ratingLoadMore;

  /// ratingHandledPlain
  ///
  /// In ar, this message translates to:
  /// **'تمّت معالجته'**
  String get ratingHandledPlain;

  /// ratingMarkHandled
  ///
  /// In ar, this message translates to:
  /// **'تمّت المعالجة'**
  String get ratingMarkHandled;

  /// ratingMarkHandledHint
  ///
  /// In ar, this message translates to:
  /// **'يُسجَّل هذا نهائياً — لا يمكن التراجع عنه لاحقاً.'**
  String get ratingMarkHandledHint;

  /// ratingHandledNoteLabel
  ///
  /// In ar, this message translates to:
  /// **'ملاحظة (اختياري)'**
  String get ratingHandledNoteLabel;

  /// ratingMarkHandledConfirm
  ///
  /// In ar, this message translates to:
  /// **'تأكيد المعالجة'**
  String get ratingMarkHandledConfirm;

  /// ratingActionFailed
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تنفيذ الإجراء، حاول مرة أخرى.'**
  String get ratingActionFailed;

  /// ratingWeightedAvgHint
  ///
  /// In ar, this message translates to:
  /// **'{count, plural, =0{لا تقييمات بعد آخر 30 يوم} one{من تقييم واحد آخر 30 يوم} other{من {count} تقييم آخر 30 يوم}}'**
  String ratingWeightedAvgHint(int count);

  /// ratingUnhandledCount
  ///
  /// In ar, this message translates to:
  /// **'{count, plural, one{تقييم واحد بانتظار المعالجة} two{تقييمان بانتظار المعالجة} other{{count} تقييم بانتظار المعالجة}}'**
  String ratingUnhandledCount(int count);

  /// ratingVisitsShort
  ///
  /// In ar, this message translates to:
  /// **'{count, plural, one{زيارة واحدة} two{زيارتان} other{{count} زيارة}}'**
  String ratingVisitsShort(int count);

  /// ratingIssueFilterLabel
  ///
  /// In ar, this message translates to:
  /// **'المشكلة: {label}'**
  String ratingIssueFilterLabel(String label);

  /// ratingByOperator
  ///
  /// In ar, this message translates to:
  /// **'خدمه {name}'**
  String ratingByOperator(String name);

  /// ratingHandledWithNote
  ///
  /// In ar, this message translates to:
  /// **'تمّت المعالجة: {note}'**
  String ratingHandledWithNote(String note);

  /// ratingQuadrantTitle
  ///
  /// In ar, this message translates to:
  /// **'رباعية الأداء'**
  String get ratingQuadrantTitle;

  /// ratingQuadrantHint
  ///
  /// In ar, this message translates to:
  /// **'الجودة مقابل معدل التفاعل — اضغط على أي نقطة لسجل تدريب الموظف.'**
  String get ratingQuadrantHint;

  /// ratingQuadrantStars
  ///
  /// In ar, this message translates to:
  /// **'نجوم'**
  String get ratingQuadrantStars;

  /// ratingQuadrantUnderused
  ///
  /// In ar, this message translates to:
  /// **'غير مُستغَل'**
  String get ratingQuadrantUnderused;

  /// ratingQuadrantNeedsCoaching
  ///
  /// In ar, this message translates to:
  /// **'يحتاج تدريب'**
  String get ratingQuadrantNeedsCoaching;

  /// ratingQuadrantAtRisk
  ///
  /// In ar, this message translates to:
  /// **'يحتاج متابعة'**
  String get ratingQuadrantAtRisk;

  /// ratingTrainingTitle
  ///
  /// In ar, this message translates to:
  /// **'سجل التدريب'**
  String get ratingTrainingTitle;

  /// ratingTrainingNoAccess
  ///
  /// In ar, this message translates to:
  /// **'ما عندك صلاحية عرض هذا.'**
  String get ratingTrainingNoAccess;

  /// ratingTrainingClean
  ///
  /// In ar, this message translates to:
  /// **'سجل نظيف — ما فيه ملاحظات متكررة.'**
  String get ratingTrainingClean;

  /// ratingEngagementPercent
  ///
  /// In ar, this message translates to:
  /// **'{percent}٪ تفاعل'**
  String ratingEngagementPercent(int percent);

  /// ratingTabOverview
  ///
  /// In ar, this message translates to:
  /// **'نظرة عامة'**
  String get ratingTabOverview;

  /// ratingTabFeed
  ///
  /// In ar, this message translates to:
  /// **'كل التقييمات'**
  String get ratingTabFeed;

  /// ratingOverviewEmpty
  ///
  /// In ar, this message translates to:
  /// **'لا بيانات أداء بعد آخر 30 يوم.'**
  String get ratingOverviewEmpty;

  /// ratingExportTitle
  ///
  /// In ar, this message translates to:
  /// **'تصدير التقرير'**
  String get ratingExportTitle;

  /// ratingExportHint
  ///
  /// In ar, this message translates to:
  /// **'تقرير أداء الفريق للمدة المختارة، جاهز للمشاركة.'**
  String get ratingExportHint;

  /// ratingExportFailed
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تصدير التقرير، حاول مرة أخرى.'**
  String get ratingExportFailed;

  /// customersPrivacyRequestsTitle
  ///
  /// In ar, this message translates to:
  /// **'طلبات حماية البيانات'**
  String get customersPrivacyRequestsTitle;

  /// customersPrivacyRequestErase
  ///
  /// In ar, this message translates to:
  /// **'طلب حذف بيانات'**
  String get customersPrivacyRequestErase;

  /// customersPrivacyRequestCopy
  ///
  /// In ar, this message translates to:
  /// **'طلب نسخة من البيانات'**
  String get customersPrivacyRequestCopy;

  /// customersPrivacyRequestGeneric
  ///
  /// In ar, this message translates to:
  /// **'طلب: {type}'**
  String customersPrivacyRequestGeneric(String type);

  /// customersPrivacyRequestClose
  ///
  /// In ar, this message translates to:
  /// **'إغلاق'**
  String get customersPrivacyRequestClose;

  /// customersLoyaltyHistoryTitle
  ///
  /// In ar, this message translates to:
  /// **'سجل نقاط الولاء'**
  String get customersLoyaltyHistoryTitle;

  /// customersLoyaltyHistoryNoReason
  ///
  /// In ar, this message translates to:
  /// **'بدون سبب مذكور'**
  String get customersLoyaltyHistoryNoReason;

  /// customersLoyaltyReasonRedeem
  ///
  /// In ar, this message translates to:
  /// **'استبدال مكافأة'**
  String get customersLoyaltyReasonRedeem;

  /// customersLoyaltyReasonAdjust
  ///
  /// In ar, this message translates to:
  /// **'تعديل يدوي'**
  String get customersLoyaltyReasonAdjust;

  /// customersLoyaltyReasonEarn
  ///
  /// In ar, this message translates to:
  /// **'نقاط من زيارة'**
  String get customersLoyaltyReasonEarn;

  /// customersLoyaltyReasonExpire
  ///
  /// In ar, this message translates to:
  /// **'انتهت صلاحيتها'**
  String get customersLoyaltyReasonExpire;

  /// readCustomersFailed
  ///
  /// In ar, this message translates to:
  /// **'تعذّر جلب بيانات العملاء الآن، حاول مرة ثانية.'**
  String get readCustomersFailed;

  /// readCustomersTotal
  ///
  /// In ar, this message translates to:
  /// **'{count, plural, =0{ما عندك أي عميل مسجّل بعد.} one{عندك عميل واحد مسجّل.} other{عندك {count} عميل مسجّل.}}'**
  String readCustomersTotal(int count);

  /// readCustomersOverdueCount
  ///
  /// In ar, this message translates to:
  /// **'{count, plural, =0{ما فيه عميل متأخر عن دورته حالياً.} one{عندك عميل واحد متأخر عن دورته.} other{عندك {count} عميل متأخر عن دورتهم.}}'**
  String readCustomersOverdueCount(int count);

  /// readMobileRequestsFailed
  ///
  /// In ar, this message translates to:
  /// **'تعذّر جلب طلبات الخدمة المتنقلة الآن، حاول مرة ثانية.'**
  String get readMobileRequestsFailed;

  /// readMobileRequestsPendingCount
  ///
  /// In ar, this message translates to:
  /// **'{count, plural, =0{ما فيه طلبات خدمة متنقلة بانتظار قرار.} one{عندك طلب واحد بانتظار قرار.} other{عندك {count} طلب بانتظار قرار.}}'**
  String readMobileRequestsPendingCount(int count);

  /// readMobileRequestsNeedsDecisionCount
  ///
  /// In ar, this message translates to:
  /// **'{count, plural, =0{ما فيه طلبات متنقلة تحتاج قرارك الآن.} one{عندك طلب واحد يحتاج قرارك الآن.} other{عندك {count} طلبات تحتاج قرارك الآن.}}'**
  String readMobileRequestsNeedsDecisionCount(int count);

  /// readRatingFailed
  ///
  /// In ar, this message translates to:
  /// **'تعذّر جلب بيانات التقييم الآن، حاول مرة ثانية.'**
  String get readRatingFailed;

  /// readRatingNone
  ///
  /// In ar, this message translates to:
  /// **'ما عندك تقييمات آخر 30 يوم بعد.'**
  String get readRatingNone;

  /// readRatingAverage
  ///
  /// In ar, this message translates to:
  /// **'متوسط تقييمك آخر 30 يوم {avg} من 5، من {count} تقييم.'**
  String readRatingAverage(String avg, int count);

  /// readRatingUnhandledCount
  ///
  /// In ar, this message translates to:
  /// **'{count, plural, =0{ما فيه تقييمات بانتظار المعالجة.} one{عندك تقييم واحد بانتظار المعالجة.} other{عندك {count} تقييم بانتظار المعالجة.}}'**
  String readRatingUnhandledCount(int count);

  /// readRatingTopStaff
  ///
  /// In ar, this message translates to:
  /// **'أفضل موظف تقييماً آخر 30 يوم هو {name}، بمتوسط {avg} من 5.'**
  String readRatingTopStaff(String name, String avg);

  /// readMobileRequestsCompletedCount
  ///
  /// In ar, this message translates to:
  /// **'{count, plural, =0{ما خلّصت أي طلب متنقل هذا الشهر بعد.} one{خلّصت طلب واحد هذا الشهر.} other{خلّصت {count} طلب هذا الشهر.}}'**
  String readMobileRequestsCompletedCount(int count);

  /// readMobileRequestsTodayCount
  ///
  /// In ar, this message translates to:
  /// **'{count, plural, =0{ما جاك أي طلب خدمة متنقلة اليوم بعد.} one{جاك طلب واحد اليوم.} other{جاك {count} طلب اليوم.}}'**
  String readMobileRequestsTodayCount(int count);

  /// readOperatorsFailed
  ///
  /// In ar, this message translates to:
  /// **'تعذّر جلب عدد الموظفين الآن، حاول مرة ثانية.'**
  String get readOperatorsFailed;

  /// readOperatorsCount
  ///
  /// In ar, this message translates to:
  /// **'{count, plural, =0{ما عندك أي موظف مسجّل بعد.} one{عندك موظف واحد بفريقك.} other{عندك {count} موظف بفريقك.}}'**
  String readOperatorsCount(int count);

  /// readBranchesDisconnectedCount
  ///
  /// In ar, this message translates to:
  /// **'{count, plural, =0{كل فروعك النشطة واتسابها مربوط ويشتغل.} one{عندك فرع واحد واتسابه مو شغّال.} other{عندك {count} فروع واتسابها مو شغّال.}}'**
  String readBranchesDisconnectedCount(int count);

  /// readCustomersRecentNone
  ///
  /// In ar, this message translates to:
  /// **'ما عندك أي عميل مسجّل بعد.'**
  String get readCustomersRecentNone;

  /// readCustomersRecentName
  ///
  /// In ar, this message translates to:
  /// **'آخر عميل سجّلته هو {name}.'**
  String readCustomersRecentName(String name);

  /// readRatingCriticalIssuesCount
  ///
  /// In ar, this message translates to:
  /// **'{count, plural, =0{ما فيه تقييمات فيها ملاحظة خطيرة ما رديت عليها.} one{عندك تقييم واحد فيه ملاحظة خطيرة ما رديت عليه.} other{عندك {count} تقييمات فيها ملاحظات خطيرة ما رديت عليها.}}'**
  String readRatingCriticalIssuesCount(int count);

  /// readPerBranchModeOn
  ///
  /// In ar, this message translates to:
  /// **'أيوه، محلك يشتغل بنظام تعدد الفروع.'**
  String get readPerBranchModeOn;

  /// readPerBranchModeOff
  ///
  /// In ar, this message translates to:
  /// **'لا، محلك يشتغل كفرع واحد فقط.'**
  String get readPerBranchModeOff;

  /// readBillingOverdueYes
  ///
  /// In ar, this message translates to:
  /// **'أيوه، عندك فاتورة متأخرة السداد — سدّدها لتفادي إيقاف خدماتك.'**
  String get readBillingOverdueYes;

  /// readBillingOverdueNo
  ///
  /// In ar, this message translates to:
  /// **'لا، فوترتك بحالة جيدة، ما فيه فواتير متأخرة.'**
  String get readBillingOverdueNo;

  /// readServicesFailed
  ///
  /// In ar, this message translates to:
  /// **'تعذّر جلب عدد الخدمات الآن، حاول مرة ثانية.'**
  String get readServicesFailed;

  /// readServicesCount
  ///
  /// In ar, this message translates to:
  /// **'{count, plural, =0{ما عندك أي خدمة بقائمتك بعد.} one{عندك خدمة واحدة بقائمتك.} other{عندك {count} خدمة بقائمتك.}}'**
  String readServicesCount(int count);

  /// readCustomersTodayCount
  ///
  /// In ar, this message translates to:
  /// **'{count, plural, =0{ما جاك عميل جديد اليوم بعد.} one{جاك عميل جديد واحد اليوم.} other{جاك {count} عميل جديد اليوم.}}'**
  String readCustomersTodayCount(int count);

  /// readMobileRequestsRejectedCount
  ///
  /// In ar, this message translates to:
  /// **'{count, plural, =0{ما رفضت أي طلب خدمة متنقلة هذا الشهر.} one{رفضت طلب واحد هذا الشهر.} other{رفضت {count} طلب هذا الشهر.}}'**
  String readMobileRequestsRejectedCount(int count);

  /// readMobileRequestsNoShowCount
  ///
  /// In ar, this message translates to:
  /// **'{count, plural, =0{ما فيه عميل ما حضر هذا الشهر.} one{عندك عميل واحد ما حضر هذا الشهر.} other{عندك {count} عملاء ما حضروا هذا الشهر.}}'**
  String readMobileRequestsNoShowCount(int count);

  /// readRatingFiveStarCount
  ///
  /// In ar, this message translates to:
  /// **'{count, plural, =0{ما عندك أي تقييم خماسي بعد.} one{عندك تقييم خماسي واحد.} other{عندك {count} تقييم خماسي.}}'**
  String readRatingFiveStarCount(int count);

  /// readBranchesActiveCount
  ///
  /// In ar, this message translates to:
  /// **'{count, plural, =0{ما عندك أي فرع نشط حالياً.} one{عندك فرع واحد نشط.} other{عندك {count} فروع نشطة.}}'**
  String readBranchesActiveCount(int count);

  /// servicesTitle
  ///
  /// In ar, this message translates to:
  /// **'خدماتي ومنتجاتي'**
  String get servicesTitle;

  /// servicesUnnamedGlyph
  ///
  /// In ar, this message translates to:
  /// **'؟'**
  String get servicesUnnamedGlyph;

  /// servicesSearchHint
  ///
  /// In ar, this message translates to:
  /// **'ابحث باسم الخدمة'**
  String get servicesSearchHint;

  /// servicesTabActive
  ///
  /// In ar, this message translates to:
  /// **'نشطة'**
  String get servicesTabActive;

  /// servicesTabStopped
  ///
  /// In ar, this message translates to:
  /// **'متوقفة'**
  String get servicesTabStopped;

  /// servicesLoadFailedTitle
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تحميل الخدمات'**
  String get servicesLoadFailedTitle;

  /// servicesEmptyActive
  ///
  /// In ar, this message translates to:
  /// **'لا خدمات نشطة بعد'**
  String get servicesEmptyActive;

  /// servicesEmptyStopped
  ///
  /// In ar, this message translates to:
  /// **'لا خدمات متوقفة'**
  String get servicesEmptyStopped;

  /// servicesAddOpen
  ///
  /// In ar, this message translates to:
  /// **'إضافة خدمة'**
  String get servicesAddOpen;

  /// servicesNoPrice
  ///
  /// In ar, this message translates to:
  /// **'بدون سعر'**
  String get servicesNoPrice;

  /// servicesNoDuration
  ///
  /// In ar, this message translates to:
  /// **'غير محدّدة'**
  String get servicesNoDuration;

  /// servicesNoCycle
  ///
  /// In ar, this message translates to:
  /// **'بدون دورة'**
  String get servicesNoCycle;

  /// servicesStopTitle
  ///
  /// In ar, this message translates to:
  /// **'إيقاف الخدمة'**
  String get servicesStopTitle;

  /// servicesStopConfirm
  ///
  /// In ar, this message translates to:
  /// **'إيقاف'**
  String get servicesStopConfirm;

  /// servicesActionFailed
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تنفيذ الإجراء، حاول مرة أخرى.'**
  String get servicesActionFailed;

  /// servicesEditTitle
  ///
  /// In ar, this message translates to:
  /// **'تعديل الخدمة'**
  String get servicesEditTitle;

  /// servicesAddTitle
  ///
  /// In ar, this message translates to:
  /// **'إضافة خدمة جديدة'**
  String get servicesAddTitle;

  /// servicesNameLabel
  ///
  /// In ar, this message translates to:
  /// **'اسم الخدمة'**
  String get servicesNameLabel;

  /// servicesPriceLabel
  ///
  /// In ar, this message translates to:
  /// **'السعر (اختياري)'**
  String get servicesPriceLabel;

  /// servicesDurationLabel
  ///
  /// In ar, this message translates to:
  /// **'المدة بالدقائق (اختياري)'**
  String get servicesDurationLabel;

  /// servicesCycleLabel
  ///
  /// In ar, this message translates to:
  /// **'دورة التذكير بالأيام (اختياري)'**
  String get servicesCycleLabel;

  /// servicesDescriptionLabel
  ///
  /// In ar, this message translates to:
  /// **'وصف مختصر (اختياري)'**
  String get servicesDescriptionLabel;

  /// servicesSaving
  ///
  /// In ar, this message translates to:
  /// **'جارٍ الحفظ...'**
  String get servicesSaving;

  /// servicesSave
  ///
  /// In ar, this message translates to:
  /// **'حفظ'**
  String get servicesSave;

  /// servicesNameRequired
  ///
  /// In ar, this message translates to:
  /// **'اسم الخدمة مطلوب'**
  String get servicesNameRequired;

  /// servicesActiveCount
  ///
  /// In ar, this message translates to:
  /// **'{count, plural, =0{ما عندك أي خدمة نشطة بعد.} one{عندك خدمة نشطة واحدة.} other{عندك {count} خدمة نشطة.}}'**
  String servicesActiveCount(int count);

  /// servicesDurationMinutes
  ///
  /// In ar, this message translates to:
  /// **'{count} دقيقة'**
  String servicesDurationMinutes(int count);

  /// servicesCycleDays
  ///
  /// In ar, this message translates to:
  /// **'كل {count} يوم'**
  String servicesCycleDays(int count);

  /// servicesStopWarning
  ///
  /// In ar, this message translates to:
  /// **'بيوقف خدمة «{name}» — ما راح تظهر لعميل جديد بتسجيل الزيارة، وتذكيراتها تتوقف. ما تُحذف بياناتها.'**
  String servicesStopWarning(String name);

  /// servicesPhotoPickFailed
  ///
  /// In ar, this message translates to:
  /// **'تعذّر اختيار الصورة'**
  String get servicesPhotoPickFailed;

  /// servicesPhotoUploadFailed
  ///
  /// In ar, this message translates to:
  /// **'تم الحفظ لكن تعذّر رفع الصورة'**
  String get servicesPhotoUploadFailed;

  /// servicesPhotoLabel
  ///
  /// In ar, this message translates to:
  /// **'صورة الخدمة (اختياري)'**
  String get servicesPhotoLabel;

  /// servicesUploadPhoto
  ///
  /// In ar, this message translates to:
  /// **'رفع صورة'**
  String get servicesUploadPhoto;

  /// servicesChangePhoto
  ///
  /// In ar, this message translates to:
  /// **'تغيير الصورة'**
  String get servicesChangePhoto;

  /// servicesRemovePhoto
  ///
  /// In ar, this message translates to:
  /// **'إزالة'**
  String get servicesRemovePhoto;

  /// servicesAssignmentLabel
  ///
  /// In ar, this message translates to:
  /// **'من يقدّم هذه الخدمة؟'**
  String get servicesAssignmentLabel;

  /// servicesAssignmentAuto
  ///
  /// In ar, this message translates to:
  /// **'أي موظف متاح'**
  String get servicesAssignmentAuto;

  /// servicesAssignmentNamed
  ///
  /// In ar, this message translates to:
  /// **'موظفون محدّدون'**
  String get servicesAssignmentNamed;

  /// servicesChecklistLabel
  ///
  /// In ar, this message translates to:
  /// **'خطوات الإجراء'**
  String get servicesChecklistLabel;

  /// servicesChecklistEmpty
  ///
  /// In ar, this message translates to:
  /// **'لا خطوات بعد — أضف أول خطوة'**
  String get servicesChecklistEmpty;

  /// servicesStepAddTitle
  ///
  /// In ar, this message translates to:
  /// **'إضافة خطوة'**
  String get servicesStepAddTitle;

  /// servicesGeneralSettingsTitle
  ///
  /// In ar, this message translates to:
  /// **'الإعداد العام'**
  String get servicesGeneralSettingsTitle;

  /// servicesGeneralSettingsHint
  ///
  /// In ar, this message translates to:
  /// **'القيمة التي تتبعها كل خدمة لم تُخصَّص بعد'**
  String get servicesGeneralSettingsHint;

  /// servicesFollowUpLabel
  ///
  /// In ar, this message translates to:
  /// **'أيام المتابعة بعد الزيارة'**
  String get servicesFollowUpLabel;

  /// servicesPointsLabel
  ///
  /// In ar, this message translates to:
  /// **'نقاط لكل زيارة'**
  String get servicesPointsLabel;

  /// servicesGroupThem
  ///
  /// In ar, this message translates to:
  /// **'تجميعها'**
  String get servicesGroupThem;

  /// servicesGroupNameHint
  ///
  /// In ar, this message translates to:
  /// **'اسم المجموعة'**
  String get servicesGroupNameHint;

  /// servicesAllGroups
  ///
  /// In ar, this message translates to:
  /// **'الكل'**
  String get servicesAllGroups;

  /// servicesStepEditTitle
  ///
  /// In ar, this message translates to:
  /// **'تعديل الخطوة'**
  String get servicesStepEditTitle;

  /// servicesStepCriticalLabel
  ///
  /// In ar, this message translates to:
  /// **'خطوة حرجة'**
  String get servicesStepCriticalLabel;

  /// servicesStepRetire
  ///
  /// In ar, this message translates to:
  /// **'إيقاف هذه الخطوة'**
  String get servicesStepRetire;

  /// servicesStepEditHint
  ///
  /// In ar, this message translates to:
  /// **'اضغط مطوّلاً على أي خطوة لتعديلها أو إيقافها'**
  String get servicesStepEditHint;

  /// servicesAdvancedTitle
  ///
  /// In ar, this message translates to:
  /// **'إعدادات متقدمة'**
  String get servicesAdvancedTitle;

  /// servicesAdvancedHint
  ///
  /// In ar, this message translates to:
  /// **'تخصيص هذه الخدمة عن الإعداد العام — لدورة التذكير والنقاط والتجميع'**
  String get servicesAdvancedHint;

  /// servicesGroupLabel
  ///
  /// In ar, this message translates to:
  /// **'المجموعة'**
  String get servicesGroupLabel;

  /// servicesNoGroup
  ///
  /// In ar, this message translates to:
  /// **'بدون مجموعة'**
  String get servicesNoGroup;

  /// servicesNewGroup
  ///
  /// In ar, this message translates to:
  /// **'مجموعة جديدة'**
  String get servicesNewGroup;

  /// servicesFollowGeneralAction
  ///
  /// In ar, this message translates to:
  /// **'اتّباع العام'**
  String get servicesFollowGeneralAction;

  /// servicesCustomizeAction
  ///
  /// In ar, this message translates to:
  /// **'تخصيص'**
  String get servicesCustomizeAction;

  /// servicesFollowUpDays
  ///
  /// In ar, this message translates to:
  /// **'متابعة بعد {n} يوم'**
  String servicesFollowUpDays(int n);

  /// servicesPointsPerVisit
  ///
  /// In ar, this message translates to:
  /// **'{n} نقطة'**
  String servicesPointsPerVisit(int n);

  /// servicesSuggestionText
  ///
  /// In ar, this message translates to:
  /// **'{n} خدمات تتشارك نفس القيمة — تجميعها في مجموعة واحدة يسهّل تعديلها معاً لاحقاً.'**
  String servicesSuggestionText(int n);

  /// servicesFollowsGeneral
  ///
  /// In ar, this message translates to:
  /// **'يتبع العام — {hint}'**
  String servicesFollowsGeneral(String hint);

  /// servicesPageTabServices
  ///
  /// In ar, this message translates to:
  /// **'الخدمات'**
  String get servicesPageTabServices;

  /// servicesPageTabPackages
  ///
  /// In ar, this message translates to:
  /// **'الباقات'**
  String get servicesPageTabPackages;

  /// servicesPackageAdd
  ///
  /// In ar, this message translates to:
  /// **'إضافة باقة'**
  String get servicesPackageAdd;

  /// servicesPackageNeedsTwoServices
  ///
  /// In ar, this message translates to:
  /// **'الباقة تحتاج خدمتين نشطتين على الأقل'**
  String get servicesPackageNeedsTwoServices;

  /// servicesPackageEmpty
  ///
  /// In ar, this message translates to:
  /// **'لا باقات بعد'**
  String get servicesPackageEmpty;

  /// servicesPackageEditTitle
  ///
  /// In ar, this message translates to:
  /// **'تعديل الباقة'**
  String get servicesPackageEditTitle;

  /// servicesPackageAddTitle
  ///
  /// In ar, this message translates to:
  /// **'إضافة باقة جديدة'**
  String get servicesPackageAddTitle;

  /// servicesPackageNameLabel
  ///
  /// In ar, this message translates to:
  /// **'اسم الباقة'**
  String get servicesPackageNameLabel;

  /// servicesPackagePriceRequired
  ///
  /// In ar, this message translates to:
  /// **'سعر الباقة مطلوب، أكبر من صفر'**
  String get servicesPackagePriceRequired;

  /// servicesPackageServicesLabel
  ///
  /// In ar, this message translates to:
  /// **'الخدمات المشمولة'**
  String get servicesPackageServicesLabel;

  /// servicesImportTitle
  ///
  /// In ar, this message translates to:
  /// **'استيراد خدمات من ملف'**
  String get servicesImportTitle;

  /// servicesImportHint
  ///
  /// In ar, this message translates to:
  /// **'ملف CSV بأعمدة: name, price, duration_minutes, cycle_days, description'**
  String get servicesImportHint;

  /// servicesImportPickFile
  ///
  /// In ar, this message translates to:
  /// **'اختيار ملف CSV'**
  String get servicesImportPickFile;

  /// servicesImportReadFailed
  ///
  /// In ar, this message translates to:
  /// **'تعذّرت قراءة الملف'**
  String get servicesImportReadFailed;

  /// servicesImportParseFailed
  ///
  /// In ar, this message translates to:
  /// **'الملف لا يحتوي عمود name، أو تنسيقه غير صحيح'**
  String get servicesImportParseFailed;

  /// servicesImportDeactivateMissing
  ///
  /// In ar, this message translates to:
  /// **'إيقاف الخدمات غير الموجودة بالملف'**
  String get servicesImportDeactivateMissing;

  /// servicesImportDeactivateMissingHint
  ///
  /// In ar, this message translates to:
  /// **'أي خدمة عندك حاليًا ولم تظهر بهذا الملف تُوقَف تلقائيًا'**
  String get servicesImportDeactivateMissingHint;

  /// servicesImportConfirm
  ///
  /// In ar, this message translates to:
  /// **'استيراد'**
  String get servicesImportConfirm;

  /// servicesImportClose
  ///
  /// In ar, this message translates to:
  /// **'تم'**
  String get servicesImportClose;

  /// servicesImportRowCount
  ///
  /// In ar, this message translates to:
  /// **'{n, plural, =0{لا صفوف} one{صف واحد} other{{n} صف}} جاهزة للاستيراد'**
  String servicesImportRowCount(int n);

  /// servicesImportDone
  ///
  /// In ar, this message translates to:
  /// **'أُضيفت {created}، وحُدّثت {updated}، وأُعيد تفعيل {reactivated}.'**
  String servicesImportDone(int created, int updated, int reactivated);

  /// visitPackagesSectionTitle
  ///
  /// In ar, this message translates to:
  /// **'باقات مميّزة'**
  String get visitPackagesSectionTitle;

  /// visitNameFieldHint
  ///
  /// In ar, this message translates to:
  /// **'اسم العميل (اختياري)'**
  String get visitNameFieldHint;

  /// visitMeterFieldHint
  ///
  /// In ar, this message translates to:
  /// **'قراءة العدّاد'**
  String get visitMeterFieldHint;

  /// visitQuantityDialogTitle
  ///
  /// In ar, this message translates to:
  /// **'الكمية'**
  String get visitQuantityDialogTitle;

  /// visitCouponCheckboxLabel
  ///
  /// In ar, this message translates to:
  /// **'منح كوبون خصم لمحل آخر'**
  String get visitCouponCheckboxLabel;

  /// visitCouponPhoneHint
  ///
  /// In ar, this message translates to:
  /// **'جوال صاحب المحل'**
  String get visitCouponPhoneHint;

  /// visitClearAllButton
  ///
  /// In ar, this message translates to:
  /// **'مسح الكل'**
  String get visitClearAllButton;

  /// visitServicesSelectedCount
  ///
  /// In ar, this message translates to:
  /// **'{n, plural, one{خدمة واحدة مختارة} other{{n} خدمة مختارة}}'**
  String visitServicesSelectedCount(int n);

  /// visitTodayBookingsTitle
  ///
  /// In ar, this message translates to:
  /// **'مواعيد اليوم'**
  String get visitTodayBookingsTitle;

  /// visitBookingAttendFailed
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تسجيل الحضور، حاول مرة أخرى'**
  String get visitBookingAttendFailed;

  /// branchSwitcherChooseBranch
  ///
  /// In ar, this message translates to:
  /// **'اختر الفرع'**
  String get branchSwitcherChooseBranch;

  /// branchSwitcherTitle
  ///
  /// In ar, this message translates to:
  /// **'الفرع الحالي'**
  String get branchSwitcherTitle;

  /// branchSwitcherHint
  ///
  /// In ar, this message translates to:
  /// **'كل ما تفتحه بعدها يخص هذا الفرع'**
  String get branchSwitcherHint;

  /// proceduresPrintFailed
  ///
  /// In ar, this message translates to:
  /// **'تعذّر إنشاء المستند'**
  String get proceduresPrintFailed;

  /// proceduresTitle
  ///
  /// In ar, this message translates to:
  /// **'الإجراءات'**
  String get proceduresTitle;

  /// proceduresSubtitle
  ///
  /// In ar, this message translates to:
  /// **'اضبط قائمة الإجراءات لكل خدمة، أو أدر المكتبة المشتركة كاملة. اضغط مطوّلًا على خدمة لتحديدها للطباعة'**
  String get proceduresSubtitle;

  /// proceduresLibraryLink
  ///
  /// In ar, this message translates to:
  /// **'مكتبة الإجراءات'**
  String get proceduresLibraryLink;

  /// proceduresPrint
  ///
  /// In ar, this message translates to:
  /// **'طباعة'**
  String get proceduresPrint;

  /// proceduresEmptyTitle
  ///
  /// In ar, this message translates to:
  /// **'لا خدمات نشطة بعد'**
  String get proceduresEmptyTitle;

  /// servicesStepSeverityNormal
  ///
  /// In ar, this message translates to:
  /// **'عادي'**
  String get servicesStepSeverityNormal;

  /// servicesStepSeverityCritical
  ///
  /// In ar, this message translates to:
  /// **'حرج'**
  String get servicesStepSeverityCritical;

  /// proceduresSaveFailed
  ///
  /// In ar, this message translates to:
  /// **'تعذّر الحفظ'**
  String get proceduresSaveFailed;

  /// proceduresDrawerSubtitle
  ///
  /// In ar, this message translates to:
  /// **'رتّب الإجراءات بالسحب، أو أضف إجراءً من المكتبة'**
  String get proceduresDrawerSubtitle;

  /// proceduresDrawerEmpty
  ///
  /// In ar, this message translates to:
  /// **'لا إجراءات لهذه الخدمة بعد'**
  String get proceduresDrawerEmpty;

  /// proceduresDrawerAddButton
  ///
  /// In ar, this message translates to:
  /// **'إضافة من المكتبة'**
  String get proceduresDrawerAddButton;

  /// proceduresPickTitle
  ///
  /// In ar, this message translates to:
  /// **'اختيار إجراء'**
  String get proceduresPickTitle;

  /// proceduresPickClose
  ///
  /// In ar, this message translates to:
  /// **'إغلاق'**
  String get proceduresPickClose;

  /// proceduresPickApply
  ///
  /// In ar, this message translates to:
  /// **'إضافة'**
  String get proceduresPickApply;

  /// proceduresPickSearch
  ///
  /// In ar, this message translates to:
  /// **'ابحث بالإجراءات'**
  String get proceduresPickSearch;

  /// proceduresPickEmpty
  ///
  /// In ar, this message translates to:
  /// **'لا نتائج'**
  String get proceduresPickEmpty;

  /// proceduresPickCreatePlaceholder
  ///
  /// In ar, this message translates to:
  /// **'إجراء جديد...'**
  String get proceduresPickCreatePlaceholder;

  /// proceduresLibrarySaveFailed
  ///
  /// In ar, this message translates to:
  /// **'تعذّر الحفظ'**
  String get proceduresLibrarySaveFailed;

  /// proceduresLibraryTitle
  ///
  /// In ar, this message translates to:
  /// **'مكتبة الإجراءات'**
  String get proceduresLibraryTitle;

  /// proceduresLibrarySubtitle
  ///
  /// In ar, this message translates to:
  /// **'كل إجراء هنا مشترك بين كل الخدمات اللي تستخدمه — تعديله يغيّره بكل مكان'**
  String get proceduresLibrarySubtitle;

  /// proceduresLibraryNewPlaceholder
  ///
  /// In ar, this message translates to:
  /// **'نص الإجراء الجديد'**
  String get proceduresLibraryNewPlaceholder;

  /// proceduresLibraryAdd
  ///
  /// In ar, this message translates to:
  /// **'إضافة'**
  String get proceduresLibraryAdd;

  /// proceduresLibraryShowRetired
  ///
  /// In ar, this message translates to:
  /// **'إظهار الملغاة'**
  String get proceduresLibraryShowRetired;

  /// proceduresLibraryEmpty
  ///
  /// In ar, this message translates to:
  /// **'لا إجراءات بعد'**
  String get proceduresLibraryEmpty;

  /// proceduresLibraryRetired
  ///
  /// In ar, this message translates to:
  /// **'ملغى'**
  String get proceduresLibraryRetired;

  /// proceduresLibraryRetire
  ///
  /// In ar, this message translates to:
  /// **'إلغاء'**
  String get proceduresLibraryRetire;

  /// proceduresLibraryReactivate
  ///
  /// In ar, this message translates to:
  /// **'إعادة تفعيل'**
  String get proceduresLibraryReactivate;

  /// proceduresSeverityHint
  ///
  /// In ar, this message translates to:
  /// **'الإجراء الحرج يُبرَز للموظف بلون مختلف، ولا يجوز تخطّيه أثناء تنفيذ الخدمة'**
  String get proceduresSeverityHint;

  /// proceduresSelectedCount
  ///
  /// In ar, this message translates to:
  /// **'{n} محددة'**
  String proceduresSelectedCount(int n);

  /// proceduresStepCount
  ///
  /// In ar, this message translates to:
  /// **'{n} إجراء'**
  String proceduresStepCount(int n);

  /// proceduresUsedIn
  ///
  /// In ar, this message translates to:
  /// **'مستخدم بـ{n} خدمة'**
  String proceduresUsedIn(int n);

  /// mutualBenefitProposeButton
  ///
  /// In ar, this message translates to:
  /// **'اقتراح شراكة'**
  String get mutualBenefitProposeButton;

  /// mutualBenefitTitle
  ///
  /// In ar, this message translates to:
  /// **'تبادل منافع'**
  String get mutualBenefitTitle;

  /// mutualBenefitSubtitle
  ///
  /// In ar, this message translates to:
  /// **'انقل عملاء حقيقيين بينك وبين محلات أخرى، باتفاق متبادل'**
  String get mutualBenefitSubtitle;

  /// mutualBenefitRoleAll
  ///
  /// In ar, this message translates to:
  /// **'الكل'**
  String get mutualBenefitRoleAll;

  /// mutualBenefitRoleReferrer
  ///
  /// In ar, this message translates to:
  /// **'كمُحيل'**
  String get mutualBenefitRoleReferrer;

  /// mutualBenefitRoleBeneficiary
  ///
  /// In ar, this message translates to:
  /// **'كمستفيد'**
  String get mutualBenefitRoleBeneficiary;

  /// mutualBenefitLoadFailed
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تحميل الشراكات'**
  String get mutualBenefitLoadFailed;

  /// mutualBenefitEmptyTitle
  ///
  /// In ar, this message translates to:
  /// **'لا شراكات بعد'**
  String get mutualBenefitEmptyTitle;

  /// mutualBenefitKpiAsReferrer
  ///
  /// In ar, this message translates to:
  /// **'كمُحيل'**
  String get mutualBenefitKpiAsReferrer;

  /// mutualBenefitKpiAsBeneficiary
  ///
  /// In ar, this message translates to:
  /// **'كمستفيد'**
  String get mutualBenefitKpiAsBeneficiary;

  /// mutualBenefitKpiSent
  ///
  /// In ar, this message translates to:
  /// **'أُحيل'**
  String get mutualBenefitKpiSent;

  /// mutualBenefitKpiRedeemed
  ///
  /// In ar, this message translates to:
  /// **'استُبدل'**
  String get mutualBenefitKpiRedeemed;

  /// mutualBenefitKpiRate
  ///
  /// In ar, this message translates to:
  /// **'نسبة الاستبدال'**
  String get mutualBenefitKpiRate;

  /// mutualBenefitConfirm
  ///
  /// In ar, this message translates to:
  /// **'تأكيد'**
  String get mutualBenefitConfirm;

  /// mutualBenefitGrantDiscountBlanket
  ///
  /// In ar, this message translates to:
  /// **'خصم على كامل الزيارة'**
  String get mutualBenefitGrantDiscountBlanket;

  /// mutualBenefitStatusProposed
  ///
  /// In ar, this message translates to:
  /// **'مقترحة'**
  String get mutualBenefitStatusProposed;

  /// mutualBenefitStatusActive
  ///
  /// In ar, this message translates to:
  /// **'نشطة'**
  String get mutualBenefitStatusActive;

  /// mutualBenefitStatusPaused
  ///
  /// In ar, this message translates to:
  /// **'متوقفة مؤقتًا'**
  String get mutualBenefitStatusPaused;

  /// mutualBenefitStatusCancelRequested
  ///
  /// In ar, this message translates to:
  /// **'طُلب إنهاؤها'**
  String get mutualBenefitStatusCancelRequested;

  /// mutualBenefitStatusEnded
  ///
  /// In ar, this message translates to:
  /// **'منتهية'**
  String get mutualBenefitStatusEnded;

  /// mutualBenefitStatusRejected
  ///
  /// In ar, this message translates to:
  /// **'مرفوضة'**
  String get mutualBenefitStatusRejected;

  /// mutualBenefitStatusExpiredUnanswered
  ///
  /// In ar, this message translates to:
  /// **'انتهت بلا رد'**
  String get mutualBenefitStatusExpiredUnanswered;

  /// mutualBenefitEventProposed
  ///
  /// In ar, this message translates to:
  /// **'اقتراح الشراكة'**
  String get mutualBenefitEventProposed;

  /// mutualBenefitEventAccepted
  ///
  /// In ar, this message translates to:
  /// **'قبول الشراكة'**
  String get mutualBenefitEventAccepted;

  /// mutualBenefitEventRejected
  ///
  /// In ar, this message translates to:
  /// **'رفض الشراكة'**
  String get mutualBenefitEventRejected;

  /// mutualBenefitEventActivated
  ///
  /// In ar, this message translates to:
  /// **'تفعيل الشراكة'**
  String get mutualBenefitEventActivated;

  /// mutualBenefitEventCancelRequested
  ///
  /// In ar, this message translates to:
  /// **'طلب إنهاء'**
  String get mutualBenefitEventCancelRequested;

  /// mutualBenefitEventCancelConfirmed
  ///
  /// In ar, this message translates to:
  /// **'تأكيد الإنهاء'**
  String get mutualBenefitEventCancelConfirmed;

  /// mutualBenefitEventExpiredUnanswered
  ///
  /// In ar, this message translates to:
  /// **'انتهت المهلة بلا رد'**
  String get mutualBenefitEventExpiredUnanswered;

  /// mutualBenefitEventPaused
  ///
  /// In ar, this message translates to:
  /// **'إيقاف مؤقت'**
  String get mutualBenefitEventPaused;

  /// mutualBenefitEventResumed
  ///
  /// In ar, this message translates to:
  /// **'استئناف'**
  String get mutualBenefitEventResumed;

  /// mutualBenefitEventEndedTerm
  ///
  /// In ar, this message translates to:
  /// **'انتهت المدة'**
  String get mutualBenefitEventEndedTerm;

  /// mutualBenefitEventGrantCreated
  ///
  /// In ar, this message translates to:
  /// **'منحة جديدة'**
  String get mutualBenefitEventGrantCreated;

  /// mutualBenefitEventGrantRedeemed
  ///
  /// In ar, this message translates to:
  /// **'استبدال منحة'**
  String get mutualBenefitEventGrantRedeemed;

  /// mutualBenefitActivityActive
  ///
  /// In ar, this message translates to:
  /// **'نشطة'**
  String get mutualBenefitActivityActive;

  /// mutualBenefitActivityPaused
  ///
  /// In ar, this message translates to:
  /// **'متوقفة مؤقتًا'**
  String get mutualBenefitActivityPaused;

  /// mutualBenefitActivityPending
  ///
  /// In ar, this message translates to:
  /// **'بانتظار الرد'**
  String get mutualBenefitActivityPending;

  /// mutualBenefitActivityInactive
  ///
  /// In ar, this message translates to:
  /// **'غير نشطة'**
  String get mutualBenefitActivityInactive;

  /// mutualBenefitScorecardTitle
  ///
  /// In ar, this message translates to:
  /// **'الأداء'**
  String get mutualBenefitScorecardTitle;

  /// mutualBenefitScorecardFailed
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تحميل الأداء'**
  String get mutualBenefitScorecardFailed;

  /// mutualBenefitActivityTitle
  ///
  /// In ar, this message translates to:
  /// **'النشاط الأخير'**
  String get mutualBenefitActivityTitle;

  /// mutualBenefitActivityEmpty
  ///
  /// In ar, this message translates to:
  /// **'لا نشاط بعد'**
  String get mutualBenefitActivityEmpty;

  /// mutualBenefitAgreementsTitle
  ///
  /// In ar, this message translates to:
  /// **'الاتفاقيات'**
  String get mutualBenefitAgreementsTitle;

  /// mutualBenefitConfirmCancel
  ///
  /// In ar, this message translates to:
  /// **'تأكيد إنهاء هذه الشراكة نهائيًا؟'**
  String get mutualBenefitConfirmCancel;

  /// mutualBenefitActionAccept
  ///
  /// In ar, this message translates to:
  /// **'قبول'**
  String get mutualBenefitActionAccept;

  /// mutualBenefitActionReject
  ///
  /// In ar, this message translates to:
  /// **'رفض'**
  String get mutualBenefitActionReject;

  /// mutualBenefitActionWaitingThem
  ///
  /// In ar, this message translates to:
  /// **'بانتظار الطرف الآخر'**
  String get mutualBenefitActionWaitingThem;

  /// mutualBenefitActionCancelRequest
  ///
  /// In ar, this message translates to:
  /// **'طلب إنهاء'**
  String get mutualBenefitActionCancelRequest;

  /// mutualBenefitActionCancelConfirm
  ///
  /// In ar, this message translates to:
  /// **'تأكيد الإنهاء'**
  String get mutualBenefitActionCancelConfirm;

  /// mutualBenefitProposeTitle
  ///
  /// In ar, this message translates to:
  /// **'اقتراح شراكة جديدة'**
  String get mutualBenefitProposeTitle;

  /// mutualBenefitProposePhoneLabel
  ///
  /// In ar, this message translates to:
  /// **'جوال المحل الآخر'**
  String get mutualBenefitProposePhoneLabel;

  /// mutualBenefitProposeConditionLabel
  ///
  /// In ar, this message translates to:
  /// **'شرط الاستحقاق عندك'**
  String get mutualBenefitProposeConditionLabel;

  /// mutualBenefitConditionMinTotal
  ///
  /// In ar, this message translates to:
  /// **'حد أدنى للفاتورة'**
  String get mutualBenefitConditionMinTotal;

  /// mutualBenefitConditionServiceId
  ///
  /// In ar, this message translates to:
  /// **'خدمة معينة'**
  String get mutualBenefitConditionServiceId;

  /// mutualBenefitProposeConditionValueRiyals
  ///
  /// In ar, this message translates to:
  /// **'المبلغ (ريال)'**
  String get mutualBenefitProposeConditionValueRiyals;

  /// mutualBenefitProposeConditionValueService
  ///
  /// In ar, this message translates to:
  /// **'الخدمة'**
  String get mutualBenefitProposeConditionValueService;

  /// mutualBenefitProposeValidityLabel
  ///
  /// In ar, this message translates to:
  /// **'الصلاحية (يوم)'**
  String get mutualBenefitProposeValidityLabel;

  /// mutualBenefitProposeDurationLabel
  ///
  /// In ar, this message translates to:
  /// **'المدة (يوم)'**
  String get mutualBenefitProposeDurationLabel;

  /// mutualBenefitProposeCapLabel
  ///
  /// In ar, this message translates to:
  /// **'الحد كل 30 يوم'**
  String get mutualBenefitProposeCapLabel;

  /// mutualBenefitProposeGrantTypeLabel
  ///
  /// In ar, this message translates to:
  /// **'نوع المنحة'**
  String get mutualBenefitProposeGrantTypeLabel;

  /// mutualBenefitGrantTypeDiscount
  ///
  /// In ar, this message translates to:
  /// **'خصم'**
  String get mutualBenefitGrantTypeDiscount;

  /// mutualBenefitGrantTypeGift
  ///
  /// In ar, this message translates to:
  /// **'هدية'**
  String get mutualBenefitGrantTypeGift;

  /// mutualBenefitScopeBlanket
  ///
  /// In ar, this message translates to:
  /// **'كامل الزيارة'**
  String get mutualBenefitScopeBlanket;

  /// mutualBenefitScopeItem
  ///
  /// In ar, this message translates to:
  /// **'خدمة معينة'**
  String get mutualBenefitScopeItem;

  /// mutualBenefitScopeGroup
  ///
  /// In ar, this message translates to:
  /// **'مجموعة/باقة'**
  String get mutualBenefitScopeGroup;

  /// mutualBenefitProposeServiceLabel
  ///
  /// In ar, this message translates to:
  /// **'الخدمة'**
  String get mutualBenefitProposeServiceLabel;

  /// mutualBenefitProposeGroupLabel
  ///
  /// In ar, this message translates to:
  /// **'المجموعة'**
  String get mutualBenefitProposeGroupLabel;

  /// mutualBenefitProposeImmutableNote
  ///
  /// In ar, this message translates to:
  /// **'شروط المنحة ثابتة بعد الإرسال — أي تغيير يحتاج اتفاقية جديدة'**
  String get mutualBenefitProposeImmutableNote;

  /// mutualBenefitProposeSubmitting
  ///
  /// In ar, this message translates to:
  /// **'جارٍ الإرسال...'**
  String get mutualBenefitProposeSubmitting;

  /// mutualBenefitProposeSubmit
  ///
  /// In ar, this message translates to:
  /// **'إرسال الاقتراح'**
  String get mutualBenefitProposeSubmit;

  /// mutualBenefitGrantGift
  ///
  /// In ar, this message translates to:
  /// **'هدية: {name}'**
  String mutualBenefitGrantGift(String name);

  /// mutualBenefitGrantDiscountItem
  ///
  /// In ar, this message translates to:
  /// **'خصم على: {name}'**
  String mutualBenefitGrantDiscountItem(String name);

  /// mutualBenefitGrantDiscountGroup
  ///
  /// In ar, this message translates to:
  /// **'خصم على مجموعة: {name}'**
  String mutualBenefitGrantDiscountGroup(String name);

  /// mutualBenefitPartnerCount
  ///
  /// In ar, this message translates to:
  /// **'{n} اتفاقية'**
  String mutualBenefitPartnerCount(int n);

  /// mutualBenefitProposeResultFail
  ///
  /// In ar, this message translates to:
  /// **'تعذّر إرسال الاقتراح'**
  String get mutualBenefitProposeResultFail;

  /// mutualBenefitRefusal402
  ///
  /// In ar, this message translates to:
  /// **'محلك غير مشترك بتطبيق تبادل منافع — اشترك من متجر التطبيقات أولًا'**
  String get mutualBenefitRefusal402;

  /// mutualBenefitRefusal403
  ///
  /// In ar, this message translates to:
  /// **'لا تملك صلاحية كافية لهذا الإجراء'**
  String get mutualBenefitRefusal403;

  /// mutualBenefitRefusal400
  ///
  /// In ar, this message translates to:
  /// **'بيانات الاقتراح غير صحيحة — تأكد من الشرط، أو أنك لا تقترح شراكة على محلك نفسه'**
  String get mutualBenefitRefusal400;

  /// mutualBenefitRefusal404
  ///
  /// In ar, this message translates to:
  /// **'لم يُعثر على محل بهذا الرقم، أو على الخدمة/المجموعة المختارة بكتالوج الطرف الآخر'**
  String get mutualBenefitRefusal404;

  /// mutualBenefitRefusal409
  ///
  /// In ar, this message translates to:
  /// **'تجاوزت الحد الأقصى للشراكات النشطة (3)، أو حالة الشراكة تغيّرت'**
  String get mutualBenefitRefusal409;

  /// mutualBenefitRefusal503
  ///
  /// In ar, this message translates to:
  /// **'خدمة الفوترة غير متاحة حاليًا، حاول لاحقًا'**
  String get mutualBenefitRefusal503;

  /// appStoreTitle
  ///
  /// In ar, this message translates to:
  /// **'متجر التطبيقات'**
  String get appStoreTitle;

  /// appStoreSubtitle
  ///
  /// In ar, this message translates to:
  /// **'طوّر محلك بتطبيقات حقيقية، واحد واحد'**
  String get appStoreSubtitle;

  /// appStoreTabMine
  ///
  /// In ar, this message translates to:
  /// **'تطبيقاتي'**
  String get appStoreTabMine;

  /// appStoreTabAll
  ///
  /// In ar, this message translates to:
  /// **'متجر التطبيقات'**
  String get appStoreTabAll;

  /// appStoreDetails
  ///
  /// In ar, this message translates to:
  /// **'التفاصيل'**
  String get appStoreDetails;

  /// appStorePerMonth
  ///
  /// In ar, this message translates to:
  /// **'شهريًا'**
  String get appStorePerMonth;

  /// appStorePerMonthShort
  ///
  /// In ar, this message translates to:
  /// **'/شهر'**
  String get appStorePerMonthShort;

  /// appStoreActive
  ///
  /// In ar, this message translates to:
  /// **'نشط'**
  String get appStoreActive;

  /// appStoreTrialing
  ///
  /// In ar, this message translates to:
  /// **'تجريبي'**
  String get appStoreTrialing;

  /// appStoreSubscribe
  ///
  /// In ar, this message translates to:
  /// **'اشترك الآن'**
  String get appStoreSubscribe;

  /// appStoreCancelRenewal
  ///
  /// In ar, this message translates to:
  /// **'إيقاف التجديد'**
  String get appStoreCancelRenewal;

  /// appStoreUndoCancel
  ///
  /// In ar, this message translates to:
  /// **'تراجع عن الإيقاف'**
  String get appStoreUndoCancel;

  /// appStoreConfirmCancel
  ///
  /// In ar, this message translates to:
  /// **'هل تريد إيقاف تجديد هذا التطبيق؟ يستمر لين نهاية الفترة المدفوعة'**
  String get appStoreConfirmCancel;

  /// appStoreCartCount
  ///
  /// In ar, this message translates to:
  /// **'{n} بالسلة'**
  String appStoreCartCount(int n);

  /// appStoreCheckout
  ///
  /// In ar, this message translates to:
  /// **'إتمام الشراء'**
  String get appStoreCheckout;

  /// appStoreCheckingOut
  ///
  /// In ar, this message translates to:
  /// **'جاري الشراء...'**
  String get appStoreCheckingOut;

  /// appStoreRefusal402
  ///
  /// In ar, this message translates to:
  /// **'الدفع غير مفعّل على حسابك حاليًا — تواصل معنا لتفعيله'**
  String get appStoreRefusal402;

  /// appStoreRefusal403
  ///
  /// In ar, this message translates to:
  /// **'لا صلاحية لك لإتمام عملية الشراء هذه'**
  String get appStoreRefusal403;

  /// appStoreRefusal404
  ///
  /// In ar, this message translates to:
  /// **'لم يُعثر على الباقة المطلوبة — أعد المحاولة بعد تحديث الشاشة'**
  String get appStoreRefusal404;

  /// appStoreRefusal409
  ///
  /// In ar, this message translates to:
  /// **'هذا التطبيق مملوك مسبقًا أو تغيّرت حالته أثناء الشراء'**
  String get appStoreRefusal409;

  /// appStoreRefusalGeneric
  ///
  /// In ar, this message translates to:
  /// **'تعذّر إتمام الشراء، حاول مرة أخرى'**
  String get appStoreRefusalGeneric;

  /// appStoreCapacityTitle
  ///
  /// In ar, this message translates to:
  /// **'السعة'**
  String get appStoreCapacityTitle;

  /// appStoreCapacityConfirmRemove
  ///
  /// In ar, this message translates to:
  /// **'هل تريد إزالة آخر وحدة من \"{name}\"؟ هذا يوقف تجديده بالكامل'**
  String appStoreCapacityConfirmRemove(String name);

  /// No description provided for @appStoreCartSubtotal.
  ///
  /// In ar, this message translates to:
  /// **'الإجمالي الفرعي'**
  String get appStoreCartSubtotal;

  /// No description provided for @appStoreCartDiscount.
  ///
  /// In ar, this message translates to:
  /// **'الخصم'**
  String get appStoreCartDiscount;

  /// No description provided for @appStoreCartTax.
  ///
  /// In ar, this message translates to:
  /// **'الضريبة'**
  String get appStoreCartTax;

  /// No description provided for @appStoreCartTotal.
  ///
  /// In ar, this message translates to:
  /// **'الإجمالي'**
  String get appStoreCartTotal;

  /// No description provided for @appStoreCartDiscountCaveat.
  ///
  /// In ar, this message translates to:
  /// **'السعر المعروض قبل الخصم والضريبة؛ المبلغ الفعلي يُحسب ويظهر عند الدفع.'**
  String get appStoreCartDiscountCaveat;

  /// No description provided for @appStoreCartItemDiscount.
  ///
  /// In ar, this message translates to:
  /// **'(خصم {percent}٪)'**
  String appStoreCartItemDiscount(int percent);

  /// No description provided for @appStoreAutoAdded.
  ///
  /// In ar, this message translates to:
  /// **'أُضيف \"{added}\" تلقائيًا لأن \"{trigger}\" يحتاج إليه.'**
  String appStoreAutoAdded(String added, String trigger);

  /// No description provided for @appStoreMissingRequirement.
  ///
  /// In ar, this message translates to:
  /// **'يحتاج تفعيل {names} أولاً.'**
  String appStoreMissingRequirement(String names);

  /// No description provided for @appStoreRequiresAnyVisit.
  ///
  /// In ar, this message translates to:
  /// **'تسجيل زيارة'**
  String get appStoreRequiresAnyVisit;

  /// No description provided for @appStoreRequiresAnyBookings.
  ///
  /// In ar, this message translates to:
  /// **'الحجوزات'**
  String get appStoreRequiresAnyBookings;

  /// No description provided for @appStoreRequiresAnyContacts.
  ///
  /// In ar, this message translates to:
  /// **'جهات الاتصال'**
  String get appStoreRequiresAnyContacts;

  /// No description provided for @appStoreRequiresAnyMobileRequests.
  ///
  /// In ar, this message translates to:
  /// **'خدمات متنقلة'**
  String get appStoreRequiresAnyMobileRequests;

  /// No description provided for @appStoreRequiresOr.
  ///
  /// In ar, this message translates to:
  /// **'أو'**
  String get appStoreRequiresOr;

  /// No description provided for @appStoreOr.
  ///
  /// In ar, this message translates to:
  /// **'أو'**
  String get appStoreOr;

  /// No description provided for @appStoreCascadeWarning.
  ///
  /// In ar, this message translates to:
  /// **'سيتوقف معه أيضًا: {names}'**
  String appStoreCascadeWarning(String names);

  /// No description provided for @appStoreDiscountBadge.
  ///
  /// In ar, this message translates to:
  /// **'خصم {percent}٪ مطبَّق'**
  String appStoreDiscountBadge(int percent);

  /// No description provided for @appStoreDiscountBadgeWithApp.
  ///
  /// In ar, this message translates to:
  /// **'خصم {percent}٪ مطبَّق من {app}'**
  String appStoreDiscountBadgeWithApp(int percent, String app);

  /// No description provided for @appStoreDiscountedShort.
  ///
  /// In ar, this message translates to:
  /// **'خصم {percent}٪'**
  String appStoreDiscountedShort(int percent);

  /// No description provided for @appStoreOfferTitle.
  ///
  /// In ar, this message translates to:
  /// **'خصم {percent}٪ بانتظارك'**
  String appStoreOfferTitle(int percent);

  /// No description provided for @appStoreOfferDesc.
  ///
  /// In ar, this message translates to:
  /// **'فعّله تلقائياً باشتراكك في {app}'**
  String appStoreOfferDesc(String app);

  /// No description provided for @appStoreAiUnitsCount.
  ///
  /// In ar, this message translates to:
  /// **'{units} وحدة'**
  String appStoreAiUnitsCount(int units);

  /// No description provided for @appStoreAiUnitsIncluded.
  ///
  /// In ar, this message translates to:
  /// **'ذكاء اصطناعي مجاناً كل شهر'**
  String get appStoreAiUnitsIncluded;

  /// No description provided for @whatsappAssistantTitle.
  ///
  /// In ar, this message translates to:
  /// **'المساعد الذكي'**
  String get whatsappAssistantTitle;

  /// No description provided for @whatsappAssistantSubtitle.
  ///
  /// In ar, this message translates to:
  /// **'يرد على عملائك بواتساب نيابة عنك، ويقترح عليهم باقاتك ونقاطهم في الوقت المناسب.'**
  String get whatsappAssistantSubtitle;

  /// No description provided for @whatsappAssistantLoadFailed.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تحميل إعدادات المساعد الذكي.'**
  String get whatsappAssistantLoadFailed;

  /// No description provided for @whatsappAssistantConfirm.
  ///
  /// In ar, this message translates to:
  /// **'تأكيد'**
  String get whatsappAssistantConfirm;

  /// No description provided for @whatsappAssistantSaveFailed.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر الحفظ، حاول مرة أخرى.'**
  String get whatsappAssistantSaveFailed;

  /// No description provided for @whatsappAssistantToggleTitle.
  ///
  /// In ar, this message translates to:
  /// **'المساعد يرد الآن'**
  String get whatsappAssistantToggleTitle;

  /// No description provided for @whatsappAssistantToggleDesc.
  ///
  /// In ar, this message translates to:
  /// **'إيقافه يقفل المساعد تمامًا، بدون إلغاء اشتراكك — ترجعه متى شئت.'**
  String get whatsappAssistantToggleDesc;

  /// No description provided for @whatsappAssistantToggleConfirmEnableTitle.
  ///
  /// In ar, this message translates to:
  /// **'تشغيل المساعد الذكي؟'**
  String get whatsappAssistantToggleConfirmEnableTitle;

  /// No description provided for @whatsappAssistantToggleConfirmEnableBody.
  ///
  /// In ar, this message translates to:
  /// **'بيبدأ يرد على عملائك بواتساب فورًا.'**
  String get whatsappAssistantToggleConfirmEnableBody;

  /// No description provided for @whatsappAssistantToggleConfirmDisableTitle.
  ///
  /// In ar, this message translates to:
  /// **'إيقاف المساعد الذكي؟'**
  String get whatsappAssistantToggleConfirmDisableTitle;

  /// No description provided for @whatsappAssistantToggleConfirmDisableBody.
  ///
  /// In ar, this message translates to:
  /// **'بيتوقف عن الرد تمامًا، وكأنك غير مشترك فيه — بدون إلغاء الاشتراك نفسه.'**
  String get whatsappAssistantToggleConfirmDisableBody;

  /// No description provided for @whatsappAssistantNotesTitle.
  ///
  /// In ar, this message translates to:
  /// **'ملاحظات المحل'**
  String get whatsappAssistantNotesTitle;

  /// No description provided for @whatsappAssistantNotesDesc.
  ///
  /// In ar, this message translates to:
  /// **'ما تكتبه هنا يساعد المساعد الذكي يخدم عملاءك بمعلومات إضافية عن محلك.'**
  String get whatsappAssistantNotesDesc;

  /// No description provided for @whatsappAssistantWordLimitTitle.
  ///
  /// In ar, this message translates to:
  /// **'حد كلمات رسالة العميل'**
  String get whatsappAssistantWordLimitTitle;

  /// No description provided for @whatsappAssistantWordLimitDesc.
  ///
  /// In ar, this message translates to:
  /// **'أطول رسالة يقبلها المساعد من العميل قبل ما يطلب منه اختصارها.'**
  String get whatsappAssistantWordLimitDesc;

  /// No description provided for @whatsappAssistantAutoRegisterTitle.
  ///
  /// In ar, this message translates to:
  /// **'تسجيل جهات الاتصال تلقائيًا'**
  String get whatsappAssistantAutoRegisterTitle;

  /// No description provided for @whatsappAssistantAutoRegisterDesc.
  ///
  /// In ar, this message translates to:
  /// **'أي رقم جديد يراسل واتسابك يُسجَّل تلقائيًا كجهة اتصال حقيقية.'**
  String get whatsappAssistantAutoRegisterDesc;

  /// No description provided for @whatsappAssistantAutoRegisterConfirmEnableTitle.
  ///
  /// In ar, this message translates to:
  /// **'تفعيل التسجيل التلقائي؟'**
  String get whatsappAssistantAutoRegisterConfirmEnableTitle;

  /// No description provided for @whatsappAssistantAutoRegisterConfirmEnableBody.
  ///
  /// In ar, this message translates to:
  /// **'كل من يراسل رقمك بواتساب راح يُسجَّل تلقائيًا كجهة اتصال، حتى لو رسالة وحدة.'**
  String get whatsappAssistantAutoRegisterConfirmEnableBody;

  /// No description provided for @whatsappAssistantAutoRegisterConfirmDisableTitle.
  ///
  /// In ar, this message translates to:
  /// **'إيقاف التسجيل التلقائي؟'**
  String get whatsappAssistantAutoRegisterConfirmDisableTitle;

  /// No description provided for @whatsappAssistantAutoRegisterConfirmDisableBody.
  ///
  /// In ar, this message translates to:
  /// **'الأرقام الجديدة ما راح تُسجَّل كجهات اتصال تلقائيًا بعد الآن.'**
  String get whatsappAssistantAutoRegisterConfirmDisableBody;

  /// No description provided for @partnerLoyaltyTitle.
  ///
  /// In ar, this message translates to:
  /// **'ولاء الشركاء'**
  String get partnerLoyaltyTitle;

  /// No description provided for @partnerLoyaltySubtitle.
  ///
  /// In ar, this message translates to:
  /// **'كوّن تحالفاً مع محل آخر مسجّل عندنا وامنحه امتيازاً على اشتراكه معنا'**
  String get partnerLoyaltySubtitle;

  /// No description provided for @partnerLoyaltyCapLabel.
  ///
  /// In ar, this message translates to:
  /// **'سقفك الحالي'**
  String get partnerLoyaltyCapLabel;

  /// No description provided for @partnerLoyaltyPrefsTitle.
  ///
  /// In ar, this message translates to:
  /// **'خانة تكوين التحالف أثناء تسجيل الزيارة'**
  String get partnerLoyaltyPrefsTitle;

  /// No description provided for @partnerLoyaltyPrefsDesc.
  ///
  /// In ar, this message translates to:
  /// **'تشغيلها يسمح لأي موظف يسجّل زيارة إنه يكوّن تحالفاً بنفس اللحظة.'**
  String get partnerLoyaltyPrefsDesc;

  /// No description provided for @partnerLoyaltyGrantTitle.
  ///
  /// In ar, this message translates to:
  /// **'كوّن تحالفاً'**
  String get partnerLoyaltyGrantTitle;

  /// No description provided for @partnerLoyaltyPhoneLabel.
  ///
  /// In ar, this message translates to:
  /// **'رقم جوال المحل الشريك'**
  String get partnerLoyaltyPhoneLabel;

  /// No description provided for @partnerLoyaltyPhoneHintOk.
  ///
  /// In ar, this message translates to:
  /// **'لا تحالف بينكما هذا الشهر'**
  String get partnerLoyaltyPhoneHintOk;

  /// No description provided for @partnerLoyaltyPhoneHintAlready.
  ///
  /// In ar, this message translates to:
  /// **'عندك تحالف معه هذا الشهر بالفعل'**
  String get partnerLoyaltyPhoneHintAlready;

  /// No description provided for @partnerLoyaltyPhoneHintUnregistered.
  ///
  /// In ar, this message translates to:
  /// **'هذا الرقم ليس محلاً مسجّلاً عندنا'**
  String get partnerLoyaltyPhoneHintUnregistered;

  /// No description provided for @partnerLoyaltyPercentLabel.
  ///
  /// In ar, this message translates to:
  /// **'نسبة الامتياز'**
  String get partnerLoyaltyPercentLabel;

  /// No description provided for @partnerLoyaltyCapLine.
  ///
  /// In ar, this message translates to:
  /// **'أقصى نسبة تقدر تمنحها الآن: {p}%'**
  String partnerLoyaltyCapLine(int p);

  /// No description provided for @partnerLoyaltyScopeLabel.
  ///
  /// In ar, this message translates to:
  /// **'يشمل'**
  String get partnerLoyaltyScopeLabel;

  /// No description provided for @partnerLoyaltyScopeAll.
  ///
  /// In ar, this message translates to:
  /// **'الكل'**
  String get partnerLoyaltyScopeAll;

  /// No description provided for @partnerLoyaltySubmit.
  ///
  /// In ar, this message translates to:
  /// **'كوّن التحالف'**
  String get partnerLoyaltySubmit;

  /// No description provided for @partnerLoyaltySubmitting.
  ///
  /// In ar, this message translates to:
  /// **'يُرسَل…'**
  String get partnerLoyaltySubmitting;

  /// No description provided for @partnerLoyaltyResultSuccess.
  ///
  /// In ar, this message translates to:
  /// **'تم تكوين التحالف — سيُطبَّق تلقائياً عند تجديد اشتراك المحل القادم.'**
  String get partnerLoyaltyResultSuccess;

  /// No description provided for @partnerLoyaltyResultPartial.
  ///
  /// In ar, this message translates to:
  /// **'تحالف جزئي — بعض التطبيقات رُفضت، افتح «السجل» للتفاصيل.'**
  String get partnerLoyaltyResultPartial;

  /// No description provided for @partnerLoyaltyOutcomeGranted.
  ///
  /// In ar, this message translates to:
  /// **'نجح'**
  String get partnerLoyaltyOutcomeGranted;

  /// No description provided for @partnerLoyaltyOutcomeInvalidPercent.
  ///
  /// In ar, this message translates to:
  /// **'نسبة الامتياز غير صحيحة'**
  String get partnerLoyaltyOutcomeInvalidPercent;

  /// No description provided for @partnerLoyaltyOutcomeInvalidScope.
  ///
  /// In ar, this message translates to:
  /// **'اختر تطبيقاً حقيقياً'**
  String get partnerLoyaltyOutcomeInvalidScope;

  /// No description provided for @partnerLoyaltyOutcomeOverCap.
  ///
  /// In ar, this message translates to:
  /// **'تجاوزت سقفك الحالي'**
  String get partnerLoyaltyOutcomeOverCap;

  /// No description provided for @partnerLoyaltyOutcomeNoAccount.
  ///
  /// In ar, this message translates to:
  /// **'هذا الرقم ليس محلاً مسجّلاً عندنا'**
  String get partnerLoyaltyOutcomeNoAccount;

  /// No description provided for @partnerLoyaltyOutcomeNotSubscribed.
  ///
  /// In ar, this message translates to:
  /// **'المحل لا يملك أي تطبيق ضمن ما اخترته'**
  String get partnerLoyaltyOutcomeNotSubscribed;

  /// No description provided for @partnerLoyaltyOutcomeBillingUnavailable.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر إتمام العملية، حاول مرة أخرى'**
  String get partnerLoyaltyOutcomeBillingUnavailable;

  /// No description provided for @partnerLoyaltyOutcomeAlreadyHasBetterCoupon.
  ///
  /// In ar, this message translates to:
  /// **'عنده امتياز أقوى بالفعل'**
  String get partnerLoyaltyOutcomeAlreadyHasBetterCoupon;

  /// No description provided for @partnerLoyaltyOutcomeCouponExpired.
  ///
  /// In ar, this message translates to:
  /// **'الامتياز منتهٍ'**
  String get partnerLoyaltyOutcomeCouponExpired;

  /// No description provided for @partnerLoyaltyOutcomeCouponExhausted.
  ///
  /// In ar, this message translates to:
  /// **'الامتياز استُنفد'**
  String get partnerLoyaltyOutcomeCouponExhausted;

  /// No description provided for @partnerLoyaltyOutcomeCouponUnknown.
  ///
  /// In ar, this message translates to:
  /// **'امتياز غير معروف'**
  String get partnerLoyaltyOutcomeCouponUnknown;

  /// No description provided for @partnerLoyaltyOutcomePlanMismatch.
  ///
  /// In ar, this message translates to:
  /// **'الامتياز لا يطابق هذا التطبيق'**
  String get partnerLoyaltyOutcomePlanMismatch;

  /// No description provided for @partnerLoyaltyOutcomeCouponDisabled.
  ///
  /// In ar, this message translates to:
  /// **'الامتياز معطّل'**
  String get partnerLoyaltyOutcomeCouponDisabled;

  /// No description provided for @partnerLoyaltyOutcomeCouponScheduled.
  ///
  /// In ar, this message translates to:
  /// **'الامتياز لم يبدأ بعد'**
  String get partnerLoyaltyOutcomeCouponScheduled;

  /// No description provided for @partnerLoyaltyTabLog.
  ///
  /// In ar, this message translates to:
  /// **'السجل'**
  String get partnerLoyaltyTabLog;

  /// No description provided for @partnerLoyaltyTabStats.
  ///
  /// In ar, this message translates to:
  /// **'الإحصائيات'**
  String get partnerLoyaltyTabStats;

  /// No description provided for @partnerLoyaltyLogSearchHint.
  ///
  /// In ar, this message translates to:
  /// **'بحث بآخر 4 أرقام'**
  String get partnerLoyaltyLogSearchHint;

  /// No description provided for @partnerLoyaltyLogFilterAll.
  ///
  /// In ar, this message translates to:
  /// **'كل الحالات'**
  String get partnerLoyaltyLogFilterAll;

  /// No description provided for @partnerLoyaltyLogFilterOk.
  ///
  /// In ar, this message translates to:
  /// **'ناجح فقط'**
  String get partnerLoyaltyLogFilterOk;

  /// No description provided for @partnerLoyaltyLogFilterFail.
  ///
  /// In ar, this message translates to:
  /// **'فاشل فقط'**
  String get partnerLoyaltyLogFilterFail;

  /// No description provided for @partnerLoyaltyLogEmptyTitle.
  ///
  /// In ar, this message translates to:
  /// **'لا تحالفات بعد'**
  String get partnerLoyaltyLogEmptyTitle;

  /// No description provided for @partnerLoyaltyLogEmptyDesc.
  ///
  /// In ar, this message translates to:
  /// **'أول تحالف تكوّنه يظهر هنا.'**
  String get partnerLoyaltyLogEmptyDesc;

  /// No description provided for @partnerLoyaltyLogReadFailed.
  ///
  /// In ar, this message translates to:
  /// **'تعذّرت قراءة السجل'**
  String get partnerLoyaltyLogReadFailed;

  /// No description provided for @partnerLoyaltyStatsKpiMonth.
  ///
  /// In ar, this message translates to:
  /// **'تحالفات هذا الشهر'**
  String get partnerLoyaltyStatsKpiMonth;

  /// No description provided for @partnerLoyaltyStatsKpiCap.
  ///
  /// In ar, this message translates to:
  /// **'سقفك الحالي'**
  String get partnerLoyaltyStatsKpiCap;

  /// No description provided for @partnerLoyaltyStatsKpiCeiling.
  ///
  /// In ar, this message translates to:
  /// **'السقف الأقصى بالمنصة'**
  String get partnerLoyaltyStatsKpiCeiling;

  /// No description provided for @partnerLoyaltyStatsLadderTitle.
  ///
  /// In ar, this message translates to:
  /// **'مكانك بالسلّم'**
  String get partnerLoyaltyStatsLadderTitle;

  /// No description provided for @partnerLoyaltyStatsLadderNote.
  ///
  /// In ar, this message translates to:
  /// **'{n} تحالفاً هذا الشهر — باقي {left} عشان توصل لشريحة الـ{p}%'**
  String partnerLoyaltyStatsLadderNote(int n, int left, int p);

  /// No description provided for @partnerLoyaltyStatsLadderAtTop.
  ///
  /// In ar, this message translates to:
  /// **'{n} تحالفاً هذا الشهر — أنت بأعلى شريحة'**
  String partnerLoyaltyStatsLadderAtTop(int n);

  /// No description provided for @partnerLoyaltyStatsCeilingNote.
  ///
  /// In ar, this message translates to:
  /// **'السقف الأقصى بالمنصة {p}% — ما يتجاوزه أي محل بأي حال'**
  String partnerLoyaltyStatsCeilingNote(int p);

  /// No description provided for @partnerLoyaltyStatsChartTitle.
  ///
  /// In ar, this message translates to:
  /// **'عدد التحالفات آخر 6 أشهر'**
  String get partnerLoyaltyStatsChartTitle;

  /// No description provided for @partnerLoyaltyReadFailedTitle.
  ///
  /// In ar, this message translates to:
  /// **'تعذّرت قراءة بياناتك'**
  String get partnerLoyaltyReadFailedTitle;

  /// No description provided for @partnerLoyaltyReadFailedDesc.
  ///
  /// In ar, this message translates to:
  /// **'حاول بعد قليل.'**
  String get partnerLoyaltyReadFailedDesc;

  /// No description provided for @shopReadFailed.
  ///
  /// In ar, this message translates to:
  /// **'تعذّرت قراءة مؤشرات محلّك'**
  String get shopReadFailed;

  /// No description provided for @shopMultiBranchTitle.
  ///
  /// In ar, this message translates to:
  /// **'اختر فرعًا'**
  String get shopMultiBranchTitle;

  /// No description provided for @shopMultiBranchDesc.
  ///
  /// In ar, this message translates to:
  /// **'عندك أكثر من فرع — اختر واحدًا لعرض مؤشراته.'**
  String get shopMultiBranchDesc;

  /// No description provided for @shopEmptyBranchTitle.
  ///
  /// In ar, this message translates to:
  /// **'ما فيه بيانات لهذا الفرع بعد'**
  String get shopEmptyBranchTitle;

  /// No description provided for @shopRetentionTitle.
  ///
  /// In ar, this message translates to:
  /// **'نسبة رجوع عملائك'**
  String get shopRetentionTitle;

  /// No description provided for @shopRetentionMutedNote.
  ///
  /// In ar, this message translates to:
  /// **'لسا ما فيه زيارات كافية لحساب هذا الرقم.'**
  String get shopRetentionMutedNote;

  /// No description provided for @shopRetentionBrandNew.
  ///
  /// In ar, this message translates to:
  /// **'سجّل أول زيارة عشان تبدأ نشوف نسبة رجوع عملائك.'**
  String get shopRetentionBrandNew;

  /// No description provided for @shopRegisterFirstVisit.
  ///
  /// In ar, this message translates to:
  /// **'سجّل أول زيارة'**
  String get shopRegisterFirstVisit;

  /// No description provided for @shopRetentionPrefix10.
  ///
  /// In ar, this message translates to:
  /// **'من كل 10 عملاء زاروك،'**
  String get shopRetentionPrefix10;

  /// No description provided for @shopRetentionSuffix.
  ///
  /// In ar, this message translates to:
  /// **'يرجعون لك'**
  String get shopRetentionSuffix;

  /// No description provided for @shopOneCustomer.
  ///
  /// In ar, this message translates to:
  /// **'عميل واحد زارك'**
  String get shopOneCustomer;

  /// No description provided for @shopNCustomers.
  ///
  /// In ar, this message translates to:
  /// **'{n} عميل زاروك'**
  String shopNCustomers(int n);

  /// No description provided for @shopRetentionSmallPrefix.
  ///
  /// In ar, this message translates to:
  /// **'{base}، منهم'**
  String shopRetentionSmallPrefix(String base);

  /// No description provided for @shopOverNMonths.
  ///
  /// In ar, this message translates to:
  /// **'خلال {n} أشهر'**
  String shopOverNMonths(int n);

  /// No description provided for @shopUnlimited.
  ///
  /// In ar, this message translates to:
  /// **'بلا حد'**
  String get shopUnlimited;

  /// No description provided for @shopTileSentToday.
  ///
  /// In ar, this message translates to:
  /// **'أُرسلت اليوم'**
  String get shopTileSentToday;

  /// No description provided for @shopTileWaiting.
  ///
  /// In ar, this message translates to:
  /// **'بالانتظار'**
  String get shopTileWaiting;

  /// No description provided for @shopTileCeilingRemaining.
  ///
  /// In ar, this message translates to:
  /// **'المتبقي اليوم'**
  String get shopTileCeilingRemaining;

  /// No description provided for @shopNextStepLabel.
  ///
  /// In ar, this message translates to:
  /// **'الخطوة التالية'**
  String get shopNextStepLabel;

  /// No description provided for @shopNotNow.
  ///
  /// In ar, this message translates to:
  /// **'ليس الآن'**
  String get shopNotNow;

  /// No description provided for @shopDeckUrgent.
  ///
  /// In ar, this message translates to:
  /// **'عاجل'**
  String get shopDeckUrgent;

  /// No description provided for @shopDeckWeek.
  ///
  /// In ar, this message translates to:
  /// **'الأسبوع'**
  String get shopDeckWeek;

  /// No description provided for @shopDeckOpportunities.
  ///
  /// In ar, this message translates to:
  /// **'فرص'**
  String get shopDeckOpportunities;

  /// No description provided for @shopComputedNow.
  ///
  /// In ar, this message translates to:
  /// **'احتُسبت الآن'**
  String get shopComputedNow;

  /// No description provided for @shopComputedHoursAgo.
  ///
  /// In ar, this message translates to:
  /// **'احتُسبت قبل {n} ساعة'**
  String shopComputedHoursAgo(int n);

  /// No description provided for @shopStale.
  ///
  /// In ar, this message translates to:
  /// **'قديمة'**
  String get shopStale;

  /// No description provided for @shopRefreshAction.
  ///
  /// In ar, this message translates to:
  /// **'تحديث'**
  String get shopRefreshAction;

  /// No description provided for @shopComputingTitle.
  ///
  /// In ar, this message translates to:
  /// **'جاري احتساب مؤشراتك'**
  String get shopComputingTitle;

  /// No description provided for @shopComputeLoading.
  ///
  /// In ar, this message translates to:
  /// **'يُحتسب…'**
  String get shopComputeLoading;

  /// No description provided for @shopComputeAction.
  ///
  /// In ar, this message translates to:
  /// **'احتسب الآن'**
  String get shopComputeAction;

  /// No description provided for @shopAtRiskTitle.
  ///
  /// In ar, this message translates to:
  /// **'عملاء على وشك الابتعاد'**
  String get shopAtRiskTitle;

  /// No description provided for @shopAtRiskMutedNote.
  ///
  /// In ar, this message translates to:
  /// **'لسا ما فيه بيانات كافية.'**
  String get shopAtRiskMutedNote;

  /// No description provided for @shopAtRiskAllGood.
  ///
  /// In ar, this message translates to:
  /// **'ما فيه عميل متأخر عن موعده الآن — كله تمام'**
  String get shopAtRiskAllGood;

  /// No description provided for @shopWaNotConnected.
  ///
  /// In ar, this message translates to:
  /// **'واتساب محلك غير مربوط بعد'**
  String get shopWaNotConnected;

  /// No description provided for @shopWaNotVerified.
  ///
  /// In ar, this message translates to:
  /// **'رقم واتساب محلك غير موثّق بعد'**
  String get shopWaNotVerified;

  /// No description provided for @shopCeilingReached.
  ///
  /// In ar, this message translates to:
  /// **'وصلت الحد الأقصى للرسائل اليوم'**
  String get shopCeilingReached;

  /// No description provided for @shopDaysOverdue.
  ///
  /// In ar, this message translates to:
  /// **'متأخر {n} يوم'**
  String shopDaysOverdue(int n);

  /// No description provided for @shopAtRiskCta.
  ///
  /// In ar, this message translates to:
  /// **'أرسل حملة استرجاع'**
  String get shopAtRiskCta;

  /// No description provided for @shopAiImpactTitle.
  ///
  /// In ar, this message translates to:
  /// **'أثر المساعد الذكي عبر واتساب'**
  String get shopAiImpactTitle;

  /// No description provided for @shopAiConversations.
  ///
  /// In ar, this message translates to:
  /// **'محادثات'**
  String get shopAiConversations;

  /// No description provided for @shopAiBookings.
  ///
  /// In ar, this message translates to:
  /// **'حجوزات'**
  String get shopAiBookings;

  /// No description provided for @shopAiUpsellRate.
  ///
  /// In ar, this message translates to:
  /// **'قبول العروض'**
  String get shopAiUpsellRate;

  /// No description provided for @shopWeekMutedTitle.
  ///
  /// In ar, this message translates to:
  /// **'زيارات الأسبوع'**
  String get shopWeekMutedTitle;

  /// No description provided for @shopWeekMutedNote.
  ///
  /// In ar, this message translates to:
  /// **'لسا ما فيه بيانات كافية.'**
  String get shopWeekMutedNote;

  /// No description provided for @shopNewReturningMutedTitle.
  ///
  /// In ar, this message translates to:
  /// **'عملاء جدد مقابل عائدين'**
  String get shopNewReturningMutedTitle;

  /// No description provided for @shopNewReturningMutedNote.
  ///
  /// In ar, this message translates to:
  /// **'لسا ما فيه بيانات كافية.'**
  String get shopNewReturningMutedNote;

  /// No description provided for @shopBranchCompareTitle.
  ///
  /// In ar, this message translates to:
  /// **'مقارنة الفروع'**
  String get shopBranchCompareTitle;

  /// No description provided for @shopBranchCompareMutedNote.
  ///
  /// In ar, this message translates to:
  /// **'تحتاج فرعين على الأقل عشان تقارن.'**
  String get shopBranchCompareMutedNote;

  /// No description provided for @shopStaffCompareTitle.
  ///
  /// In ar, this message translates to:
  /// **'مقارنة الموظفين'**
  String get shopStaffCompareTitle;

  /// No description provided for @shopStaffCompareMutedNote.
  ///
  /// In ar, this message translates to:
  /// **'تحتاج موظفين على الأقل عشان تقارن.'**
  String get shopStaffCompareMutedNote;

  /// No description provided for @shopWeekTitle.
  ///
  /// In ar, this message translates to:
  /// **'زيارات هذا الأسبوع'**
  String get shopWeekTitle;

  /// No description provided for @shopNewReturningTitle.
  ///
  /// In ar, this message translates to:
  /// **'جدد مقابل عائدين'**
  String get shopNewReturningTitle;

  /// No description provided for @shopNewLabel.
  ///
  /// In ar, this message translates to:
  /// **'جدد:'**
  String get shopNewLabel;

  /// No description provided for @shopReturningLabel.
  ///
  /// In ar, this message translates to:
  /// **'عائدين:'**
  String get shopReturningLabel;

  /// No description provided for @shopServicesTitle.
  ///
  /// In ar, this message translates to:
  /// **'خدماتك'**
  String get shopServicesTitle;

  /// No description provided for @shopServicesMutedNote.
  ///
  /// In ar, this message translates to:
  /// **'لسا ما فيه بيانات كافية.'**
  String get shopServicesMutedNote;

  /// No description provided for @shopMessageFlowTitle.
  ///
  /// In ar, this message translates to:
  /// **'أثر رسائل التذكير'**
  String get shopMessageFlowTitle;

  /// No description provided for @shopMutedMessageFlowNote.
  ///
  /// In ar, this message translates to:
  /// **'لسا ما فيه بيانات كافية.'**
  String get shopMutedMessageFlowNote;

  /// No description provided for @shopHoldoutTitle.
  ///
  /// In ar, this message translates to:
  /// **'مقارنة: من راسلناه مقابل من لا'**
  String get shopHoldoutTitle;

  /// No description provided for @shopMutedHoldoutNote.
  ///
  /// In ar, this message translates to:
  /// **'لسا يُقاس.'**
  String get shopMutedHoldoutNote;

  /// No description provided for @shopReturnedAfterReminder.
  ///
  /// In ar, this message translates to:
  /// **'{visits} زيارة خلال {days} يوم بعد التذكير'**
  String shopReturnedAfterReminder(int visits, int days);

  /// No description provided for @shopOptOutRate.
  ///
  /// In ar, this message translates to:
  /// **'{p}% طلبوا التوقف عن الرسائل'**
  String shopOptOutRate(String p);

  /// No description provided for @shopHoldoutNoMessages.
  ///
  /// In ar, this message translates to:
  /// **'بلا رسائل'**
  String get shopHoldoutNoMessages;

  /// No description provided for @shopHoldoutReached.
  ///
  /// In ar, this message translates to:
  /// **'راسلناهم'**
  String get shopHoldoutReached;

  /// No description provided for @shopHoldoutOff.
  ///
  /// In ar, this message translates to:
  /// **'قياس أثر الرسائل غير مُفعَّل — كل عملائك يصلهم كل شيء، فلا مجموعة نقارن بها.'**
  String get shopHoldoutOff;

  /// No description provided for @shopHoldoutMeasuring.
  ///
  /// In ar, this message translates to:
  /// **'ما زلنا نقيس أثر الرسائل على محلّك — {min} من {need} في أصغر المجموعتين.'**
  String shopHoldoutMeasuring(int min, int need);

  /// No description provided for @shopTodayRetrying.
  ///
  /// In ar, this message translates to:
  /// **'{n} رسالة تحاول الخروج'**
  String shopTodayRetrying(int n);

  /// No description provided for @shopTrendUp.
  ///
  /// In ar, this message translates to:
  /// **'تتحسّن'**
  String get shopTrendUp;

  /// No description provided for @shopTrendDown.
  ///
  /// In ar, this message translates to:
  /// **'تتراجع'**
  String get shopTrendDown;

  /// No description provided for @shopRetentionSincePeriods.
  ///
  /// In ar, this message translates to:
  /// **'منذ {n} فترات'**
  String shopRetentionSincePeriods(int n);

  /// No description provided for @shopAtLeastSuffix.
  ///
  /// In ar, this message translates to:
  /// **' — على الأقل'**
  String get shopAtLeastSuffix;

  /// No description provided for @shopRegisterFirstVisitArrow.
  ///
  /// In ar, this message translates to:
  /// **'سجّل أول زيارة ←'**
  String get shopRegisterFirstVisitArrow;

  /// No description provided for @shopWeekNoCompare.
  ///
  /// In ar, this message translates to:
  /// **'لسه ما عندنا أسبوع كامل نقارنه'**
  String get shopWeekNoCompare;

  /// No description provided for @shopNextStepAlso.
  ///
  /// In ar, this message translates to:
  /// **'وأيضاً: {msg}'**
  String shopNextStepAlso(String msg);

  /// No description provided for @shopBranchCompareUnassigned.
  ///
  /// In ar, this message translates to:
  /// **'{n} زيارة بلا فرع محدَّد — لا تُحتسب لأي فرع.'**
  String shopBranchCompareUnassigned(int n);

  /// No description provided for @shopBranchCompareNeedTwo.
  ///
  /// In ar, this message translates to:
  /// **'لا نقارن الفروع بعد — يحتاج فرعان فأكثر بزيارات حقيقية.'**
  String get shopBranchCompareNeedTwo;

  /// No description provided for @shopBranchCompareNeedSecond.
  ///
  /// In ar, this message translates to:
  /// **'فرع واحد فعّال حتى الآن — المقارنة تحتاج فرعاً ثانياً بزيارات حقيقية.'**
  String get shopBranchCompareNeedSecond;

  /// No description provided for @shopBranchCompareTooShort.
  ///
  /// In ar, this message translates to:
  /// **'لا نرتّب الفروع بعد — الفترة قصيرة، والمقارنة الآن تظلم الأحدث.'**
  String get shopBranchCompareTooShort;

  /// No description provided for @shopStaffCompareUnassigned.
  ///
  /// In ar, this message translates to:
  /// **'{n} زيارة بلا موظف محدَّد — لا تُحتسب لأحد.'**
  String shopStaffCompareUnassigned(int n);

  /// No description provided for @shopStaffCompareNeedTwo.
  ///
  /// In ar, this message translates to:
  /// **'لا نقارن الموظفين بعد — يحتاج موظفان فأكثر بزيارات منسوبة لهم.'**
  String get shopStaffCompareNeedTwo;

  /// No description provided for @shopStaffCompareNeedSecond.
  ///
  /// In ar, this message translates to:
  /// **'موظف واحد منسوب حتى الآن — المقارنة تحتاج موظفاً ثانياً بزيارات حقيقية.'**
  String get shopStaffCompareNeedSecond;

  /// No description provided for @shopStaffCompareTooShort.
  ///
  /// In ar, this message translates to:
  /// **'لا نرتّب الموظفين بعد — الفترة قصيرة، والمقارنة الآن تظلم الأحدث.'**
  String get shopStaffCompareTooShort;

  /// No description provided for @shopPeakTitle.
  ///
  /// In ar, this message translates to:
  /// **'أكثر أوقاتك ازدحامًا'**
  String get shopPeakTitle;

  /// No description provided for @shopPeakMutedNote.
  ///
  /// In ar, this message translates to:
  /// **'تحتاج زياراتٍ موزّعة على أيام وساعات كافية لنرسمها.'**
  String get shopPeakMutedNote;

  /// No description provided for @shopPeakBusiestTime.
  ///
  /// In ar, this message translates to:
  /// **'{day} حوالي الساعة {h}:00'**
  String shopPeakBusiestTime(String day, int h);

  /// No description provided for @shopPeakBusiestNote.
  ///
  /// In ar, this message translates to:
  /// **'أكثر وقت زحمة عندك: {name}.'**
  String shopPeakBusiestNote(String name);

  /// No description provided for @shopEntityDayServicesTitle.
  ///
  /// In ar, this message translates to:
  /// **'خدماتك حسب يوم الأسبوع'**
  String get shopEntityDayServicesTitle;

  /// No description provided for @shopEntityDayServicesHint.
  ///
  /// In ar, this message translates to:
  /// **'أي خدمة تُطلب بيوم معيّن أكثر — يساعدك تجهّز الطاقم المناسب ذاك اليوم.'**
  String get shopEntityDayServicesHint;

  /// No description provided for @shopEntityDayServicesMutedNote.
  ///
  /// In ar, this message translates to:
  /// **'تحتاج زياراتٍ موزّعة على أيام كافية لنرسمها.'**
  String get shopEntityDayServicesMutedNote;

  /// No description provided for @shopEntityDayBranchesTitle.
  ///
  /// In ar, this message translates to:
  /// **'فروعك حسب يوم الأسبوع'**
  String get shopEntityDayBranchesTitle;

  /// No description provided for @shopEntityDayBranchesHint.
  ///
  /// In ar, this message translates to:
  /// **'فروعك ما تشترك بالضرورة بنفس الإيقاع — فرع بمول يزدحم بعطلة، وفرع حيّ يزدحم بعد الدوام.'**
  String get shopEntityDayBranchesHint;

  /// No description provided for @shopEntityDayBranchesMutedNote.
  ///
  /// In ar, this message translates to:
  /// **'تحتاج فرعاً ثانياً وزياراتٍ موزّعة على أيام كافية لنرسمها.'**
  String get shopEntityDayBranchesMutedNote;

  /// No description provided for @shopBundlesTitle.
  ///
  /// In ar, this message translates to:
  /// **'باقات مقترحة'**
  String get shopBundlesTitle;

  /// No description provided for @shopBundlesMutedNote.
  ///
  /// In ar, this message translates to:
  /// **'ما فيه اقترانات كافية بعد لنقترح باقة منها.'**
  String get shopBundlesMutedNote;

  /// No description provided for @shopBundlesOpportunity.
  ///
  /// In ar, this message translates to:
  /// **'{n} فرصة'**
  String shopBundlesOpportunity(int n);

  /// No description provided for @shopAssociationsTitle.
  ///
  /// In ar, this message translates to:
  /// **'ما يُطلب معًا'**
  String get shopAssociationsTitle;

  /// No description provided for @shopAssociationsMutedNote.
  ///
  /// In ar, this message translates to:
  /// **'ما فيه اقترانات كافية بعد.'**
  String get shopAssociationsMutedNote;

  /// No description provided for @shopAssociationsLearningNote.
  ///
  /// In ar, this message translates to:
  /// **'ما نعرف بعد ما الذي يُطلب مع ماذا — التعرّف على الاقترانات يحتاج زياراتٍ أكثر ليصير الاستنتاج صحيحاً لا صدفة. ({have}/{need})'**
  String shopAssociationsLearningNote(int have, int need);

  /// No description provided for @shopCustomersCount.
  ///
  /// In ar, this message translates to:
  /// **'{n} عميلاً'**
  String shopCustomersCount(int n);

  /// No description provided for @shopDay0Short.
  ///
  /// In ar, this message translates to:
  /// **'ح'**
  String get shopDay0Short;

  /// No description provided for @shopDay1Short.
  ///
  /// In ar, this message translates to:
  /// **'ن'**
  String get shopDay1Short;

  /// No description provided for @shopDay2Short.
  ///
  /// In ar, this message translates to:
  /// **'ث'**
  String get shopDay2Short;

  /// No description provided for @shopDay3Short.
  ///
  /// In ar, this message translates to:
  /// **'ر'**
  String get shopDay3Short;

  /// No description provided for @shopDay4Short.
  ///
  /// In ar, this message translates to:
  /// **'خ'**
  String get shopDay4Short;

  /// No description provided for @shopDay5Short.
  ///
  /// In ar, this message translates to:
  /// **'ج'**
  String get shopDay5Short;

  /// No description provided for @shopDay6Short.
  ///
  /// In ar, this message translates to:
  /// **'س'**
  String get shopDay6Short;

  /// No description provided for @shopDay0Full.
  ///
  /// In ar, this message translates to:
  /// **'الأحد'**
  String get shopDay0Full;

  /// No description provided for @shopDay1Full.
  ///
  /// In ar, this message translates to:
  /// **'الإثنين'**
  String get shopDay1Full;

  /// No description provided for @shopDay2Full.
  ///
  /// In ar, this message translates to:
  /// **'الثلاثاء'**
  String get shopDay2Full;

  /// No description provided for @shopDay3Full.
  ///
  /// In ar, this message translates to:
  /// **'الأربعاء'**
  String get shopDay3Full;

  /// No description provided for @shopDay4Full.
  ///
  /// In ar, this message translates to:
  /// **'الخميس'**
  String get shopDay4Full;

  /// No description provided for @shopDay5Full.
  ///
  /// In ar, this message translates to:
  /// **'الجمعة'**
  String get shopDay5Full;

  /// No description provided for @shopDay6Full.
  ///
  /// In ar, this message translates to:
  /// **'السبت'**
  String get shopDay6Full;

  /// No description provided for @shopMissedTitle.
  ///
  /// In ar, this message translates to:
  /// **'عملاء ما جرّبوا كل اللي يناسبهم'**
  String get shopMissedTitle;

  /// No description provided for @shopMissedMutedNote.
  ///
  /// In ar, this message translates to:
  /// **'لا عملاء واضحين بعد ناقصين خدمة تُشترى عادة مع خدماتهم.'**
  String get shopMissedMutedNote;

  /// No description provided for @shopCustomerFallback.
  ///
  /// In ar, this message translates to:
  /// **'عميل'**
  String get shopCustomerFallback;

  /// No description provided for @shopKpiActiveCustomers.
  ///
  /// In ar, this message translates to:
  /// **'عملاء نشطون'**
  String get shopKpiActiveCustomers;

  /// No description provided for @shopKpiReturnCycle.
  ///
  /// In ar, this message translates to:
  /// **'دورة العودة'**
  String get shopKpiReturnCycle;

  /// No description provided for @shopDaysSuffix.
  ///
  /// In ar, this message translates to:
  /// **'{n} يومًا'**
  String shopDaysSuffix(int n);

  /// No description provided for @shopKpiChurnRate.
  ///
  /// In ar, this message translates to:
  /// **'التسرّب'**
  String get shopKpiChurnRate;

  /// No description provided for @shopTileServicesPerVisit.
  ///
  /// In ar, this message translates to:
  /// **'خدمات لكل زيارة'**
  String get shopTileServicesPerVisit;

  /// No description provided for @shopTileExpectedNextWeek.
  ///
  /// In ar, this message translates to:
  /// **'متوقّع الأسبوع الجاي'**
  String get shopTileExpectedNextWeek;

  /// No description provided for @shopTileCycleCompletion.
  ///
  /// In ar, this message translates to:
  /// **'التزام الدورة الدورية'**
  String get shopTileCycleCompletion;

  /// No description provided for @shopPerVisitMutedTitle.
  ///
  /// In ar, this message translates to:
  /// **'خدماتك لكل زيارة، والالتزام بالدورة'**
  String get shopPerVisitMutedTitle;

  /// No description provided for @shopPerVisitMutedNote.
  ///
  /// In ar, this message translates to:
  /// **'تحتاج زياراتٍ حقيقية أولاً لتُحسب.'**
  String get shopPerVisitMutedNote;

  /// No description provided for @shopLeadConversionTitle.
  ///
  /// In ar, this message translates to:
  /// **'تحوّل من تواصلوا معك أول مرة'**
  String get shopLeadConversionTitle;

  /// No description provided for @shopLeadConversionDetail.
  ///
  /// In ar, this message translates to:
  /// **'{converted} من {total} تحوّل لزيارة حقيقية'**
  String shopLeadConversionDetail(int converted, int total);
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
