// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Hausa (`ha`).
class SHa extends S {
  SHa([String locale = 'ha']) : super(locale);

  @override
  String get appName => 'Raje3';

  @override
  String get ok => 'To';

  @override
  String get cancel => 'Soke';

  @override
  String get save => 'Ajiye';

  @override
  String get close => 'Rufe';

  @override
  String get back => 'Baya';

  @override
  String get next => 'Gaba';

  @override
  String get done => 'An gama';

  @override
  String get loading => 'Ana lodawa...';

  @override
  String get retry => 'Sake gwadawa';

  @override
  String get error => 'An samu kuskure';

  @override
  String get success => 'An yi nasara';

  @override
  String get search => 'Bincike';

  @override
  String get login => 'Shiga';

  @override
  String get logout => 'Fita';

  @override
  String get homeDashboardTitle => 'Allon bayanai';

  @override
  String get homeShopSectionLabel => 'Shagona';

  @override
  String get homeLoadErrorTitle => 'An kasa lodawa';

  @override
  String get homeLoadErrorMessage => 'An kasa loda bayanan yau. Sake gwadawa.';

  @override
  String get homeTodaySectionTitle => 'Yau';

  @override
  String get homeStatSent => 'An aika';

  @override
  String get homeStatWaiting => 'Ana jira';

  @override
  String get homeStatRetrying => 'Ana sake gwadawa';

  @override
  String get homeDashboardComputing =>
      'Ana lissafin bayanan shagonka yanzu — sabunta bayan wani lokaci.';

  @override
  String get homeDashboardSectionTitle => 'Bayanan shago';

  @override
  String get homeDashboardEmpty => 'Babu isassun bayanai tukuna.';

  @override
  String get themeDarkMode => 'Yanayin duhu';

  @override
  String get themeLightMode => 'Yanayin haske';

  @override
  String get validatorFieldRequiredGeneric => 'Wannan filin yana bukata';

  @override
  String validatorFieldRequiredNamed(String field) {
    return 'Ana bukatar $field';
  }

  @override
  String get validatorEmailRequired => 'Ana bukatar imel';

  @override
  String get validatorEmailInvalid => 'Adireshin imel ba daidai ba ne';

  @override
  String get validatorPhoneRequired => 'Ana bukatar lambar waya';

  @override
  String get validatorPhoneInvalid =>
      'Lambar waya ba daidai ba ne — dole ta fara da 05';

  @override
  String get validatorPasswordRequired => 'Ana bukatar kalmar sirri';

  @override
  String get validatorPasswordTooShort =>
      'Kalmar sirri dole ta zama akalla haruffa 8';

  @override
  String get validatorPasswordNeedsUppercase =>
      'Kalmar sirri dole ta ɗunshi babban harafi';

  @override
  String get validatorPasswordNeedsLowercase =>
      'Kalmar sirri dole ta ɗunshi ƙaramin harafi';

  @override
  String get validatorPasswordNeedsDigit => 'Kalmar sirri dole ta ɗunshi lamba';

  @override
  String get validatorConfirmPasswordFieldName => 'Tabbatar da kalmar sirri';

  @override
  String get validatorPasswordMismatch => 'Kalmomin sirri ba su dace ba';

  @override
  String get validatorOtpRequired => 'Ana bukatar lambar tabbatarwa';

  @override
  String get validatorOtpLength => 'Lambar tabbatarwa dole ta zama lambobi 6';

  @override
  String get validatorOtpDigitsOnly =>
      'Lambar tabbatarwa dole ta ɗunshi lambobi kawai';

  @override
  String get validatorNameRequired => 'Ana bukatar suna';

  @override
  String get validatorNameTooShort => 'Suna dole ya zama akalla haruffa 2';

  @override
  String get validatorNameTooLong => 'Suna bai kamata ya wuce haruffa 100 ba';

  @override
  String get validatorNameInvalidChars =>
      'Suna yana ɗauke da haruffan da ba a yarda da su ba';

  @override
  String get validatorGenericFieldName => 'Wannan filin';

  @override
  String validatorMinLengthNamed(String field, int minLength) {
    return '$field dole ya zama akalla haruffa $minLength';
  }

  @override
  String validatorMaxLengthNamed(String field, int maxLength) {
    return '$field bai kamata ya wuce haruffa $maxLength ba';
  }

  @override
  String get validatorGenericValueName => 'Ƙimar';

  @override
  String validatorNotANumberNamed(String field) {
    return '$field dole ya zama lamba';
  }

  @override
  String validatorMinValueNamed(String field, String min) {
    return '$field dole ya zama akalla $min';
  }

  @override
  String validatorMaxValueNamed(String field, String max) {
    return '$field bai kamata ya wuce $max ba';
  }

  @override
  String get validatorUrlRequired => 'Ana bukatar hanyar haɗi';

  @override
  String get validatorUrlInvalid => 'Hanyar haɗi ba daidai ba ce';

  @override
  String get urlHelperUnavailable => 'Hanyar haɗin ba ta samuwa ba';

  @override
  String get urlHelperOpenFailed => 'An kasa buɗe hanyar haɗin';

  @override
  String get routerScreenNotOnMobileYet =>
      'Wannan allon ba a samu shi ba tukuna a manhajar wayar hannu.';

  @override
  String get kbHintNoEntry => 'Babu bayani game da wannan tukuna.';

  @override
  String get assistantChatTitle => 'Mataimaki';

  @override
  String get assistantInputHint => 'Rubuta tambayarka...';

  @override
  String get assistantSend => 'Aika';

  @override
  String get assistantUnavailable => 'Mataimaki ba ya samuwa a yanzu.';

  @override
  String get assistantPreparing => 'Ana shirya mataimaki...';

  @override
  String get assistantRetryDownload => 'Sake gwadawa';

  @override
  String get assistantSpeak => 'Saurari amsa';

  @override
  String get assistantStopSpeaking => 'Dakatar da magana';

  @override
  String get assistantActionUnavailable => 'Ba za ka iya yin wannan yanzu ba.';

  @override
  String get assistantConfirm => 'Tabbatar';

  @override
  String get assistantCancel => 'Soke';

  @override
  String get assistantReplySettingsTooltip => 'Saitunan amsa';

  @override
  String get assistantReplyModeTitle => 'Yadda mataimaki ke amsawa';

  @override
  String get assistantReplyModeSubtitle =>
      'Ya shafi kowace amsa, ko da ka tambaya da murya';

  @override
  String get assistantReplyModeVoice => 'Murya';

  @override
  String get assistantReplyModeText => 'Rubutu';

  @override
  String get authLoginSubtitle => 'Shiga don ci gaba';

  @override
  String get authPhoneLabel => 'Lambar wayar hannu';

  @override
  String get authPasswordLabel => 'Kalmar sirri';

  @override
  String get authNoShopYetLabel => 'Ba ku da shago tukuna?';

  @override
  String get authOpenNewShopCta => 'Buɗe sabon shago';

  @override
  String get authOpenShopTitle => 'Buɗe sabon shago';

  @override
  String get authSignupSubtitle => 'Matakai uku kawai don buɗe shagonka';

  @override
  String get authShopNameLabel => 'Sunan shago';

  @override
  String get authOwnerNameLabel => 'Sunanka (na son rai)';

  @override
  String get authAlreadyHaveShopCta => 'Kana da shago tuni? Shiga';

  @override
  String get authOpenShopCta => 'Buɗe shago';

  @override
  String get authVerifyPhoneTitle => 'Tabbatar da lambar wayar hannu';

  @override
  String authVerifyCodeSentTo(String phone) {
    return 'Mun aika lambar tabbatarwa zuwa $phone';
  }

  @override
  String get authVerifying => 'Ana tabbatarwa...';

  @override
  String get authConfirmCta => 'Tabbatar';

  @override
  String get authResendCodeCta => 'Sake aika lambar';

  @override
  String get authSendCodeCta => 'Aika lambar';

  @override
  String get authCodeSendFailedFallback => 'An kasa aika lambar.';

  @override
  String get authOtpIncorrectFallback => 'Lambar tabbatarwa ba daidai ba ce.';

  @override
  String get visitCatalogueLoadErrorFallback =>
      'An kasa loda ayyuka. Ja ƙasa don sake gwadawa.';

  @override
  String get visitEnterCustomerPhone => 'Shigar da lambar wayar abokin ciniki';

  @override
  String get visitSelectAtLeastOneService => 'Zaɓi aƙalla sabis ɗaya';

  @override
  String get visitSavedMessage => 'An yi rikodin ziyarar.';

  @override
  String get visitSaveErrorFallback => 'An kasa yin rikodin ziyarar.';

  @override
  String get visitSaveErrorNetworkFallback =>
      'An kasa yin rikodin ziyarar. Duba haɗin intanet ɗinka sannan ka sake gwadawa.';

  @override
  String get visitTitle => 'Yin rikodin ziyara';

  @override
  String get visitCustomerSectionTitle => 'Abokin ciniki';

  @override
  String get visitCustomerPhoneFieldLabel => 'Lambar wayar abokin ciniki';

  @override
  String get visitPlateFieldLabel => 'Lambar farantin mota';

  @override
  String get visitPlateRequired =>
      'Shigar da lambar farantin da ta dace (aƙalla harafi ɗaya da lamba ɗaya)';

  @override
  String visitKnownVehicle(String name) {
    return 'Sanannen mota: $name';
  }

  @override
  String get visitNewVehicle => 'Sabuwar mota';

  @override
  String visitKnownCustomer(String name) {
    return 'Sanannen abokin ciniki: $name';
  }

  @override
  String get visitNewCustomer => 'Sabon abokin ciniki';

  @override
  String get visitServicesSectionTitle => 'Ayyuka';

  @override
  String get visitNoServicesYet => 'Babu ayyuka tukuna.';

  @override
  String get visitNoteSectionTitle => 'Bayani (na son rai)';

  @override
  String get visitSaveButtonLabel => 'Ajiye ziyarar';

  @override
  String get navAppsLabel => 'Kantin app';

  @override
  String get navHomeLabel => 'Gida';

  @override
  String get navAccountLabel => 'Asusuna';

  @override
  String get homeGreetingMorning => 'Ina kwana';

  @override
  String get homeGreetingEvening => 'Ina yamma';

  @override
  String homeGreetingMorningNamed(String name) {
    return 'Ina kwana, $name';
  }

  @override
  String homeGreetingEveningNamed(String name) {
    return 'Ina yamma, $name';
  }

  @override
  String get homeAppsSectionTitle => 'Aikace-aikacenka';

  @override
  String get homeFeaturedStartNow => 'Fara yanzu';

  @override
  String get homeEmptyStateTitle => 'Babu wani aiki da ake samu tukuna';

  @override
  String get homeEmptyStateBody => 'Tuntuɓi mai shago don ƙara izininka.';

  @override
  String get appsScreenTitle => 'Manhajojina';

  @override
  String get appsScreenHint =>
      'Danna alamar allura don liƙa manhaja a wurin na 5 na sandar ƙasa';

  @override
  String get appsPinnedBadge => 'An liƙa a sanda';

  @override
  String get appsPinAction => 'Liƙa nan';

  @override
  String get homeLauncherEmptyTitle => 'Babu manhaja da ake da su';

  @override
  String get homeLauncherEmptyMessage =>
      'Tuntuɓi tallafi don kunna manhaja ga shagonka';

  @override
  String get accountScreenTitle => 'Asusuna';

  @override
  String get accountPhoneLabel => 'Lambar waya';

  @override
  String get accountLogoutAction => 'Fita';

  @override
  String get accountLogoutConfirmTitle => 'Fita';

  @override
  String get accountLogoutConfirmMessage => 'Kana son fita daga asusunka?';

  @override
  String get notificationsUnavailable => 'Sanarwa ba su samuwa tukuna';

  @override
  String get notificationsTitle => 'Sanarwa';

  @override
  String get notificationsEmptyState => 'Babu sanarwa tukuna';

  @override
  String get notificationsAgoJustNow => 'Yanzu';

  @override
  String notificationsAgoMinutes(int n) {
    return 'Mintuna $n da suka wuce';
  }

  @override
  String notificationsAgoHours(int n) {
    return 'Awanni $n da suka wuce';
  }

  @override
  String get notificationsAgoYesterday => 'Jiya';

  @override
  String notificationsAgoDays(int n) {
    return 'Kwanaki $n da suka wuce';
  }

  @override
  String get accountPageTitle => 'Asusuna';

  @override
  String get accountLegalSectionTitle => 'Shari\'a';

  @override
  String get accountTermsRow => 'Sharuɗɗa da Ka\'idoji';

  @override
  String get accountPrivacyRow => 'Manufar Sirri';

  @override
  String get accountSignOutRow => 'Fita';

  @override
  String get accountSignOutConfirmTitle => 'Fita?';

  @override
  String get accountSignOutConfirmBody =>
      'Za ka buƙaci shiga kuma don ci gaba.';

  @override
  String get accountSignOutCancel => 'Soke';

  @override
  String get accountSignOutConfirm => 'Fita';

  @override
  String get accountNameFieldHint => 'Sunanka';

  @override
  String get accountSaveNameFailed => 'An kasa ajiye sunan, sake gwadawa.';

  @override
  String get accountShopSectionTitle => 'Shagona';

  @override
  String get accountShopIdentityRow => 'Shagona';

  @override
  String get shopIdentityPageTitle => 'Shagona';

  @override
  String get shopIdentityVehicleTitle => 'Aiki akan motoci';

  @override
  String get shopIdentityVehicleDesc =>
      'Yana kunna filin lambar farantin mota a allon rubuta ziyara na wannan shago.';

  @override
  String get shopIdentityVehicleSaveFailed => 'An kasa ajiyewa, sake gwadawa.';

  @override
  String get shopIdentityBrandTitle => 'Sunan shagonka da alamarsa';

  @override
  String get shopIdentityCustomerPagePreview =>
      'Wannan shine abin da abokin cinikinka yake gani';

  @override
  String get shopIdentityNameLabel => 'Sunan shago';

  @override
  String get shopIdentityUploadLogo => 'Loda alama';

  @override
  String get shopIdentityChangeLogo => 'Canza alama';

  @override
  String get shopIdentityRemoveLogo => 'Cire';

  @override
  String get shopIdentityColorLabel => 'Launin shagonka';

  @override
  String get shopIdentityResetColor => 'Yi amfani da tsoho';

  @override
  String get shopIdentitySave => 'Ajiye';

  @override
  String get shopIdentityDefaultName => 'Shagonka';

  @override
  String get shopIdentityLogoPickFailed =>
      'An kasa karanta hoton, gwada wani hoto.';

  @override
  String get shopIdentityInvalidColor =>
      'Shigar da launi mai kyau, kamar #B08A3E';

  @override
  String get shopIdentitySaveFailed => 'An kasa ajiyewa, sake gwadawa.';

  @override
  String get shopIdentitySaved => 'An ajiye.';

  @override
  String get shopIdentityBranchesRow => 'Rassa';

  @override
  String get branchesPageTitle => 'Rassa';

  @override
  String get branchesAddBranch => 'Ƙara reshe';

  @override
  String get branchesActiveChip => 'Yana aiki';

  @override
  String get branchesClosedChip => 'An rufe';

  @override
  String get branchesLoadFailed =>
      'An kasa loda rassa, ja ƙasa don sake gwadawa.';

  @override
  String get branchesLimitReached =>
      'Tsarinka na yanzu ba ya barin ƙarin reshe.';

  @override
  String get branchesNameRequired => 'Ana bukatar sunan reshe';

  @override
  String get branchesNameLabel => 'Sunan reshe';

  @override
  String get branchesCityLabel => 'Birni';

  @override
  String get branchesLocationHint =>
      'Manna hanyar haɗin wuri daga Google Maps (na zaɓi a reshe na farko, dole daga na biyu)';

  @override
  String get branchesMapsLinkLabel => 'Hanyar haɗin Google Maps';

  @override
  String get branchesMapsLinkInvalid =>
      'An kasa karanta wannan hanyar haɗi — tabbatar cewa hanyar haɗin Google Maps ce.';

  @override
  String get branchesMapsLinkShort =>
      'Manna cikakkiyar hanyar haɗin Google Maps, ba gajarta ba.';

  @override
  String get branchesLocationRequired =>
      'Saita wurin reshe akan taswira — dole daga reshe na biyu.';

  @override
  String get branchesSaveFailed => 'An kasa ajiyewa, sake gwadawa.';

  @override
  String get branchesStatusLabel => 'Matsayin reshe';

  @override
  String get branchesMainCannotClose =>
      'Babban reshe ba ya rufewa — za ka iya canza sunansa kawai.';

  @override
  String get branchesWhatsappTitle => 'Haɗin WhatsApp';

  @override
  String get branchesWhatsappNotStarted => 'Ba a haɗa ba tukuna';

  @override
  String get branchesWhatsappConnected => 'An haɗa kuma yana aiki';

  @override
  String get branchesWhatsappCannotSend => 'An haɗa amma akwai matsalar aikawa';

  @override
  String get branchesTeamTitle => 'Ƙungiyar reshe';

  @override
  String get branchesTeamEmpty => 'Babu memba a wannan reshe tukuna.';

  @override
  String get branchesAddMember => 'Ƙara memba';

  @override
  String get branchesMemberNameLabel => 'Sunan ma\'aikaci';

  @override
  String get branchesMemberPhoneLabel => 'Lambar wayarsa';

  @override
  String get branchesMemberPasswordLabel => 'Kalmar sirrin shigarsa';

  @override
  String get branchesMemberRoleLabel => 'Matsayi';

  @override
  String get branchesRoleOperator => 'Ma\'aikacin filin';

  @override
  String get branchesRoleSupervisor => 'Mai kula da canjin aiki';

  @override
  String get branchesRoleMarketer => 'Shugaban tallace-tallace';

  @override
  String get branchesRoleManager => 'Manaja';

  @override
  String get branchesSeatLimit =>
      'Tsarinka na yanzu ba ya barin ƙarin ma\'aikaci.';

  @override
  String get branchesHireFailed => 'An kasa ƙara ma\'aikaci, sake gwadawa.';

  @override
  String get branchesVisibleAllHint => 'Yana ganin kowanne reshe';

  @override
  String branchesVisibleSomeHint(int count) {
    return 'Yana ganin rassa $count';
  }

  @override
  String get branchesEditMember => 'Gyara ma\'aikaci';

  @override
  String get branchesMemberStopped => 'An dakatar';

  @override
  String get branchesMemberStationLabel => 'Wanne reshe yake aiki';

  @override
  String get branchesMemberVisibilityLabel => 'Wadanne rassa zai iya gani';

  @override
  String get branchesVisibilityOwnOnly => 'Reshensa kawai';

  @override
  String get branchesVisibilitySome => 'Rassan da aka zaɓa';

  @override
  String get branchesVisibilityAll => 'Kowanne reshe';

  @override
  String get branchesWorkingHours => 'Sa\'o\'in aiki';

  @override
  String get branchesStopMember => 'Dakatar da ma\'aikaci';

  @override
  String get branchesStopMemberTitle => 'Dakatar da wannan ma\'aikaci?';

  @override
  String branchesStopMemberBody(String name) {
    return '$name zai rasa damar shiga app nan take. Tarihin ziyararsa zai ci gaba da ajiye.';
  }

  @override
  String get branchesStopMemberConfirm => 'Dakatar';

  @override
  String get branchesReactivateMember => 'Sake kunnawa';

  @override
  String get branchesRehireRequired =>
      'Wannan ma\'aikaci an dakatar da shi gaba daya — sake kunnawa yana bukatar sake daukar sa aiki, ba kawai kunnawa ba.';

  @override
  String get branchesHoursSaved => 'An ajiye sa\'o\'in aiki.';

  @override
  String get branchesHoursExceedsShop =>
      'Wadannan sa\'o\'i sun fi na shago kansa fadi — gyara su.';

  @override
  String get branchesHoursHint =>
      'Idan ba ka canza komai ba, zai bi sa\'o\'in shago kansa kai tsaye.';

  @override
  String get branchesHoursClear => 'Mayar da sa\'o\'in shago na asali';

  @override
  String get branchesDayMonday => 'Litinin';

  @override
  String get branchesDayTuesday => 'Talata';

  @override
  String get branchesDayWednesday => 'Laraba';

  @override
  String get branchesDayThursday => 'Alhamis';

  @override
  String get branchesDayFriday => 'Jumma\'a';

  @override
  String get branchesDaySaturday => 'Asabar';

  @override
  String get branchesDaySunday => 'Lahadi';

  @override
  String get branchesDayClosed => 'A rufe';

  @override
  String get accountLanguageSectionTitle => 'Harshe';

  @override
  String get accountLanguageRow => 'Harshen aikace-aikace';

  @override
  String get accountLanguageSheetTitle => 'Zaɓi harshen aikace-aikace';

  @override
  String get accountSecuritySectionTitle => 'Tsaro';

  @override
  String get accountChangePasswordRow => 'Canza kalmar sirri';

  @override
  String get accountChangePasswordFailed =>
      'An kasa canza kalmar sirri, sake gwadawa.';

  @override
  String get accountChangePasswordSuccess => 'An canza kalmar sirri.';

  @override
  String get accountCurrentPasswordLabel => 'Kalmar sirri ta yanzu';

  @override
  String get accountNewPasswordLabel => 'Sabuwar kalmar sirri';

  @override
  String get accountConfirmNewPasswordLabel =>
      'Tabbatar da sabuwar kalmar sirri';

  @override
  String get branchesIncreaseCapacity => 'Ƙara ƙarfin';

  @override
  String get accountBillingSectionTitle => 'Kuɗi';

  @override
  String get accountBillingRow => 'Biyan kuɗi da lissafin kuɗi';

  @override
  String get billingPageTitle => 'Kuɗi';

  @override
  String get billingLoadFailed =>
      'An kasa loda bayanan kuɗi. Ja ƙasa don sake gwadawa.';

  @override
  String get billingAllGood =>
      'Kuɗin ka yana lafiya — babu abin da ke bukatar kulawarka yanzu.';

  @override
  String get billingPastDue =>
      'Kana da lissafin da ya wuce lokacin biya — biya don guje wa dakatar da ayyukanka.';

  @override
  String get billingPaymentConfirming =>
      'Mun samu ƙoƙarin biyanka kuma muna tabbatar da shi yanzu — wannan na iya ɗaukar har zuwa mintuna 20.';

  @override
  String get billingUsageSectionTitle => 'Amfaninka';

  @override
  String get billingUsageStaffSeats => 'Wuraren ma\'aikata';

  @override
  String get billingUsageBranches => 'Rassa';

  @override
  String get billingUsageUnlimited => 'Babu iyaka';

  @override
  String get billingMyAppsSectionTitle => 'Aikace-aikacen da na yi biyan kuɗi';

  @override
  String get billingStatusActive => 'Aiki';

  @override
  String get billingStatusStopping => 'Zai tsaya';

  @override
  String billingRenewsOn(Object date) {
    return 'Zai sabunta a $date';
  }

  @override
  String get billingStopRenewal => 'Dakatar da sabuntawa';

  @override
  String get billingUndoStopRenewal => 'Soke dakatarwa';

  @override
  String get billingRenewNow => 'Sabunta yanzu';

  @override
  String get billingActionFailed =>
      'An kasa kammala wannan aikin. Sake gwadawa.';

  @override
  String get billingRenewalPreviewSectionTitle => 'Duban sabuntawa na gaba';

  @override
  String billingRenewalPreviewNextChargeOn(Object date) {
    return 'Karɓar kuɗi na gaba a $date';
  }

  @override
  String get billingRenewalPreviewNoDate =>
      'Babu ranar sabuntawa da za ta zo tukuna.';

  @override
  String get billingRenewalPreviewSubtotal => 'Jimlar farko';

  @override
  String get billingRenewalPreviewSavings => 'Ajiyayye';

  @override
  String get billingRenewalPreviewTax => 'Haraji';

  @override
  String get billingRenewalPreviewTotal => 'Jimla';

  @override
  String get billingInvoicesSectionTitle => 'Lissafin kuɗi';

  @override
  String get billingInvoicesEmpty => 'Babu lissafin kuɗi tukuna.';

  @override
  String get billingInvoiceStatusPaid => 'An biya';

  @override
  String get billingInvoiceStatusOpen => 'Ba a biya ba';

  @override
  String get billingInvoiceStatusPartiallyPaid => 'An biya wani ɓangare';

  @override
  String get billingInvoiceStatusVoid => 'An soke';

  @override
  String get billingInvoiceStatusUncollectible => 'Ba a iya karɓa ba';

  @override
  String get billingInvoiceStatusDraft => 'Zane-zane';

  @override
  String get billingPayNow => 'Biya yanzu';

  @override
  String get billingPayLinkFailed =>
      'An kasa ƙirƙirar hanyar biya. Sake gwadawa.';

  @override
  String get paymentPageLoadFailed =>
      'An kasa loda shafin biya. Duba haɗin intanet ɗinka sannan ka sake gwadawa.';

  @override
  String get billingCancelConfirmTitle => 'Dakatar da sabuntawa?';

  @override
  String get billingCancelConfirmBody =>
      'Ayyukan za su ci gaba har zuwa ƙarshen wannan lokacin, sannan ba za su sabunta ba.';

  @override
  String get billingCancelConfirmAction => 'Dakatar da sabuntawa';

  @override
  String get visitOfferApplyLabel =>
      'Yi amfani da wannan tayin a wannan ziyarar';

  @override
  String visitPointsRedeemCost(Object cost) {
    return 'maki $cost';
  }

  @override
  String get visitPointsOneBenefitOnly =>
      'Fa’ida ɗaya kawai a kowace ziyara — zaɓar maki yana soke tayin atomatik.';

  @override
  String visitPointsRedeemedMessage(Object name) {
    return 'An musanya $name ✓';
  }

  @override
  String visitPointsChosenMessage(Object name) {
    return 'An zaɓa: $name — za a yi amfani da shi maimakon tayin yayin ajiyewa';
  }

  @override
  String get visitPointsRedeemFailed => 'An kasa musanyawa. Sake gwadawa.';

  @override
  String readBillingActiveCount(Object count) {
    return 'Kana da rajista $count masu aiki.';
  }

  @override
  String get readBillingNone => 'Ba ka da wata rajista mai aiki a yanzu.';

  @override
  String readBillingRenewsSoon(Object date) {
    return 'Sabuntawa na gaba ranar $date ne.';
  }

  @override
  String get readBillingFailed =>
      'An kasa samun matsayin lissafin kuɗi yanzu, sake gwadawa.';

  @override
  String readBranchCount(Object count) {
    return 'Kana da rassa $count.';
  }

  @override
  String get readBranchFailed =>
      'An kasa samun yawan rassa yanzu, sake gwadawa.';

  @override
  String get readVehicleTrackingOn => 'Bin diddigin motoci yana aiki yanzu.';

  @override
  String get readVehicleTrackingOff =>
      'Bin diddigin motoci ba ya aiki a yanzu.';

  @override
  String get readVehicleTrackingFailed =>
      'An kasa tabbatar da matsayin bin diddigin motoci yanzu, sake gwadawa.';

  @override
  String get writeVehicleTrackingEnabledConfirm =>
      'Zai kunna filin lambar farantin a shafin rijistar ziyara na wannan shago. Tabbatarwa?';

  @override
  String get writeVehicleTrackingDisabledConfirm =>
      'Zai kashe filin lambar farantin a shafin rijistar ziyara na wannan shago. Tabbatarwa?';

  @override
  String get writeVehicleTrackingEnabledDone =>
      'An kunna bin diddigin motoci ✓';

  @override
  String get writeVehicleTrackingDisabledDone =>
      'An kashe bin diddigin motoci ✓';

  @override
  String get writeVehicleTrackingFailed =>
      'An kasa canza saitin bin diddigin motoci, sake gwadawa.';

  @override
  String get mobileRequestsTitle => 'Buƙatun keɓaɓɓu';

  @override
  String get mobileRequestsSubtitle =>
      'Buƙatun sabis da ke zuwa wurin abokin ciniki, daga karɓa zuwa kammalawa.';

  @override
  String get mobileRequestsKpiPending => 'Jiran yanke shawara';

  @override
  String get mobileRequestsKpiNeedsDecision => 'Yana buƙatar yanke shawara';

  @override
  String get mobileRequestsKpiCompletedMonth => 'An kammala wannan wata';

  @override
  String get mobileRequestsBannerGo => 'Duba';

  @override
  String get mobileRequestsFilterAll => 'Duka';

  @override
  String get mobileRequestsFilterPending => 'Jiran';

  @override
  String get mobileRequestsFilterAccepted => 'An karɓa';

  @override
  String get mobileRequestsFilterNeedsDecision => 'Yana buƙatar shawara';

  @override
  String get mobileRequestsFilterCompleted => 'An kammala';

  @override
  String get mobileRequestsFilterClosed => 'An rufe';

  @override
  String get mobileRequestsSearchHint => 'Nema da suna ko waya';

  @override
  String get mobileRequestsLoadFailedTitle => 'An kasa loda buƙatun';

  @override
  String get mobileRequestsLoadFailedBody =>
      'Duba haɗin intanetinka kuma sake gwadawa.';

  @override
  String get mobileRequestsRetry => 'Sake gwadawa';

  @override
  String get mobileRequestsEmptyTitle => 'Babu buƙatu tukuna';

  @override
  String get mobileRequestsEmptyBody =>
      'Buƙatun sabis na keɓaɓɓu daga abokan cinikinka suna bayyana anan.';

  @override
  String get mobileRequestsStatusPending => 'Ana jira';

  @override
  String get mobileRequestsStatusAccepted => 'An karɓa';

  @override
  String get mobileRequestsStatusNeedsDecision => 'Yana buƙatar shawara';

  @override
  String get mobileRequestsStatusCompleted => 'An kammala';

  @override
  String get mobileRequestsStatusNoShow => 'Bai zo ba';

  @override
  String get mobileRequestsStatusRejected => 'An ƙi';

  @override
  String get mobileRequestsUnnamed => 'Ba tare da suna ba';

  @override
  String get mobileRequestsOpenMap => 'Wuri';

  @override
  String get mobileRequestsPhoneCopied => 'An kwafi lambar wayar';

  @override
  String get mobileRequestsRiskyCustomer =>
      'Abokin ciniki mai haɗarin rashin zuwa';

  @override
  String mobileRequestsRejectReasonLine(Object reason) {
    return 'Dalilin ƙi: $reason';
  }

  @override
  String get mobileRequestsActionAccept => 'Karɓa';

  @override
  String get mobileRequestsActionReject => 'Ƙi';

  @override
  String get mobileRequestsActionComplete => 'An kammala';

  @override
  String get mobileRequestsActionNoShow => 'Bai zo ba';

  @override
  String get mobileRequestsAssignUnassigned => 'Ba a ba da alhaki ba';

  @override
  String get mobileRequestsActionFailed =>
      'An kasa kammala aikin, sake gwadawa.';

  @override
  String get mobileRequestsRejectTitle => 'Dalilin ƙi';

  @override
  String get mobileRequestsRejectHint => 'Na zaɓi';

  @override
  String get mobileRequestsRejectCancel => 'Soke';

  @override
  String get mobileRequestsRejectConfirm => 'Ƙi buƙatar';

  @override
  String get mobileRequestsAddOpen => 'Ƙara buƙata';

  @override
  String get mobileRequestsAddTitle => 'Ƙara buƙatar sabis na keɓaɓɓu';

  @override
  String get mobileRequestsAddPhoneLabel => 'Wayar abokin ciniki';

  @override
  String get mobileRequestsAddNameLabel => 'Sunan abokin ciniki (na zaɓi)';

  @override
  String get mobileRequestsAddServicesLabel => 'Ayyuka';

  @override
  String get mobileRequestsAddServicesEmpty => 'Babu ayyuka tukuna.';

  @override
  String get mobileRequestsAddDayLabel => 'Rana';

  @override
  String get mobileRequestsAddTimeLabel => 'Lokaci';

  @override
  String get mobileRequestsAddMapsLinkLabel => 'Hanyar wurin Google Maps';

  @override
  String get mobileRequestsAddMapsLinkHint =>
      'Yana karɓar cikakkiyar ko gajarciyar hanyar Google Maps.';

  @override
  String get mobileRequestsAddMapsLinkShort =>
      'Wannan gajarciyar hanya ce — manna cikakkiyar hanyar Google Maps.';

  @override
  String get mobileRequestsAddMapsLinkInvalid =>
      'An kasa karanta wuri daga wannan hanyar.';

  @override
  String get mobileRequestsAddAssignLabel => 'Ba da alhaki ga (na zaɓi)';

  @override
  String get mobileRequestsAddCancel => 'Soke';

  @override
  String get mobileRequestsAddSubmit => 'Ƙara buƙatar';

  @override
  String get mobileRequestsAddSubmitting => 'Ana ƙarawa...';

  @override
  String get mobileRequestsAddError => 'An kasa ƙara buƙatar, sake gwadawa.';

  @override
  String mobileRequestsBannerText(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Buƙatu $count suna buƙatar yanke shawararka yanzu',
    );
    return '$_temp0';
  }

  @override
  String get mobileRequestsAddMapsLinkResolving =>
      'Ana karanta wuri daga hanyar...';

  @override
  String get customersTitle => 'Masu Tuntuɓa';

  @override
  String get customersAddOpen => 'Ƙara abokin ciniki';

  @override
  String get customersSearchHint => 'Nema da suna ko waya';

  @override
  String get customersTabAll => 'Duka';

  @override
  String get customersTabOverdue => 'Wanda ya jinkirta';

  @override
  String get customersSearchFailedTitle => 'Bincike ba ya samuwa yanzu';

  @override
  String get customersSearchFailedBody => 'Sake gwadawa nan da ƴan lokaci.';

  @override
  String get customersSearchEmpty => 'Babu sakamako';

  @override
  String get customersLoadFailedTitle => 'An kasa loda';

  @override
  String get customersEmptyTitle => 'Babu abokan ciniki tukuna';

  @override
  String get customersOverdueEmpty => 'Babu wanda ya jinkirta a yanzu';

  @override
  String get customersUnnamed => 'Ba tare da suna ba';

  @override
  String customersVisitCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Ziyara $count',
    );
    return '$_temp0';
  }

  @override
  String get customersOverdueBadge => 'Jinkiri';

  @override
  String customersStatEveryDays(int days) {
    String _temp0 = intl.Intl.pluralLogic(
      days,
      locale: localeName,
      other: 'kowanne kwana $days',
    );
    return '$_temp0';
  }

  @override
  String customersOverdueBanner(int every, int since) {
    return 'Ya jinkirta ziyararsa ta saba — yawanci kowanne kwana $every, kwana $since tun ziyararsa ta karshe';
  }

  @override
  String customersVisitMeter(int n) {
    return 'Karatun mita: $n';
  }

  @override
  String get customersOfferExpiredBadge => 'Ya kare';

  @override
  String get customersDeniedAllTitle =>
      'Ba ka da izinin duba jerin abokan ciniki';

  @override
  String get customersDeniedOverdueTitle =>
      'Ba ka da izinin duba wanda ya jinkirta';

  @override
  String get customersDeniedDesc => 'Nemi mai shago ya baka wannan izinin.';

  @override
  String get customersAddTitle => 'Ƙara sabon abokin ciniki';

  @override
  String get customersAddPhoneLabel => 'Wayar abokin ciniki';

  @override
  String get customersAddNameLabel => 'Sunan abokin ciniki';

  @override
  String get customersAddPhoneInvalid => 'Lambar waya ba daidai ba ce.';

  @override
  String get customersAddFailed => 'An kasa ƙara abokin ciniki, sake gwadawa.';

  @override
  String get customersAddSubmitting => 'Ana ƙarawa...';

  @override
  String get customersAddSubmit => 'Ƙara';

  @override
  String get customersActionFailed => 'An kasa kammala aikin, sake gwadawa.';

  @override
  String get customersRepeatedIssuesTitle => 'Matsaloli masu maimaituwa';

  @override
  String get customersVehiclesTitle => 'Motoci';

  @override
  String get customersLoyaltyTitle => 'Aminci';

  @override
  String get customersLoyaltyLoading => 'Ana loda...';

  @override
  String customersLoyaltyPoints(int count) {
    return 'Maki $count';
  }

  @override
  String get customersLoyaltyAdjust => 'Gyara';

  @override
  String get customersOffersTitle => 'Tayin da ke aiki';

  @override
  String customersOfferExpires(String date) {
    return 'Yana ƙarewa $date';
  }

  @override
  String get customersVisitsTitle => 'Tarihin ziyara';

  @override
  String get customersVisitsEmpty => 'Babu ziyara tukuna';

  @override
  String get customersVisitNoServices => 'Babu ayyukan da aka rubuta';

  @override
  String get customersRenameTitle => 'Gyara sunan abokin ciniki';

  @override
  String get customersRenameSubmit => 'Ajiye';

  @override
  String get customersLoyaltyAdjustTitle => 'Gyara makin aminci';

  @override
  String get customersLoyaltyAdjustNoteLabel => 'Dalilin gyara';

  @override
  String get customersLoyaltyAdjustNoteRequired =>
      'Rubuta dalili na gaskiya (aƙalla haruffa 3), kuma zaɓi lambar da ba sifili ba.';

  @override
  String get customersLoyaltyAdjustSubmit => 'Ajiye gyara';

  @override
  String get customersEraseButton => 'Share bayanan wannan abokin ciniki';

  @override
  String get customersEraseTitle => 'Share bayanan abokin ciniki';

  @override
  String get customersEraseWarning =>
      'Wannan yana share duk bayanan abokin ciniki daga dandali har abada — ba za a iya soke wannan ba.';

  @override
  String customersEraseTypeNameLabel(String name) {
    return 'Don tabbatarwa, rubuta sunan abokin ciniki: $name';
  }

  @override
  String get customersEraseConfirm => 'Share har abada';

  @override
  String get customersBookingsTitle => 'Ajiyewa';

  @override
  String customersAttendanceRate(int rate) {
    return '$rate% halarta';
  }

  @override
  String get customersBookingsNoneUpcoming => 'Babu ajiyewa mai zuwa';

  @override
  String get customersCyclesTitle => 'Zagayowar tunatarwa';

  @override
  String customersCyclesEveryDays(int days) {
    return 'Kowace kwana $days';
  }

  @override
  String get customersCyclesEditHint =>
      'Saita tazara, kuma koyo ta atomatik zai tsaya don wannan sabis tare da wannan abokin ciniki.';

  @override
  String get customersCyclesSave => 'Ajiye';

  @override
  String get customersLogTitle => 'Tarihin saƙonni';

  @override
  String get customersLogEmpty => 'Ba mu aika masa da komai ba tukuna';

  @override
  String get customersLogOutcomeSent => 'An aika';

  @override
  String get customersLogOutcomeSuppressed => 'Ba a aika ba';

  @override
  String get customersTemplateVisitConfirmation => 'Tabbatar ziyara';

  @override
  String get customersTemplateVisitConfirmationRating =>
      'Neman kimantawa bayan ziyara';

  @override
  String get customersTemplateBookingConfirmation => 'Tabbatar tanadi';

  @override
  String get customersTemplateVisitRedeemed => 'Sanarwar musanya lada';

  @override
  String get customersTemplateServiceReminder => 'Tunatarwa sabis';

  @override
  String get customersTemplateFollowUp => 'Bibiya bayan ziyara';

  @override
  String get customersTemplateAccountNotice => 'Sanarwa game da asusu';

  @override
  String get customersTemplatePointsExpiring => 'Faɗakarwa ƙarewar maki';

  @override
  String get customersTemplateLoyaltyActivation => 'Kunna shirin aminci';

  @override
  String get customersTemplateWinback => 'Dawo da abokin ciniki da ya ɓace';

  @override
  String get customersTemplatePersonalOccasion => 'Gaisuwa a wani biki';

  @override
  String customersShowAll(int count) {
    return 'Nuna duka ($count)';
  }

  @override
  String get customersCyclesUnknownService => 'Sabis wanda ba a sani ba';

  @override
  String customersVisitGapDays(int days) {
    String _temp0 = intl.Intl.pluralLogic(
      days,
      locale: localeName,
      other: 'bayan kwana $days',
      zero: 'a rana daya',
    );
    return '$_temp0';
  }

  @override
  String customersCountLabel(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Abokan ciniki $count',
      zero: 'babu abokan ciniki tukuna',
    );
    return '$_temp0';
  }

  @override
  String get ratingTitle => 'Kimantawa';

  @override
  String get pointsTitle => 'Maki na Aminci';

  @override
  String get pointsAddReward => 'Sabuwar lada';

  @override
  String get pointsEditReward => 'Gyara lada';

  @override
  String get pointsTabRewards => 'Ladoji';

  @override
  String get pointsTabLeaderboard => 'Mafi karɓa';

  @override
  String get pointsOutstandingHint =>
      'maki da shago har yanzu yake bin abokan ciniki';

  @override
  String pointsRedemptionsCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'karɓe $count',
    );
    return '$_temp0';
  }

  @override
  String pointsCustomersCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'abokan ciniki $count sun karɓa',
    );
    return '$_temp0';
  }

  @override
  String pointsExpiredWarning(int percent) {
    return '%$percent na makin da aka bayar sun kare ba tare da karɓa ba — duba farashin ladodinka';
  }

  @override
  String get pointsLoadFailedTitle => 'An kasa loda ladoji';

  @override
  String get pointsRewardsEmpty =>
      'Babu lada tukuna — kara lada na farko ga abokan cinikinka';

  @override
  String get pointsLeaderboardEmpty =>
      'Babu karɓa tukuna — zai bayyana anan da zarar abokin ciniki ya karɓi lada';

  @override
  String get pointsLeaderboardTitle => 'Mafi karɓa';

  @override
  String get pointsLeaderboardHint =>
      'Manyan ladoji biyar da abokan cinikinka suka karɓa';

  @override
  String pointsTimesRedeemed(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'sau $count',
    );
    return '$_temp0';
  }

  @override
  String get pointsRewardRetired => 'An dakatar';

  @override
  String pointsRewardServiceHint(String name) {
    return 'Sabis: $name';
  }

  @override
  String pointsRewardDiscountHint(String amount) {
    return 'Rangwame na riyal $amount';
  }

  @override
  String get pointsRewardItemHint => 'Kyauta, ba a haɗa da katalog ba';

  @override
  String get pointsRewardNameLabel => 'Sunan lada';

  @override
  String get pointsRewardTypeLabel => 'Nau\'in lada';

  @override
  String get pointsTypeService => 'Sabis daga katalogka';

  @override
  String get pointsTypeItem => 'Kyauta';

  @override
  String get pointsTypeDiscount => 'Rangwamen kudi';

  @override
  String get pointsRewardServiceLabel => 'Wanne sabis';

  @override
  String get pointsRewardDiscountLabel => 'Adadin rangwame, riyal';

  @override
  String get pointsRewardCostLabel => 'Kudin a maki';

  @override
  String get pointsRewardActiveLabel =>
      'Yana aiki — abokan ciniki na iya karɓarsa';

  @override
  String get pointsRewardInvalid =>
      'Shigar da suna da maki na gaskiya sama da sifili';

  @override
  String get pointsSaveFailed => 'An kasa ajiyewa, sake gwadawa';

  @override
  String get pointsModeTitle => 'Hanyar ƙidayawa';

  @override
  String get pointsModeHint =>
      'Ta sabis: kowace sabis makinta na kanta. Ta darajar sigina: maki ɗaya kowace riyal.';

  @override
  String get pointsModeServices => 'Ta sabis';

  @override
  String get pointsModeInvoice => 'Ta darajar sigina';

  @override
  String get pointsModeNeedsPricedServices =>
      'Ƙidayawa ta darajar sigina tana buƙatar an sanya farashin kowace sabis tukuna — sanya farashin duka a Ayyuka, sannan a kunna shi.';

  @override
  String get pointsOpenEarnSettings => 'Saitin maki na kowace sabis';

  @override
  String get ratingLeaderboardTitle => 'Mas kimanta mafi girma';

  @override
  String get ratingCardNoName => 'Ba tare da suna ba';

  @override
  String get ratingMetricVisits => 'Mafi yawan ziyara';

  @override
  String get ratingMetricRatings => 'Mafi yawan kimantawa';

  @override
  String get ratingMetricAvg => 'Mas kimanta mafi girma';

  @override
  String ratingStaffCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'ma\'aikata $count',
    );
    return '$_temp0';
  }

  @override
  String get ratingTableTitle => 'Kowanne ma\'aikaci';

  @override
  String ratingTableVisitsValue(int n) {
    return 'ziyara $n';
  }

  @override
  String ratingTableRatingsValue(int n) {
    return 'kimantawa $n';
  }

  @override
  String ratingTableEngagementValue(int n) {
    return 'shiga %$n';
  }

  @override
  String ratingTableNoShowValue(int n) {
    return 'rashin zuwa %$n';
  }

  @override
  String get ratingPeriodWeek => 'Mako';

  @override
  String get ratingPeriodMonth => 'Wata';

  @override
  String get ratingPeriodQuarter => 'Kwata';

  @override
  String get ratingPeriodCustom => 'Na musamman';

  @override
  String ratingCustomSince(String date) {
    return 'Daga: $date';
  }

  @override
  String ratingCustomUntil(String date) {
    return 'Zuwa: $date';
  }

  @override
  String get ratingCustomRangeInvalid =>
      'Zangon ba daidai ba ne — tabbatar ranar farawa ta gabaci ranar ƙarshe';

  @override
  String get ratingExportLocaleLabel => 'Harshen rahoto';

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
  String get ratingTopIssuesTitle => 'Matsalolin da suka fi maimaituwa';

  @override
  String get ratingFilterUnhandled => 'Ana jira';

  @override
  String get ratingFilterAll => 'Duka';

  @override
  String get ratingFilterHandled => 'An warware';

  @override
  String get ratingStarsAll => 'Duk taurari';

  @override
  String get ratingLoadFailedTitle => 'An kasa loda kimantawa';

  @override
  String get ratingEmptyTitle => 'Babu kimantawa tukuna';

  @override
  String get ratingLoadMore => 'Nuna ƙari';

  @override
  String get ratingHandledPlain => 'An warware';

  @override
  String get ratingMarkHandled => 'Yi alama an warware';

  @override
  String get ratingMarkHandledHint =>
      'Ana rikodin wannan har abada — ba za a iya soke shi daga baya ba.';

  @override
  String get ratingHandledNoteLabel => 'Bayani (na zaɓi)';

  @override
  String get ratingMarkHandledConfirm => 'Tabbatar';

  @override
  String get ratingActionFailed => 'An kasa kammala aikin, sake gwadawa.';

  @override
  String ratingWeightedAvgHint(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'daga kimantawa $count cikin kwanaki 30 da suka wuce',
      zero: 'babu kimantawa cikin kwanaki 30 da suka wuce',
    );
    return '$_temp0';
  }

  @override
  String ratingUnhandledCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Kimantawa $count suna jira',
    );
    return '$_temp0';
  }

  @override
  String ratingVisitsShort(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Ziyara $count',
    );
    return '$_temp0';
  }

  @override
  String ratingIssueFilterLabel(String label) {
    return 'Matsala: $label';
  }

  @override
  String ratingByOperator(String name) {
    return '$name ne yi masa hidima';
  }

  @override
  String ratingHandledWithNote(String note) {
    return 'An warware: $note';
  }

  @override
  String get ratingQuadrantTitle => 'Kashin aiki';

  @override
  String get ratingQuadrantHint =>
      'Inganci da yawan sadarwa — danna kowane digo don rikodin horar da ma\'aikacin.';

  @override
  String get ratingQuadrantStars => 'Taurari';

  @override
  String get ratingQuadrantUnderused => 'Ba a amfani da shi sosai ba';

  @override
  String get ratingQuadrantNeedsCoaching => 'Yana buƙatar horo';

  @override
  String get ratingQuadrantAtRisk => 'Yana cikin haɗari';

  @override
  String get ratingTrainingTitle => 'Rikodin horo';

  @override
  String get ratingTrainingNoAccess => 'Ba ka da izinin ganin wannan.';

  @override
  String get ratingTrainingClean =>
      'Tsaftataccen rikodi — babu matsalolin da suka maimaita.';

  @override
  String ratingEngagementPercent(int percent) {
    return '%$percent sadarwa';
  }

  @override
  String get ratingTabOverview => 'Bayyani';

  @override
  String get ratingTabFeed => 'Duk kimantawa';

  @override
  String get ratingOverviewEmpty =>
      'Babu bayanan aiki tukuna cikin kwanaki 30 da suka wuce.';

  @override
  String get ratingExportTitle => 'Fitar da rahoto';

  @override
  String get ratingExportHint =>
      'Rahoton aikin ƙungiya na lokacin da aka zaɓa, a shirye don rabawa.';

  @override
  String get ratingExportFailed => 'An kasa fitar da rahoto, sake gwadawa.';

  @override
  String get customersPrivacyRequestsTitle => 'Buƙatun keɓantawa';

  @override
  String get customersPrivacyRequestErase => 'Buƙatar share bayanai';

  @override
  String get customersPrivacyRequestCopy => 'Buƙatar kwafin bayanai';

  @override
  String customersPrivacyRequestGeneric(String type) {
    return 'Buƙata: $type';
  }

  @override
  String get customersPrivacyRequestClose => 'Rufe';

  @override
  String get customersLoyaltyHistoryTitle => 'Tarihin maki';

  @override
  String get customersLoyaltyHistoryNoReason => 'Ba a bayar da dalili ba';

  @override
  String get customersLoyaltyReasonRedeem => 'An maida lada';

  @override
  String get customersLoyaltyReasonAdjust => 'Gyaran hannu';

  @override
  String get customersLoyaltyReasonEarn => 'Maki daga ziyara';

  @override
  String get customersLoyaltyReasonExpire => 'Ya ƙare';

  @override
  String get readCustomersFailed =>
      'An kasa samun bayanan abokan ciniki yanzu, sake gwadawa.';

  @override
  String readCustomersTotal(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Kana da abokan ciniki $count da aka yi wa rijista.',
      zero: 'Babu abokan ciniki da aka yi wa rijista tukuna.',
    );
    return '$_temp0';
  }

  @override
  String readCustomersOverdueCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Abokan cinikinka $count sun jinkirta a zagayowarsu.',
      zero: 'Babu abokin ciniki da ya jinkirta a zagayowarsa yanzu.',
    );
    return '$_temp0';
  }

  @override
  String get readMobileRequestsFailed =>
      'An kasa samun buƙatun keɓaɓɓu yanzu, sake gwadawa.';

  @override
  String readMobileRequestsPendingCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Kana da buƙatu $count da ke jiran yanke shawara.',
      zero: 'Babu buƙatun keɓaɓɓu da ke jiran yanke shawara.',
    );
    return '$_temp0';
  }

  @override
  String readMobileRequestsNeedsDecisionCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Buƙatu $count suna buƙatar yanke shawararka yanzu.',
      zero: 'Babu buƙatu da ke buƙatar yanke shawararka yanzu.',
    );
    return '$_temp0';
  }

  @override
  String get readRatingFailed =>
      'An kasa samun bayanan kimantawa yanzu, sake gwadawa.';

  @override
  String get readRatingNone =>
      'Babu kimantawa a cikin kwanaki 30 da suka wuce tukuna.';

  @override
  String readRatingAverage(String avg, int count) {
    return 'Matsakaicin kimantawarka a cikin kwanaki 30 da suka wuce $avg daga cikin 5, daga kimantawa $count.';
  }

  @override
  String readRatingUnhandledCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Kana da kimantawa $count da ke jira.',
      zero: 'Babu kimantawa da ke jira.',
    );
    return '$_temp0';
  }

  @override
  String readRatingTopStaff(String name, String avg) {
    return 'Ma\'aikaci mafi kyawun kimantawa a cikin kwanaki 30 da suka wuce shine $name, matsakaicin $avg daga 5.';
  }

  @override
  String readMobileRequestsCompletedCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Ka kammala $count a wannan wata.',
      zero: 'Ba ka kammala wata buƙatar keɓaɓɓu a wannan wata ba tukuna.',
    );
    return '$_temp0';
  }

  @override
  String readMobileRequestsTodayCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Buƙatu $count sun zo yau.',
      zero: 'Babu buƙatar keɓaɓɓu da ta zo yau tukuna.',
    );
    return '$_temp0';
  }

  @override
  String get readOperatorsFailed =>
      'An kasa samun adadin ma\'aikata yanzu, sake gwadawa.';

  @override
  String readOperatorsCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Kana da ma\'aikata $count a ƙungiyarka.',
      zero: 'Babu ma\'aikata da aka yi wa rijista tukuna.',
    );
    return '$_temp0';
  }

  @override
  String readBranchesDisconnectedCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Kana da rassa $count da WhatsApp ba ya aiki.',
      zero:
          'Duk rassanka masu aiki suna da WhatsApp da aka haɗa kuma yana aiki.',
    );
    return '$_temp0';
  }

  @override
  String get readCustomersRecentNone =>
      'Ba ka da wani abokin ciniki da aka yi wa rijista tukuna.';

  @override
  String readCustomersRecentName(String name) {
    return 'Abokin cinikinka na baya-bayan nan shine $name.';
  }

  @override
  String readRatingCriticalIssuesCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Kana da kimantawa $count da ke jira masu matsala mai tsanani.',
      zero: 'Babu kimantawar da ke jira mai matsala mai tsanani.',
    );
    return '$_temp0';
  }

  @override
  String get readPerBranchModeOn =>
      'Ee, shagonka yana aiki cikin yanayin rassa da yawa.';

  @override
  String get readPerBranchModeOff =>
      'A\'a, shagonka yana aiki azaman reshe ɗaya kawai.';

  @override
  String get readBillingOverdueYes =>
      'Ee, kana da lissafin da bai biya ba — biya don kauce wa dakatar da hidimominka.';

  @override
  String get readBillingOverdueNo =>
      'A\'a, biyan kuɗinka yana da kyau, babu lissafin da bai biya ba.';

  @override
  String get readServicesFailed =>
      'An kasa samun adadin ayyuka yanzu, sake gwadawa.';

  @override
  String readServicesCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Kana da ayyuka $count a jerinka.',
      zero: 'Babu wani sabis a jerinka tukuna.',
    );
    return '$_temp0';
  }

  @override
  String readCustomersTodayCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Sabbin abokan ciniki $count sun zo yau.',
      zero: 'Babu sabon abokin ciniki da ya zo yau tukuna.',
    );
    return '$_temp0';
  }

  @override
  String readMobileRequestsRejectedCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Ka ƙi $count a wannan wata.',
      zero: 'Ba ka ƙi wata buƙatar keɓaɓɓu a wannan wata ba.',
    );
    return '$_temp0';
  }

  @override
  String readMobileRequestsNoShowCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Abokan ciniki $count ba su zo ba a wannan wata.',
      zero: 'Babu abokin ciniki da bai zo ba a wannan wata.',
    );
    return '$_temp0';
  }

  @override
  String readRatingFiveStarCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Kana da kimantawa $count na taurari biyar.',
      zero: 'Babu kimantawar taurari biyar tukuna.',
    );
    return '$_temp0';
  }

  @override
  String readBranchesActiveCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Kana da rassa $count masu aiki.',
      zero: 'Babu reshe mai aiki a yanzu.',
    );
    return '$_temp0';
  }

  @override
  String get servicesTitle => 'Ayyukana';

  @override
  String get servicesUnnamedGlyph => '?';

  @override
  String get servicesSearchHint => 'Nema da sunan sabis';

  @override
  String get servicesTabActive => 'Masu aiki';

  @override
  String get servicesTabStopped => 'An dakatar';

  @override
  String get servicesLoadFailedTitle => 'An kasa loda ayyuka';

  @override
  String get servicesEmptyActive => 'Babu ayyuka masu aiki tukuna';

  @override
  String get servicesEmptyStopped => 'Babu ayyukan da aka dakatar';

  @override
  String get servicesAddOpen => 'Ƙara sabis';

  @override
  String get servicesNoPrice => 'Ba a saita farashi ba';

  @override
  String get servicesNoDuration => 'Ba a saita ba';

  @override
  String get servicesNoCycle => 'Babu zagaye';

  @override
  String get servicesStopTitle => 'Dakatar da sabis';

  @override
  String get servicesStopConfirm => 'Dakatar';

  @override
  String get servicesActionFailed => 'An kasa kammala aikin, sake gwadawa.';

  @override
  String get servicesEditTitle => 'Gyara sabis';

  @override
  String get servicesAddTitle => 'Ƙara sabon sabis';

  @override
  String get servicesNameLabel => 'Sunan sabis';

  @override
  String get servicesPriceLabel => 'Farashi (na zaɓi)';

  @override
  String get servicesDurationLabel => 'Tsawon lokaci a mintuna (na zaɓi)';

  @override
  String get servicesCycleLabel => 'Zagayen tunatarwa a kwanaki (na zaɓi)';

  @override
  String get servicesDescriptionLabel => 'Gajeren bayani (na zaɓi)';

  @override
  String get servicesSaving => 'Ana ajiyewa...';

  @override
  String get servicesSave => 'Ajiye';

  @override
  String get servicesNameRequired => 'Sunan sabis ana buƙata';

  @override
  String servicesActiveCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Kana da ayyuka $count masu aiki.',
      zero: 'Babu sabis mai aiki tukuna.',
    );
    return '$_temp0';
  }

  @override
  String servicesDurationMinutes(int count) {
    return 'Mintuna $count';
  }

  @override
  String servicesCycleDays(int count) {
    return 'Kowace kwana $count';
  }

  @override
  String servicesStopWarning(String name) {
    return 'Wannan zai dakatar da \"$name\" — ba za ta bayyana don sabon ziyara ba, kuma tunatarwarta za su tsaya. Ba a taɓa share bayananta ba.';
  }

  @override
  String get servicesPhotoPickFailed => 'An kasa zaɓar hoto';

  @override
  String get servicesPhotoUploadFailed => 'An ajiye, amma an kasa loda hoto';

  @override
  String get servicesPhotoLabel => 'Hoton sabis (na zaɓi)';

  @override
  String get servicesUploadPhoto => 'Loda hoto';

  @override
  String get servicesChangePhoto => 'Canza hoto';

  @override
  String get servicesRemovePhoto => 'Cire';

  @override
  String get servicesAssignmentLabel => 'Wa ke bayar da wannan sabis?';

  @override
  String get servicesAssignmentAuto => 'Duk wani ma\'aikaci da ke akwai';

  @override
  String get servicesAssignmentNamed => 'Takamaiman ma\'aikata';

  @override
  String get servicesChecklistLabel => 'Matakan aiki';

  @override
  String get servicesChecklistEmpty => 'Babu matakai tukuna — ƙara na farko';

  @override
  String get servicesStepAddTitle => 'Ƙara mataki';

  @override
  String get servicesGeneralSettingsTitle => 'Saitin gama-gari';

  @override
  String get servicesGeneralSettingsHint =>
      'Ƙimar da kowane sabis da ba a keɓance ba yake bi';

  @override
  String get servicesFollowUpLabel => 'Kwanakin bibiya bayan ziyara';

  @override
  String get servicesPointsLabel => 'Maki a kowace ziyara';

  @override
  String get servicesGroupThem => 'Haɗa su';

  @override
  String get servicesGroupNameHint => 'Sunan rukuni';

  @override
  String get servicesAllGroups => 'Duka';

  @override
  String get servicesStepEditTitle => 'Gyara mataki';

  @override
  String get servicesStepCriticalLabel => 'Muhimmin mataki';

  @override
  String get servicesStepRetire => 'Dakatar da wannan mataki';

  @override
  String get servicesStepEditHint =>
      'Riƙe kowane mataki na dogon lokaci don gyara ko dakatar da shi';

  @override
  String get servicesAdvancedTitle => 'Ci-gaba na saituna';

  @override
  String get servicesAdvancedHint =>
      'Keɓance wannan sabis daga saitin gama-gari — zagaye, maki, da haɗawa';

  @override
  String get servicesGroupLabel => 'Rukuni';

  @override
  String get servicesNoGroup => 'Babu rukuni';

  @override
  String get servicesNewGroup => 'Sabon rukuni';

  @override
  String get servicesFollowGeneralAction => 'Bi na gama-gari';

  @override
  String get servicesCustomizeAction => 'Keɓance';

  @override
  String servicesFollowUpDays(int n) {
    return 'Bibiya bayan kwanaki $n';
  }

  @override
  String servicesPointsPerVisit(int n) {
    return 'Maki $n';
  }

  @override
  String servicesSuggestionText(int n) {
    return 'Sabis $n suna da ƙima ɗaya — haɗa su cikin rukuni ɗaya yana sauƙaƙa gyara su tare daga baya.';
  }

  @override
  String servicesFollowsGeneral(String hint) {
    return 'Yana bin gama-gari — $hint';
  }

  @override
  String get servicesPageTabServices => 'Ayyuka';

  @override
  String get servicesPageTabPackages => 'Fakiti';

  @override
  String get servicesPackageAdd => 'Ƙara fakiti';

  @override
  String get servicesPackageNeedsTwoServices =>
      'Fakiti yana buƙatar aƙalla ayyuka biyu masu aiki';

  @override
  String get servicesPackageEmpty => 'Babu fakiti tukuna';

  @override
  String get servicesPackageEditTitle => 'Gyara fakiti';

  @override
  String get servicesPackageAddTitle => 'Ƙara sabon fakiti';

  @override
  String get servicesPackageNameLabel => 'Sunan fakiti';

  @override
  String get servicesPackagePriceRequired =>
      'Ana buƙatar farashin fakiti, sama da sifili';

  @override
  String get servicesPackageServicesLabel => 'Ayyukan da aka haɗa';

  @override
  String get servicesImportTitle => 'Shigo da ayyuka daga fayil';

  @override
  String get servicesImportHint =>
      'Fayil CSV mai ginshiƙai: name, price, duration_minutes, cycle_days, description';

  @override
  String get servicesImportPickFile => 'Zaɓi fayil CSV';

  @override
  String get servicesImportReadFailed => 'An kasa karanta fayil';

  @override
  String get servicesImportParseFailed =>
      'Fayil ba shi da ginshiƙin name, ko tsarinsa ba daidai ba ne';

  @override
  String get servicesImportDeactivateMissing =>
      'Dakatar da ayyukan da ba su nan a fayil';

  @override
  String get servicesImportDeactivateMissingHint =>
      'Duk wani sabis da kake da shi a halin yanzu wanda ba ya cikin wannan fayil za a dakatar da shi ta atomatik';

  @override
  String get servicesImportConfirm => 'Shigo da su';

  @override
  String get servicesImportClose => 'An gama';

  @override
  String servicesImportRowCount(int n) {
    return 'Layuka $n a shirye don shigowa';
  }

  @override
  String servicesImportDone(int created, int updated, int reactivated) {
    return 'An ƙara $created, an sabunta $updated, an sake kunna $reactivated.';
  }

  @override
  String get visitPackagesSectionTitle => 'Fakiti masu fice';

  @override
  String get visitNameFieldHint => 'Sunan abokin ciniki (na zaɓi)';

  @override
  String get visitMeterFieldHint => 'Karatun mita';

  @override
  String get visitQuantityDialogTitle => 'Yawa';

  @override
  String get visitCouponCheckboxLabel => 'Ba wani shago kubo na rangwame';

  @override
  String get visitCouponPhoneHint => 'Wayar mai shago';

  @override
  String get visitClearAllButton => 'Share duka';

  @override
  String visitServicesSelectedCount(int n) {
    return 'An zaɓi ayyuka $n';
  }

  @override
  String get visitTodayBookingsTitle => 'Alkawuran yau';

  @override
  String get visitBookingAttendFailed =>
      'An kasa tabbatar da halarta, sake gwadawa';

  @override
  String get branchSwitcherChooseBranch => 'Zaɓi reshe';

  @override
  String get branchSwitcherTitle => 'Reshen yanzu';

  @override
  String get branchSwitcherHint =>
      'Duk abin da ka buɗe bayan wannan na wannan reshe ne';

  @override
  String get proceduresPrintFailed => 'An kasa qirqirar takarda';

  @override
  String get proceduresTitle => 'Matakan Aiki';

  @override
  String get proceduresSubtitle =>
      'Saita jerin matakan aiki na kowace sabis, ko kula da dukan dakin karatu na gama gari. Latsa na dade don zaba don bugawa';

  @override
  String get proceduresLibraryLink => 'Dakin karatun matakai';

  @override
  String get proceduresPrint => 'Buga';

  @override
  String get proceduresEmptyTitle => 'Babu sabis mai aiki tukuna';

  @override
  String get servicesStepSeverityNormal => 'Na yau da kullun';

  @override
  String get servicesStepSeverityCritical => 'Mai muhimmanci';

  @override
  String get proceduresSaveFailed => 'An kasa ajiyewa';

  @override
  String get proceduresDrawerSubtitle =>
      'Ja don sake tsari, ko qara mataki daga dakin karatu';

  @override
  String get proceduresDrawerEmpty => 'Babu matakai na wannan sabis tukuna';

  @override
  String get proceduresDrawerAddButton => 'Qara daga dakin karatu';

  @override
  String get proceduresPickTitle => 'Zabi mataki';

  @override
  String get proceduresPickClose => 'Rufe';

  @override
  String get proceduresPickApply => 'Qara';

  @override
  String get proceduresPickSearch => 'Nema matakai';

  @override
  String get proceduresPickEmpty => 'Babu sakamako';

  @override
  String get proceduresPickCreatePlaceholder => 'Sabon mataki...';

  @override
  String get proceduresLibrarySaveFailed => 'An kasa ajiyewa';

  @override
  String get proceduresLibraryTitle => 'Dakin karatun matakai';

  @override
  String get proceduresLibrarySubtitle =>
      'Kowane mataki anan an raba shi tsakanin duk sabis da ke amfani da shi - gyara shi yana canza shi kowa inda';

  @override
  String get proceduresLibraryNewPlaceholder => 'Rubutun sabon mataki';

  @override
  String get proceduresLibraryAdd => 'Qara';

  @override
  String get proceduresLibraryShowRetired => 'Nuna wadanda aka dakatar';

  @override
  String get proceduresLibraryEmpty => 'Babu matakai tukuna';

  @override
  String get proceduresLibraryRetired => 'An dakatar';

  @override
  String get proceduresLibraryRetire => 'Dakatar';

  @override
  String get proceduresLibraryReactivate => 'Sake kunnawa';

  @override
  String get proceduresSeverityHint =>
      'Ana haskaka muhimmin mataki wa maaikaci kuma ba za a iya tsallake shi ba yayin aiwatar da sabis';

  @override
  String proceduresSelectedCount(int n) {
    return 'An zabi $n';
  }

  @override
  String proceduresStepCount(int n) {
    return 'Matakai $n';
  }

  @override
  String proceduresUsedIn(int n) {
    return 'Ana amfani a sabis $n';
  }

  @override
  String get mutualBenefitProposeButton => 'Baiwa shawarar hadin gwiwa';

  @override
  String get mutualBenefitTitle => 'Amfanin Juna';

  @override
  String get mutualBenefitSubtitle =>
      'Tura abokan ciniki na gaske tsakanin ku da sauran shaguna, ta yarjejeniya tsakanin bangarorin biyu';

  @override
  String get mutualBenefitRoleAll => 'Duka';

  @override
  String get mutualBenefitRoleReferrer => 'A matsayin mai tura';

  @override
  String get mutualBenefitRoleBeneficiary => 'A matsayin mai amfana';

  @override
  String get mutualBenefitLoadFailed => 'An kasa loda hadin gwiwa';

  @override
  String get mutualBenefitEmptyTitle => 'Babu hadin gwiwa tukuna';

  @override
  String get mutualBenefitKpiAsReferrer => 'A matsayin mai tura';

  @override
  String get mutualBenefitKpiAsBeneficiary => 'A matsayin mai amfana';

  @override
  String get mutualBenefitKpiSent => 'An tura';

  @override
  String get mutualBenefitKpiRedeemed => 'An fanshi';

  @override
  String get mutualBenefitKpiRate => 'Adadin fansa';

  @override
  String get mutualBenefitConfirm => 'Tabbatar';

  @override
  String get mutualBenefitGrantDiscountBlanket => 'Rangwame akan dukan ziyara';

  @override
  String get mutualBenefitStatusProposed => 'An bayar da shawara';

  @override
  String get mutualBenefitStatusActive => 'Mai aiki';

  @override
  String get mutualBenefitStatusPaused => 'An dakatar na wucin gadi';

  @override
  String get mutualBenefitStatusCancelRequested => 'An nemi soke';

  @override
  String get mutualBenefitStatusEnded => 'Ya kare';

  @override
  String get mutualBenefitStatusRejected => 'An ki amincewa';

  @override
  String get mutualBenefitStatusExpiredUnanswered =>
      'Ya kare ba tare da amsa ba';

  @override
  String get mutualBenefitEventProposed => 'An bayar da shawarar hadin gwiwa';

  @override
  String get mutualBenefitEventAccepted => 'An amince da hadin gwiwa';

  @override
  String get mutualBenefitEventRejected => 'An ki amincewa da hadin gwiwa';

  @override
  String get mutualBenefitEventActivated => 'An kunna hadin gwiwa';

  @override
  String get mutualBenefitEventCancelRequested => 'An nemi soke';

  @override
  String get mutualBenefitEventCancelConfirmed => 'An tabbatar da sokewa';

  @override
  String get mutualBenefitEventExpiredUnanswered =>
      'Ya kare ba tare da amsa ba';

  @override
  String get mutualBenefitEventPaused => 'An dakatar na wucin gadi';

  @override
  String get mutualBenefitEventResumed => 'An sake farawa';

  @override
  String get mutualBenefitEventEndedTerm => 'Lokaci ya kare';

  @override
  String get mutualBenefitEventGrantCreated => 'Sabon kyauta';

  @override
  String get mutualBenefitEventGrantRedeemed => 'An fanshi kyauta';

  @override
  String get mutualBenefitActivityActive => 'Mai aiki';

  @override
  String get mutualBenefitActivityPaused => 'An dakatar na wucin gadi';

  @override
  String get mutualBenefitActivityPending => 'Ana jiran amsa';

  @override
  String get mutualBenefitActivityInactive => 'Ba mai aiki ba';

  @override
  String get mutualBenefitScorecardTitle => 'Aiki';

  @override
  String get mutualBenefitScorecardFailed => 'An kasa loda aiki';

  @override
  String get mutualBenefitActivityTitle => 'Ayyukan kwanan nan';

  @override
  String get mutualBenefitActivityEmpty => 'Babu ayyuka tukuna';

  @override
  String get mutualBenefitAgreementsTitle => 'Yarjejeniyoyi';

  @override
  String get mutualBenefitConfirmCancel =>
      'Tabbatar da kawo karshen wannan hadin gwiwa har abada?';

  @override
  String get mutualBenefitActionAccept => 'Amince';

  @override
  String get mutualBenefitActionReject => 'Ki amincewa';

  @override
  String get mutualBenefitActionWaitingThem => 'Ana jiran daya bangaren';

  @override
  String get mutualBenefitActionCancelRequest => 'Nema a kawo karshen';

  @override
  String get mutualBenefitActionCancelConfirm => 'Tabbatar da kawo karshen';

  @override
  String get mutualBenefitProposeTitle => 'Baiwa sabon shawarar hadin gwiwa';

  @override
  String get mutualBenefitProposePhoneLabel => 'Lambar wayar sauran shago';

  @override
  String get mutualBenefitProposeConditionLabel =>
      'Sharadin cancanta a shagon ku';

  @override
  String get mutualBenefitConditionMinTotal => 'Mafi karancin kudin biya';

  @override
  String get mutualBenefitConditionServiceId => 'Takamaiman sabis';

  @override
  String get mutualBenefitProposeConditionValueRiyals => 'Adadin (Riyal)';

  @override
  String get mutualBenefitProposeConditionValueService => 'Sabis';

  @override
  String get mutualBenefitProposeValidityLabel => 'Ingancin (kwanaki)';

  @override
  String get mutualBenefitProposeDurationLabel => 'Tsawon (kwanaki)';

  @override
  String get mutualBenefitProposeCapLabel => 'Iyaka / kwana 30';

  @override
  String get mutualBenefitProposeGrantTypeLabel => 'Nau\'in kyauta';

  @override
  String get mutualBenefitGrantTypeDiscount => 'Rangwame';

  @override
  String get mutualBenefitGrantTypeGift => 'Kyauta';

  @override
  String get mutualBenefitScopeBlanket => 'Dukan ziyara';

  @override
  String get mutualBenefitScopeItem => 'Takamaiman sabis';

  @override
  String get mutualBenefitScopeGroup => 'Kungiya/kunshin';

  @override
  String get mutualBenefitProposeServiceLabel => 'Sabis';

  @override
  String get mutualBenefitProposeGroupLabel => 'Kungiya';

  @override
  String get mutualBenefitProposeImmutableNote =>
      'Sharuddan kyauta sun tabbata bayan aikawa — sabon tayi yana bukatar sabuwar yarjejeniya';

  @override
  String get mutualBenefitProposeSubmitting => 'Ana aikawa...';

  @override
  String get mutualBenefitProposeSubmit => 'Aika shawara';

  @override
  String mutualBenefitGrantGift(String name) {
    return 'Kyauta: $name';
  }

  @override
  String mutualBenefitGrantDiscountItem(String name) {
    return 'Rangwame akan: $name';
  }

  @override
  String mutualBenefitGrantDiscountGroup(String name) {
    return 'Rangwame akan kungiya: $name';
  }

  @override
  String mutualBenefitPartnerCount(int n) {
    return 'Yarjejeniya $n';
  }

  @override
  String get mutualBenefitProposeResultFail => 'An kasa aika shawara';

  @override
  String get mutualBenefitRefusal402 =>
      'Shagon ku bai yi rajista da app na Amfanin Juna ba — yi rajista daga shagon aikace-aikace tukuna';

  @override
  String get mutualBenefitRefusal403 => 'Ba ka da izinin wannan aikin';

  @override
  String get mutualBenefitRefusal400 =>
      'Bayanan shawara ba daidai ba ne — duba sharadin, ko kana bayar da shawarar hadin gwiwa da kanka';

  @override
  String get mutualBenefitRefusal404 =>
      'Ba a sami shago da wannan lambar ba, ko sabis/kungiyar da aka zaba babu su a cikin kundin sauran shagon';

  @override
  String get mutualBenefitRefusal409 =>
      'Ka kai iyakar hadin gwiwa 3 masu aiki, ko yanayin hadin gwiwa ya canza';

  @override
  String get mutualBenefitRefusal503 =>
      'Ba a samun sabis na kudi na wucin gadi, sake gwadawa daga baya';

  @override
  String get appStoreTitle => 'Kantin App';

  @override
  String get appStoreSubtitle =>
      'Bunkasa shagon ka da apps na gaske, ɗaya bayan ɗaya';

  @override
  String get appStoreTabMine => 'Apps na';

  @override
  String get appStoreTabAll => 'Kantin App';

  @override
  String get appStoreDetails => 'Cikakkun bayanai';

  @override
  String get appStorePerMonth => 'kowane wata';

  @override
  String get appStorePerMonthShort => '/wata';

  @override
  String get appStoreActive => 'Mai aiki';

  @override
  String get appStoreTrialing => 'Gwaji';

  @override
  String get appStoreSubscribe => 'Yi rajista yanzu';

  @override
  String get appStoreCancelRenewal => 'Dakatar da sabuntawa';

  @override
  String get appStoreUndoCancel => 'Soke bata';

  @override
  String get appStoreConfirmCancel =>
      'Dakatar da sabunta wannan app? Zai ci gaba da aiki har zuwa ƙarshen lokacin da aka biya';

  @override
  String appStoreCartCount(int n) {
    return '$n a keken saya';
  }

  @override
  String get appStoreCheckout => 'Kammala Siye';

  @override
  String get appStoreCheckingOut => 'Ana kammala siye...';

  @override
  String get appStoreRefusal402 =>
      'Biyan kuɗi ba a kunna ba a asusun ka yanzu — tuntube mu don kunna shi';

  @override
  String get appStoreRefusal403 => 'Ba ka da izinin kammala wannan sayayya';

  @override
  String get appStoreRefusal404 =>
      'Ba a sami shirin da ake nema ba — sabunta sannan a sake gwadawa';

  @override
  String get appStoreRefusal409 =>
      'An riga an mallaki wannan app, ko yanayinsa ya canza yayin sayayya';

  @override
  String get appStoreRefusalGeneric => 'An kasa kammala sayayya, sake gwadawa';

  @override
  String get appStoreCapacityTitle => 'Iyaka';

  @override
  String appStoreCapacityConfirmRemove(String name) {
    return 'Cire raka na ƙarshe na \"$name\"? Wannan zai dakatar da sabuntawarsa gaba ɗaya';
  }

  @override
  String get appStoreCartSubtotal => 'Jimillar farko';

  @override
  String get appStoreCartDiscount => 'Ragi';

  @override
  String get appStoreCartTax => 'Haraji';

  @override
  String get appStoreCartTotal => 'Jimilla';

  @override
  String get appStoreCartDiscountCaveat =>
      'Wannan farashin ba shi da ragi da haraji tukuna; ainihin adadin za a nuna lokacin biya.';

  @override
  String appStoreCartItemDiscount(int percent) {
    return '(ragi $percent٪)';
  }

  @override
  String appStoreAutoAdded(String added, String trigger) {
    return 'An ƙara \"$added\" kai tsaye domin \"$trigger\" yana buƙatarsa.';
  }

  @override
  String appStoreMissingRequirement(String names) {
    return 'Yana buƙatar kunna $names tukuna.';
  }

  @override
  String get appStoreRequiresAnyVisit => 'Rubuta Ziyara';

  @override
  String get appStoreRequiresAnyBookings => 'Ajiya';

  @override
  String get appStoreRequiresAnyContacts => 'Ma\'amaloli';

  @override
  String get appStoreRequiresAnyMobileRequests => 'Bukatun Waya';

  @override
  String get appStoreRequiresOr => 'ko';

  @override
  String get appStoreOr => 'ko';

  @override
  String appStoreCascadeWarning(String names) {
    return 'Wadannan ma za su dakata: $names';
  }

  @override
  String appStoreDiscountBadge(int percent) {
    return 'An yi ragi na $percent٪';
  }

  @override
  String appStoreDiscountBadgeWithApp(int percent, String app) {
    return 'An yi ragi na $percent٪ daga $app';
  }

  @override
  String appStoreDiscountedShort(int percent) {
    return 'Ragi $percent٪';
  }

  @override
  String appStoreOfferTitle(int percent) {
    return 'Ragin $percent٪ yana jiranka';
  }

  @override
  String appStoreOfferDesc(String app) {
    return 'Zai kunna kansa idan ka yi rijistar $app';
  }

  @override
  String appStoreAiUnitsCount(int units) {
    return 'yunit $units';
  }

  @override
  String get appStoreAiUnitsIncluded => 'AI kyauta kowane wata';

  @override
  String get whatsappAssistantTitle => 'Mataimakin AI';

  @override
  String get whatsappAssistantSubtitle =>
      'Yana amsa wa abokan cinikinka a WhatsApp maimakonka, yana ba da shawarar shirye-shiryenka da maki nasu a daidai lokaci.';

  @override
  String get whatsappAssistantLoadFailed => 'An kasa loda saitunan mataimaki.';

  @override
  String get whatsappAssistantConfirm => 'Tabbatar';

  @override
  String get whatsappAssistantSaveFailed => 'An kasa ajiyewa, a sake gwadawa.';

  @override
  String get whatsappAssistantToggleTitle => 'Mataimaki yana amsawa';

  @override
  String get whatsappAssistantToggleDesc =>
      'Kashe shi zai kulle mataimaki gaba ɗaya, ba tare da soke biyan kuɗinka ba — sake kunna shi kowane lokaci.';

  @override
  String get whatsappAssistantToggleConfirmEnableTitle =>
      'Kunna mataimakin AI?';

  @override
  String get whatsappAssistantToggleConfirmEnableBody =>
      'Zai fara amsa wa abokan cinikinka a WhatsApp nan take.';

  @override
  String get whatsappAssistantToggleConfirmDisableTitle =>
      'Kashe mataimakin AI?';

  @override
  String get whatsappAssistantToggleConfirmDisableBody =>
      'Zai daina amsawa gaba ɗaya, kamar ba ka biya ba — ba tare da soke biyan kuɗin da kansa ba.';

  @override
  String get whatsappAssistantNotesTitle => 'Bayanan shago';

  @override
  String get whatsappAssistantNotesDesc =>
      'Abin da ka rubuta a nan yana taimaka wa mataimaki ya yi wa abokan cinikinka hidima da ƙarin bayani game da shagonka.';

  @override
  String get whatsappAssistantWordLimitTitle =>
      'Iyakar kalmomin saƙon abokin ciniki';

  @override
  String get whatsappAssistantWordLimitDesc =>
      'Mafi tsayin saƙon da mataimaki zai karɓa daga abokin ciniki kafin ya nemi ya taƙaita shi.';

  @override
  String get whatsappAssistantAutoRegisterTitle =>
      'Rijistar mutane ta atomatik';

  @override
  String get whatsappAssistantAutoRegisterDesc =>
      'Duk sabon lambar da ta aiko wa WhatsApp ɗinka za a ajiye ta atomatik a matsayin lamba ta gaske.';

  @override
  String get whatsappAssistantAutoRegisterConfirmEnableTitle =>
      'Kunna rijista ta atomatik?';

  @override
  String get whatsappAssistantAutoRegisterConfirmEnableBody =>
      'Duk wanda ya aiko saƙo zuwa lambar WhatsApp ɗinka za a ajiye shi a matsayin lamba ta atomatik, ko da saƙo ɗaya ne kawai.';

  @override
  String get whatsappAssistantAutoRegisterConfirmDisableTitle =>
      'Kashe rijista ta atomatik?';

  @override
  String get whatsappAssistantAutoRegisterConfirmDisableBody =>
      'Sabbin lambobi ba za a ƙara ajiye su a matsayin lambobi ta atomatik ba.';

  @override
  String get partnerLoyaltyTitle => 'Amincin Abokan Hulɗa';

  @override
  String get partnerLoyaltySubtitle =>
      'Kafa kawance da wani shago da aka yi masa rajista tare da mu, ka ba shi rangwame a kan biyan kuɗinsa';

  @override
  String get partnerLoyaltyCapLabel => 'Iyakar ka ta yanzu';

  @override
  String get partnerLoyaltyPrefsTitle =>
      'Akwatin kafa kawance lokacin rikodin ziyara';

  @override
  String get partnerLoyaltyPrefsDesc =>
      'Kunna shi yana bawa duk wani ma\'aikacin da yake rikodin ziyara damar kafa kawance a lokaci guda.';

  @override
  String get partnerLoyaltyGrantTitle => 'Kafa kawance';

  @override
  String get partnerLoyaltyPhoneLabel => 'Lambar wayar shagon abokin tarayya';

  @override
  String get partnerLoyaltyPhoneHintOk => 'Babu kawance da shi a wannan watan';

  @override
  String get partnerLoyaltyPhoneHintAlready =>
      'Kana da kawance da shi a wannan watan tuni';

  @override
  String get partnerLoyaltyPhoneHintUnregistered =>
      'Wannan lambar ba shago ne da aka yi masa rajista tare da mu ba';

  @override
  String get partnerLoyaltyPercentLabel => 'Kason rangwame';

  @override
  String partnerLoyaltyCapLine(int p) {
    return 'Mafi girman kaso da za ka iya bayarwa yanzu: $p%';
  }

  @override
  String get partnerLoyaltyScopeLabel => 'Ya haɗa da';

  @override
  String get partnerLoyaltyScopeAll => 'Duka';

  @override
  String get partnerLoyaltySubmit => 'Kafa kawancen';

  @override
  String get partnerLoyaltySubmitting => 'Ana tura…';

  @override
  String get partnerLoyaltyResultSuccess =>
      'An kafa kawance — zai shiga aiki kai tsaye a lokacin sabunta biyan kuɗin shagon na gaba.';

  @override
  String get partnerLoyaltyResultPartial =>
      'An kafa wani ɓangare — an ƙi wasu app, buɗe «Rikodi» don ƙarin bayani.';

  @override
  String get partnerLoyaltyOutcomeGranted => 'Nasara';

  @override
  String get partnerLoyaltyOutcomeInvalidPercent =>
      'Kason rangwame ba daidai ba ne';

  @override
  String get partnerLoyaltyOutcomeInvalidScope => 'Zaɓi app na gaske';

  @override
  String get partnerLoyaltyOutcomeOverCap => 'Ya wuce iyakar ka ta yanzu';

  @override
  String get partnerLoyaltyOutcomeNoAccount =>
      'Wannan lambar ba shago ne da aka yi masa rajista tare da mu ba';

  @override
  String get partnerLoyaltyOutcomeNotSubscribed =>
      'Shagon ba shi da wani app daga cikin abin da ka zaɓa';

  @override
  String get partnerLoyaltyOutcomeBillingUnavailable =>
      'Ba a kammala ba, sake gwadawa';

  @override
  String get partnerLoyaltyOutcomeAlreadyHasBetterCoupon =>
      'Yana da rangwame mafi ƙarfi tuni';

  @override
  String get partnerLoyaltyOutcomeCouponExpired => 'Rangwame ya ƙare';

  @override
  String get partnerLoyaltyOutcomeCouponExhausted =>
      'An gama amfani da rangwame';

  @override
  String get partnerLoyaltyOutcomeCouponUnknown =>
      'Rangwame wanda ba a sani ba';

  @override
  String get partnerLoyaltyOutcomePlanMismatch =>
      'Rangwame bai dace da wannan app ba';

  @override
  String get partnerLoyaltyOutcomeCouponDisabled => 'An kashe rangwame';

  @override
  String get partnerLoyaltyOutcomeCouponScheduled =>
      'Rangwame bai fara ba tukuna';

  @override
  String get partnerLoyaltyTabLog => 'Rikodi';

  @override
  String get partnerLoyaltyTabStats => 'Ƙidaya';

  @override
  String get partnerLoyaltyLogSearchHint => 'Bincika ta lambobi 4 na ƙarshe';

  @override
  String get partnerLoyaltyLogFilterAll => 'Dukan matsayi';

  @override
  String get partnerLoyaltyLogFilterOk => 'Masu nasara kawai';

  @override
  String get partnerLoyaltyLogFilterFail => 'Masu gazawa kawai';

  @override
  String get partnerLoyaltyLogEmptyTitle => 'Babu wani kawance tukuna';

  @override
  String get partnerLoyaltyLogEmptyDesc =>
      'Kawancen ka na farko zai bayyana anan.';

  @override
  String get partnerLoyaltyLogReadFailed => 'Ba a iya karanta rikodin ba';

  @override
  String get partnerLoyaltyStatsKpiMonth => 'Kawance a wannan watan';

  @override
  String get partnerLoyaltyStatsKpiCap => 'Iyakar ka ta yanzu';

  @override
  String get partnerLoyaltyStatsKpiCeiling => 'Babbar iyaka ta dandali';

  @override
  String get partnerLoyaltyStatsLadderTitle => 'Matsayinka a kan matakala';

  @override
  String partnerLoyaltyStatsLadderNote(int n, int left, int p) {
    return 'Kawance $n a wannan watan — sauran $left don kai matakin $p%';
  }

  @override
  String partnerLoyaltyStatsLadderAtTop(int n) {
    return 'Kawance $n a wannan watan — kana kan matakin da ya fi girma';
  }

  @override
  String partnerLoyaltyStatsCeilingNote(int p) {
    return 'Babbar iyaka ta dandali $p% — babu shagon da ya taɓa wucewa';
  }

  @override
  String get partnerLoyaltyStatsChartTitle =>
      'Kawance a cikin watanni 6 na ƙarshe';

  @override
  String get partnerLoyaltyReadFailedTitle => 'Ba a iya karanta bayanan ka ba';

  @override
  String get partnerLoyaltyReadFailedDesc => 'Sake gwadawa bayan ɗan lokaci.';

  @override
  String get shopReadFailed => 'Ba a iya karanta alamun shagon ka ba';

  @override
  String get shopMultiBranchTitle => 'Zaɓi reshe';

  @override
  String get shopMultiBranchDesc =>
      'Kana da fiye da reshe ɗaya — zaɓi ɗaya don ganin alamunsa.';

  @override
  String get shopEmptyBranchTitle => 'Babu bayani na wannan reshe tukuna';

  @override
  String get shopRetentionTitle => 'Yawan dawowar abokan cinikin ka';

  @override
  String get shopRetentionMutedNote =>
      'Babu isassun ziyara don lissafa wannan tukuna.';

  @override
  String get shopRetentionBrandNew =>
      'Yi rijistar ziyara ta farko don fara ganin yawan dawowar abokan ciniki.';

  @override
  String get shopRegisterFirstVisit => 'Yi rijistar ziyara ta farko';

  @override
  String get shopRetentionPrefix10 =>
      'Daga cikin kowane abokan ciniki 10 da suka ziyarce ka,';

  @override
  String get shopRetentionSuffix => 'suke dawowa';

  @override
  String get shopOneCustomer => 'Abokin ciniki ɗaya ya ziyarce ka';

  @override
  String shopNCustomers(int n) {
    return 'Abokan ciniki $n sun ziyarce ka';
  }

  @override
  String shopRetentionSmallPrefix(String base) {
    return '$base, daga cikinsu';
  }

  @override
  String shopOverNMonths(int n) {
    return 'cikin watanni $n';
  }

  @override
  String get shopUnlimited => 'Ba iyaka';

  @override
  String get shopTileSentToday => 'An aika yau';

  @override
  String get shopTileWaiting => 'Ana jira';

  @override
  String get shopTileCeilingRemaining => 'Sauran yau';

  @override
  String get shopNextStepLabel => 'Mataki na gaba';

  @override
  String get shopNotNow => 'Ba yanzu ba';

  @override
  String get shopDeckUrgent => 'Gaggawa';

  @override
  String get shopDeckWeek => 'Wannan makon';

  @override
  String get shopDeckOpportunities => 'Damarmaki';

  @override
  String get shopComputedNow => 'An lissafa yanzu';

  @override
  String shopComputedHoursAgo(int n) {
    return 'An lissafa awa $n da suka wuce';
  }

  @override
  String get shopStale => 'Tsohuwa';

  @override
  String get shopRefreshAction => 'Sabunta';

  @override
  String get shopComputingTitle => 'Ana lissafa alamunka';

  @override
  String get shopComputeLoading => 'Ana lissafawa…';

  @override
  String get shopComputeAction => 'Lissafa yanzu';

  @override
  String get shopAtRiskTitle => 'Abokan ciniki kusa da barin ka';

  @override
  String get shopAtRiskMutedNote => 'Babu isassun bayanai tukuna.';

  @override
  String get shopAtRiskAllGood =>
      'Babu abokin ciniki da ya makara yanzu — komai lafiya';

  @override
  String get shopWaNotConnected => 'WhatsApp na shagon ka bai haɗu ba tukuna';

  @override
  String get shopWaNotVerified =>
      'Lambar WhatsApp ta shagon ka ba a tabbatar da ita ba tukuna';

  @override
  String get shopCeilingReached => 'Ka kai iyakar saƙonni na yau';

  @override
  String shopDaysOverdue(int n) {
    return 'Kwana $n da suka wuce';
  }

  @override
  String get shopAtRiskCta => 'Aika yaƙin neman dawowa';

  @override
  String get shopAiImpactTitle => 'Tasirin Mataimaki na AI ta WhatsApp';

  @override
  String get shopAiConversations => 'Tattaunawa';

  @override
  String get shopAiBookings => 'Ajiye lokaci';

  @override
  String get shopAiUpsellRate => 'Karɓar ƙarin tayi';

  @override
  String get shopWeekMutedTitle => 'Ziyarar wannan makon';

  @override
  String get shopWeekMutedNote => 'Babu isassun bayanai tukuna.';

  @override
  String get shopNewReturningMutedTitle =>
      'Sabbin abokan ciniki da masu dawowa';

  @override
  String get shopNewReturningMutedNote => 'Babu isassun bayanai tukuna.';

  @override
  String get shopBranchCompareTitle => 'Kwatanta rassa';

  @override
  String get shopBranchCompareMutedNote =>
      'Ana buƙatar rassa biyu a kalla don kwatantawa.';

  @override
  String get shopStaffCompareTitle => 'Kwatanta ma\'aikata';

  @override
  String get shopStaffCompareMutedNote =>
      'Ana buƙatar ma\'aikata biyu a kalla don kwatantawa.';

  @override
  String get shopWeekTitle => 'Ziyara a wannan makon';

  @override
  String get shopNewReturningTitle => 'Sabbi da masu dawowa';

  @override
  String get shopNewLabel => 'Sabbi:';

  @override
  String get shopReturningLabel => 'Masu dawowa:';

  @override
  String get shopServicesTitle => 'Ayyukanka';

  @override
  String get shopServicesMutedNote => 'Babu isassun bayanai tukuna.';

  @override
  String get shopMessageFlowTitle => 'Tasirin saƙon tuni';

  @override
  String get shopMutedMessageFlowNote => 'Babu isassun bayanai tukuna.';

  @override
  String get shopHoldoutTitle =>
      'Kwatanta wanda aka aika masa da wanda ba a aika masa ba';

  @override
  String get shopMutedHoldoutNote => 'Ana auna har yanzu.';

  @override
  String shopReturnedAfterReminder(int visits, int days) {
    return 'Ziyara $visits cikin kwanaki $days bayan tuni';
  }

  @override
  String shopOptOutRate(String p) {
    return '$p% sun nemi a daina musu saƙonni';
  }

  @override
  String get shopHoldoutNoMessages => 'Babu saƙo';

  @override
  String get shopHoldoutReached => 'An aika saƙo';

  @override
  String get shopHoldoutOff =>
      'Auna tasirin saƙonni a kashe yake — duk abokan cinikinka suna karɓar komai, don haka babu ƙungiyar kwatantawa.';

  @override
  String shopHoldoutMeasuring(int min, int need) {
    return 'Muna ci gaba da auna tasirin saƙonni a shagonka — $min daga cikin $need a ƙaramar ƙungiya.';
  }

  @override
  String shopTodayRetrying(int n) {
    return 'Saƙo $n yana ƙoƙarin fita';
  }

  @override
  String get shopTrendUp => 'yana inganta';

  @override
  String get shopTrendDown => 'yana raguwa';

  @override
  String shopRetentionSincePeriods(int n) {
    return 'tun lokuta $n';
  }

  @override
  String get shopAtLeastSuffix => ' — a kalla';

  @override
  String get shopRegisterFirstVisitArrow => 'Rubuta ziyara ta farko ←';

  @override
  String get shopWeekNoCompare =>
      'Ba mu da cikakken mako tukuna don kwatantawa';

  @override
  String shopNextStepAlso(String msg) {
    return 'Haka kuma: $msg';
  }

  @override
  String shopBranchCompareUnassigned(int n) {
    return 'Ziyara $n ba tare da reshe ba — ba a lissafta ga kowane reshe ba.';
  }

  @override
  String get shopBranchCompareNeedTwo =>
      'Ba mu kwatanta rassa tukuna ba — ana buƙatar rassa biyu ko fiye da ziyara na gaske.';

  @override
  String get shopBranchCompareNeedSecond =>
      'Reshe ɗaya mai aiki har yanzu — kwatantawa tana buƙatar reshe na biyu da ziyara na gaske.';

  @override
  String get shopBranchCompareTooShort =>
      'Ba mu tsara rassa tukuna ba — lokacin ya yi gajarta, kuma kwatantawa yanzu za ta zalunci sabon.';

  @override
  String shopStaffCompareUnassigned(int n) {
    return 'Ziyara $n ba tare da ma\'aikaci ba — ba a lissafta ga kowa ba.';
  }

  @override
  String get shopStaffCompareNeedTwo =>
      'Ba mu kwatanta ma\'aikata tukuna ba — ana buƙatar ma\'aikata biyu ko fiye da ziyara da aka danganta.';

  @override
  String get shopStaffCompareNeedSecond =>
      'Ma\'aikaci ɗaya an danganta har yanzu — kwatantawa tana buƙatar na biyu da ziyara na gaske.';

  @override
  String get shopStaffCompareTooShort =>
      'Ba mu tsara ma\'aikata tukuna ba — lokacin ya yi gajarta, kuma kwatantawa yanzu za ta zalunci sabon.';

  @override
  String get shopPeakTitle => 'Lokutanka mafi cika';

  @override
  String get shopPeakMutedNote =>
      'Ana buƙatar ziyara da suka bazu a kwanaki da sa\'o\'i isassu don zana su.';

  @override
  String shopPeakBusiestTime(String day, int h) {
    return '$day kusan ƙarfe $h:00';
  }

  @override
  String shopPeakBusiestNote(String name) {
    return 'Lokacinka mafi cika: $name.';
  }

  @override
  String get shopEntityDayServicesTitle => 'Ayyukanka bisa ranar mako';

  @override
  String get shopEntityDayServicesHint =>
      'Wane sabis ake buƙata sosai a wata rana — yana taimaka maka shirya ma\'aikatan da suka dace ranar.';

  @override
  String get shopEntityDayServicesMutedNote =>
      'Ana buƙatar ziyara da suka bazu a kwanaki isassu don zana su.';

  @override
  String get shopEntityDayBranchesTitle => 'Rassanka bisa ranar mako';

  @override
  String get shopEntityDayBranchesHint =>
      'Rassanka ba dole ne su raba salo ɗaya ba — reshen mall yana cika a hutu, reshen unguwa yana cika bayan aiki.';

  @override
  String get shopEntityDayBranchesMutedNote =>
      'Ana buƙatar reshe na biyu da ziyara da suka bazu a kwanaki isassu don zana su.';

  @override
  String get shopBundlesTitle => 'Kunshin da aka ba da shawara';

  @override
  String get shopBundlesMutedNote =>
      'Babu isassun alaƙa tukuna don ba da shawarar kunshi daga ciki.';

  @override
  String shopBundlesOpportunity(int n) {
    return 'Dama $n';
  }

  @override
  String get shopAssociationsTitle => 'Ana buƙata tare sau da yawa';

  @override
  String get shopAssociationsMutedNote => 'Babu isassun alaƙa tukuna.';

  @override
  String shopAssociationsLearningNote(int have, int need) {
    return 'Ba mu san tukuna abin da ake buƙata tare da me ba — gano alaƙa yana buƙatar ƙarin ziyara don sakamakon ya zama na gaske, ba na kwatsam ba. ($have/$need)';
  }

  @override
  String shopCustomersCount(int n) {
    return 'Abokan ciniki $n';
  }

  @override
  String get shopDay0Short => 'Lh';

  @override
  String get shopDay1Short => 'Li';

  @override
  String get shopDay2Short => 'Ta';

  @override
  String get shopDay3Short => 'La';

  @override
  String get shopDay4Short => 'Al';

  @override
  String get shopDay5Short => 'Ju';

  @override
  String get shopDay6Short => 'As';

  @override
  String get shopDay0Full => 'Lahadi';

  @override
  String get shopDay1Full => 'Litinin';

  @override
  String get shopDay2Full => 'Talata';

  @override
  String get shopDay3Full => 'Laraba';

  @override
  String get shopDay4Full => 'Alhamis';

  @override
  String get shopDay5Full => 'Jumma\'a';

  @override
  String get shopDay6Full => 'Asabar';

  @override
  String get shopMissedTitle =>
      'Abokan ciniki da ba su gwada duk abin da ya dace da su ba';

  @override
  String get shopMissedMutedNote =>
      'Babu abokan ciniki bayyanannu tukuna waɗanda suka rasa sabis da ake saye tare da nasu.';

  @override
  String get shopCustomerFallback => 'Abokin ciniki';

  @override
  String get shopKpiActiveCustomers => 'Abokan ciniki masu aiki';

  @override
  String get shopKpiReturnCycle => 'Zagayen dawowa';

  @override
  String shopDaysSuffix(int n) {
    return 'kwana $n';
  }

  @override
  String get shopKpiChurnRate => 'Barin abokan ciniki';

  @override
  String get shopTileServicesPerVisit => 'Ayyuka a kowace ziyara';

  @override
  String get shopTileExpectedNextWeek => 'Ana tsammani mako mai zuwa';

  @override
  String get shopTileCycleCompletion => 'Bin zagayen komowa';

  @override
  String get shopPerVisitMutedTitle => 'Ayyuka a kowace ziyara, da bin zagaye';

  @override
  String get shopPerVisitMutedNote =>
      'Ana buƙatar ziyara na gaske tukuna don lissafawa.';

  @override
  String get shopLeadConversionTitle =>
      'Sauyawar waɗanda suka fara tuntuɓar ka';

  @override
  String shopLeadConversionDetail(int converted, int total) {
    return '$converted daga cikin $total sun zama ziyara ta gaske';
  }

  @override
  String get whatsappOrdersTitle => 'Oda kai tsaye ta WhatsApp';

  @override
  String get whatsappOrdersSubtitle =>
      'Odar da abokan cinikinka suke yi daga kayanka ta WhatsApp, daga isowa zuwa kai wa.';

  @override
  String get whatsappOrdersKpiWaiting => 'Ana jiran dubawa';

  @override
  String get whatsappOrdersKpiStuck => 'Sun jima';

  @override
  String get whatsappOrdersKpiDeliveredToday => 'An kai yau';

  @override
  String get whatsappOrdersFilterAll => 'Duka';

  @override
  String get whatsappOrdersFilterIncoming => 'Sabbi';

  @override
  String get whatsappOrdersFilterConfirmed => 'An tabbatar';

  @override
  String get whatsappOrdersFilterPreparing => 'Ana shiryawa';

  @override
  String get whatsappOrdersFilterReady => 'A shirye';

  @override
  String get whatsappOrdersFilterDelivery => 'Ana kai wa';

  @override
  String get whatsappOrdersFilterClosed => 'An kammala';

  @override
  String get whatsappOrdersLoadFailedTitle => 'An kasa loda oda';

  @override
  String get whatsappOrdersLoadFailedBody =>
      'Duba hanyar sadarwarka kuma sake gwadawa.';

  @override
  String get whatsappOrdersRetry => 'Sake gwadawa';

  @override
  String get whatsappOrdersEmptyTitle => 'Babu oda tukuna';

  @override
  String get whatsappOrdersEmptyBody =>
      'Duk wata oda da ta zo ta WhatsApp za ta bayyana nan take.';

  @override
  String get whatsappOrdersUnnamed => 'Abokin ciniki';

  @override
  String get whatsappOrdersStatusReceived => 'Sabo';

  @override
  String get whatsappOrdersStatusPaymentMismatch => 'Rashin daidaiton biya';

  @override
  String get whatsappOrdersStatusConfirmed => 'An tabbatar';

  @override
  String get whatsappOrdersStatusPreparing => 'Ana shiryawa';

  @override
  String get whatsappOrdersStatusReady => 'A shirye';

  @override
  String get whatsappOrdersStatusOutForDelivery => 'Ana kai wa';

  @override
  String get whatsappOrdersStatusDelivered => 'An kai';

  @override
  String get whatsappOrdersStatusCancelled => 'An soke';

  @override
  String get whatsappOrdersStuckBadge => 'Ya jima';

  @override
  String get whatsappOrdersOpenMap => 'Bude wurin a taswira';

  @override
  String get whatsappOrdersPhoneCopied => 'An kwafi lambar waya';

  @override
  String get whatsappOrdersActionStartPreparing => 'Fara shiryawa';

  @override
  String get whatsappOrdersActionMarkReady => 'Alamta a shirye';

  @override
  String get whatsappOrdersActionStartDelivery => 'Aika don kaiwa';

  @override
  String get whatsappOrdersActionMarkDelivered => 'Alamta an kai';

  @override
  String get whatsappOrdersActionResolveMismatch => 'Tabbatar da biya da hannu';

  @override
  String get whatsappOrdersActionCancel => 'Soke oda';

  @override
  String get whatsappOrdersActionFailed =>
      'An kasa kammala aikin, sake gwadawa.';

  @override
  String get whatsappOrdersCancelReasonPrompt => 'Dalilin sokewa (ba tilas ba)';

  @override
  String get whatsappOrdersCancelReasonCancel => 'Koma baya';

  @override
  String get whatsappOrdersCancelReasonConfirm => 'Tabbatar da sokewa';

  @override
  String get whatsappOrdersPauseLabel => 'Dakatar da karɓar oda';

  @override
  String whatsappOrdersPauseBannerText(String reason) {
    return 'Wannan reshe ba ya karɓar sabbin odar WhatsApp — $reason';
  }

  @override
  String get whatsappOrdersPauseDefaultReason =>
      'Kashiya ta dakatar na ɗan lokaci';

  @override
  String get whatsappOrdersDrawerSubtotal => 'Jimla kafin ragi';

  @override
  String get whatsappOrdersDrawerDiscount => 'Ragi';

  @override
  String get whatsappOrdersDrawerPointsReward => 'Lada na makin aminci';

  @override
  String get whatsappOrdersDrawerTotal => 'Jimlar da ake bukata';

  @override
  String whatsappOrdersDrawerMismatchHint(String paid) {
    return 'Adadin da gidan biya ya bayar ($paid) bai dace da abin da ake bukata ba — duba da kanka kafin tabbatarwa.';
  }

  @override
  String whatsappOrdersDrawerCancelReason(String reason) {
    return 'Dalilin sokewa: $reason';
  }

  @override
  String whatsappOrdersDrawerNote(String note) {
    return 'Bayani: $note';
  }
}
