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
