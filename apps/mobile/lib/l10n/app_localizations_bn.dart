// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Bengali Bangla (`bn`).
class SBn extends S {
  SBn([String locale = 'bn']) : super(locale);

  @override
  String get appName => 'Raje3';

  @override
  String get ok => 'ঠিক আছে';

  @override
  String get cancel => 'বাতিল';

  @override
  String get save => 'সংরক্ষণ করুন';

  @override
  String get close => 'বন্ধ করুন';

  @override
  String get back => 'ফিরে যান';

  @override
  String get next => 'পরবর্তী';

  @override
  String get done => 'সম্পন্ন';

  @override
  String get loading => 'লোড হচ্ছে...';

  @override
  String get retry => 'আবার চেষ্টা করুন';

  @override
  String get error => 'একটি ত্রুটি ঘটেছে';

  @override
  String get success => 'সফল হয়েছে';

  @override
  String get homeDashboardTitle => 'ড্যাশবোর্ড';

  @override
  String get homeShopSectionLabel => 'আমার দোকান';

  @override
  String get homeLoadErrorTitle => 'লোড করা যায়নি';

  @override
  String get homeLoadErrorMessage => 'আজকের তথ্য লোড করা যায়নি। আবার চেষ্টা করুন।';

  @override
  String get homeTodaySectionTitle => 'আজ';

  @override
  String get homeStatSent => 'পাঠানো হয়েছে';

  @override
  String get homeStatWaiting => 'অপেক্ষমাণ';

  @override
  String get homeStatRetrying => 'পুনরায় চেষ্টা';

  @override
  String get homeDashboardComputing => 'আপনার দোকানের পরিসংখ্যান গণনা হচ্ছে — কিছুক্ষণ পর রিফ্রেশ করুন।';

  @override
  String get homeDashboardSectionTitle => 'দোকানের পরিসংখ্যান';

  @override
  String get homeDashboardEmpty => 'এখনও পর্যাপ্ত তথ্য নেই।';

  @override
  String get moreSectionsTitle => 'আরও';

  @override
  String get themeDarkMode => 'ডার্ক মোড';

  @override
  String get themeLightMode => 'লাইট মোড';

  @override
  String get search => 'অনুসন্ধান';

  @override
  String get login => 'লগ ইন';

  @override
  String get logout => 'লগ আউট';

  @override
  String get validatorFieldRequiredGeneric => 'এই ঘরটি আবশ্যক';

  @override
  String validatorFieldRequiredNamed(String field) => '$field আবশ্যক';

  @override
  String get validatorEmailRequired => 'ইমেইল আবশ্যক';

  @override
  String get validatorEmailInvalid => 'ইমেইল ঠিকানা সঠিক নয়';

  @override
  String get validatorPhoneRequired => 'ফোন নম্বর আবশ্যক';

  @override
  String get validatorPhoneInvalid => 'ফোন নম্বরটি সঠিক নয় — এটি অবশ্যই 05 দিয়ে শুরু হতে হবে';

  @override
  String get validatorPasswordRequired => 'পাসওয়ার্ড আবশ্যক';

  @override
  String get validatorPasswordTooShort => 'পাসওয়ার্ড অবশ্যই কমপক্ষে ৮টি অক্ষরের হতে হবে';

  @override
  String get validatorPasswordNeedsUppercase => 'পাসওয়ার্ডে একটি বড় হাতের অক্ষর থাকতে হবে';

  @override
  String get validatorPasswordNeedsLowercase => 'পাসওয়ার্ডে একটি ছোট হাতের অক্ষর থাকতে হবে';

  @override
  String get validatorPasswordNeedsDigit => 'পাসওয়ার্ডে একটি সংখ্যা থাকতে হবে';

  @override
  String get validatorConfirmPasswordFieldName => 'পাসওয়ার্ড নিশ্চিত করুন';

  @override
  String get validatorPasswordMismatch => 'পাসওয়ার্ড মিলছে না';

  @override
  String get validatorOtpRequired => 'যাচাইকরণ কোড আবশ্যক';

  @override
  String get validatorOtpLength => 'যাচাইকরণ কোড অবশ্যই ৬ সংখ্যার হতে হবে';

  @override
  String get validatorOtpDigitsOnly => 'যাচাইকরণ কোডে শুধুমাত্র সংখ্যা থাকতে হবে';

  @override
  String get validatorNameRequired => 'নাম আবশ্যক';

  @override
  String get validatorNameTooShort => 'নাম অবশ্যই কমপক্ষে ২টি অক্ষরের হতে হবে';

  @override
  String get validatorNameTooLong => 'নাম ১০০টি অক্ষরের বেশি হতে পারবে না';

  @override
  String get validatorNameInvalidChars => 'নামে অননুমোদিত অক্ষর রয়েছে';

  @override
  String get validatorGenericFieldName => 'এই ঘর';

  @override
  String validatorMinLengthNamed(String field, int minLength) => '$field অবশ্যই কমপক্ষে $minLength টি অক্ষরের হতে হবে';

  @override
  String validatorMaxLengthNamed(String field, int maxLength) => '$field $maxLength টি অক্ষরের বেশি হতে পারবে না';

  @override
  String get validatorGenericValueName => 'মান';

  @override
  String validatorNotANumberNamed(String field) => '$field একটি সংখ্যা হতে হবে';

  @override
  String validatorMinValueNamed(String field, String min) => '$field অবশ্যই কমপক্ষে $min হতে হবে';

  @override
  String validatorMaxValueNamed(String field, String max) => '$field $max এর বেশি হতে পারবে না';

  @override
  String get validatorUrlRequired => 'লিঙ্ক আবশ্যক';

  @override
  String get validatorUrlInvalid => 'লিঙ্কটি সঠিক নয়';

  @override
  String get urlHelperUnavailable => 'লিঙ্কটি উপলব্ধ নেই';

  @override
  String get urlHelperOpenFailed => 'লিঙ্কটি খোলা যায়নি';

  @override
  String get routerScreenNotOnMobileYet => 'এই স্ক্রিনটি এখনও মোবাইল অ্যাপে উপলব্ধ নেই।';

  @override
  String get authLoginSubtitle => 'চালিয়ে যেতে সাইন ইন করুন';

  @override
  String get authPhoneLabel => 'মোবাইল নম্বর';

  @override
  String get authPasswordLabel => 'পাসওয়ার্ড';

  @override
  String get authNoShopYetLabel => 'এখনো দোকান নেই?';

  @override
  String get authOpenNewShopCta => 'একটি নতুন দোকান খুলুন';

  @override
  String get authOpenShopTitle => 'নতুন দোকান খোলা';

  @override
  String get authSignupSubtitle => 'আপনার দোকান খুলতে মাত্র তিনটি ধাপ';

  @override
  String get authShopNameLabel => 'দোকানের নাম';

  @override
  String get authAlreadyHaveShopCta => 'ইতিমধ্যে দোকান আছে? লগ ইন করুন';

  @override
  String get authOpenShopCta => 'দোকান খুলুন';

  @override
  String get authVerifyPhoneTitle => 'মোবাইল নম্বর যাচাই করুন';

  @override
  String authVerifyCodeSentTo(String phone) => 'আমরা $phone নম্বরে একটি যাচাইকরণ কোড পাঠিয়েছি';

  @override
  String get authVerifying => 'যাচাই করা হচ্ছে...';

  @override
  String get authConfirmCta => 'নিশ্চিত করুন';

  @override
  String get authResendCodeCta => 'আবার কোড পাঠান';

  @override
  String get authSendCodeCta => 'কোড পাঠান';

  @override
  String get authCodeSendFailedFallback => 'কোডটি পাঠানো যায়নি।';

  @override
  String get authOtpIncorrectFallback => 'যাচাইকরণ কোডটি সঠিক নয়।';

  @override
  String get visitCatalogueLoadErrorFallback => 'পরিষেবাগুলো লোড করা যায়নি। আবার চেষ্টা করতে নিচে টানুন।';

  @override
  String get visitEnterCustomerPhone => 'গ্রাহকের মোবাইল নম্বর লিখুন';

  @override
  String get visitSelectAtLeastOneService => 'অন্তত একটি পরিষেবা নির্বাচন করুন';

  @override
  String get visitSavedMessage => 'ভিজিট রেকর্ড করা হয়েছে।';

  @override
  String get visitSaveErrorFallback => 'ভিজিট রেকর্ড করা যায়নি।';

  @override
  String get visitSaveErrorNetworkFallback => 'ভিজিট রেকর্ড করা যায়নি। আপনার সংযোগ পরীক্ষা করে আবার চেষ্টা করুন।';

  @override
  String get visitTitle => 'ভিজিট রেকর্ড করুন';

  @override
  String get visitCustomerSectionTitle => 'গ্রাহক';

  @override
  String get visitCustomerPhoneFieldLabel => 'গ্রাহকের মোবাইল নম্বর';

  @override
  String visitKnownCustomer(String name) => 'পরিচিত গ্রাহক: $name';

  @override
  String get visitNewCustomer => 'নতুন গ্রাহক';

  @override
  String get visitServicesSectionTitle => 'পরিষেবাসমূহ';

  @override
  String get visitNoServicesYet => 'এখনো কোনো পরিষেবা নেই।';

  @override
  String get visitNoteSectionTitle => 'নোট (ঐচ্ছিক)';

  @override
  String get visitSaveButtonLabel => 'ভিজিট সংরক্ষণ করুন';
}
