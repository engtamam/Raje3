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
  String get assistantConfirmActionPrompt => 'Confirm this action?';

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
  String get navAnalyticsLabel => 'Analytics';

  @override
  String get navHomeLabel => 'Home';

  @override
  String get navAccountLabel => 'Account';

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
}
