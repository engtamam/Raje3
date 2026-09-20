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
  String get navAnalyticsLabel => 'Bincike';

  @override
  String get navHomeLabel => 'Gida';

  @override
  String get navAccountLabel => 'Asusuna';

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
}
