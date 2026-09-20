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
  /// to the .task/.litertlm file (LiteRT/MediaPipe format), never a Kaggle/HuggingFace PAGE.
  /// Left empty until the model is actually hosted somewhere this app can reach without a
  /// per-request user credential — a real decision, not yet made, so it is not guessed here.
  static const String gemmaModelUrl = String.fromEnvironment('AI_GEMMA_MODEL_URL');

  /// A bearer token for [gemmaModelUrl], if the host requires one (e.g. a gated HuggingFace
  /// download). Empty means "no auth needed" — never a real secret checked into source.
  static const String gemmaModelToken = String.fromEnvironment('AI_GEMMA_MODEL_TOKEN');
}
