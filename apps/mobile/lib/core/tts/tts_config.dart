/// Which [TtsModel] adapter to build — compile-time only (`--dart-define`), same convention as
/// [AiConfig] (lib/core/ai/ai_config.dart).
///
/// DEFAULTS TO OFF, same reasoning as [AiConfig]: a build that sets nothing ships with no spoken
/// output at all, until the assistant surface that would actually use this is real and this is
/// deliberately turned on for it.
class TtsConfig {
  TtsConfig._();

  /// 'null' (default, feature off) | 'platform' (the device's own TTS engine via flutter_tts).
  /// Set via: flutter run --dart-define=TTS_MODEL_DRIVER=platform
  static const String modelDriver = String.fromEnvironment('TTS_MODEL_DRIVER', defaultValue: 'null');
}
