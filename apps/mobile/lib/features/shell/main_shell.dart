import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/nav/nav_sections.g.dart';
import 'package:raje3_mobile/core/providers/nav_provider.dart';
import 'package:raje3_mobile/theme/app_theme.dart';

/// The app's personalised bottom navigation bar.
///
/// Shows up to [kMaxPinnedNav] of the operator's own pinned sections. When the catalogue makes
/// more sections visible than fit in the bar, a trailing "More" tab opens [MoreSectionsScreen]
/// listing the rest. A session with 0 or 1 visible section gets no bottom bar at all — a bare
/// [Scaffold] around [child], never a broken/empty tab strip.
///
/// This does NOT use go_router's StatefulShellRoute — the section list is only known after the
/// catalogue loads (async, per-session), so the tab set cannot be declared at router-build time
/// the way the placeholder single-tab shell was. Instead this wraps whatever screen the router
/// already navigated to, and tab taps just `context.go` to that section's real path — simpler,
/// and correct for a bar whose contents change per operator and per session.
class MainShell extends StatelessWidget {
  final Widget child;
  const MainShell({super.key, required this.child});

  @override
  Widget build(BuildContext context) {
    final nav = context.watch<NavProvider>();
    final pinned = nav.pinnedSections;
    final hasOverflow = nav.overflowSections.isNotEmpty;

    // 0 or 1 visible section: no chrome at all — a bar with one destination (or none) is not a
    // navigation control, it is decoration that invites a confused tap.
    if (pinned.length + (hasOverflow ? 1 : 0) < 2) {
      return Scaffold(backgroundColor: AppColors.surface0, body: child);
    }

    final currentPath = GoRouterState.of(context).uri.path;
    final destinations = <_Destination>[
      for (final section in pinned) _Destination.section(section),
      if (hasOverflow) const _Destination.more(),
    ];
    var selectedIndex = destinations.indexWhere((d) => d.path == currentPath);
    if (selectedIndex < 0) selectedIndex = 0;

    return Scaffold(
      backgroundColor: AppColors.surface0,
      body: child,
      bottomNavigationBar: NavigationBar(
        selectedIndex: selectedIndex,
        onDestinationSelected: (index) {
          final dest = destinations[index];
          if (dest.isMore) {
            Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const MoreSectionsScreen()),
            );
            return;
          }
          context.go(dest.path);
        },
        destinations: [
          for (final dest in destinations)
            NavigationDestination(
              icon: Icon(dest.icon),
              label: dest.label,
            ),
        ],
      ),
    );
  }
}

class _Destination {
  final String path;
  final String label;
  final IconData icon;
  final bool isMore;

  const _Destination({
    required this.path,
    required this.label,
    required this.icon,
    this.isMore = false,
  });

  factory _Destination.section(NavSectionDef section) => _Destination(
        path: section.path,
        label: section.label,
        icon: section.icon,
      );

  const _Destination.more()
      : path = '__more__',
        label = 'المزيد',
        icon = Icons.more_horiz;
}

/// The rest of the operator's visible sections — a plain tappable list, opened from the "More"
/// tab. Navigates via the same real routes as the bottom bar itself.
class MoreSectionsScreen extends StatelessWidget {
  const MoreSectionsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final sections = context.watch<NavProvider>().overflowSections;
    return Scaffold(
      backgroundColor: AppColors.surface0,
      appBar: AppBar(title: const Text('المزيد')),
      body: ListView.separated(
        itemCount: sections.length,
        separatorBuilder: (_, __) => const Divider(height: 1),
        itemBuilder: (context, index) {
          final section = sections[index];
          return ListTile(
            leading: Icon(section.icon, color: AppColors.accent),
            title: Text(section.label, style: AppTextStyles.bodyMedium),
            trailing: const Icon(Icons.chevron_right),
            onTap: () {
              Navigator.of(context).pop();
              context.go(section.path);
            },
          );
        },
      ),
    );
  }
}
