/// Which [SpeechInputModel] adapter to build — compile-time only (`--dart-define`), the same
/// convention [AiConfig]/[TtsConfig] already use.
///
/// DEFAULTS TO OFF, same reasoning as both: a build that sets nothing ships with no microphone
/// access at all, until the surface that would actually use it is real and this is deliberately
/// turned on for it.
class SpeechInputConfig {
  SpeechInputConfig._();

  /// 'null' (default, feature off) | 'platform' (the device's own speech recognizer via
  /// speech_to_text). Set via: flutter run --dart-define=SPEECH_INPUT_DRIVER=platform
  static const String modelDriver = String.fromEnvironment('SPEECH_INPUT_DRIVER', defaultValue: 'null');
}
