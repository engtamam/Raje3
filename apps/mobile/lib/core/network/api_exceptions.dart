// Custom API exception classes for structured error handling.
//
// Exception hierarchy:
// - ApiException — Base exception for all API errors
//   - UnauthorizedException — 401 authentication errors
//   - NetworkException — No internet / connection failures
//   - ServerException — 500+ server-side errors
//   - ValidationException — 422 validation errors with field-level details
//   - ApiTimeoutException — Request timeout errors
//   - NotFoundException — 404 resource not found
//   - ForbiddenException — 403 access denied
//   - TooManyRequestsException — 429 rate limiting

/// Base exception for all API-related errors.
class ApiException implements Exception {
  /// Human-readable error message.
  final String message;

  /// HTTP status code (if available).
  final int? statusCode;

  /// Raw response data from the server (if available).
  final dynamic data;

  /// Arabic error message from the server.
  final String? messageAr;

  /// English error message from the server.
  final String? messageEn;

  const ApiException({
    required this.message,
    this.statusCode,
    this.data,
    this.messageAr,
    this.messageEn,
  });

  /// Returns the appropriate message based on locale.
  String localizedMessage(String locale) {
    if (locale == 'ar') {
      return messageAr ?? message;
    }
    return messageEn ?? message;
  }

  @override
  String toString() => 'ApiException($statusCode): $message';
}

/// Thrown when the user's authentication token is invalid or expired (HTTP 401).
///
/// The app should respond by attempting a token refresh, and if that fails,
/// redirecting the user to the login screen.
class UnauthorizedException extends ApiException {
  const UnauthorizedException({
    super.message = 'غير مصرح - يرجى تسجيل الدخول مرة أخرى',
    super.statusCode = 401,
    super.data,
    super.messageAr = 'غير مصرح - يرجى تسجيل الدخول مرة أخرى',
    super.messageEn = 'Unauthorized - Please login again',
  });
}

/// Thrown when there is no internet connection or a DNS/TCP failure.
class NetworkException extends ApiException {
  const NetworkException({
    super.message = 'لا يوجد اتصال بالإنترنت',
    super.statusCode,
    super.data,
    super.messageAr = 'لا يوجد اتصال بالإنترنت',
    super.messageEn = 'No internet connection',
  });
}

/// Thrown when the server returns a 5xx error.
class ServerException extends ApiException {
  const ServerException({
    super.message = 'حدث خطأ في الخادم - يرجى المحاولة لاحقاً',
    super.statusCode = 500,
    super.data,
    super.messageAr = 'حدث خطأ في الخادم - يرجى المحاولة لاحقاً',
    super.messageEn = 'Server error - Please try again later',
  });
}

/// Thrown when the server returns validation errors (HTTP 422).
///
/// Contains a map of field names to their error messages, allowing
/// the UI to display inline field-level errors.
class ValidationException extends ApiException {
  /// Map of field name to list of error messages.
  /// Example: `{'email': ['البريد الإلكتروني مطلوب'], 'phone': ['رقم الهاتف غير صالح']}`
  final Map<String, List<String>> errors;

  const ValidationException({
    super.message = 'يوجد أخطاء في البيانات المدخلة',
    super.statusCode = 422,
    super.data,
    super.messageAr = 'يوجد أخطاء في البيانات المدخلة',
    super.messageEn = 'Validation errors in the submitted data',
    this.errors = const {},
  });

  /// Get the first error message for a specific field.
  String? getFieldError(String field) {
    final fieldErrors = errors[field];
    if (fieldErrors != null && fieldErrors.isNotEmpty) {
      return fieldErrors.first;
    }
    return null;
  }

  /// Whether there are errors for a specific field.
  bool hasFieldError(String field) => errors.containsKey(field);

  /// Get all error messages flattened into a single list.
  List<String> get allErrors =>
      errors.values.expand((errorList) => errorList).toList();

  /// Factory to parse validation errors from the server response data.
  factory ValidationException.fromResponse(Map<String, dynamic>? responseData) {
    final Map<String, List<String>> parsedErrors = {};

    if (responseData != null && responseData['errors'] is Map) {
      final errorsMap = responseData['errors'] as Map<String, dynamic>;
      for (final entry in errorsMap.entries) {
        if (entry.value is List) {
          parsedErrors[entry.key] = (entry.value as List)
              .map((e) => e.toString())
              .toList();
        } else if (entry.value is String) {
          parsedErrors[entry.key] = [entry.value as String];
        }
      }
    }

    return ValidationException(
      message: responseData?['message_ar'] as String? ??
          'يوجد أخطاء في البيانات المدخلة',
      messageAr: responseData?['message_ar'] as String?,
      messageEn: responseData?['message_en'] as String?,
      data: responseData,
      errors: parsedErrors,
    );
  }

  @override
  String toString() =>
      'ValidationException($statusCode): $message, errors: $errors';
}

/// Thrown when a request times out.
class ApiTimeoutException extends ApiException {
  const ApiTimeoutException({
    super.message = 'انتهت مهلة الطلب - يرجى المحاولة مرة أخرى',
    super.statusCode,
    super.data,
    super.messageAr = 'انتهت مهلة الطلب - يرجى المحاولة مرة أخرى',
    super.messageEn = 'Request timed out - Please try again',
  });
}

/// Thrown when the requested resource is not found (HTTP 404).
class NotFoundException extends ApiException {
  const NotFoundException({
    super.message = 'العنصر المطلوب غير موجود',
    super.statusCode = 404,
    super.data,
    super.messageAr = 'العنصر المطلوب غير موجود',
    super.messageEn = 'The requested resource was not found',
  });
}

/// Thrown when the user does not have permission (HTTP 403).
class ForbiddenException extends ApiException {
  const ForbiddenException({
    super.message = 'ليس لديك صلاحية للقيام بهذا الإجراء',
    super.statusCode = 403,
    super.data,
    super.messageAr = 'ليس لديك صلاحية للقيام بهذا الإجراء',
    super.messageEn = 'You do not have permission to perform this action',
  });
}

/// Thrown when the rate limit is exceeded (HTTP 429).
class TooManyRequestsException extends ApiException {
  /// Number of seconds before the user can retry.
  final int? retryAfterSeconds;

  const TooManyRequestsException({
    super.message = 'تم تجاوز الحد المسموح من الطلبات - يرجى الانتظار',
    super.statusCode = 429,
    super.data,
    super.messageAr = 'تم تجاوز الحد المسموح من الطلبات - يرجى الانتظار',
    super.messageEn = 'Too many requests - Please wait before trying again',
    this.retryAfterSeconds,
  });
}
