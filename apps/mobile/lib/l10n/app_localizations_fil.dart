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
  String get assistantReplySettingsTooltip => 'Mga setting ng sagot';

  @override
  String get assistantReplyModeTitle => 'Paano sumasagot ang katulong';

  @override
  String get assistantReplyModeSubtitle =>
      'Nalalapat sa bawat sagot, kahit tinanong mo sa boses';

  @override
  String get assistantReplyModeVoice => 'Boses';

  @override
  String get assistantReplyModeText => 'Nakasulat na teksto';

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
  String get branchesRoleMarketer => 'Marketing lead';

  @override
  String get branchesRoleManager => 'Manager';

  @override
  String get branchesSeatLimit =>
      'Hindi pinapayagan ng iyong kasalukuyang plano ang karagdagang empleyado.';

  @override
  String get branchesHireFailed =>
      'Hindi maidagdag ang empleyado, subukan ulit.';

  @override
  String get branchesVisibleAllHint => 'Nakikita ang lahat ng sangay';

  @override
  String branchesVisibleSomeHint(int count) {
    return 'Nakikita ang $count sangay';
  }

  @override
  String get branchesEditMember => 'I-edit ang empleyado';

  @override
  String get branchesMemberStopped => 'Naka-stop';

  @override
  String get branchesMemberStationLabel => 'Saang sangay siya nagtatrabaho';

  @override
  String get branchesMemberVisibilityLabel =>
      'Aling mga sangay ang makikita niya';

  @override
  String get branchesVisibilityOwnOnly => 'Sariling sangay lang';

  @override
  String get branchesVisibilitySome => 'Mga tiyak na sangay';

  @override
  String get branchesVisibilityAll => 'Lahat ng sangay';

  @override
  String get branchesWorkingHours => 'Oras ng trabaho';

  @override
  String get branchesStopMember => 'Itigil ang empleyado';

  @override
  String get branchesStopMemberTitle => 'Itigil ang empleyadong ito?';

  @override
  String branchesStopMemberBody(String name) {
    return 'Mawawala kay $name ang access sa app agad. Mananatiling naka-save ang kanyang kasaysayan ng pagbisita.';
  }

  @override
  String get branchesStopMemberConfirm => 'Itigil';

  @override
  String get branchesReactivateMember => 'I-reactivate';

  @override
  String get branchesRehireRequired =>
      'Ganap nang naka-stop ang empleyadong ito — ang pag-reactivate ay nangangailangan ng muling pagkuha, hindi lang isang toggle.';

  @override
  String get branchesHoursSaved => 'Na-save ang oras ng trabaho.';

  @override
  String get branchesHoursExceedsShop =>
      'Mas malawak ang oras na ito kaysa sa oras ng tindahan mismo — ayusin ito.';

  @override
  String get branchesHoursHint =>
      'Kung wala kang babaguhin, susundin niya ang oras ng tindahan mismo awtomatiko.';

  @override
  String get branchesHoursClear => 'Ibalik sa default na oras ng tindahan';

  @override
  String get branchesDayMonday => 'Lunes';

  @override
  String get branchesDayTuesday => 'Martes';

  @override
  String get branchesDayWednesday => 'Miyerkules';

  @override
  String get branchesDayThursday => 'Huwebes';

  @override
  String get branchesDayFriday => 'Biyernes';

  @override
  String get branchesDaySaturday => 'Sabado';

  @override
  String get branchesDaySunday => 'Linggo';

  @override
  String get branchesDayClosed => 'Sarado';

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
  String get billingPaymentConfirming =>
      'Natanggap namin ang iyong pagsubok na bayad at kinukumpirma na ito — maaaring umabot ito ng 20 minuto.';

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
  String get paymentPageLoadFailed =>
      'Hindi na-load ang pahina ng pagbabayad. Tingnan ang iyong koneksyon at subukan muli.';

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

  @override
  String get writeVehicleTrackingEnabledConfirm =>
      'Ia-on ang field ng plate number sa visit-registration screen ng tindahang ito. Kumpirmahin?';

  @override
  String get writeVehicleTrackingDisabledConfirm =>
      'Ia-off ang field ng plate number sa visit-registration screen ng tindahang ito. Kumpirmahin?';

  @override
  String get writeVehicleTrackingEnabledDone =>
      'Na-on na ang pagsubaybay sa sasakyan ✓';

  @override
  String get writeVehicleTrackingDisabledDone =>
      'Na-off na ang pagsubaybay sa sasakyan ✓';

  @override
  String get writeVehicleTrackingFailed =>
      'Hindi mapalitan ang setting ng pagsubaybay sa sasakyan, subukan muli.';

  @override
  String get mobileRequestsTitle => 'Mga hiling na mobile';

  @override
  String get mobileRequestsSubtitle =>
      'Mga hiling para sa serbisyong pupunta sa customer, mula pagtanggap hanggang pagkumpleto.';

  @override
  String get mobileRequestsKpiPending => 'Naghihintay ng desisyon';

  @override
  String get mobileRequestsKpiNeedsDecision => 'Kailangan ng desisyon';

  @override
  String get mobileRequestsKpiCompletedMonth => 'Nakumpleto ngayong buwan';

  @override
  String get mobileRequestsBannerGo => 'Tingnan';

  @override
  String get mobileRequestsFilterAll => 'Lahat';

  @override
  String get mobileRequestsFilterPending => 'Nakabinbin';

  @override
  String get mobileRequestsFilterAccepted => 'Tinanggap';

  @override
  String get mobileRequestsFilterNeedsDecision => 'Kailangan ng desisyon';

  @override
  String get mobileRequestsFilterCompleted => 'Nakumpleto';

  @override
  String get mobileRequestsFilterClosed => 'Sarado';

  @override
  String get mobileRequestsSearchHint => 'Maghanap sa pangalan o telepono';

  @override
  String get mobileRequestsLoadFailedTitle => 'Hindi ma-load ang mga hiling';

  @override
  String get mobileRequestsLoadFailedBody =>
      'Suriin ang iyong koneksyon at subukan ulit.';

  @override
  String get mobileRequestsRetry => 'Subukan ulit';

  @override
  String get mobileRequestsEmptyTitle => 'Wala pang hiling';

  @override
  String get mobileRequestsEmptyBody =>
      'Lalabas dito ang mga hiling ng mobile-service mula sa iyong mga customer.';

  @override
  String get mobileRequestsStatusPending => 'Nakabinbin';

  @override
  String get mobileRequestsStatusAccepted => 'Tinanggap';

  @override
  String get mobileRequestsStatusNeedsDecision => 'Kailangan ng desisyon';

  @override
  String get mobileRequestsStatusCompleted => 'Nakumpleto';

  @override
  String get mobileRequestsStatusNoShow => 'Hindi dumating';

  @override
  String get mobileRequestsStatusRejected => 'Tinanggihan';

  @override
  String get mobileRequestsUnnamed => 'Walang pangalan';

  @override
  String get mobileRequestsOpenMap => 'Lokasyon';

  @override
  String get mobileRequestsPhoneCopied => 'Nakopya ang numero ng telepono';

  @override
  String get mobileRequestsRiskyCustomer =>
      'Customer na mataas ang risk sa no-show';

  @override
  String mobileRequestsRejectReasonLine(Object reason) {
    return 'Dahilan ng pagtanggi: $reason';
  }

  @override
  String get mobileRequestsActionAccept => 'Tanggapin';

  @override
  String get mobileRequestsActionReject => 'Tanggihan';

  @override
  String get mobileRequestsActionComplete => 'Kumpleto';

  @override
  String get mobileRequestsActionNoShow => 'Hindi dumating';

  @override
  String get mobileRequestsAssignUnassigned => 'Walang itinalaga';

  @override
  String get mobileRequestsActionFailed =>
      'Hindi nakumpleto ang aksyon, subukan ulit.';

  @override
  String get mobileRequestsRejectTitle => 'Dahilan ng pagtanggi';

  @override
  String get mobileRequestsRejectHint => 'Opsyonal';

  @override
  String get mobileRequestsRejectCancel => 'Kanselahin';

  @override
  String get mobileRequestsRejectConfirm => 'Tanggihan ang hiling';

  @override
  String get mobileRequestsAddOpen => 'Magdagdag ng hiling';

  @override
  String get mobileRequestsAddTitle => 'Magdagdag ng hiling ng mobile service';

  @override
  String get mobileRequestsAddPhoneLabel => 'Telepono ng customer';

  @override
  String get mobileRequestsAddNameLabel => 'Pangalan ng customer (opsyonal)';

  @override
  String get mobileRequestsAddServicesLabel => 'Mga serbisyo';

  @override
  String get mobileRequestsAddServicesEmpty =>
      'Wala pang available na serbisyo.';

  @override
  String get mobileRequestsAddDayLabel => 'Araw';

  @override
  String get mobileRequestsAddTimeLabel => 'Oras';

  @override
  String get mobileRequestsAddMapsLinkLabel =>
      'Link ng lokasyon sa Google Maps';

  @override
  String get mobileRequestsAddMapsLinkHint =>
      'Tumatanggap ng buo o pinaikling Google Maps link.';

  @override
  String get mobileRequestsAddMapsLinkShort =>
      'Pinaikling link ito — i-paste ang buong Google Maps link.';

  @override
  String get mobileRequestsAddMapsLinkInvalid =>
      'Hindi mabasa ang lokasyon mula sa link na ito.';

  @override
  String get mobileRequestsAddAssignLabel => 'Italaga kay (opsyonal)';

  @override
  String get mobileRequestsAddCancel => 'Kanselahin';

  @override
  String get mobileRequestsAddSubmit => 'Idagdag ang hiling';

  @override
  String get mobileRequestsAddSubmitting => 'Idinaragdag...';

  @override
  String get mobileRequestsAddError =>
      'Hindi naidagdag ang hiling, subukan ulit.';

  @override
  String mobileRequestsBannerText(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count hiling ang nangangailangan ng desisyon mo ngayon',
      one: '1 hiling ang nangangailangan ng desisyon mo ngayon',
    );
    return '$_temp0';
  }

  @override
  String get mobileRequestsAddMapsLinkResolving =>
      'Binabasa ang lokasyon mula sa link...';

  @override
  String get customersTitle => 'Mga Kontak';

  @override
  String get customersAddOpen => 'Magdagdag ng customer';

  @override
  String get customersSearchHint => 'Maghanap sa pangalan o telepono';

  @override
  String get customersTabAll => 'Lahat';

  @override
  String get customersTabOverdue => 'Naantala';

  @override
  String get customersSearchFailedTitle =>
      'Hindi available ang paghahanap ngayon';

  @override
  String get customersSearchFailedBody => 'Subukan ulit sandali.';

  @override
  String get customersSearchEmpty => 'Walang resulta';

  @override
  String get customersLoadFailedTitle => 'Hindi na-load';

  @override
  String get customersEmptyTitle => 'Wala pang customer';

  @override
  String get customersOverdueEmpty => 'Walang naaantala ngayon';

  @override
  String get customersUnnamed => 'Walang pangalan';

  @override
  String customersVisitCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count na bisita',
      one: '1 bisita',
    );
    return '$_temp0';
  }

  @override
  String get customersOverdueBadge => 'Naantala';

  @override
  String customersStatEveryDays(int days) {
    String _temp0 = intl.Intl.pluralLogic(
      days,
      locale: localeName,
      other: 'tuwing $days araw',
    );
    return '$_temp0';
  }

  @override
  String customersOverdueBanner(int every, int since) {
    return 'Naantala na sa karaniwang bisita — karaniwan tuwing $every araw, $since araw na mula sa huling bisita';
  }

  @override
  String customersVisitMeter(int n) {
    return 'Odometer: $n';
  }

  @override
  String get customersOfferExpiredBadge => 'Nag-expire na';

  @override
  String get customersDeniedAllTitle =>
      'Wala kang pahintulot na tingnan ang listahan ng customer';

  @override
  String get customersDeniedOverdueTitle =>
      'Wala kang pahintulot na tingnan kung sino ang naantala';

  @override
  String get customersDeniedDesc =>
      'Hilingin sa may-ari ng tindahan ang pahintulot na ito.';

  @override
  String get customersAddTitle => 'Magdagdag ng bagong customer';

  @override
  String get customersAddPhoneLabel => 'Telepono ng customer';

  @override
  String get customersAddNameLabel => 'Pangalan ng customer';

  @override
  String get customersAddPhoneInvalid => 'Hindi tama ang numero ng telepono.';

  @override
  String get customersAddFailed =>
      'Hindi naidagdag ang customer, subukan ulit.';

  @override
  String get customersAddSubmitting => 'Idinaragdag...';

  @override
  String get customersAddSubmit => 'Idagdag';

  @override
  String get customersActionFailed =>
      'Hindi nakumpleto ang aksyon, subukan ulit.';

  @override
  String get customersRepeatedIssuesTitle => 'Paulit-ulit na isyu';

  @override
  String get customersVehiclesTitle => 'Mga sasakyan';

  @override
  String get customersLoyaltyTitle => 'Loyalty';

  @override
  String get customersLoyaltyLoading => 'Nilo-load...';

  @override
  String customersLoyaltyPoints(int count) {
    return '$count puntos';
  }

  @override
  String get customersLoyaltyAdjust => 'Ayusin';

  @override
  String get customersOffersTitle => 'Mga aktibong alok';

  @override
  String customersOfferExpires(String date) {
    return 'Mag-e-expire $date';
  }

  @override
  String get customersVisitsTitle => 'Kasaysayan ng bisita';

  @override
  String get customersVisitsEmpty => 'Wala pang bisita';

  @override
  String get customersVisitNoServices => 'Walang naitalang serbisyo';

  @override
  String get customersRenameTitle => 'I-edit ang pangalan ng customer';

  @override
  String get customersRenameSubmit => 'I-save';

  @override
  String get customersLoyaltyAdjustTitle => 'Ayusin ang loyalty points';

  @override
  String get customersLoyaltyAdjustNoteLabel => 'Dahilan ng pagsasaayos';

  @override
  String get customersLoyaltyAdjustNoteRequired =>
      'Magsulat ng totoong dahilan (hindi bababa sa 3 karakter), at pumili ng hindi zero na halaga.';

  @override
  String get customersLoyaltyAdjustSubmit => 'I-save ang pagsasaayos';

  @override
  String get customersEraseButton => 'Burahin ang data ng customer na ito';

  @override
  String get customersEraseTitle => 'Burahin ang data ng customer';

  @override
  String get customersEraseWarning =>
      'Permanente nitong buburahin ang lahat ng data ng customer mula sa platform — hindi na ito mababawi.';

  @override
  String customersEraseTypeNameLabel(String name) {
    return 'Para kumpirmahin, i-type ang pangalan ng customer: $name';
  }

  @override
  String get customersEraseConfirm => 'Buraburahin nang permanente';

  @override
  String get customersBookingsTitle => 'Mga booking';

  @override
  String customersAttendanceRate(int rate) {
    return '$rate% pagdalo';
  }

  @override
  String get customersBookingsNoneUpcoming => 'Walang paparating na booking';

  @override
  String get customersCyclesTitle => 'Mga cycle ng paalala';

  @override
  String customersCyclesEveryDays(int days) {
    return 'Bawat $days araw';
  }

  @override
  String get customersCyclesEditHint =>
      'Itakda ang interval, at hihinto ang awtomatikong pagkatuto para sa serbisyong ito sa customer na ito.';

  @override
  String get customersCyclesSave => 'I-save';

  @override
  String get customersLogTitle => 'Ano ang sinabi namin sa kanila';

  @override
  String get customersLogEmpty => 'Wala pa kaming naipadala sa kanila';

  @override
  String get customersCyclesUnknownService => 'Hindi kilalang serbisyo';

  @override
  String customersVisitGapDays(int days) {
    String _temp0 = intl.Intl.pluralLogic(
      days,
      locale: localeName,
      other: 'pagkatapos ng $days araw',
      one: 'pagkatapos ng 1 araw',
      zero: 'sa parehong araw',
    );
    return '$_temp0';
  }

  @override
  String customersCountLabel(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count na customer',
      one: '1 customer',
      zero: 'wala pang customer',
    );
    return '$_temp0';
  }

  @override
  String get ratingTitle => 'Mga rating';

  @override
  String get pointsTitle => 'Loyalty Points';

  @override
  String get pointsAddReward => 'Bagong reward';

  @override
  String get pointsEditReward => 'I-edit ang reward';

  @override
  String get pointsTabRewards => 'Mga reward';

  @override
  String get pointsTabLeaderboard => 'Pinaka-redeem';

  @override
  String get pointsOutstandingHint =>
      'puntos na utang pa ng tindahan sa mga customer';

  @override
  String pointsRedemptionsCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count redemption',
      one: '1 redemption',
    );
    return '$_temp0';
  }

  @override
  String pointsCustomersCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count customer ang nag-redeem',
      one: '1 customer ang nag-redeem',
    );
    return '$_temp0';
  }

  @override
  String pointsExpiredWarning(int percent) {
    return '$percent% ng mga puntos na ibinigay ay nag-expire na hindi na-redeem — suriin ang presyo ng reward';
  }

  @override
  String get pointsLoadFailedTitle => 'Hindi ma-load ang mga reward';

  @override
  String get pointsRewardsEmpty =>
      'Wala pang reward — idagdag ang unang reward para sa iyong mga customer';

  @override
  String get pointsLeaderboardEmpty =>
      'Wala pang redemption — lalabas dito kapag may nag-redeem na customer';

  @override
  String get pointsLeaderboardTitle => 'Pinaka-redeem';

  @override
  String get pointsLeaderboardHint =>
      'Ang top limang reward na na-redeem ng iyong mga customer';

  @override
  String pointsTimesRedeemed(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count beses',
      one: 'isang beses',
    );
    return '$_temp0';
  }

  @override
  String get pointsRewardRetired => 'Naka-retire';

  @override
  String pointsRewardServiceHint(String name) {
    return 'Serbisyo: $name';
  }

  @override
  String pointsRewardDiscountHint(String amount) {
    return '$amount SAR na diskwento';
  }

  @override
  String get pointsRewardItemHint => 'Regalo, hindi konektado sa katalogo';

  @override
  String get pointsRewardNameLabel => 'Pangalan ng reward';

  @override
  String get pointsRewardTypeLabel => 'Uri ng reward';

  @override
  String get pointsTypeService => 'Isang serbisyo mula sa iyong katalogo';

  @override
  String get pointsTypeItem => 'Isang regalo';

  @override
  String get pointsTypeDiscount => 'Diskwentong pera';

  @override
  String get pointsRewardServiceLabel => 'Aling serbisyo';

  @override
  String get pointsRewardDiscountLabel => 'Halaga ng diskwento, SAR';

  @override
  String get pointsRewardCostLabel => 'Gastos sa puntos';

  @override
  String get pointsRewardActiveLabel =>
      'Aktibo — maaaring i-redeem ng mga customer';

  @override
  String get pointsRewardInvalid =>
      'Maglagay ng pangalan at tunay na gastos sa puntos na higit sa zero';

  @override
  String get pointsSaveFailed => 'Hindi na-save, subukan ulit';

  @override
  String get pointsModeTitle => 'Paraan ng pagkalkula';

  @override
  String get pointsModeHint =>
      'Ayon sa serbisyo: bawat serbisyo may sariling puntos. Ayon sa halaga ng invoice: isang puntos kada riyal.';

  @override
  String get pointsModeServices => 'Ayon sa serbisyo';

  @override
  String get pointsModeInvoice => 'Ayon sa halaga ng invoice';

  @override
  String get pointsModeNeedsPricedServices =>
      'Ang pagkalkula ayon sa halaga ng invoice ay nangangailangan munang mapresyuhan ang bawat serbisyo — presyuhan lahat sa Mga Serbisyo, pagkatapos i-on.';

  @override
  String get pointsOpenEarnSettings => 'Setting ng puntos kada serbisyo';

  @override
  String get ratingLeaderboardTitle => 'Pinakamataas ang rating';

  @override
  String get ratingCardNoName => 'Walang pangalan';

  @override
  String get ratingMetricVisits => 'Pinakamaraming bisita';

  @override
  String get ratingMetricRatings => 'Pinakamaraming rating';

  @override
  String get ratingMetricAvg => 'Pinakamataas ang rating';

  @override
  String ratingStaffCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count kawani',
      one: '1 kawani',
    );
    return '$_temp0';
  }

  @override
  String get ratingTableTitle => 'Bawat kawani';

  @override
  String ratingTableVisitsValue(int n) {
    return '$n bisita';
  }

  @override
  String ratingTableRatingsValue(int n) {
    return '$n rating';
  }

  @override
  String ratingTableEngagementValue(int n) {
    return '$n% engagement';
  }

  @override
  String ratingTableNoShowValue(int n) {
    return '$n% no-show';
  }

  @override
  String get ratingPeriodWeek => 'Linggo';

  @override
  String get ratingPeriodMonth => 'Buwan';

  @override
  String get ratingPeriodQuarter => 'Quarter';

  @override
  String get ratingPeriodCustom => 'Custom';

  @override
  String ratingCustomSince(String date) {
    return 'Mula: $date';
  }

  @override
  String ratingCustomUntil(String date) {
    return 'Hanggang: $date';
  }

  @override
  String get ratingCustomRangeInvalid =>
      'Invalid ang saklaw — siguraduhing nauna ang petsa ng simula sa petsa ng pagtatapos';

  @override
  String get ratingExportLocaleLabel => 'Wika ng ulat';

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
  String get ratingTopIssuesTitle => 'Pinaka-paulit-ulit na isyu';

  @override
  String get ratingFilterUnhandled => 'Nakabinbin';

  @override
  String get ratingFilterAll => 'Lahat';

  @override
  String get ratingFilterHandled => 'Nahandle na';

  @override
  String get ratingStarsAll => 'Lahat ng bituin';

  @override
  String get ratingLoadFailedTitle => 'Hindi na-load ang mga rating';

  @override
  String get ratingEmptyTitle => 'Wala pang rating';

  @override
  String get ratingLoadMore => 'Magpakita pa';

  @override
  String get ratingHandledPlain => 'Nahandle na';

  @override
  String get ratingMarkHandled => 'Markahan bilang nahandle';

  @override
  String get ratingMarkHandledHint =>
      'Permanenteng naitala ito — hindi na ito mababawi mamaya.';

  @override
  String get ratingHandledNoteLabel => 'Tala (opsyonal)';

  @override
  String get ratingMarkHandledConfirm => 'Kumpirmahin';

  @override
  String get ratingActionFailed => 'Hindi nakumpleto ang aksyon, subukan ulit.';

  @override
  String ratingWeightedAvgHint(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'mula sa $count rating sa huling 30 araw',
      one: 'mula sa 1 rating sa huling 30 araw',
      zero: 'walang rating sa huling 30 araw',
    );
    return '$_temp0';
  }

  @override
  String ratingUnhandledCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count rating ang nakabinbin',
      one: '1 rating ang nakabinbin',
    );
    return '$_temp0';
  }

  @override
  String ratingVisitsShort(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count na bisita',
      one: '1 bisita',
    );
    return '$_temp0';
  }

  @override
  String ratingIssueFilterLabel(String label) {
    return 'Isyu: $label';
  }

  @override
  String ratingByOperator(String name) {
    return 'Sinilbihan ni $name';
  }

  @override
  String ratingHandledWithNote(String note) {
    return 'Nahandle na: $note';
  }

  @override
  String get ratingQuadrantTitle => 'Quadrant ng performance';

  @override
  String get ratingQuadrantHint =>
      'Kalidad laban sa engagement rate — pindutin ang anumang punto para sa training record.';

  @override
  String get ratingQuadrantStars => 'Mga bituin';

  @override
  String get ratingQuadrantUnderused => 'Hindi gaanong ginagamit';

  @override
  String get ratingQuadrantNeedsCoaching => 'Kailangan ng coaching';

  @override
  String get ratingQuadrantAtRisk => 'Nangangailangan ng pansin';

  @override
  String get ratingTrainingTitle => 'Training record';

  @override
  String get ratingTrainingNoAccess => 'Wala kang pahintulot na makita ito.';

  @override
  String get ratingTrainingClean =>
      'Malinis na record — walang paulit-ulit na isyu.';

  @override
  String ratingEngagementPercent(int percent) {
    return '$percent% engagement';
  }

  @override
  String get ratingTabOverview => 'Overview';

  @override
  String get ratingTabFeed => 'Lahat ng rating';

  @override
  String get ratingOverviewEmpty =>
      'Wala pang performance data para sa huling 30 araw.';

  @override
  String get ratingExportTitle => 'I-export ang ulat';

  @override
  String get ratingExportHint =>
      'Ang ulat ng performance ng team para sa napiling panahon, handa nang ibahagi.';

  @override
  String get ratingExportFailed => 'Hindi na-export ang ulat, subukan ulit.';

  @override
  String get customersPrivacyRequestsTitle => 'Mga hiling sa privacy';

  @override
  String get customersPrivacyRequestErase => 'Hiling sa pagbura ng data';

  @override
  String get customersPrivacyRequestCopy => 'Hiling sa kopya ng data';

  @override
  String customersPrivacyRequestGeneric(String type) {
    return 'Hiling: $type';
  }

  @override
  String get customersPrivacyRequestClose => 'Isara';

  @override
  String get customersLoyaltyHistoryTitle => 'Kasaysayan ng puntos';

  @override
  String get customersLoyaltyHistoryNoReason => 'Walang ibinigay na dahilan';

  @override
  String get customersLoyaltyReasonRedeem => 'Ginamit na reward';

  @override
  String get customersLoyaltyReasonAdjust => 'Manual na pagsasaayos';

  @override
  String get customersLoyaltyReasonEarn => 'Puntos mula sa bisita';

  @override
  String get customersLoyaltyReasonExpire => 'Nag-expire';

  @override
  String get readCustomersFailed =>
      'Hindi nakuha ang data ng customer ngayon, subukan ulit.';

  @override
  String readCustomersTotal(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'May $count kang nakarehistrong customer.',
      one: 'May 1 kang nakarehistrong customer.',
      zero: 'Wala ka pang nakarehistrong customer.',
    );
    return '$_temp0';
  }

  @override
  String readCustomersOverdueCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'May $count kang customer na naantala sa cycle.',
      one: 'May 1 kang customer na naantala sa cycle.',
      zero: 'Walang customer na naantala sa kanilang cycle ngayon.',
    );
    return '$_temp0';
  }

  @override
  String get readMobileRequestsFailed =>
      'Hindi nakuha ang mga mobile request ngayon, subukan ulit.';

  @override
  String readMobileRequestsPendingCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'May $count kang hiling na naghihintay ng desisyon.',
      one: 'May 1 kang hiling na naghihintay ng desisyon.',
      zero: 'Walang mobile request na naghihintay ng desisyon.',
    );
    return '$_temp0';
  }

  @override
  String readMobileRequestsNeedsDecisionCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count hiling ang nangangailangan ng desisyon mo ngayon.',
      one: '1 hiling ang nangangailangan ng desisyon mo ngayon.',
      zero: 'Walang mobile request na nangangailangan ng desisyon mo ngayon.',
    );
    return '$_temp0';
  }

  @override
  String get readRatingFailed =>
      'Hindi nakuha ang rating data ngayon, subukan ulit.';

  @override
  String get readRatingNone => 'Wala ka pang rating sa huling 30 araw.';

  @override
  String readRatingAverage(String avg, int count) {
    return 'Ang average rating mo sa huling 30 araw ay $avg sa 5, mula sa $count rating.';
  }

  @override
  String readRatingUnhandledCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'May $count kang nakabinbing rating.',
      one: 'May 1 kang nakabinbing rating.',
      zero: 'Walang nakabinbin na rating.',
    );
    return '$_temp0';
  }

  @override
  String readRatingTopStaff(String name, String avg) {
    return 'Ang pinakamataas ang rating na staff sa huling 30 araw ay si $name, na may average na $avg sa 5.';
  }

  @override
  String readMobileRequestsCompletedCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count ang nakumpleto mo ngayong buwan.',
      one: '1 ang nakumpleto mo ngayong buwan.',
      zero: 'Wala ka pang nakumpletong mobile request ngayong buwan.',
    );
    return '$_temp0';
  }

  @override
  String readMobileRequestsTodayCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count hiling ang dumating ngayong araw.',
      one: '1 hiling ang dumating ngayong araw.',
      zero: 'Wala pang dumarating na mobile request ngayong araw.',
    );
    return '$_temp0';
  }

  @override
  String get readOperatorsFailed =>
      'Hindi nakuha ang bilang ng staff ngayon, subukan ulit.';

  @override
  String readOperatorsCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'May $count kang miyembro ng staff.',
      one: 'May 1 kang miyembro ng staff.',
      zero: 'Wala ka pang nakarehistrong staff.',
    );
    return '$_temp0';
  }

  @override
  String readBranchesDisconnectedCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'May $count kang branch na hindi gumagana ang WhatsApp.',
      one: 'May 1 kang branch na hindi gumagana ang WhatsApp.',
      zero:
          'Lahat ng aktibong branch mo ay konektado at gumagana ang WhatsApp.',
    );
    return '$_temp0';
  }

  @override
  String get readCustomersRecentNone => 'Wala ka pang nakarehistrong customer.';

  @override
  String readCustomersRecentName(String name) {
    return 'Ang pinakabagong customer mo ay si $name.';
  }

  @override
  String readRatingCriticalIssuesCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'May $count kang nakabinbing rating na may kritikal na isyu.',
      one: 'May 1 kang nakabinbing rating na may kritikal na isyu.',
      zero: 'Walang nakabinbing rating na may kritikal na isyu.',
    );
    return '$_temp0';
  }

  @override
  String get readPerBranchModeOn =>
      'Oo, tumatakbo ang tindahan mo sa multi-branch mode.';

  @override
  String get readPerBranchModeOff =>
      'Hindi, tumatakbo ang tindahan mo bilang iisang branch lang.';

  @override
  String get readBillingOverdueYes =>
      'Oo, may overdue kang invoice — bayaran ito para maiwasan ang pagkakansela ng serbisyo.';

  @override
  String get readBillingOverdueNo =>
      'Hindi, maayos ang billing mo, walang overdue na invoice.';

  @override
  String get readServicesFailed =>
      'Hindi nakuha ang bilang ng serbisyo ngayon, subukan ulit.';

  @override
  String readServicesCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'May $count kang serbisyo sa listahan mo.',
      one: 'May 1 kang serbisyo sa listahan mo.',
      zero: 'Wala ka pang serbisyo sa listahan mo.',
    );
    return '$_temp0';
  }

  @override
  String readCustomersTodayCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count bagong customer ang dumating ngayong araw.',
      one: '1 bagong customer ang dumating ngayong araw.',
      zero: 'Wala pang bagong customer na dumating ngayong araw.',
    );
    return '$_temp0';
  }

  @override
  String readMobileRequestsRejectedCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count ang tinanggihan mo ngayong buwan.',
      one: '1 ang tinanggihan mo ngayong buwan.',
      zero: 'Wala kang tinanggihang mobile request ngayong buwan.',
    );
    return '$_temp0';
  }

  @override
  String readMobileRequestsNoShowCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count customer ang hindi dumating ngayong buwan.',
      one: '1 customer ang hindi dumating ngayong buwan.',
      zero: 'Walang customer na hindi dumating ngayong buwan.',
    );
    return '$_temp0';
  }

  @override
  String readRatingFiveStarCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'May $count kang five-star rating.',
      one: 'May 1 kang five-star rating.',
      zero: 'Wala ka pang five-star rating.',
    );
    return '$_temp0';
  }

  @override
  String readBranchesActiveCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'May $count kang aktibong branch.',
      one: 'May 1 kang aktibong branch.',
      zero: 'Wala kang aktibong branch ngayon.',
    );
    return '$_temp0';
  }

  @override
  String get servicesTitle => 'Mga serbisyo ko';

  @override
  String get servicesUnnamedGlyph => '?';

  @override
  String get servicesSearchHint => 'Maghanap sa pangalan ng serbisyo';

  @override
  String get servicesTabActive => 'Aktibo';

  @override
  String get servicesTabStopped => 'Nakahinto';

  @override
  String get servicesLoadFailedTitle => 'Hindi na-load ang mga serbisyo';

  @override
  String get servicesEmptyActive => 'Wala pang aktibong serbisyo';

  @override
  String get servicesEmptyStopped => 'Walang nakahintong serbisyo';

  @override
  String get servicesAddOpen => 'Magdagdag ng serbisyo';

  @override
  String get servicesNoPrice => 'Walang nakatakdang presyo';

  @override
  String get servicesNoDuration => 'Hindi nakatakda';

  @override
  String get servicesNoCycle => 'Walang cycle';

  @override
  String get servicesStopTitle => 'Ihinto ang serbisyo';

  @override
  String get servicesStopConfirm => 'Ihinto';

  @override
  String get servicesActionFailed =>
      'Hindi nakumpleto ang aksyon, subukan ulit.';

  @override
  String get servicesEditTitle => 'I-edit ang serbisyo';

  @override
  String get servicesAddTitle => 'Magdagdag ng bagong serbisyo';

  @override
  String get servicesNameLabel => 'Pangalan ng serbisyo';

  @override
  String get servicesPriceLabel => 'Presyo (opsyonal)';

  @override
  String get servicesDurationLabel => 'Tagal sa minuto (opsyonal)';

  @override
  String get servicesCycleLabel => 'Cycle ng paalala sa araw (opsyonal)';

  @override
  String get servicesDescriptionLabel => 'Maikling paglalarawan (opsyonal)';

  @override
  String get servicesSaving => 'Sine-save...';

  @override
  String get servicesSave => 'I-save';

  @override
  String get servicesNameRequired => 'Kailangan ang pangalan ng serbisyo';

  @override
  String servicesActiveCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'May $count kang aktibong serbisyo.',
      one: 'May 1 kang aktibong serbisyo.',
      zero: 'Wala ka pang aktibong serbisyo.',
    );
    return '$_temp0';
  }

  @override
  String servicesDurationMinutes(int count) {
    return '$count minuto';
  }

  @override
  String servicesCycleDays(int count) {
    return 'Bawat $count araw';
  }

  @override
  String servicesStopWarning(String name) {
    return 'Ihihinto nito ang \"$name\" — hindi ito lalabas sa bagong bisita, at hihinto ang mga paalala nito. Hindi kailanman nabuburang ang data nito.';
  }

  @override
  String get servicesPhotoPickFailed => 'Hindi napili ang larawan';

  @override
  String get servicesPhotoUploadFailed =>
      'Na-save, pero hindi na-upload ang larawan';

  @override
  String get servicesPhotoLabel => 'Larawan ng serbisyo (opsyonal)';

  @override
  String get servicesUploadPhoto => 'Mag-upload ng larawan';

  @override
  String get servicesChangePhoto => 'Palitan ang larawan';

  @override
  String get servicesRemovePhoto => 'Alisin';

  @override
  String get servicesAssignmentLabel =>
      'Sino ang nagbibigay ng serbisyong ito?';

  @override
  String get servicesAssignmentAuto => 'Kahit sinong available na staff';

  @override
  String get servicesAssignmentNamed => 'Tiyak na staff';

  @override
  String get servicesChecklistLabel => 'Checklist ng pamamaraan';

  @override
  String get servicesChecklistEmpty => 'Wala pang hakbang — magdagdag ng una';

  @override
  String get servicesStepAddTitle => 'Magdagdag ng hakbang';

  @override
  String get servicesGeneralSettingsTitle => 'Pangkalahatang setting';

  @override
  String get servicesGeneralSettingsHint =>
      'Ang halagang sinusunod ng bawat serbisyong hindi pa naka-customize';

  @override
  String get servicesFollowUpLabel =>
      'Mga araw ng follow-up pagkatapos ng bisita';

  @override
  String get servicesPointsLabel => 'Puntos kada bisita';

  @override
  String get servicesGroupThem => 'Pagsamahin';

  @override
  String get servicesGroupNameHint => 'Pangalan ng grupo';

  @override
  String get servicesAllGroups => 'Lahat';

  @override
  String get servicesStepEditTitle => 'I-edit ang hakbang';

  @override
  String get servicesStepCriticalLabel => 'Kritikal na hakbang';

  @override
  String get servicesStepRetire => 'Ihinto ang hakbang na ito';

  @override
  String get servicesStepEditHint =>
      'Pindutin nang matagal ang anumang hakbang para i-edit o ihinto ito';

  @override
  String get servicesAdvancedTitle => 'Mga advanced na setting';

  @override
  String get servicesAdvancedHint =>
      'I-customize ang serbisyong ito mula sa pangkalahatang setting — cycle, puntos, at pagpapangkat';

  @override
  String get servicesGroupLabel => 'Grupo';

  @override
  String get servicesNoGroup => 'Walang grupo';

  @override
  String get servicesNewGroup => 'Bagong grupo';

  @override
  String get servicesFollowGeneralAction => 'Sundin ang pangkalahatan';

  @override
  String get servicesCustomizeAction => 'I-customize';

  @override
  String servicesFollowUpDays(int n) {
    return 'Follow-up pagkatapos ng $n araw';
  }

  @override
  String servicesPointsPerVisit(int n) {
    return '$n puntos';
  }

  @override
  String servicesSuggestionText(int n) {
    return '$n serbisyo ang may parehong halaga — ang pagsasama-sama sa kanila ay nagpapadali sa pag-edit sa kanila nang magkasama sa hinaharap.';
  }

  @override
  String servicesFollowsGeneral(String hint) {
    return 'Sumusunod sa pangkalahatan — $hint';
  }

  @override
  String get servicesPageTabServices => 'Mga serbisyo';

  @override
  String get servicesPageTabPackages => 'Mga package';

  @override
  String get servicesPackageAdd => 'Magdagdag ng package';

  @override
  String get servicesPackageNeedsTwoServices =>
      'Nangangailangan ang package ng hindi bababa sa dalawang aktibong serbisyo';

  @override
  String get servicesPackageEmpty => 'Wala pang package';

  @override
  String get servicesPackageEditTitle => 'I-edit ang package';

  @override
  String get servicesPackageAddTitle => 'Magdagdag ng bagong package';

  @override
  String get servicesPackageNameLabel => 'Pangalan ng package';

  @override
  String get servicesPackagePriceRequired =>
      'Kailangan ang presyo ng package, higit sa zero';

  @override
  String get servicesPackageServicesLabel => 'Kasamang mga serbisyo';

  @override
  String get servicesImportTitle => 'Mag-import ng mga serbisyo mula sa file';

  @override
  String get servicesImportHint =>
      'CSV file na may mga column: name, price, duration_minutes, cycle_days, description';

  @override
  String get servicesImportPickFile => 'Pumili ng CSV file';

  @override
  String get servicesImportReadFailed => 'Hindi mabasa ang file';

  @override
  String get servicesImportParseFailed =>
      'Walang name column ang file, o hindi wasto ang format nito';

  @override
  String get servicesImportDeactivateMissing =>
      'Ihinto ang mga serbisyong wala sa file';

  @override
  String get servicesImportDeactivateMissingHint =>
      'Ang anumang serbisyong mayroon ka ngayon na wala sa file na ito ay awtomatikong ihihinto';

  @override
  String get servicesImportConfirm => 'I-import';

  @override
  String get servicesImportClose => 'Tapos na';

  @override
  String servicesImportRowCount(int n) {
    String _temp0 = intl.Intl.pluralLogic(
      n,
      locale: localeName,
      other: '$n rows',
      one: '1 row',
    );
    return '$_temp0 na handa nang i-import';
  }

  @override
  String servicesImportDone(int created, int updated, int reactivated) {
    return 'Nadagdag $created, na-update $updated, na-reactivate $reactivated.';
  }

  @override
  String get visitPackagesSectionTitle => 'Mga featured na package';

  @override
  String get visitNameFieldHint => 'Pangalan ng customer (opsyonal)';

  @override
  String get visitMeterFieldHint => 'Reading ng odometer';

  @override
  String get visitQuantityDialogTitle => 'Dami';

  @override
  String get visitCouponCheckboxLabel =>
      'Magbigay ng discount coupon sa ibang tindahan';

  @override
  String get visitCouponPhoneHint => 'Numero ng may-ari ng tindahan';

  @override
  String get visitClearAllButton => 'I-clear lahat';

  @override
  String visitServicesSelectedCount(int n) {
    String _temp0 = intl.Intl.pluralLogic(
      n,
      locale: localeName,
      other: '$n serbisyo ang napili',
      one: '1 serbisyo ang napili',
    );
    return '$_temp0';
  }

  @override
  String get visitTodayBookingsTitle => 'Mga appointment ngayon';

  @override
  String get visitBookingAttendFailed =>
      'Hindi na-confirm ang pagdating, subukan ulit';

  @override
  String get branchSwitcherChooseBranch => 'Pumili ng sangay';

  @override
  String get branchSwitcherTitle => 'Kasalukuyang sangay';

  @override
  String get branchSwitcherHint =>
      'Ang lahat ng bubuksan mo pagkatapos nito ay para sa sangay na ito';

  @override
  String get proceduresPrintFailed => 'Hindi magawa ang dokumento';

  @override
  String get proceduresTitle => 'Mga Pamamaraan';

  @override
  String get proceduresSubtitle =>
      'I-set ang checklist ng pamamaraan para sa bawat serbisyo, o pamahalaan ang buong shared library. I-long-press ang serbisyo para piliin ito para sa pag-print';

  @override
  String get proceduresLibraryLink => 'Library ng Pamamaraan';

  @override
  String get proceduresPrint => 'I-print';

  @override
  String get proceduresEmptyTitle => 'Wala pang aktibong serbisyo';

  @override
  String get servicesStepSeverityNormal => 'Normal';

  @override
  String get servicesStepSeverityCritical => 'Kritikal';

  @override
  String get proceduresSaveFailed => 'Hindi ma-save';

  @override
  String get proceduresDrawerSubtitle =>
      'I-drag para ayusin, o magdagdag ng hakbang mula sa library';

  @override
  String get proceduresDrawerEmpty =>
      'Wala pang hakbang para sa serbisyong ito';

  @override
  String get proceduresDrawerAddButton => 'Idagdag mula sa library';

  @override
  String get proceduresPickTitle => 'Pumili ng hakbang';

  @override
  String get proceduresPickClose => 'Isara';

  @override
  String get proceduresPickApply => 'Idagdag';

  @override
  String get proceduresPickSearch => 'Maghanap ng hakbang';

  @override
  String get proceduresPickEmpty => 'Walang resulta';

  @override
  String get proceduresPickCreatePlaceholder => 'Bagong hakbang...';

  @override
  String get proceduresLibrarySaveFailed => 'Hindi ma-save';

  @override
  String get proceduresLibraryTitle => 'Library ng Pamamaraan';

  @override
  String get proceduresLibrarySubtitle =>
      'Bawat hakbang dito ay shared sa lahat ng serbisyong gumagamit nito - ang pag-edit nito ay nagbabago saanman';

  @override
  String get proceduresLibraryNewPlaceholder => 'Teksto ng bagong hakbang';

  @override
  String get proceduresLibraryAdd => 'Idagdag';

  @override
  String get proceduresLibraryShowRetired => 'Ipakita ang mga retirado';

  @override
  String get proceduresLibraryEmpty => 'Wala pang hakbang';

  @override
  String get proceduresLibraryRetired => 'Retirado';

  @override
  String get proceduresLibraryRetire => 'I-retire';

  @override
  String get proceduresLibraryReactivate => 'I-reactivate';

  @override
  String get proceduresSeverityHint =>
      'Ang kritikal na hakbang ay naka-highlight para sa staff at hindi maaaring laktawan habang ginagawa ang serbisyo';

  @override
  String proceduresSelectedCount(int n) {
    return '$n napili';
  }

  @override
  String proceduresStepCount(int n) {
    return '$n hakbang';
  }

  @override
  String proceduresUsedIn(int n) {
    return 'Ginagamit sa $n serbisyo';
  }

  @override
  String get referralProposeButton => 'Mag-propose ng partnership';

  @override
  String get referralTitle => 'Strategic na Partnership';

  @override
  String get referralSubtitle =>
      'Ilipat ang tunay na customer sa pagitan mo at ibang tindahan, sa magkabilang pagsang-ayon';

  @override
  String get referralRoleAll => 'Lahat';

  @override
  String get referralRoleReferrer => 'Bilang referrer';

  @override
  String get referralRoleBeneficiary => 'Bilang beneficiary';

  @override
  String get referralLoadFailed => 'Hindi ma-load ang mga partnership';

  @override
  String get referralEmptyTitle => 'Wala pang partnership';

  @override
  String get referralKpiAsReferrer => 'Bilang referrer';

  @override
  String get referralKpiAsBeneficiary => 'Bilang beneficiary';

  @override
  String get referralKpiSent => 'Na-refer';

  @override
  String get referralKpiRedeemed => 'Na-redeem';

  @override
  String get referralKpiRate => 'Redemption rate';

  @override
  String get referralConfirm => 'Kumpirmahin';

  @override
  String get referralGrantDiscountBlanket => 'Diskwento sa buong bisita';

  @override
  String get referralStatusProposed => 'Iminungkahi';

  @override
  String get referralStatusActive => 'Aktibo';

  @override
  String get referralStatusPaused => 'Naka-pause';

  @override
  String get referralStatusCancelRequested => 'Hiniling na kanselahin';

  @override
  String get referralStatusEnded => 'Tapos na';

  @override
  String get referralStatusRejected => 'Tinanggihan';

  @override
  String get referralStatusExpiredUnanswered => 'Nag-expire, walang sagot';

  @override
  String get referralEventProposed => 'Iminungkahi ang partnership';

  @override
  String get referralEventAccepted => 'Tinanggap ang partnership';

  @override
  String get referralEventRejected => 'Tinanggihan ang partnership';

  @override
  String get referralEventActivated => 'Na-activate ang partnership';

  @override
  String get referralEventCancelRequested => 'Hiniling na kanselahin';

  @override
  String get referralEventCancelConfirmed => 'Nakumpirma ang pagkansela';

  @override
  String get referralEventExpiredUnanswered => 'Nag-expire nang walang sagot';

  @override
  String get referralEventPaused => 'Naka-pause';

  @override
  String get referralEventResumed => 'Ipinagpatuloy';

  @override
  String get referralEventEndedTerm => 'Natapos ang termino';

  @override
  String get referralEventGrantCreated => 'Bagong grant';

  @override
  String get referralEventGrantRedeemed => 'Na-redeem ang grant';

  @override
  String get referralActivityActive => 'Aktibo';

  @override
  String get referralActivityPaused => 'Naka-pause';

  @override
  String get referralActivityPending => 'Naghihintay ng sagot';

  @override
  String get referralActivityInactive => 'Hindi aktibo';

  @override
  String get referralScorecardTitle => 'Pagganap';

  @override
  String get referralScorecardFailed => 'Hindi ma-load ang pagganap';

  @override
  String get referralActivityTitle => 'Kamakailang aktibidad';

  @override
  String get referralActivityEmpty => 'Wala pang aktibidad';

  @override
  String get referralAgreementsTitle => 'Mga kasunduan';

  @override
  String get referralConfirmCancel => 'Tapusin na ang partnership na ito?';

  @override
  String get referralActionAccept => 'Tanggapin';

  @override
  String get referralActionReject => 'Tanggihan';

  @override
  String get referralActionWaitingThem => 'Naghihintay sa kabilang panig';

  @override
  String get referralActionCancelRequest => 'Humiling na tapusin';

  @override
  String get referralActionCancelConfirm => 'Kumpirmahin ang pagtatapos';

  @override
  String get referralProposeTitle => 'Mag-propose ng bagong partnership';

  @override
  String get referralProposePhoneLabel => 'Numero ng ibang tindahan';

  @override
  String get referralProposeConditionLabel =>
      'Kondisyon ng pagiging karapat-dapat sa iyong tindahan';

  @override
  String get referralConditionMinTotal => 'Pinakamababang invoice';

  @override
  String get referralConditionServiceId => 'Isang partikular na serbisyo';

  @override
  String get referralProposeConditionValueRiyals => 'Halaga (SAR)';

  @override
  String get referralProposeConditionValueService => 'Serbisyo';

  @override
  String get referralProposeValidityLabel => 'Bisa (araw)';

  @override
  String get referralProposeDurationLabel => 'Tagal (araw)';

  @override
  String get referralProposeCapLabel => 'Limit / 30 araw';

  @override
  String get referralProposeGrantTypeLabel => 'Uri ng grant';

  @override
  String get referralGrantTypeDiscount => 'Diskwento';

  @override
  String get referralGrantTypeGift => 'Regalo';

  @override
  String get referralScopeBlanket => 'Buong bisita';

  @override
  String get referralScopeItem => 'Isang partikular na serbisyo';

  @override
  String get referralScopeGroup => 'Grupo/package';

  @override
  String get referralProposeServiceLabel => 'Serbisyo';

  @override
  String get referralProposeGroupLabel => 'Grupo';

  @override
  String get referralProposeImmutableNote =>
      'Ang mga termino ng grant ay fixed na pagkatapos ipadala — kailangan ng bagong kasunduan para sa ibang alok';

  @override
  String get referralProposeSubmitting => 'Ipinapadala...';

  @override
  String get referralProposeSubmit => 'Ipadala ang panukala';

  @override
  String referralGrantGift(String name) {
    return 'Regalo: $name';
  }

  @override
  String referralGrantDiscountItem(String name) {
    return 'Diskwento sa: $name';
  }

  @override
  String referralGrantDiscountGroup(String name) {
    return 'Diskwento sa grupo: $name';
  }

  @override
  String referralPartnerCount(int n) {
    return '$n kasunduan';
  }

  @override
  String get referralProposeResultFail => 'Hindi maipadala ang panukala';

  @override
  String get referralRefusal402 =>
      'Hindi subscribed ang tindahan mo sa Strategic Partnership app — mag-subscribe muna sa app store';

  @override
  String get referralRefusal403 => 'Wala kang pahintulot para sa aksyong ito';

  @override
  String get referralRefusal400 =>
      'Hindi valid ang datos ng panukala — suriin ang kondisyon, o baka ikaw mismo ang minumungkahi mong partner';

  @override
  String get referralRefusal404 =>
      'Walang natagpuang tindahan sa numerong iyon, o wala ang napiling serbisyo/grupo sa katalogo ng kabilang tindahan';

  @override
  String get referralRefusal409 =>
      'Naabot mo na ang limitasyon na 3 aktibong partnership, o nagbago ang estado ng partnership';

  @override
  String get referralRefusal503 =>
      'Pansamantalang hindi available ang billing, subukan muli mamaya';

  @override
  String get appStoreTitle => 'App Store';

  @override
  String get appStoreSubtitle =>
      'Palaguin ang tindahan mo gamit ang totoong apps, isa-isa';

  @override
  String get appStoreTabMine => 'Mga app ko';

  @override
  String get appStoreTabAll => 'App Store';

  @override
  String get appStoreDetails => 'Detalye';

  @override
  String get appStorePerMonth => 'kada buwan';

  @override
  String get appStorePerMonthShort => '/buwan';

  @override
  String get appStoreActive => 'Aktibo';

  @override
  String get appStoreTrialing => 'Trial';

  @override
  String get appStoreSubscribe => 'Mag-subscribe ngayon';

  @override
  String get appStoreCancelRenewal => 'Ihinto ang renewal';

  @override
  String get appStoreUndoCancel => 'I-undo ang pagkanselá';

  @override
  String get appStoreConfirmCancel =>
      'Ihinto ang renewal ng app na ito? Mananatiling aktibo hanggang matapos ang bayad na yugto';

  @override
  String appStoreCartCount(int n) {
    return '$n sa cart';
  }

  @override
  String get appStoreCheckout => 'Mag-checkout';

  @override
  String get appStoreCheckingOut => 'Nagche-checkout...';

  @override
  String get appStoreRefusal402 =>
      'Hindi pa naka-enable ang bayad sa account mo ngayon — makipag-ugnayan para i-enable';

  @override
  String get appStoreRefusal403 =>
      'Wala kang pahintulot na kumpletuhin ang bilhing ito';

  @override
  String get appStoreRefusal404 =>
      'Hindi nahanap ang planong hiniling — i-refresh at subukan ulit';

  @override
  String get appStoreRefusal409 =>
      'May-ari na ng app na ito, o nagbago ang kalagayan nito habang bumibili';

  @override
  String get appStoreRefusalGeneric =>
      'Hindi nakumpleto ang pagbili, subukan ulit';

  @override
  String get appStoreCapacityTitle => 'Kapasidad';

  @override
  String appStoreCapacityConfirmRemove(String name) {
    return 'Alisin ang huling unit ng \"$name\"? Ihihinto nito ang buong renewal';
  }

  @override
  String get whatsappAssistantTitle => 'AI Assistant';

  @override
  String get whatsappAssistantSubtitle =>
      'Sumasagot sa mga customer mo sa WhatsApp para sa iyo, iminumungkahi ang mga plano mo at ang points nila sa tamang sandali.';

  @override
  String get whatsappAssistantLoadFailed =>
      'Hindi na-load ang settings ng assistant.';

  @override
  String get whatsappAssistantConfirm => 'Kumpirmahin';

  @override
  String get whatsappAssistantSaveFailed => 'Hindi na-save, subukan ulit.';

  @override
  String get whatsappAssistantToggleTitle => 'Sumasagot ang assistant';

  @override
  String get whatsappAssistantToggleDesc =>
      'Ang pag-off ay kumpletong iki-lock ang assistant, nang hindi kinakansela ang subscription mo — buksan muli anumang oras.';

  @override
  String get whatsappAssistantToggleConfirmEnableTitle =>
      'I-on ang AI assistant?';

  @override
  String get whatsappAssistantToggleConfirmEnableBody =>
      'Magsisimula itong sumagot sa mga customer mo sa WhatsApp agad.';

  @override
  String get whatsappAssistantToggleConfirmDisableTitle =>
      'I-off ang AI assistant?';

  @override
  String get whatsappAssistantToggleConfirmDisableBody =>
      'Hihinto itong sumagot nang tuluyan, na parang hindi ka nag-subscribe — nang hindi kinakansela ang subscription mismo.';

  @override
  String get whatsappAssistantNotesTitle => 'Mga tala ng tindahan';

  @override
  String get whatsappAssistantNotesDesc =>
      'Ang isinusulat mo dito ay tumutulong sa assistant na paglingkuran ang mga customer mo nang may karagdagang konteksto tungkol sa tindahan mo.';

  @override
  String get whatsappAssistantWordLimitTitle =>
      'Limitasyon ng salita ng mensahe ng customer';

  @override
  String get whatsappAssistantWordLimitDesc =>
      'Ang pinakamahabang mensaheng tinatanggap ng assistant mula sa customer bago hilingin sa kanyang paikliin ito.';

  @override
  String get whatsappAssistantAutoRegisterTitle =>
      'Awtomatikong pagrehistro ng contact';

  @override
  String get whatsappAssistantAutoRegisterDesc =>
      'Anumang bagong numerong magme-message sa WhatsApp mo ay awtomatikong ise-save bilang tunay na contact.';

  @override
  String get whatsappAssistantAutoRegisterConfirmEnableTitle =>
      'I-on ang awtomatikong pagrehistro?';

  @override
  String get whatsappAssistantAutoRegisterConfirmEnableBody =>
      'Ang lahat ng magme-message sa WhatsApp number mo ay awtomatikong ise-save bilang contact, kahit sa iisang mensahe lang.';

  @override
  String get whatsappAssistantAutoRegisterConfirmDisableTitle =>
      'I-off ang awtomatikong pagrehistro?';

  @override
  String get whatsappAssistantAutoRegisterConfirmDisableBody =>
      'Ang mga bagong numero ay hindi na awtomatikong ise-save bilang contact.';

  @override
  String get partnerLoyaltyTitle => 'Katapatan ng Kasosyo';

  @override
  String get partnerLoyaltySubtitle =>
      'Bumuo ng alyansa sa ibang tindahang nakarehistro sa amin at bigyan ito ng benepisyo sa subscription nito';

  @override
  String get partnerLoyaltyCapLabel => 'Kasalukuyang limitasyon mo';

  @override
  String get partnerLoyaltyPrefsTitle =>
      'Checkbox ng alyansa habang nagre-record ng bisita';

  @override
  String get partnerLoyaltyPrefsDesc =>
      'Ang pag-on dito ay nagbibigay-daan sa sinumang staff na nagre-record ng bisita na bumuo ng alyansa sa parehong sandali.';

  @override
  String get partnerLoyaltyGrantTitle => 'Bumuo ng alyansa';

  @override
  String get partnerLoyaltyPhoneLabel =>
      'Numero ng telepono ng katuwang na tindahan';

  @override
  String get partnerLoyaltyPhoneHintOk =>
      'Walang alyansa sa kanila ngayong buwan';

  @override
  String get partnerLoyaltyPhoneHintAlready =>
      'May alyansa ka na sa kanila ngayong buwan';

  @override
  String get partnerLoyaltyPhoneHintUnregistered =>
      'Hindi ito nakarehistrong tindahan sa amin';

  @override
  String get partnerLoyaltyPercentLabel => 'Porsyento ng benepisyo';

  @override
  String partnerLoyaltyCapLine(int p) {
    return 'Pinakamataas na porsyentong maibibigay mo ngayon: $p%';
  }

  @override
  String get partnerLoyaltyScopeLabel => 'Sakop';

  @override
  String get partnerLoyaltyScopeAll => 'Lahat';

  @override
  String get partnerLoyaltySubmit => 'Buuin ang alyansa';

  @override
  String get partnerLoyaltySubmitting => 'Ipinapadala…';

  @override
  String get partnerLoyaltyResultSuccess =>
      'Nabuo ang alyansa — awtomatikong ilalapat sa susunod na pag-renew ng tindahan.';

  @override
  String get partnerLoyaltyResultPartial =>
      'Bahagyang nabuo — may ilang app na tinanggihan, buksan ang «Log» para sa detalye.';

  @override
  String get partnerLoyaltyOutcomeGranted => 'Tagumpay';

  @override
  String get partnerLoyaltyOutcomeInvalidPercent =>
      'Hindi tamang porsyento ng benepisyo';

  @override
  String get partnerLoyaltyOutcomeInvalidScope => 'Pumili ng tunay na app';

  @override
  String get partnerLoyaltyOutcomeOverCap =>
      'Lampas sa kasalukuyang limitasyon mo';

  @override
  String get partnerLoyaltyOutcomeNoAccount =>
      'Hindi ito nakarehistrong tindahan sa amin';

  @override
  String get partnerLoyaltyOutcomeNotSubscribed =>
      'Wala sa mga piniling app ang taglay ng tindahang iyon';

  @override
  String get partnerLoyaltyOutcomeBillingUnavailable =>
      'Hindi natapos, subukan muli';

  @override
  String get partnerLoyaltyOutcomeAlreadyHasBetterCoupon =>
      'May mas malakas nang benepisyo';

  @override
  String get partnerLoyaltyOutcomeCouponExpired => 'Expired na ang benepisyo';

  @override
  String get partnerLoyaltyOutcomeCouponExhausted => 'Naubos na ang benepisyo';

  @override
  String get partnerLoyaltyOutcomeCouponUnknown => 'Hindi kilalang benepisyo';

  @override
  String get partnerLoyaltyOutcomePlanMismatch =>
      'Hindi tugma ang benepisyo sa app na ito';

  @override
  String get partnerLoyaltyOutcomeCouponDisabled =>
      'Naka-disable ang benepisyo';

  @override
  String get partnerLoyaltyOutcomeCouponScheduled =>
      'Hindi pa nagsisimula ang benepisyo';

  @override
  String get partnerLoyaltyTabLog => 'Log';

  @override
  String get partnerLoyaltyTabStats => 'Estadistika';

  @override
  String get partnerLoyaltyLogSearchHint =>
      'Maghanap gamit ang huling 4 na digit';

  @override
  String get partnerLoyaltyLogFilterAll => 'Lahat ng status';

  @override
  String get partnerLoyaltyLogFilterOk => 'Matagumpay lang';

  @override
  String get partnerLoyaltyLogFilterFail => 'Nabigo lang';

  @override
  String get partnerLoyaltyLogEmptyTitle => 'Wala pang alyansa';

  @override
  String get partnerLoyaltyLogEmptyDesc => 'Lalabas dito ang unang alyansa mo.';

  @override
  String get partnerLoyaltyLogReadFailed => 'Hindi mabasa ang log';

  @override
  String get partnerLoyaltyStatsKpiMonth => 'Mga alyansa ngayong buwan';

  @override
  String get partnerLoyaltyStatsKpiCap => 'Kasalukuyang limitasyon mo';

  @override
  String get partnerLoyaltyStatsKpiCeiling =>
      'Pinakamataas na limitasyon ng platform';

  @override
  String get partnerLoyaltyStatsLadderTitle => 'Ang posisyon mo sa hagdan';

  @override
  String partnerLoyaltyStatsLadderNote(int n, int left, int p) {
    return '$n alyansa ngayong buwan — $left na lang para sa tier na $p%';
  }

  @override
  String partnerLoyaltyStatsLadderAtTop(int n) {
    return '$n alyansa ngayong buwan — nasa pinakamataas na tier ka na';
  }

  @override
  String partnerLoyaltyStatsCeilingNote(int p) {
    return 'Pinakamataas na limitasyon ng platform $p% — walang tindahang lalampas dito';
  }

  @override
  String get partnerLoyaltyStatsChartTitle =>
      'Bilang ng alyansa sa nakaraang 6 na buwan';

  @override
  String get partnerLoyaltyReadFailedTitle => 'Hindi mabasa ang datos mo';

  @override
  String get partnerLoyaltyReadFailedDesc =>
      'Subukan muli sa ibang pagkakataon.';

  @override
  String get shopReadFailed => 'Hindi mabasa ang mga indikador ng tindahan mo';

  @override
  String get shopMultiBranchTitle => 'Pumili ng sangay';

  @override
  String get shopMultiBranchDesc =>
      'May higit sa isang sangay ka — pumili ng isa para makita ang mga indikador nito.';

  @override
  String get shopEmptyBranchTitle => 'Wala pang datos para sa sangay na ito';

  @override
  String get shopRetentionTitle => 'Rate ng pagbalik ng mga customer mo';

  @override
  String get shopRetentionMutedNote =>
      'Hindi pa sapat ang mga bisita para kalkulahin ito.';

  @override
  String get shopRetentionBrandNew =>
      'I-rehistro ang unang bisita para makita ang rate ng pagbalik.';

  @override
  String get shopRegisterFirstVisit => 'Irehistro ang unang bisita';

  @override
  String get shopRetentionPrefix10 =>
      'Sa bawat 10 customer na bumisita sa iyo,';

  @override
  String get shopRetentionSuffix => 'ang bumalik';

  @override
  String get shopOneCustomer => 'Isang customer ang bumisita sa iyo';

  @override
  String shopNCustomers(int n) {
    return '$n customer ang bumisita sa iyo';
  }

  @override
  String shopRetentionSmallPrefix(String base) {
    return '$base, kung saan';
  }

  @override
  String shopOverNMonths(int n) {
    return 'sa loob ng $n buwan';
  }

  @override
  String get shopUnlimited => 'Walang limitasyon';

  @override
  String get shopTileSentToday => 'Naipadala ngayon';

  @override
  String get shopTileWaiting => 'Naghihintay';

  @override
  String get shopTileCeilingRemaining => 'Natitira ngayon';

  @override
  String get shopNextStepLabel => 'Susunod na hakbang';

  @override
  String get shopNotNow => 'Hindi ngayon';

  @override
  String get shopDeckUrgent => 'Agaran';

  @override
  String get shopDeckWeek => 'Ngayong linggo';

  @override
  String get shopDeckOpportunities => 'Mga pagkakataon';

  @override
  String get shopComputedNow => 'Nakalkula ngayon';

  @override
  String shopComputedHoursAgo(int n) {
    return 'Nakalkula $n oras ang nakalipas';
  }

  @override
  String get shopStale => 'Luma na';

  @override
  String get shopRefreshAction => 'I-refresh';

  @override
  String get shopComputingTitle => 'Kinakalkula ang mga indikador mo';

  @override
  String get shopComputeLoading => 'Kinakalkula…';

  @override
  String get shopComputeAction => 'Kalkulahin ngayon';

  @override
  String get shopAtRiskTitle => 'Mga customer na malapit nang umalis';

  @override
  String get shopAtRiskMutedNote => 'Hindi pa sapat ang datos.';

  @override
  String get shopAtRiskAllGood =>
      'Walang overdue na customer ngayon — maayos ang lahat';

  @override
  String get shopWaNotConnected =>
      'Hindi pa nakakonekta ang WhatsApp ng tindahan mo';

  @override
  String get shopWaNotVerified =>
      'Hindi pa na-verify ang numero ng WhatsApp ng tindahan mo';

  @override
  String get shopCeilingReached =>
      'Naabot mo na ang limitasyon ng mensahe ngayong araw';

  @override
  String shopDaysOverdue(int n) {
    return '$n araw na overdue';
  }

  @override
  String get shopAtRiskCta => 'Magpadala ng win-back campaign';

  @override
  String get shopAiImpactTitle => 'Epekto ng AI assistant sa WhatsApp';

  @override
  String get shopAiConversations => 'Mga usapan';

  @override
  String get shopAiBookings => 'Mga booking';

  @override
  String get shopAiUpsellRate => 'Pagtanggap sa upsell';

  @override
  String get shopWeekMutedTitle => 'Mga bisita ngayong linggo';

  @override
  String get shopWeekMutedNote => 'Hindi pa sapat ang datos.';

  @override
  String get shopNewReturningMutedTitle =>
      'Bago kumpara sa bumabalik na customer';

  @override
  String get shopNewReturningMutedNote => 'Hindi pa sapat ang datos.';

  @override
  String get shopBranchCompareTitle => 'Paghahambing ng sangay';

  @override
  String get shopBranchCompareMutedNote =>
      'Kailangan ng hindi bababa sa dalawang sangay para maihambing.';

  @override
  String get shopStaffCompareTitle => 'Paghahambing ng staff';

  @override
  String get shopStaffCompareMutedNote =>
      'Kailangan ng hindi bababa sa dalawang staff para maihambing.';

  @override
  String get shopWeekTitle => 'Mga bisita ngayong linggo';

  @override
  String get shopNewReturningTitle => 'Bago kumpara sa bumabalik';

  @override
  String get shopNewLabel => 'Bago:';

  @override
  String get shopReturningLabel => 'Bumabalik:';

  @override
  String get shopServicesTitle => 'Mga serbisyo mo';

  @override
  String get shopServicesMutedNote => 'Hindi pa sapat ang datos.';

  @override
  String get shopMessageFlowTitle => 'Epekto ng reminder message';

  @override
  String get shopMutedMessageFlowNote => 'Hindi pa sapat ang datos.';

  @override
  String get shopHoldoutTitle => 'Paghahambing: na-message kumpara sa hindi';

  @override
  String get shopMutedHoldoutNote => 'Sinusukat pa.';

  @override
  String shopReturnedAfterReminder(int visits, int days) {
    return '$visits bisita sa loob ng $days araw pagkatapos ng reminder';
  }

  @override
  String shopOptOutRate(String p) {
    return '$p% ang humiling na itigil ang mensahe';
  }

  @override
  String get shopHoldoutNoMessages => 'Walang mensahe';

  @override
  String get shopHoldoutReached => 'Na-message';

  @override
  String get shopHoldoutOff =>
      'Naka-off ang pagsukat ng epekto ng mensahe — natatanggap ng lahat ng customer mo ang lahat, kaya walang grupong maikukumpara.';

  @override
  String shopHoldoutMeasuring(int min, int need) {
    return 'Sinusukat pa namin ang epekto ng mensahe sa tindahan mo — $min sa $need sa mas maliit na grupo.';
  }

  @override
  String shopTodayRetrying(int n) {
    return 'May $n mensaheng sinusubukan pa ring makalabas';
  }

  @override
  String get shopTrendUp => 'gumagaling';

  @override
  String get shopTrendDown => 'bumababa';

  @override
  String shopRetentionSincePeriods(int n) {
    return 'sa loob ng $n yugto';
  }

  @override
  String get shopAtLeastSuffix => ' — kahit man lang';

  @override
  String get shopRegisterFirstVisitArrow => 'Irehistro ang unang bisita ←';

  @override
  String get shopWeekNoCompare =>
      'Wala pa kaming kumpletong linggo para ikumpara';

  @override
  String shopNextStepAlso(String msg) {
    return 'Dagdag pa: $msg';
  }

  @override
  String shopBranchCompareUnassigned(int n) {
    return '$n bisitang walang itinalagang branch — hindi naibilang sa kahit anong branch.';
  }

  @override
  String get shopBranchCompareNeedTwo =>
      'Hindi pa namin ikinukumpara ang mga branch — kailangan ng dalawa o higit pang branch na may totoong bisita.';

  @override
  String get shopBranchCompareNeedSecond =>
      'Isang aktibong branch pa lamang — kailangan ng pangalawang branch na may totoong bisita para sa paghahambing.';

  @override
  String get shopBranchCompareTooShort =>
      'Hindi pa namin ini-rank ang mga branch — maikli pa ang panahon, at hindi pa makatarungan ang paghahambing sa pinakabago.';

  @override
  String shopStaffCompareUnassigned(int n) {
    return '$n bisitang walang itinalagang staff — hindi naibilang kaninuman.';
  }

  @override
  String get shopStaffCompareNeedTwo =>
      'Hindi pa namin ikinukumpara ang staff — kailangan ng dalawa o higit pang staff na may naitalagang bisita.';

  @override
  String get shopStaffCompareNeedSecond =>
      'Isang naitalagang staff pa lamang — kailangan ng pangalawa na may totoong bisita para sa paghahambing.';

  @override
  String get shopStaffCompareTooShort =>
      'Hindi pa namin ini-rank ang staff — maikli pa ang panahon, at hindi pa makatarungan ang paghahambing sa pinakabago.';

  @override
  String get shopPeakTitle => 'Mga pinaka-busy mong oras';

  @override
  String get shopPeakMutedNote =>
      'Kailangan ng mga bisitang kumalat sa sapat na araw at oras para maiguhit.';

  @override
  String shopPeakBusiestTime(String day, int h) {
    return '$day humigit-kumulang $h:00';
  }

  @override
  String shopPeakBusiestNote(String name) {
    return 'Ang pinaka-busy mong oras: $name.';
  }

  @override
  String get shopEntityDayServicesTitle =>
      'Mga serbisyo mo ayon sa araw ng linggo';

  @override
  String get shopEntityDayServicesHint =>
      'Aling serbisyo ang mas hinihiling sa tiyak na araw — tumutulong ito sa paghahanda ng tamang staff sa araw na iyon.';

  @override
  String get shopEntityDayServicesMutedNote =>
      'Kailangan ng mga bisitang kumalat sa sapat na araw para maiguhit.';

  @override
  String get shopEntityDayBranchesTitle =>
      'Mga branch mo ayon sa araw ng linggo';

  @override
  String get shopEntityDayBranchesHint =>
      'Hindi kailangang magkapareho ang ritmo ng mga branch mo — busy ang branch sa mall sa holiday, busy ang branch sa neighborhood pagkatapos ng trabaho.';

  @override
  String get shopEntityDayBranchesMutedNote =>
      'Kailangan ng pangalawang branch at mga bisitang kumalat sa sapat na araw para maiguhit.';

  @override
  String get shopBundlesTitle => 'Mga iminumungkahing bundle';

  @override
  String get shopBundlesMutedNote =>
      'Kulang pa ang mga association para makapagmungkahi ng bundle mula rito.';

  @override
  String shopBundlesOpportunity(int n) {
    return '$n pagkakataon';
  }

  @override
  String get shopAssociationsTitle => 'Madalas hilingin nang magkasama';

  @override
  String get shopAssociationsMutedNote => 'Kulang pa ang mga association.';

  @override
  String shopAssociationsLearningNote(int have, int need) {
    return 'Hindi pa namin alam kung ano ang hinihiling kasama ng ano — kailangan ng mas maraming bisita ang pagtukoy ng association para totoo ang resulta, hindi lang pagkakataon. ($have/$need)';
  }

  @override
  String shopCustomersCount(int n) {
    return '$n customer';
  }

  @override
  String get shopDay0Short => 'Lin';

  @override
  String get shopDay1Short => 'Lun';

  @override
  String get shopDay2Short => 'Mar';

  @override
  String get shopDay3Short => 'Miy';

  @override
  String get shopDay4Short => 'Huw';

  @override
  String get shopDay5Short => 'Biy';

  @override
  String get shopDay6Short => 'Sab';

  @override
  String get shopDay0Full => 'Linggo';

  @override
  String get shopDay1Full => 'Lunes';

  @override
  String get shopDay2Full => 'Martes';

  @override
  String get shopDay3Full => 'Miyerkules';

  @override
  String get shopDay4Full => 'Huwebes';

  @override
  String get shopDay5Full => 'Biyernes';

  @override
  String get shopDay6Full => 'Sabado';
}
