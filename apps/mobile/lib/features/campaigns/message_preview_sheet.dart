import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/services/messages_service.dart';
import 'package:raje3_mobile/models/messages_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/features/campaigns/campaigns_i18n.dart';
import 'package:raje3_mobile/features/campaigns/text_editor_sheet.dart';
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
  bool canRetext = false,
}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (_) => _MessagePreviewSheet(
      label: label, when: when, reasonId: reasonId, templateType: templateType, canRetext: canRetext,
    ),
  );
}

class _MessagePreviewSheet extends StatefulWidget {
  const _MessagePreviewSheet({
    required this.label, required this.when, this.reasonId, this.templateType, this.canRetext = false,
  });

  final String label;
  final String when;
  final String? reasonId;
  final String? templateType;
  /// Only a REASON carries a legal right to opt out on the customer's own end, and only that
  /// same subset may be re-worded by the shop (`reason.can_retext`) — never for a bare goal.
  final bool canRetext;

  @override
  State<_MessagePreviewSheet> createState() => _MessagePreviewSheetState();
}

class _MessagePreviewSheetState extends State<_MessagePreviewSheet> {
  late final MessagesService _service;
  PreviewAnswer? _answer;
  bool _failed = false;
  String _saving = '';

  /// HIS OWN TEXTS THAT ARE NOT SENDING YET, and this is the half the bubbles cannot show — a
  /// draft he saved, one waiting on Meta, one refused. `null` while unread/not applicable
  /// (a bare goal has no texts of its own — see `_hasReason`).
  List<MyTemplate>? _mine;
  List<TemplateHelpRequest>? _help;

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
    if (_hasReason) {
      _service.myTemplates(widget.reasonId!).then((rows) {
        if (mounted) setState(() => _mine = rows?.where((t) => t.status != 'approved').toList());
      });
      _service.myTemplateHelp().then((rows) {
        if (mounted) setState(() => _help = rows);
      });
    }
  }

  Future<void> _openEditor() async {
    if (_answer == null) return;
    final existing = (_mine ?? const []).where((t) => t.body.isNotEmpty).firstOrNull;
    await showTextEditorSheet(
      context,
      reasonId: widget.reasonId!,
      label: widget.label,
      slots: _answer!.slots,
      mandatory: _answer!.mandatory,
      initialBody: existing?.body ?? '',
      replaces: existing?.name ?? '',
      onSaved: _load,
    );
  }

  Future<void> _submit(String name) async {
    setState(() => _saving = 'submit:$name');
    await _service.submitTemplate(name);
    if (!mounted) return;
    setState(() => _saving = '');
    _load();
  }

  Future<void> _requestHelp(String name) async {
    setState(() => _saving = 'help:$name');
    await _service.templateHelp(name);
    if (!mounted) return;
    setState(() => _saving = '');
    _load();
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
            // «اكتب نصّك» + HIS OWN TEXTS THAT ARE NOT SENDING YET — never for a bare goal,
            // which has no reason to attach a written text to, and never when the customer's
            // own right to opt out means this reason cannot be re-worded at all.
            if (_hasReason && widget.canRetext && _answer != null) ...[
              const Divider(height: 1),
              Padding(
                padding: const EdgeInsets.all(AppSpacing.md),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    SecondaryButton(
                      text: ct(context, 'writeYourText'),
                      icon: Icons.edit_outlined,
                      onPressed: _openEditor,
                    ),
                    if ((_mine ?? const []).isNotEmpty) ...[
                      const SizedBox(height: AppSpacing.sm),
                      for (final m in _mine!)
                        Padding(
                          padding: const EdgeInsets.only(top: AppSpacing.sm),
                          child: _MyTemplateRow(
                            template: m,
                            help: (_help ?? const []).where((h) => h.name == m.name).firstOrNull,
                            busy: _saving == 'submit:${m.name}' || _saving == 'help:${m.name}',
                            onSubmit: () => _submit(m.name),
                            onRequestHelp: () => _requestHelp(m.name),
                          ),
                        ),
                    ],
                  ],
                ),
              ),
            ] else if (_hasReason && !widget.canRetext && _answer != null)
              Padding(
                padding: const EdgeInsets.all(AppSpacing.md),
                child: Row(children: [
                  Icon(Icons.lock_outline, size: 14, color: colors.textSecondary),
                  const SizedBox(width: 6),
                  Expanded(child: Text(ct(context, 'cannotWriteNote'), style: AppTextStyles.caption)),
                ]),
              ),
          ],
        ),
      ),
    );
  }
}

/// One of the shop's own texts, with the two buttons it never had before this pass: «ارفعه» (a
/// draft is otherwise a notepad — nothing to press) and «ساعدوني» (the cost of having no reviewer
/// of ours between him and Meta, when it is refused).
class _MyTemplateRow extends StatelessWidget {
  const _MyTemplateRow({
    required this.template,
    required this.help,
    required this.busy,
    required this.onSubmit,
    required this.onRequestHelp,
  });

  final MyTemplate template;
  final TemplateHelpRequest? help;
  final bool busy;
  final VoidCallback onSubmit;
  final VoidCallback onRequestHelp;

  @override
  Widget build(BuildContext context) {
    final isDark = context.isDark;
    final (label, fg, bg) = switch (template.status) {
      'rejected' => (ct(context, 'statusRejected'), isDark ? AppDarkColors.danger : AppColors.danger,
          isDark ? AppDarkColors.dangerSoft : AppColors.dangerSoft),
      'pending' => (ct(context, 'statusPending'), isDark ? AppDarkColors.warning : AppColors.warning,
          isDark ? AppDarkColors.warningSoft : AppColors.warningSoft),
      _ => (ct(context, 'statusDraft'), context.appColors.textSecondary, context.appColors.surfaceAlt),
    };
    return AppCard(
      hasShadow: false,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            AppBadge(text: label, textColor: fg, backgroundColor: bg),
            const SizedBox(width: AppSpacing.sm),
            Expanded(child: Text(template.body, maxLines: 2, overflow: TextOverflow.ellipsis, style: AppTextStyles.bodySmall)),
          ]),
          if (template.reason.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(template.reason, style: AppTextStyles.caption),
          ],
          const SizedBox(height: AppSpacing.sm),
          Wrap(spacing: AppSpacing.sm, children: [
            if (template.status == 'draft')
              SecondaryButton(text: ct(context, 'submitToWhatsapp'), onPressed: busy ? null : onSubmit),
            if (template.status == 'rejected')
              SecondaryButton(text: ct(context, 'helpMe'), onPressed: busy ? null : onRequestHelp),
          ]),
          if (help?.answer.isNotEmpty == true) ...[
            const SizedBox(height: AppSpacing.sm),
            Text(help!.answer, style: AppTextStyles.caption),
          ] else if (help?.status == 'open') ...[
            const SizedBox(height: AppSpacing.sm),
            Text(ct(context, 'requestReceived'), style: AppTextStyles.caption),
          ],
        ],
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
          WhatsAppPhoneFrame(
            child: WhatsAppBubble(text: option.text, buttons: option.buttons),
          ),
          const SizedBox(height: 4),
          Text(caption, style: AppTextStyles.caption),
          // THE SHAPE, THEN THE FILLED EXAMPLE — shown only when it actually differs, so a
          // customer never reads «[اسم العميل]» as the shop's own words: the blanks are named,
          // never numbered, so one word describes the same blank everywhere.
          if (option.template.isNotEmpty && option.template != option.text) ...[
            const SizedBox(height: AppSpacing.sm),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(AppSpacing.sm),
              decoration: BoxDecoration(
                color: context.appColors.surfaceAlt,
                borderRadius: AppRadius.standardRadius,
              ),
              child: Text(option.template, style: AppTextStyles.caption),
            ),
          ],
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
