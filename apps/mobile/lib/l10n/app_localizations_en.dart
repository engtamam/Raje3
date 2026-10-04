// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class SEn extends S {
  SEn([String locale = 'en']) : super(locale);

  @override
  String get appName => 'Raje3';

  @override
  String get ok => 'OK';

  @override
  String get cancel => 'Cancel';

  @override
  String get save => 'Save';

  @override
  String get close => 'Close';

  @override
  String get back => 'Back';

  @override
  String get next => 'Next';

  @override
  String get done => 'Done';

  @override
  String get loading => 'Loading...';

  @override
  String get retry => 'Retry';

  @override
  String get error => 'An error occurred';

  @override
  String get success => 'Success';

  @override
  String get search => 'Search';

  @override
  String get login => 'Log in';

  @override
  String get logout => 'Log out';

  @override
  String get homeDashboardTitle => 'Dashboard';

  @override
  String get homeShopSectionLabel => 'My shop';

  @override
  String get homeLoadErrorTitle => 'Couldn\'t load';

  @override
  String get homeLoadErrorMessage => 'Couldn\'t load today\'s data. Try again.';

  @override
  String get homeTodaySectionTitle => 'Today';

  @override
  String get homeStatSent => 'Sent';

  @override
  String get homeStatWaiting => 'Waiting';

  @override
  String get homeStatRetrying => 'Retrying';

  @override
  String get homeDashboardComputing =>
      'Calculating your shop\'s metrics now — refresh shortly.';

  @override
  String get homeDashboardSectionTitle => 'Shop metrics';

  @override
  String get homeDashboardEmpty => 'Not enough data yet.';

  @override
  String get themeDarkMode => 'Dark mode';

  @override
  String get themeLightMode => 'Light mode';

  @override
  String get validatorFieldRequiredGeneric => 'This field is required';

  @override
  String validatorFieldRequiredNamed(String field) {
    return '$field is required';
  }

  @override
  String get validatorEmailRequired => 'Email is required';

  @override
  String get validatorEmailInvalid => 'Invalid email address';

  @override
  String get validatorPhoneRequired => 'Phone number is required';

  @override
  String get validatorPhoneInvalid =>
      'Invalid phone number — it must start with 05';

  @override
  String get validatorPasswordRequired => 'Password is required';

  @override
  String get validatorPasswordTooShort =>
      'Password must be at least 8 characters';

  @override
  String get validatorPasswordNeedsUppercase =>
      'Password must contain an uppercase letter';

  @override
  String get validatorPasswordNeedsLowercase =>
      'Password must contain a lowercase letter';

  @override
  String get validatorPasswordNeedsDigit => 'Password must contain a number';

  @override
  String get validatorConfirmPasswordFieldName => 'Confirm password';

  @override
  String get validatorPasswordMismatch => 'Passwords do not match';

  @override
  String get validatorOtpRequired => 'Verification code is required';

  @override
  String get validatorOtpLength => 'Verification code must be 6 digits';

  @override
  String get validatorOtpDigitsOnly =>
      'Verification code must contain digits only';

  @override
  String get validatorNameRequired => 'Name is required';

  @override
  String get validatorNameTooShort => 'Name must be at least 2 characters';

  @override
  String get validatorNameTooLong => 'Name must not exceed 100 characters';

  @override
  String get validatorNameInvalidChars =>
      'Name contains characters that are not allowed';

  @override
  String get validatorGenericFieldName => 'This field';

  @override
  String validatorMinLengthNamed(String field, int minLength) {
    return '$field must be at least $minLength characters';
  }

  @override
  String validatorMaxLengthNamed(String field, int maxLength) {
    return '$field must not exceed $maxLength characters';
  }

  @override
  String get validatorGenericValueName => 'The value';

  @override
  String validatorNotANumberNamed(String field) {
    return '$field must be a number';
  }

  @override
  String validatorMinValueNamed(String field, String min) {
    return '$field must be at least $min';
  }

  @override
  String validatorMaxValueNamed(String field, String max) {
    return '$field must not exceed $max';
  }

  @override
  String get validatorUrlRequired => 'URL is required';

  @override
  String get validatorUrlInvalid => 'Invalid URL';

  @override
  String get urlHelperUnavailable => 'The link is not available';

  @override
  String get urlHelperOpenFailed => 'Couldn\'t open the link';

  @override
  String get routerScreenNotOnMobileYet =>
      'This screen isn\'t available on the mobile app yet.';

  @override
  String get kbHintNoEntry => 'No explanation for this yet.';

  @override
  String get assistantChatTitle => 'Assistant';

  @override
  String get assistantInputHint => 'Type your question...';

  @override
  String get assistantSend => 'Send';

  @override
  String get assistantUnavailable =>
      'The assistant is not available right now.';

  @override
  String get assistantPreparing => 'Preparing the assistant...';

  @override
  String get assistantRetryDownload => 'Retry';

  @override
  String get assistantSpeak => 'Listen to the answer';

  @override
  String get assistantStopSpeaking => 'Stop speaking';

  @override
  String get assistantActionUnavailable => 'You can\'t do this right now.';

  @override
  String get assistantConfirm => 'Confirm';

  @override
  String get assistantCancel => 'Cancel';

  @override
  String get assistantReplySettingsTooltip => 'Reply settings';

  @override
  String get assistantReplyModeTitle => 'How the assistant replies';

  @override
  String get assistantReplyModeSubtitle =>
      'Applies to every answer, even if you asked by voice';

  @override
  String get assistantReplyModeVoice => 'Voice';

  @override
  String get assistantReplyModeText => 'Written text';

  @override
  String get authLoginSubtitle => 'Sign in to continue';

  @override
  String get authPhoneLabel => 'Mobile number';

  @override
  String get authPasswordLabel => 'Password';

  @override
  String get authNoShopYetLabel => 'Don\'t have a shop yet?';

  @override
  String get authOpenNewShopCta => 'Open a new shop';

  @override
  String get authOpenShopTitle => 'Open a new shop';

  @override
  String get authSignupSubtitle => 'Just three steps to open your shop';

  @override
  String get authShopNameLabel => 'Shop name';

  @override
  String get authOwnerNameLabel => 'Your name (optional)';

  @override
  String get authAlreadyHaveShopCta => 'Already have a shop? Log in';

  @override
  String get authOpenShopCta => 'Open the shop';

  @override
  String get authVerifyPhoneTitle => 'Verify mobile number';

  @override
  String authVerifyCodeSentTo(String phone) {
    return 'We sent a verification code to $phone';
  }

  @override
  String get authVerifying => 'Verifying...';

  @override
  String get authConfirmCta => 'Confirm';

  @override
  String get authResendCodeCta => 'Resend code';

  @override
  String get authSendCodeCta => 'Send code';

  @override
  String get authCodeSendFailedFallback => 'Couldn\'t send the code.';

  @override
  String get authOtpIncorrectFallback => 'Incorrect verification code.';

  @override
  String get visitCatalogueLoadErrorFallback =>
      'Couldn\'t load the services. Pull down to retry.';

  @override
  String get visitEnterCustomerPhone => 'Enter the customer\'s mobile number';

  @override
  String get visitSelectAtLeastOneService => 'Select at least one service';

  @override
  String get visitSavedMessage => 'The visit has been recorded.';

  @override
  String get visitSaveErrorFallback => 'Couldn\'t record the visit.';

  @override
  String get visitSaveErrorNetworkFallback =>
      'Couldn\'t record the visit. Check your connection and try again.';

  @override
  String get visitTitle => 'Record a visit';

  @override
  String get visitCustomerSectionTitle => 'Customer';

  @override
  String get visitCustomerPhoneFieldLabel => 'Customer\'s mobile number';

  @override
  String get visitPlateFieldLabel => 'Plate number';

  @override
  String get visitPlateRequired =>
      'Enter a valid plate (at least one letter and one digit)';

  @override
  String visitKnownVehicle(String name) {
    return 'Known vehicle: $name';
  }

  @override
  String get visitNewVehicle => 'New vehicle';

  @override
  String visitKnownCustomer(String name) {
    return 'Known customer: $name';
  }

  @override
  String get visitNewCustomer => 'New customer';

  @override
  String get visitServicesSectionTitle => 'Services';

  @override
  String get visitNoServicesYet => 'No services yet.';

  @override
  String get visitNoteSectionTitle => 'Note (optional)';

  @override
  String get visitSaveButtonLabel => 'Save the visit';

  @override
  String get navAppsLabel => 'App store';

  @override
  String get navHomeLabel => 'Home';

  @override
  String get navAccountLabel => 'Account';

  @override
  String get homeGreetingMorning => 'Good morning';

  @override
  String get homeGreetingEvening => 'Good evening';

  @override
  String homeGreetingMorningNamed(String name) {
    return 'Good morning, $name';
  }

  @override
  String homeGreetingEveningNamed(String name) {
    return 'Good evening, $name';
  }

  @override
  String get homeAppsSectionTitle => 'Your apps';

  @override
  String get homeFeaturedStartNow => 'Start now';

  @override
  String get homeEmptyStateTitle => 'No apps available yet';

  @override
  String get homeEmptyStateBody =>
      'Contact the shop owner to add your permissions.';

  @override
  String get appsScreenTitle => 'My apps';

  @override
  String get appsScreenHint =>
      'Tap the pin icon to pin an app to the bottom bar\'s 5th slot';

  @override
  String get appsPinnedBadge => 'Pinned to the bar';

  @override
  String get appsPinAction => 'Pin here';

  @override
  String get homeLauncherEmptyTitle => 'No apps available';

  @override
  String get homeLauncherEmptyMessage =>
      'Contact support to activate an app for your shop';

  @override
  String get accountScreenTitle => 'My account';

  @override
  String get accountPhoneLabel => 'Phone number';

  @override
  String get accountLogoutAction => 'Log out';

  @override
  String get accountLogoutConfirmTitle => 'Log out';

  @override
  String get accountLogoutConfirmMessage =>
      'Do you want to log out of your account?';

  @override
  String get notificationsUnavailable => 'Notifications aren\'t available yet';

  @override
  String get notificationsTitle => 'Notifications';

  @override
  String get notificationsEmptyState => 'No notifications yet';

  @override
  String get notificationsAgoJustNow => 'Just now';

  @override
  String notificationsAgoMinutes(int n) {
    return '${n}m ago';
  }

  @override
  String notificationsAgoHours(int n) {
    return '${n}h ago';
  }

  @override
  String get notificationsAgoYesterday => 'Yesterday';

  @override
  String notificationsAgoDays(int n) {
    return '${n}d ago';
  }

  @override
  String get accountPageTitle => 'My Account';

  @override
  String get accountLegalSectionTitle => 'Legal';

  @override
  String get accountTermsRow => 'Terms & Conditions';

  @override
  String get accountPrivacyRow => 'Privacy Policy';

  @override
  String get accountSignOutRow => 'Sign out';

  @override
  String get accountSignOutConfirmTitle => 'Sign out?';

  @override
  String get accountSignOutConfirmBody =>
      'You\'ll need to sign in again to continue.';

  @override
  String get accountSignOutCancel => 'Cancel';

  @override
  String get accountSignOutConfirm => 'Sign out';

  @override
  String get accountNameFieldHint => 'Your name';

  @override
  String get accountSaveNameFailed => 'Could not save the name, try again.';

  @override
  String get accountShopSectionTitle => 'My shop';

  @override
  String get accountShopIdentityRow => 'My shop';

  @override
  String get shopIdentityPageTitle => 'My shop';

  @override
  String get shopIdentityVehicleTitle => 'Works on vehicles';

  @override
  String get shopIdentityVehicleDesc =>
      'Turns on the plate field on the visit-recording screen for this shop.';

  @override
  String get shopIdentityVehicleSaveFailed => 'Could not save, try again.';

  @override
  String get shopIdentityBrandTitle => 'Your shop\'s name and logo';

  @override
  String get shopIdentityCustomerPagePreview =>
      'This is what your customer sees';

  @override
  String get shopIdentityNameLabel => 'Shop name';

  @override
  String get shopIdentityUploadLogo => 'Upload logo';

  @override
  String get shopIdentityChangeLogo => 'Change logo';

  @override
  String get shopIdentityRemoveLogo => 'Remove';

  @override
  String get shopIdentityColorLabel => 'Your shop\'s colour';

  @override
  String get shopIdentityResetColor => 'Use default';

  @override
  String get shopIdentitySave => 'Save';

  @override
  String get shopIdentityDefaultName => 'Your shop';

  @override
  String get shopIdentityLogoPickFailed =>
      'Could not read the image, try another one.';

  @override
  String get shopIdentityInvalidColor => 'Enter a valid colour, like #B08A3E';

  @override
  String get shopIdentitySaveFailed => 'Could not save, try again.';

  @override
  String get shopIdentitySaved => 'Saved.';

  @override
  String get shopIdentityBranchesRow => 'Branches';

  @override
  String get branchesPageTitle => 'Branches';

  @override
  String get branchesAddBranch => 'Add branch';

  @override
  String get branchesActiveChip => 'Active';

  @override
  String get branchesClosedChip => 'Closed';

  @override
  String get branchesLoadFailed =>
      'Could not load branches, pull down to retry.';

  @override
  String get branchesLimitReached =>
      'Your current plan does not allow another branch.';

  @override
  String get branchesNameRequired => 'Branch name is required';

  @override
  String get branchesNameLabel => 'Branch name';

  @override
  String get branchesCityLabel => 'City';

  @override
  String get branchesLocationHint =>
      'Paste the location link from Google Maps (optional on the first branch, required from the second on)';

  @override
  String get branchesMapsLinkLabel => 'Google Maps link';

  @override
  String get branchesMapsLinkInvalid =>
      'Could not read that link — make sure it\'s a Google Maps link.';

  @override
  String get branchesMapsLinkShort =>
      'Paste the full Google Maps link, not the shortened one.';

  @override
  String get branchesLocationRequired =>
      'Set the branch\'s location on the map — required from the second branch on.';

  @override
  String get branchesSaveFailed => 'Could not save, try again.';

  @override
  String get branchesStatusLabel => 'Branch status';

  @override
  String get branchesMainCannotClose =>
      'The main branch cannot be closed — you can only rename it.';

  @override
  String get branchesWhatsappTitle => 'WhatsApp connection';

  @override
  String get branchesWhatsappNotStarted => 'Not connected yet';

  @override
  String get branchesWhatsappConnected => 'Connected and working';

  @override
  String get branchesWhatsappCannotSend => 'Connected but has a sending issue';

  @override
  String get branchesTeamTitle => 'Branch team';

  @override
  String get branchesTeamEmpty => 'No team members at this branch yet.';

  @override
  String get branchesAddMember => 'Add member';

  @override
  String get branchesMemberNameLabel => 'Employee\'s name';

  @override
  String get branchesMemberPhoneLabel => 'His phone number';

  @override
  String get branchesMemberPasswordLabel => 'His sign-in password';

  @override
  String get branchesMemberRoleLabel => 'Role';

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
      'Your current plan does not allow another employee.';

  @override
  String get branchesHireFailed => 'Could not add the employee, try again.';

  @override
  String get branchesVisibleAllHint => 'Sees every branch';

  @override
  String branchesVisibleSomeHint(int count) {
    return 'Sees $count branches';
  }

  @override
  String get branchesEditMember => 'Edit employee';

  @override
  String get branchesMemberStopped => 'Stopped';

  @override
  String get branchesMemberStationLabel => 'Which branch they work at';

  @override
  String get branchesMemberVisibilityLabel => 'Which branches they may see';

  @override
  String get branchesVisibilityOwnOnly => 'Their own branch only';

  @override
  String get branchesVisibilitySome => 'Specific branches';

  @override
  String get branchesVisibilityAll => 'Every branch';

  @override
  String get branchesWorkingHours => 'Working hours';

  @override
  String get branchesStopMember => 'Stop employee';

  @override
  String get branchesStopMemberTitle => 'Stop this employee?';

  @override
  String branchesStopMemberBody(String name) {
    return '$name loses access to the app immediately. Their visit history and records stay saved.';
  }

  @override
  String get branchesStopMemberConfirm => 'Stop';

  @override
  String get branchesReactivateMember => 'Reactivate';

  @override
  String get branchesRehireRequired =>
      'This employee is fully stopped — reactivating them needs hiring them again, not just a toggle.';

  @override
  String get branchesHoursSaved => 'Working hours saved.';

  @override
  String get branchesHoursExceedsShop =>
      'These hours are wider than the shop\'s own hours — adjust them.';

  @override
  String get branchesHoursHint =>
      'If you don\'t change anything, they follow the shop\'s own hours automatically.';

  @override
  String get branchesHoursClear => 'Reset to the shop\'s default hours';

  @override
  String get branchesDayMonday => 'Monday';

  @override
  String get branchesDayTuesday => 'Tuesday';

  @override
  String get branchesDayWednesday => 'Wednesday';

  @override
  String get branchesDayThursday => 'Thursday';

  @override
  String get branchesDayFriday => 'Friday';

  @override
  String get branchesDaySaturday => 'Saturday';

  @override
  String get branchesDaySunday => 'Sunday';

  @override
  String get branchesDayClosed => 'Closed';

  @override
  String get accountLanguageSectionTitle => 'Language';

  @override
  String get accountLanguageRow => 'App language';

  @override
  String get accountLanguageSheetTitle => 'Choose app language';

  @override
  String get accountSecuritySectionTitle => 'Security';

  @override
  String get accountChangePasswordRow => 'Change password';

  @override
  String get accountChangePasswordFailed =>
      'Could not change the password, try again.';

  @override
  String get accountChangePasswordSuccess => 'Password changed.';

  @override
  String get accountCurrentPasswordLabel => 'Current password';

  @override
  String get accountNewPasswordLabel => 'New password';

  @override
  String get accountConfirmNewPasswordLabel => 'Confirm new password';

  @override
  String get branchesIncreaseCapacity => 'Increase capacity';

  @override
  String get accountBillingSectionTitle => 'Billing';

  @override
  String get accountBillingRow => 'Subscription & invoices';

  @override
  String get billingPageTitle => 'Billing';

  @override
  String get billingLoadFailed =>
      'Couldn\'t load your billing data. Pull down to retry.';

  @override
  String get billingAllGood =>
      'Your billing is in good shape — nothing needs your attention right now.';

  @override
  String get billingPastDue =>
      'You have a past-due invoice — pay it to avoid your services being paused.';

  @override
  String get billingPaymentConfirming =>
      'We got your payment attempt and are confirming it now — this can take up to 20 minutes.';

  @override
  String get billingUsageSectionTitle => 'Your usage';

  @override
  String get billingUsageStaffSeats => 'Staff seats';

  @override
  String get billingUsageBranches => 'Branches';

  @override
  String get billingUsageUnlimited => 'Unlimited';

  @override
  String get billingMyAppsSectionTitle => 'My subscribed apps';

  @override
  String get billingStatusActive => 'Active';

  @override
  String get billingStatusStopping => 'Stopping';

  @override
  String billingRenewsOn(Object date) {
    return 'Renews on $date';
  }

  @override
  String get billingStopRenewal => 'Stop renewal';

  @override
  String get billingUndoStopRenewal => 'Undo stop';

  @override
  String get billingRenewNow => 'Renew now';

  @override
  String get billingActionFailed =>
      'Couldn\'t complete this action. Try again.';

  @override
  String get billingRenewalPreviewSectionTitle => 'Next renewal preview';

  @override
  String billingRenewalPreviewNextChargeOn(Object date) {
    return 'Next charge on $date';
  }

  @override
  String get billingRenewalPreviewNoDate => 'No upcoming renewal date yet.';

  @override
  String get billingRenewalPreviewSubtotal => 'Subtotal';

  @override
  String get billingRenewalPreviewSavings => 'Savings';

  @override
  String get billingRenewalPreviewTax => 'Tax';

  @override
  String get billingRenewalPreviewTotal => 'Total';

  @override
  String get billingInvoicesSectionTitle => 'Invoices';

  @override
  String get billingInvoicesEmpty => 'No invoices yet.';

  @override
  String get billingInvoiceStatusPaid => 'Paid';

  @override
  String get billingInvoiceStatusOpen => 'Unpaid';

  @override
  String get billingInvoiceStatusPartiallyPaid => 'Partially paid';

  @override
  String get billingInvoiceStatusVoid => 'Voided';

  @override
  String get billingInvoiceStatusUncollectible => 'Uncollectible';

  @override
  String get billingInvoiceStatusDraft => 'Draft';

  @override
  String get billingPayNow => 'Pay now';

  @override
  String get billingPayLinkFailed => 'Couldn\'t create a pay link. Try again.';

  @override
  String get paymentPageLoadFailed =>
      'Couldn\'t load the payment page. Check your connection and try again.';

  @override
  String get billingCancelConfirmTitle => 'Stop renewal?';

  @override
  String get billingCancelConfirmBody =>
      'The service keeps working until the end of the current period, then it won\'t renew.';

  @override
  String get billingCancelConfirmAction => 'Stop renewal';

  @override
  String get visitOfferApplyLabel => 'Apply this offer to this visit';

  @override
  String visitPointsRedeemCost(Object cost) {
    return '$cost points';
  }

  @override
  String get visitPointsOneBenefitOnly =>
      'One benefit per visit — choosing points drops the automatic offer.';

  @override
  String visitPointsRedeemedMessage(Object name) {
    return '$name redeemed ✓';
  }

  @override
  String visitPointsChosenMessage(Object name) {
    return 'Chosen: $name — will be used instead of the offer on save';
  }

  @override
  String get visitPointsRedeemFailed => 'Couldn\'t redeem it. Try again.';

  @override
  String readBillingActiveCount(Object count) {
    return 'You have $count active subscription(s).';
  }

  @override
  String get readBillingNone => 'You have no active subscriptions right now.';

  @override
  String readBillingRenewsSoon(Object date) {
    return 'The next renewal is on $date.';
  }

  @override
  String get readBillingFailed =>
      'Could not fetch billing status right now, try again.';

  @override
  String readBranchCount(Object count) {
    return 'You have $count branch(es).';
  }

  @override
  String get readBranchFailed =>
      'Could not fetch the branch count right now, try again.';

  @override
  String get readVehicleTrackingOn => 'Vehicle tracking is on right now.';

  @override
  String get readVehicleTrackingOff => 'Vehicle tracking is off right now.';

  @override
  String get readVehicleTrackingFailed =>
      'Could not check vehicle tracking status right now, try again.';

  @override
  String get writeVehicleTrackingEnabledConfirm =>
      'Turns on the plate-number field on this shop\'s visit-registration screen. Confirm?';

  @override
  String get writeVehicleTrackingDisabledConfirm =>
      'Turns off the plate-number field on this shop\'s visit-registration screen. Confirm?';

  @override
  String get writeVehicleTrackingEnabledDone => 'Vehicle tracking turned on ✓';

  @override
  String get writeVehicleTrackingDisabledDone =>
      'Vehicle tracking turned off ✓';

  @override
  String get writeVehicleTrackingFailed =>
      'Could not change the vehicle-tracking setting, try again.';

  @override
  String get mobileRequestsTitle => 'Mobile requests';

  @override
  String get mobileRequestsSubtitle =>
      'Requests for a service that comes to the customer, from intake to completion.';

  @override
  String get mobileRequestsKpiPending => 'Awaiting decision';

  @override
  String get mobileRequestsKpiNeedsDecision => 'Needs a decision';

  @override
  String get mobileRequestsKpiCompletedMonth => 'Completed this month';

  @override
  String get mobileRequestsBannerGo => 'View';

  @override
  String get mobileRequestsFilterAll => 'All';

  @override
  String get mobileRequestsFilterPending => 'Pending';

  @override
  String get mobileRequestsFilterAccepted => 'Accepted';

  @override
  String get mobileRequestsFilterNeedsDecision => 'Needs decision';

  @override
  String get mobileRequestsFilterCompleted => 'Completed';

  @override
  String get mobileRequestsFilterClosed => 'Closed';

  @override
  String get mobileRequestsSearchHint => 'Search by name or phone';

  @override
  String get mobileRequestsLoadFailedTitle => 'Couldn\'t load requests';

  @override
  String get mobileRequestsLoadFailedBody =>
      'Check your connection and try again.';

  @override
  String get mobileRequestsRetry => 'Retry';

  @override
  String get mobileRequestsEmptyTitle => 'No requests yet';

  @override
  String get mobileRequestsEmptyBody =>
      'Mobile-service requests from your customers show up here.';

  @override
  String get mobileRequestsStatusPending => 'Pending';

  @override
  String get mobileRequestsStatusAccepted => 'Accepted';

  @override
  String get mobileRequestsStatusNeedsDecision => 'Needs decision';

  @override
  String get mobileRequestsStatusCompleted => 'Completed';

  @override
  String get mobileRequestsStatusNoShow => 'No-show';

  @override
  String get mobileRequestsStatusRejected => 'Rejected';

  @override
  String get mobileRequestsUnnamed => 'Unnamed';

  @override
  String get mobileRequestsOpenMap => 'Location';

  @override
  String get mobileRequestsPhoneCopied => 'Phone number copied';

  @override
  String get mobileRequestsRiskyCustomer => 'High no-show risk customer';

  @override
  String mobileRequestsRejectReasonLine(Object reason) {
    return 'Rejection reason: $reason';
  }

  @override
  String get mobileRequestsActionAccept => 'Accept';

  @override
  String get mobileRequestsActionReject => 'Reject';

  @override
  String get mobileRequestsActionComplete => 'Complete';

  @override
  String get mobileRequestsActionNoShow => 'No-show';

  @override
  String get mobileRequestsAssignUnassigned => 'Unassigned';

  @override
  String get mobileRequestsActionFailed =>
      'Couldn\'t complete the action, try again.';

  @override
  String get mobileRequestsRejectTitle => 'Reason for rejection';

  @override
  String get mobileRequestsRejectHint => 'Optional';

  @override
  String get mobileRequestsRejectCancel => 'Cancel';

  @override
  String get mobileRequestsRejectConfirm => 'Reject request';

  @override
  String get mobileRequestsAddOpen => 'Add request';

  @override
  String get mobileRequestsAddTitle => 'Add a mobile-service request';

  @override
  String get mobileRequestsAddPhoneLabel => 'Customer\'s phone';

  @override
  String get mobileRequestsAddNameLabel => 'Customer\'s name (optional)';

  @override
  String get mobileRequestsAddServicesLabel => 'Services';

  @override
  String get mobileRequestsAddServicesEmpty => 'No services available yet.';

  @override
  String get mobileRequestsAddDayLabel => 'Day';

  @override
  String get mobileRequestsAddTimeLabel => 'Time';

  @override
  String get mobileRequestsAddMapsLinkLabel => 'Google Maps location link';

  @override
  String get mobileRequestsAddMapsLinkHint =>
      'Accepts a full or shortened Google Maps link.';

  @override
  String get mobileRequestsAddMapsLinkShort =>
      'This is a shortened link — paste the full Google Maps link.';

  @override
  String get mobileRequestsAddMapsLinkInvalid =>
      'Couldn\'t read a location from this link.';

  @override
  String get mobileRequestsAddAssignLabel => 'Assign to (optional)';

  @override
  String get mobileRequestsAddCancel => 'Cancel';

  @override
  String get mobileRequestsAddSubmit => 'Add request';

  @override
  String get mobileRequestsAddSubmitting => 'Adding...';

  @override
  String get mobileRequestsAddError => 'Couldn\'t add the request, try again.';

  @override
  String mobileRequestsBannerText(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count requests need your decision now',
      one: '1 request needs your decision now',
    );
    return '$_temp0';
  }

  @override
  String get mobileRequestsAddMapsLinkResolving =>
      'Reading the location from the link...';

  @override
  String get customersTitle => 'Contacts';

  @override
  String get customersAddOpen => 'Add customer';

  @override
  String get customersSearchHint => 'Search by name or phone';

  @override
  String get customersTabAll => 'All';

  @override
  String get customersTabOverdue => 'Overdue';

  @override
  String get customersSearchFailedTitle => 'Search unavailable right now';

  @override
  String get customersSearchFailedBody => 'Try again shortly.';

  @override
  String get customersSearchEmpty => 'No results';

  @override
  String get customersLoadFailedTitle => 'Couldn\'t load';

  @override
  String get customersEmptyTitle => 'No customers yet';

  @override
  String get customersOverdueEmpty => 'No one is overdue right now';

  @override
  String get customersUnnamed => 'Unnamed';

  @override
  String customersVisitCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count visits',
      one: '1 visit',
    );
    return '$_temp0';
  }

  @override
  String get customersOverdueBadge => 'Overdue';

  @override
  String customersStatEveryDays(int days) {
    String _temp0 = intl.Intl.pluralLogic(
      days,
      locale: localeName,
      other: 'every $days days',
      one: 'every day',
    );
    return '$_temp0';
  }

  @override
  String customersOverdueBanner(int every, int since) {
    return 'Overdue for their usual visit — usually every $every days, $since days since their last visit';
  }

  @override
  String customersVisitMeter(int n) {
    return 'Odometer: $n';
  }

  @override
  String get customersOfferExpiredBadge => 'Expired';

  @override
  String get customersDeniedAllTitle =>
      'You don\'t have permission to view the customer list';

  @override
  String get customersDeniedOverdueTitle =>
      'You don\'t have permission to view who\'s overdue';

  @override
  String get customersDeniedDesc =>
      'Ask the shop owner to grant you this permission.';

  @override
  String get customersAddTitle => 'Add a new customer';

  @override
  String get customersAddPhoneLabel => 'Customer\'s phone';

  @override
  String get customersAddNameLabel => 'Customer\'s name';

  @override
  String get customersAddPhoneInvalid => 'Invalid phone number.';

  @override
  String get customersAddFailed => 'Couldn\'t add the customer, try again.';

  @override
  String get customersAddSubmitting => 'Adding...';

  @override
  String get customersAddSubmit => 'Add';

  @override
  String get customersActionFailed =>
      'Couldn\'t complete the action, try again.';

  @override
  String get customersRepeatedIssuesTitle => 'Repeated issues';

  @override
  String get customersVehiclesTitle => 'Vehicles';

  @override
  String get customersLoyaltyTitle => 'Loyalty';

  @override
  String get customersLoyaltyLoading => 'Loading...';

  @override
  String customersLoyaltyPoints(int count) {
    return '$count points';
  }

  @override
  String get customersLoyaltyAdjust => 'Adjust';

  @override
  String get customersOffersTitle => 'Live offers';

  @override
  String customersOfferExpires(String date) {
    return 'Expires $date';
  }

  @override
  String get customersVisitsTitle => 'Visit history';

  @override
  String get customersVisitsEmpty => 'No visits yet';

  @override
  String get customersVisitNoServices => 'No services recorded';

  @override
  String get customersRenameTitle => 'Edit customer\'s name';

  @override
  String get customersRenameSubmit => 'Save';

  @override
  String get customersLoyaltyAdjustTitle => 'Adjust loyalty points';

  @override
  String get customersLoyaltyAdjustNoteLabel => 'Reason for the adjustment';

  @override
  String get customersLoyaltyAdjustNoteRequired =>
      'Write a real reason (at least 3 characters), and pick a nonzero amount.';

  @override
  String get customersLoyaltyAdjustSubmit => 'Save adjustment';

  @override
  String get customersEraseButton => 'Erase this customer\'s data';

  @override
  String get customersEraseTitle => 'Erase customer data';

  @override
  String get customersEraseWarning =>
      'This permanently erases all of the customer\'s data from the platform — it cannot be undone.';

  @override
  String customersEraseTypeNameLabel(String name) {
    return 'To confirm, type the customer\'s name: $name';
  }

  @override
  String get customersEraseConfirm => 'Erase permanently';

  @override
  String get customersBookingsTitle => 'Bookings';

  @override
  String customersAttendanceRate(int rate) {
    return '$rate% attendance';
  }

  @override
  String get customersBookingsNoneUpcoming => 'No upcoming bookings';

  @override
  String get customersCyclesTitle => 'Reminder cycles';

  @override
  String customersCyclesEveryDays(int days) {
    return 'Every $days days';
  }

  @override
  String get customersCyclesEditHint =>
      'Set the interval, and automatic learning stops for this service with this customer.';

  @override
  String get customersCyclesSave => 'Save';

  @override
  String get customersLogTitle => 'Messages log';

  @override
  String get customersLogEmpty => 'We haven\'t sent them anything yet';

  @override
  String get customersLogOutcomeSent => 'Sent';

  @override
  String get customersLogOutcomeSuppressed => 'Not sent';

  @override
  String get customersTemplateVisitConfirmation => 'Visit confirmation';

  @override
  String get customersTemplateVisitConfirmationRating =>
      'Post-visit rating request';

  @override
  String get customersTemplateBookingConfirmation => 'Booking confirmation';

  @override
  String get customersTemplateVisitRedeemed => 'Reward redemption notice';

  @override
  String get customersTemplateServiceReminder => 'Service reminder';

  @override
  String get customersTemplateFollowUp => 'Post-visit follow-up';

  @override
  String get customersTemplateAccountNotice => 'Account notice';

  @override
  String get customersTemplatePointsExpiring => 'Points-expiring alert';

  @override
  String get customersTemplateLoyaltyActivation =>
      'Loyalty programme activation';

  @override
  String get customersTemplateWinback => 'Lapsed-customer win-back';

  @override
  String get customersTemplatePersonalOccasion => 'Occasion greeting';

  @override
  String customersShowAll(int count) {
    return 'Show all ($count)';
  }

  @override
  String get customersCyclesUnknownService => 'Unknown service';

  @override
  String customersVisitGapDays(int days) {
    String _temp0 = intl.Intl.pluralLogic(
      days,
      locale: localeName,
      other: 'after $days days',
      one: 'after 1 day',
      zero: 'same day',
    );
    return '$_temp0';
  }

  @override
  String customersCountLabel(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count customers',
      one: '1 customer',
      zero: 'no customers yet',
    );
    return '$_temp0';
  }

  @override
  String get ratingTitle => 'Ratings';

  @override
  String get pointsTitle => 'Loyalty Points';

  @override
  String get pointsAddReward => 'New reward';

  @override
  String get pointsEditReward => 'Edit reward';

  @override
  String get pointsTabRewards => 'Rewards';

  @override
  String get pointsTabLeaderboard => 'Most redeemed';

  @override
  String get pointsOutstandingHint =>
      'points the shop still owes its customers';

  @override
  String pointsRedemptionsCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count redemptions',
      one: '1 redemption',
    );
    return '$_temp0';
  }

  @override
  String pointsCustomersCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count customers redeemed',
      one: '1 customer redeemed',
    );
    return '$_temp0';
  }

  @override
  String pointsExpiredWarning(int percent) {
    return '$percent% of granted points expired unredeemed — review your reward pricing';
  }

  @override
  String get pointsLoadFailedTitle => 'Could not load rewards';

  @override
  String get pointsRewardsEmpty =>
      'No rewards yet — add your customers\' first reward';

  @override
  String get pointsLeaderboardEmpty =>
      'No redemptions yet — they\'ll show here once a customer redeems one';

  @override
  String get pointsLeaderboardTitle => 'Most redeemed';

  @override
  String get pointsLeaderboardHint =>
      'The top five rewards your customers redeemed';

  @override
  String pointsTimesRedeemed(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count times',
      one: 'once',
    );
    return '$_temp0';
  }

  @override
  String get pointsRewardRetired => 'Retired';

  @override
  String pointsRewardServiceHint(String name) {
    return 'Service: $name';
  }

  @override
  String pointsRewardDiscountHint(String amount) {
    return '$amount SAR off';
  }

  @override
  String get pointsRewardItemHint => 'A gift, not tied to the catalogue';

  @override
  String get pointsRewardNameLabel => 'Reward name';

  @override
  String get pointsRewardTypeLabel => 'Reward type';

  @override
  String get pointsTypeService => 'A service from your catalogue';

  @override
  String get pointsTypeItem => 'A gift';

  @override
  String get pointsTypeDiscount => 'A cash discount';

  @override
  String get pointsRewardServiceLabel => 'Which service';

  @override
  String get pointsRewardDiscountLabel => 'Discount amount, SAR';

  @override
  String get pointsRewardCostLabel => 'Cost in points';

  @override
  String get pointsRewardActiveLabel => 'Active — customers may redeem it';

  @override
  String get pointsRewardInvalid =>
      'Enter a name and a real point cost above zero';

  @override
  String get pointsSaveFailed => 'Could not save, try again';

  @override
  String get pointsModeTitle => 'Earning method';

  @override
  String get pointsModeHint =>
      'By service: each service has its own points. By invoice value: one point per riyal.';

  @override
  String get pointsModeServices => 'By service';

  @override
  String get pointsModeInvoice => 'By invoice value';

  @override
  String get pointsModeNeedsPricedServices =>
      'Earning by invoice value needs every service priced first — price them all in Services, then turn it on.';

  @override
  String get pointsOpenEarnSettings => 'Per-service points settings';

  @override
  String get ratingLeaderboardTitle => 'Top-rated staff';

  @override
  String get ratingCardNoName => 'Unnamed';

  @override
  String get ratingMetricVisits => 'Most visits';

  @override
  String get ratingMetricRatings => 'Most ratings';

  @override
  String get ratingMetricAvg => 'Top-rated';

  @override
  String ratingStaffCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count staff members',
      one: '1 staff member',
    );
    return '$_temp0';
  }

  @override
  String get ratingTableTitle => 'Every staff member';

  @override
  String ratingTableVisitsValue(int n) {
    return '$n visits';
  }

  @override
  String ratingTableRatingsValue(int n) {
    return '$n ratings';
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
  String get ratingPeriodWeek => 'Week';

  @override
  String get ratingPeriodMonth => 'Month';

  @override
  String get ratingPeriodQuarter => 'Quarter';

  @override
  String get ratingPeriodCustom => 'Custom';

  @override
  String ratingCustomSince(String date) {
    return 'From: $date';
  }

  @override
  String ratingCustomUntil(String date) {
    return 'To: $date';
  }

  @override
  String get ratingCustomRangeInvalid =>
      'Invalid range — make sure the start date is before the end date';

  @override
  String get ratingExportLocaleLabel => 'Report language';

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
  String get ratingTopIssuesTitle => 'Most repeated issues';

  @override
  String get ratingFilterUnhandled => 'Pending';

  @override
  String get ratingFilterAll => 'All';

  @override
  String get ratingFilterHandled => 'Handled';

  @override
  String get ratingStarsAll => 'All stars';

  @override
  String get ratingLoadFailedTitle => 'Couldn\'t load ratings';

  @override
  String get ratingEmptyTitle => 'No ratings yet';

  @override
  String get ratingLoadMore => 'Show more';

  @override
  String get ratingHandledPlain => 'Handled';

  @override
  String get ratingMarkHandled => 'Mark as handled';

  @override
  String get ratingMarkHandledHint =>
      'This is recorded permanently — it cannot be undone later.';

  @override
  String get ratingHandledNoteLabel => 'Note (optional)';

  @override
  String get ratingMarkHandledConfirm => 'Confirm';

  @override
  String get ratingActionFailed => 'Couldn\'t complete the action, try again.';

  @override
  String ratingWeightedAvgHint(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'from $count ratings over the last 30 days',
      one: 'from 1 rating over the last 30 days',
      zero: 'no ratings in the last 30 days',
    );
    return '$_temp0';
  }

  @override
  String ratingUnhandledCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count ratings pending',
      one: '1 rating pending',
    );
    return '$_temp0';
  }

  @override
  String ratingVisitsShort(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count visits',
      one: '1 visit',
    );
    return '$_temp0';
  }

  @override
  String ratingIssueFilterLabel(String label) {
    return 'Issue: $label';
  }

  @override
  String ratingByOperator(String name) {
    return 'Served by $name';
  }

  @override
  String ratingHandledWithNote(String note) {
    return 'Handled: $note';
  }

  @override
  String get ratingQuadrantTitle => 'Performance quadrant';

  @override
  String get ratingQuadrantHint =>
      'Quality against engagement rate — tap any point for that operator\'s training record.';

  @override
  String get ratingQuadrantStars => 'Stars';

  @override
  String get ratingQuadrantUnderused => 'Underused';

  @override
  String get ratingQuadrantNeedsCoaching => 'Needs coaching';

  @override
  String get ratingQuadrantAtRisk => 'At risk';

  @override
  String get ratingTrainingTitle => 'Training record';

  @override
  String get ratingTrainingNoAccess =>
      'You don\'t have permission to view this.';

  @override
  String get ratingTrainingClean => 'Clean record — no repeated issues.';

  @override
  String ratingEngagementPercent(int percent) {
    return '$percent% engagement';
  }

  @override
  String get ratingTabOverview => 'Overview';

  @override
  String get ratingTabFeed => 'All ratings';

  @override
  String get ratingOverviewEmpty =>
      'No performance data yet for the last 30 days.';

  @override
  String get ratingExportTitle => 'Export report';

  @override
  String get ratingExportHint =>
      'The team\'s performance report for the selected period, ready to share.';

  @override
  String get ratingExportFailed => 'Couldn\'t export the report, try again.';

  @override
  String get customersPrivacyRequestsTitle => 'Privacy requests';

  @override
  String get customersPrivacyRequestErase => 'Data erasure request';

  @override
  String get customersPrivacyRequestCopy => 'Data copy request';

  @override
  String customersPrivacyRequestGeneric(String type) {
    return 'Request: $type';
  }

  @override
  String get customersPrivacyRequestClose => 'Close';

  @override
  String get customersLoyaltyHistoryTitle => 'Points history';

  @override
  String get customersLoyaltyHistoryNoReason => 'No reason given';

  @override
  String get customersLoyaltyReasonRedeem => 'Reward redeemed';

  @override
  String get customersLoyaltyReasonAdjust => 'Manual adjustment';

  @override
  String get customersLoyaltyReasonEarn => 'Points from a visit';

  @override
  String get customersLoyaltyReasonExpire => 'Expired';

  @override
  String get readCustomersFailed =>
      'Could not fetch customer data right now, try again.';

  @override
  String readCustomersTotal(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'You have $count registered customers.',
      one: 'You have 1 registered customer.',
      zero: 'You have no customers registered yet.',
    );
    return '$_temp0';
  }

  @override
  String readCustomersOverdueCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'You have $count customers overdue on their cycle.',
      one: 'You have 1 customer overdue on their cycle.',
      zero: 'No customer is overdue on their cycle right now.',
    );
    return '$_temp0';
  }

  @override
  String get readMobileRequestsFailed =>
      'Could not fetch mobile requests right now, try again.';

  @override
  String readMobileRequestsPendingCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'You have $count requests awaiting a decision.',
      one: 'You have 1 request awaiting a decision.',
      zero: 'No mobile requests are awaiting a decision.',
    );
    return '$_temp0';
  }

  @override
  String readMobileRequestsNeedsDecisionCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count requests need your decision now.',
      one: '1 request needs your decision now.',
      zero: 'No mobile requests need your decision right now.',
    );
    return '$_temp0';
  }

  @override
  String get readRatingFailed =>
      'Could not fetch rating data right now, try again.';

  @override
  String get readRatingNone => 'You have no ratings in the last 30 days yet.';

  @override
  String readRatingAverage(String avg, int count) {
    return 'Your average rating over the last 30 days is $avg out of 5, from $count ratings.';
  }

  @override
  String readRatingUnhandledCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'You have $count ratings pending.',
      one: 'You have 1 rating pending.',
      zero: 'No ratings are pending.',
    );
    return '$_temp0';
  }

  @override
  String readRatingTopStaff(String name, String avg) {
    return 'Your top-rated staff over the last 30 days is $name, averaging $avg out of 5.';
  }

  @override
  String readMobileRequestsCompletedCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'You\'ve completed $count this month.',
      one: 'You\'ve completed 1 this month.',
      zero: 'You haven\'t completed any mobile requests this month yet.',
    );
    return '$_temp0';
  }

  @override
  String readMobileRequestsTodayCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count requests have come in today.',
      one: '1 request has come in today.',
      zero: 'No mobile requests have come in today yet.',
    );
    return '$_temp0';
  }

  @override
  String get readOperatorsFailed =>
      'Could not fetch the staff count right now, try again.';

  @override
  String readOperatorsCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'You have $count staff members.',
      one: 'You have 1 staff member.',
      zero: 'You have no staff registered yet.',
    );
    return '$_temp0';
  }

  @override
  String readBranchesDisconnectedCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'You have $count branches with WhatsApp not working.',
      one: 'You have 1 branch with WhatsApp not working.',
      zero: 'All your active branches have WhatsApp connected and working.',
    );
    return '$_temp0';
  }

  @override
  String get readCustomersRecentNone =>
      'You don\'t have any customers registered yet.';

  @override
  String readCustomersRecentName(String name) {
    return 'Your most recent customer is $name.';
  }

  @override
  String readRatingCriticalIssuesCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'You have $count pending ratings with critical issues.',
      one: 'You have 1 pending rating with a critical issue.',
      zero: 'No pending ratings carry a critical issue.',
    );
    return '$_temp0';
  }

  @override
  String get readPerBranchModeOn => 'Yes, your shop runs in multi-branch mode.';

  @override
  String get readPerBranchModeOff => 'No, your shop runs as a single branch.';

  @override
  String get readBillingOverdueYes =>
      'Yes, you have an overdue invoice — pay it to avoid your services being paused.';

  @override
  String get readBillingOverdueNo =>
      'No, your billing is in good standing, no overdue invoices.';

  @override
  String get readServicesFailed =>
      'Could not fetch the services count right now, try again.';

  @override
  String readServicesCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'You have $count services in your list.',
      one: 'You have 1 service in your list.',
      zero: 'You have no services in your list yet.',
    );
    return '$_temp0';
  }

  @override
  String readCustomersTodayCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count new customers have come in today.',
      one: '1 new customer has come in today.',
      zero: 'No new customer has come in today yet.',
    );
    return '$_temp0';
  }

  @override
  String readMobileRequestsRejectedCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'You\'ve rejected $count this month.',
      one: 'You\'ve rejected 1 this month.',
      zero: 'You haven\'t rejected any mobile requests this month.',
    );
    return '$_temp0';
  }

  @override
  String readMobileRequestsNoShowCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count customers have been no-shows this month.',
      one: '1 customer has been a no-show this month.',
      zero: 'No customer has been a no-show this month.',
    );
    return '$_temp0';
  }

  @override
  String readRatingFiveStarCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'You have $count five-star ratings.',
      one: 'You have 1 five-star rating.',
      zero: 'You have no five-star ratings yet.',
    );
    return '$_temp0';
  }

  @override
  String readBranchesActiveCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'You have $count active branches.',
      one: 'You have 1 active branch.',
      zero: 'You have no active branches right now.',
    );
    return '$_temp0';
  }

  @override
  String get servicesTitle => 'My services';

  @override
  String get servicesUnnamedGlyph => '?';

  @override
  String get servicesSearchHint => 'Search by service name';

  @override
  String get servicesTabActive => 'Active';

  @override
  String get servicesTabStopped => 'Stopped';

  @override
  String get servicesLoadFailedTitle => 'Couldn\'t load services';

  @override
  String get servicesEmptyActive => 'No active services yet';

  @override
  String get servicesEmptyStopped => 'No stopped services';

  @override
  String get servicesAddOpen => 'Add service';

  @override
  String get servicesNoPrice => 'No price set';

  @override
  String get servicesNoDuration => 'Not set';

  @override
  String get servicesNoCycle => 'No cycle';

  @override
  String get servicesStopTitle => 'Stop this service';

  @override
  String get servicesStopConfirm => 'Stop';

  @override
  String get servicesActionFailed =>
      'Couldn\'t complete the action, try again.';

  @override
  String get servicesEditTitle => 'Edit service';

  @override
  String get servicesAddTitle => 'Add a new service';

  @override
  String get servicesNameLabel => 'Service name';

  @override
  String get servicesPriceLabel => 'Price (optional)';

  @override
  String get servicesDurationLabel => 'Duration in minutes (optional)';

  @override
  String get servicesCycleLabel => 'Reminder cycle in days (optional)';

  @override
  String get servicesDescriptionLabel => 'Short description (optional)';

  @override
  String get servicesSaving => 'Saving...';

  @override
  String get servicesSave => 'Save';

  @override
  String get servicesNameRequired => 'Service name is required';

  @override
  String servicesActiveCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'You have $count active services.',
      one: 'You have 1 active service.',
      zero: 'You have no active services yet.',
    );
    return '$_temp0';
  }

  @override
  String servicesDurationMinutes(int count) {
    return '$count min';
  }

  @override
  String servicesCycleDays(int count) {
    return 'Every $count days';
  }

  @override
  String servicesStopWarning(String name) {
    return 'This stops \"$name\" — it won\'t show for a new visit and its reminders stop. Its data is never deleted.';
  }

  @override
  String get servicesPhotoPickFailed => 'Couldn\'t pick the photo';

  @override
  String get servicesPhotoUploadFailed => 'Saved, but the photo upload failed';

  @override
  String get servicesPhotoLabel => 'Service photo (optional)';

  @override
  String get servicesUploadPhoto => 'Upload photo';

  @override
  String get servicesChangePhoto => 'Change photo';

  @override
  String get servicesRemovePhoto => 'Remove';

  @override
  String get servicesAssignmentLabel => 'Who provides this service?';

  @override
  String get servicesAssignmentAuto => 'Any available staff';

  @override
  String get servicesAssignmentNamed => 'Specific staff';

  @override
  String get servicesChecklistLabel => 'Procedure checklist';

  @override
  String get servicesChecklistEmpty => 'No steps yet — add the first one';

  @override
  String get servicesStepAddTitle => 'Add a step';

  @override
  String get servicesGeneralSettingsTitle => 'General default';

  @override
  String get servicesGeneralSettingsHint =>
      'The value every service that hasn\'t been customised follows';

  @override
  String get servicesFollowUpLabel => 'Follow-up days after the visit';

  @override
  String get servicesPointsLabel => 'Points per visit';

  @override
  String get servicesGroupThem => 'Group them';

  @override
  String get servicesGroupNameHint => 'Group name';

  @override
  String get servicesAllGroups => 'All';

  @override
  String get servicesStepEditTitle => 'Edit the step';

  @override
  String get servicesStepCriticalLabel => 'Critical step';

  @override
  String get servicesStepRetire => 'Retire this step';

  @override
  String get servicesStepEditHint => 'Long-press any step to edit or retire it';

  @override
  String get servicesAdvancedTitle => 'Advanced settings';

  @override
  String get servicesAdvancedHint =>
      'Customise this service away from the general default — cycle, points, and grouping';

  @override
  String get servicesGroupLabel => 'Group';

  @override
  String get servicesNoGroup => 'No group';

  @override
  String get servicesNewGroup => 'New group';

  @override
  String get servicesFollowGeneralAction => 'Follow general';

  @override
  String get servicesCustomizeAction => 'Customise';

  @override
  String servicesFollowUpDays(int n) {
    return 'Follow up after $n days';
  }

  @override
  String servicesPointsPerVisit(int n) {
    return '$n points';
  }

  @override
  String servicesSuggestionText(int n) {
    return '$n services share the same value — grouping them makes editing them together easier later.';
  }

  @override
  String servicesFollowsGeneral(String hint) {
    return 'Follows general — $hint';
  }

  @override
  String get servicesPageTabServices => 'Services';

  @override
  String get servicesPageTabPackages => 'Packages';

  @override
  String get servicesPackageAdd => 'Add package';

  @override
  String get servicesPackageNeedsTwoServices =>
      'A package needs at least two active services';

  @override
  String get servicesPackageEmpty => 'No packages yet';

  @override
  String get servicesPackageEditTitle => 'Edit package';

  @override
  String get servicesPackageAddTitle => 'Add a new package';

  @override
  String get servicesPackageNameLabel => 'Package name';

  @override
  String get servicesPackagePriceRequired =>
      'Package price is required, above zero';

  @override
  String get servicesPackageServicesLabel => 'Included services';

  @override
  String get servicesImportTitle => 'Import services from a file';

  @override
  String get servicesImportHint =>
      'A CSV file with columns: name, price, duration_minutes, cycle_days, description';

  @override
  String get servicesImportPickFile => 'Choose a CSV file';

  @override
  String get servicesImportReadFailed => 'Couldn\'t read the file';

  @override
  String get servicesImportParseFailed =>
      'The file has no name column, or its format is invalid';

  @override
  String get servicesImportDeactivateMissing =>
      'Stop services missing from the file';

  @override
  String get servicesImportDeactivateMissingHint =>
      'Any service you currently have that isn\'t in this file gets stopped automatically';

  @override
  String get servicesImportConfirm => 'Import';

  @override
  String get servicesImportClose => 'Done';

  @override
  String servicesImportRowCount(int n) {
    String _temp0 = intl.Intl.pluralLogic(
      n,
      locale: localeName,
      other: '$n rows',
      one: '1 row',
      zero: 'No rows',
    );
    return '$_temp0 ready to import';
  }

  @override
  String servicesImportDone(int created, int updated, int reactivated) {
    return 'Added $created, updated $updated, reactivated $reactivated.';
  }

  @override
  String get visitPackagesSectionTitle => 'Featured packages';

  @override
  String get visitNameFieldHint => 'Customer name (optional)';

  @override
  String get visitMeterFieldHint => 'Odometer reading';

  @override
  String get visitQuantityDialogTitle => 'Quantity';

  @override
  String get visitCouponCheckboxLabel =>
      'Grant a discount coupon to another shop';

  @override
  String get visitCouponPhoneHint => 'Shop owner\'s phone';

  @override
  String get visitClearAllButton => 'Clear all';

  @override
  String visitServicesSelectedCount(int n) {
    String _temp0 = intl.Intl.pluralLogic(
      n,
      locale: localeName,
      other: '$n services selected',
      one: '1 service selected',
    );
    return '$_temp0';
  }

  @override
  String get visitTodayBookingsTitle => 'Today\'s appointments';

  @override
  String get visitBookingAttendFailed =>
      'Couldn\'t confirm attendance, try again';

  @override
  String get branchSwitcherChooseBranch => 'Choose branch';

  @override
  String get branchSwitcherTitle => 'Current branch';

  @override
  String get branchSwitcherHint =>
      'Everything you open after this belongs to this branch';

  @override
  String get proceduresPrintFailed => 'Couldn\'t generate the document';

  @override
  String get proceduresTitle => 'Procedures';

  @override
  String get proceduresSubtitle =>
      'Set the procedure checklist for each service, or manage the whole shared library. Long-press a service to select it for printing';

  @override
  String get proceduresLibraryLink => 'Procedure library';

  @override
  String get proceduresPrint => 'Print';

  @override
  String get proceduresEmptyTitle => 'No active services yet';

  @override
  String get servicesStepSeverityNormal => 'Normal';

  @override
  String get servicesStepSeverityCritical => 'Critical';

  @override
  String get proceduresSaveFailed => 'Couldn\'t save';

  @override
  String get proceduresDrawerSubtitle =>
      'Drag to reorder, or add a step from the library';

  @override
  String get proceduresDrawerEmpty => 'No steps for this service yet';

  @override
  String get proceduresDrawerAddButton => 'Add from library';

  @override
  String get proceduresPickTitle => 'Pick a step';

  @override
  String get proceduresPickClose => 'Close';

  @override
  String get proceduresPickApply => 'Add';

  @override
  String get proceduresPickSearch => 'Search steps';

  @override
  String get proceduresPickEmpty => 'No results';

  @override
  String get proceduresPickCreatePlaceholder => 'New step...';

  @override
  String get proceduresLibrarySaveFailed => 'Couldn\'t save';

  @override
  String get proceduresLibraryTitle => 'Procedure library';

  @override
  String get proceduresLibrarySubtitle =>
      'Every step here is shared across every service that uses it - editing it changes it everywhere';

  @override
  String get proceduresLibraryNewPlaceholder => 'New step text';

  @override
  String get proceduresLibraryAdd => 'Add';

  @override
  String get proceduresLibraryShowRetired => 'Show retired';

  @override
  String get proceduresLibraryEmpty => 'No steps yet';

  @override
  String get proceduresLibraryRetired => 'Retired';

  @override
  String get proceduresLibraryRetire => 'Retire';

  @override
  String get proceduresLibraryReactivate => 'Reactivate';

  @override
  String get proceduresSeverityHint =>
      'A critical step is highlighted for staff and can\'t be skipped while performing the service';

  @override
  String proceduresSelectedCount(int n) {
    return '$n selected';
  }

  @override
  String proceduresStepCount(int n) {
    return '$n steps';
  }

  @override
  String proceduresUsedIn(int n) {
    return 'Used in $n services';
  }

  @override
  String get mutualBenefitProposeButton => 'Propose partnership';

  @override
  String get mutualBenefitTitle => 'Mutual Benefit';

  @override
  String get mutualBenefitSubtitle =>
      'Move real customers between you and other shops, by mutual agreement';

  @override
  String get mutualBenefitRoleAll => 'All';

  @override
  String get mutualBenefitRoleReferrer => 'As referrer';

  @override
  String get mutualBenefitRoleBeneficiary => 'As beneficiary';

  @override
  String get mutualBenefitLoadFailed => 'Couldn\'t load partnerships';

  @override
  String get mutualBenefitEmptyTitle => 'No partnerships yet';

  @override
  String get mutualBenefitKpiAsReferrer => 'As referrer';

  @override
  String get mutualBenefitKpiAsBeneficiary => 'As beneficiary';

  @override
  String get mutualBenefitKpiSent => 'Referred';

  @override
  String get mutualBenefitKpiRedeemed => 'Redeemed';

  @override
  String get mutualBenefitKpiRate => 'Redemption rate';

  @override
  String get mutualBenefitConfirm => 'Confirm';

  @override
  String get mutualBenefitGrantDiscountBlanket => 'Discount on the whole visit';

  @override
  String get mutualBenefitStatusProposed => 'Proposed';

  @override
  String get mutualBenefitStatusActive => 'Active';

  @override
  String get mutualBenefitStatusPaused => 'Paused';

  @override
  String get mutualBenefitStatusCancelRequested => 'Cancellation requested';

  @override
  String get mutualBenefitStatusEnded => 'Ended';

  @override
  String get mutualBenefitStatusRejected => 'Rejected';

  @override
  String get mutualBenefitStatusExpiredUnanswered => 'Expired unanswered';

  @override
  String get mutualBenefitEventProposed => 'Partnership proposed';

  @override
  String get mutualBenefitEventAccepted => 'Partnership accepted';

  @override
  String get mutualBenefitEventRejected => 'Partnership rejected';

  @override
  String get mutualBenefitEventActivated => 'Partnership activated';

  @override
  String get mutualBenefitEventCancelRequested => 'Cancellation requested';

  @override
  String get mutualBenefitEventCancelConfirmed => 'Cancellation confirmed';

  @override
  String get mutualBenefitEventExpiredUnanswered => 'Expired with no answer';

  @override
  String get mutualBenefitEventPaused => 'Paused';

  @override
  String get mutualBenefitEventResumed => 'Resumed';

  @override
  String get mutualBenefitEventEndedTerm => 'Term ended';

  @override
  String get mutualBenefitEventGrantCreated => 'New grant';

  @override
  String get mutualBenefitEventGrantRedeemed => 'Grant redeemed';

  @override
  String get mutualBenefitActivityActive => 'Active';

  @override
  String get mutualBenefitActivityPaused => 'Paused';

  @override
  String get mutualBenefitActivityPending => 'Awaiting reply';

  @override
  String get mutualBenefitActivityInactive => 'Inactive';

  @override
  String get mutualBenefitScorecardTitle => 'Performance';

  @override
  String get mutualBenefitScorecardFailed => 'Couldn\'t load performance';

  @override
  String get mutualBenefitActivityTitle => 'Recent activity';

  @override
  String get mutualBenefitActivityEmpty => 'No activity yet';

  @override
  String get mutualBenefitAgreementsTitle => 'Agreements';

  @override
  String get mutualBenefitConfirmCancel => 'End this partnership for good?';

  @override
  String get mutualBenefitActionAccept => 'Accept';

  @override
  String get mutualBenefitActionReject => 'Reject';

  @override
  String get mutualBenefitActionWaitingThem => 'Waiting on the other side';

  @override
  String get mutualBenefitActionCancelRequest => 'Request to end';

  @override
  String get mutualBenefitActionCancelConfirm => 'Confirm ending';

  @override
  String get mutualBenefitProposeTitle => 'Propose a new partnership';

  @override
  String get mutualBenefitProposePhoneLabel => 'Other shop\'s phone';

  @override
  String get mutualBenefitProposeConditionLabel =>
      'Eligibility condition at your shop';

  @override
  String get mutualBenefitConditionMinTotal => 'Minimum invoice';

  @override
  String get mutualBenefitConditionServiceId => 'A specific service';

  @override
  String get mutualBenefitProposeConditionValueRiyals => 'Amount (SAR)';

  @override
  String get mutualBenefitProposeConditionValueService => 'Service';

  @override
  String get mutualBenefitProposeValidityLabel => 'Validity (days)';

  @override
  String get mutualBenefitProposeDurationLabel => 'Duration (days)';

  @override
  String get mutualBenefitProposeCapLabel => 'Cap / 30 days';

  @override
  String get mutualBenefitProposeGrantTypeLabel => 'Grant type';

  @override
  String get mutualBenefitGrantTypeDiscount => 'Discount';

  @override
  String get mutualBenefitGrantTypeGift => 'Gift';

  @override
  String get mutualBenefitScopeBlanket => 'Whole visit';

  @override
  String get mutualBenefitScopeItem => 'A specific service';

  @override
  String get mutualBenefitScopeGroup => 'Group/package';

  @override
  String get mutualBenefitProposeServiceLabel => 'Service';

  @override
  String get mutualBenefitProposeGroupLabel => 'Group';

  @override
  String get mutualBenefitProposeImmutableNote =>
      'Grant terms are fixed once sent — a different offer needs a new agreement';

  @override
  String get mutualBenefitProposeSubmitting => 'Sending...';

  @override
  String get mutualBenefitProposeSubmit => 'Send proposal';

  @override
  String mutualBenefitGrantGift(String name) {
    return 'Gift: $name';
  }

  @override
  String mutualBenefitGrantDiscountItem(String name) {
    return 'Discount on: $name';
  }

  @override
  String mutualBenefitGrantDiscountGroup(String name) {
    return 'Discount on group: $name';
  }

  @override
  String mutualBenefitPartnerCount(int n) {
    return '$n agreement(s)';
  }

  @override
  String get mutualBenefitProposeResultFail => 'Couldn\'t send the proposal';

  @override
  String get mutualBenefitRefusal402 =>
      'Your shop isn\'t subscribed to the Mutual Benefit app — subscribe from the app store first';

  @override
  String get mutualBenefitRefusal403 =>
      'You don\'t have permission for this action';

  @override
  String get mutualBenefitRefusal400 =>
      'The proposal\'s data is invalid — check the condition, or that you\'re not proposing a partnership with your own shop';

  @override
  String get mutualBenefitRefusal404 =>
      'No shop found with that number, or the chosen service/group doesn\'t exist in the other shop\'s catalogue';

  @override
  String get mutualBenefitRefusal409 =>
      'You\'ve reached the limit of 3 active partnerships, or the partnership\'s state has changed';

  @override
  String get mutualBenefitRefusal503 =>
      'Billing is temporarily unavailable, try again later';

  @override
  String get appStoreTitle => 'App Store';

  @override
  String get appStoreSubtitle => 'Grow your shop with real apps, one at a time';

  @override
  String get appStoreTabMine => 'My apps';

  @override
  String get appStoreTabAll => 'App Store';

  @override
  String get appStoreDetails => 'Details';

  @override
  String get appStorePerMonth => 'per month';

  @override
  String get appStorePerMonthShort => '/mo';

  @override
  String get appStoreActive => 'Active';

  @override
  String get appStoreTrialing => 'Trial';

  @override
  String get appStoreSubscribe => 'Subscribe now';

  @override
  String get appStoreCancelRenewal => 'Stop renewal';

  @override
  String get appStoreUndoCancel => 'Undo cancellation';

  @override
  String get appStoreConfirmCancel =>
      'Stop renewing this app? It stays active until the paid period ends';

  @override
  String appStoreCartCount(int n) {
    return '$n in cart';
  }

  @override
  String get appStoreCheckout => 'Checkout';

  @override
  String get appStoreCheckingOut => 'Checking out...';

  @override
  String get appStoreRefusal402 =>
      'Payment isn\'t enabled on your account right now — contact us to enable it';

  @override
  String get appStoreRefusal403 =>
      'You don\'t have permission to complete this purchase';

  @override
  String get appStoreRefusal404 =>
      'The requested plan wasn\'t found — refresh and try again';

  @override
  String get appStoreRefusal409 =>
      'This app is already owned, or its state changed mid-purchase';

  @override
  String get appStoreRefusalGeneric =>
      'Couldn\'t complete the purchase, try again';

  @override
  String get appStoreCapacityTitle => 'Capacity';

  @override
  String appStoreCapacityConfirmRemove(String name) {
    return 'Remove the last unit of \"$name\"? This stops its renewal entirely';
  }

  @override
  String get appStoreCartSubtotal => 'Subtotal';

  @override
  String get appStoreCartDiscount => 'Discount';

  @override
  String get appStoreCartTax => 'Tax';

  @override
  String get appStoreCartTotal => 'Total';

  @override
  String get appStoreCartDiscountCaveat =>
      'Shown before discount and tax; the exact amount is computed and shown at checkout.';

  @override
  String appStoreCartItemDiscount(int percent) {
    return '($percent% off)';
  }

  @override
  String appStoreAutoAdded(String added, String trigger) {
    return '\"$added\" was added automatically because \"$trigger\" needs it.';
  }

  @override
  String appStoreMissingRequirement(String names) {
    return 'Needs $names enabled first.';
  }

  @override
  String get appStoreRequiresAnyVisit => 'Record Visit';

  @override
  String get appStoreRequiresAnyBookings => 'Bookings';

  @override
  String get appStoreRequiresAnyContacts => 'Contacts';

  @override
  String get appStoreRequiresAnyMobileRequests => 'Mobile Requests';

  @override
  String get appStoreRequiresOr => 'or';

  @override
  String get appStoreOr => 'or';

  @override
  String appStoreCascadeWarning(String names) {
    return 'This will also stop: $names';
  }

  @override
  String appStoreDiscountBadge(int percent) {
    return '$percent% discount applied';
  }

  @override
  String appStoreDiscountBadgeWithApp(int percent, String app) {
    return '$percent% discount applied from $app';
  }

  @override
  String appStoreDiscountedShort(int percent) {
    return '$percent% off';
  }

  @override
  String appStoreOfferTitle(int percent) {
    return '$percent% discount awaits';
  }

  @override
  String appStoreOfferDesc(String app) {
    return 'Unlocks automatically when you subscribe to $app';
  }

  @override
  String appStoreAiUnitsCount(int units) {
    return '$units unit';
  }

  @override
  String get appStoreAiUnitsIncluded => 'Free AI, every month';

  @override
  String get whatsappAssistantTitle => 'AI Assistant';

  @override
  String get whatsappAssistantSubtitle =>
      'Replies to your customers on WhatsApp for you, suggesting your plans and their points at the right moment.';

  @override
  String get whatsappAssistantLoadFailed =>
      'Couldn\'t load the assistant\'s settings.';

  @override
  String get whatsappAssistantConfirm => 'Confirm';

  @override
  String get whatsappAssistantSaveFailed => 'Couldn\'t save, try again.';

  @override
  String get whatsappAssistantToggleTitle => 'Assistant is replying';

  @override
  String get whatsappAssistantToggleDesc =>
      'Turning it off locks the assistant completely, without cancelling your subscription — turn it back on any time.';

  @override
  String get whatsappAssistantToggleConfirmEnableTitle =>
      'Turn on the AI assistant?';

  @override
  String get whatsappAssistantToggleConfirmEnableBody =>
      'It will start replying to your customers on WhatsApp right away.';

  @override
  String get whatsappAssistantToggleConfirmDisableTitle =>
      'Turn off the AI assistant?';

  @override
  String get whatsappAssistantToggleConfirmDisableBody =>
      'It stops replying entirely, as if you weren\'t subscribed at all — without cancelling the subscription itself.';

  @override
  String get whatsappAssistantNotesTitle => 'Shop notes';

  @override
  String get whatsappAssistantNotesDesc =>
      'What you write here helps the assistant serve your customers with extra context about your shop.';

  @override
  String get whatsappAssistantWordLimitTitle => 'Customer message word limit';

  @override
  String get whatsappAssistantWordLimitDesc =>
      'The longest message the assistant accepts from a customer before asking him to shorten it.';

  @override
  String get whatsappAssistantAutoRegisterTitle => 'Auto-register contacts';

  @override
  String get whatsappAssistantAutoRegisterDesc =>
      'Any new number that messages your WhatsApp is automatically saved as a real contact.';

  @override
  String get whatsappAssistantAutoRegisterConfirmEnableTitle =>
      'Turn on auto-registration?';

  @override
  String get whatsappAssistantAutoRegisterConfirmEnableBody =>
      'Everyone who messages your WhatsApp number will be automatically saved as a contact, even from a single message.';

  @override
  String get whatsappAssistantAutoRegisterConfirmDisableTitle =>
      'Turn off auto-registration?';

  @override
  String get whatsappAssistantAutoRegisterConfirmDisableBody =>
      'New numbers will no longer be automatically saved as contacts.';

  @override
  String get partnerLoyaltyTitle => 'Partner Loyalty';

  @override
  String get partnerLoyaltySubtitle =>
      'Form an alliance with another registered shop and grant it a perk on its subscription with us';

  @override
  String get partnerLoyaltyCapLabel => 'Your current cap';

  @override
  String get partnerLoyaltyPrefsTitle =>
      'Alliance checkbox during visit recording';

  @override
  String get partnerLoyaltyPrefsDesc =>
      'Turning it on lets any staff member recording a visit form an alliance at the same moment.';

  @override
  String get partnerLoyaltyGrantTitle => 'Form an alliance';

  @override
  String get partnerLoyaltyPhoneLabel => 'Partner shop\'s phone number';

  @override
  String get partnerLoyaltyPhoneHintOk => 'No alliance with them this month';

  @override
  String get partnerLoyaltyPhoneHintAlready =>
      'Already allied with them this month';

  @override
  String get partnerLoyaltyPhoneHintUnregistered =>
      'This number is not a registered shop with us';

  @override
  String get partnerLoyaltyPercentLabel => 'Perk percent';

  @override
  String partnerLoyaltyCapLine(int p) {
    return 'Max percent you can grant now: $p%';
  }

  @override
  String get partnerLoyaltyScopeLabel => 'Covers';

  @override
  String get partnerLoyaltyScopeAll => 'All';

  @override
  String get partnerLoyaltySubmit => 'Form the alliance';

  @override
  String get partnerLoyaltySubmitting => 'Sending…';

  @override
  String get partnerLoyaltyResultSuccess =>
      'Alliance formed — applied automatically at the shop\'s next renewal.';

  @override
  String get partnerLoyaltyResultPartial =>
      'Partially formed — some apps were refused, open the log for details.';

  @override
  String get partnerLoyaltyOutcomeGranted => 'Succeeded';

  @override
  String get partnerLoyaltyOutcomeInvalidPercent => 'Invalid perk percent';

  @override
  String get partnerLoyaltyOutcomeInvalidScope => 'Choose a real app';

  @override
  String get partnerLoyaltyOutcomeOverCap => 'Exceeds your current cap';

  @override
  String get partnerLoyaltyOutcomeNoAccount =>
      'This number is not a registered shop with us';

  @override
  String get partnerLoyaltyOutcomeNotSubscribed =>
      'That shop holds none of the apps you chose';

  @override
  String get partnerLoyaltyOutcomeBillingUnavailable =>
      'Could not complete, try again';

  @override
  String get partnerLoyaltyOutcomeAlreadyHasBetterCoupon =>
      'Already holds a stronger perk';

  @override
  String get partnerLoyaltyOutcomeCouponExpired => 'Perk expired';

  @override
  String get partnerLoyaltyOutcomeCouponExhausted => 'Perk exhausted';

  @override
  String get partnerLoyaltyOutcomeCouponUnknown => 'Unknown perk';

  @override
  String get partnerLoyaltyOutcomePlanMismatch =>
      'Perk doesn\'t match this app';

  @override
  String get partnerLoyaltyOutcomeCouponDisabled => 'Perk disabled';

  @override
  String get partnerLoyaltyOutcomeCouponScheduled => 'Perk hasn\'t started yet';

  @override
  String get partnerLoyaltyTabLog => 'Log';

  @override
  String get partnerLoyaltyTabStats => 'Stats';

  @override
  String get partnerLoyaltyLogSearchHint => 'Search last 4 digits';

  @override
  String get partnerLoyaltyLogFilterAll => 'All statuses';

  @override
  String get partnerLoyaltyLogFilterOk => 'Succeeded only';

  @override
  String get partnerLoyaltyLogFilterFail => 'Failed only';

  @override
  String get partnerLoyaltyLogEmptyTitle => 'No alliances yet';

  @override
  String get partnerLoyaltyLogEmptyDesc => 'Your first alliance appears here.';

  @override
  String get partnerLoyaltyLogReadFailed => 'Could not read the log';

  @override
  String get partnerLoyaltyStatsKpiMonth => 'Alliances this month';

  @override
  String get partnerLoyaltyStatsKpiCap => 'Your current cap';

  @override
  String get partnerLoyaltyStatsKpiCeiling => 'Platform ceiling';

  @override
  String get partnerLoyaltyStatsLadderTitle => 'Your place on the ladder';

  @override
  String partnerLoyaltyStatsLadderNote(int n, int left, int p) {
    return '$n alliance(s) this month — $left more to reach the $p% tier';
  }

  @override
  String partnerLoyaltyStatsLadderAtTop(int n) {
    return '$n alliance(s) this month — you are at the top tier';
  }

  @override
  String partnerLoyaltyStatsCeilingNote(int p) {
    return 'Platform ceiling $p% — no shop ever exceeds it';
  }

  @override
  String get partnerLoyaltyStatsChartTitle =>
      'Alliances over the last 6 months';

  @override
  String get partnerLoyaltyReadFailedTitle => 'Could not read your data';

  @override
  String get partnerLoyaltyReadFailedDesc => 'Try again shortly.';

  @override
  String get shopReadFailed => 'Could not read your shop\'s indicators';

  @override
  String get shopMultiBranchTitle => 'Choose a branch';

  @override
  String get shopMultiBranchDesc =>
      'You have more than one branch — pick one to see its indicators.';

  @override
  String get shopEmptyBranchTitle => 'No data for this branch yet';

  @override
  String get shopRetentionTitle => 'Your customer return rate';

  @override
  String get shopRetentionMutedNote =>
      'Not enough visits yet to calculate this.';

  @override
  String get shopRetentionBrandNew =>
      'Register your first visit to start seeing your return rate.';

  @override
  String get shopRegisterFirstVisit => 'Register first visit';

  @override
  String get shopRetentionPrefix10 =>
      'Out of every 10 customers who visited you,';

  @override
  String get shopRetentionSuffix => 'come back';

  @override
  String get shopOneCustomer => 'One customer visited you';

  @override
  String shopNCustomers(int n) {
    return '$n customers visited you';
  }

  @override
  String shopRetentionSmallPrefix(String base) {
    return '$base, of whom';
  }

  @override
  String shopOverNMonths(int n) {
    return 'over $n months';
  }

  @override
  String get shopUnlimited => 'Unlimited';

  @override
  String get shopTileSentToday => 'Sent today';

  @override
  String get shopTileWaiting => 'Waiting';

  @override
  String get shopTileCeilingRemaining => 'Remaining today';

  @override
  String get shopNextStepLabel => 'Next step';

  @override
  String get shopNotNow => 'Not now';

  @override
  String get shopDeckUrgent => 'Urgent';

  @override
  String get shopDeckWeek => 'This week';

  @override
  String get shopDeckOpportunities => 'Opportunities';

  @override
  String get shopComputedNow => 'Computed now';

  @override
  String shopComputedHoursAgo(int n) {
    return 'Computed $n hour(s) ago';
  }

  @override
  String get shopStale => 'Stale';

  @override
  String get shopRefreshAction => 'Refresh';

  @override
  String get shopComputingTitle => 'Computing your indicators';

  @override
  String get shopComputeLoading => 'Computing…';

  @override
  String get shopComputeAction => 'Compute now';

  @override
  String get shopAtRiskTitle => 'Customers about to drift away';

  @override
  String get shopAtRiskMutedNote => 'Not enough data yet.';

  @override
  String get shopAtRiskAllGood => 'No overdue customer right now — all good';

  @override
  String get shopWaNotConnected => 'Your shop\'s WhatsApp isn\'t connected yet';

  @override
  String get shopWaNotVerified =>
      'Your shop\'s WhatsApp number isn\'t verified yet';

  @override
  String get shopCeilingReached => 'You\'ve reached today\'s message limit';

  @override
  String shopDaysOverdue(int n) {
    return '$n day(s) overdue';
  }

  @override
  String get shopAtRiskCta => 'Send a win-back campaign';

  @override
  String get shopAiImpactTitle => 'WhatsApp AI assistant impact';

  @override
  String get shopAiConversations => 'Conversations';

  @override
  String get shopAiBookings => 'Bookings';

  @override
  String get shopAiUpsellRate => 'Upsell acceptance';

  @override
  String get shopWeekMutedTitle => 'This week\'s visits';

  @override
  String get shopWeekMutedNote => 'Not enough data yet.';

  @override
  String get shopNewReturningMutedTitle => 'New vs returning customers';

  @override
  String get shopNewReturningMutedNote => 'Not enough data yet.';

  @override
  String get shopBranchCompareTitle => 'Branch comparison';

  @override
  String get shopBranchCompareMutedNote =>
      'Needs at least two branches to compare.';

  @override
  String get shopStaffCompareTitle => 'Staff comparison';

  @override
  String get shopStaffCompareMutedNote =>
      'Needs at least two staff members to compare.';

  @override
  String get shopWeekTitle => 'Visits this week';

  @override
  String get shopNewReturningTitle => 'New vs returning';

  @override
  String get shopNewLabel => 'New:';

  @override
  String get shopReturningLabel => 'Returning:';

  @override
  String get shopServicesTitle => 'Your services';

  @override
  String get shopServicesMutedNote => 'Not enough data yet.';

  @override
  String get shopMessageFlowTitle => 'Reminder message impact';

  @override
  String get shopMutedMessageFlowNote => 'Not enough data yet.';

  @override
  String get shopHoldoutTitle => 'Messaged vs not-messaged comparison';

  @override
  String get shopMutedHoldoutNote => 'Still measuring.';

  @override
  String shopReturnedAfterReminder(int visits, int days) {
    return '$visits visit(s) within $days days after a reminder';
  }

  @override
  String shopOptOutRate(String p) {
    return '$p% asked to stop receiving messages';
  }

  @override
  String get shopHoldoutNoMessages => 'No messages';

  @override
  String get shopHoldoutReached => 'Messaged';

  @override
  String get shopHoldoutOff =>
      'Message-impact measurement is off — all your customers receive everything, so there\'s no group to compare against.';

  @override
  String shopHoldoutMeasuring(int min, int need) {
    return 'We\'re still measuring your messages\' impact — $min of $need in the smaller group.';
  }

  @override
  String shopTodayRetrying(int n) {
    return '$n message(s) still trying to go out';
  }

  @override
  String get shopTrendUp => 'improving';

  @override
  String get shopTrendDown => 'declining';

  @override
  String shopRetentionSincePeriods(int n) {
    return 'for $n periods';
  }

  @override
  String get shopAtLeastSuffix => ' — at least';

  @override
  String get shopRegisterFirstVisitArrow => 'Record first visit ←';

  @override
  String get shopWeekNoCompare => 'We don\'t have a full week yet to compare';

  @override
  String shopNextStepAlso(String msg) {
    return 'Also: $msg';
  }

  @override
  String shopBranchCompareUnassigned(int n) {
    return '$n visit(s) with no branch set — not counted toward any branch.';
  }

  @override
  String get shopBranchCompareNeedTwo =>
      'We don\'t compare branches yet — needs two or more branches with real visits.';

  @override
  String get shopBranchCompareNeedSecond =>
      'One active branch so far — comparison needs a second branch with real visits.';

  @override
  String get shopBranchCompareTooShort =>
      'We don\'t rank branches yet — the period is too short, and comparing now would be unfair to the newest one.';

  @override
  String shopStaffCompareUnassigned(int n) {
    return '$n visit(s) with no staff set — not counted toward anyone.';
  }

  @override
  String get shopStaffCompareNeedTwo =>
      'We don\'t compare staff yet — needs two or more staff with visits attributed to them.';

  @override
  String get shopStaffCompareNeedSecond =>
      'One staff member attributed so far — comparison needs a second with real visits.';

  @override
  String get shopStaffCompareTooShort =>
      'We don\'t rank staff yet — the period is too short, and comparing now would be unfair to the newest one.';

  @override
  String get shopPeakTitle => 'Your busiest times';

  @override
  String get shopPeakMutedNote =>
      'Needs visits spread across enough days and hours to draw.';

  @override
  String shopPeakBusiestTime(String day, int h) {
    return '$day around $h:00';
  }

  @override
  String shopPeakBusiestNote(String name) {
    return 'Your busiest time: $name.';
  }

  @override
  String get shopEntityDayServicesTitle => 'Your services by day of week';

  @override
  String get shopEntityDayServicesHint =>
      'Which service is requested more on a given day — helps you prepare the right staff that day.';

  @override
  String get shopEntityDayServicesMutedNote =>
      'Needs visits spread across enough days to draw.';

  @override
  String get shopEntityDayBranchesTitle => 'Your branches by day of week';

  @override
  String get shopEntityDayBranchesHint =>
      'Your branches don\'t necessarily share the same rhythm — a mall branch gets busy on holidays, a neighborhood branch after work hours.';

  @override
  String get shopEntityDayBranchesMutedNote =>
      'Needs a second branch and visits spread across enough days to draw.';

  @override
  String get shopBundlesTitle => 'Suggested bundles';

  @override
  String get shopBundlesMutedNote =>
      'Not enough associations yet to suggest a bundle from.';

  @override
  String shopBundlesOpportunity(int n) {
    return '$n opportunity';
  }

  @override
  String get shopAssociationsTitle => 'Often requested together';

  @override
  String get shopAssociationsMutedNote => 'Not enough associations yet.';

  @override
  String shopAssociationsLearningNote(int have, int need) {
    return 'We don\'t know yet what\'s requested with what — spotting associations needs more visits for the pattern to be real, not coincidence. ($have/$need)';
  }

  @override
  String shopCustomersCount(int n) {
    return '$n customer(s)';
  }

  @override
  String get shopDay0Short => 'Su';

  @override
  String get shopDay1Short => 'Mo';

  @override
  String get shopDay2Short => 'Tu';

  @override
  String get shopDay3Short => 'We';

  @override
  String get shopDay4Short => 'Th';

  @override
  String get shopDay5Short => 'Fr';

  @override
  String get shopDay6Short => 'Sa';

  @override
  String get shopDay0Full => 'Sunday';

  @override
  String get shopDay1Full => 'Monday';

  @override
  String get shopDay2Full => 'Tuesday';

  @override
  String get shopDay3Full => 'Wednesday';

  @override
  String get shopDay4Full => 'Thursday';

  @override
  String get shopDay5Full => 'Friday';

  @override
  String get shopDay6Full => 'Saturday';

  @override
  String get shopMissedTitle =>
      'Customers who haven\'t tried everything that suits them';

  @override
  String get shopMissedMutedNote =>
      'No clear customers yet missing a service usually bought with theirs.';

  @override
  String get shopCustomerFallback => 'Customer';

  @override
  String get shopKpiActiveCustomers => 'Active customers';

  @override
  String get shopKpiReturnCycle => 'Return cycle';

  @override
  String shopDaysSuffix(int n) {
    return '$n days';
  }

  @override
  String get shopKpiChurnRate => 'Churn';

  @override
  String get shopTileServicesPerVisit => 'Services per visit';

  @override
  String get shopTileExpectedNextWeek => 'Expected next week';

  @override
  String get shopTileCycleCompletion => 'Cycle-return adherence';

  @override
  String get shopPerVisitMutedTitle =>
      'Services per visit, and cycle adherence';

  @override
  String get shopPerVisitMutedNote => 'Needs real visits first to compute.';

  @override
  String get shopLeadConversionTitle => 'Conversion of first-time contacts';

  @override
  String shopLeadConversionDetail(int converted, int total) {
    return '$converted of $total became a real visit';
  }

  @override
  String get whatsappOrdersTitle => 'WhatsApp Direct Ordering';

  @override
  String get whatsappOrdersSubtitle =>
      'Orders your customers place from your catalogue over WhatsApp, from arrival to delivery.';

  @override
  String get whatsappOrdersKpiWaiting => 'Awaiting review';

  @override
  String get whatsappOrdersKpiStuck => 'Overdue';

  @override
  String get whatsappOrdersKpiDeliveredToday => 'Delivered today';

  @override
  String get whatsappOrdersFilterAll => 'All';

  @override
  String get whatsappOrdersFilterIncoming => 'New';

  @override
  String get whatsappOrdersFilterConfirmed => 'Confirmed';

  @override
  String get whatsappOrdersFilterPreparing => 'Preparing';

  @override
  String get whatsappOrdersFilterReady => 'Ready';

  @override
  String get whatsappOrdersFilterDelivery => 'Out for delivery';

  @override
  String get whatsappOrdersFilterClosed => 'Closed';

  @override
  String get whatsappOrdersLoadFailedTitle => 'Could not load orders';

  @override
  String get whatsappOrdersLoadFailedBody =>
      'Check your connection and try again.';

  @override
  String get whatsappOrdersRetry => 'Retry';

  @override
  String get whatsappOrdersEmptyTitle => 'No orders yet';

  @override
  String get whatsappOrdersEmptyBody =>
      'Any order that arrives over WhatsApp shows up here right away.';

  @override
  String get whatsappOrdersUnnamed => 'Customer';

  @override
  String get whatsappOrdersStatusReceived => 'New';

  @override
  String get whatsappOrdersStatusPaymentMismatch => 'Payment mismatch';

  @override
  String get whatsappOrdersStatusConfirmed => 'Confirmed';

  @override
  String get whatsappOrdersStatusPreparing => 'Preparing';

  @override
  String get whatsappOrdersStatusReady => 'Ready';

  @override
  String get whatsappOrdersStatusOutForDelivery => 'Out for delivery';

  @override
  String get whatsappOrdersStatusDelivered => 'Delivered';

  @override
  String get whatsappOrdersStatusCancelled => 'Cancelled';

  @override
  String get whatsappOrdersStuckBadge => 'Overdue';

  @override
  String get whatsappOrdersOpenMap => 'Open location on map';

  @override
  String get whatsappOrdersPhoneCopied => 'Phone number copied';

  @override
  String get whatsappOrdersActionStartPreparing => 'Start preparing';

  @override
  String get whatsappOrdersActionMarkReady => 'Mark ready';

  @override
  String get whatsappOrdersActionStartDelivery => 'Send for delivery';

  @override
  String get whatsappOrdersActionMarkDelivered => 'Mark delivered';

  @override
  String get whatsappOrdersActionResolveMismatch => 'Confirm payment manually';

  @override
  String get whatsappOrdersActionCancel => 'Cancel order';

  @override
  String get whatsappOrdersActionFailed =>
      'Could not complete the action, try again.';

  @override
  String get whatsappOrdersCancelReasonPrompt =>
      'Cancellation reason (optional)';

  @override
  String get whatsappOrdersCancelReasonCancel => 'Back';

  @override
  String get whatsappOrdersCancelReasonConfirm => 'Confirm cancellation';

  @override
  String get whatsappOrdersPauseLabel => 'Stop accepting orders';

  @override
  String whatsappOrdersPauseBannerText(String reason) {
    return 'This branch is not accepting new WhatsApp orders — $reason';
  }

  @override
  String get whatsappOrdersPauseDefaultReason =>
      'Paused temporarily by the cashier';

  @override
  String get whatsappOrdersDrawerSubtotal => 'Subtotal before discount';

  @override
  String get whatsappOrdersDrawerDiscount => 'Discount';

  @override
  String get whatsappOrdersDrawerPointsReward => 'Loyalty points reward';

  @override
  String get whatsappOrdersDrawerTotal => 'Amount due';

  @override
  String whatsappOrdersDrawerMismatchHint(String paid) {
    return 'The amount the gateway reported ($paid) does not match what was due — verify manually before confirming.';
  }

  @override
  String whatsappOrdersDrawerCancelReason(String reason) {
    return 'Cancellation reason: $reason';
  }

  @override
  String whatsappOrdersDrawerNote(String note) {
    return 'Note: $note';
  }

  @override
  String get whatsappOrdersShareToggleLabel =>
      'Show the \"share with delivery rep\" button';

  @override
  String get whatsappOrdersActionShareWithRep => 'Share with delivery rep';

  @override
  String get whatsappOrdersShareHeading => 'New delivery order:';

  @override
  String whatsappOrdersShareCustomer(String name) {
    return 'Customer: $name';
  }

  @override
  String whatsappOrdersSharePhone(String phone) {
    return 'Phone: $phone';
  }

  @override
  String whatsappOrdersShareAddress(String url) {
    return 'Location: $url';
  }

  @override
  String whatsappOrdersShareTotal(String total) {
    return 'Total: $total';
  }
}
