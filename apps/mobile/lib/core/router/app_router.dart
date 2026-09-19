import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/providers/tenant_provider.dart';
import 'package:raje3_mobile/core/router/route_names.dart';

// UI screens are NOT ported in this pass (infra-only pass — see README.md).
// Two throwaway placeholder widgets stand in for splash/home below so the
// router compiles and the auth redirect is exercisable; the real screens
// (and their routes) replace them in the next pass.
import 'package:raje3_mobile/features/auth/login_screen.dart';
import 'package:raje3_mobile/features/home/home_screen.dart';

/// App router configuration.
///
/// PORTED FROM the reference project's `lib/core/router/app_router.dart`
/// (hair-analysis-platform/mobile-app) — this pass keeps ONLY the routing
/// MECHANISM: the global auth redirect ([_globalRedirect], copied verbatim)
/// and the [StatefulShellRoute.indexedStack] tab-shell pattern (kept, but
/// reduced to a single generic tab since Raje3's own screens/tabs don't
/// exist yet). The reference file's 50+ screen imports/routes (hair-scan
/// flows, CRM, device pairing, streak gamification, …) were their product,
/// not infrastructure, and are intentionally NOT carried over — a later
/// pass adds Raje3's own routes here following this same shape.
///
/// Navigation architecture (placeholder — one branch until real screens land):
///   Tab 0: Home
class AppRouter {
  AppRouter._();

  /// Root navigator — used for full-screen routes (auth, detail screens).
  static final GlobalKey<NavigatorState> _rootNavigatorKey =
      GlobalKey<NavigatorState>(debugLabel: 'root');

  // Branch navigator keys — one per tab branch. StatefulShellRoute keeps
  // each branch's widget tree alive across tab switches so screens don't
  // rebuild (and re-fetch) on every tap.
  static final GlobalKey<NavigatorState> _homeNavKey =
      GlobalKey(debugLabel: 'branch-home');

  /// Build the GoRouter instance wired to [authProvider] for redirect logic.
  ///
  /// [refreshListenable] causes GoRouter to re-evaluate redirects whenever
  /// AuthProvider notifies (e.g., login, logout, token expiry).
  static GoRouter router(AuthProvider authProvider) {
    return GoRouter(
      navigatorKey: _rootNavigatorKey,
      debugLogDiagnostics: true,
      initialLocation: RouteNames.loginPath,
      refreshListenable: authProvider,
      redirect: (context, state) => _globalRedirect(authProvider, state),
      routes: [
        // ─────────────────────────────────────────────────────────────────
        // AUTH ROUTES (outside shell, no bottom nav)
        // ─────────────────────────────────────────────────────────────────
        GoRoute(
          path: RouteNames.loginPath,
          name: RouteNames.login,
          builder: (context, state) => const LoginScreen(),
        ),

        // ─────────────────────────────────────────────────────────────────
        // MAIN APP SHELL (bottom navigation tabs)
        // ─────────────────────────────────────────────────────────────────
        StatefulShellRoute.indexedStack(
          builder: (context, state, navigationShell) =>
              _MainShell(navigationShell: navigationShell),
          branches: [
            StatefulShellBranch(
              navigatorKey: _homeNavKey,
              routes: [
                GoRoute(
                  path: RouteNames.homePath,
                  name: RouteNames.home,
                  pageBuilder: (context, state) => const NoTransitionPage(
                    child: HomeScreen(),
                  ),
                ),
              ],
            ),
          ],
        ),
      ],
    );
  }

  /// Global redirect logic — auth guard for all routes.
  ///
  /// COPIED VERBATIM (mechanism only — path constants trimmed to what
  /// this skeleton actually has) from the reference project's own
  /// `_globalRedirect`. Rules:
  ///   - Loading/initial: keep user on splash (or auth page if already there)
  ///   - Unauthenticated: redirect to login (allow auth pages)
  ///   - Authenticated on auth/splash: redirect to home
  ///   - Otherwise: no redirect (null)
  static String? _globalRedirect(
    AuthProvider authProvider,
    GoRouterState state,
  ) {
    final authState = authProvider.state;
    final currentPath = state.uri.path;

    final isOnAuthPage = currentPath == RouteNames.loginPath ||
        currentPath.startsWith(RouteNames.loginPath);

    // No dedicated splash route in this skeleton — login doubles as the
    // "not yet authenticated" resting point while auth state resolves.
    if (authState == AuthState.initial || authState == AuthState.loading) {
      if (isOnAuthPage) return null;
      return RouteNames.loginPath;
    }

    final isAuthenticated = authState == AuthState.authenticated;

    // Not authenticated: redirect to login (allow auth pages)
    if (!isAuthenticated) {
      if (isOnAuthPage) return null;
      return RouteNames.loginPath;
    }

    // Authenticated but on the auth page: redirect to home
    if (isAuthenticated && isOnAuthPage) {
      return RouteNames.homePath;
    }

    return null;
  }
}

/// Main app shell with bottom navigation bar.
///
/// Wraps the [StatefulNavigationShell] produced by [StatefulShellRoute].
/// PATTERN copied from the reference project's `_MainShell` — the
/// context-switch branch-reset behaviour is kept (reacting to
/// [TenantProvider] instead of their business/individual context) so a
/// future multi-branch nav doesn't leave a stale tab visible after a
/// tenant switch.
class _MainShell extends StatefulWidget {
  final StatefulNavigationShell navigationShell;
  const _MainShell({required this.navigationShell});

  @override
  State<_MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<_MainShell> {
  String? _lastTenantId;

  final _messengerKey = GlobalKey<ScaffoldMessengerState>();

  @override
  Widget build(BuildContext context) {
    final tenantId = context.watch<TenantProvider>().activeTenant?.id;

    if (_lastTenantId != null && _lastTenantId != tenantId) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          _messengerKey.currentState?.clearSnackBars();
          widget.navigationShell.goBranch(0);
        }
      });
    }
    _lastTenantId = tenantId;

    return ScaffoldMessenger(
      key: _messengerKey,
      child: Scaffold(
        body: widget.navigationShell,
        bottomNavigationBar: NavigationBar(
          selectedIndex: widget.navigationShell.currentIndex,
          onDestinationSelected: widget.navigationShell.goBranch,
          destinations: const [
            NavigationDestination(
              icon: Icon(Icons.home_outlined),
              selectedIcon: Icon(Icons.home_rounded),
              label: 'Home',
            ),
          ],
        ),
      ),
    );
  }
}
