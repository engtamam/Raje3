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
  static const String analytics = 'analytics';
  static const String apps = 'apps';
  static const String account = 'account';
  static const String visit = 'visit';
  static const String shopIdentity = 'shop_identity';
  static const String branches = 'branches';
  static const String branchDetail = 'branch_detail';
  static const String billing = 'billing';
  static const String customerDetail = 'customer_detail';
  static const String whatsappAssistant = 'whatsapp_assistant';
  static const String referrals = 'referrals';

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
  /// The fixed launcher screen — always the landing screen once authenticated,
  /// one of the shell's 4 fixed bottom-bar tabs (see MainShell).
  static const String homePath = '/home';
  /// The 'shop' nav section's own dashboard (reminders/insights) — a fixed
  /// bottom-bar tab labelled "التحليلات", not the app's landing screen anymore.
  static const String analyticsPath = '/shop';
  /// "تطبيقاتي" — every section the session's catalogue makes visible, plus
  /// the picker for the bar's one customizable slot.
  static const String appsPath = '/apps';
  static const String accountPath = '/account';
  static const String visitPath = '/visit';
  /// «منشأتي» — pushed FROM «حسابي», never a bottom-bar tab of its own: a settings drill-down, so
  /// it lives OUTSIDE the shell (own back button, no bottom bar), the same "tap a row, land on a
  /// dedicated screen" pattern the account list itself is built around.
  static const String shopIdentityPath = '/account/shop';
  /// «الفروع» — pushed FROM «منشأتي», own back button, no bottom bar. Every branch-scoped fact
  /// (address, واتساب, الفريق) lives under a branch's own detail screen, never «منشأتي» itself —
  /// see shop_identity_screen.dart's own header note on why.
  static const String branchesPath = '/account/shop/branches';
  /// `:branchId` — a specific branch's own detail screen.
  static const String branchDetailPath = '/account/shop/branches/:branchId';
  static String branchDetailPathFor(String branchId) => '/account/shop/branches/$branchId';
  /// «الفوترة» — pushed FROM «حسابي» directly (own section, not nested under «منشأتي»: a
  /// billing fact belongs to the whole account, not one branch or the shop's identity). Own back
  /// button, no bottom bar, same drill-down pattern as every other account sub-screen.
  static const String billingPath = '/account/billing';
  /// `:customerId` — pushed FROM «عملائي», own back button, no bottom bar, same drill-down
  /// pattern as every other detail screen in this app.
  static const String customerDetailPath = '/customers/:customerId';
  static String customerDetailPathFor(String customerId) => '/customers/$customerId';
  /// «المساعد الذكي عبر واتساب» — pushed FROM the app store's own «تطبيقاتي»/«المتجر» row
  /// (`apps_store_screen.dart`'s `AppRow.route`), own back button, no bottom bar — this app has
  /// no `feature.*` nav section of its own, same drill-down pattern as billing.
  static const String whatsappAssistantPath = '/whatsapp-assistant';
  /// «نظام الإحالة» — pushed FROM «تطبيقاتي» (`apps_store_screen.dart`'s `AppRow.route`), same
  /// no-`feature.*`-nav-section pattern the WhatsApp assistant route already uses: this app has
  /// no `feature.*` billing key, it is gated purely by the `referrals.manage` capability instead.
  static const String referralsPath = '/referrals';
}
