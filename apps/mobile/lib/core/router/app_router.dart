import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:raje3_mobile/core/nav/nav_sections.g.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/providers/nav_provider.dart';
import 'package:raje3_mobile/core/router/route_names.dart';
import 'package:raje3_mobile/features/auth/login_screen.dart';
import 'package:raje3_mobile/features/auth/signup_screen.dart';
import 'package:raje3_mobile/features/home/home_screen.dart';
import 'package:raje3_mobile/features/shell/main_shell.dart';
import 'package:raje3_mobile/features/visit/visit_screen.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/theme/app_theme.dart';

/// App router configuration.
///
/// THE LANDING SCREEN IS NEVER HARDCODED. Earlier passes routed straight to a single `HomeScreen`
/// tab; this pass replaces that with [NavProvider.landingPath] — the first section THIS
/// session's real catalogue makes visible, in the exact priority order of kNavSections (mirrors
/// apps/console/src/nav.ts's own comment: «تسجيل زيارة» lands first because it needs only the
/// one capability most operators hold, not because it is special-cased anywhere).
///
/// Every [NavSectionDef] gets a real route below. Two of them ('shop', 'visit') have real
/// screens in this pass; the rest render [_NotYetOnMobile] — an honest "not built here yet"
/// state, not a silent placeholder, so a catalogue that makes one of them visible/first never
/// leaves the app on a blank screen or a router crash.
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
      case 'shop':
        return const HomeScreen();
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
      body: const Center(
        child: Padding(
          padding: EdgeInsets.all(AppSpacing.md),
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
