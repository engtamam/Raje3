import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/services/messages_service.dart';
import 'package:raje3_mobile/models/messages_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/features/campaigns/whatsapp_bubble.dart';

/// The message-preview bottom sheet — mirrors `MessagePreview.tsx`'s job (tap a card, read every
/// wording it can send, in a real bubble) but as a sheet that rises over the list instead of a
/// full modal, per this pass's own mobile-native brief.
///
/// TEMPLATE-STATUS BADGES ARE NEVER SIMPLIFIED AWAY HERE — a wording still awaiting WhatsApp's
/// approval, or one it rejected, must read as such: showing it as ready is a silent failed send
/// waiting to happen.
Future<void> showMessagePreviewSheet(
  BuildContext context, {
  required String label,
  required String when,
  String? reasonId,
  String? templateType,
}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (_) => _MessagePreviewSheet(label: label, when: when, reasonId: reasonId, templateType: templateType),
  );
}

class _MessagePreviewSheet extends StatefulWidget {
  const _MessagePreviewSheet({required this.label, required this.when, this.reasonId, this.templateType});

  final String label;
  final String when;
  final String? reasonId;
  final String? templateType;

  @override
  State<_MessagePreviewSheet> createState() => _MessagePreviewSheetState();
}

class _MessagePreviewSheetState extends State<_MessagePreviewSheet> {
  late final MessagesService _service;
  List<MessageOption>? _options;
  bool _failed = false;

  @override
  void initState() {
    super.initState();
    _service = MessagesService(apiClient: context.read<AuthProvider>().apiClient);
    _load();
  }

  Future<void> _load() async {
    final options = widget.reasonId != null
        ? await _service.previewReason(widget.reasonId!)
        : await _service.previewByType(widget.templateType!);
    if (!mounted) return;
    setState(() {
      _options = options;
      _failed = options == null;
    });
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final maxHeight = appSheetMaxHeight(context);

    return Container(
      constraints: BoxConstraints(maxHeight: maxHeight),
      decoration: BoxDecoration(
        color: colors.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
      ),
      child: SafeArea(
        top: false,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(height: 8),
            Container(width: 40, height: 4, decoration: BoxDecoration(
              color: colors.borderSubtle, borderRadius: BorderRadius.circular(2))),
            Padding(
              padding: const EdgeInsets.fromLTRB(AppSpacing.md, AppSpacing.md, AppSpacing.md, 0),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(widget.label, style: AppTextStyles.headlineSmall),
                        if (widget.when.isNotEmpty)
                          Text(widget.when, style: AppTextStyles.bodySmall.copyWith(color: colors.textSecondary)),
                      ],
                    ),
                  ),
                  IconButton(icon: const Icon(Icons.close), onPressed: () => Navigator.of(context).pop()),
                ],
              ),
            ),
            const Divider(height: 1),
            Flexible(
              child: _options == null
                  ? const Padding(
                      padding: EdgeInsets.all(AppSpacing.xl),
                      child: Center(child: CircularProgressIndicator()),
                    )
                  : _failed
                      ? const Padding(
                          padding: EdgeInsets.all(AppSpacing.xl),
                          child: Text('تعذّرت قراءة الرسالة الآن.', style: AppTextStyles.bodyMedium),
                        )
                      : (_options ?? const []).isEmpty
                          ? const Padding(
                              padding: EdgeInsets.all(AppSpacing.xl),
                              child: Text('لا صيغة متاحة لهذه الرسالة الآن.'),
                            )
                          : ListView(
                              shrinkWrap: true,
                              padding: const EdgeInsets.all(AppSpacing.md),
                              children: (_options ?? const [])
                                  .map((o) => Padding(
                                        padding: const EdgeInsets.only(bottom: AppSpacing.md),
                                        child: _OptionCard(option: o),
                                      ))
                                  .toList(),
                            ),
            ),
          ],
        ),
      ),
    );
  }
}

class _OptionCard extends StatelessWidget {
  const _OptionCard({required this.option});

  final MessageOption option;

  (String, Color, Color)? _statusChip(BuildContext context) {
    final isDark = context.isDark;
    if (option.mine && option.status == 'rejected') {
      return ('رفضها واتساب', isDark ? AppDarkColors.danger : AppColors.danger,
          isDark ? AppDarkColors.dangerSoft : AppColors.dangerSoft);
    }
    if (option.mine && option.status == 'pending') {
      return ('عند واتساب للمراجعة', isDark ? AppDarkColors.warning : AppColors.warning,
          isDark ? AppDarkColors.warningSoft : AppColors.warningSoft);
    }
    if (option.mine && option.status == 'draft') {
      return ('لم تُرفَع بعد', context.appColors.textSecondary, context.appColors.surfaceAlt);
    }
    if (option.approved == true) {
      return ('جاهزة للإرسال', isDark ? AppDarkColors.success : AppColors.success,
          isDark ? AppDarkColors.successSoft : AppColors.successSoft);
    }
    if (option.approved == false) {
      return ('بانتظار اعتماد واتساب', isDark ? AppDarkColors.warning : AppColors.warning,
          isDark ? AppDarkColors.warningSoft : AppColors.warningSoft);
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final chip = _statusChip(context);
    final caption = option.mine
        ? 'نصّك أنت'
        : (option.tone == 'masculine' ? 'مذكر' : option.tone == 'feminine' ? 'مؤنث' : option.tone);
    return AppCard(
      hasShadow: false,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (chip != null)
            Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.sm),
              child: AppBadge(text: chip.$1, textColor: chip.$2, backgroundColor: chip.$3),
            ),
          WhatsAppBubble(text: option.text, caption: caption),
          if (option.reason.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.sm),
            Text(option.reason, style: AppTextStyles.caption),
          ],
        ],
      ),
    );
  }
}
