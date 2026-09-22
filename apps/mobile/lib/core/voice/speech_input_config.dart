/// Which [SpeechInputModel] adapter to build — compile-time only (`--dart-define`), the same
/// convention [AiConfig]/[TtsConfig] already use.
///
/// DEFAULTS TO ON, same owner decision as [AiConfig]/[TtsConfig] (2026-09-21): the surface that
/// uses this is real now, so a build that sets nothing ships WITH microphone access —
/// `_DRIVER=null` remains the escape hatch for a build that must not open the microphone.
class SpeechInputConfig {
  SpeechInputConfig._();

  /// 'platform' (default, the device's own speech recognizer via speech_to_text) | 'null'
  /// (feature off). Set via: flutter run --dart-define=SPEECH_INPUT_DRIVER=null
  static const String modelDriver = String.fromEnvironment('SPEECH_INPUT_DRIVER', defaultValue: 'platform');
}
