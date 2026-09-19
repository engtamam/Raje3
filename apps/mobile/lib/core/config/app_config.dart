// =============================================================================
// AppConfig — Central Configuration Registry
// =============================================================================
//
// PURPOSE
// -------
// Single source of truth for every hardcoded value in the app.
// Think of this as the mobile equivalent of a backend .env file.
//
// RULES
// -----
// 1. Every magic number or string constant that affects app behavior lives here.
// 2. All values are `static const` — compile-time, immutable, zero runtime cost.
// 3. Runtime overrides (from backend via AppConfigService) are handled separately
//    and fall back to these defaults when the server is unreachable.
// 4. When you change a value here, it changes everywhere automatically.
//    You never need to grep for a magic number again.
//
// HOW TO USE
// ----------
// Import this file and reference the section you need:
//
//   import 'package:raje3_mobile/core/config/app_config.dart';
//
//   final timeout = Duration(milliseconds: AppConfig.apiConnectTimeoutMs);
//
// PHASES
// ------
// PORTED FROM the reference project's `lib/core/config/app_config.dart`
// (hair-analysis-platform/mobile-app) — that file's "phase" doc-comment
// registry pattern is kept, but ONLY the phases that are genuinely
// reusable infrastructure are carried over (network, auth, cache,
// pagination, UI behaviour, app info). Their Phase 3 (BLE/WiFi device
// pairing), Phase 4 (on-device TFLite/YOLO AI), Phase 5 (scan sessions)
// and the FCM-token part of Phase 9 were that product's own domain and
// are intentionally NOT ported — add Raje3's own phases here as its
// features land, following this same shape.
//   Phase 1 — Network & API
//   Phase 2 — Auth & Sessions
//   Phase 6 — Cache & Storage
//   Phase 7 — Business Rules (pagination only — scan/cart caps dropped)
//   Phase 8 — UI Behavior
//   Phase 10 — App Info
//
// =============================================================================

// ignore_for_file: avoid_classes_with_only_static_members

class AppConfig {
  // ===========================================================================
  // PHASE 1 — NETWORK & API
  // ===========================================================================
  //
  // Source files audited:
  //   • lib/core/constants/api_constants.dart   (primary — all values live here)
  //   • lib/core/network/api_client.dart        (consumer — passes these to Dio)
  //
  // Architecture note:
  //   This is a THIN SHELL app — every call hits our own server directly, no
  //   offline queue or local cache of server data. ApiClient reads these
  //   constants for a plain REST client (see api_client.dart's own doc
  //   comment for why this is REST, not the reference project's "unified
  //   execute endpoint" pattern).
  // ---------------------------------------------------------------------------

  /// API version segment used in every endpoint URL.
  static const String apiVersion = 'v1';

  /// Client type header value sent with every request.
  static const String apiClientType = 'mobile';

  // ── Timeouts ───────────────────────────────────────────────────────────────
  //
  // All timeouts are in MILLISECONDS to match Dio's BaseOptions API.

  /// TCP connection timeout — how long to wait for the server to accept the
  /// socket before giving up and throwing ApiTimeoutException.
  static const int apiConnectTimeoutMs = 15000;

  /// Response receive timeout — how long to wait for the server to send the
  /// full response body after the connection is established.
  static const int apiReceiveTimeoutMs = 30000;

  /// Extended upload timeout — used for file upload requests.
  static const int apiUploadTimeoutMs = 60000;

  // ── HTTP Headers ───────────────────────────────────────────────────────────

  /// Authorization header name. Value is set to 'Bearer {token}'.
  static const String apiAuthHeader = 'Authorization';

  /// Content-Type header name.
  static const String apiContentTypeHeader = 'Content-Type';

  /// Accept-Language header name. Value is set by LanguageInterceptor
  /// based on the user's locale preference.
  static const String apiAcceptLanguageHeader = 'Accept-Language';

  /// Custom header that identifies the client type to the backend router.
  static const String apiClientTypeHeader = 'X-Client-Type';

  // ── HTTP Status codes of interest ─────────────────────────────────────────
  //
  // Listed here for documentation — the actual switch/case is in
  // api_client.dart._handleResponseError(). If the backend adds a new
  // error code that needs special handling, add it here for visibility.

  /// 401 Unauthorized — session token expired or invalid.
  static const int httpUnauthorized = 401;

  /// 403 Forbidden — valid session but insufficient permissions.
  static const int httpForbidden = 403;

  /// 422 Unprocessable Entity — validation error from the backend.
  static const int httpValidationError = 422;

  /// 429 Too Many Requests — rate limit exceeded.
  static const int httpRateLimit = 429;

  /// 503 Service Unavailable — maintenance mode.
  static const int httpMaintenance = 503;

  // ===========================================================================
  // PHASE 2 — AUTH & SESSIONS
  // ===========================================================================
  //
  // Source files audited:
  //   • lib/core/services/auth_service.dart      (login, OTP, register, logout)
  //   • lib/core/providers/auth_provider.dart    (state machine, force-logout wiring)
  //   • lib/core/storage/secure_storage.dart     (token read/write, expiry check)
  //   • lib/core/network/api_interceptors.dart   (AuthInterceptor — 401 handling)
  //
  // Architecture note:
  //   SESSION-BASED auth — the backend returns a session_id (UUID) stored and
  //   sent as a Bearer token. There is NO refresh token flow. On 401:
  //   AuthInterceptor checks if the local token changed (stale request),
  //   retries once with the current token, then calls forceLogout if it fails.
  // ---------------------------------------------------------------------------

  /// How many seconds BEFORE actual token expiry the app treats the token
  /// as already expired and forces a fresh login. Prevents a race where the
  /// token expires between the local check and the server receiving the request.
  static const int authTokenExpiryBufferSec = 30;

  /// Number of digits in an OTP code.
  static const int authOtpDigits = 6;

  /// Seconds the user must wait before requesting a new OTP.
  static const int authOtpResendCooldownSec = 60;

  // ===========================================================================
  // PHASE 6 — CACHE & STORAGE
  // ===========================================================================
  //
  // Source files audited:
  //   • lib/core/storage/cache_manager.dart    (in-memory cache infrastructure)
  //
  // Architecture note:
  //   A single shared CacheManager instance (in-memory, TTL-based) may be used
  //   by future feature services that read cacheable data. This is separate
  //   from local persistence — there is still NO local database in this app.
  // ---------------------------------------------------------------------------

  /// Default TTL for cache.put() calls that don't specify a [duration] (minutes).
  static const int cacheDefaultTtlMin = 5;

  /// Maximum number of entries the in-memory cache will hold before evicting
  /// the oldest entry.
  static const int cacheMaxEntries = 100;

  // ===========================================================================
  // PHASE 7 — BUSINESS RULES
  // ===========================================================================
  //
  // Source files audited:
  //   • lib/core/constants/app_constants.dart  (pagination limits)
  //
  // Architecture note:
  //   Pagination caps prevent accidental huge SQL queries. The reference
  //   project also had scan-count and cart-size caps here — those were its
  //   own product rules and are dropped; Raje3's own business-rule caps (if
  //   any) get added here when the features that need them land.
  // ---------------------------------------------------------------------------

  /// Default number of items per page in list API calls.
  static const int businessRulesDefaultPageSize = 20;

  /// Maximum allowed page size for any list endpoint.
  static const int businessRulesMaxPageSize = 50;

  /// Maximum size in megabytes for a file upload.
  static const int businessRulesMaxImageSizeMB = 10;

  // ===========================================================================
  // PHASE 8 — UI BEHAVIOR
  // ===========================================================================
  //
  // Source files audited:
  //   • lib/core/constants/app_constants.dart  (splash duration, page transition)
  // ---------------------------------------------------------------------------

  /// How long the splash screen stays visible before the app navigates to
  /// the auth/home screen (milliseconds).
  static const int uiSplashDurationMs = 2000;

  /// Duration of the default page transition animation (milliseconds).
  static const int uiPageTransitionMs = 300;

  // ===========================================================================
  // PHASE 10 — APP INFO
  // ===========================================================================
  //
  // Source files audited:
  //   • lib/core/constants/app_constants.dart  (appName, appNameAr)
  //
  // Architecture note:
  //   These are CLIENT-SIDE FALLBACKS for the app's own identity — Raje3's
  //   real name/description, not the reference product's.
  // ---------------------------------------------------------------------------

  /// Default English display name of the app.
  static const String appInfoNameEn = 'Raje3';

  /// Default Arabic display name of the app.
  static const String appInfoNameAr = 'راجِع';

  /// Default version string used when the server has not yet returned AppInfo.
  static const String appInfoVersionDefault = '0.1.0';

  /// Default copyright year shown in the About screen.
  static const String appInfoCopyrightYear = '2026';
}
