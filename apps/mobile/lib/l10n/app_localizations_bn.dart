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
  String get search => 'অনুসন্ধান';

  @override
  String get login => 'লগ ইন';

  @override
  String get logout => 'লগ আউট';

  @override
  String get homeDashboardTitle => 'ড্যাশবোর্ড';

  @override
  String get homeShopSectionLabel => 'আমার দোকান';

  @override
  String get homeLoadErrorTitle => 'লোড করা যায়নি';

  @override
  String get homeLoadErrorMessage =>
      'আজকের তথ্য লোড করা যায়নি। আবার চেষ্টা করুন।';

  @override
  String get homeTodaySectionTitle => 'আজ';

  @override
  String get homeStatSent => 'পাঠানো হয়েছে';

  @override
  String get homeStatWaiting => 'অপেক্ষমাণ';

  @override
  String get homeStatRetrying => 'পুনরায় চেষ্টা';

  @override
  String get homeDashboardComputing =>
      'আপনার দোকানের পরিসংখ্যান গণনা হচ্ছে — কিছুক্ষণ পর রিফ্রেশ করুন।';

  @override
  String get homeDashboardSectionTitle => 'দোকানের পরিসংখ্যান';

  @override
  String get homeDashboardEmpty => 'এখনও পর্যাপ্ত তথ্য নেই।';

  @override
  String get themeDarkMode => 'ডার্ক মোড';

  @override
  String get themeLightMode => 'লাইট মোড';

  @override
  String get validatorFieldRequiredGeneric => 'এই ঘরটি আবশ্যক';

  @override
  String validatorFieldRequiredNamed(String field) {
    return '$field আবশ্যক';
  }

  @override
  String get validatorEmailRequired => 'ইমেইল আবশ্যক';

  @override
  String get validatorEmailInvalid => 'ইমেইল ঠিকানা সঠিক নয়';

  @override
  String get validatorPhoneRequired => 'ফোন নম্বর আবশ্যক';

  @override
  String get validatorPhoneInvalid =>
      'ফোন নম্বরটি সঠিক নয় — এটি অবশ্যই 05 দিয়ে শুরু হতে হবে';

  @override
  String get validatorPasswordRequired => 'পাসওয়ার্ড আবশ্যক';

  @override
  String get validatorPasswordTooShort =>
      'পাসওয়ার্ড অবশ্যই কমপক্ষে ৮টি অক্ষরের হতে হবে';

  @override
  String get validatorPasswordNeedsUppercase =>
      'পাসওয়ার্ডে একটি বড় হাতের অক্ষর থাকতে হবে';

  @override
  String get validatorPasswordNeedsLowercase =>
      'পাসওয়ার্ডে একটি ছোট হাতের অক্ষর থাকতে হবে';

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
  String get validatorOtpDigitsOnly =>
      'যাচাইকরণ কোডে শুধুমাত্র সংখ্যা থাকতে হবে';

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
  String validatorMinLengthNamed(String field, int minLength) {
    return '$field অবশ্যই কমপক্ষে $minLength টি অক্ষরের হতে হবে';
  }

  @override
  String validatorMaxLengthNamed(String field, int maxLength) {
    return '$field $maxLength টি অক্ষরের বেশি হতে পারবে না';
  }

  @override
  String get validatorGenericValueName => 'মান';

  @override
  String validatorNotANumberNamed(String field) {
    return '$field একটি সংখ্যা হতে হবে';
  }

  @override
  String validatorMinValueNamed(String field, String min) {
    return '$field অবশ্যই কমপক্ষে $min হতে হবে';
  }

  @override
  String validatorMaxValueNamed(String field, String max) {
    return '$field $max এর বেশি হতে পারবে না';
  }

  @override
  String get validatorUrlRequired => 'লিঙ্ক আবশ্যক';

  @override
  String get validatorUrlInvalid => 'লিঙ্কটি সঠিক নয়';

  @override
  String get urlHelperUnavailable => 'লিঙ্কটি উপলব্ধ নেই';

  @override
  String get urlHelperOpenFailed => 'লিঙ্কটি খোলা যায়নি';

  @override
  String get routerScreenNotOnMobileYet =>
      'এই স্ক্রিনটি এখনও মোবাইল অ্যাপে উপলব্ধ নেই।';

  @override
  String get kbHintNoEntry => 'এখনও এর জন্য কোনো ব্যাখ্যা নেই।';

  @override
  String get assistantChatTitle => 'সহায়ক';

  @override
  String get assistantInputHint => 'আপনার প্রশ্ন লিখুন...';

  @override
  String get assistantSend => 'পাঠান';

  @override
  String get assistantUnavailable => 'সহায়ক এখন উপলব্ধ নেই।';

  @override
  String get assistantPreparing => 'সহায়ক প্রস্তুত হচ্ছে...';

  @override
  String get assistantSpeak => 'উত্তর শুনুন';

  @override
  String get assistantStopSpeaking => 'থামান';

  @override
  String get assistantActionUnavailable => 'আপনি এখন এটি করতে পারবেন না।';

  @override
  String get assistantConfirm => 'নিশ্চিত করুন';

  @override
  String get assistantCancel => 'বাতিল';

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
  String get authOwnerNameLabel => 'আপনার নাম (ঐচ্ছিক)';

  @override
  String get authAlreadyHaveShopCta => 'ইতিমধ্যে দোকান আছে? লগ ইন করুন';

  @override
  String get authOpenShopCta => 'দোকান খুলুন';

  @override
  String get authVerifyPhoneTitle => 'মোবাইল নম্বর যাচাই করুন';

  @override
  String authVerifyCodeSentTo(String phone) {
    return 'আমরা $phone নম্বরে একটি যাচাইকরণ কোড পাঠিয়েছি';
  }

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
  String get visitCatalogueLoadErrorFallback =>
      'পরিষেবাগুলো লোড করা যায়নি। আবার চেষ্টা করতে নিচে টানুন।';

  @override
  String get visitEnterCustomerPhone => 'গ্রাহকের মোবাইল নম্বর লিখুন';

  @override
  String get visitSelectAtLeastOneService => 'অন্তত একটি পরিষেবা নির্বাচন করুন';

  @override
  String get visitSavedMessage => 'ভিজিট রেকর্ড করা হয়েছে।';

  @override
  String get visitSaveErrorFallback => 'ভিজিট রেকর্ড করা যায়নি।';

  @override
  String get visitSaveErrorNetworkFallback =>
      'ভিজিট রেকর্ড করা যায়নি। আপনার সংযোগ পরীক্ষা করে আবার চেষ্টা করুন।';

  @override
  String get visitTitle => 'ভিজিট রেকর্ড করুন';

  @override
  String get visitCustomerSectionTitle => 'গ্রাহক';

  @override
  String get visitCustomerPhoneFieldLabel => 'গ্রাহকের মোবাইল নম্বর';

  @override
  String get visitPlateFieldLabel => 'গাড়ির নম্বর প্লেট';

  @override
  String get visitPlateRequired =>
      'একটি বৈধ প্লেট লিখুন (অন্তত একটি অক্ষর ও একটি সংখ্যা)';

  @override
  String visitKnownVehicle(String name) {
    return 'পরিচিত গাড়ি: $name';
  }

  @override
  String get visitNewVehicle => 'নতুন গাড়ি';

  @override
  String visitKnownCustomer(String name) {
    return 'পরিচিত গ্রাহক: $name';
  }

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

  @override
  String get navAppsLabel => 'আমার অ্যাপ';

  @override
  String get navHomeLabel => 'হোম';

  @override
  String get navAccountLabel => 'আমার অ্যাকাউন্ট';

  @override
  String get homeGreetingMorning => 'শুভ সকাল';

  @override
  String get homeGreetingEvening => 'শুভ সন্ধ্যা';

  @override
  String homeGreetingMorningNamed(String name) {
    return 'শুভ সকাল, $name';
  }

  @override
  String homeGreetingEveningNamed(String name) {
    return 'শুভ সন্ধ্যা, $name';
  }

  @override
  String get homeAppsSectionTitle => 'আপনার অ্যাপ';

  @override
  String get homeFeaturedStartNow => 'এখনই শুরু করুন';

  @override
  String get homeEmptyStateTitle => 'এখনো কোনো অ্যাপ নেই';

  @override
  String get homeEmptyStateBody =>
      'আপনার অনুমতি যোগ করতে দোকানের মালিকের সাথে যোগাযোগ করুন।';

  @override
  String get appsScreenTitle => 'আমার অ্যাপ';

  @override
  String get appsScreenHint =>
      'নিচের বারের ৫ম স্থানে অ্যাপ পিন করতে পিন আইকনে চাপুন';

  @override
  String get appsPinnedBadge => 'বারে পিন করা আছে';

  @override
  String get appsPinAction => 'এখানে পিন করুন';

  @override
  String get homeLauncherEmptyTitle => 'কোনো অ্যাপ পাওয়া যায়নি';

  @override
  String get homeLauncherEmptyMessage =>
      'আপনার দোকানের জন্য একটি অ্যাপ চালু করতে সহায়তার সাথে যোগাযোগ করুন';

  @override
  String get accountScreenTitle => 'আমার অ্যাকাউন্ট';

  @override
  String get accountPhoneLabel => 'মোবাইল নম্বর';

  @override
  String get accountLogoutAction => 'লগ আউট';

  @override
  String get accountLogoutConfirmTitle => 'লগ আউট';

  @override
  String get accountLogoutConfirmMessage =>
      'আপনি কি আপনার অ্যাকাউন্ট থেকে লগ আউট করতে চান?';

  @override
  String get notificationsUnavailable => 'বিজ্ঞপ্তি এখনো উপলব্ধ নয়';

  @override
  String get notificationsTitle => 'বিজ্ঞপ্তি';

  @override
  String get notificationsEmptyState => 'এখনো কোনো বিজ্ঞপ্তি নেই';

  @override
  String get notificationsAgoJustNow => 'এখনই';

  @override
  String notificationsAgoMinutes(int n) {
    return '$n মিনিট আগে';
  }

  @override
  String notificationsAgoHours(int n) {
    return '$n ঘণ্টা আগে';
  }

  @override
  String get notificationsAgoYesterday => 'গতকাল';

  @override
  String notificationsAgoDays(int n) {
    return '$n দিন আগে';
  }

  @override
  String get accountPageTitle => 'আমার অ্যাকাউন্ট';

  @override
  String get accountLegalSectionTitle => 'আইনি';

  @override
  String get accountTermsRow => 'শর্তাবলী';

  @override
  String get accountPrivacyRow => 'গোপনীয়তা নীতি';

  @override
  String get accountSignOutRow => 'সাইন আউট';

  @override
  String get accountSignOutConfirmTitle => 'সাইন আউট করবেন?';

  @override
  String get accountSignOutConfirmBody =>
      'চালিয়ে যেতে আপনাকে আবার সাইন ইন করতে হবে।';

  @override
  String get accountSignOutCancel => 'বাতিল';

  @override
  String get accountSignOutConfirm => 'সাইন আউট';

  @override
  String get accountNameFieldHint => 'আপনার নাম';

  @override
  String get accountSaveNameFailed =>
      'নাম সংরক্ষণ করা যায়নি, আবার চেষ্টা করুন।';

  @override
  String get accountShopSectionTitle => 'আমার দোকান';

  @override
  String get accountShopIdentityRow => 'আমার দোকান';

  @override
  String get shopIdentityPageTitle => 'আমার দোকান';

  @override
  String get shopIdentityVehicleTitle => 'গাড়ির কাজ';

  @override
  String get shopIdentityVehicleDesc =>
      'এই দোকানের জন্য ভিজিট স্ক্রিনে লাইসেন্স প্লেট ফিল্ড চালু করে।';

  @override
  String get shopIdentityVehicleSaveFailed =>
      'সংরক্ষণ করা যায়নি, আবার চেষ্টা করুন।';

  @override
  String get shopIdentityBrandTitle => 'আপনার দোকানের নাম ও লোগো';

  @override
  String get shopIdentityCustomerPagePreview => 'এটি আপনার গ্রাহক দেখেন';

  @override
  String get shopIdentityNameLabel => 'দোকানের নাম';

  @override
  String get shopIdentityUploadLogo => 'লোগো আপলোড করুন';

  @override
  String get shopIdentityChangeLogo => 'লোগো পরিবর্তন করুন';

  @override
  String get shopIdentityRemoveLogo => 'মুছুন';

  @override
  String get shopIdentityColorLabel => 'আপনার দোকানের রঙ';

  @override
  String get shopIdentityResetColor => 'ডিফল্ট ব্যবহার করুন';

  @override
  String get shopIdentitySave => 'সংরক্ষণ করুন';

  @override
  String get shopIdentityDefaultName => 'আপনার দোকান';

  @override
  String get shopIdentityLogoPickFailed =>
      'ছবিটি পড়া যায়নি, অন্য ছবি চেষ্টা করুন।';

  @override
  String get shopIdentityInvalidColor => 'একটি সঠিক রঙ লিখুন, যেমন #B08A3E';

  @override
  String get shopIdentitySaveFailed => 'সংরক্ষণ করা যায়নি, আবার চেষ্টা করুন।';

  @override
  String get shopIdentitySaved => 'সংরক্ষিত হয়েছে।';

  @override
  String get shopIdentityBranchesRow => 'শাখাসমূহ';

  @override
  String get branchesPageTitle => 'শাখাসমূহ';

  @override
  String get branchesAddBranch => 'শাখা যোগ করুন';

  @override
  String get branchesActiveChip => 'সক্রিয়';

  @override
  String get branchesClosedChip => 'বন্ধ';

  @override
  String get branchesLoadFailed =>
      'শাখা লোড করা যায়নি, আবার চেষ্টা করতে নিচে টানুন।';

  @override
  String get branchesLimitReached =>
      'আপনার বর্তমান প্ল্যানে আরেকটি শাখা যোগ করা যাবে না।';

  @override
  String get branchesNameRequired => 'শাখার নাম আবশ্যক';

  @override
  String get branchesNameLabel => 'শাখার নাম';

  @override
  String get branchesCityLabel => 'শহর';

  @override
  String get branchesLocationHint =>
      'গুগল ম্যাপ থেকে অবস্থানের লিংক পেস্ট করুন (প্রথম শাখায় ঐচ্ছিক, দ্বিতীয় থেকে বাধ্যতামূলক)';

  @override
  String get branchesMapsLinkLabel => 'গুগল ম্যাপ লিংক';

  @override
  String get branchesMapsLinkInvalid =>
      'লিংকটি পড়া যায়নি — নিশ্চিত করুন এটি গুগল ম্যাপের লিংক।';

  @override
  String get branchesMapsLinkShort =>
      'সংক্ষিপ্ত লিংক নয়, গুগল ম্যাপের সম্পূর্ণ লিংক পেস্ট করুন।';

  @override
  String get branchesLocationRequired =>
      'মানচিত্রে শাখার অবস্থান নির্ধারণ করুন — দ্বিতীয় শাখা থেকে আবশ্যক।';

  @override
  String get branchesSaveFailed => 'সংরক্ষণ করা যায়নি, আবার চেষ্টা করুন।';

  @override
  String get branchesStatusLabel => 'শাখার অবস্থা';

  @override
  String get branchesMainCannotClose =>
      'প্রধান শাখা বন্ধ করা যাবে না — শুধু নাম পরিবর্তন করা যাবে।';

  @override
  String get branchesWhatsappTitle => 'হোয়াটসঅ্যাপ সংযোগ';

  @override
  String get branchesWhatsappNotStarted => 'এখনও সংযুক্ত হয়নি';

  @override
  String get branchesWhatsappConnected => 'সংযুক্ত এবং কাজ করছে';

  @override
  String get branchesWhatsappCannotSend => 'সংযুক্ত কিন্তু পাঠাতে সমস্যা আছে';

  @override
  String get branchesTeamTitle => 'শাখার দল';

  @override
  String get branchesTeamEmpty => 'এই শাখায় এখনও কোনো সদস্য নেই।';

  @override
  String get branchesAddMember => 'সদস্য যোগ করুন';

  @override
  String get branchesMemberNameLabel => 'কর্মচারীর নাম';

  @override
  String get branchesMemberPhoneLabel => 'তার ফোন নম্বর';

  @override
  String get branchesMemberPasswordLabel => 'তার লগইন পাসওয়ার্ড';

  @override
  String get branchesMemberRoleLabel => 'ভূমিকা';

  @override
  String get branchesRoleOperator => 'মাঠকর্মী';

  @override
  String get branchesRoleSupervisor => 'শিফট সুপারভাইজার';

  @override
  String get branchesRoleManager => 'ম্যানেজার';

  @override
  String get branchesSeatLimit =>
      'আপনার বর্তমান প্ল্যানে আরেকজন কর্মচারী যোগ করা যাবে না।';

  @override
  String get branchesHireFailed => 'কর্মচারী যোগ করা যায়নি, আবার চেষ্টা করুন।';

  @override
  String get accountSecuritySectionTitle => 'নিরাপত্তা';

  @override
  String get accountChangePasswordRow => 'পাসওয়ার্ড পরিবর্তন করুন';

  @override
  String get accountChangePasswordFailed =>
      'পাসওয়ার্ড পরিবর্তন করা যায়নি, আবার চেষ্টা করুন।';

  @override
  String get accountChangePasswordSuccess => 'পাসওয়ার্ড পরিবর্তিত হয়েছে।';

  @override
  String get accountCurrentPasswordLabel => 'বর্তমান পাসওয়ার্ড';

  @override
  String get accountNewPasswordLabel => 'নতুন পাসওয়ার্ড';

  @override
  String get accountConfirmNewPasswordLabel => 'নতুন পাসওয়ার্ড নিশ্চিত করুন';

  @override
  String get branchesIncreaseCapacity => 'ক্ষমতা বাড়ান';

  @override
  String get accountBillingSectionTitle => 'বিলিং';

  @override
  String get accountBillingRow => 'সাবস্ক্রিপশন ও ইনভয়েস';

  @override
  String get billingPageTitle => 'বিলিং';

  @override
  String get billingLoadFailed =>
      'বিলিং তথ্য লোড করা যায়নি। আবার চেষ্টা করতে নিচে টানুন।';

  @override
  String get billingAllGood =>
      'আপনার বিলিং ঠিক আছে, এখন কিছুতে মনোযোগ দিতে হবে না।';

  @override
  String get billingPastDue =>
      'আপনার একটি বকেয়া ইনভয়েস আছে — সেবা বন্ধ হওয়া এড়াতে পরিশোধ করুন।';

  @override
  String get billingUsageSectionTitle => 'আপনার ব্যবহার';

  @override
  String get billingUsageStaffSeats => 'স্টাফ আসন';

  @override
  String get billingUsageBranches => 'শাখা';

  @override
  String get billingUsageUnlimited => 'সীমাহীন';

  @override
  String get billingMyAppsSectionTitle => 'আমার সাবস্ক্রাইব করা অ্যাপ';

  @override
  String get billingStatusActive => 'সক্রিয়';

  @override
  String get billingStatusStopping => 'বন্ধ হচ্ছে';

  @override
  String billingRenewsOn(Object date) {
    return '$date তারিখে নবায়ন হবে';
  }

  @override
  String get billingStopRenewal => 'নবায়ন বন্ধ করুন';

  @override
  String get billingUndoStopRenewal => 'বন্ধ বাতিল করুন';

  @override
  String get billingRenewNow => 'এখনই নবায়ন করুন';

  @override
  String get billingActionFailed =>
      'এই কাজটি সম্পন্ন করা যায়নি। আবার চেষ্টা করুন।';

  @override
  String get billingRenewalPreviewSectionTitle => 'পরবর্তী নবায়নের পূর্বরূপ';

  @override
  String billingRenewalPreviewNextChargeOn(Object date) {
    return 'পরবর্তী চার্জ $date তারিখে';
  }

  @override
  String get billingRenewalPreviewNoDate => 'এখনো কোনো আসন্ন নবায়ন তারিখ নেই।';

  @override
  String get billingRenewalPreviewSubtotal => 'সাবটোটাল';

  @override
  String get billingRenewalPreviewSavings => 'সঞ্চয়';

  @override
  String get billingRenewalPreviewTax => 'কর';

  @override
  String get billingRenewalPreviewTotal => 'মোট';

  @override
  String get billingInvoicesSectionTitle => 'ইনভয়েস';

  @override
  String get billingInvoicesEmpty => 'এখনো কোনো ইনভয়েস নেই।';

  @override
  String get billingInvoiceStatusPaid => 'পরিশোধিত';

  @override
  String get billingInvoiceStatusOpen => 'অপরিশোধিত';

  @override
  String get billingInvoiceStatusPartiallyPaid => 'আংশিক পরিশোধিত';

  @override
  String get billingInvoiceStatusVoid => 'বাতিল';

  @override
  String get billingInvoiceStatusUncollectible => 'আদায়যোগ্য নয়';

  @override
  String get billingInvoiceStatusDraft => 'খসড়া';

  @override
  String get billingPayNow => 'এখনই পরিশোধ করুন';

  @override
  String get billingPayLinkFailed =>
      'পেমেন্ট লিঙ্ক তৈরি করা যায়নি। আবার চেষ্টা করুন।';

  @override
  String get billingCancelConfirmTitle => 'নবায়ন বন্ধ করবেন?';

  @override
  String get billingCancelConfirmBody =>
      'চলতি মেয়াদ শেষ পর্যন্ত সেবা চালু থাকবে, এরপর তা আর নবায়ন হবে না।';

  @override
  String get billingCancelConfirmAction => 'নবায়ন বন্ধ করুন';

  @override
  String get visitOfferApplyLabel => 'এই ভিজিটে এই অফারটি প্রয়োগ করুন';

  @override
  String visitPointsRedeemCost(Object cost) {
    return '$cost পয়েন্ট';
  }

  @override
  String visitPointsRedeemedMessage(Object name) {
    return '$name রিডিম হয়েছে ✓';
  }

  @override
  String get visitPointsRedeemFailed => 'রিডিম করা যায়নি। আবার চেষ্টা করুন।';

  @override
  String readBillingActiveCount(Object count) {
    return 'আপনার $countটি সক্রিয় সাবস্ক্রিপশন আছে।';
  }

  @override
  String get readBillingNone => 'এখন আপনার কোনো সক্রিয় সাবস্ক্রিপশন নেই।';

  @override
  String readBillingRenewsSoon(Object date) {
    return 'পরবর্তী নবায়ন $date তারিখে।';
  }

  @override
  String get readBillingFailed =>
      'এখন বিলিং স্ট্যাটাস আনা যায়নি, আবার চেষ্টা করুন।';

  @override
  String readBranchCount(Object count) {
    return 'আপনার $countটি শাখা আছে।';
  }

  @override
  String get readBranchFailed =>
      'এখন শাখার সংখ্যা আনা যায়নি, আবার চেষ্টা করুন।';

  @override
  String get readVehicleTrackingOn => 'গাড়ি ট্র্যাকিং এখন চালু আছে।';

  @override
  String get readVehicleTrackingOff => 'গাড়ি ট্র্যাকিং এখন বন্ধ আছে।';

  @override
  String get readVehicleTrackingFailed =>
      'এখন গাড়ি ট্র্যাকিং স্ট্যাটাস যাচাই করা যায়নি, আবার চেষ্টা করুন।';

  @override
  String get writeVehicleTrackingEnabledConfirm =>
      'এই দোকানের ভিজিট-রেজিস্ট্রেশন স্ক্রিনে প্লেট নম্বর ফিল্ড চালু করবে। নিশ্চিত করবেন?';

  @override
  String get writeVehicleTrackingDisabledConfirm =>
      'এই দোকানের ভিজিট-রেজিস্ট্রেশন স্ক্রিনে প্লেট নম্বর ফিল্ড বন্ধ করবে। নিশ্চিত করবেন?';

  @override
  String get writeVehicleTrackingEnabledDone =>
      'গাড়ি ট্র্যাকিং চালু করা হয়েছে ✓';

  @override
  String get writeVehicleTrackingDisabledDone =>
      'গাড়ি ট্র্যাকিং বন্ধ করা হয়েছে ✓';

  @override
  String get writeVehicleTrackingFailed =>
      'গাড়ি ট্র্যাকিং সেটিং পরিবর্তন করা যায়নি, আবার চেষ্টা করুন।';
}
