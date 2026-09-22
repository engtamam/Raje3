/// Which [TtsModel] adapter to build — compile-time only (`--dart-define`), same convention as
/// [AiConfig] (lib/core/ai/ai_config.dart).
///
/// DEFAULTS TO ON, same owner decision as [AiConfig] (2026-09-21): the assistant surface that
/// uses this is real now, so a build that sets nothing ships WITH spoken output — `_MODEL_DRIVER
/// =null` remains the escape hatch for a build that must not touch the device's TTS engine.
class TtsConfig {
  TtsConfig._();

  /// 'platform' (default, the device's own TTS engine via flutter_tts) | 'null' (feature off).
  /// Set via: flutter run --dart-define=TTS_MODEL_DRIVER=null
  static const String modelDriver = String.fromEnvironment('TTS_MODEL_DRIVER', defaultValue: 'platform');
}
