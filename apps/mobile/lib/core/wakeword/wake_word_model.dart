/// Wake word ("راجِع") — a FOURTH port, independent from [AiModel], [TtsModel], and
/// [SpeechInputModel] (see each of their own doc comments for why this project keeps one port
/// per real capability rather than one do-everything voice class): continuously listening for a
/// name has nothing to do with turning a recognized utterance into text, generating an answer, or
/// speaking one back, and its own failure modes (no microphone permission, the trained model
/// asset missing, the app backgrounded) belong to none of them.
///
/// ENTIRELY ON-DEVICE, same posture every other port here holds: the trained classifier
/// (`assets/wakeword/raje_wakeword.tflite`) and the raw microphone audio never leave the device;
/// nothing here ever calls our own servers or anyone else's.
abstract class WakeWordModel {
  /// 'null' (feature off) or 'platform' (mic + on-device tflite classifier). Diagnostics only.
  String get driver;

  /// Whether this device can listen for the wake word at all — the trained model asset loads
  /// successfully and microphone access can be requested. NEVER THROWS: any failure (denied
  /// permission, missing/corrupt asset, unsupported platform) resolves to `false`, same
  /// "caller checks first" contract [SpeechInputModel.isAvailable] already uses.
  Future<bool> isAvailable();

  /// Start continuously listening for the wake word. [onDetected] fires at most once per
  /// [start] call — detecting the word stops listening automatically (a caller that wants to
  /// keep listening afterward calls [start] again, typically once whatever the wake word
  /// triggered has finished). Calling [start] while already listening is a no-op.
  Future<void> start({required void Function() onDetected});

  /// Stop listening without having detected anything — the app being backgrounded, or the
  /// caller no longer wanting passive listening. Safe to call even when not currently listening.
  Future<void> stop();

  /// Whether [start] has been called and [stop]/[onDetected] hasn't fired yet.
  bool get isListening;

  /// Release any engine/microphone resources this adapter holds.
  Future<void> dispose();
}
