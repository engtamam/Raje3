/// Which [WakeWordModel] adapter to build — compile-time only (`--dart-define`), the same
/// convention [AiConfig]/[TtsConfig]/[SpeechInputConfig] already use.
///
/// DEFAULTS TO ON, same owner decision as the rest of this file's own siblings (2026-09-21): a
/// build that sets nothing now opens the microphone in the background for wake-word detection —
/// `_DRIVER=null` remains the escape hatch for a build that must not.
class WakeWordConfig {
  WakeWordConfig._();

  /// 'platform' (default, mic + on-device tflite classifier) | 'null' (feature off). Set via:
  /// flutter run --dart-define=WAKE_WORD_DRIVER=null
  static const String modelDriver = String.fromEnvironment('WAKE_WORD_DRIVER', defaultValue: 'platform');
}
