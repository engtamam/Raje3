import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:raje3_mobile/core/nav/nav_sections.g.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/providers/nav_provider.dart';
import 'package:raje3_mobile/core/router/route_names.dart';
import 'package:raje3_mobile/features/account/account_screen.dart';
import 'package:raje3_mobile/features/analytics/analytics_screen.dart';
import 'package:raje3_mobile/features/apps/apps_screen.dart';
import 'package:raje3_mobile/features/auth/login_screen.dart';
import 'package:raje3_mobile/features/auth/signup_screen.dart';
import 'package:raje3_mobile/features/home/home_screen.dart';
import 'package:raje3_mobile/features/shell/main_shell.dart';
import 'package:raje3_mobile/features/visit/visit_screen.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/theme/app_theme.dart';

/// App router configuration.
///
/// THE LANDING SCREEN IS ALWAYS [RouteNames.homePath] — the fixed launcher, one of the shell's
/// 4 fixed bottom-bar tabs. An earlier pass landed on [NavProvider]'s first-visible-section
/// instead (mirroring apps/console/src/nav.ts's own «تسجيل زيارة lands first» comment); that
/// dynamic-landing idea was tied to the dynamic bottom bar the owner replaced — see
/// NavProvider's own doc comment. The launcher screen itself still reads the catalogue to build
/// its grid, so nothing about WHICH sections are reachable changed, only where you land.
///
/// Every [NavSectionDef] still gets a real route below, reachable from the launcher grid or
/// "تطبيقاتي" even when it isn't one of the bar's fixed tabs. Two of them ('shop', 'visit') have
/// real screens; the rest render [_NotYetOnMobile] — an honest "not built here yet" state, not a
/// silent placeholder.
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
            GoRoute(
              path: RouteNames.homePath,
              name: RouteNames.home,
              builder: (context, state) => const HomeScreen(),
            ),
            GoRoute(
              path: RouteNames.appsPath,
              name: RouteNames.apps,
              builder: (context, state) => const AppsScreen(),
            ),
            GoRoute(
              path: RouteNames.accountPath,
              name: RouteNames.account,
              builder: (context, state) => const AccountScreen(),
            ),
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
        return const AnalyticsScreen();
      case 'visit':
        return const VisitScreen();
      default:
        return _NotYetOnMobile(section: section);
    }
  }

  /// Auth guard, extended with the nav guard: once authenticated, a caller sitting on the login
  /// route or on the app's own root is sent to the fixed launcher ([RouteNames.homePath]) —
  /// never a dynamic, catalogue-dependent path (see this file's own header comment on why the
  /// landing screen is fixed now). The catalogue load is still kicked off here so the launcher's
  /// grid and the bar's customizable slot have real data by the time they render.
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

    if (navProvider.state == NavLoadState.initial) {
      // Fire-and-forget: the redirect callback itself must stay synchronous. NavProvider
      // notifying when the load resolves triggers GoRouter to re-evaluate via
      // refreshListenable — the launcher/apps screens re-render with real data once it lands.
      navProvider.load();
    }

    if (isOnAuthPage) {
      return RouteNames.homePath;
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
