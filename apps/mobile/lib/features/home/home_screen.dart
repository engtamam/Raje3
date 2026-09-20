import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/nav/nav_sections.g.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/providers/nav_provider.dart';
import 'package:raje3_mobile/core/providers/theme_provider.dart';
import 'package:raje3_mobile/core/utils/snackbar_helper.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';

/// THE FIXED LAUNCHER — always the landing screen (see app_router.dart), one of the shell's
/// 4 fixed bottom-bar tabs. NEW in this pass: the app's philosophy changed from "the bottom bar
/// mirrors your catalogue" to "the bottom bar is fixed chrome, this screen is the launcher" —
/// see NavProvider's own doc comment for the full reasoning and the case studies it cites
/// (WeChat, Grab, Careem).
///
/// Top bar (this screen only, per the owner's own instruction): shop name, theme toggle,
/// support, notifications. NOT SHOWN: an employee name or a shop logo — neither exists as a
/// real field in this app's models or its signup/signin doors today (see AccountScreen's own
/// doc comment for the same gap) — faking either would be placeholder drift.
class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final isDark = context.isDark;
    final surface0 = isDark ? AppDarkColors.surface0 : AppColors.surface0;
    final nav = context.watch<NavProvider>();

    return Scaffold(
      backgroundColor: surface0,
      body: SafeArea(
        child: Column(
          children: [
            _TopBar(),
            Expanded(
              child: nav.isLoading
                  ? const AppLoadingIndicator()
                  : _LauncherGrid(sections: nav.visibleSections),
            ),
          ],
        ),
      ),
    );
  }
}

class _TopBar extends StatelessWidget {
  static NavSectionDef? get _supportSection {
    for (final section in kNavSections) {
      if (section.id == 'support') return section;
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final colors = context.appColors;
    final isDark = context.isDark;
    final accent = isDark ? AppDarkColors.accent : AppColors.accent;
    final user = context.watch<AuthProvider>().user;
    final themeProvider = context.watch<ThemeProvider>();

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.sm),
      child: Row(
        children: [
          CircleAvatar(
            radius: 20,
            backgroundColor: isDark ? AppDarkColors.accentSoft : AppColors.accentSoft,
            child: Icon(Icons.storefront_rounded, color: accent, size: 20),
          ),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Text(
              user?.fullName ?? '—',
              style: AppTextStyles.labelMedium.copyWith(
                color: colors.textPrimary,
                fontWeight: FontWeight.w700,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          IconButton(
            tooltip: themeProvider.isDark ? s.themeLightMode : s.themeDarkMode,
            onPressed: themeProvider.toggle,
            icon: Icon(
              themeProvider.isDark ? Icons.light_mode_rounded : Icons.dark_mode_rounded,
              color: colors.textSecondary,
            ),
          ),
          IconButton(
            tooltip: _supportSection?.label,
            onPressed: _supportSection == null ? null : () => context.go(_supportSection!.path),
            icon: Icon(Icons.support_agent_rounded, color: colors.textSecondary),
          ),
          IconButton(
            tooltip: s.notificationsUnavailable,
            onPressed: () => SnackbarHelper.showInfo(context, s.notificationsUnavailable),
            icon: Icon(Icons.notifications_outlined, color: colors.textSecondary),
          ),
        ],
      ),
    );
  }
}

class _LauncherGrid extends StatelessWidget {
  final List<NavSectionDef> sections;
  const _LauncherGrid({required this.sections});

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    if (sections.isEmpty) {
      return EmptyState(
        icon: Icons.apps_outlined,
        title: s.homeLauncherEmptyTitle,
        message: s.homeLauncherEmptyMessage,
      );
    }

    final isDark = context.isDark;
    final accent = isDark ? AppDarkColors.accent : AppColors.accent;
    final colors = context.appColors;

    return GridView.builder(
      padding: const EdgeInsets.all(AppSpacing.md),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 3,
        mainAxisSpacing: AppSpacing.md,
        crossAxisSpacing: AppSpacing.md,
        childAspectRatio: 0.85,
      ),
      itemCount: sections.length,
      itemBuilder: (context, index) {
        final section = sections[index];
        return AppCard(
          onTap: () => context.go(section.path),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: isDark ? AppDarkColors.accentSoft : AppColors.accentSoft,
                  borderRadius: AppRadius.standardRadius,
                ),
                child: Icon(section.icon, color: accent, size: 22),
              ),
              const SizedBox(height: AppSpacing.sm),
              Text(
                section.label,
                style: AppTextStyles.bodySmall.copyWith(color: colors.textPrimary),
                textAlign: TextAlign.center,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        );
      },
    );
  }
}
