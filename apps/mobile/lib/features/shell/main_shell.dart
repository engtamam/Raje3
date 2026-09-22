import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/ai/ai_config.dart';
import 'package:raje3_mobile/core/providers/ai_entitlement_provider.dart';
import 'package:raje3_mobile/core/nav/nav_sections.g.dart';
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
/// built left-to-right and rendered mirrored by the framework): تطبيقاتي, محلّي, الرئيسية
/// (centre), حسابي, and the one customizable slot (default: تسجيل زيارة).
///
/// «محلّي» is the one fixed slot that is STILL capability-gated — it is the 'shop' nav section
/// (`requires: ['reminders.today', 'insights.dashboard']`) wearing a fixed-tab costume, not a
/// truly universal anchor like الرئيسية/حسابي/تطبيقاتي. An account whose catalogue does not
/// make 'shop' visible (a role with neither capability) never sees the tab at all — showing it
/// and letting AnalyticsScreen fail to load would be worse than omitting it.
///
/// ALWAYS THE SECTION'S OWN LABEL/ICON ([NavSectionDef.label]/[NavSectionDef.icon]), never a
/// second, separately-typed name for this tab — this app used to show it as «التحليلات» here
/// while the SAME section read «محلّي» in the home-screen grid, one feature wearing two names
/// depending which screen the operator happened to be on (FOUND LIVE, the owner's own catch).
class MainShell extends StatelessWidget {
  final Widget child;
  const MainShell({super.key, required this.child});

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final nav = context.watch<NavProvider>();
    final surface0 = context.isDark ? AppDarkColors.surface0 : AppColors.surface0;

    final customSlot = nav.customSlotSection;
    NavSectionDef? shopSection;
    for (final section in nav.visibleSections) {
      if (section.id == 'shop') {
        shopSection = section;
        break;
      }
    }
    final destinations = <_Destination>[
      _Destination(path: RouteNames.appsPath, label: s.navAppsLabel, icon: Icons.apps_rounded),
      if (shopSection != null)
        _Destination(path: shopSection.path, label: shopSection.label, icon: shopSection.icon),
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

    // TWO INDEPENDENT GATES, BOTH MUST PASS. `AiConfig.modelDriver` says the CODE PATH exists in
    // this build (the same fail-closed check buildAiModel() itself uses); `entitlement.subscribed
    // == true` says THIS SHOP actually bought «المساعد الذكي» (a real, subscribe/cancel-able
    // plan now — core/apps.py, priced 0 today). `== true` on purpose, not a bare truthy check:
    // `null` (no confirmed answer yet) must read exactly like `false` here, never like "on".
    final entitlement = context.watch<AiEntitlementProvider>();
    final showMicButton = AiConfig.modelDriver != 'null' && entitlement.subscribed == true;

    final dark = context.isDark;
    final surface1 = dark ? AppDarkColors.surface1 : AppColors.surface1;
    final accent = dark ? AppDarkColors.accent : AppColors.accent;
    final accentSoft = dark ? AppDarkColors.accentSoft : AppColors.accentSoft;
    final muted = dark ? AppDarkColors.textMuted : AppColors.textMuted;

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
      // A REAL ELEVATED BAR, not the platform default flat strip — rounded top corners lift it
      // off the content behind it, and its own shadow (never relying on Material's near-invisible
      // default elevation tint) gives it the same physical weight every primary surface in this
      // app's theme (AppShadows.card) already carries.
      bottomNavigationBar: DecoratedBox(
        decoration: BoxDecoration(
          color: surface1,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
          boxShadow: dark ? AppShadows.darkCard : AppShadows.card,
        ),
        child: ClipRRect(
          borderRadius: const BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
          child: NavigationBarTheme(
            data: NavigationBarThemeData(
              backgroundColor: surface1,
              indicatorColor: accentSoft,
              height: 68,
              labelTextStyle: WidgetStateProperty.resolveWith(
                (states) => AppTextStyles.caption.copyWith(
                  fontWeight: states.contains(WidgetState.selected) ? FontWeight.w700 : FontWeight.w500,
                  color: states.contains(WidgetState.selected) ? accent : muted,
                ),
              ),
            ),
            child: NavigationBar(
              selectedIndex: selectedIndex,
              onDestinationSelected: (index) => context.go(destinations[index].path),
              destinations: [
                for (final dest in destinations)
                  NavigationDestination(
                    icon: Icon(dest.icon, color: muted),
                    selectedIcon: Icon(dest.icon, color: accent),
                    label: dest.label,
                  ),
              ],
            ),
          ),
        ),
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
