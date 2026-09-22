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
  String get save => 'I-save';

  @override
  String get close => 'Isara';

  @override
  String get back => 'Bumalik';

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
  String get search => 'Maghanap';

  @override
  String get login => 'Mag-log in';

  @override
  String get logout => 'Mag-log out';

  @override
  String get homeDashboardTitle => 'Dashboard';

  @override
  String get homeShopSectionLabel => 'Aking tindahan';

  @override
  String get homeLoadErrorTitle => 'Hindi ma-load';

  @override
  String get homeLoadErrorMessage =>
      'Hindi na-load ang datos ngayong araw. Subukan muli.';

  @override
  String get homeTodaySectionTitle => 'Ngayon';

  @override
  String get homeStatSent => 'Naipadala';

  @override
  String get homeStatWaiting => 'Naghihintay';

  @override
  String get homeStatRetrying => 'Sinusubukan muli';

  @override
  String get homeDashboardComputing =>
      'Kinukuwenta ang mga sukatan ng iyong tindahan — i-refresh mamaya.';

  @override
  String get homeDashboardSectionTitle => 'Mga sukatan ng tindahan';

  @override
  String get homeDashboardEmpty => 'Wala pang sapat na datos.';

  @override
  String get themeDarkMode => 'Madilim na mode';

  @override
  String get themeLightMode => 'Maliwanag na mode';

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
  String get kbHintNoEntry => 'Wala pang paliwanag para dito.';

  @override
  String get assistantChatTitle => 'Katulong';

  @override
  String get assistantInputHint => 'I-type ang iyong tanong...';

  @override
  String get assistantSend => 'Ipadala';

  @override
  String get assistantUnavailable => 'Hindi available ang katulong ngayon.';

  @override
  String get assistantPreparing => 'Inihahanda ang katulong...';

  @override
  String get assistantSpeak => 'Pakinggan ang sagot';

  @override
  String get assistantStopSpeaking => 'Itigil ang pagsasalita';

  @override
  String get assistantActionUnavailable => 'Hindi mo magagawa ito ngayon.';

  @override
  String get assistantConfirm => 'Kumpirmahin';

  @override
  String get assistantCancel => 'Kanselahin';

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
  String get authOwnerNameLabel => 'Pangalan mo (opsyonal)';

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
  String get visitCustomerSectionTitle => 'Customer';

  @override
  String get visitCustomerPhoneFieldLabel => 'Numero ng mobile ng customer';

  @override
  String get visitPlateFieldLabel => 'Numero ng plaka';

  @override
  String get visitPlateRequired =>
      'Maglagay ng tamang plaka (kahit isang letra at isang numero)';

  @override
  String visitKnownVehicle(String name) {
    return 'Kilalang sasakyan: $name';
  }

  @override
  String get visitNewVehicle => 'Bagong sasakyan';

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

  @override
  String get navAppsLabel => 'Mga app ko';

  @override
  String get navHomeLabel => 'Home';

  @override
  String get navAccountLabel => 'Account ko';

  @override
  String get homeGreetingMorning => 'Magandang umaga';

  @override
  String get homeGreetingEvening => 'Magandang gabi';

  @override
  String homeGreetingMorningNamed(String name) {
    return 'Magandang umaga, $name';
  }

  @override
  String homeGreetingEveningNamed(String name) {
    return 'Magandang gabi, $name';
  }

  @override
  String get homeAppsSectionTitle => 'Mga app mo';

  @override
  String get homeFeaturedStartNow => 'Simulan na';

  @override
  String get homeEmptyStateTitle => 'Wala pang available na app';

  @override
  String get homeEmptyStateBody =>
      'Makipag-ugnayan sa may-ari ng tindahan para idagdag ang iyong pahintulot.';

  @override
  String get appsScreenTitle => 'Mga app ko';

  @override
  String get appsScreenHint =>
      'Pindutin ang pin icon para i-pin ang isang app sa ika-5 slot ng ibabang bar';

  @override
  String get appsPinnedBadge => 'Naka-pin sa bar';

  @override
  String get appsPinAction => 'I-pin dito';

  @override
  String get homeLauncherEmptyTitle => 'Walang available na app';

  @override
  String get homeLauncherEmptyMessage =>
      'Makipag-ugnayan sa support para i-activate ang isang app para sa iyong tindahan';

  @override
  String get accountScreenTitle => 'Account ko';

  @override
  String get accountPhoneLabel => 'Numero ng telepono';

  @override
  String get accountLogoutAction => 'Mag-log out';

  @override
  String get accountLogoutConfirmTitle => 'Mag-log out';

  @override
  String get accountLogoutConfirmMessage =>
      'Gusto mo bang mag-log out sa iyong account?';

  @override
  String get notificationsUnavailable =>
      'Hindi pa available ang mga notification';

  @override
  String get notificationsTitle => 'Mga Notification';

  @override
  String get notificationsEmptyState => 'Wala pang notification';

  @override
  String get notificationsAgoJustNow => 'Ngayon lang';

  @override
  String notificationsAgoMinutes(int n) {
    return '${n}m ang nakalipas';
  }

  @override
  String notificationsAgoHours(int n) {
    return '${n}h ang nakalipas';
  }

  @override
  String get notificationsAgoYesterday => 'Kahapon';

  @override
  String notificationsAgoDays(int n) {
    return '${n}d ang nakalipas';
  }

  @override
  String get accountPageTitle => 'Aking Account';

  @override
  String get accountLegalSectionTitle => 'Legal';

  @override
  String get accountTermsRow => 'Mga Tuntunin at Kundisyon';

  @override
  String get accountPrivacyRow => 'Patakaran sa Privacy';

  @override
  String get accountSignOutRow => 'Mag-sign out';

  @override
  String get accountSignOutConfirmTitle => 'Mag-sign out?';

  @override
  String get accountSignOutConfirmBody =>
      'Kakailanganin mong mag-sign in muli para magpatuloy.';

  @override
  String get accountSignOutCancel => 'Kanselahin';

  @override
  String get accountSignOutConfirm => 'Mag-sign out';

  @override
  String get accountNameFieldHint => 'Ang iyong pangalan';

  @override
  String get accountSaveNameFailed =>
      'Hindi na-save ang pangalan, subukan ulit.';

  @override
  String get accountShopSectionTitle => 'Aking tindahan';

  @override
  String get accountShopIdentityRow => 'Aking tindahan';

  @override
  String get shopIdentityPageTitle => 'Aking tindahan';

  @override
  String get shopIdentityVehicleTitle => 'Gumagana sa mga sasakyan';

  @override
  String get shopIdentityVehicleDesc =>
      'Ina-on ang field ng plate number sa visit screen para sa tindahang ito.';

  @override
  String get shopIdentityVehicleSaveFailed => 'Hindi na-save, subukan ulit.';

  @override
  String get shopIdentityBrandTitle => 'Pangalan at logo ng tindahan mo';

  @override
  String get shopIdentityCustomerPagePreview =>
      'Ito ang nakikita ng kustomer mo';

  @override
  String get shopIdentityNameLabel => 'Pangalan ng tindahan';

  @override
  String get shopIdentityUploadLogo => 'Mag-upload ng logo';

  @override
  String get shopIdentityChangeLogo => 'Palitan ang logo';

  @override
  String get shopIdentityRemoveLogo => 'Alisin';

  @override
  String get shopIdentityColorLabel => 'Kulay ng tindahan mo';

  @override
  String get shopIdentityResetColor => 'Gamitin ang default';

  @override
  String get shopIdentitySave => 'I-save';

  @override
  String get shopIdentityDefaultName => 'Ang tindahan mo';

  @override
  String get shopIdentityLogoPickFailed =>
      'Hindi mabasa ang larawan, subukan ang iba.';

  @override
  String get shopIdentityInvalidColor =>
      'Maglagay ng tamang kulay, tulad ng #B08A3E';

  @override
  String get shopIdentitySaveFailed => 'Hindi na-save, subukan ulit.';

  @override
  String get shopIdentitySaved => 'Na-save na.';

  @override
  String get shopIdentityBranchesRow => 'Mga Sangay';

  @override
  String get branchesPageTitle => 'Mga Sangay';

  @override
  String get branchesAddBranch => 'Magdagdag ng sangay';

  @override
  String get branchesActiveChip => 'Aktibo';

  @override
  String get branchesClosedChip => 'Sarado';

  @override
  String get branchesLoadFailed =>
      'Hindi na-load ang mga sangay, i-pull down para subukan muli.';

  @override
  String get branchesLimitReached =>
      'Hindi pinapayagan ng iyong kasalukuyang plano ang karagdagang sangay.';

  @override
  String get branchesNameRequired => 'Kailangan ang pangalan ng sangay';

  @override
  String get branchesNameLabel => 'Pangalan ng sangay';

  @override
  String get branchesCityLabel => 'Lungsod';

  @override
  String get branchesLocationHint =>
      'I-paste ang link ng lokasyon mula sa Google Maps (opsyonal sa unang sangay, kailangan mula sa ikalawa)';

  @override
  String get branchesMapsLinkLabel => 'Link ng Google Maps';

  @override
  String get branchesMapsLinkInvalid =>
      'Hindi mabasa ang link na iyon — siguraduhing link ito mula sa Google Maps.';

  @override
  String get branchesMapsLinkShort =>
      'I-paste ang buong link ng Google Maps, hindi ang pinaikling link.';

  @override
  String get branchesLocationRequired =>
      'Itakda ang lokasyon ng sangay sa mapa — kailangan mula sa ikalawang sangay.';

  @override
  String get branchesSaveFailed => 'Hindi na-save, subukan ulit.';

  @override
  String get branchesStatusLabel => 'Katayuan ng sangay';

  @override
  String get branchesMainCannotClose =>
      'Hindi maaaring isara ang pangunahing sangay — pangalan lang ang maaaring baguhin.';

  @override
  String get branchesWhatsappTitle => 'Koneksyon sa WhatsApp';

  @override
  String get branchesWhatsappNotStarted => 'Hindi pa nakakonekta';

  @override
  String get branchesWhatsappConnected => 'Nakakonekta at gumagana';

  @override
  String get branchesWhatsappCannotSend =>
      'Nakakonekta pero may isyu sa pagpapadala';

  @override
  String get branchesTeamTitle => 'Koponan ng sangay';

  @override
  String get branchesTeamEmpty => 'Wala pang miyembro sa sangay na ito.';

  @override
  String get branchesAddMember => 'Magdagdag ng miyembro';

  @override
  String get branchesMemberNameLabel => 'Pangalan ng empleyado';

  @override
  String get branchesMemberPhoneLabel => 'Numero ng telepono niya';

  @override
  String get branchesMemberPasswordLabel => 'Password niya sa pag-login';

  @override
  String get branchesMemberRoleLabel => 'Tungkulin';

  @override
  String get branchesRoleOperator => 'Field operator';

  @override
  String get branchesRoleSupervisor => 'Shift supervisor';

  @override
  String get branchesRoleManager => 'Manager';

  @override
  String get branchesSeatLimit =>
      'Hindi pinapayagan ng iyong kasalukuyang plano ang karagdagang empleyado.';

  @override
  String get branchesHireFailed =>
      'Hindi maidagdag ang empleyado, subukan ulit.';

  @override
  String get accountSecuritySectionTitle => 'Seguridad';

  @override
  String get accountChangePasswordRow => 'Palitan ang password';

  @override
  String get accountChangePasswordFailed =>
      'Hindi mapalitan ang password, subukan ulit.';

  @override
  String get accountChangePasswordSuccess => 'Napalitan ang password.';

  @override
  String get accountCurrentPasswordLabel => 'Kasalukuyang password';

  @override
  String get accountNewPasswordLabel => 'Bagong password';

  @override
  String get accountConfirmNewPasswordLabel =>
      'Kumpirmahin ang bagong password';

  @override
  String get branchesIncreaseCapacity => 'Dagdagan ang kapasidad';

  @override
  String get accountBillingSectionTitle => 'Pagsingil';

  @override
  String get accountBillingRow => 'Subscription at mga invoice';

  @override
  String get billingPageTitle => 'Pagsingil';

  @override
  String get billingLoadFailed =>
      'Hindi na-load ang datos ng pagsingil. Hilahin pababa para subukan muli.';

  @override
  String get billingAllGood =>
      'Maayos ang iyong billing — walang kailangang pansinin ngayon.';

  @override
  String get billingPastDue =>
      'Mayroon kang overdue na invoice — bayaran ito para maiwasan ang pagka-pause ng iyong mga serbisyo.';

  @override
  String get billingUsageSectionTitle => 'Ang iyong paggamit';

  @override
  String get billingUsageStaffSeats => 'Upuan ng staff';

  @override
  String get billingUsageBranches => 'Mga sangay';

  @override
  String get billingUsageUnlimited => 'Walang limitasyon';

  @override
  String get billingMyAppsSectionTitle => 'Mga naka-subscribe kong app';

  @override
  String get billingStatusActive => 'Aktibo';

  @override
  String get billingStatusStopping => 'Titigil na';

  @override
  String billingRenewsOn(Object date) {
    return 'Mare-renew sa $date';
  }

  @override
  String get billingStopRenewal => 'Ihinto ang pag-renew';

  @override
  String get billingUndoStopRenewal => 'I-undo ang paghinto';

  @override
  String get billingRenewNow => 'I-renew ngayon';

  @override
  String get billingActionFailed =>
      'Hindi natapos ang aksyong ito. Subukan muli.';

  @override
  String get billingRenewalPreviewSectionTitle =>
      'Preview ng susunod na pag-renew';

  @override
  String billingRenewalPreviewNextChargeOn(Object date) {
    return 'Susunod na sisingilin sa $date';
  }

  @override
  String get billingRenewalPreviewNoDate =>
      'Wala pang paparating na petsa ng pag-renew.';

  @override
  String get billingRenewalPreviewSubtotal => 'Subtotal';

  @override
  String get billingRenewalPreviewSavings => 'Naipon';

  @override
  String get billingRenewalPreviewTax => 'Buwis';

  @override
  String get billingRenewalPreviewTotal => 'Kabuuan';

  @override
  String get billingInvoicesSectionTitle => 'Mga invoice';

  @override
  String get billingInvoicesEmpty => 'Wala pang mga invoice.';

  @override
  String get billingInvoiceStatusPaid => 'Bayad na';

  @override
  String get billingInvoiceStatusOpen => 'Hindi pa bayad';

  @override
  String get billingInvoiceStatusPartiallyPaid => 'Bahagyang bayad';

  @override
  String get billingInvoiceStatusVoid => 'Nawalang-bisa';

  @override
  String get billingInvoiceStatusUncollectible => 'Hindi na makokolekta';

  @override
  String get billingInvoiceStatusDraft => 'Draft';

  @override
  String get billingPayNow => 'Magbayad ngayon';

  @override
  String get billingPayLinkFailed => 'Hindi nagawa ang pay link. Subukan muli.';

  @override
  String get billingCancelConfirmTitle => 'Ihinto ang pag-renew?';

  @override
  String get billingCancelConfirmBody =>
      'Patuloy na gagana ang serbisyo hanggang sa katapusan ng kasalukuyang panahon, pagkatapos hindi na ito mare-renew.';

  @override
  String get billingCancelConfirmAction => 'Ihinto ang pag-renew';

  @override
  String get visitOfferApplyLabel =>
      'Ilapat ang alok na ito sa pagbisitang ito';

  @override
  String visitPointsRedeemCost(Object cost) {
    return '$cost puntos';
  }

  @override
  String visitPointsRedeemedMessage(Object name) {
    return 'Na-redeem ang $name ✓';
  }

  @override
  String get visitPointsRedeemFailed => 'Hindi na-redeem. Subukan muli.';

  @override
  String readBillingActiveCount(Object count) {
    return 'Mayroon kang $count aktibong subscription.';
  }

  @override
  String get readBillingNone => 'Wala kang aktibong subscription ngayon.';

  @override
  String readBillingRenewsSoon(Object date) {
    return 'Ang susunod na pag-renew ay sa $date.';
  }

  @override
  String get readBillingFailed =>
      'Hindi makuha ang katayuan ng billing ngayon, subukan muli.';

  @override
  String readBranchCount(Object count) {
    return 'Mayroon kang $count branch.';
  }

  @override
  String get readBranchFailed =>
      'Hindi makuha ang bilang ng branch ngayon, subukan muli.';

  @override
  String get readVehicleTrackingOn =>
      'Naka-on ang pagsubaybay sa sasakyan ngayon.';

  @override
  String get readVehicleTrackingOff =>
      'Naka-off ang pagsubaybay sa sasakyan ngayon.';

  @override
  String get readVehicleTrackingFailed =>
      'Hindi ma-check ang status ng pagsubaybay sa sasakyan ngayon, subukan muli.';
}
