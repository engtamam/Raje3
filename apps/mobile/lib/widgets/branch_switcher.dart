import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'package:raje3_mobile/core/providers/branch_provider.dart';
import 'package:raje3_mobile/core/services/auth_service.dart' show Branch;
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';

/// «الفرع الحالي» — the real, app-wide equivalent of the console's own top-bar switcher (every
/// read the operator makes there narrows to whichever branch is selected). A glass chip worn on
/// the home hero, never a fixed top bar of its own — this app has no persistent app bar across
/// screens, so the chip lives where the operator already looks first, and every branch-scoped
/// screen reads [BranchProvider] rather than growing its own picker.
///
/// INVISIBLE FOR A SINGLE-BRANCH SHOP, ALWAYS — [BranchProvider.hasChoice] is false the moment
/// there is nothing to switch between, and a chip that opens a sheet with one disabled row would
/// be furniture on the busiest screen in the app.
class BranchChip extends StatelessWidget {
  const BranchChip({super.key});

  @override
  Widget build(BuildContext context) {
    final branchProvider = context.watch<BranchProvider>();
    if (!branchProvider.hasChoice) return const SizedBox.shrink();
    final s = S.of(context)!;
    final selected = branchProvider.selected;
    return KbAnchor(
      id: 'home.branch_switcher',
      child: Material(
        color: Colors.white.withValues(alpha: 0.16),
        borderRadius: BorderRadius.circular(AppRadius.pill),
        child: InkWell(
          borderRadius: BorderRadius.circular(AppRadius.pill),
          onTap: () => _openSwitcher(context),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.storefront_rounded, size: 15, color: Colors.white),
                const SizedBox(width: 6),
                ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 120),
                  child: Text(
                    selected?.name ?? s.branchSwitcherChooseBranch,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppTextStyles.caption
                        .copyWith(color: Colors.white, fontWeight: FontWeight.w700),
                  ),
                ),
                const SizedBox(width: 4),
                const Icon(Icons.expand_more_rounded, size: 16, color: Colors.white),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _openSwitcher(BuildContext context) async {
    final branchProvider = context.read<BranchProvider>();
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (sheetContext) => _BranchSheet(provider: branchProvider),
    );
  }
}

class _BranchSheet extends StatelessWidget {
  const _BranchSheet({required this.provider});
  final BranchProvider provider;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    return AnimatedBuilder(
      animation: provider,
      builder: (context, _) {
        final branches = provider.branches;
        return Padding(
          padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
          child: Container(
            constraints: BoxConstraints(maxHeight: MediaQuery.sizeOf(context).height * 0.7),
            padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.lg, AppSpacing.lg, AppSpacing.xl),
            decoration: const BoxDecoration(
              color: AppColors.surface1,
              borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(s.branchSwitcherTitle, style: AppTextStyles.headlineSmall),
                const SizedBox(height: 4),
                Text(s.branchSwitcherHint,
                    style: AppTextStyles.bodySmall.copyWith(color: AppColors.textMuted)),
                const SizedBox(height: AppSpacing.lg),
                Flexible(
                  child: ListView.separated(
                    shrinkWrap: true,
                    itemCount: branches.length,
                    separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.xs),
                    itemBuilder: (context, i) => _BranchRow(
                      branch: branches[i],
                      selected: branches[i].id == provider.selectedId,
                      onTap: () {
                        provider.select(branches[i].id);
                        Navigator.of(context).pop();
                      },
                    ),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _BranchRow extends StatelessWidget {
  const _BranchRow({required this.branch, required this.selected, required this.onTap});
  final Branch branch;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final dark = context.isDark;
    final accent = dark ? AppDarkColors.accent : AppColors.accent;
    return Material(
      color: selected ? accent.withValues(alpha: 0.10) : Colors.transparent,
      borderRadius: AppRadius.standardRadius,
      child: InkWell(
        onTap: onTap,
        borderRadius: AppRadius.standardRadius,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.sm),
          child: Row(
            children: [
              Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(
                  color: selected ? accent : context.appColors.surfaceAlt,
                  borderRadius: BorderRadius.circular(AppRadius.sm),
                ),
                child: Icon(
                  branch.isMain ? Icons.star_rounded : Icons.storefront_rounded,
                  size: 18,
                  color: selected ? Colors.white : context.appColors.textSecondary,
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(branch.name,
                        style: AppTextStyles.bodyMedium.copyWith(
                            fontWeight: selected ? FontWeight.w800 : FontWeight.w600,
                            color: selected ? accent : context.appColors.textPrimary)),
                    if (branch.city.isNotEmpty)
                      Text(branch.city,
                          style: AppTextStyles.caption.copyWith(color: context.appColors.textMuted)),
                  ],
                ),
              ),
              if (selected) Icon(Icons.check_circle_rounded, color: accent, size: 20),
            ],
          ),
        ),
      ),
    );
  }
}
