import 'dart:async';

import 'package:flutter_gemma/flutter_gemma.dart';
import 'package:raje3_mobile/core/ai/ai_model.dart';

/// Gemma 4 E4B, entirely on-device via `flutter_gemma` — the model file is downloaded once to
/// this device's own storage and every prompt/answer after that runs locally; nothing here ever
/// calls one of our own servers (see AiModel's own doc comment for why that matters).
///
/// ONE ADAPTER, THE PLUGIN'S OWN LIFECYCLE UNDERNEATH. [_model]/[_chat] are `flutter_gemma`'s own
/// [InferenceModel]/[InferenceChat] — this class exists to translate ITS shape into [AiModel]'s
/// shape (a status enum instead of exceptions bubbling up, a token stream instead of the plugin's
/// own [TextResponse]/[FunctionCallResponse] union), never to add product logic of its own.
class GemmaAiModel implements AiModel {
  GemmaAiModel({required String modelUrl, String token = ''})
      : _modelUrl = modelUrl,
        _token = token;

  final String _modelUrl;
  final String _token;

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
  Future<void> ensureReady() async {
    if (_status == AiModelStatus.ready) return;
    try {
      _setStatus(AiModelStatus.downloading);
      await FlutterGemma.installModel(
        modelType: ModelType.gemmaIt,
        fileType: ModelFileType.litertlm,
      )
          .fromNetwork(_modelUrl, token: _token.isEmpty ? null : _token)
          .withProgress((progress) => _progressController.add(progress))
          .install();

      _setStatus(AiModelStatus.loading);
      final model = await FlutterGemma.getActiveModel(
        maxTokens: 2048,
        preferredBackend: PreferredBackend.gpu,
      );
      final chat = await model.createChat();
      _model = model;
      _chat = chat;
      _setStatus(AiModelStatus.ready);
    } catch (_) {
      // NEVER RETHROWN — see AiModel.ensureReady's own doc comment: a failed model load
      // degrades the assistant surface, it does not crash whatever screen opened it.
      _setStatus(AiModelStatus.error);
    }
  }

  @override
  Stream<String> generate(String prompt, {String systemInstruction = ''}) {
    final chat = _chat;
    if (_status != AiModelStatus.ready || chat == null) {
      throw StateError('GemmaAiModel cannot generate — check AiModel.status before calling generate().');
    }
    final controller = StreamController<String>();
    () async {
      try {
        await chat.addQueryChunk(Message.text(text: prompt, isUser: true));
        await for (final response in chat.generateChatResponseAsync()) {
          if (response is TextResponse) controller.add(response.token);
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
