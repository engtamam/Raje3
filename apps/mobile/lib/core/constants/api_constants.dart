import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:raje3_mobile/core/config/app_config.dart';

/// API endpoint URLs, timeouts, and header constants.
///
/// Values are sourced from [AppConfig] — the central configuration registry.
/// This file assembles full URLs from AppConfig segments and resolves the
/// environment-specific base URL.
///
/// NOT the "unified execute endpoint" pattern. The reference project this
/// file was adapted from (hair-analysis-platform/mobile-app) routed every
/// call through `POST /api/v1/mobile/execute { module, action, data }`.
/// We deliberately do NOT copy that here — it would require backend changes
/// across our whole services fleet, a decision the owner hasn't made (see
/// the TODO in apps/mobile/README.md). This app instead uses plain REST:
/// [ApiClient] takes a path + method per call, same shape as a normal Dio
/// client. `apiBasePath` is the one shared prefix every endpoint sits under.
///
/// To change a timeout or version: edit AppConfig, not this file.
class ApiConstants {
  /// Compile-time override for the API base URL.
  /// Set via: flutter run --dart-define=API_BASE_URL=https://api.example.com
  ///
  /// EVERY RELEASE BUILD MUST PASS THIS — found live (2026-09-28): neither
  /// scripts/build_apk_direct.sh nor the Play `flutter build appbundle` command passed it for a
  /// while, so [baseUrl] silently fell back to the emulator-only default below on a real,
  /// signed, installable release build. It built, signed, and shipped with no error anywhere —
  /// the failure only shows up as "the app can't reach the server" on an actual phone. Both
  /// build commands now pass `--dart-define=API_BASE_URL=https://kobo-cloud.com`
  /// (scripts/build_apk_direct.sh, ops-mcp's own mobile.build_bundle_command) — if a THIRD one is
  /// ever added, it needs this too.
  static const String _envUrl = String.fromEnvironment('API_BASE_URL');

  /// Resolved base URL — prefers env override, then platform default.
  ///
  /// Android emulator: 10.0.2.2 maps to the host machine's localhost.
  /// iOS simulator / web: localhost:3000.
  /// Production: set API_BASE_URL via --dart-define at build time — see [_envUrl]'s own doc
  /// comment above for why this is not optional.
  static String get baseUrl {
    if (_envUrl.isNotEmpty) return _envUrl;
    if (kIsWeb) return 'http://localhost:3000';
    return 'http://10.0.2.2:3000';
  }

  // Values sourced from AppConfig — edit AppConfig to change them.

  /// API version segment. Source: [AppConfig.apiVersion]
  static const String apiVersion = AppConfig.apiVersion;

  /// Client type header value. Source: [AppConfig.apiClientType]
  static const String clientType = AppConfig.apiClientType;

  // ── Base API path ──────────────────────────────────────────────────────

  /// Shared prefix every REST endpoint sits under, e.g. call
  /// `apiClient.get('/shops/me')` and it resolves to
  /// `{baseUrl}{apiBasePath}/shops/me`.
  static String get apiBasePath => '/api/$apiVersion/$clientType';

  // ── Timeouts (milliseconds) — source: AppConfig ────────────────────────

  /// TCP connection timeout. Source: [AppConfig.apiConnectTimeoutMs]
  static const int connectTimeout = AppConfig.apiConnectTimeoutMs;

  /// Response receive timeout for standard API calls. Source: [AppConfig.apiReceiveTimeoutMs]
  static const int receiveTimeout = AppConfig.apiReceiveTimeoutMs;

  /// Extended timeout for file uploads. Source: [AppConfig.apiUploadTimeoutMs]
  static const int uploadTimeout = AppConfig.apiUploadTimeoutMs;

  // ── HTTP Header Names — source: AppConfig ──────────────────────────────

  /// Bearer token header key. Source: [AppConfig.apiAuthHeader]
  static const String authHeader = AppConfig.apiAuthHeader;

  /// Content-Type header key. Source: [AppConfig.apiContentTypeHeader]
  static const String contentType = AppConfig.apiContentTypeHeader;

  /// Accept-Language header. Source: [AppConfig.apiAcceptLanguageHeader]
  static const String acceptLanguage = AppConfig.apiAcceptLanguageHeader;

  /// Custom header identifying the client type. Source: [AppConfig.apiClientTypeHeader]
  static const String clientTypeHeader = AppConfig.apiClientTypeHeader;
}
