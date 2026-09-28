import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/actions/action_executor.dart';
import 'package:raje3_mobile/core/actions/action_model.dart';
import 'package:raje3_mobile/core/actions/action_registry.dart';
import 'package:raje3_mobile/core/ai/ai_model.dart';
import 'package:raje3_mobile/core/ai/assistant_service.dart';
import 'package:raje3_mobile/core/ai/assistant_turn.dart';
import 'package:raje3_mobile/core/providers/nav_provider.dart';
import 'package:raje3_mobile/core/storage/local_storage.dart';
import 'package:raje3_mobile/features/home/app_tone.dart';
import 'package:raje3_mobile/models/catalog_model.dart';
import 'package:raje3_mobile/core/tts/tts_model.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/assistant_reply_mode_sheet.dart';

/// Phase 1 of the on-device assistant: type a question, get a text answer grounded in
/// [AssistantService]'s own KB — the floating mic button's `onTap` opens this today; voice input
/// and output are separate, later phases (see AiModel's own doc comment on why speech OUTPUT is
/// an entirely independent port).
class AssistantChatSheet extends StatefulWidget {
  /// A voice question already answered elsewhere (see [FloatingMicButton]'s own "text reply
  /// mode" branch) — shown here exactly like one typed in, rather than making the operator
  /// re-ask it.
  final AssistantTurn? seed;

  const AssistantChatSheet({super.key, this.seed});

  @override
  State<AssistantChatSheet> createState() => _AssistantChatSheetState();

  static void show(BuildContext context, {AssistantTurn? seed}) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => AssistantChatSheet(seed: seed),
    );
  }
}

class _AssistantChatSheetState extends State<AssistantChatSheet> {
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  late final List<AssistantTurn> _turns = widget.seed == null ? [] : [widget.seed!];
  AiModelStatus _status = AiModelStatus.unavailable;
  int _downloadPercent = 0;
  StreamSubscription<int>? _downloadProgressSubscription;
  bool _answering = false;
  AssistantTurn? _speaking;

  late final AssistantService _assistant;
  late final TtsModel _tts;
  late final ActionExecutor _executor;
  late final LocalStorage _localStorage;

  @override
  void initState() {
    super.initState();
    _assistant = context.read<AssistantService>();
    _tts = context.read<TtsModel>();
    _executor = ActionExecutor(registry: context.read<ActionRegistry>());
    _localStorage = context.read<LocalStorage>();
    _status = _assistant.status;
    _assistant.statusStream.listen((s) {
      if (mounted) setState(() => _status = s);
    });
    _downloadProgressSubscription = _assistant.downloadProgress.listen((p) {
      if (mounted) setState(() => _downloadPercent = p);
    });
    if (_status != AiModelStatus.ready) {
      _assistant.ensureReady(context.read<NavProvider>().catalog);
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    _downloadProgressSubscription?.cancel();
    _tts.stop();
    super.dispose();
  }

  /// Retries the exact same [AssistantService.ensureReady] the sheet's own initState already
  /// tried once — a lost connection mid-download previously left [_status] stuck at
  /// [AiModelStatus.error] forever, with no way back short of force-closing the app (found live,
  /// 2026-09-28). [AiModelStatus.unavailable] gets no such button: that state means the device or
  /// build genuinely cannot run the model at all, not a failure retrying would ever fix.
  void _retryDownload() {
    setState(() => _status = AiModelStatus.downloading);
    _assistant.ensureReady(context.read<NavProvider>().catalog);
  }

  Future<void> _toggleSpeak(AssistantTurn turn) async {
    if (_speaking == turn) {
      await _tts.stop();
      if (mounted) setState(() => _speaking = null);
      return;
    }
    final lang = Localizations.localeOf(context).languageCode;
    await _tts.stop();
    if (!mounted) return;
    setState(() => _speaking = turn);
    await _tts.speak(turn.answer, languageCode: lang);
    if (mounted && _speaking == turn) setState(() => _speaking = null);
  }

  void _send() {
    final question = _controller.text.trim();
    if (question.isEmpty || _status != AiModelStatus.ready || _answering) return;
    _controller.clear();

    final catalog = context.read<NavProvider>().catalog;
    final lang = Localizations.localeOf(context).languageCode;
    final turn = AssistantTurn(question: question);
    setState(() {
      _turns.add(turn);
      _answering = true;
    });

    _assistant.ask(question, lang: lang, catalog: catalog).listen(
      (event) {
        if (!mounted) return;
        switch (event) {
          case AiTextToken(:final text):
            setState(() => turn.answer += text);
          case AiActionProposed():
            _handleProposedAction(turn, event, catalog);
        }
      },
      onDone: () {
        if (!mounted) return;
        setState(() => _answering = false);
        // TYPED QUESTION, SPOKEN ANSWER — only when the operator's own reply-mode setting asks
        // for it (see assistant_reply_mode_sheet.dart); the manual 🔊 button below always works
        // regardless, this just does it automatically.
        if (_localStorage.assistantReplyIsVoice && turn.answer.isNotEmpty) {
          unawaited(_toggleSpeak(turn));
        }
      },
    );
  }

  /// Resolves one proposed action against the REAL, CURRENT catalog — [_send]'s own [catalog]
  /// snapshot can be a beat stale by the time the model actually proposes something, so this
  /// re-reads it fresh rather than trusting the one captured when the question was first asked.
  void _handleProposedAction(AssistantTurn turn, AiActionProposed event, Catalog catalog) {
    final freshCatalog = context.read<NavProvider>().catalog;
    final decision = _executor.resolve(event, freshCatalog);
    switch (decision) {
      case ActionUnavailable():
        setState(() => turn.answer += '\n${S.of(context)!.assistantActionUnavailable}');
      case ActionRunNow(:final action):
        unawaited(_runAndShow(turn, action));
      case ActionNeedsConfirmation(:final action):
        setState(() => turn.pendingAction = action);
    }
  }

  /// Carries out [action] and either closes the sheet (a real navigation just happened — the
  /// destination screen IS the answer, and the sheet's own overlay would otherwise sit
  /// confusingly on top of it) or, for a READ action with a real spoken answer, appends that
  /// answer to the turn and keeps the sheet open — there is nowhere to navigate TO, so closing
  /// it would hide the one thing the operator actually asked for.
  Future<void> _runAndShow(AssistantTurn turn, AppAction action) async {
    final result = await _executor.execute(context, action);
    if (!mounted) return;
    if (result != null) {
      setState(() => turn.answer += (turn.answer.isEmpty ? '' : '\n') + result);
      return;
    }
    if (Navigator.of(context).canPop()) Navigator.of(context).pop();
  }

  void _confirmPendingAction(AssistantTurn turn) {
    final action = turn.pendingAction;
    if (action == null) return;
    setState(() => turn.pendingAction = null);
    unawaited(_runAndShow(turn, action));
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    return DraggableScrollableSheet(
      initialChildSize: 0.7,
      minChildSize: 0.4,
      maxChildSize: 0.95,
      expand: false,
      builder: (context, scrollController) => Container(
        decoration: const BoxDecoration(
          color: AppColors.surface0,
          borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.lg)),
        ),
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsetsDirectional.fromSTEB(
                  AppSpacing.md, AppSpacing.md, AppSpacing.sm, AppSpacing.md),
              child: Row(
                children: [
                  Expanded(
                    child: Text(s.assistantChatTitle, style: AppTextStyles.headlineSmall),
                  ),
                  IconButton(
                    icon: const Icon(Icons.tune_rounded, size: 20),
                    tooltip: s.assistantReplySettingsTooltip,
                    onPressed: () => AssistantReplyModeSheet.show(context),
                  ),
                ],
              ),
            ),
            Expanded(child: _buildBody(scrollController)),
            _buildInputRow(s),
          ],
        ),
      ),
    );
  }

  Widget _buildBody(ScrollController scrollController) {
    final s = S.of(context)!;
    if (_status == AiModelStatus.unavailable) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Text(s.assistantUnavailable, style: AppTextStyles.bodyMedium, textAlign: TextAlign.center),
        ),
      );
    }
    if (_status == AiModelStatus.error) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(s.assistantUnavailable, style: AppTextStyles.bodyMedium, textAlign: TextAlign.center),
              const SizedBox(height: AppSpacing.md),
              FilledButton.icon(
                onPressed: _retryDownload,
                icon: const Icon(Icons.refresh_rounded, size: 18),
                label: Text(s.assistantRetryDownload),
              ),
            ],
          ),
        ),
      );
    }
    if (_status != AiModelStatus.ready) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              CircularProgressIndicator(value: _downloadPercent > 0 ? _downloadPercent / 100 : null),
              const SizedBox(height: AppSpacing.md),
              Text(
                _downloadPercent > 0 ? '${s.assistantPreparing} ($_downloadPercent%)' : s.assistantPreparing,
                style: AppTextStyles.bodyMedium,
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      );
    }
    return ListView.builder(
      controller: scrollController,
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
      itemCount: _turns.length,
      itemBuilder: (context, i) => _buildTurn(_turns[i]),
    );
  }

  Widget _buildTurn(AssistantTurn turn) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Align(
            alignment: AlignmentDirectional.centerEnd,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.sm),
              decoration: BoxDecoration(color: AppColors.accentSoft, borderRadius: AppRadius.standardRadius),
              child: Text(turn.question, style: AppTextStyles.bodyMedium),
            ),
          ),
          if (turn.answer.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.xs),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(child: Text(turn.answer, style: AppTextStyles.bodyMedium)),
                if (!_answering || turn != _turns.last)
                  IconButton(
                    icon: Icon(_speaking == turn ? Icons.stop_circle_rounded : Icons.volume_up_rounded,
                        size: 20, color: AppColors.textMuted),
                    tooltip: _speaking == turn ? S.of(context)!.assistantStopSpeaking : S.of(context)!.assistantSpeak,
                    onPressed: () => _toggleSpeak(turn),
                  ),
              ],
            ),
          ],
          if (turn.pendingAction != null) ...[
            const SizedBox(height: AppSpacing.sm),
            _ActionConfirmCard(
              action: turn.pendingAction!,
              onCancel: () => setState(() => turn.pendingAction = null),
              onConfirm: () => _confirmPendingAction(turn),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildInputRow(S s) {
    final enabled = _status == AiModelStatus.ready && !_answering;
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Row(
          children: [
            Expanded(
              child: TextField(
                controller: _controller,
                enabled: enabled,
                onSubmitted: (_) => _send(),
                decoration: InputDecoration(hintText: s.assistantInputHint),
              ),
            ),
            const SizedBox(width: AppSpacing.sm),
            IconButton(
              icon: const Icon(Icons.send_rounded),
              onPressed: enabled ? _send : null,
              tooltip: s.assistantSend,
            ),
          ],
        ),
      ),
    );
  }
}

/// The card a sensitive action's confirmation actually shows — [action]'s OWN
/// [AppAction.confirmMessage], never a generic "confirm this?" (the owner's own catch,
/// 2026-09-22). A real tap on [onConfirm] is what carries the action out; the model's own
/// proposal never does — see [AppAction.requiresConfirmation]'s own doc comment.
class _ActionConfirmCard extends StatelessWidget {
  final AppAction action;
  final VoidCallback onCancel;
  final VoidCallback onConfirm;

  const _ActionConfirmCard({required this.action, required this.onCancel, required this.onConfirm});

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final colors = ToneColors.of(context, AppTone.warning);
    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: colors.soft,
        borderRadius: AppRadius.standardRadius,
        border: Border.all(color: colors.solid.withValues(alpha: 0.35)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.warning_amber_rounded, size: 18, color: colors.onSoft),
              const SizedBox(width: AppSpacing.xs),
              Expanded(
                child: Text(action.confirmMessage ?? '',
                    style: AppTextStyles.bodySmall.copyWith(color: colors.onSoft, fontWeight: FontWeight.w600)),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              TextButton(onPressed: onCancel, child: Text(s.assistantCancel)),
              const SizedBox(width: AppSpacing.xs),
              TextButton(
                style: colors.textStyle(),
                onPressed: onConfirm,
                child: Text(s.assistantConfirm),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
