import 'dart:developer' as developer;
import 'dart:ui' show VoidCallback;
import 'package:dio/dio.dart';
import 'package:raje3_mobile/core/constants/api_constants.dart';
import 'package:raje3_mobile/core/storage/secure_storage.dart';

/// Interceptor that attaches the Bearer authentication token to every request.
///
/// On a 401 response (session expired/invalid), clears stored tokens and
/// triggers force-logout so the router redirects to the login screen.
/// Uses session-based auth (no refresh token mechanism).
class AuthInterceptor extends Interceptor {
  final SecureStorage _secureStorage;
  final Dio _dio;
  bool _hasForceLoggedOut = false;

  /// Callback invoked when token refresh fails and the user must re-login.
  /// Set this from main.dart to wire into AuthProvider.forceLogout().
  VoidCallback? onForceLogout;

  /// Last maintenance info from server (message + estimated end time).
  Map<String, dynamic>? _lastMaintenanceInfo;

  /// Returns the last maintenance info if in maintenance mode.
  Map<String, dynamic>? get lastMaintenanceInfo => _lastMaintenanceInfo;

  AuthInterceptor({
    required SecureStorage secureStorage,
    required Dio dio,
    this.onForceLogout,
  })  : _secureStorage = secureStorage,
        _dio = dio;

  /// Reset the force-logout guard after a successful login.
  ///
  /// Must be called when a new session is established so that future
  /// 401 errors can properly trigger force-logout again.
  void resetForceLogout() {
    _hasForceLoggedOut = false;
  }

  @override
  void onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) {
    // Attach token asynchronously but call handler only after completion.
    // Using .then() instead of async/await to satisfy Dio's void return type
    // contract — a `void async` method returns immediately, causing Dio to
    // proceed before the token is attached.
    _secureStorage.getAccessToken().then((accessToken) {
      if (accessToken != null && accessToken.isNotEmpty) {
        options.headers[ApiConstants.authHeader] = 'Bearer $accessToken';
      }

      // Always include client type header
      options.headers[ApiConstants.clientTypeHeader] = ApiConstants.clientType;

      handler.next(options);
    }).catchError((Object e) {
      // If token retrieval fails, proceed without token
      options.headers[ApiConstants.clientTypeHeader] = ApiConstants.clientType;
      handler.next(options);
    });
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    // Handle maintenance mode (503 with MAINTENANCE_MODE code)
    if (err.response?.statusCode == 503) {
      final data = err.response?.data;
      if (data is Map && data['error'] is Map && data['error']['code'] == 'MAINTENANCE_MODE') {
        _lastMaintenanceInfo = data['maintenance'] as Map<String, dynamic>?;
        developer.log(
          'Server is in maintenance mode: $_lastMaintenanceInfo',
          name: 'AuthInterceptor',
        );
      }
      handler.next(err);
      return;
    }

    if (err.response?.statusCode != 401) {
      handler.next(err);
      return;
    }

    // Handle 401 asynchronously using .then() chain to avoid void async.
    _handle401(err, handler);
  }

  /// Handles 401 errors: checks for stale token, retries, or forces logout.
  void _handle401(DioException err, ErrorInterceptorHandler handler) {
    final requestAuth = err.requestOptions.headers[ApiConstants.authHeader] as String?;

    _secureStorage.getAccessToken().then((currentToken) async {
      if (currentToken != null &&
          currentToken.isNotEmpty &&
          requestAuth != 'Bearer $currentToken') {
        // Token changed — retry with the newer token
        try {
          err.requestOptions.headers[ApiConstants.authHeader] = 'Bearer $currentToken';
          final response = await _dio.fetch(err.requestOptions);
          handler.resolve(response);
          return; // Retry succeeded, do not force logout
        } catch (_) {
          // Retry also failed — fall through to force logout
        }
      }

      // No retry possible or retry failed — force logout
      await _secureStorage.clearTokens();
      if (!_hasForceLoggedOut) {
        _hasForceLoggedOut = true;
        onForceLogout?.call();
      }
      handler.next(err);
    });
  }

}

/// Interceptor that sets the Accept-Language header based on the user's
/// preferred locale.
///
/// The backend uses this header to return localized messages.
class LanguageInterceptor extends Interceptor {
  String _locale;

  LanguageInterceptor({String locale = 'ar'}) : _locale = locale;

  /// Update the locale at runtime (e.g., when the user switches language).
  void updateLocale(String locale) {
    _locale = locale;
  }

  /// Current locale value.
  String get locale => _locale;

  @override
  void onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) {
    options.headers[ApiConstants.acceptLanguage] = _locale;
    handler.next(options);
  }
}

/// Interceptor that injects the active tenant (shop/branch) into every
/// API request as a header.
///
/// ADAPTED from the reference project's `ContextInterceptor`, which
/// injected `business_id`/`context_type` into the unified execute
/// endpoint's request body. Since this app uses plain REST (see
/// api_client.dart), there is no shared request-body shape to inject
/// into — a header serves the same purpose for every verb (GET included,
/// where there is no body at all).
///
/// Call [setActiveTenantId] when the active shop/branch changes. Pass
/// `null` to clear it.
class ContextInterceptor extends Interceptor {
  static const String tenantHeader = 'X-Tenant-Id';

  String? _activeTenantId;

  /// Update the active tenant ID for injection.
  void setActiveTenantId(String? id) {
    _activeTenantId = id;
  }

  /// Current active tenant ID, or null.
  String? get activeTenantId => _activeTenantId;

  @override
  void onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) {
    if (_activeTenantId != null) {
      options.headers[tenantHeader] = _activeTenantId;
    }
    handler.next(options);
  }
}

/// Debug-only interceptor that logs request and response details.
///
/// Enable this only in debug/development builds to avoid leaking
/// sensitive data in production logs.
class LoggingInterceptor extends Interceptor {
  final bool _enabled;

  LoggingInterceptor({bool enabled = true}) : _enabled = enabled;

  @override
  void onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) {
    if (_enabled) {
      developer.log(
        '--- REQUEST ---\n'
        'URL: ${options.method} ${options.uri}\n'
        'Headers: ${_sanitizeHeaders(options.headers)}\n'
        'Data: ${_truncateData(options.data)}',
        name: 'API',
      );
    }
    handler.next(options);
  }

  @override
  void onResponse(
    Response response,
    ResponseInterceptorHandler handler,
  ) {
    if (_enabled) {
      final success = response.data is Map
          ? response.data['success'] ?? 'N/A'
          : 'N/A';
      developer.log(
        '--- RESPONSE ---\n'
        'URL: ${response.requestOptions.uri}\n'
        'Status: ${response.statusCode}\n'
        'Success: $success\n'
        'Data: ${_truncateData(response.data)}',
        name: 'API',
      );
    }
    handler.next(response);
  }

  @override
  void onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) {
    if (_enabled) {
      developer.log(
        '--- ERROR ---\n'
        'URL: ${err.requestOptions.uri}\n'
        'Type: ${err.type}\n'
        'Status: ${err.response?.statusCode}\n'
        'Message: ${err.message}\n'
        'Response: ${_truncateData(err.response?.data)}',
        name: 'API',
        error: err,
      );
    }
    handler.next(err);
  }

  /// Remove sensitive headers (Authorization) before logging.
  Map<String, dynamic> _sanitizeHeaders(Map<String, dynamic> headers) {
    final sanitized = Map<String, dynamic>.from(headers);
    if (sanitized.containsKey(ApiConstants.authHeader)) {
      final token = sanitized[ApiConstants.authHeader] as String?;
      if (token != null && token.length > 20) {
        sanitized[ApiConstants.authHeader] =
            '${token.substring(0, 15)}...***';
      }
    }
    return sanitized;
  }

  /// Truncate data to avoid flooding the log console.
  String _truncateData(dynamic data) {
    if (data == null) return 'null';
    final str = data.toString();
    if (str.length > 500) {
      return '${str.substring(0, 500)}... [truncated]';
    }
    return str;
  }
}
