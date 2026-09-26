import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/services/messages_service.dart';
import 'package:raje3_mobile/models/messages_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/features/campaigns/campaigns_i18n.dart';
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
  PreviewAnswer? _answer;
  bool _failed = false;
  String _saving = '';

  /// Only a REASON has a shop-wide voice to pick or a customer text to point it at — a bare
  /// goal (`templateType` with no `reasonId`) has neither, same scope Launch.tsx's own
  /// `byGoal` flag already narrows on the console side.
  bool get _hasReason => widget.reasonId != null;

  @override
  void initState() {
    super.initState();
    _service = MessagesService(apiClient: context.read<AuthProvider>().apiClient);
    _load();
  }

  Future<void> _load() async {
    final answer = widget.reasonId != null
        ? await _service.previewReason(widget.reasonId!)
        : await _service.previewByType(widget.templateType!);
    if (!mounted) return;
    setState(() {
      _answer = answer;
      _failed = answer == null;
    });
  }

  Future<void> _chooseTone(String tone) async {
    if (_answer == null || tone == _answer!.tone) return;
    setState(() => _saving = 'tone:$tone');
    await _service.chooseTone(tone);
    if (!mounted) return;
    setState(() => _saving = '');
    _load();
  }

  Future<void> _useCustomerText(String name) async {
    if (widget.reasonId == null) return;
    setState(() => _saving = name);
    await _service.setReason(widget.reasonId!, true, template: name);
    if (!mounted) return;
    setState(() => _saving = '');
    _load();
  }

  Future<void> _revertToOurs() async {
    if (widget.reasonId == null) return;
    setState(() => _saving = 'ours');
    // EMPTY STRING DELETES THE STORED CUSTOM TEMPLATE (reason_choices.py's own `ChoiceStore.set`,
    // never a stored blank) — "point this reason back at ours".
    await _service.setReason(widget.reasonId!, true, template: '');
    if (!mounted) return;
    setState(() => _saving = '');
    _load();
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
              child: _answer == null
                  ? const Padding(
                      padding: EdgeInsets.all(AppSpacing.xl),
                      child: Center(child: CircularProgressIndicator()),
                    )
                  : _failed
                      ? Padding(
                          padding: const EdgeInsets.all(AppSpacing.xl),
                          child: Text(ct(context, 'previewLoadFailed'), style: AppTextStyles.bodyMedium),
                        )
                      : _answer!.options.isEmpty
                          // THREE REASONS, THREE SENTENCES (MessagePreview.tsx's own header
                          // note) — never one sentence shown for all three: "under review"
                          // said about a text that was never submitted sends an owner to wait
                          // on Meta for a refusal that was ours.
                          ? Padding(
                              padding: const EdgeInsets.all(AppSpacing.xl),
                              child: Text(switch (_answer!.emptyBecause) {
                                'unread' => ct(context, 'emptyUnread'),
                                'pending' => ct(context, 'emptyPending'),
                                _ => ct(context, 'emptyNone'),
                              }),
                            )
                          : ListView(
                              shrinkWrap: true,
                              padding: const EdgeInsets.all(AppSpacing.md),
                              children: _answer!.options
                                  .map((o) => Padding(
                                        padding: const EdgeInsets.only(bottom: AppSpacing.md),
                                        child: _OptionCard(
                                          option: o,
                                          hasReason: _hasReason,
                                          sending: o.mine ? _answer!.chosen == o.name : (_answer!.chosen.isEmpty && o.tone == _answer!.tone),
                                          chosen: _answer!.chosen,
                                          saving: _saving,
                                          onChooseTone: () => _chooseTone(o.tone),
                                          onUseCustomerText: () => _useCustomerText(o.name),
                                          onRevertToOurs: _revertToOurs,
                                        ),
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
  const _OptionCard({
    required this.option,
    required this.hasReason,
    required this.sending,
    required this.chosen,
    required this.saving,
    required this.onChooseTone,
    required this.onUseCustomerText,
    required this.onRevertToOurs,
  });

  final MessageOption option;
  final bool hasReason;
  final bool sending;
  /// The shop's own chosen custom-text name — empty means "sending ours" (the tone-based
  /// default), non-empty names which of his own texts is active.
  final String chosen;
  final String saving;
  final VoidCallback onChooseTone;
  final VoidCallback onUseCustomerText;
  final VoidCallback onRevertToOurs;

  (String, Color, Color)? _statusChip(BuildContext context) {
    final isDark = context.isDark;
    if (option.mine && option.status == 'rejected') {
      return (ct(context, 'statusRejected'), isDark ? AppDarkColors.danger : AppColors.danger,
          isDark ? AppDarkColors.dangerSoft : AppColors.dangerSoft);
    }
    if (option.mine && option.status == 'pending') {
      return (ct(context, 'statusPending'), isDark ? AppDarkColors.warning : AppColors.warning,
          isDark ? AppDarkColors.warningSoft : AppColors.warningSoft);
    }
    if (option.mine && option.status == 'draft') {
      return (ct(context, 'statusDraft'), context.appColors.textSecondary, context.appColors.surfaceAlt);
    }
    if (option.approved == true) {
      return (ct(context, 'statusReady'), isDark ? AppDarkColors.success : AppColors.success,
          isDark ? AppDarkColors.successSoft : AppColors.successSoft);
    }
    if (option.approved == false) {
      return (ct(context, 'statusAwaiting'), isDark ? AppDarkColors.warning : AppColors.warning,
          isDark ? AppDarkColors.warningSoft : AppColors.warningSoft);
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final chip = _statusChip(context);
    final caption = option.mine
        ? ct(context, 'yourText')
        : (option.tone == 'masculine'
            ? ct(context, 'toneMasculine')
            : option.tone == 'feminine' ? ct(context, 'toneFeminine') : option.tone);
    final isDark = context.isDark;
    final busy = saving == option.name || saving == 'tone:${option.tone}' || saving == 'ours';
    return AppCard(
      hasShadow: false,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(spacing: 6, runSpacing: 6, children: [
            if (chip != null) AppBadge(text: chip.$1, textColor: chip.$2, backgroundColor: chip.$3),
            // THE ACTIVE VOICE IS ALWAYS NAMED, NEVER JUST "READY" — the chosen one used to lose
            // its own status once it became the sending option; this badge is additive, so the
            // owner can still see BOTH which voice this is and that it is the one going out.
            if (sending)
              AppBadge(
                text: ct(context, 'sendingNow'),
                icon: Icons.check_circle_outline,
                backgroundColor: isDark ? AppDarkColors.accentSoft : AppColors.accentSoft,
                textColor: isDark ? AppDarkColors.accentOnSoft : AppColors.accentOnSoft,
              ),
          ]),
          if (chip != null || sending) const SizedBox(height: AppSpacing.sm),
          WhatsAppBubble(text: option.text, caption: caption),
          if (option.reason.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.sm),
            Text(option.reason, style: AppTextStyles.caption),
          ],
          if (hasReason && !sending) ...[
            const SizedBox(height: AppSpacing.sm),
            if (option.mine)
              SecondaryButton(text: ct(context, 'useIt'), onPressed: busy ? null : onUseCustomerText)
            else if (chosen.isEmpty)
              SecondaryButton(text: ct(context, 'makeMyTone'), onPressed: busy ? null : onChooseTone)
            else
              SecondaryButton(text: ct(context, 'backToOurs'), onPressed: busy ? null : onRevertToOurs),
          ],
        ],
      ),
    );
  }
}
