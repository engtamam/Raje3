import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/ai/ai_config.dart';
import 'package:raje3_mobile/core/providers/nav_provider.dart';
import 'package:raje3_mobile/core/router/route_names.dart';
import 'package:raje3_mobile/core/storage/local_storage.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/floating_mic_button.dart';

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
///
/// "التحليلات" is the one fixed slot that is STILL capability-gated — it is really the 'shop'
/// nav section (`requires: ['reminders.today', 'insights.dashboard']`) wearing a fixed-tab
/// costume, not a truly universal anchor like الرئيسية/حسابي/تطبيقاتي. An account whose
/// catalogue does not make 'shop' visible (a role with neither capability) never sees the tab
/// at all — showing it and letting AnalyticsScreen fail to load would be worse than omitting it.
class MainShell extends StatelessWidget {
  final Widget child;
  const MainShell({super.key, required this.child});

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final nav = context.watch<NavProvider>();
    final surface0 = context.isDark ? AppDarkColors.surface0 : AppColors.surface0;

    final customSlot = nav.customSlotSection;
    final hasAnalytics = nav.visibleSections.any((section) => section.id == 'shop');
    final destinations = <_Destination>[
      _Destination(path: RouteNames.appsPath, label: s.navAppsLabel, icon: Icons.apps_rounded),
      if (hasAnalytics)
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
    if (selectedIndex < 0) {
      selectedIndex = destinations.indexWhere((d) => d.path == RouteNames.homePath);
    }
    if (selectedIndex < 0) selectedIndex = 0;

    // ONLY SHOWN WHEN AN AI DRIVER IS ACTUALLY BUILT IN — the same fail-closed check
    // buildAiModel() itself uses, not a separate guessed entitlement. See
    // FloatingMicButton's own doc comment on why this is the caller's job, not the
    // widget's.
    const showMicButton = AiConfig.modelDriver != 'null';

    return Scaffold(
      backgroundColor: surface0,
      body: showMicButton
          ? Stack(
              children: [
                child,
                FloatingMicButton(localStorage: context.read<LocalStorage>()),
              ],
            )
          : child,
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
