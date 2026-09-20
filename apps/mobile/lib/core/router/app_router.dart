import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:raje3_mobile/core/nav/nav_sections.g.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/providers/nav_provider.dart';
import 'package:raje3_mobile/core/router/route_names.dart';
import 'package:raje3_mobile/features/auth/login_screen.dart';
import 'package:raje3_mobile/features/auth/signup_screen.dart';
import 'package:raje3_mobile/features/shell/main_shell.dart';
import 'package:raje3_mobile/features/visit/visit_screen.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/theme/app_theme.dart';

/// App router configuration.
///
/// ONLY ONE REAL SCREEN TODAY: تسجيل زيارة. Every other section this session's catalogue makes
/// visible still gets a real route (below) so a capability change never leaves the app on a
/// blank screen or a router crash — it just renders [_NotYetOnMobile] until its own screen is
/// built. The owner's own instruction (2026-09-20): everything that was not built to a real
/// standard is deleted rather than kept half-finished — home/apps/account/analytics are gone
/// entirely, to be rebuilt one at a time, not patched.
///
/// THE LANDING SCREEN IS [NavProvider.landingPath] — the first section the session's own
/// catalogue makes visible, in [kNavSections]'s priority order (mirrors
/// apps/console/src/nav.ts's own comment: «تسجيل زيارة» lands first because it needs only the
/// one capability most operators hold, not because it is special-cased anywhere).
class AppRouter {
  AppRouter._();

  static final GlobalKey<NavigatorState> _rootNavigatorKey =
      GlobalKey<NavigatorState>(debugLabel: 'root');
  static final GlobalKey<NavigatorState> _shellNavKey =
      GlobalKey(debugLabel: 'shell');

  /// Build the GoRouter instance wired to [authProvider]/[navProvider] for redirect logic.
  static GoRouter router(AuthProvider authProvider, NavProvider navProvider) {
    return GoRouter(
      navigatorKey: _rootNavigatorKey,
      debugLogDiagnostics: true,
      initialLocation: RouteNames.loginPath,
      refreshListenable: Listenable.merge([authProvider, navProvider]),
      redirect: (context, state) => _globalRedirect(authProvider, navProvider, state),
      routes: [
        GoRoute(
          path: RouteNames.loginPath,
          name: RouteNames.login,
          builder: (context, state) => const LoginScreen(),
        ),
        GoRoute(
          path: RouteNames.signupPath,
          name: RouteNames.signup,
          builder: (context, state) => const SignupScreen(),
        ),
        ShellRoute(
          navigatorKey: _shellNavKey,
          builder: (context, state, child) => MainShell(child: child),
          routes: [
            for (final section in kNavSections)
              GoRoute(
                path: section.path,
                name: section.id,
                builder: (context, state) => _screenFor(section),
              ),
          ],
        ),
      ],
    );
  }

  static Widget _screenFor(NavSectionDef section) {
    switch (section.id) {
      case 'visit':
        return const VisitScreen();
      default:
        return _NotYetOnMobile(section: section);
    }
  }

  /// Auth guard, extended with the nav guard: once authenticated, a caller sitting on the login
  /// route or on the app's own root is sent to [NavProvider.landingPath] rather than a fixed
  /// path. While the catalogue is still loading, the caller is held on login (which shows a
  /// spinner via AuthProvider's own loading state) rather than guessing a landing screen ahead
  /// of the data that decides it.
  static String? _globalRedirect(
    AuthProvider authProvider,
    NavProvider navProvider,
    GoRouterState state,
  ) {
    final authState = authProvider.state;
    final currentPath = state.uri.path;
    final isOnAuthPage =
        currentPath == RouteNames.loginPath || currentPath == RouteNames.signupPath;

    if (authState == AuthState.initial || authState == AuthState.loading) {
      return isOnAuthPage ? null : RouteNames.loginPath;
    }

    final isAuthenticated = authState == AuthState.authenticated;
    if (!isAuthenticated) {
      return isOnAuthPage ? null : RouteNames.loginPath;
    }

    if (isOnAuthPage) {
      if (navProvider.state == NavLoadState.initial) {
        // Fire-and-forget: the redirect callback itself must stay synchronous. NavProvider
        // notifying when the load resolves triggers GoRouter to re-evaluate via
        // refreshListenable, landing the user once the real answer is known.
        navProvider.load();
        return null;
      }
      final landing = navProvider.landingPath;
      return landing ?? RouteNames.loginPath;
    }

    return null;
  }
}

/// Honest placeholder for a section the catalogue makes visible but this mobile pass has not
/// built a real screen for yet — never silent, never a router crash, never a fabricated feature.
class _NotYetOnMobile extends StatelessWidget {
  final NavSectionDef section;
  const _NotYetOnMobile({required this.section});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.surface0,
      appBar: AppBar(title: Text(section.label)),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Text(
            S.of(context)!.routerScreenNotOnMobileYet,
            style: AppTextStyles.bodyMedium,
            textAlign: TextAlign.center,
          ),
        ),
      ),
    );
  }
}
