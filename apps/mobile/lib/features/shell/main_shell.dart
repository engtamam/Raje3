import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/providers/nav_provider.dart';
import 'package:raje3_mobile/core/router/route_names.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/theme/app_theme.dart';

/// THE FIXED BOTTOM BAR — 4 anchors that never change, plus one customizable slot. Replaces an
/// earlier pass's catalogue-driven bar (up to 4 pinned sections + a "More" overflow tab) after
/// the owner changed the underlying philosophy: a bottom bar that lists installed "apps" reads
/// as an app list, not a navigation bar. Every super-app case study researched for this pass
/// (WeChat, Grab, Careem) keeps its bar to a handful of FIXED anchors and surfaces the actual
/// services from the home screen's own launcher grid ([HomeScreen]) and a dedicated apps screen
/// ([AppsScreen], "تطبيقاتي") instead. See NavProvider's own doc comment for the full reasoning.
///
/// Order (right to left in an RTL layout — see MainShell's own destinations list, which is
/// built left-to-right and rendered mirrored by the framework): تطبيقاتي, التحليلات, الرئيسية
/// (centre), حسابي, and the one customizable slot (default: تسجيل زيارة).
class MainShell extends StatelessWidget {
  final Widget child;
  const MainShell({super.key, required this.child});

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final nav = context.watch<NavProvider>();
    final surface0 = context.isDark ? AppDarkColors.surface0 : AppColors.surface0;

    final customSlot = nav.customSlotSection;
    final destinations = <_Destination>[
      _Destination(path: RouteNames.appsPath, label: s.navAppsLabel, icon: Icons.apps_rounded),
      _Destination(
          path: RouteNames.analyticsPath, label: s.navAnalyticsLabel, icon: Icons.trending_up),
      _Destination(path: RouteNames.homePath, label: s.navHomeLabel, icon: Icons.home_rounded),
      _Destination(
          path: RouteNames.accountPath, label: s.navAccountLabel, icon: Icons.person_rounded),
      if (customSlot != null)
        _Destination(path: customSlot.path, label: customSlot.label, icon: customSlot.icon),
    ];

    final currentPath = GoRouterState.of(context).uri.path;
    var selectedIndex = destinations.indexWhere((d) => d.path == currentPath);
    if (selectedIndex < 0) selectedIndex = 2; // home

    return Scaffold(
      backgroundColor: surface0,
      body: child,
      bottomNavigationBar: NavigationBar(
        selectedIndex: selectedIndex,
        onDestinationSelected: (index) => context.go(destinations[index].path),
        destinations: [
          for (final dest in destinations)
            NavigationDestination(icon: Icon(dest.icon), label: dest.label),
        ],
      ),
    );
  }
}

class _Destination {
  final String path;
  final String label;
  final IconData icon;

  const _Destination({required this.path, required this.label, required this.icon});
}
