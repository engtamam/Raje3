import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'package:raje3_mobile/core/storage/local_storage.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart' show appSheetMaxHeight;

/// The one setting the operator asked for after using the assistant a while: does it ALWAYS
/// answer aloud, or does it ALWAYS answer in writing — even a question he asked BY VOICE. Before
/// this existed the mode was hard-coded per input (speak after voice, stay silent after typing,
/// with only a manual per-message 🔊 override) — see [LocalStorage.assistantReplyIsVoice]'s own
/// doc comment for the two call sites this now governs
/// ([FloatingMicButton]'s own `_speakAnswer`/text-fallback branch and [AssistantChatSheet]'s
/// own `_send`).
class AssistantReplyModeSheet extends StatefulWidget {
  const AssistantReplyModeSheet({super.key});

  static void show(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => const AssistantReplyModeSheet(),
    );
  }

  @override
  State<AssistantReplyModeSheet> createState() => _AssistantReplyModeSheetState();
}

class _AssistantReplyModeSheetState extends State<AssistantReplyModeSheet> {
  late final LocalStorage _storage = context.read<LocalStorage>();
  late bool _voice = _storage.assistantReplyIsVoice;

  void _pick(bool voice) {
    if (_voice == voice) return;
    setState(() => _voice = voice);
    _storage.setAssistantReplyIsVoice(voice);
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: Container(
        constraints: BoxConstraints(maxHeight: appSheetMaxHeight(context)),
        padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.lg, AppSpacing.lg, AppSpacing.xl),
        decoration: const BoxDecoration(
          color: AppColors.surface1,
          borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(s.assistantReplyModeTitle, style: AppTextStyles.headlineSmall),
            const SizedBox(height: AppSpacing.xs),
            Text(s.assistantReplyModeSubtitle,
                style: AppTextStyles.bodySmall.copyWith(color: AppColors.textMuted)),
            const SizedBox(height: AppSpacing.lg),
            _ModeOption(
              icon: Icons.volume_up_rounded,
              label: s.assistantReplyModeVoice,
              selected: _voice,
              onTap: () => _pick(true),
            ),
            const SizedBox(height: AppSpacing.sm),
            _ModeOption(
              icon: Icons.chat_bubble_outline_rounded,
              label: s.assistantReplyModeText,
              selected: !_voice,
              onTap: () => _pick(false),
            ),
          ],
        ),
      ),
    );
  }
}

class _ModeOption extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool selected;
  final VoidCallback onTap;

  const _ModeOption({
    required this.icon,
    required this.label,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: selected ? AppColors.accentSoft : AppColors.surface0,
      borderRadius: AppRadius.standardRadius,
      child: InkWell(
        onTap: onTap,
        borderRadius: AppRadius.standardRadius,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.md),
          child: Row(
            children: [
              Icon(icon, size: 20, color: selected ? AppColors.accent : AppColors.textMuted),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Text(label,
                    style: AppTextStyles.bodyMedium.copyWith(
                        fontWeight: selected ? FontWeight.w700 : FontWeight.w500)),
              ),
              if (selected) const Icon(Icons.check_circle_rounded, size: 20, color: AppColors.accent),
            ],
          ),
        ),
      ),
    );
  }
}
