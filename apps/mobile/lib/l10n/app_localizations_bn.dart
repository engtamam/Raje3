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
  String get assistantReplySettingsTooltip => 'উত্তরের সেটিংস';

  @override
  String get assistantReplyModeTitle => 'সহায়ক যেভাবে উত্তর দেয়';

  @override
  String get assistantReplyModeSubtitle =>
      'কণ্ঠে জিজ্ঞাসা করলেও প্রতিটি উত্তরে প্রযোজ্য';

  @override
  String get assistantReplyModeVoice => 'কণ্ঠস্বর';

  @override
  String get assistantReplyModeText => 'লিখিত টেক্সট';

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
  String get branchesRoleMarketer => 'মার্কেটিং লিড';

  @override
  String get branchesRoleManager => 'ম্যানেজার';

  @override
  String get branchesSeatLimit =>
      'আপনার বর্তমান প্ল্যানে আরেকজন কর্মচারী যোগ করা যাবে না।';

  @override
  String get branchesHireFailed => 'কর্মচারী যোগ করা যায়নি, আবার চেষ্টা করুন।';

  @override
  String get branchesVisibleAllHint => 'সব শাখা দেখে';

  @override
  String branchesVisibleSomeHint(int count) {
    return '$count শাখা দেখে';
  }

  @override
  String get branchesEditMember => 'কর্মচারী সম্পাদনা';

  @override
  String get branchesMemberStopped => 'বন্ধ';

  @override
  String get branchesMemberStationLabel => 'কোন শাখায় কাজ করে';

  @override
  String get branchesMemberVisibilityLabel => 'কোন শাখাগুলো দেখতে পারবে';

  @override
  String get branchesVisibilityOwnOnly => 'শুধু তার নিজের শাখা';

  @override
  String get branchesVisibilitySome => 'নির্দিষ্ট শাখা';

  @override
  String get branchesVisibilityAll => 'সব শাখা';

  @override
  String get branchesWorkingHours => 'কাজের সময়';

  @override
  String get branchesStopMember => 'কর্মচারী বন্ধ করুন';

  @override
  String get branchesStopMemberTitle => 'এই কর্মচারীকে বন্ধ করবেন?';

  @override
  String branchesStopMemberBody(String name) {
    return '$name সাথে সাথে অ্যাপে প্রবেশাধিকার হারাবে। তার ভিজিট ইতিহাস সংরক্ষিত থাকবে।';
  }

  @override
  String get branchesStopMemberConfirm => 'বন্ধ করুন';

  @override
  String get branchesReactivateMember => 'পুনরায় সক্রিয় করুন';

  @override
  String get branchesRehireRequired =>
      'এই কর্মচারী সম্পূর্ণ বন্ধ — পুনরায় সক্রিয় করতে আবার নিয়োগ দিতে হবে, শুধু টগল যথেষ্ট নয়।';

  @override
  String get branchesHoursSaved => 'কাজের সময় সংরক্ষিত হয়েছে।';

  @override
  String get branchesHoursExceedsShop =>
      'এই সময়গুলো দোকানের নিজস্ব সময়ের চেয়ে বেশি — ঠিক করুন।';

  @override
  String get branchesHoursHint =>
      'কিছু না বদলালে, তিনি দোকানের নিজস্ব সময় অনুসরণ করবেন স্বয়ংক্রিয়ভাবে।';

  @override
  String get branchesHoursClear => 'দোকানের ডিফল্ট সময়ে ফিরিয়ে দিন';

  @override
  String get branchesDayMonday => 'সোমবার';

  @override
  String get branchesDayTuesday => 'মঙ্গলবার';

  @override
  String get branchesDayWednesday => 'বুধবার';

  @override
  String get branchesDayThursday => 'বৃহস্পতিবার';

  @override
  String get branchesDayFriday => 'শুক্রবার';

  @override
  String get branchesDaySaturday => 'শনিবার';

  @override
  String get branchesDaySunday => 'রবিবার';

  @override
  String get branchesDayClosed => 'বন্ধ';

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
  String get billingPaymentConfirming =>
      'আমরা আপনার পেমেন্টের চেষ্টা পেয়েছি এবং এখন যাচাই করছি — এতে ২০ মিনিট পর্যন্ত সময় লাগতে পারে।';

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
  String get paymentPageLoadFailed =>
      'পেমেন্ট পেজ লোড করা যায়নি। আপনার সংযোগ পরীক্ষা করে আবার চেষ্টা করুন।';

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

  @override
  String get mobileRequestsTitle => 'মোবাইল অনুরোধ';

  @override
  String get mobileRequestsSubtitle =>
      'সেবা যা গ্রাহকের কাছে পৌঁছায়, গ্রহণ থেকে সম্পন্ন হওয়া পর্যন্ত।';

  @override
  String get mobileRequestsKpiPending => 'সিদ্ধান্তের অপেক্ষায়';

  @override
  String get mobileRequestsKpiNeedsDecision => 'সিদ্ধান্ত প্রয়োজন';

  @override
  String get mobileRequestsKpiCompletedMonth => 'এই মাসে সম্পন্ন';

  @override
  String get mobileRequestsBannerGo => 'দেখুন';

  @override
  String get mobileRequestsFilterAll => 'সব';

  @override
  String get mobileRequestsFilterPending => 'মুলতুবি';

  @override
  String get mobileRequestsFilterAccepted => 'গৃহীত';

  @override
  String get mobileRequestsFilterNeedsDecision => 'সিদ্ধান্ত প্রয়োজন';

  @override
  String get mobileRequestsFilterCompleted => 'সম্পন্ন';

  @override
  String get mobileRequestsFilterClosed => 'বন্ধ';

  @override
  String get mobileRequestsSearchHint => 'নাম বা ফোন দিয়ে খুঁজুন';

  @override
  String get mobileRequestsLoadFailedTitle => 'অনুরোধ লোড করা যায়নি';

  @override
  String get mobileRequestsLoadFailedBody =>
      'আপনার সংযোগ পরীক্ষা করে আবার চেষ্টা করুন।';

  @override
  String get mobileRequestsRetry => 'আবার চেষ্টা করুন';

  @override
  String get mobileRequestsEmptyTitle => 'এখনো কোনো অনুরোধ নেই';

  @override
  String get mobileRequestsEmptyBody =>
      'আপনার গ্রাহকদের মোবাইল সার্ভিস অনুরোধ এখানে দেখা যাবে।';

  @override
  String get mobileRequestsStatusPending => 'মুলতুবি';

  @override
  String get mobileRequestsStatusAccepted => 'গৃহীত';

  @override
  String get mobileRequestsStatusNeedsDecision => 'সিদ্ধান্ত প্রয়োজন';

  @override
  String get mobileRequestsStatusCompleted => 'সম্পন্ন';

  @override
  String get mobileRequestsStatusNoShow => 'উপস্থিত হয়নি';

  @override
  String get mobileRequestsStatusRejected => 'প্রত্যাখ্যাত';

  @override
  String get mobileRequestsUnnamed => 'নামহীন';

  @override
  String get mobileRequestsOpenMap => 'অবস্থান';

  @override
  String get mobileRequestsPhoneCopied => 'ফোন নম্বর কপি হয়েছে';

  @override
  String get mobileRequestsRiskyCustomer => 'উচ্চ নো-শো ঝুঁকিসম্পন্ন গ্রাহক';

  @override
  String mobileRequestsRejectReasonLine(Object reason) {
    return 'প্রত্যাখ্যানের কারণ: $reason';
  }

  @override
  String get mobileRequestsActionAccept => 'গ্রহণ করুন';

  @override
  String get mobileRequestsActionReject => 'প্রত্যাখ্যান করুন';

  @override
  String get mobileRequestsActionComplete => 'সম্পন্ন';

  @override
  String get mobileRequestsActionNoShow => 'উপস্থিত হয়নি';

  @override
  String get mobileRequestsAssignUnassigned => 'অনির্ধারিত';

  @override
  String get mobileRequestsActionFailed =>
      'কাজটি সম্পন্ন করা যায়নি, আবার চেষ্টা করুন।';

  @override
  String get mobileRequestsRejectTitle => 'প্রত্যাখ্যানের কারণ';

  @override
  String get mobileRequestsRejectHint => 'ঐচ্ছিক';

  @override
  String get mobileRequestsRejectCancel => 'বাতিল করুন';

  @override
  String get mobileRequestsRejectConfirm => 'অনুরোধ প্রত্যাখ্যান করুন';

  @override
  String get mobileRequestsAddOpen => 'অনুরোধ যোগ করুন';

  @override
  String get mobileRequestsAddTitle => 'মোবাইল সার্ভিস অনুরোধ যোগ করুন';

  @override
  String get mobileRequestsAddPhoneLabel => 'গ্রাহকের ফোন';

  @override
  String get mobileRequestsAddNameLabel => 'গ্রাহকের নাম (ঐচ্ছিক)';

  @override
  String get mobileRequestsAddServicesLabel => 'সেবাসমূহ';

  @override
  String get mobileRequestsAddServicesEmpty => 'এখনো কোনো সেবা উপলব্ধ নেই।';

  @override
  String get mobileRequestsAddDayLabel => 'দিন';

  @override
  String get mobileRequestsAddTimeLabel => 'সময়';

  @override
  String get mobileRequestsAddMapsLinkLabel => 'গুগল ম্যাপস অবস্থান লিঙ্ক';

  @override
  String get mobileRequestsAddMapsLinkHint =>
      'সম্পূর্ণ বা সংক্ষিপ্ত গুগল ম্যাপস লিঙ্ক গ্রহণ করে।';

  @override
  String get mobileRequestsAddMapsLinkShort =>
      'এটি একটি সংক্ষিপ্ত লিঙ্ক — সম্পূর্ণ গুগল ম্যাপস লিঙ্ক পেস্ট করুন।';

  @override
  String get mobileRequestsAddMapsLinkInvalid =>
      'এই লিঙ্ক থেকে অবস্থান পড়া যায়নি।';

  @override
  String get mobileRequestsAddAssignLabel => 'নিয়োগ করুন (ঐচ্ছিক)';

  @override
  String get mobileRequestsAddCancel => 'বাতিল করুন';

  @override
  String get mobileRequestsAddSubmit => 'অনুরোধ যোগ করুন';

  @override
  String get mobileRequestsAddSubmitting => 'যোগ করা হচ্ছে...';

  @override
  String get mobileRequestsAddError =>
      'অনুরোধ যোগ করা যায়নি, আবার চেষ্টা করুন।';

  @override
  String mobileRequestsBannerText(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$countটি অনুরোধ এখন আপনার সিদ্ধান্তের অপেক্ষায়',
    );
    return '$_temp0';
  }

  @override
  String get mobileRequestsAddMapsLinkResolving =>
      'লিঙ্ক থেকে অবস্থান পড়া হচ্ছে...';

  @override
  String get customersTitle => 'পরিচিতি';

  @override
  String get customersAddOpen => 'গ্রাহক যোগ করুন';

  @override
  String get customersSearchHint => 'নাম বা ফোন দিয়ে খুঁজুন';

  @override
  String get customersTabAll => 'সব';

  @override
  String get customersTabOverdue => 'বিলম্বিত';

  @override
  String get customersSearchFailedTitle => 'এখন অনুসন্ধান উপলব্ধ নয়';

  @override
  String get customersSearchFailedBody => 'শীঘ্রই আবার চেষ্টা করুন।';

  @override
  String get customersSearchEmpty => 'কোনো ফলাফল নেই';

  @override
  String get customersLoadFailedTitle => 'লোড করা যায়নি';

  @override
  String get customersEmptyTitle => 'এখনো কোনো গ্রাহক নেই';

  @override
  String get customersOverdueEmpty => 'এখন কেউ বিলম্বিত নয়';

  @override
  String get customersUnnamed => 'নামহীন';

  @override
  String customersVisitCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$countটি ভিজিট',
    );
    return '$_temp0';
  }

  @override
  String get customersOverdueBadge => 'বিলম্বিত';

  @override
  String customersStatEveryDays(int days) {
    String _temp0 = intl.Intl.pluralLogic(
      days,
      locale: localeName,
      other: 'প্রতি $days দিন',
    );
    return '$_temp0';
  }

  @override
  String customersOverdueBanner(int every, int since) {
    return 'তার স্বাভাবিক ভিজিটের চেয়ে দেরি — সাধারণত প্রতি $every দিনে, শেষ ভিজিটের পর $since দিন হয়েছে';
  }

  @override
  String customersVisitMeter(int n) {
    return 'মিটার রিডিং: $n';
  }

  @override
  String get customersOfferExpiredBadge => 'মেয়াদোত্তীর্ণ';

  @override
  String get customersDeniedAllTitle => 'গ্রাহক তালিকা দেখার অনুমতি আপনার নেই';

  @override
  String get customersDeniedOverdueTitle =>
      'কে দেরি করেছে তা দেখার অনুমতি আপনার নেই';

  @override
  String get customersDeniedDesc => 'দোকান মালিকের কাছে এই অনুমতি চান।';

  @override
  String get customersAddTitle => 'নতুন গ্রাহক যোগ করুন';

  @override
  String get customersAddPhoneLabel => 'গ্রাহকের ফোন';

  @override
  String get customersAddNameLabel => 'গ্রাহকের নাম';

  @override
  String get customersAddPhoneInvalid => 'ফোন নম্বর সঠিক নয়।';

  @override
  String get customersAddFailed => 'গ্রাহক যোগ করা যায়নি, আবার চেষ্টা করুন।';

  @override
  String get customersAddSubmitting => 'যোগ করা হচ্ছে...';

  @override
  String get customersAddSubmit => 'যোগ করুন';

  @override
  String get customersActionFailed =>
      'কাজটি সম্পন্ন করা যায়নি, আবার চেষ্টা করুন।';

  @override
  String get customersRepeatedIssuesTitle => 'পুনরাবৃত্ত সমস্যা';

  @override
  String get customersVehiclesTitle => 'যানবাহন';

  @override
  String get customersLoyaltyTitle => 'লয়্যালটি';

  @override
  String get customersLoyaltyLoading => 'লোড হচ্ছে...';

  @override
  String customersLoyaltyPoints(int count) {
    return '$count পয়েন্ট';
  }

  @override
  String get customersLoyaltyAdjust => 'সামঞ্জস্য করুন';

  @override
  String get customersOffersTitle => 'সক্রিয় অফার';

  @override
  String customersOfferExpires(String date) {
    return '$date মেয়াদ শেষ';
  }

  @override
  String get customersVisitsTitle => 'ভিজিটের ইতিহাস';

  @override
  String get customersVisitsEmpty => 'এখনো কোনো ভিজিট নেই';

  @override
  String get customersVisitNoServices => 'কোনো সেবা রেকর্ড করা হয়নি';

  @override
  String get customersRenameTitle => 'গ্রাহকের নাম সম্পাদনা করুন';

  @override
  String get customersRenameSubmit => 'সংরক্ষণ করুন';

  @override
  String get customersLoyaltyAdjustTitle => 'লয়্যালটি পয়েন্ট সামঞ্জস্য করুন';

  @override
  String get customersLoyaltyAdjustNoteLabel => 'সামঞ্জস্যের কারণ';

  @override
  String get customersLoyaltyAdjustNoteRequired =>
      'একটি বাস্তব কারণ লিখুন (কমপক্ষে ৩ অক্ষর), এবং শূন্য নয় এমন সংখ্যা বেছে নিন।';

  @override
  String get customersLoyaltyAdjustSubmit => 'সামঞ্জস্য সংরক্ষণ করুন';

  @override
  String get customersEraseButton => 'এই গ্রাহকের তথ্য মুছুন';

  @override
  String get customersEraseTitle => 'গ্রাহকের তথ্য মুছুন';

  @override
  String get customersEraseWarning =>
      'এটি প্ল্যাটফর্ম থেকে গ্রাহকের সমস্ত তথ্য স্থায়ীভাবে মুছে দেয় — এটি ফিরিয়ে আনা যাবে না।';

  @override
  String customersEraseTypeNameLabel(String name) {
    return 'নিশ্চিত করতে, গ্রাহকের নাম লিখুন: $name';
  }

  @override
  String get customersEraseConfirm => 'স্থায়ীভাবে মুছুন';

  @override
  String get customersBookingsTitle => 'বুকিং';

  @override
  String customersAttendanceRate(int rate) {
    return '$rate% উপস্থিতি';
  }

  @override
  String get customersBookingsNoneUpcoming => 'কোনো আসন্ন বুকিং নেই';

  @override
  String get customersCyclesTitle => 'রিমাইন্ডার চক্র';

  @override
  String customersCyclesEveryDays(int days) {
    return 'প্রতি $days দিন';
  }

  @override
  String get customersCyclesEditHint =>
      'ব্যবধান নির্ধারণ করুন, এবং এই গ্রাহকের সাথে এই সেবার জন্য স্বয়ংক্রিয় শিক্ষণ বন্ধ হয়ে যাবে।';

  @override
  String get customersCyclesSave => 'সংরক্ষণ করুন';

  @override
  String get customersLogTitle => 'আমরা তাকে যা বলেছি';

  @override
  String get customersLogEmpty => 'আমরা এখনো তাকে কিছু পাঠাইনি';

  @override
  String get customersCyclesUnknownService => 'অজানা সেবা';

  @override
  String customersVisitGapDays(int days) {
    String _temp0 = intl.Intl.pluralLogic(
      days,
      locale: localeName,
      other: '$days দিন পরে',
      zero: 'একই দিনে',
    );
    return '$_temp0';
  }

  @override
  String customersCountLabel(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count জন গ্রাহক',
      zero: 'এখনো কোনো গ্রাহক নেই',
    );
    return '$_temp0';
  }

  @override
  String get ratingTitle => 'রেটিং';

  @override
  String get pointsTitle => 'লয়্যালটি পয়েন্ট';

  @override
  String get pointsAddReward => 'নতুন পুরস্কার';

  @override
  String get pointsEditReward => 'পুরস্কার সম্পাদনা';

  @override
  String get pointsTabRewards => 'পুরস্কার';

  @override
  String get pointsTabLeaderboard => 'সবচেয়ে বেশি বিনিময়';

  @override
  String get pointsOutstandingHint =>
      'পয়েন্ট যা দোকান এখনও গ্রাহকদের কাছে ঋণী';

  @override
  String pointsRedemptionsCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$countটি বিনিময়',
    );
    return '$_temp0';
  }

  @override
  String pointsCustomersCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count জন গ্রাহক বিনিময় করেছেন',
    );
    return '$_temp0';
  }

  @override
  String pointsExpiredWarning(int percent) {
    return 'প্রদত্ত পয়েন্টের $percent% বিনিময় ছাড়াই মেয়াদোত্তীর্ণ হয়েছে — আপনার পুরস্কারের মূল্য পর্যালোচনা করুন';
  }

  @override
  String get pointsLoadFailedTitle => 'পুরস্কার লোড করা যায়নি';

  @override
  String get pointsRewardsEmpty =>
      'এখনো কোন পুরস্কার নেই — আপনার গ্রাহকদের প্রথম পুরস্কার যোগ করুন';

  @override
  String get pointsLeaderboardEmpty =>
      'এখনো কোন বিনিময় নেই — গ্রাহক একটি বিনিময় করলে এখানে দেখা যাবে';

  @override
  String get pointsLeaderboardTitle => 'সবচেয়ে বেশি বিনিময়';

  @override
  String get pointsLeaderboardHint =>
      'আপনার গ্রাহকরা বিনিময় করা শীর্ষ পাঁচটি পুরস্কার';

  @override
  String pointsTimesRedeemed(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count বার',
    );
    return '$_temp0';
  }

  @override
  String get pointsRewardRetired => 'বন্ধ';

  @override
  String pointsRewardServiceHint(String name) {
    return 'সেবা: $name';
  }

  @override
  String pointsRewardDiscountHint(String amount) {
    return '$amount রিয়াল ছাড়';
  }

  @override
  String get pointsRewardItemHint =>
      'একটি উপহার, ক্যাটালগের সাথে সম্পর্কিত নয়';

  @override
  String get pointsRewardNameLabel => 'পুরস্কারের নাম';

  @override
  String get pointsRewardTypeLabel => 'পুরস্কারের ধরন';

  @override
  String get pointsTypeService => 'আপনার ক্যাটালগ থেকে একটি সেবা';

  @override
  String get pointsTypeItem => 'একটি উপহার';

  @override
  String get pointsTypeDiscount => 'নগদ ছাড়';

  @override
  String get pointsRewardServiceLabel => 'কোন সেবা';

  @override
  String get pointsRewardDiscountLabel => 'ছাড়ের পরিমাণ, রিয়াল';

  @override
  String get pointsRewardCostLabel => 'পয়েন্টে খরচ';

  @override
  String get pointsRewardActiveLabel =>
      'সক্রিয় — গ্রাহকরা এটি বিনিময় করতে পারবেন';

  @override
  String get pointsRewardInvalid =>
      'একটি নাম এবং শূন্যের বেশি প্রকৃত পয়েন্ট খরচ লিখুন';

  @override
  String get pointsSaveFailed => 'সংরক্ষণ করা যায়নি, আবার চেষ্টা করুন';

  @override
  String get pointsModeTitle => 'হিসাবের পদ্ধতি';

  @override
  String get pointsModeHint =>
      'সেবা অনুযায়ী: প্রতিটি সেবার নিজস্ব পয়েন্ট। বিলের মূল্য অনুযায়ী: প্রতি রিয়ালে এক পয়েন্ট।';

  @override
  String get pointsModeServices => 'সেবা অনুযায়ী';

  @override
  String get pointsModeInvoice => 'বিলের মূল্য অনুযায়ী';

  @override
  String get pointsModeNeedsPricedServices =>
      'বিলের মূল্য অনুযায়ী হিসাবের জন্য প্রথমে আপনার সব সেবার মূল্য নির্ধারণ থাকতে হবে — সেবাগুলোতে সবগুলোর দাম দিন, তারপর চালু করুন।';

  @override
  String get pointsOpenEarnSettings => 'প্রতি সেবার পয়েন্ট সেটিংস';

  @override
  String get ratingLeaderboardTitle => 'সর্বোচ্চ রেটেড';

  @override
  String get ratingCardNoName => 'নামহীন';

  @override
  String get ratingMetricVisits => 'সবচেয়ে বেশি ভিজিট';

  @override
  String get ratingMetricRatings => 'সবচেয়ে বেশি রেটিং';

  @override
  String get ratingMetricAvg => 'সর্বোচ্চ রেটেড';

  @override
  String ratingStaffCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count জন কর্মী',
    );
    return '$_temp0';
  }

  @override
  String get ratingTableTitle => 'প্রতিটি কর্মী';

  @override
  String ratingTableVisitsValue(int n) {
    return '$n ভিজিট';
  }

  @override
  String ratingTableRatingsValue(int n) {
    return '$n রেটিং';
  }

  @override
  String ratingTableEngagementValue(int n) {
    return 'সম্পৃক্ততা $n%';
  }

  @override
  String ratingTableNoShowValue(int n) {
    return 'অনুপস্থিত $n%';
  }

  @override
  String get ratingPeriodWeek => 'সপ্তাহ';

  @override
  String get ratingPeriodMonth => 'মাস';

  @override
  String get ratingPeriodQuarter => 'প্রান্তিক';

  @override
  String get ratingPeriodCustom => 'কাস্টম';

  @override
  String ratingCustomSince(String date) {
    return 'থেকে: $date';
  }

  @override
  String ratingCustomUntil(String date) {
    return 'পর্যন্ত: $date';
  }

  @override
  String get ratingCustomRangeInvalid =>
      'সীমা অবৈধ — শুরুর তারিখ শেষ তারিখের আগে কিনা নিশ্চিত করুন';

  @override
  String get ratingExportLocaleLabel => 'রিপোর্টের ভাষা';

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
  String get ratingTopIssuesTitle => 'সর্বাধিক পুনরাবৃত্ত সমস্যা';

  @override
  String get ratingFilterUnhandled => 'মুলতুবি';

  @override
  String get ratingFilterAll => 'সব';

  @override
  String get ratingFilterHandled => 'সমাধান হয়েছে';

  @override
  String get ratingStarsAll => 'সব তারকা';

  @override
  String get ratingLoadFailedTitle => 'রেটিং লোড করা যায়নি';

  @override
  String get ratingEmptyTitle => 'এখনো কোনো রেটিং নেই';

  @override
  String get ratingLoadMore => 'আরও দেখুন';

  @override
  String get ratingHandledPlain => 'সমাধান হয়ে গেছে';

  @override
  String get ratingMarkHandled => 'সমাধান হয়েছে হিসেবে চিহ্নিত করুন';

  @override
  String get ratingMarkHandledHint =>
      'এটি স্থায়ীভাবে রেকর্ড করা হয় — পরে ফিরিয়ে নেওয়া যাবে না।';

  @override
  String get ratingHandledNoteLabel => 'নোট (ঐচ্ছিক)';

  @override
  String get ratingMarkHandledConfirm => 'নিশ্চিত করুন';

  @override
  String get ratingActionFailed =>
      'কাজটি সম্পন্ন করা যায়নি, আবার চেষ্টা করুন।';

  @override
  String ratingWeightedAvgHint(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'গত ৩০ দিনে $countটি রেটিং থেকে',
      zero: 'গত ৩০ দিনে কোনো রেটিং নেই',
    );
    return '$_temp0';
  }

  @override
  String ratingUnhandledCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$countটি রেটিং মুলতুবি',
    );
    return '$_temp0';
  }

  @override
  String ratingVisitsShort(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$countটি ভিজিট',
    );
    return '$_temp0';
  }

  @override
  String ratingIssueFilterLabel(String label) {
    return 'সমস্যা: $label';
  }

  @override
  String ratingByOperator(String name) {
    return '$name সেবা দিয়েছেন';
  }

  @override
  String ratingHandledWithNote(String note) {
    return 'সমাধান হয়েছে: $note';
  }

  @override
  String get ratingQuadrantTitle => 'পারফরম্যান্স কোয়াড্রেন্ট';

  @override
  String get ratingQuadrantHint =>
      'গুণমান বনাম সম্পৃক্ততার হার — প্রশিক্ষণ রেকর্ডের জন্য যেকোনো পয়েন্টে চাপুন।';

  @override
  String get ratingQuadrantStars => 'তারকা';

  @override
  String get ratingQuadrantUnderused => 'কম ব্যবহৃত';

  @override
  String get ratingQuadrantNeedsCoaching => 'প্রশিক্ষণ প্রয়োজন';

  @override
  String get ratingQuadrantAtRisk => 'মনোযোগ প্রয়োজন';

  @override
  String get ratingTrainingTitle => 'প্রশিক্ষণ রেকর্ড';

  @override
  String get ratingTrainingNoAccess => 'এটি দেখার অনুমতি আপনার নেই।';

  @override
  String get ratingTrainingClean =>
      'পরিষ্কার রেকর্ড — কোনো পুনরাবৃত্ত সমস্যা নেই।';

  @override
  String ratingEngagementPercent(int percent) {
    return '$percent% সম্পৃক্ততা';
  }

  @override
  String get ratingTabOverview => 'ওভারভিউ';

  @override
  String get ratingTabFeed => 'সব রেটিং';

  @override
  String get ratingOverviewEmpty =>
      'গত 30 দিনের জন্য এখনো কোনো পারফরম্যান্স তথ্য নেই।';

  @override
  String get ratingExportTitle => 'রিপোর্ট রপ্তানি করুন';

  @override
  String get ratingExportHint =>
      'নির্বাচিত সময়ের জন্য দলের পারফরম্যান্স রিপোর্ট, শেয়ার করার জন্য প্রস্তুত।';

  @override
  String get ratingExportFailed =>
      'রিপোর্ট রপ্তানি করা যায়নি, আবার চেষ্টা করুন।';

  @override
  String get customersPrivacyRequestsTitle => 'গোপনীয়তা অনুরোধ';

  @override
  String get customersPrivacyRequestErase => 'তথ্য মুছার অনুরোধ';

  @override
  String get customersPrivacyRequestCopy => 'তথ্যের কপির অনুরোধ';

  @override
  String customersPrivacyRequestGeneric(String type) {
    return 'অনুরোধ: $type';
  }

  @override
  String get customersPrivacyRequestClose => 'বন্ধ করুন';

  @override
  String get customersLoyaltyHistoryTitle => 'পয়েন্ট ইতিহাস';

  @override
  String get customersLoyaltyHistoryNoReason => 'কোনো কারণ উল্লেখ করা হয়নি';

  @override
  String get customersLoyaltyReasonRedeem => 'পুরস্কার ব্যবহৃত';

  @override
  String get customersLoyaltyReasonAdjust => 'ম্যানুয়াল সমন্বয়';

  @override
  String get customersLoyaltyReasonEarn => 'ভিজিট থেকে পয়েন্ট';

  @override
  String get customersLoyaltyReasonExpire => 'মেয়াদোত্তীর্ণ';

  @override
  String get readCustomersFailed =>
      'এখন গ্রাহকের তথ্য পাওয়া যায়নি, আবার চেষ্টা করুন।';

  @override
  String readCustomersTotal(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'আপনার $count জন নিবন্ধিত গ্রাহক আছে।',
      zero: 'আপনার এখনো কোনো নিবন্ধিত গ্রাহক নেই।',
    );
    return '$_temp0';
  }

  @override
  String readCustomersOverdueCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'আপনার $count জন গ্রাহক তাদের চক্রে বিলম্বিত।',
      zero: 'এখন কোনো গ্রাহক তাদের চক্রে বিলম্বিত নয়।',
    );
    return '$_temp0';
  }

  @override
  String get readMobileRequestsFailed =>
      'এখন মোবাইল অনুরোধ পাওয়া যায়নি, আবার চেষ্টা করুন।';

  @override
  String readMobileRequestsPendingCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'আপনার $countটি অনুরোধ সিদ্ধান্তের অপেক্ষায়।',
      zero: 'কোনো মোবাইল অনুরোধ সিদ্ধান্তের অপেক্ষায় নেই।',
    );
    return '$_temp0';
  }

  @override
  String readMobileRequestsNeedsDecisionCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$countটি অনুরোধ এখন আপনার সিদ্ধান্তের অপেক্ষায়।',
      zero: 'এখন কোনো মোবাইল অনুরোধ আপনার সিদ্ধান্তের প্রয়োজন নেই।',
    );
    return '$_temp0';
  }

  @override
  String get readRatingFailed =>
      'এখন রেটিং তথ্য পাওয়া যায়নি, আবার চেষ্টা করুন।';

  @override
  String get readRatingNone => 'গত 30 দিনে আপনার এখনো কোনো রেটিং নেই।';

  @override
  String readRatingAverage(String avg, int count) {
    return 'গত 30 দিনে আপনার গড় রেটিং 5 এর মধ্যে $avg, $countটি রেটিং থেকে।';
  }

  @override
  String readRatingUnhandledCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'আপনার $countটি রেটিং মুলতুবি রয়েছে।',
      zero: 'কোনো রেটিং মুলতুবি নেই।',
    );
    return '$_temp0';
  }

  @override
  String readRatingTopStaff(String name, String avg) {
    return 'গত 30 দিনে আপনার শীর্ষ রেটেড স্টাফ হলেন $name, গড়ে 5-এর মধ্যে $avg।';
  }

  @override
  String readMobileRequestsCompletedCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'এই মাসে আপনি $countটি সম্পন্ন করেছেন।',
      zero: 'এই মাসে আপনি এখনো কোনো মোবাইল অনুরোধ সম্পন্ন করেননি।',
    );
    return '$_temp0';
  }

  @override
  String readMobileRequestsTodayCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'আজ $countটি অনুরোধ এসেছে।',
      zero: 'আজ এখনো কোনো মোবাইল অনুরোধ আসেনি।',
    );
    return '$_temp0';
  }

  @override
  String get readOperatorsFailed =>
      'এখন কর্মীর সংখ্যা পাওয়া যায়নি, আবার চেষ্টা করুন।';

  @override
  String readOperatorsCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'আপনার দলে $count জন কর্মী আছেন।',
      zero: 'আপনার এখনো কোনো নিবন্ধিত কর্মী নেই।',
    );
    return '$_temp0';
  }

  @override
  String readBranchesDisconnectedCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'আপনার $countটি শাখার হোয়াটসঅ্যাপ কাজ করছে না।',
      zero: 'আপনার সব সক্রিয় শাখার হোয়াটসঅ্যাপ সংযুক্ত এবং কাজ করছে।',
    );
    return '$_temp0';
  }

  @override
  String get readCustomersRecentNone => 'আপনার এখনো কোনো নিবন্ধিত গ্রাহক নেই।';

  @override
  String readCustomersRecentName(String name) {
    return 'আপনার সাম্প্রতিকতম গ্রাহক হলেন $name।';
  }

  @override
  String readRatingCriticalIssuesCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'আপনার $countটি মুলতুবি রেটিংয়ে গুরুতর সমস্যা রয়েছে।',
      zero: 'কোনো মুলতুবি রেটিংয়ে গুরুতর সমস্যা নেই।',
    );
    return '$_temp0';
  }

  @override
  String get readPerBranchModeOn =>
      'হ্যাঁ, আপনার দোকান মাল্টি-ব্রাঞ্চ মোডে চলে।';

  @override
  String get readPerBranchModeOff =>
      'না, আপনার দোকান শুধুমাত্র একটি শাখা হিসেবে চলে।';

  @override
  String get readBillingOverdueYes =>
      'হ্যাঁ, আপনার একটি বকেয়া চালান আছে — পরিষেবা বন্ধ হওয়া এড়াতে পরিশোধ করুন।';

  @override
  String get readBillingOverdueNo =>
      'না, আপনার বিলিং ঠিক আছে, কোনো বকেয়া চালান নেই।';

  @override
  String get readServicesFailed =>
      'এখন সেবার সংখ্যা পাওয়া যায়নি, আবার চেষ্টা করুন।';

  @override
  String readServicesCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'আপনার তালিকায় $countটি সেবা আছে।',
      zero: 'আপনার তালিকায় এখনো কোনো সেবা নেই।',
    );
    return '$_temp0';
  }

  @override
  String readCustomersTodayCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'আজ $count জন নতুন গ্রাহক এসেছেন।',
      zero: 'আজ এখনো কোনো নতুন গ্রাহক আসেননি।',
    );
    return '$_temp0';
  }

  @override
  String readMobileRequestsRejectedCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'এই মাসে আপনি $countটি প্রত্যাখ্যান করেছেন।',
      zero: 'এই মাসে আপনি কোনো মোবাইল অনুরোধ প্রত্যাখ্যান করেননি।',
    );
    return '$_temp0';
  }

  @override
  String readMobileRequestsNoShowCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'এই মাসে $count জন গ্রাহক অনুপস্থিত ছিলেন।',
      zero: 'এই মাসে কোনো গ্রাহক অনুপস্থিত থাকেননি।',
    );
    return '$_temp0';
  }

  @override
  String readRatingFiveStarCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'আপনার $countটি ৫-তারকা রেটিং আছে।',
      zero: 'আপনার এখনো কোনো ৫-তারকা রেটিং নেই।',
    );
    return '$_temp0';
  }

  @override
  String readBranchesActiveCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'আপনার $countটি সক্রিয় শাখা আছে।',
      zero: 'এখন আপনার কোনো সক্রিয় শাখা নেই।',
    );
    return '$_temp0';
  }

  @override
  String get servicesTitle => 'আমার সেবা';

  @override
  String get servicesUnnamedGlyph => '?';

  @override
  String get servicesSearchHint => 'সেবার নাম দিয়ে খুঁজুন';

  @override
  String get servicesTabActive => 'সক্রিয়';

  @override
  String get servicesTabStopped => 'বন্ধ';

  @override
  String get servicesLoadFailedTitle => 'সেবা লোড করা যায়নি';

  @override
  String get servicesEmptyActive => 'এখনো কোনো সক্রিয় সেবা নেই';

  @override
  String get servicesEmptyStopped => 'কোনো বন্ধ সেবা নেই';

  @override
  String get servicesAddOpen => 'সেবা যোগ করুন';

  @override
  String get servicesNoPrice => 'কোনো মূল্য নির্ধারিত নেই';

  @override
  String get servicesNoDuration => 'নির্ধারিত নয়';

  @override
  String get servicesNoCycle => 'কোনো চক্র নেই';

  @override
  String get servicesStopTitle => 'সেবা বন্ধ করুন';

  @override
  String get servicesStopConfirm => 'বন্ধ করুন';

  @override
  String get servicesActionFailed =>
      'কাজটি সম্পন্ন করা যায়নি, আবার চেষ্টা করুন।';

  @override
  String get servicesEditTitle => 'সেবা সম্পাদনা করুন';

  @override
  String get servicesAddTitle => 'নতুন সেবা যোগ করুন';

  @override
  String get servicesNameLabel => 'সেবার নাম';

  @override
  String get servicesPriceLabel => 'মূল্য (ঐচ্ছিক)';

  @override
  String get servicesDurationLabel => 'মিনিটে সময়কাল (ঐচ্ছিক)';

  @override
  String get servicesCycleLabel => 'দিনে রিমাইন্ডার চক্র (ঐচ্ছিক)';

  @override
  String get servicesDescriptionLabel => 'সংক্ষিপ্ত বিবরণ (ঐচ্ছিক)';

  @override
  String get servicesSaving => 'সংরক্ষণ করা হচ্ছে...';

  @override
  String get servicesSave => 'সংরক্ষণ করুন';

  @override
  String get servicesNameRequired => 'সেবার নাম আবশ্যক';

  @override
  String servicesActiveCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'আপনার $countটি সক্রিয় সেবা আছে।',
      zero: 'আপনার এখনো কোনো সক্রিয় সেবা নেই।',
    );
    return '$_temp0';
  }

  @override
  String servicesDurationMinutes(int count) {
    return '$count মিনিট';
  }

  @override
  String servicesCycleDays(int count) {
    return 'প্রতি $count দিন';
  }

  @override
  String servicesStopWarning(String name) {
    return 'এটি \"$name\" বন্ধ করবে — নতুন ভিজিটে দেখাবে না, এবং এর রিমাইন্ডার বন্ধ হয়ে যাবে। এর তথ্য কখনো মুছে ফেলা হয় না।';
  }

  @override
  String get servicesPhotoPickFailed => 'ছবি নির্বাচন করা যায়নি';

  @override
  String get servicesPhotoUploadFailed =>
      'সংরক্ষিত হয়েছে, কিন্তু ছবি আপলোড করা যায়নি';

  @override
  String get servicesPhotoLabel => 'সেবার ছবি (ঐচ্ছিক)';

  @override
  String get servicesUploadPhoto => 'ছবি আপলোড করুন';

  @override
  String get servicesChangePhoto => 'ছবি পরিবর্তন করুন';

  @override
  String get servicesRemovePhoto => 'সরান';

  @override
  String get servicesAssignmentLabel => 'এই সেবা কে প্রদান করে?';

  @override
  String get servicesAssignmentAuto => 'যেকোনো উপলব্ধ কর্মী';

  @override
  String get servicesAssignmentNamed => 'নির্দিষ্ট কর্মী';

  @override
  String get servicesChecklistLabel => 'প্রক্রিয়ার তালিকা';

  @override
  String get servicesChecklistEmpty => 'এখনো কোনো ধাপ নেই — প্রথমটি যোগ করুন';

  @override
  String get servicesStepAddTitle => 'ধাপ যোগ করুন';

  @override
  String get servicesGeneralSettingsTitle => 'সাধারণ সেটিং';

  @override
  String get servicesGeneralSettingsHint =>
      'যে মান প্রতিটি কাস্টমাইজ না করা সেবা অনুসরণ করে';

  @override
  String get servicesFollowUpLabel => 'ভিজিটের পর ফলো-আপ দিন';

  @override
  String get servicesPointsLabel => 'প্রতি ভিজিট পয়েন্ট';

  @override
  String get servicesGroupThem => 'একত্র করুন';

  @override
  String get servicesGroupNameHint => 'গ্রুপের নাম';

  @override
  String get servicesAllGroups => 'সব';

  @override
  String get servicesStepEditTitle => 'ধাপ সম্পাদনা করুন';

  @override
  String get servicesStepCriticalLabel => 'সংকটাপন্ন ধাপ';

  @override
  String get servicesStepRetire => 'এই ধাপ বন্ধ করুন';

  @override
  String get servicesStepEditHint =>
      'যেকোনো ধাপে দীর্ঘক্ষণ চাপুন সম্পাদনা বা বন্ধ করতে';

  @override
  String get servicesAdvancedTitle => 'উন্নত সেটিং';

  @override
  String get servicesAdvancedHint =>
      'সাধারণ সেটিং থেকে এই সেবা কাস্টমাইজ করুন — চক্র, পয়েন্ট, এবং গ্রুপিং';

  @override
  String get servicesGroupLabel => 'গ্রুপ';

  @override
  String get servicesNoGroup => 'কোনো গ্রুপ নেই';

  @override
  String get servicesNewGroup => 'নতুন গ্রুপ';

  @override
  String get servicesFollowGeneralAction => 'সাধারণ অনুসরণ করুন';

  @override
  String get servicesCustomizeAction => 'কাস্টমাইজ';

  @override
  String servicesFollowUpDays(int n) {
    return '$n দিন পর ফলো-আপ';
  }

  @override
  String servicesPointsPerVisit(int n) {
    return '$n পয়েন্ট';
  }

  @override
  String servicesSuggestionText(int n) {
    return '$nটি সেবা একই মান শেয়ার করে — তাদের একটি গ্রুপে একত্র করলে পরে একসাথে সম্পাদনা সহজ হবে।';
  }

  @override
  String servicesFollowsGeneral(String hint) {
    return 'সাধারণ অনুসরণ করে — $hint';
  }

  @override
  String get servicesPageTabServices => 'সেবাসমূহ';

  @override
  String get servicesPageTabPackages => 'প্যাকেজ';

  @override
  String get servicesPackageAdd => 'প্যাকেজ যোগ করুন';

  @override
  String get servicesPackageNeedsTwoServices =>
      'প্যাকেজের জন্য অন্তত দুটি সক্রিয় সেবা প্রয়োজন';

  @override
  String get servicesPackageEmpty => 'এখনো কোনো প্যাকেজ নেই';

  @override
  String get servicesPackageEditTitle => 'প্যাকেজ সম্পাদনা করুন';

  @override
  String get servicesPackageAddTitle => 'নতুন প্যাকেজ যোগ করুন';

  @override
  String get servicesPackageNameLabel => 'প্যাকেজের নাম';

  @override
  String get servicesPackagePriceRequired =>
      'প্যাকেজের মূল্য আবশ্যক, শূন্যের বেশি';

  @override
  String get servicesPackageServicesLabel => 'অন্তর্ভুক্ত সেবা';

  @override
  String get servicesImportTitle => 'ফাইল থেকে সেবা আমদানি করুন';

  @override
  String get servicesImportHint =>
      'কলামসহ CSV ফাইল: name, price, duration_minutes, cycle_days, description';

  @override
  String get servicesImportPickFile => 'CSV ফাইল নির্বাচন করুন';

  @override
  String get servicesImportReadFailed => 'ফাইল পড়া যায়নি';

  @override
  String get servicesImportParseFailed =>
      'ফাইলে name কলাম নেই, অথবা এর ফরম্যাট সঠিক নয়';

  @override
  String get servicesImportDeactivateMissing =>
      'ফাইলে অনুপস্থিত সেবা বন্ধ করুন';

  @override
  String get servicesImportDeactivateMissingHint =>
      'আপনার বর্তমান যেকোনো সেবা যা এই ফাইলে নেই তা স্বয়ংক্রিয়ভাবে বন্ধ হয়ে যাবে';

  @override
  String get servicesImportConfirm => 'আমদানি করুন';

  @override
  String get servicesImportClose => 'সম্পন্ন';

  @override
  String servicesImportRowCount(int n) {
    return '$nটি সারি আমদানির জন্য প্রস্তুত';
  }

  @override
  String servicesImportDone(int created, int updated, int reactivated) {
    return '$createdটি যোগ, $updatedটি আপডেট, $reactivatedটি পুনরায় সক্রিয়।';
  }

  @override
  String get visitPackagesSectionTitle => 'বৈশিষ্ট্যযুক্ত প্যাকেজ';

  @override
  String get visitNameFieldHint => 'গ্রাহকের নাম (ঐচ্ছিক)';

  @override
  String get visitMeterFieldHint => 'মিটার রিডিং';

  @override
  String get visitQuantityDialogTitle => 'পরিমাণ';

  @override
  String get visitCouponCheckboxLabel => 'অন্য দোকানকে ছাড়ের কুপন দিন';

  @override
  String get visitCouponPhoneHint => 'দোকানের মালিকের ফোন';

  @override
  String get visitClearAllButton => 'সব মুছুন';

  @override
  String visitServicesSelectedCount(int n) {
    return '$nটি সেবা নির্বাচিত';
  }

  @override
  String get visitTodayBookingsTitle => 'আজকের অ্যাপয়েন্টমেন্ট';

  @override
  String get visitBookingAttendFailed =>
      'উপস্থিতি নিশ্চিত করা যায়নি, আবার চেষ্টা করুন';

  @override
  String get branchSwitcherChooseBranch => 'শাখা নির্বাচন করুন';

  @override
  String get branchSwitcherTitle => 'বর্তমান শাখা';

  @override
  String get branchSwitcherHint =>
      'এর পরে আপনি যা কিছু খুলবেন তা এই শাখার অন্তর্গত';

  @override
  String get proceduresPrintFailed => 'নথি তৈরি করা যায়নি';

  @override
  String get proceduresTitle => 'পদ্ধতিসমূহ';

  @override
  String get proceduresSubtitle =>
      'প্রতিটি সেবার জন্য পদ্ধতি তালিকা সেট করুন, অথবা পুরো শেয়ার্ড লাইব্রেরি পরিচালনা করুন। প্রিন্টের জন্য নির্বাচন করতে দীর্ঘক্ষণ চাপুন';

  @override
  String get proceduresLibraryLink => 'পদ্ধতি লাইব্রেরি';

  @override
  String get proceduresPrint => 'প্রিন্ট';

  @override
  String get proceduresEmptyTitle => 'এখনো কোনো সক্রিয় সেবা নেই';

  @override
  String get servicesStepSeverityNormal => 'সাধারণ';

  @override
  String get servicesStepSeverityCritical => 'জরুরি';

  @override
  String get proceduresSaveFailed => 'সংরক্ষণ করা যায়নি';

  @override
  String get proceduresDrawerSubtitle =>
      'ক্রম পরিবর্তনে টেনে আনুন, অথবা লাইব্রেরি থেকে একটি ধাপ যোগ করুন';

  @override
  String get proceduresDrawerEmpty => 'এই সেবার জন্য এখনো কোনো ধাপ নেই';

  @override
  String get proceduresDrawerAddButton => 'লাইব্রেরি থেকে যোগ করুন';

  @override
  String get proceduresPickTitle => 'একটি ধাপ বেছে নিন';

  @override
  String get proceduresPickClose => 'বন্ধ করুন';

  @override
  String get proceduresPickApply => 'যোগ করুন';

  @override
  String get proceduresPickSearch => 'ধাপ খুঁজুন';

  @override
  String get proceduresPickEmpty => 'কোনো ফলাফল নেই';

  @override
  String get proceduresPickCreatePlaceholder => 'নতুন ধাপ...';

  @override
  String get proceduresLibrarySaveFailed => 'সংরক্ষণ করা যায়নি';

  @override
  String get proceduresLibraryTitle => 'পদ্ধতি লাইব্রেরি';

  @override
  String get proceduresLibrarySubtitle =>
      'এখানের প্রতিটি ধাপ এটি ব্যবহারকারী সব সেবার মধ্যে শেয়ার করা - সম্পাদনা করলে সব জায়গায় পরিবর্তন হয়';

  @override
  String get proceduresLibraryNewPlaceholder => 'নতুন ধাপের লেখা';

  @override
  String get proceduresLibraryAdd => 'যোগ করুন';

  @override
  String get proceduresLibraryShowRetired => 'বাতিলকৃত দেখান';

  @override
  String get proceduresLibraryEmpty => 'এখনো কোনো ধাপ নেই';

  @override
  String get proceduresLibraryRetired => 'বাতিল';

  @override
  String get proceduresLibraryRetire => 'বাতিল করুন';

  @override
  String get proceduresLibraryReactivate => 'পুনরায় সক্রিয় করুন';

  @override
  String get proceduresSeverityHint =>
      'জরুরি ধাপ কর্মীর জন্য ভিন্ন রঙে হাইলাইট করা হয় এবং সেবা সম্পাদনের সময় এড়ানো যায় না';

  @override
  String proceduresSelectedCount(int n) {
    return '$nটি নির্বাচিত';
  }

  @override
  String proceduresStepCount(int n) {
    return '$nটি ধাপ';
  }

  @override
  String proceduresUsedIn(int n) {
    return '$nটি সেবায় ব্যবহৃত';
  }

  @override
  String get referralProposeButton => 'অংশীদারিত্ব প্রস্তাব করুন';

  @override
  String get referralTitle => 'কৌশলগত অংশীদারিত্ব';

  @override
  String get referralSubtitle =>
      'পারস্পরিক সম্মতিতে আপনার এবং অন্য দোকানের মধ্যে প্রকৃত গ্রাহক স্থানান্তর করুন';

  @override
  String get referralRoleAll => 'সব';

  @override
  String get referralRoleReferrer => 'রেফারার হিসেবে';

  @override
  String get referralRoleBeneficiary => 'সুবিধাভোগী হিসেবে';

  @override
  String get referralLoadFailed => 'অংশীদারিত্ব লোড করা যায়নি';

  @override
  String get referralEmptyTitle => 'এখনো কোনো অংশীদারিত্ব নেই';

  @override
  String get referralKpiAsReferrer => 'রেফারার হিসেবে';

  @override
  String get referralKpiAsBeneficiary => 'সুবিধাভোগী হিসেবে';

  @override
  String get referralKpiSent => 'রেফার করা হয়েছে';

  @override
  String get referralKpiRedeemed => 'রিডিম করা হয়েছে';

  @override
  String get referralKpiRate => 'রিডেম্পশন হার';

  @override
  String get referralConfirm => 'নিশ্চিত করুন';

  @override
  String get referralGrantDiscountBlanket => 'পুরো ভিজিটে ছাড়';

  @override
  String get referralStatusProposed => 'প্রস্তাবিত';

  @override
  String get referralStatusActive => 'সক্রিয়';

  @override
  String get referralStatusPaused => 'স্থগিত';

  @override
  String get referralStatusCancelRequested => 'বাতিলের অনুরোধ করা হয়েছে';

  @override
  String get referralStatusEnded => 'সমাপ্ত';

  @override
  String get referralStatusRejected => 'প্রত্যাখ্যাত';

  @override
  String get referralStatusExpiredUnanswered => 'উত্তরহীন মেয়াদোত্তীর্ণ';

  @override
  String get referralEventProposed => 'অংশীদারিত্ব প্রস্তাবিত';

  @override
  String get referralEventAccepted => 'অংশীদারিত্ব গৃহীত';

  @override
  String get referralEventRejected => 'অংশীদারিত্ব প্রত্যাখ্যাত';

  @override
  String get referralEventActivated => 'অংশীদারিত্ব সক্রিয় হয়েছে';

  @override
  String get referralEventCancelRequested => 'বাতিলের অনুরোধ';

  @override
  String get referralEventCancelConfirmed => 'বাতিল নিশ্চিত হয়েছে';

  @override
  String get referralEventExpiredUnanswered => 'উত্তর ছাড়া মেয়াদোত্তীর্ণ';

  @override
  String get referralEventPaused => 'স্থগিত';

  @override
  String get referralEventResumed => 'পুনরায় শুরু';

  @override
  String get referralEventEndedTerm => 'মেয়াদ শেষ';

  @override
  String get referralEventGrantCreated => 'নতুন মঞ্জুরি';

  @override
  String get referralEventGrantRedeemed => 'মঞ্জুরি রিডিম হয়েছে';

  @override
  String get referralActivityActive => 'সক্রিয়';

  @override
  String get referralActivityPaused => 'স্থগিত';

  @override
  String get referralActivityPending => 'উত্তরের অপেক্ষায়';

  @override
  String get referralActivityInactive => 'নিষ্ক্রিয়';

  @override
  String get referralScorecardTitle => 'কর্মক্ষমতা';

  @override
  String get referralScorecardFailed => 'কর্মক্ষমতা লোড করা যায়নি';

  @override
  String get referralActivityTitle => 'সাম্প্রতিক কার্যকলাপ';

  @override
  String get referralActivityEmpty => 'এখনো কোনো কার্যকলাপ নেই';

  @override
  String get referralAgreementsTitle => 'চুক্তিসমূহ';

  @override
  String get referralConfirmCancel => 'এই অংশীদারিত্ব স্থায়ীভাবে শেষ করবেন?';

  @override
  String get referralActionAccept => 'গ্রহণ করুন';

  @override
  String get referralActionReject => 'প্রত্যাখ্যান করুন';

  @override
  String get referralActionWaitingThem => 'অন্য পক্ষের অপেক্ষায়';

  @override
  String get referralActionCancelRequest => 'শেষ করার অনুরোধ';

  @override
  String get referralActionCancelConfirm => 'সমাপ্তি নিশ্চিত করুন';

  @override
  String get referralProposeTitle => 'নতুন অংশীদারিত্ব প্রস্তাব করুন';

  @override
  String get referralProposePhoneLabel => 'অন্য দোকানের ফোন';

  @override
  String get referralProposeConditionLabel => 'আপনার দোকানে যোগ্যতার শর্ত';

  @override
  String get referralConditionMinTotal => 'সর্বনিম্ন চালান';

  @override
  String get referralConditionServiceId => 'নির্দিষ্ট একটি সেবা';

  @override
  String get referralProposeConditionValueRiyals => 'পরিমাণ (রিয়াল)';

  @override
  String get referralProposeConditionValueService => 'সেবা';

  @override
  String get referralProposeValidityLabel => 'মেয়াদ (দিন)';

  @override
  String get referralProposeDurationLabel => 'সময়কাল (দিন)';

  @override
  String get referralProposeCapLabel => 'সীমা / ৩০ দিন';

  @override
  String get referralProposeGrantTypeLabel => 'মঞ্জুরির ধরন';

  @override
  String get referralGrantTypeDiscount => 'ছাড়';

  @override
  String get referralGrantTypeGift => 'উপহার';

  @override
  String get referralScopeBlanket => 'পুরো ভিজিট';

  @override
  String get referralScopeItem => 'নির্দিষ্ট একটি সেবা';

  @override
  String get referralScopeGroup => 'গ্রুপ/প্যাকেজ';

  @override
  String get referralProposeServiceLabel => 'সেবা';

  @override
  String get referralProposeGroupLabel => 'গ্রুপ';

  @override
  String get referralProposeImmutableNote =>
      'পাঠানোর পর মঞ্জুরির শর্ত স্থির — ভিন্ন অফারের জন্য নতুন চুক্তি প্রয়োজন';

  @override
  String get referralProposeSubmitting => 'পাঠানো হচ্ছে...';

  @override
  String get referralProposeSubmit => 'প্রস্তাব পাঠান';

  @override
  String referralGrantGift(String name) {
    return 'উপহার: $name';
  }

  @override
  String referralGrantDiscountItem(String name) {
    return 'ছাড়: $name';
  }

  @override
  String referralGrantDiscountGroup(String name) {
    return 'গ্রুপে ছাড়: $name';
  }

  @override
  String referralPartnerCount(int n) {
    return '$nটি চুক্তি';
  }

  @override
  String get referralProposeResultFail => 'প্রস্তাব পাঠানো যায়নি';

  @override
  String get referralRefusal402 =>
      'আপনার দোকান কৌশলগত অংশীদারিত্ব অ্যাপে সাবস্ক্রাইব করা নেই — প্রথমে অ্যাপ স্টোর থেকে সাবস্ক্রাইব করুন';

  @override
  String get referralRefusal403 => 'এই কাজের জন্য আপনার পর্যাপ্ত অনুমতি নেই';

  @override
  String get referralRefusal400 =>
      'প্রস্তাবের তথ্য সঠিক নয় — শর্ত পরীক্ষা করুন, অথবা আপনি নিজের দোকানের সাথে অংশীদারিত্ব প্রস্তাব করছেন না তা নিশ্চিত করুন';

  @override
  String get referralRefusal404 =>
      'এই নম্বরে কোনো দোকান পাওয়া যায়নি, অথবা নির্বাচিত সেবা/গ্রুপ অন্য দোকানের ক্যাটালগে নেই';

  @override
  String get referralRefusal409 =>
      'আপনি সক্রিয় অংশীদারিত্বের সীমা (৩) অতিক্রম করেছেন, অথবা অংশীদারিত্বের অবস্থা পরিবর্তিত হয়েছে';

  @override
  String get referralRefusal503 =>
      'বিলিং সাময়িকভাবে অনুপলব্ধ, পরে আবার চেষ্টা করুন';

  @override
  String get appStoreTitle => 'অ্যাপ স্টোর';

  @override
  String get appStoreSubtitle =>
      'সত্যিকারের অ্যাপ দিয়ে আপনার দোকান বাড়ান, একটি একটি করে';

  @override
  String get appStoreTabMine => 'আমার অ্যাপস';

  @override
  String get appStoreTabAll => 'অ্যাপ স্টোর';

  @override
  String get appStoreDetails => 'বিস্তারিত';

  @override
  String get appStorePerMonth => 'মাসিক';

  @override
  String get appStorePerMonthShort => '/মাস';

  @override
  String get appStoreActive => 'সক্রিয়';

  @override
  String get appStoreTrialing => 'ট্রায়াল';

  @override
  String get appStoreSubscribe => 'এখনই সাবস্ক্রাইব করুন';

  @override
  String get appStoreCancelRenewal => 'নবায়ন বন্ধ করুন';

  @override
  String get appStoreUndoCancel => 'বাতিল পূর্বাবস্থায় ফেরান';

  @override
  String get appStoreConfirmCancel =>
      'এই অ্যাপের নবায়ন বন্ধ করবেন? পরিশোধিত মেয়াদ শেষ না হওয়া পর্যন্ত এটি সক্রিয় থাকবে';

  @override
  String appStoreCartCount(int n) {
    return 'কার্টে $n';
  }

  @override
  String get appStoreCheckout => 'চেকআউট';

  @override
  String get appStoreCheckingOut => 'চেকআউট হচ্ছে...';

  @override
  String get appStoreRefusal402 =>
      'আপনার অ্যাকাউন্টে এখন পেমেন্ট সক্রিয় নেই — সক্রিয় করতে যোগাযোগ করুন';

  @override
  String get appStoreRefusal403 => 'এই ক্রয় সম্পন্ন করার অনুমতি আপনার নেই';

  @override
  String get appStoreRefusal404 =>
      'অনুরোধকৃত প্ল্যান পাওয়া যায়নি — রিফ্রেশ করে আবার চেষ্টা করুন';

  @override
  String get appStoreRefusal409 =>
      'এই অ্যাপ ইতিমধ্যে মালিকানাধীন, অথবা এর অবস্থা ক্রয়ের মাঝে পরিবর্তিত হয়েছে';

  @override
  String get appStoreRefusalGeneric =>
      'ক্রয় সম্পন্ন করা যায়নি, আবার চেষ্টা করুন';

  @override
  String get appStoreCapacityTitle => 'ক্ষমতা';

  @override
  String appStoreCapacityConfirmRemove(String name) {
    return '\"$name\" এর শেষ ইউনিট সরাতে চান? এটি সম্পূর্ণভাবে এর নবায়ন বন্ধ করবে';
  }

  @override
  String get whatsappAssistantTitle => 'এআই সহকারী';

  @override
  String get whatsappAssistantSubtitle =>
      'আপনার পক্ষ থেকে হোয়াটসঅ্যাপে গ্রাহকদের জবাব দেয়, সঠিক মুহূর্তে আপনার প্ল্যান ও তাদের পয়েন্ট সাজেস্ট করে।';

  @override
  String get whatsappAssistantLoadFailed => 'সহকারীর সেটিংস লোড করা যায়নি।';

  @override
  String get whatsappAssistantConfirm => 'নিশ্চিত করুন';

  @override
  String get whatsappAssistantSaveFailed =>
      'সংরক্ষণ করা যায়নি, আবার চেষ্টা করুন।';

  @override
  String get whatsappAssistantToggleTitle => 'সহকারী উত্তর দিচ্ছে';

  @override
  String get whatsappAssistantToggleDesc =>
      'বন্ধ করলে সহকারী সম্পূর্ণভাবে বন্ধ হয়ে যায়, সাবস্ক্রিপশন বাতিল ছাড়াই — যেকোনো সময় আবার চালু করুন।';

  @override
  String get whatsappAssistantToggleConfirmEnableTitle =>
      'এআই সহকারী চালু করবেন?';

  @override
  String get whatsappAssistantToggleConfirmEnableBody =>
      'এটি এখনই আপনার গ্রাহকদের হোয়াটসঅ্যাপে উত্তর দেওয়া শুরু করবে।';

  @override
  String get whatsappAssistantToggleConfirmDisableTitle =>
      'এআই সহকারী বন্ধ করবেন?';

  @override
  String get whatsappAssistantToggleConfirmDisableBody =>
      'এটি সম্পূর্ণভাবে উত্তর দেওয়া বন্ধ করে দেবে, সাবস্ক্রিপশন বাতিল না করেই।';

  @override
  String get whatsappAssistantNotesTitle => 'দোকানের নোট';

  @override
  String get whatsappAssistantNotesDesc =>
      'এখানে যা লিখবেন তা সহকারীকে আপনার দোকান সম্পর্কে অতিরিক্ত তথ্য দিয়ে গ্রাহকদের সেবা দিতে সাহায্য করে।';

  @override
  String get whatsappAssistantWordLimitTitle => 'গ্রাহক বার্তার শব্দসীমা';

  @override
  String get whatsappAssistantWordLimitDesc =>
      'সংক্ষিপ্ত করতে বলার আগে সহকারী গ্রাহকের কাছ থেকে সর্বোচ্চ যত শব্দের বার্তা গ্রহণ করে।';

  @override
  String get whatsappAssistantAutoRegisterTitle =>
      'স্বয়ংক্রিয় যোগাযোগ নিবন্ধন';

  @override
  String get whatsappAssistantAutoRegisterDesc =>
      'আপনার হোয়াটসঅ্যাপে বার্তা পাঠানো যেকোনো নতুন নম্বর স্বয়ংক্রিয়ভাবে একটি প্রকৃত পরিচিতি হিসেবে সংরক্ষিত হয়।';

  @override
  String get whatsappAssistantAutoRegisterConfirmEnableTitle =>
      'স্বয়ংক্রিয় নিবন্ধন চালু করবেন?';

  @override
  String get whatsappAssistantAutoRegisterConfirmEnableBody =>
      'আপনার হোয়াটসঅ্যাপ নম্বরে বার্তা পাঠানো প্রত্যেকে স্বয়ংক্রিয়ভাবে পরিচিতি হিসেবে সংরক্ষিত হবে, এমনকি একটি বার্তা থেকেও।';

  @override
  String get whatsappAssistantAutoRegisterConfirmDisableTitle =>
      'স্বয়ংক্রিয় নিবন্ধন বন্ধ করবেন?';

  @override
  String get whatsappAssistantAutoRegisterConfirmDisableBody =>
      'নতুন নম্বরগুলো আর স্বয়ংক্রিয়ভাবে পরিচিতি হিসেবে সংরক্ষিত হবে না।';

  @override
  String get partnerLoyaltyTitle => 'অংশীদার আনুগত্য';

  @override
  String get partnerLoyaltySubtitle =>
      'আমাদের কাছে নিবন্ধিত অন্য একটি দোকানের সাথে জোট গঠন করুন এবং তার সাবস্ক্রিপশনে সুবিধা দিন';

  @override
  String get partnerLoyaltyCapLabel => 'আপনার বর্তমান সীমা';

  @override
  String get partnerLoyaltyPrefsTitle =>
      'ভিজিট রেকর্ড করার সময় জোট গঠনের চেকবক্স';

  @override
  String get partnerLoyaltyPrefsDesc =>
      'এটি চালু করলে ভিজিট রেকর্ডকারী যেকোনো স্টাফ একই মুহূর্তে জোট গঠন করতে পারবে।';

  @override
  String get partnerLoyaltyGrantTitle => 'জোট গঠন করুন';

  @override
  String get partnerLoyaltyPhoneLabel => 'অংশীদার দোকানের ফোন নম্বর';

  @override
  String get partnerLoyaltyPhoneHintOk => 'এই মাসে তাদের সাথে কোনো জোট নেই';

  @override
  String get partnerLoyaltyPhoneHintAlready =>
      'এই মাসে তাদের সাথে ইতিমধ্যে জোট রয়েছে';

  @override
  String get partnerLoyaltyPhoneHintUnregistered =>
      'এই নম্বরটি আমাদের কাছে নিবন্ধিত দোকান নয়';

  @override
  String get partnerLoyaltyPercentLabel => 'সুবিধার শতাংশ';

  @override
  String partnerLoyaltyCapLine(int p) {
    return 'এখন আপনি সর্বোচ্চ যে শতাংশ দিতে পারবেন: $p%';
  }

  @override
  String get partnerLoyaltyScopeLabel => 'অন্তর্ভুক্ত';

  @override
  String get partnerLoyaltyScopeAll => 'সব';

  @override
  String get partnerLoyaltySubmit => 'জোট গঠন করুন';

  @override
  String get partnerLoyaltySubmitting => 'পাঠানো হচ্ছে…';

  @override
  String get partnerLoyaltyResultSuccess =>
      'জোট গঠিত হয়েছে — দোকানের পরবর্তী নবায়নে স্বয়ংক্রিয়ভাবে প্রয়োগ হবে।';

  @override
  String get partnerLoyaltyResultPartial =>
      'আংশিকভাবে গঠিত হয়েছে — কিছু অ্যাপ প্রত্যাখ্যাত হয়েছে, বিস্তারিত জানতে «লগ» খুলুন।';

  @override
  String get partnerLoyaltyOutcomeGranted => 'সফল';

  @override
  String get partnerLoyaltyOutcomeInvalidPercent => 'সুবিধার শতাংশ সঠিক নয়';

  @override
  String get partnerLoyaltyOutcomeInvalidScope => 'একটি প্রকৃত অ্যাপ বেছে নিন';

  @override
  String get partnerLoyaltyOutcomeOverCap => 'আপনার বর্তমান সীমা অতিক্রম করেছে';

  @override
  String get partnerLoyaltyOutcomeNoAccount =>
      'এই নম্বরটি আমাদের কাছে নিবন্ধিত দোকান নয়';

  @override
  String get partnerLoyaltyOutcomeNotSubscribed =>
      'আপনার বাছাই করা কোনো অ্যাপ ওই দোকানের নেই';

  @override
  String get partnerLoyaltyOutcomeBillingUnavailable =>
      'সম্পন্ন করা যায়নি, আবার চেষ্টা করুন';

  @override
  String get partnerLoyaltyOutcomeAlreadyHasBetterCoupon =>
      'ইতিমধ্যে আরও শক্তিশালী সুবিধা রয়েছে';

  @override
  String get partnerLoyaltyOutcomeCouponExpired => 'সুবিধার মেয়াদ শেষ';

  @override
  String get partnerLoyaltyOutcomeCouponExhausted => 'সুবিধা শেষ হয়ে গেছে';

  @override
  String get partnerLoyaltyOutcomeCouponUnknown => 'অজানা সুবিধা';

  @override
  String get partnerLoyaltyOutcomePlanMismatch =>
      'সুবিধাটি এই অ্যাপের সাথে মেলে না';

  @override
  String get partnerLoyaltyOutcomeCouponDisabled => 'সুবিধা নিষ্ক্রিয়';

  @override
  String get partnerLoyaltyOutcomeCouponScheduled => 'সুবিধা এখনও শুরু হয়নি';

  @override
  String get partnerLoyaltyTabLog => 'লগ';

  @override
  String get partnerLoyaltyTabStats => 'পরিসংখ্যান';

  @override
  String get partnerLoyaltyLogSearchHint => 'শেষ ৪ সংখ্যা দিয়ে খুঁজুন';

  @override
  String get partnerLoyaltyLogFilterAll => 'সব অবস্থা';

  @override
  String get partnerLoyaltyLogFilterOk => 'শুধু সফল';

  @override
  String get partnerLoyaltyLogFilterFail => 'শুধু ব্যর্থ';

  @override
  String get partnerLoyaltyLogEmptyTitle => 'এখনও কোনো জোট নেই';

  @override
  String get partnerLoyaltyLogEmptyDesc => 'আপনার প্রথম জোট এখানে দেখা যাবে।';

  @override
  String get partnerLoyaltyLogReadFailed => 'লগ পড়া যায়নি';

  @override
  String get partnerLoyaltyStatsKpiMonth => 'এই মাসের জোট';

  @override
  String get partnerLoyaltyStatsKpiCap => 'আপনার বর্তমান সীমা';

  @override
  String get partnerLoyaltyStatsKpiCeiling => 'প্ল্যাটফর্মের সর্বোচ্চ সীমা';

  @override
  String get partnerLoyaltyStatsLadderTitle => 'সিঁড়িতে আপনার অবস্থান';

  @override
  String partnerLoyaltyStatsLadderNote(int n, int left, int p) {
    return 'এই মাসে $nটি জোট — $p% স্তরে পৌঁছাতে আরও $leftটি বাকি';
  }

  @override
  String partnerLoyaltyStatsLadderAtTop(int n) {
    return 'এই মাসে $nটি জোট — আপনি সর্বোচ্চ স্তরে আছেন';
  }

  @override
  String partnerLoyaltyStatsCeilingNote(int p) {
    return 'প্ল্যাটফর্মের সর্বোচ্চ সীমা $p% — কোনো দোকান কখনো এটি অতিক্রম করে না';
  }

  @override
  String get partnerLoyaltyStatsChartTitle => 'গত ৬ মাসের জোটের সংখ্যা';

  @override
  String get partnerLoyaltyReadFailedTitle => 'আপনার তথ্য পড়া যায়নি';

  @override
  String get partnerLoyaltyReadFailedDesc => 'কিছুক্ষণ পর আবার চেষ্টা করুন।';

  @override
  String get shopReadFailed => 'আপনার দোকানের সূচক পড়া যায়নি';

  @override
  String get shopMultiBranchTitle => 'একটি শাখা বেছে নিন';

  @override
  String get shopMultiBranchDesc =>
      'আপনার একাধিক শাখা আছে — সূচক দেখতে একটি বেছে নিন।';

  @override
  String get shopEmptyBranchTitle => 'এই শাখার জন্য এখনও কোনো তথ্য নেই';

  @override
  String get shopRetentionTitle => 'আপনার গ্রাহক ফিরে আসার হার';

  @override
  String get shopRetentionMutedNote => 'এটি গণনা করার জন্য পর্যাপ্ত ভিজিট নেই।';

  @override
  String get shopRetentionBrandNew =>
      'গ্রাহক ফিরে আসার হার দেখতে প্রথম ভিজিট নিবন্ধন করুন।';

  @override
  String get shopRegisterFirstVisit => 'প্রথম ভিজিট নিবন্ধন করুন';

  @override
  String get shopRetentionPrefix10 => 'প্রতি ১০ জন গ্রাহকের মধ্যে,';

  @override
  String get shopRetentionSuffix => 'ফিরে আসেন';

  @override
  String get shopOneCustomer => 'একজন গ্রাহক আপনাকে ভিজিট করেছেন';

  @override
  String shopNCustomers(int n) {
    return '$n জন গ্রাহক আপনাকে ভিজিট করেছেন';
  }

  @override
  String shopRetentionSmallPrefix(String base) {
    return '$base, তাদের মধ্যে';
  }

  @override
  String shopOverNMonths(int n) {
    return '$n মাসে';
  }

  @override
  String get shopUnlimited => 'সীমাহীন';

  @override
  String get shopTileSentToday => 'আজ পাঠানো হয়েছে';

  @override
  String get shopTileWaiting => 'অপেক্ষায়';

  @override
  String get shopTileCeilingRemaining => 'আজ বাকি আছে';

  @override
  String get shopNextStepLabel => 'পরবর্তী পদক্ষেপ';

  @override
  String get shopNotNow => 'এখন না';

  @override
  String get shopDeckUrgent => 'জরুরি';

  @override
  String get shopDeckWeek => 'এই সপ্তাহ';

  @override
  String get shopDeckOpportunities => 'সুযোগ';

  @override
  String get shopComputedNow => 'এখনই গণনা করা হয়েছে';

  @override
  String shopComputedHoursAgo(int n) {
    return '$n ঘণ্টা আগে গণনা করা হয়েছে';
  }

  @override
  String get shopStale => 'পুরনো';

  @override
  String get shopRefreshAction => 'রিফ্রেশ';

  @override
  String get shopComputingTitle => 'আপনার সূচক গণনা করা হচ্ছে';

  @override
  String get shopComputeLoading => 'গণনা করা হচ্ছে…';

  @override
  String get shopComputeAction => 'এখনই গণনা করুন';

  @override
  String get shopAtRiskTitle => 'চলে যাওয়ার পথে থাকা গ্রাহক';

  @override
  String get shopAtRiskMutedNote => 'পর্যাপ্ত তথ্য নেই।';

  @override
  String get shopAtRiskAllGood => 'এখন কোনো বিলম্বিত গ্রাহক নেই — সব ঠিক আছে';

  @override
  String get shopWaNotConnected =>
      'আপনার দোকানের হোয়াটসঅ্যাপ এখনও সংযুক্ত নয়';

  @override
  String get shopWaNotVerified =>
      'আপনার দোকানের হোয়াটসঅ্যাপ নম্বর এখনও যাচাই করা হয়নি';

  @override
  String get shopCeilingReached => 'আজকের বার্তার সীমায় পৌঁছেছেন';

  @override
  String shopDaysOverdue(int n) {
    return '$n দিন বিলম্বিত';
  }

  @override
  String get shopAtRiskCta => 'ফিরিয়ে আনার প্রচারণা পাঠান';

  @override
  String get shopAiImpactTitle => 'হোয়াটসঅ্যাপ এআই সহায়কের প্রভাব';

  @override
  String get shopAiConversations => 'কথোপকথন';

  @override
  String get shopAiBookings => 'বুকিং';

  @override
  String get shopAiUpsellRate => 'অতিরিক্ত অফার গ্রহণ';

  @override
  String get shopWeekMutedTitle => 'এই সপ্তাহের ভিজিট';

  @override
  String get shopWeekMutedNote => 'পর্যাপ্ত তথ্য নেই।';

  @override
  String get shopNewReturningMutedTitle => 'নতুন বনাম ফিরে আসা গ্রাহক';

  @override
  String get shopNewReturningMutedNote => 'পর্যাপ্ত তথ্য নেই।';

  @override
  String get shopBranchCompareTitle => 'শাখা তুলনা';

  @override
  String get shopBranchCompareMutedNote =>
      'তুলনা করতে অন্তত দুটি শাখা প্রয়োজন।';

  @override
  String get shopStaffCompareTitle => 'কর্মী তুলনা';

  @override
  String get shopStaffCompareMutedNote =>
      'তুলনা করতে অন্তত দুইজন কর্মী প্রয়োজন।';

  @override
  String get shopWeekTitle => 'এই সপ্তাহের ভিজিট';

  @override
  String get shopNewReturningTitle => 'নতুন বনাম ফিরে আসা';

  @override
  String get shopNewLabel => 'নতুন:';

  @override
  String get shopReturningLabel => 'ফিরে আসা:';

  @override
  String get shopServicesTitle => 'আপনার সেবা';

  @override
  String get shopServicesMutedNote => 'পর্যাপ্ত তথ্য নেই।';

  @override
  String get shopMessageFlowTitle => 'রিমাইন্ডার বার্তার প্রভাব';

  @override
  String get shopMutedMessageFlowNote => 'পর্যাপ্ত তথ্য নেই।';

  @override
  String get shopHoldoutTitle => 'বার্তা পাঠানো বনাম না পাঠানো তুলনা';

  @override
  String get shopMutedHoldoutNote => 'এখনও পরিমাপ করা হচ্ছে।';

  @override
  String shopReturnedAfterReminder(int visits, int days) {
    return 'রিমাইন্ডারের পর $days দিনে $visitsটি ভিজিট';
  }

  @override
  String shopOptOutRate(String p) {
    return '$p% বার্তা বন্ধ করতে বলেছেন';
  }

  @override
  String get shopHoldoutNoMessages => 'বার্তা ছাড়া';

  @override
  String get shopHoldoutReached => 'বার্তা পাঠানো হয়েছে';

  @override
  String get shopHoldoutOff =>
      'বার্তার প্রভাব পরিমাপ বন্ধ আছে — আপনার সব গ্রাহকের কাছে সবকিছু পৌঁছায়, তাই তুলনা করার কোনো দল নেই।';

  @override
  String shopHoldoutMeasuring(int min, int need) {
    return 'আমরা এখনও আপনার দোকানে বার্তার প্রভাব পরিমাপ করছি — ছোট দলে $need-এর মধ্যে $min জন।';
  }

  @override
  String shopTodayRetrying(int n) {
    return '$nটি বার্তা এখনও বের হওয়ার চেষ্টা করছে';
  }

  @override
  String get shopTrendUp => 'উন্নতি হচ্ছে';

  @override
  String get shopTrendDown => 'কমছে';

  @override
  String shopRetentionSincePeriods(int n) {
    return '$n সময়কাল ধরে';
  }

  @override
  String get shopAtLeastSuffix => ' — অন্তত';

  @override
  String get shopRegisterFirstVisitArrow => 'প্রথম ভিজিট নথিভুক্ত করুন ←';

  @override
  String get shopWeekNoCompare => 'তুলনা করার মতো এখনও একটি পূর্ণ সপ্তাহ নেই';

  @override
  String shopNextStepAlso(String msg) {
    return 'আরও: $msg';
  }

  @override
  String shopBranchCompareUnassigned(int n) {
    return '$nটি ভিজিটে কোনো শাখা নির্ধারিত নেই — কোনো শাখার জন্য গণনা হয়নি।';
  }

  @override
  String get shopBranchCompareNeedTwo =>
      'এখনও শাখাগুলো তুলনা করা হয় না — বাস্তব ভিজিটসহ দুই বা তার বেশি শাখা দরকার।';

  @override
  String get shopBranchCompareNeedSecond =>
      'এখন পর্যন্ত একটি সক্রিয় শাখা — তুলনার জন্য বাস্তব ভিজিটসহ দ্বিতীয় শাখা দরকার।';

  @override
  String get shopBranchCompareTooShort =>
      'এখনও শাখাগুলোর ক্রম নির্ধারণ করা হয় না — সময়কাল খুব ছোট, আর এখন তুলনা করলে নতুনটির প্রতি অন্যায় হবে।';

  @override
  String shopStaffCompareUnassigned(int n) {
    return '$nটি ভিজিটে কোনো কর্মী নির্ধারিত নেই — কারো জন্য গণনা হয়নি।';
  }

  @override
  String get shopStaffCompareNeedTwo =>
      'এখনও কর্মীদের তুলনা করা হয় না — যুক্ত ভিজিটসহ দুই বা তার বেশি কর্মী দরকার।';

  @override
  String get shopStaffCompareNeedSecond =>
      'এখন পর্যন্ত একজন কর্মী যুক্ত — তুলনার জন্য বাস্তব ভিজিটসহ দ্বিতীয় জন দরকার।';

  @override
  String get shopStaffCompareTooShort =>
      'এখনও কর্মীদের ক্রম নির্ধারণ করা হয় না — সময়কাল খুব ছোট, আর এখন তুলনা করলে নতুনটির প্রতি অন্যায় হবে।';
}
