import 'dart:async';

import 'package:flutter/services.dart';
import 'package:flutter_gemma/flutter_gemma.dart';
import 'package:raje3_mobile/core/ai/ai_config.dart';
import 'package:raje3_mobile/core/ai/ai_model.dart';

/// Gemma 4 E4B, entirely on-device via `flutter_gemma` — the model file SHIPS INSIDE THE APP
/// PACKAGE ITSELF (owner's own explicit decision, 2026-09-22, reversing the earlier "download
/// after install" design — see ai_config.dart's own doc comment on [AiConfig.gemmaModelAssetPath]
/// for the full reasoning and the real size trade-off that decision accepts) — no network call is
/// ever made to install it, and every prompt/answer after that runs locally; nothing here ever
/// calls one of our own servers either (see AiModel's own doc comment for why that matters).
///
/// THE FILE ITSELF IS A PLAY ASSET DELIVERY PACK, NOT A FLUTTER ASSET (moved 2026-09-28) — the
/// raw ~2.77GB file inside a plain `assets:` entry put the whole thing in the app's base module,
/// which Google Play caps at 200MB compressed. `MainActivity.kt`'s own MethodChannel
/// (`raje3/ai_model_pack`) resolves the real on-device path at runtime instead of a static asset
/// key; the "ships with the app, no separate download" product decision is unchanged — an
/// install-time pack downloads together with the base app, before the user ever opens it.
///
/// ONE ADAPTER, THE PLUGIN'S OWN LIFECYCLE UNDERNEATH. [_model]/[_chat] are `flutter_gemma`'s own
/// [InferenceModel]/[InferenceChat] — this class exists to translate ITS shape into [AiModel]'s
/// shape (a status enum instead of exceptions bubbling up, [AiEvent] instead of the plugin's own
/// [TextResponse]/[FunctionCallResponse] union, [AiTool] instead of its own [Tool]), never to add
/// product logic of its own.
class GemmaAiModel implements AiModel {
  static const _methodChannel = MethodChannel('raje3/ai_model_pack');
  static const _progressChannel = EventChannel('raje3/ai_model_pack/progress');
  // Only used when AiConfig.modelSource == 'asset' (scripts/build_apk_direct.sh) — that script
  // copies the same file scripts/fetch_ai_model.sh fetches into this path and adds it to
  // pubspec.yaml's assets: list just for that one build, since a sideloaded APK has no Play
  // Store underneath it to serve an install-time asset pack.
  static const _directAssetPath = 'assets/models/gemma-4-E4B-it-gpu.litertlm';
  // Only used when AiConfig.modelSource == 'download' (the direct-download APK, GitHub Releases'
  // own 2GB-per-file cap ruled out shipping the ~2.77GB model inside that APK at all) — the exact
  // same public URL scripts/fetch_ai_model.sh already fetches at BUILD time, fetched instead at
  // RUNTIME, on-device, once, on first launch. No token, no auth — the litert-community repo on
  // Hugging Face is public.
  //
  // THREE CANDIDATES, TRIED STRONGEST TO WEAKEST — found live (2026-09-28): "Failed to create
  // engine. Model may be invalid" on Gemma 4 E4B is a widely-reported, Google-acknowledged upstream
  // regression (google-ai-edge/LiteRT-LM#1864, google-ai-edge/gallery#557), not something wrong
  // with our own download or device — it fails identically on GPU and CPU, and even inside
  // Google's own model Gallery app, on a range of real chipsets. There is no fix we can ship for a
  // bug in someone else's runtime/model pair. Each fallback is a genuinely DIFFERENT model (not a
  // re-download of the same broken bytes), so a device that can't init one gets a real independent
  // next attempt instead of a permanent dead end. Owner's own explicit ordering (2026-09-28,
  // discussed and compared): E4B (best quality) → E2B (same family, ~1/3 the size, still
  // Gemma-native tool-calling) → Qwen3-0.6B (last resort only — a real, verified-working litertlm
  // build, ~1/4 E2B's size and far less capable, but Qwen's own broader multilingual training
  // means it is not obviously worse than E2B specifically on Arabic, and it is small enough that
  // an init failure here would point at something more fundamental than model incompatibility).
  static const _networkCandidates = [
    (
      modelType: ModelType.gemma4,
      url: 'https://huggingface.co/litert-community/gemma-4-E4B-it-litert-lm/resolve/main/gemma-4-E4B-it-gpu.litertlm',
    ),
    (
      modelType: ModelType.gemma4,
      url: 'https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm/resolve/main/gemma-4-E2B-it-gpu.litertlm',
    ),
    (
      modelType: ModelType.qwen3,
      url: 'https://huggingface.co/litert-community/Qwen3-0.6B/resolve/main/qwen3_0_6b_mixed_int4.litertlm',
    ),
  ];

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

  String? _lastError;

  @override
  String? get lastError => _lastError;

  void _setStatus(AiModelStatus next) {
    _status = next;
    _statusController.add(next);
  }

  @override
  Future<void> ensureReady({List<AiTool> tools = const []}) async {
    if (_status == AiModelStatus.ready) return;

    if (AiConfig.modelSource == 'download') {
      // STRONGEST TO WEAKEST — see [_networkCandidates]'s own doc comment for why this is a real
      // fallback chain of different models, not a naive retry of the same broken download.
      Object? lastError;
      for (final candidate in _networkCandidates) {
        // PURGE ANY STALE PARTIAL BEFORE EVERY ATTEMPT, not just after a whole-method retry —
        // found live (2026-09-28): a download interrupted before this device ever got the
        // foreground-service fix (v0.1.11 and earlier) can leave a corrupt/incomplete file on
        // disk with its own "already handled" bookkeeping. The OS-level downloader reattaches to
        // that same on-disk state by a path-derived id, not by content — so a later candidate in
        // this SAME loop could otherwise inherit a previous candidate's leftover state too.
        // performCleanup() is flutter_gemma's own official answer: "delete orphaned files and
        // stale metadata left by interrupted installs."
        if (_status == AiModelStatus.error || _status == AiModelStatus.downloading) {
          try {
            await FlutterGemma.performCleanup();
          } catch (_) {
            // Best-effort — a cleanup failure must not block the attempt it exists to unblock.
          }
        }
        try {
          _setStatus(AiModelStatus.downloading);
          final installer = FlutterGemma.installModel(
            modelType: candidate.modelType,
            fileType: ModelFileType.litertlm,
          );
          // Direct-download APK, model fetched AFTER install (GitHub Releases' 2GB-per-file cap —
          // see this class's own header comment). `.fromNetwork` is flutter_gemma's own
          // downloader: resumable, and it re-uses whatever it already staged on a previous
          // ensureReady() that got interrupted rather than starting over.
          // foreground: true — WITHOUT IT, background_downloader never calls Android's
          // WorkManager.setForeground(), regardless of the manifest permissions already declared
          // (found live 2026-09-28: the manifest fix alone did nothing, because nothing in this
          // file ever asked for the service the manifest merely allows). A multi-GB transfer with
          // no foreground service is the OS's to kill on a whim; this is the flag that actually
          // shows the "Downloading model" notification and keeps it alive.
          await installer
              .fromNetwork(candidate.url, foreground: true)
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
          // else, per ai_model.dart's own doc comment on why. modelType matches whichever
          // candidate just loaded — Qwen3's own chat template is not Gemma's.
          final chat = await model.createChat(modelType: candidate.modelType, tools: _convertTools(tools));
          _model = model;
          _chat = chat;
          _setStatus(AiModelStatus.ready);
          return;
        } catch (e) {
          lastError = e;
          // Try the next candidate — never rethrown here, only after the last one also fails.
        }
      }
      // NEVER RETHROWN — see AiModel.ensureReady's own doc comment: a failed model load degrades
      // the assistant surface, it does not crash whatever screen opened it. The last candidate's
      // exception is kept on [lastError] so a caller CAN still learn why, on demand.
      _lastError = lastError?.toString();
      _setStatus(AiModelStatus.error);
      return;
    }

    // 'asset' and 'pack' modes: ONE fixed on-device file, not a fallback chain — see this class's
    // own header comment on why those two never fetch a candidate list. Never rethrown, same as
    // the 'download' branch above.
    try {
      _setStatus(AiModelStatus.downloading);
      final installer = FlutterGemma.installModel(
        modelType: ModelType.gemma4,
        fileType: ModelFileType.litertlm,
      );
      if (AiConfig.modelSource == 'asset') {
        // Direct-download build with the model still bundled in-APK (scripts/build_apk_direct.sh,
        // kept as the other direct-build option — see AiConfig.modelSource's own doc comment).
        // No Play Store underneath a sideloaded APK, so no asset pack to fetch(); the file is
        // just a plain Flutter asset this build's pubspec.yaml declares.
        await installer
            .fromAsset(_directAssetPath)
            .withProgress((progress) => _progressController.add(progress))
            .install();
      } else {
        // RESOLVED AT RUNTIME, NEVER A STATIC ASSET KEY — see this class's own doc comment.
        // `MainActivity.kt` returns immediately if Play already staged the pack (the ordinary
        // install-time case); the progress stream only carries real events on the rarer path
        // where it has to fetch() first (a fresh install caught mid-sync, or a local/debug run).
        late final StreamSubscription<dynamic> progressSub;
        progressSub = _progressChannel.receiveBroadcastStream().listen(
          (event) => _progressController.add((event as num).toInt()),
        );
        final String modelFilePath;
        try {
          modelFilePath = await _methodChannel.invokeMethod<String>('ensureInstalled') as String;
        } finally {
          await progressSub.cancel();
        }
        // BUNDLED, NEVER NETWORK — see this class's own doc comment. `.install()` here is a
        // local copy out of the pack's own on-device storage into the plugin's own writable
        // storage on first run (still worth the progress stream above: a 2.77GB copy is not
        // instant), never an HTTP request.
        await installer
            .fromFile(modelFilePath)
            .withProgress((progress) => _progressController.add(progress))
            .install();
      }

      _setStatus(AiModelStatus.loading);
      final model = await FlutterGemma.getActiveModel(
        maxTokens: 2048,
        preferredBackend: PreferredBackend.gpu,
      );
      final chat = await model.createChat(modelType: ModelType.gemma4, tools: _convertTools(tools));
      _model = model;
      _chat = chat;
      _setStatus(AiModelStatus.ready);
    } catch (e) {
      _lastError = e.toString();
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
