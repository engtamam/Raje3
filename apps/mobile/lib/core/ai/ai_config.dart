/// Which [AiModel] adapter to build, and what the 'gemma' adapter needs to fetch its model —
/// compile-time only (`--dart-define`), the same convention `ApiConstants._envUrl` already uses.
///
/// DEFAULTS TO OFF. `modelDriver` defaults to 'null': a build that sets nothing ships with no
/// on-device model at all, the same fail-closed default every driver-selected port in this
/// product already holds to (BILLING_PLANS_DRIVER, ENTITLEMENTS_RESOLVER_DRIVER, ...). The
/// 'gemma' driver with no [gemmaModelUrl] configured is ALSO treated as off by
/// `buildAiModel()` (see ai_container.dart) — a half-configured driver must never half-work.
class AiConfig {
  AiConfig._();

  /// 'null' (default, feature off) | 'gemma' (on-device Gemma 4 via flutter_gemma).
  /// Set via: flutter run --dart-define=AI_MODEL_DRIVER=gemma
  static const String modelDriver = String.fromEnvironment('AI_MODEL_DRIVER', defaultValue: 'null');

  /// Where the 'gemma' adapter downloads the model file from — a direct, publicly-fetchable URL
  /// to the .litertlm file (LiteRT/MediaPipe format), never a Kaggle/HuggingFace PAGE.
  ///
  /// THE OWNER'S OWN DECISION (2026-09-20): point directly at the model's real HuggingFace host
  /// rather than mirror the multi-GB file on our own storage — we do not have a paid public
  /// object-storage/CDN subscription set up yet, and litert-community's own repo is a genuine,
  /// ungated (`"gated": false`, confirmed via the HF API), Apache-2.0 release of Gemma 4, so a
  /// third party is fine here in a way it would not be for anything carrying our own users' data.
  ///
  /// litert-community/gemma-4-E4B-it-litert-lm — E4B (the larger, more capable variant, the
  /// owner's own choice over the smaller E2B) — the "-gpu" file, matching
  /// GemmaAiModel.ensureReady()'s own `PreferredBackend.gpu` request; confirmed reachable via a
  /// real HEAD request (200, content-length ~2.77GiB) before this URL was set as the default.
  static const String gemmaModelUrl = String.fromEnvironment(
    'AI_GEMMA_MODEL_URL',
    defaultValue:
        'https://huggingface.co/litert-community/gemma-4-E4B-it-litert-lm/resolve/main/gemma-4-E4B-it-gpu.litertlm',
  );

  /// A bearer token for [gemmaModelUrl], if the host ever requires one. Empty here because the
  /// repo above is confirmed ungated — never a real secret checked into source regardless.
  static const String gemmaModelToken = String.fromEnvironment('AI_GEMMA_MODEL_TOKEN');
}
