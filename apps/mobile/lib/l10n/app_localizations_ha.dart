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
  String get navAppsLabel => 'Manhajojina';

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
  String get branchesRoleManager => 'Manaja';

  @override
  String get branchesSeatLimit =>
      'Tsarinka na yanzu ba ya barin ƙarin ma\'aikaci.';

  @override
  String get branchesHireFailed => 'An kasa ƙara ma\'aikaci, sake gwadawa.';

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
  String visitPointsRedeemedMessage(Object name) {
    return 'An musanya $name ✓';
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
}
