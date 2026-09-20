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

  // ── ROUTE PATHS ───────────────────────────────────────────────────────────
  static const String loginPath = '/login';
  /// Establishment signup — opening a brand-new shop. Distinct from any
  /// future "join an existing shop" screen, which is a different flow
  /// (`hire`/staff invite in services/operations/app/core/signup.py) with no
  /// mobile entry point yet.
  static const String signupPath = '/signup';
  /// Phone verification (OTP) is pushed directly via MaterialPageRoute from
  /// login/signup (see VerifyPhoneScreen's own callers) — not a GoRouter
  /// route, so it carries no name/path constant here.
  ///
  /// Every other real screen's route comes from `kNavSections` itself
  /// (`section.path`/`section.id`, see app_router.dart) — a section not yet
  /// built on mobile still gets a real, honest placeholder route this way,
  /// with no separate constant needed per screen.
}
