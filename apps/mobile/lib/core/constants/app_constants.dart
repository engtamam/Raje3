import 'package:raje3_mobile/core/config/app_config.dart';

/// Application-wide constants: storage keys, limits, and regional defaults.
///
/// Region-specific values (currency, VAT) default to Saudi Arabia but can
/// be overridden at runtime via [loadRegionConfig].
class AppConstants {
  // ── App Identity ───────────────────────────────────────────────────────

  /// English app display name.
  static const String appName = AppConfig.appInfoNameEn;

  /// Arabic app display name.
  static const String appNameAr = AppConfig.appInfoNameAr;

  // ── Secure & Local Storage Keys ────────────────────────────────────────

  /// JWT access token (stored in secure storage).
  static const String accessTokenKey = 'access_token';

  /// JWT refresh token (stored in secure storage; currently unused).
  static const String refreshTokenKey = 'refresh_token';

  /// Token expiry timestamp (stored in secure storage).
  static const String tokenExpiryKey = 'token_expiry';

  /// Serialized user profile JSON (stored in secure storage).
  static const String userDataKey = 'user_data';

  /// The signed-in account's tenant id (stored in secure storage). Phone-based
  /// auth resolves to exactly one tenant per phone number — see
  /// services/operations/app/core/signup.py's own note on why its phone index
  /// holds one tenant per number, never a list. Set on login/signup, read on
  /// app start so [ContextInterceptor] can scope every request immediately.
  static const String tenantIdKey = 'tenant_id';

  /// Currently selected context ID (local storage).
  static const String activeContextKey = 'active_context';

  /// User's preferred locale: 'ar' or 'en' (local storage).
  static const String localeKey = 'locale';

  /// User's preferred theme mode: 'light' or 'dark' (local storage).
  static const String themeModeKey = 'theme_mode';

  /// Whether the user has completed onboarding (local storage).
  static const String onboardingCompleteKey = 'onboarding_complete';

  /// Flag indicating phone verification is pending after registration.
  static const String pendingPhoneVerifyKey = 'pending_phone_verify';

  /// Timestamp of last background data sync (local storage).
  static const String lastSyncKey = 'last_sync';

  /// The operator's own choice for the bottom bar's one customizable slot —
  /// a [NavSectionDef.id] (see nav_sections.g.dart). Defaults to 'visit'
  /// when unset; stored per-device (local storage), not per-account, since
  /// there is no backend field for a single-slot preference — see
  /// NavProvider's own doc comment.
  static const String customNavSlotKey = 'custom_nav_slot';

  /// The floating AI mic button's last dragged position (local storage) —
  /// stored as fractions of the screen width/height (0.0–1.0) so it still
  /// lands somewhere on-screen after a rotation or a different device.
  static const String micButtonPositionKey = 'mic_button_position';

  // NOTE: the reference project also kept keys here for its own streak-card
  // display settings and BLE/WiFi device pairing — those are product
  // features (gamification, hardware scanners), not reusable storage
  // infrastructure, so they are not ported.

  // ── Pagination ─────────────────────────────────────────────────────────

  /// Default number of items per page in list endpoints.
  static const int defaultPageSize = AppConfig.businessRulesDefaultPageSize;

  /// Maximum allowed page size.
  static const int maxPageSize = AppConfig.businessRulesMaxPageSize;

  // ── Upload Limits ──────────────────────────────────────────────────────

  /// Maximum size per image upload in megabytes.
  static const int maxImageSizeMB = AppConfig.businessRulesMaxImageSizeMB;

  // ── OTP ────────────────────────────────────────────────────────────────

  /// Number of digits in a one-time password.
  static const int otpLength = 6;

  /// Cooldown in seconds before the user can request a new OTP.
  static const int otpResendSeconds = 60;

  // ── Currency & Region (mutable — loaded from API) ──────────────────────

  /// ISO 4217 currency code (default: Saudi Riyal).
  static String currency = 'SAR';

  /// Localized currency symbol for display.
  static String currencyAr = 'ر.س';

  /// VAT rate as a decimal (0.15 = 15%). Used in price calculations.
  static double vatRate = 0.15;

  /// Override regional defaults with values from the server config.
  ///
  /// Called after login or at app startup. Expects keys:
  /// `currency`, `currency_symbol`, `tax_rate` (percentage, e.g. 15).
  static void loadRegionConfig(Map<String, dynamic> config) {
    currency = config['currency'] as String? ?? 'SAR';
    currencyAr = config['currency_symbol'] as String? ?? 'ر.س';
    final taxRate = config['tax_rate'];
    if (taxRate != null) {
      vatRate = (taxRate is num) ? taxRate.toDouble() / 100 : 0.15;
    }
  }

  // ── Animation Durations ────────────────────────────────────────────────

  /// How long the splash screen stays visible (milliseconds).
  static const int splashDurationMs = AppConfig.uiSplashDurationMs;

  /// Default page transition animation duration (milliseconds).
  static const int pageTransitionMs = AppConfig.uiPageTransitionMs;
}
