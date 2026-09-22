import 'dart:async';

import 'package:flutter_gemma/flutter_gemma.dart';
import 'package:raje3_mobile/core/ai/ai_model.dart';

/// Gemma 4 E4B, entirely on-device via `flutter_gemma` — the model file SHIPS INSIDE THE APP
/// PACKAGE ITSELF (owner's own explicit decision, 2026-09-22, reversing the earlier "download
/// after install" design — see ai_config.dart's own doc comment on [AiConfig.gemmaModelAssetPath]
/// for the full reasoning and the real size trade-off that decision accepts) — no network call is
/// ever made to install it, and every prompt/answer after that runs locally; nothing here ever
/// calls one of our own servers either (see AiModel's own doc comment for why that matters).
///
/// ONE ADAPTER, THE PLUGIN'S OWN LIFECYCLE UNDERNEATH. [_model]/[_chat] are `flutter_gemma`'s own
/// [InferenceModel]/[InferenceChat] — this class exists to translate ITS shape into [AiModel]'s
/// shape (a status enum instead of exceptions bubbling up, [AiEvent] instead of the plugin's own
/// [TextResponse]/[FunctionCallResponse] union, [AiTool] instead of its own [Tool]), never to add
/// product logic of its own.
class GemmaAiModel implements AiModel {
  GemmaAiModel({required String modelAssetPath}) : _modelAssetPath = modelAssetPath;

  final String _modelAssetPath;

  @override
  String get driver => 'gemma';

  AiModelStatus _status = AiModelStatus.needsDownload;
  final _statusController = StreamController<AiModelStatus>.broadcast();
  final _progressController = StreamController<int>.broadcast();

  InferenceModel? _model;
  InferenceChat? _chat;

  @override
  AiModelStatus get status => _status;

  @override
  Stream<AiModelStatus> get statusStream => _statusController.stream;

  @override
  Stream<int> get downloadProgress => _progressController.stream;

  void _setStatus(AiModelStatus next) {
    _status = next;
    _statusController.add(next);
  }

  @override
  Future<void> ensureReady({List<AiTool> tools = const []}) async {
    if (_status == AiModelStatus.ready) return;
    try {
      _setStatus(AiModelStatus.downloading);
      // ModelType.gemma4, NOT .gemmaIt — this is item 1 of the models checklist: Gemma 4's
      // native function-calling tokens (see ai_model.dart's own doc comment on why actions
      // never needed a different model file, only this one flag) only activate under this
      // model type. The file itself hasn't changed; ai_config.dart already points at a real
      // Gemma 4 E4B build.
      await FlutterGemma.installModel(
        modelType: ModelType.gemma4,
        fileType: ModelFileType.litertlm,
      )
          // BUNDLED, NEVER NETWORK — see this class's own doc comment. `.install()` here is a
          // local copy out of the app bundle into the plugin's own writable storage on first
          // run (still worth the progress stream: a 2.77GB copy is not instant), never an HTTP
          // request.
          .fromAsset(_modelAssetPath)
          .withProgress((progress) => _progressController.add(progress))
          .install();

      _setStatus(AiModelStatus.loading);
      final model = await FlutterGemma.getActiveModel(
        maxTokens: 2048,
        preferredBackend: PreferredBackend.gpu,
      );
      // TOOLS ARE DECLARED HERE, ONCE — see AiModel.ensureReady's own doc comment on why the
      // plugin has no per-message tool list. [_convertTools] is the only place this file ever
      // touches flutter_gemma's own Tool type — [AiTool] stays the port's own shape everywhere
      // else, per ai_model.dart's own doc comment on why.
      final chat = await model.createChat(modelType: ModelType.gemma4, tools: _convertTools(tools));
      _model = model;
      _chat = chat;
      _setStatus(AiModelStatus.ready);
    } catch (_) {
      // NEVER RETHROWN — see AiModel.ensureReady's own doc comment: a failed model load
      // degrades the assistant surface, it does not crash whatever screen opened it.
      _setStatus(AiModelStatus.error);
    }
  }

  List<Tool> _convertTools(List<AiTool> tools) =>
      [for (final t in tools) Tool(name: t.name, description: t.description)];

  @override
  Stream<AiEvent> generate(String prompt, {String systemInstruction = ''}) {
    final chat = _chat;
    if (_status != AiModelStatus.ready || chat == null) {
      throw StateError('GemmaAiModel cannot generate — check AiModel.status before calling generate().');
    }
    final controller = StreamController<AiEvent>();
    // THE MODEL NEVER SEES A BARE PROMPT — flutter_gemma's own chat has no separate
    // "system message" call, so the grounding instruction (see AssistantService's own doc
    // comment) travels as a prefix on the first user turn. Silently dropping this parameter,
    // as an earlier pass of this file did, would answer every question ungrounded.
    final query = systemInstruction.isEmpty ? prompt : '$systemInstruction\n\n$prompt';
    () async {
      try {
        await chat.addQueryChunk(Message.text(text: query, isUser: true));
        await for (final response in chat.generateChatResponseAsync()) {
          switch (response) {
            case TextResponse():
              controller.add(AiTextToken(response.token));
            case FunctionCallResponse():
              controller.add(AiActionProposed(response.name, response.args));
            case ParallelFunctionCallResponse(:final calls):
              // ONE PROPOSAL AT A TIME. A caller that acts on the first action a turn proposes
              // and re-asks for the rest is simpler and safer than one that must reconcile
              // several proposals from a single utterance — no action registered today needs
              // more than one call per turn anyway.
              for (final call in calls) {
                controller.add(AiActionProposed(call.name, call.args));
              }
            default:
              // Thinking/other response kinds carry nothing the caller needs — never surfaced.
              break;
          }
        }
      } catch (_) {
        // A GENERATION FAILURE ENDS THE STREAM, IT DOES NOT MOVE STATUS TO error — the model
        // itself is still loaded and ready for the NEXT question; only this one answer failed.
      } finally {
        await controller.close();
      }
    }();
    return controller.stream;
  }

  @override
  Future<void> dispose() async {
    await _model?.close();
    _model = null;
    _chat = null;
    await _statusController.close();
    await _progressController.close();
  }
}
