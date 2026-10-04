import 'dart:developer' as developer;
import 'dart:ui' show VoidCallback;
import 'package:dio/dio.dart';
import 'package:raje3_mobile/core/constants/api_constants.dart';
import 'package:raje3_mobile/core/storage/secure_storage.dart';

/// Interceptor that attaches the Bearer authentication token to every request.
///
/// On a 401, transparently mints a fresh access token from the stored refresh token
/// (`POST /api/v1/auth/refresh`, `platform/services/identity-service/app/api/v1/auth.py`'s own
/// route — real, rotating, theft-detecting) and retries the failed request. Force-logout is now
/// the FALLBACK, not the first response to expiry: it fires only when there is no refresh token
/// at all, or the identity service itself refuses it (revoked session, reused/stolen token).
///
/// FOUND LIVE, 2026-09-23: the access token's own 900-second TTL made the app look like it had
/// silently lost the account's permissions every ~15 minutes — `NavProvider` read a 401-caused
/// `null` catalogue exactly like "no capabilities", with nothing telling the operator to sign in
/// again. `ApiClient`'s own `validateStatus` comment already said the intent out loud
/// ("401 must trigger AuthInterceptor's onError so it can attempt automatic token refresh") —
/// this was always the design, just never actually wired to the refresh endpoint that already
/// existed server-side.
class AuthInterceptor extends Interceptor {
  final SecureStorage _secureStorage;
  final Dio _dio;
  bool _hasForceLoggedOut = false;

  /// SINGLE-FLIGHT REFRESH, NOT ONE PER FAILED REQUEST. Several requests can 401 at once (this
  /// screen fires 3–4 calls in parallel routinely); identity's own refresh-token rotation treats
  /// a SECOND concurrent use of the same refresh token as theft and revokes the whole session
  /// family (`auth_service.py::refresh`'s own CAS comment) — so every 401 that lands while a
  /// refresh is already in flight awaits that SAME future instead of starting its own.
  Future<bool>? _refreshing;

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

  /// Handles 401 errors: retry with an already-newer token (another request refreshed first),
  /// refresh and retry (the common case), or force logout (no refresh token, or identity itself
  /// refused it — a genuinely dead session).
  void _handle401(DioException err, ErrorInterceptorHandler handler) {
    // A REFRESH CALL 401ING MEANS THE REFRESH TOKEN ITSELF IS DEAD — refreshing a dead refresh
    // token would recurse forever. This is the one real "must log in again" case.
    if (err.requestOptions.path.contains('/auth/refresh')) {
      _forceLogout(err, handler);
      return;
    }
    _refreshAndRetry(err, handler);
  }

  Future<void> _refreshAndRetry(DioException err, ErrorInterceptorHandler handler) async {
    final requestAuth = err.requestOptions.headers[ApiConstants.authHeader] as String?;

    // ANOTHER REQUEST ALREADY REFRESHED, between when this one was SENT and when its 401 landed
    // — retry straight away with the token that already exists, no second refresh needed.
    final storedToken = await _secureStorage.getAccessToken();
    if (storedToken != null && storedToken.isNotEmpty && requestAuth != 'Bearer $storedToken') {
      if (await _retry(err, handler, storedToken)) return;
    }

    final refreshed = await _ensureRefreshed();
    if (!refreshed) {
      await _forceLogout(err, handler);
      return;
    }
    final newToken = await _secureStorage.getAccessToken();
    if (newToken == null || newToken.isEmpty || await _retry(err, handler, newToken)) return;
    await _forceLogout(err, handler);
  }

  /// Retries the failed request with [token]. Returns whether the retry itself succeeded —
  /// `false` falls through to whatever the caller does next (another attempt, or force logout).
  Future<bool> _retry(DioException err, ErrorInterceptorHandler handler, String token) async {
    try {
      err.requestOptions.headers[ApiConstants.authHeader] = 'Bearer $token';
      final response = await _dio.fetch(err.requestOptions);
      handler.resolve(response);
      return true;
    } catch (_) {
      return false;
    }
  }

  Future<bool> _ensureRefreshed() {
    return _refreshing ??= _doRefresh().whenComplete(() => _refreshing = null);
  }

  /// `POST /api/v1/auth/refresh` — a RAW Dio instance, deliberately outside this same
  /// interceptor stack: routing the refresh call through `_dio` would re-enter `onRequest`'s own
  /// Bearer-token attach (the wrong, now-expired token) and, on failure, this same `onError`
  /// handler recursively. A bare client with only the base URL and client-type header is the
  /// whole request this route needs.
  Future<bool> _doRefresh() async {
    final refreshToken = await _secureStorage.getRefreshToken();
    if (refreshToken == null || refreshToken.isEmpty) return false;
    try {
      final raw = Dio(BaseOptions(
        baseUrl: ApiConstants.baseUrl,
        connectTimeout: const Duration(milliseconds: 10000),
        receiveTimeout: const Duration(milliseconds: 10000),
        headers: {ApiConstants.clientTypeHeader: ApiConstants.clientType},
      ));
      final response = await raw.post<dynamic>(
        '/api/v1/auth/refresh',
        data: {'refresh_token': refreshToken},
      );
      final data = response.data;
      if (data is! Map) return false;
      final newAccess = data['access_token'] as String?;
      final newRefresh = data['refresh_token'] as String?;
      final expiresIn = (data['expires_in'] as num?)?.toInt();
      if (newAccess == null || newAccess.isEmpty || newRefresh == null || newRefresh.isEmpty) {
        return false;
      }
      await _secureStorage.setTokens(
        accessToken: newAccess,
        refreshToken: newRefresh,
        tokenExpiry: expiresIn != null
            ? DateTime.now().add(Duration(seconds: expiresIn)).toIso8601String()
            : null,
      );
      return true;
    } on DioException {
      // INVALID_REFRESH (401, dead/revoked/reused token), CAPS_UNAVAILABLE (503), a network
      // failure — every case is "could not refresh", never a partial success to half-trust.
      return false;
    }
  }

  Future<void> _forceLogout(DioException err, ErrorInterceptorHandler handler) async {
    await _secureStorage.clearTokens();
    if (!_hasForceLoggedOut) {
      _hasForceLoggedOut = true;
      onForceLogout?.call();
    }
    handler.next(err);
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
