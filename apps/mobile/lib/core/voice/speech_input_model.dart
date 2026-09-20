/// Speech INPUT — a third PORT, independent from [AiModel] (lib/core/ai/ai_model.dart) and
/// [TtsModel] (lib/core/tts/tts_model.dart). Turning a spoken question into text is a different
/// runtime with a different failure mode again (no microphone permission, no recognizer
/// installed on this device, an unsupported locale) — same "one port per real capability"
/// reasoning [AiModel]'s own doc comment gives.
///
/// STILL ENTIRELY ON-DEVICE. The default adapter wraps the platform's own speech recognizer
/// (Android's SpeechRecognizer, iOS's SFSpeechRecognizer via the `speech_to_text` plugin) —
/// no server call of ours, same posture [AiModel]/[TtsModel] both hold to. Some Android builds
/// route their OWN recognizer through Google's cloud depending on the device's own settings —
/// that is the OS vendor's behaviour, identical to how [TtsModel]'s "platform" adapter can only
/// promise what the platform itself promises, never a guarantee this port can make stronger.
abstract class SpeechInputModel {
  /// 'null' (feature off) or 'platform' (the device's own speech recognizer). Diagnostics only.
  String get driver;

  /// Whether this device can listen at all, resolved once and cached — a caller checks this
  /// before [startListening]. NEVER THROWS: a missing recognizer or a denied permission both
  /// resolve to `false`, because a caller cannot tell those apart without a live device anyway.
  Future<bool> isAvailable();

  /// Start listening in `languageCode` (a BCP-47 tag). [onResult] fires with the best-guess
  /// transcript as it forms; `isFinal` marks the recognizer's own end-of-utterance call — a
  /// caller acts on the LAST `isFinal` result, not every partial one. Listening stops on its own
  /// once the recognizer decides the utterance ended; a caller that wants it to stop sooner uses
  /// [cancel].
  Future<void> startListening({
    required String languageCode,
    required void Function(String text, {required bool isFinal}) onResult,
  });

  /// Stop listening immediately and discard whatever was heard so far — the "tap to cancel"
  /// action, never a partial answer treated as final.
  Future<void> cancel();

  /// Release any engine resources this adapter holds.
  Future<void> dispose();
}
