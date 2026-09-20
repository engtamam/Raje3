import 'package:flutter/widgets.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';

/// A validation failure produced by [Validators].
///
/// [Validators] is a pure logic layer with no [BuildContext], so it cannot
/// call `S.of(context)` itself. Each validator returns a [ValidationError]
/// (or `null` when the value is valid) instead of a ready-made sentence; the
/// call site — always a widget with a [BuildContext], such as a
/// `TextFormField.validator` closure defined inside `build()` — resolves it
/// to a localized string with [text].
class ValidationError {
  const ValidationError(this._resolve);

  final String Function(S s) _resolve;

  /// Resolve this error to a localized message for [context].
  String text(BuildContext context) => _resolve(S.of(context)!);
}

/// Input validation utilities for form fields.
///
/// All validators follow the Flutter convention: return `null` if valid,
/// or a [ValidationError] if invalid — see [ValidationError] for why this
/// isn't a ready-made [String].
///
/// Usage:
/// ```dart
/// TextFormField(
///   validator: (value) => Validators.validateEmail(value)?.text(context),
/// )
///
/// // Or with custom field name:
/// TextFormField(
///   validator: (value) =>
///       Validators.validateRequired(value, fieldName: S.of(context)!.authShopNameLabel)
///           ?.text(context),
/// )
/// ```
class Validators {
  Validators._(); // Prevent instantiation

  // ─────────────────────────────────────────────────────────────────────────
  // REQUIRED
  // ─────────────────────────────────────────────────────────────────────────

  /// Validate that a field is not empty.
  ///
  /// [fieldName] should already be localized by the caller (e.g.
  /// `S.of(context)!.authPasswordLabel`) — this layer only plugs it into the
  /// generic "$fieldName is required" template.
  static ValidationError? validateRequired(String? value, {String? fieldName}) {
    if (value == null || value.trim().isEmpty) {
      if (fieldName != null) {
        return ValidationError((s) => s.validatorFieldRequiredNamed(fieldName));
      }
      return const ValidationError(_requiredGeneric);
    }
    return null;
  }

  static String _requiredGeneric(S s) => s.validatorFieldRequiredGeneric;

  // ─────────────────────────────────────────────────────────────────────────
  // EMAIL
  // ─────────────────────────────────────────────────────────────────────────

  /// Validate an email address.
  ///
  /// Checks:
  /// - Not empty
  /// - Matches standard email pattern
  static ValidationError? validateEmail(String? value) {
    if (value == null || value.trim().isEmpty) {
      return const ValidationError(_emailRequired);
    }

    final trimmed = value.trim();

    // Standard email regex pattern
    final emailRegex = RegExp(
      r'^[a-zA-Z0-9.!#$%&*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,253}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,253}[a-zA-Z0-9])?)*$',
    );

    if (!emailRegex.hasMatch(trimmed)) {
      return const ValidationError(_emailInvalid);
    }

    // Must have at least one dot after @
    final parts = trimmed.split('@');
    if (parts.length != 2 || !parts[1].contains('.')) {
      return const ValidationError(_emailInvalid);
    }

    return null;
  }

  static String _emailRequired(S s) => s.validatorEmailRequired;
  static String _emailInvalid(S s) => s.validatorEmailInvalid;

  // ─────────────────────────────────────────────────────────────────────────
  // PHONE (Saudi Arabia)
  // ─────────────────────────────────────────────────────────────────────────

  /// Validate a Saudi phone number.
  ///
  /// Accepted formats:
  /// - 05XXXXXXXX (10 digits starting with 05)
  /// - 5XXXXXXXX (9 digits starting with 5)
  /// - 966XXXXXXXXX (12 digits with country code)
  /// - +966XXXXXXXXX (with +)
  /// - 00966XXXXXXXXX (with 00)
  static ValidationError? validatePhone(String? value) {
    if (value == null || value.trim().isEmpty) {
      return const ValidationError(_phoneRequired);
    }

    // Remove all non-digit characters except +
    String phone = value.trim().replaceAll(RegExp(r'[^\d+]'), '');

    // Remove leading + if present
    if (phone.startsWith('+')) {
      phone = phone.substring(1);
    }

    // Remove leading 00 if present
    if (phone.startsWith('00')) {
      phone = phone.substring(2);
    }

    // Normalize to digits only
    phone = phone.replaceAll(RegExp(r'[^\d]'), '');

    // Check valid Saudi mobile formats
    bool isValid = false;

    // Format: 05XXXXXXXX (10 digits)
    if (phone.length == 10 && phone.startsWith('05')) {
      isValid = true;
    }
    // Format: 5XXXXXXXX (9 digits)
    else if (phone.length == 9 && phone.startsWith('5')) {
      isValid = true;
    }
    // Format: 9665XXXXXXXX (12 digits)
    else if (phone.length == 12 && phone.startsWith('9665')) {
      isValid = true;
    }

    if (!isValid) {
      return const ValidationError(_phoneInvalid);
    }

    return null;
  }

  static String _phoneRequired(S s) => s.validatorPhoneRequired;
  static String _phoneInvalid(S s) => s.validatorPhoneInvalid;

  // ─────────────────────────────────────────────────────────────────────────
  // PASSWORD
  // ─────────────────────────────────────────────────────────────────────────

  /// Validate a password.
  ///
  /// Requirements:
  /// - Minimum 8 characters
  /// - At least one uppercase letter
  /// - At least one lowercase letter
  /// - At least one digit
  static ValidationError? validatePassword(String? value) {
    if (value == null || value.isEmpty) {
      return const ValidationError(_passwordRequired);
    }

    if (value.length < 8) {
      return const ValidationError(_passwordTooShort);
    }

    if (!RegExp(r'[A-Z]').hasMatch(value)) {
      return const ValidationError(_passwordNeedsUppercase);
    }

    if (!RegExp(r'[a-z]').hasMatch(value)) {
      return const ValidationError(_passwordNeedsLowercase);
    }

    if (!RegExp(r'[0-9]').hasMatch(value)) {
      return const ValidationError(_passwordNeedsDigit);
    }

    return null;
  }

  static String _passwordRequired(S s) => s.validatorPasswordRequired;
  static String _passwordTooShort(S s) => s.validatorPasswordTooShort;
  static String _passwordNeedsUppercase(S s) => s.validatorPasswordNeedsUppercase;
  static String _passwordNeedsLowercase(S s) => s.validatorPasswordNeedsLowercase;
  static String _passwordNeedsDigit(S s) => s.validatorPasswordNeedsDigit;

  /// Validate that a confirmation password matches the original.
  ///
  /// [fieldName] defaults to the localized "Confirm password" label so
  /// existing call sites don't need to pass one.
  static ValidationError? validateConfirmPassword(String? value, String? password) {
    if (value == null || value.trim().isEmpty) {
      return ValidationError((s) => s.validatorFieldRequiredNamed(s.validatorConfirmPasswordFieldName));
    }

    if (value != password) {
      return const ValidationError(_passwordMismatch);
    }

    return null;
  }

  static String _passwordMismatch(S s) => s.validatorPasswordMismatch;

  // ─────────────────────────────────────────────────────────────────────────
  // OTP
  // ─────────────────────────────────────────────────────────────────────────

  /// Validate a 6-digit OTP code.
  static ValidationError? validateOtp(String? value) {
    if (value == null || value.trim().isEmpty) {
      return const ValidationError(_otpRequired);
    }

    final digits = value.trim().replaceAll(RegExp(r'[^\d]'), '');

    if (digits.length != 6) {
      return const ValidationError(_otpLength);
    }

    if (!RegExp(r'^\d{6}$').hasMatch(digits)) {
      return const ValidationError(_otpDigitsOnly);
    }

    return null;
  }

  static String _otpRequired(S s) => s.validatorOtpRequired;
  static String _otpLength(S s) => s.validatorOtpLength;
  static String _otpDigitsOnly(S s) => s.validatorOtpDigitsOnly;

  // ─────────────────────────────────────────────────────────────────────────
  // NAME
  // ─────────────────────────────────────────────────────────────────────────

  /// Validate a name field.
  ///
  /// Requirements:
  /// - Not empty
  /// - Minimum 2 characters
  /// - Only letters, spaces, and Arabic characters
  static ValidationError? validateName(String? value) {
    if (value == null || value.trim().isEmpty) {
      return const ValidationError(_nameRequired);
    }

    final trimmed = value.trim();

    if (trimmed.length < 2) {
      return const ValidationError(_nameTooShort);
    }

    if (trimmed.length > 100) {
      return const ValidationError(_nameTooLong);
    }

    // Allow Arabic characters, Latin characters, spaces, hyphens, and apostrophes
    final nameRegex = RegExp(r"^[؀-ۿa-zA-Z\s\-'\.]+$");
    if (!nameRegex.hasMatch(trimmed)) {
      return const ValidationError(_nameInvalidChars);
    }

    return null;
  }

  static String _nameRequired(S s) => s.validatorNameRequired;
  static String _nameTooShort(S s) => s.validatorNameTooShort;
  static String _nameTooLong(S s) => s.validatorNameTooLong;
  static String _nameInvalidChars(S s) => s.validatorNameInvalidChars;

  // ─────────────────────────────────────────────────────────────────────────
  // MIN / MAX LENGTH
  // ─────────────────────────────────────────────────────────────────────────

  /// Validate minimum length.
  ///
  /// [fieldName] should already be localized by the caller.
  static ValidationError? validateMinLength(String? value, int minLength, {String? fieldName}) {
    if (value == null || value.trim().length < minLength) {
      return ValidationError((s) =>
          s.validatorMinLengthNamed(fieldName ?? s.validatorGenericFieldName, minLength));
    }
    return null;
  }

  /// Validate maximum length.
  ///
  /// [fieldName] should already be localized by the caller.
  static ValidationError? validateMaxLength(String? value, int maxLength, {String? fieldName}) {
    if (value != null && value.trim().length > maxLength) {
      return ValidationError((s) =>
          s.validatorMaxLengthNamed(fieldName ?? s.validatorGenericFieldName, maxLength));
    }
    return null;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // NUMERIC
  // ─────────────────────────────────────────────────────────────────────────

  /// Validate that a value is a valid number.
  ///
  /// [fieldName] should already be localized by the caller.
  static ValidationError? validateNumber(String? value, {String? fieldName}) {
    if (value == null || value.trim().isEmpty) {
      return ValidationError((s) => s.validatorFieldRequiredNamed(fieldName ?? s.validatorGenericFieldName));
    }

    if (double.tryParse(value.trim()) == null) {
      return ValidationError((s) => s.validatorNotANumberNamed(fieldName ?? s.validatorGenericFieldName));
    }

    return null;
  }

  /// Validate that a number is within a range.
  ///
  /// [fieldName] should already be localized by the caller.
  static ValidationError? validateNumberRange(
    String? value, {
    double? min,
    double? max,
    String? fieldName,
  }) {
    final numberError = validateNumber(value, fieldName: fieldName);
    if (numberError != null) return numberError;

    final number = double.parse(value!.trim());

    if (min != null && number < min) {
      return ValidationError(
          (s) => s.validatorMinValueNamed(fieldName ?? s.validatorGenericValueName, _numToString(min)));
    }

    if (max != null && number > max) {
      return ValidationError(
          (s) => s.validatorMaxValueNamed(fieldName ?? s.validatorGenericValueName, _numToString(max)));
    }

    return null;
  }

  static String _numToString(double n) => n == n.roundToDouble() ? n.toStringAsFixed(0) : n.toString();

  // ─────────────────────────────────────────────────────────────────────────
  // URL
  // ─────────────────────────────────────────────────────────────────────────

  /// Validate a URL.
  static ValidationError? validateUrl(String? value) {
    if (value == null || value.trim().isEmpty) {
      return const ValidationError(_urlRequired);
    }

    final uri = Uri.tryParse(value.trim());
    if (uri == null || !uri.hasScheme || !uri.hasAuthority) {
      return const ValidationError(_urlInvalid);
    }

    return null;
  }

  static String _urlRequired(S s) => s.validatorUrlRequired;
  static String _urlInvalid(S s) => s.validatorUrlInvalid;

  // ─────────────────────────────────────────────────────────────────────────
  // COMPOSE VALIDATORS
  // ─────────────────────────────────────────────────────────────────────────

  /// Compose multiple validators into a single validator function.
  ///
  /// Returns the first error found, or null if all validators pass.
  ///
  /// ```dart
  /// TextFormField(
  ///   validator: (v) => Validators.compose([
  ///     (v) => Validators.validateRequired(v, fieldName: S.of(context)!.authShopNameLabel),
  ///     (v) => Validators.validateMinLength(v, 3),
  ///   ])(v)?.text(context),
  /// )
  /// ```
  static ValidationError? Function(String?) compose(
    List<ValidationError? Function(String?)> validators,
  ) {
    return (String? value) {
      for (final validator in validators) {
        final error = validator(value);
        if (error != null) return error;
      }
      return null;
    };
  }
}
