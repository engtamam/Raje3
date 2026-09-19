/// Centralized route name and path constants for GoRouter.
///
/// Naming convention (kept from the reference project's own
/// `route_names.dart` — this file is otherwise trimmed to a skeleton
/// since Raje3's own screens aren't ported in this infra-only pass):
///   - Route names (e.g. `home`): used with `goNamed()` / `pushNamed()`
///   - Route paths (e.g. `homePath`): used in GoRoute `path:` definitions
///   - Nested paths are relative (no leading `/`); top-level paths are absolute
///
/// Add Raje3's own routes here as screens land, following this same
/// name/path pairing convention.
class RouteNames {
  RouteNames._();

  // ── ROUTE NAMES ──────────────────────────────────────────────────────────
  static const String login = 'login';
  static const String signup = 'signup';
  static const String verifyPhone = 'verify_phone';
  static const String home = 'home';
  static const String visit = 'visit';

  // ── ROUTE PATHS ───────────────────────────────────────────────────────────
  static const String loginPath = '/login';
  /// Establishment signup — opening a brand-new shop. Distinct from any
  /// future "join an existing shop" screen, which is a different flow
  /// (`hire`/staff invite in services/operations/app/core/signup.py) with no
  /// mobile entry point yet.
  static const String signupPath = '/signup';
  /// Phone verification (OTP), reachable from either door — see
  /// AuthProvider.errorReason for the `unverified`/`otp_required`/
  /// `unverified_hold` reasons that route here.
  static const String verifyPhonePath = '/verify-phone';
  /// Kept as an alias of the 'shop' nav section's own path so a bookmark/deep-link to
  /// `/home` still lands somewhere real. The actual landing screen is decided at runtime by
  /// NavProvider.landingPath, never hardcoded to this constant — see app_router.dart.
  static const String homePath = '/shop';
  static const String visitPath = '/visit';
}
