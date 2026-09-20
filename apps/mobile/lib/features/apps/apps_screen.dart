import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/nav/nav_sections.g.dart';
import 'package:raje3_mobile/core/providers/nav_provider.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';

/// "تطبيقاتي" — every section this session's catalogue makes visible, plus the picker for
/// the bottom bar's one customizable slot (see NavProvider's own doc comment for why the bar
/// no longer follows the catalogue directly).
class AppsScreen extends StatelessWidget {
  const AppsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final colors = context.appColors;
    final isDark = context.isDark;
    final surface0 = isDark ? AppDarkColors.surface0 : AppColors.surface0;
    final accent = isDark ? AppDarkColors.accent : AppColors.accent;
    final nav = context.watch<NavProvider>();
    final sections = nav.visibleSections;

    return Scaffold(
      backgroundColor: surface0,
      appBar: AppBar(title: Text(s.appsScreenTitle)),
      body: sections.isEmpty
          ? EmptyState(
              icon: Icons.apps_outlined,
              title: s.homeLauncherEmptyTitle,
              message: s.homeLauncherEmptyMessage,
            )
          : ListView(
              padding: const EdgeInsets.all(AppSpacing.md),
              children: [
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xs),
                  child: Text(
                    s.appsScreenHint,
                    style: AppTextStyles.bodySmall.copyWith(color: colors.textSecondary),
                  ),
                ),
                const SizedBox(height: AppSpacing.md),
                for (final section in sections) ...[
                  _AppRow(
                    section: section,
                    isPinned: section.id == nav.customSlotId,
                    accent: accent,
                    onOpen: () => context.go(section.path),
                    onPin: () => nav.setCustomSlot(section.id),
                  ),
                  const SizedBox(height: AppSpacing.sm),
                ],
              ],
            ),
    );
  }
}

class _AppRow extends StatelessWidget {
  final NavSectionDef section;
  final bool isPinned;
  final Color accent;
  final VoidCallback onOpen;
  final VoidCallback onPin;

  const _AppRow({
    required this.section,
    required this.isPinned,
    required this.accent,
    required this.onOpen,
    required this.onPin,
  });

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final colors = context.appColors;
    final isDark = context.isDark;

    return AppCard(
      onTap: onOpen,
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: isDark ? AppDarkColors.accentSoft : AppColors.accentSoft,
              borderRadius: AppRadius.standardRadius,
            ),
            child: Icon(section.icon, color: accent, size: 20),
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  section.label,
                  style: AppTextStyles.labelMedium.copyWith(color: colors.textPrimary),
                ),
                if (isPinned) ...[
                  const SizedBox(height: 2),
                  Text(
                    s.appsPinnedBadge,
                    style: AppTextStyles.caption.copyWith(color: accent),
                  ),
                ],
              ],
            ),
          ),
          IconButton(
            tooltip: isPinned ? s.appsPinnedBadge : s.appsPinAction,
            onPressed: isPinned ? null : onPin,
            icon: Icon(
              isPinned ? Icons.push_pin_rounded : Icons.push_pin_outlined,
              color: isPinned ? accent : colors.textMuted,
            ),
          ),
        ],
      ),
    );
  }
}
