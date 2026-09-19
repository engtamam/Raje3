/// Input validation utilities for form fields.
///
/// All validators follow the Flutter convention: return `null` if valid,
/// or a [String] error message if invalid. Error messages are in Arabic
/// (primary language) with the option for English.
///
/// Usage:
/// ```dart
/// TextFormField(
///   validator: (value) => Validators.validateEmail(value),
/// )
///
/// // Or with custom field name:
/// TextFormField(
///   validator: (value) => Validators.validateRequired(value, fieldName: 'الاسم'),
/// )
/// ```
class Validators {
  Validators._(); // Prevent instantiation

  // ─────────────────────────────────────────────────────────────────────────
  // REQUIRED
  // ─────────────────────────────────────────────────────────────────────────

  /// Validate that a field is not empty.
  ///
  /// Returns an error message if the value is null, empty, or only whitespace.
  static String? validateRequired(String? value, {String? fieldName}) {
    if (value == null || value.trim().isEmpty) {
      if (fieldName != null) {
        return '$fieldName مطلوب';
      }
      return 'هذا الحقل مطلوب';
    }
    return null;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // EMAIL
  // ─────────────────────────────────────────────────────────────────────────

  /// Validate an email address.
  ///
  /// Checks:
  /// - Not empty
  /// - Matches standard email pattern
  static String? validateEmail(String? value) {
    if (value == null || value.trim().isEmpty) {
      return 'البريد الإلكتروني مطلوب';
    }

    final trimmed = value.trim();

    // Standard email regex pattern
    final emailRegex = RegExp(
      r'^[a-zA-Z0-9.!#$%&*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,253}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,253}[a-zA-Z0-9])?)*$',
    );

    if (!emailRegex.hasMatch(trimmed)) {
      return 'البريد الإلكتروني غير صالح';
    }

    // Must have at least one dot after @
    final parts = trimmed.split('@');
    if (parts.length != 2 || !parts[1].contains('.')) {
      return 'البريد الإلكتروني غير صالح';
    }

    return null;
  }

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
  static String? validatePhone(String? value) {
    if (value == null || value.trim().isEmpty) {
      return 'رقم الهاتف مطلوب';
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
      return 'رقم الهاتف غير صالح - يجب أن يبدأ بـ 05';
    }

    return null;
  }

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
  static String? validatePassword(String? value) {
    if (value == null || value.isEmpty) {
      return 'كلمة المرور مطلوبة';
    }

    if (value.length < 8) {
      return 'كلمة المرور يجب أن تكون 8 أحرف على الأقل';
    }

    if (!RegExp(r'[A-Z]').hasMatch(value)) {
      return 'كلمة المرور يجب أن تحتوي على حرف كبير';
    }

    if (!RegExp(r'[a-z]').hasMatch(value)) {
      return 'كلمة المرور يجب أن تحتوي على حرف صغير';
    }

    if (!RegExp(r'[0-9]').hasMatch(value)) {
      return 'كلمة المرور يجب أن تحتوي على رقم';
    }

    return null;
  }

  /// Validate that a confirmation password matches the original.
  static String? validateConfirmPassword(String? value, String? password) {
    final requiredError = validateRequired(value, fieldName: 'تأكيد كلمة المرور');
    if (requiredError != null) return requiredError;

    if (value != password) {
      return 'كلمة المرور غير متطابقة';
    }

    return null;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // OTP
  // ─────────────────────────────────────────────────────────────────────────

  /// Validate a 6-digit OTP code.
  static String? validateOtp(String? value) {
    if (value == null || value.trim().isEmpty) {
      return 'رمز التحقق مطلوب';
    }

    final digits = value.trim().replaceAll(RegExp(r'[^\d]'), '');

    if (digits.length != 6) {
      return 'رمز التحقق يجب أن يكون 6 أرقام';
    }

    if (!RegExp(r'^\d{6}$').hasMatch(digits)) {
      return 'رمز التحقق يجب أن يحتوي على أرقام فقط';
    }

    return null;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // NAME
  // ─────────────────────────────────────────────────────────────────────────

  /// Validate a name field.
  ///
  /// Requirements:
  /// - Not empty
  /// - Minimum 2 characters
  /// - Only letters, spaces, and Arabic characters
  static String? validateName(String? value) {
    if (value == null || value.trim().isEmpty) {
      return 'الاسم مطلوب';
    }

    final trimmed = value.trim();

    if (trimmed.length < 2) {
      return 'الاسم يجب أن يكون حرفين على الأقل';
    }

    if (trimmed.length > 100) {
      return 'الاسم يجب أن لا يتجاوز 100 حرف';
    }

    // Allow Arabic characters, Latin characters, spaces, hyphens, and apostrophes
    final nameRegex = RegExp(r"^[\u0600-\u06FFa-zA-Z\s\-'\.]+$");
    if (!nameRegex.hasMatch(trimmed)) {
      return 'الاسم يحتوي على أحرف غير مسموحة';
    }

    return null;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // MIN / MAX LENGTH
  // ─────────────────────────────────────────────────────────────────────────

  /// Validate minimum length.
  static String? validateMinLength(String? value, int minLength, {String? fieldName}) {
    if (value == null || value.trim().length < minLength) {
      final name = fieldName ?? 'هذا الحقل';
      return '$name يجب أن يكون $minLength أحرف على الأقل';
    }
    return null;
  }

  /// Validate maximum length.
  static String? validateMaxLength(String? value, int maxLength, {String? fieldName}) {
    if (value != null && value.trim().length > maxLength) {
      final name = fieldName ?? 'هذا الحقل';
      return '$name يجب أن لا يتجاوز $maxLength حرف';
    }
    return null;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // NUMERIC
  // ─────────────────────────────────────────────────────────────────────────

  /// Validate that a value is a valid number.
  static String? validateNumber(String? value, {String? fieldName}) {
    if (value == null || value.trim().isEmpty) {
      return '${fieldName ?? 'هذا الحقل'} مطلوب';
    }

    if (double.tryParse(value.trim()) == null) {
      return '${fieldName ?? 'هذا الحقل'} يجب أن يكون رقم';
    }

    return null;
  }

  /// Validate that a number is within a range.
  static String? validateNumberRange(
    String? value, {
    double? min,
    double? max,
    String? fieldName,
  }) {
    final numberError = validateNumber(value, fieldName: fieldName);
    if (numberError != null) return numberError;

    final number = double.parse(value!.trim());
    final name = fieldName ?? 'القيمة';

    if (min != null && number < min) {
      return '$name يجب أن يكون $min على الأقل';
    }

    if (max != null && number > max) {
      return '$name يجب أن لا يتجاوز $max';
    }

    return null;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // URL
  // ─────────────────────────────────────────────────────────────────────────

  /// Validate a URL.
  static String? validateUrl(String? value) {
    if (value == null || value.trim().isEmpty) {
      return 'الرابط مطلوب';
    }

    final uri = Uri.tryParse(value.trim());
    if (uri == null || !uri.hasScheme || !uri.hasAuthority) {
      return 'الرابط غير صالح';
    }

    return null;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // COMPOSE VALIDATORS
  // ─────────────────────────────────────────────────────────────────────────

  /// Compose multiple validators into a single validator function.
  ///
  /// Returns the first error found, or null if all validators pass.
  ///
  /// ```dart
  /// TextFormField(
  ///   validator: Validators.compose([
  ///     (v) => Validators.validateRequired(v, fieldName: 'الاسم'),
  ///     (v) => Validators.validateMinLength(v, 3),
  ///   ]),
  /// )
  /// ```
  static String? Function(String?) compose(
    List<String? Function(String?)> validators,
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
