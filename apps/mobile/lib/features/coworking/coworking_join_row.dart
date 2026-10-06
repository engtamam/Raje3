import 'package:flutter/material.dart';

import 'package:raje3_mobile/models/coworking_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/widgets/capability_gate.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';

/// One join-request row — swipe-right-to-approve, swipe-left-to-reject (real `Dismissible`
/// background gestures, not buttons), with «حظر»/«رفع الحظر» as a separate long-press action —
/// deliberately more final than a swipe, and answerable even when [join].status is not
/// `pending` at all (see `core/joins.py`'s own "block is answerable with no prior row" doc).
class CoworkingJoinRow extends StatelessWidget {
  const CoworkingJoinRow({
    super.key,
    required this.join,
    required this.canManage,
    required this.onApprove,
    required this.onReject,
    required this.onBlock,
    required this.onUnblock,
  });

  final CoworkingJoin join;
  final bool canManage;
  final VoidCallback onApprove;
  final VoidCallback onReject;
  final VoidCallback onBlock;
  final VoidCallback onUnblock;

  String get _statusLabel => switch (join.status) {
        'approved' => 'مقبول',
        'blocked' => 'محظور',
        _ => 'بانتظار الموافقة',
      };

  Color _statusColor(BuildContext context) => switch (join.status) {
        'approved' => AppColors.successOnSoft,
        'blocked' => AppColors.dangerOnSoft,
        _ => AppColors.warningOnSoft,
      };

  Color _statusBg(BuildContext context) => switch (join.status) {
        'approved' => AppColors.successSoft,
        'blocked' => AppColors.dangerSoft,
        _ => AppColors.warningSoft,
      };

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final dark = context.isDark;
    final pending = join.status == 'pending';
    final blocked = join.status == 'blocked';

    final row = Container(
      decoration: BoxDecoration(
        color: colors.surface,
        borderRadius: AppRadius.cardRadius,
        border: Border.all(color: colors.borderSubtle),
        boxShadow: dark ? AppShadows.darkCard : AppShadows.card,
      ),
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(color: colors.surfaceAlt, shape: BoxShape.circle),
            child: Icon(Icons.person_outline_rounded, color: colors.textMuted, size: 20),
          ),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(join.phone, style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w700)),
                Text(_timeAgo(join.createdAt), style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
              ],
            ),
          ),
          AppBadge(text: _statusLabel, backgroundColor: _statusBg(context), textColor: _statusColor(context)),
        ],
      ),
    );

    final gated = CapabilityGate(
      requires: const [
        'coworking.approve_join', 'coworking.reject_join',
        'coworking.block_phone', 'coworking.unblock_phone',
      ],
      child: KbAnchor(
        id: 'coworking.join_row',
        child: GestureDetector(
          onLongPress: () => _showBlockSheet(context, blocked: blocked),
          child: pending
              ? Dismissible(
                  key: ValueKey('join-${join.phone}'),
                  background: _swipeBackground(alignStart: true, color: AppColors.successSoft, icon: Icons.check_circle_rounded, label: 'قبول'),
                  secondaryBackground: _swipeBackground(alignStart: false, color: AppColors.dangerSoft, icon: Icons.cancel_rounded, label: 'رفض'),
                  confirmDismiss: (direction) async {
                    if (direction == DismissDirection.startToEnd) {
                      onApprove();
                    } else {
                      onReject();
                    }
                    return false; // the list reloads from the server; never remove the row locally
                  },
                  child: row,
                )
              : row,
        ),
      ),
    );

    return canManage ? gated : row;
  }

  Widget _swipeBackground({required bool alignStart, required Color color, required IconData icon, required String label}) {
    return Container(
      decoration: BoxDecoration(color: color, borderRadius: AppRadius.cardRadius),
      alignment: alignStart ? AlignmentDirectional.centerStart : AlignmentDirectional.centerEnd,
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: color == AppColors.successSoft ? AppColors.successOnSoft : AppColors.dangerOnSoft),
          const SizedBox(width: 6),
          Text(label,
              style: TextStyle(
                  fontWeight: FontWeight.w700,
                  color: color == AppColors.successSoft ? AppColors.successOnSoft : AppColors.dangerOnSoft)),
        ],
      ),
    );
  }

  Future<void> _showBlockSheet(BuildContext context, {required bool blocked}) async {
    final action = await showModalBottomSheet<String>(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (sheetContext) => _BlockActionSheet(phone: join.phone, blocked: blocked),
    );
    if (action == 'block') onBlock();
    if (action == 'unblock') onUnblock();
  }

  String _timeAgo(int epochSeconds) {
    if (epochSeconds <= 0) return '';
    final diff = DateTime.now().difference(DateTime.fromMillisecondsSinceEpoch(epochSeconds * 1000));
    if (diff.inMinutes < 1) return 'الآن';
    if (diff.inHours < 1) return 'قبل ${diff.inMinutes} دقيقة';
    if (diff.inDays < 1) return 'قبل ${diff.inHours} ساعة';
    return 'قبل ${diff.inDays} يوم';
  }
}

/// A short, fixed confirm sheet — 2 lines + one button, cannot grow, same shape
/// `ci/check_mobile_sheet_max_height.py`'s own EXEMPT list already tolerates for a plain
/// yes/no confirm; still capped with [appSheetMaxHeight] here since this file is new.
class _BlockActionSheet extends StatelessWidget {
  const _BlockActionSheet({required this.phone, required this.blocked});
  final String phone;
  final bool blocked;

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    return Container(
      constraints: BoxConstraints(maxHeight: appSheetMaxHeight(context)),
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        color: colors.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
      ),
      child: SafeArea(
        top: false,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(blocked ? 'رفع الحظر عن $phone؟' : 'حظر $phone؟',
                style: AppTextStyles.headlineSmall, textAlign: TextAlign.center),
            const SizedBox(height: AppSpacing.xs),
            Text(
              blocked
                  ? 'سيتمكن هذا الرقم من إرسال طلب انضمام جديد.'
                  : 'لن يتمكن هذا الرقم من الحجز في هذا المحل حتى لو لم يسبق له أي طلب.',
              style: AppTextStyles.bodySmall.copyWith(color: colors.textSecondary),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AppSpacing.lg),
            SizedBox(
              width: double.infinity,
              child: PrimaryButton(
                text: blocked ? 'رفع الحظر' : 'حظر',
                onPressed: () => Navigator.of(context).pop(blocked ? 'unblock' : 'block'),
              ),
            ),
            const SizedBox(height: AppSpacing.sm),
            SizedBox(
              width: double.infinity,
              child: SecondaryButton(text: 'إلغاء', onPressed: () => Navigator.of(context).pop()),
            ),
          ],
        ),
      ),
    );
  }
}
