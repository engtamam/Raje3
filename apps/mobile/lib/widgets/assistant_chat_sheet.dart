import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/ai/ai_model.dart';
import 'package:raje3_mobile/core/ai/assistant_service.dart';
import 'package:raje3_mobile/core/providers/nav_provider.dart';
import 'package:raje3_mobile/core/tts/tts_model.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/theme/app_theme.dart';

/// Phase 1 of the on-device assistant: type a question, get a text answer grounded in
/// [AssistantService]'s own KB — the floating mic button's `onTap` opens this today; voice input
/// and output are separate, later phases (see AiModel's own doc comment on why speech OUTPUT is
/// an entirely independent port).
class AssistantChatSheet extends StatefulWidget {
  const AssistantChatSheet({super.key});

  @override
  State<AssistantChatSheet> createState() => _AssistantChatSheetState();

  static void show(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => const AssistantChatSheet(),
    );
  }
}

class _AssistantChatSheetState extends State<AssistantChatSheet> {
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  final List<_Turn> _turns = [];
  AiModelStatus _status = AiModelStatus.unavailable;
  bool _answering = false;
  _Turn? _speaking;

  late final AssistantService _assistant;
  late final TtsModel _tts;

  @override
  void initState() {
    super.initState();
    _assistant = context.read<AssistantService>();
    _tts = context.read<TtsModel>();
    _status = _assistant.status;
    _assistant.statusStream.listen((s) {
      if (mounted) setState(() => _status = s);
    });
    if (_status != AiModelStatus.ready) _assistant.ensureReady();
  }

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    _tts.stop();
    super.dispose();
  }

  Future<void> _toggleSpeak(_Turn turn) async {
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
    final turn = _Turn(question: question, answer: '');
    setState(() {
      _turns.add(turn);
      _answering = true;
    });

    _assistant.ask(question, lang: lang, catalog: catalog).listen(
      (token) {
        if (!mounted) return;
        setState(() => turn.answer += token);
      },
      onDone: () {
        if (mounted) setState(() => _answering = false);
      },
    );
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
              padding: const EdgeInsets.all(AppSpacing.md),
              child: Text(s.assistantChatTitle, style: AppTextStyles.headlineSmall),
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
    if (_status == AiModelStatus.unavailable || _status == AiModelStatus.error) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Text(s.assistantUnavailable, style: AppTextStyles.bodyMedium, textAlign: TextAlign.center),
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
              const CircularProgressIndicator(),
              const SizedBox(height: AppSpacing.md),
              Text(s.assistantPreparing, style: AppTextStyles.bodyMedium, textAlign: TextAlign.center),
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

  Widget _buildTurn(_Turn turn) {
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

class _Turn {
  final String question;
  String answer;
  _Turn({required this.question, required this.answer});
}
