import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/providers/nav_provider.dart';
import 'package:raje3_mobile/theme/app_theme.dart';

/// The app's own bottom navigation bar — built from whatever the session's real catalogue makes
/// visible, in [kNavSections]'s own priority order. This is deliberately the ONLY nav shell in
/// the app right now: the earlier fixed-5-slot bar (home/apps/account/analytics) was deleted
/// with those same screens (owner's own instruction, 2026-09-20 — nothing half-finished stays
/// half-finished, it gets rebuilt for real, one screen at a time), not patched to point at
/// placeholders.
///
/// A session with 0 or 1 visible section gets no bottom bar at all — a bar with one destination
/// (or none) is not a navigation control, it is decoration that invites a confused tap.
class MainShell extends StatelessWidget {
  final Widget child;
  const MainShell({super.key, required this.child});

  @override
  Widget build(BuildContext context) {
    final nav = context.watch<NavProvider>();
    final visible = nav.visibleSections;

    if (visible.length < 2) {
      return Scaffold(backgroundColor: AppColors.surface0, body: child);
    }

    final currentPath = GoRouterState.of(context).uri.path;
    var selectedIndex = visible.indexWhere((s) => s.path == currentPath);
    if (selectedIndex < 0) selectedIndex = 0;

    return Scaffold(
      backgroundColor: AppColors.surface0,
      body: child,
      bottomNavigationBar: NavigationBar(
        selectedIndex: selectedIndex,
        onDestinationSelected: (index) => context.go(visible[index].path),
        destinations: [
          for (final section in visible)
            NavigationDestination(icon: Icon(section.icon), label: section.label),
        ],
      ),
    );
  }
}
