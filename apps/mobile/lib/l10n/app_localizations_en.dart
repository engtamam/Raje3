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
  String get navAppsLabel => 'My apps';

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
  String get branchesRoleManager => 'Manager';

  @override
  String get branchesSeatLimit =>
      'Your current plan does not allow another employee.';

  @override
  String get branchesHireFailed => 'Could not add the employee, try again.';

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
  String visitPointsRedeemedMessage(Object name) {
    return '$name redeemed ✓';
  }

  @override
  String get visitPointsRedeemFailed => 'Couldn\'t redeem it. Try again.';
}
