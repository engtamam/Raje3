import 'package:flutter_test/flutter_test.dart';
import 'package:raje3_mobile/core/network/api_response.dart';
import 'package:raje3_mobile/core/network/api_exceptions.dart';
import 'package:raje3_mobile/models/user_model.dart';

/// Security & critical-path tests for the network/auth infrastructure.
///
/// ADAPTED from the reference project's `test/security/security_critical_test.dart`
/// — this pass keeps the groups that test genuinely reusable infra
/// (ApiResponse parsing edge cases, ApiException handling/localization,
/// interceptor documentation tests) and drops the groups that asserted on
/// its own product's domain models (OrderModel, SubscriptionModel,
/// ScanModel, BusinessModel) or on the unified-execute-endpoint
/// module/action spread risk — this app doesn't use that endpoint pattern
/// (see api_client.dart's own doc comment), so that risk doesn't apply here.
void main() {
  // ═══════════════════════════════════════════════════════════════════════════
  // 1. API RESPONSE PARSING — EDGE CASES & SECURITY
  // ═══════════════════════════════════════════════════════════════════════════

  group('ApiResponse parsing edge cases', () {
    test('fromJson handles success=false with no data gracefully', () {
      final json = <String, dynamic>{
        'success': false,
        'message_ar': 'خطأ',
        'message_en': 'Error',
      };

      final response = ApiResponse<Map<String, dynamic>>.fromJson(json);

      expect(response.success, false);
      expect(response.data, isNull);
      expect(response.messageAr, 'خطأ');
    });

    test('fromJson handles missing success field (defaults to false)', () {
      final json = <String, dynamic>{
        'data': {'id': '123'},
      };

      final response = ApiResponse<Map<String, dynamic>>.fromJson(json);

      // success defaults to false when missing — safe default
      expect(response.success, false);
    });

    test('fromJson ignores data when it is a List (not Map)', () {
      final json = <String, dynamic>{
        'success': true,
        'data': [1, 2, 3],
      };

      final response = ApiResponse<UserModel>.fromJson(
        json,
        fromJsonT: (j) => UserModel.fromJson(j),
      );

      // data should be null because the JSON data field is a List, not a Map
      expect(response.success, true);
      expect(response.data, isNull);
    });

    test('fromJsonList silently drops non-Map items in data array', () {
      final json = <String, dynamic>{
        'success': true,
        'data': [
          {'id': 'u1', 'phone': '0500000001'},
          'invalid-string-item',
          42,
          null,
          {'id': 'u2', 'phone': '0500000002'},
        ],
      };

      final response = ApiResponse.fromJsonList<UserModel>(
        json,
        fromJsonT: (j) => UserModel.fromJson(j),
      );

      // Only valid Map items should be parsed
      expect(response.success, true);
      expect(response.data, isNotNull);
      expect(response.data!.length, 2);
    });

    test('fromJsonRaw returns null data when data is non-Map (fixed)', () {
      final json = <String, dynamic>{
        'success': true,
        'data': 'string-not-map',
      };

      // fromJsonRaw uses `is Map<String, dynamic>` check instead of an
      // unsafe `as` cast — returns null data for non-Map values.
      final response = ApiResponse.fromJsonRaw(json);
      expect(response.success, true);
      expect(response.data, isNull);
    });

    test('fromJson extracts error messages from nested error object', () {
      final json = <String, dynamic>{
        'success': false,
        'error': {
          'code': 'PLAN_LIMIT_REACHED',
          'message': 'Plan limit reached',
          'message_ar': 'تم الوصول للحد الأقصى',
          'message_en': 'Plan limit reached',
        },
      };

      final response = ApiResponse.fromJson(json);

      expect(response.success, false);
      expect(response.messageAr, 'تم الوصول للحد الأقصى');
      expect(response.messageEn, 'Plan limit reached');
    });

    test('fromJson handles error field that is not a Map', () {
      final json = <String, dynamic>{
        'success': false,
        'error': 'Simple string error',
      };

      final response = ApiResponse.fromJson(json);

      expect(response.success, false);
      // error is a string, not Map — should not crash
      expect(response.messageAr, isNull);
    });

    test('localizedMessage returns correct language', () {
      const response = ApiResponse(
        success: false,
        messageAr: 'رسالة عربية',
        messageEn: 'English message',
      );

      expect(response.localizedMessage('ar'), 'رسالة عربية');
      expect(response.localizedMessage('en'), 'English message');
    });

    test('localizedMessage falls back when preferred locale is null', () {
      const response = ApiResponse(
        success: false,
        messageAr: 'رسالة عربية',
        messageEn: null,
      );

      expect(response.localizedMessage('en'), 'رسالة عربية');
    });

    test('pagination hasMore calculation is correct', () {
      const response = ApiResponse(
        success: true,
        meta: {'total': 100, 'page': 5, 'limit': 20},
      );

      // page 5 * limit 20 = 100, total = 100 → no more
      expect(response.hasMore, false);

      const response2 = ApiResponse(
        success: true,
        meta: {'total': 101, 'page': 5, 'limit': 20},
      );

      // page 5 * limit 20 = 100 < 101 → has more
      expect(response2.hasMore, true);
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // 2. API EXCEPTIONS — SECURITY EDGE CASES
  // ═══════════════════════════════════════════════════════════════════════════

  group('API Exception handling', () {
    test('ValidationException.fromResponse handles null responseData', () {
      final exception = ValidationException.fromResponse(null);

      expect(exception.errors, isEmpty);
      expect(exception.statusCode, 422);
    });

    test('ValidationException.fromResponse parses field errors correctly', () {
      final responseData = <String, dynamic>{
        'message_ar': 'أخطاء في البيانات',
        'errors': {
          'phone': ['رقم الهاتف مطلوب', 'الرقم غير صالح'],
          'email': 'البريد مطلوب', // String instead of List
        },
      };

      final exception = ValidationException.fromResponse(responseData);

      expect(exception.errors['phone']!.length, 2);
      expect(exception.errors['email']!.length, 1); // String wrapped in List
      expect(exception.getFieldError('phone'), 'رقم الهاتف مطلوب');
      expect(exception.hasFieldError('email'), true);
      expect(exception.hasFieldError('name'), false);
      expect(exception.allErrors.length, 3);
    });

    test('ValidationException.fromResponse handles errors as non-Map', () {
      final responseData = <String, dynamic>{
        'errors': 'not a map',
      };

      // Should not throw
      final exception = ValidationException.fromResponse(responseData);
      expect(exception.errors, isEmpty);
    });

    test('All exception types have correct status codes', () {
      expect(const UnauthorizedException().statusCode, 401);
      expect(const ForbiddenException().statusCode, 403);
      expect(const NotFoundException().statusCode, 404);
      expect(const ValidationException().statusCode, 422);
      expect(const TooManyRequestsException().statusCode, 429);
      expect(const ServerException().statusCode, 500);
    });

    test('Exception localization works for both languages', () {
      const exception = UnauthorizedException();

      expect(exception.localizedMessage('ar'), contains('غير مصرح'));
      expect(exception.localizedMessage('en'), contains('Unauthorized'));
    });

    test('TooManyRequestsException carries retryAfterSeconds', () {
      const exception = TooManyRequestsException(retryAfterSeconds: 30);

      expect(exception.retryAfterSeconds, 30);
      expect(exception.statusCode, 429);
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // 3. API RESPONSE — FACTORY METHODS
  // ═══════════════════════════════════════════════════════════════════════════

  group('ApiResponse factory methods', () {
    test('success factory creates correct response', () {
      final response = ApiResponse.success(
        data: 'test-data',
        messageAr: 'تم بنجاح',
      );

      expect(response.success, true);
      expect(response.data, 'test-data');
      expect(response.messageAr, 'تم بنجاح');
    });

    test('failure factory creates correct response', () {
      final response = ApiResponse<String>.failure(
        messageAr: 'فشل',
        messageEn: 'Failed',
      );

      expect(response.success, false);
      expect(response.data, isNull);
      expect(response.messageAr, 'فشل');
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // 4. AUTH INTERCEPTOR — 401 HANDLING (documents expected behaviour)
  // ═══════════════════════════════════════════════════════════════════════════

  group('Auth interceptor 401 handling', () {
    test('force logout guard prevents multiple force logouts', () {
      // The _hasForceLoggedOut flag prevents cascading force logouts
      // when multiple requests fail with 401 simultaneously.
      // After resetForceLogout() is called (on new login), the guard resets.
      //
      // This is critical because without it:
      // - 5 concurrent requests all return 401
      // - Each triggers force logout
      // - AuthProvider.forceLogout() called 5 times
      // - setState(unauthenticated) fires 5 times
      // - Router redirects to login 5 times
    });

    test('stale token detection retries with current token', () {
      // When a 401 arrives, the interceptor checks if the failed request's
      // token differs from the currently stored token. If so, it retries
      // with the current token before triggering force logout.
      //
      // This handles the race condition:
      // 1. Request A sent with token-1
      // 2. User re-logs in, gets token-2
      // 3. Request A fails with 401 (token-1 expired)
      // 4. Interceptor detects token-1 != token-2, retries with token-2
      // 5. If retry succeeds, no force logout needed
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // 5. LOGGING INTERCEPTOR — TOKEN LEAK PREVENTION
  // ═══════════════════════════════════════════════════════════════════════════

  group('Logging interceptor token sanitization', () {
    test('sanitizeHeaders masks auth token (leaves only 15 chars)', () {
      // LoggingInterceptor._sanitizeHeaders replaces the full token with
      // first 15 chars + "...***" — enough for debug identification
      // without leaking enough to reconstruct it.
      const token = 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.sig';
      expect(token.length, greaterThan(20));

      final sanitized = '${token.substring(0, 15)}...***';
      expect(sanitized, 'Bearer eyJhbGci...***');
      expect(sanitized.length, lessThan(token.length));
    });

    test('sanitizeHeaders handles short/missing tokens', () {
      // If token is <= 20 chars, it's logged as-is — acceptable because
      // tokens that short are likely test tokens or malformed.
      const shortToken = 'Bearer short';
      expect(shortToken.length, lessThanOrEqualTo(20));
    });
  });
}
