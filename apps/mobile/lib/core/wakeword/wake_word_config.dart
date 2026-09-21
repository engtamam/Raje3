/// Which [WakeWordModel] adapter to build — compile-time only (`--dart-define`), the same
/// convention [AiConfig]/[TtsConfig]/[SpeechInputConfig] already use.
///
/// DEFAULTS TO OFF: a build that sets nothing never opens the microphone in the background,
/// until the surface that would actually use it is real and this is deliberately turned on.
class WakeWordConfig {
  WakeWordConfig._();

  /// 'null' (default, feature off) | 'platform' (mic + on-device tflite classifier). Set via:
  /// flutter run --dart-define=WAKE_WORD_DRIVER=platform
  static const String modelDriver = String.fromEnvironment('WAKE_WORD_DRIVER', defaultValue: 'null');
}
