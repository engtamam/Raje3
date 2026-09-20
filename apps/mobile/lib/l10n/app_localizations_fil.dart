// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Filipino Pilipino (`fil`).
class SFil extends S {
  SFil([String locale = 'fil']) : super(locale);

  @override
  String get appName => 'Raje3';

  @override
  String get ok => 'OK';

  @override
  String get cancel => 'Kanselahin';

  @override
  String get close => 'Isara';

  @override
  String get next => 'Susunod';

  @override
  String get done => 'Tapos na';

  @override
  String get loading => 'Naglo-load...';

  @override
  String get retry => 'Subukan muli';

  @override
  String get error => 'May naganap na error';

  @override
  String get success => 'Matagumpay';

  @override
  String get login => 'Mag-log in';

  @override
  String get logout => 'Mag-log out';

  @override
  String get validatorFieldRequiredGeneric => 'Kailangan ang field na ito';

  @override
  String validatorFieldRequiredNamed(String field) {
    return 'Kailangan ang $field';
  }

  @override
  String get validatorEmailRequired => 'Kailangan ang email';

  @override
  String get validatorEmailInvalid => 'Hindi wasto ang email address';

  @override
  String get validatorPhoneRequired => 'Kailangan ang numero ng telepono';

  @override
  String get validatorPhoneInvalid =>
      'Hindi wasto ang numero ng telepono — dapat magsimula sa 05';

  @override
  String get validatorPasswordRequired => 'Kailangan ang password';

  @override
  String get validatorPasswordTooShort =>
      'Ang password ay dapat may hindi bababa sa 8 na karakter';

  @override
  String get validatorPasswordNeedsUppercase =>
      'Ang password ay dapat may malaking titik';

  @override
  String get validatorPasswordNeedsLowercase =>
      'Ang password ay dapat may maliit na titik';

  @override
  String get validatorPasswordNeedsDigit => 'Ang password ay dapat may numero';

  @override
  String get validatorConfirmPasswordFieldName => 'Kumpirmahin ang password';

  @override
  String get validatorPasswordMismatch => 'Hindi magkatugma ang mga password';

  @override
  String get validatorOtpRequired => 'Kailangan ang verification code';

  @override
  String get validatorOtpLength => 'Ang verification code ay dapat 6 na digit';

  @override
  String get validatorOtpDigitsOnly =>
      'Ang verification code ay dapat mga numero lamang';

  @override
  String get validatorNameRequired => 'Kailangan ang pangalan';

  @override
  String get validatorNameTooShort =>
      'Ang pangalan ay dapat may hindi bababa sa 2 na karakter';

  @override
  String get validatorNameTooLong =>
      'Ang pangalan ay hindi dapat lumampas sa 100 na karakter';

  @override
  String get validatorNameInvalidChars =>
      'Ang pangalan ay may mga karakter na hindi pinapayagan';

  @override
  String get validatorGenericFieldName => 'Ang field na ito';

  @override
  String validatorMinLengthNamed(String field, int minLength) {
    return 'Ang $field ay dapat may hindi bababa sa $minLength na karakter';
  }

  @override
  String validatorMaxLengthNamed(String field, int maxLength) {
    return 'Ang $field ay hindi dapat lumampas sa $maxLength na karakter';
  }

  @override
  String get validatorGenericValueName => 'Ang halaga';

  @override
  String validatorNotANumberNamed(String field) {
    return 'Ang $field ay dapat isang numero';
  }

  @override
  String validatorMinValueNamed(String field, String min) {
    return 'Ang $field ay dapat hindi bababa sa $min';
  }

  @override
  String validatorMaxValueNamed(String field, String max) {
    return 'Ang $field ay hindi dapat lumampas sa $max';
  }

  @override
  String get validatorUrlRequired => 'Kailangan ang URL';

  @override
  String get validatorUrlInvalid => 'Hindi wasto ang URL';

  @override
  String get urlHelperUnavailable => 'Hindi available ang link';

  @override
  String get urlHelperOpenFailed => 'Hindi mabuksan ang link';

  @override
  String get routerScreenNotOnMobileYet =>
      'Hindi pa available ang screen na ito sa mobile app.';

  @override
  String get authLoginSubtitle => 'Mag-sign in para magpatuloy';

  @override
  String get authPhoneLabel => 'Numero ng mobile';

  @override
  String get authPasswordLabel => 'Password';

  @override
  String get authNoShopYetLabel => 'Wala ka pa bang tindahan?';

  @override
  String get authOpenNewShopCta => 'Magbukas ng bagong tindahan';

  @override
  String get authOpenShopTitle => 'Pagbubukas ng bagong tindahan';

  @override
  String get authSignupSubtitle =>
      'Tatlong hakbang lamang para buksan ang iyong tindahan';

  @override
  String get authShopNameLabel => 'Pangalan ng tindahan';

  @override
  String get authAlreadyHaveShopCta => 'May tindahan ka na? Mag-log in';

  @override
  String get authOpenShopCta => 'Buksan ang tindahan';

  @override
  String get authVerifyPhoneTitle => 'I-verify ang numero ng mobile';

  @override
  String authVerifyCodeSentTo(String phone) {
    return 'Nagpadala kami ng verification code sa $phone';
  }

  @override
  String get authVerifying => 'Nagve-verify...';

  @override
  String get authConfirmCta => 'Kumpirmahin';

  @override
  String get authResendCodeCta => 'Ipadala muli ang code';

  @override
  String get authSendCodeCta => 'Ipadala ang code';

  @override
  String get authCodeSendFailedFallback => 'Hindi maipadala ang code.';

  @override
  String get authOtpIncorrectFallback => 'Mali ang verification code.';

  @override
  String get visitCatalogueLoadErrorFallback =>
      'Hindi ma-load ang mga serbisyo. I-pull down para subukan muli.';

  @override
  String get visitEnterCustomerPhone =>
      'Ilagay ang numero ng mobile ng customer';

  @override
  String get visitSelectAtLeastOneService => 'Pumili ng kahit isang serbisyo';

  @override
  String get visitSavedMessage => 'Naitala na ang pagbisita.';

  @override
  String get visitSaveErrorFallback => 'Hindi maitala ang pagbisita.';

  @override
  String get visitSaveErrorNetworkFallback =>
      'Hindi maitala ang pagbisita. Suriin ang iyong koneksyon at subukan muli.';

  @override
  String get visitTitle => 'Magtala ng pagbisita';

  @override
  String get visitCustomerPhoneFieldLabel => 'Numero ng mobile ng customer';

  @override
  String visitKnownCustomer(String name) {
    return 'Kilalang customer: $name';
  }

  @override
  String get visitNewCustomer => 'Bagong customer';

  @override
  String get visitServicesSectionTitle => 'Mga Serbisyo';

  @override
  String get visitNoServicesYet => 'Wala pang serbisyo.';

  @override
  String get visitNoteSectionTitle => 'Tala (opsyonal)';

  @override
  String get visitSaveButtonLabel => 'I-save ang pagbisita';
}
