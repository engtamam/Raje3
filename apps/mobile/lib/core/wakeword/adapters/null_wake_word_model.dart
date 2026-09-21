import 'package:raje3_mobile/core/wakeword/wake_word_model.dart';

/// The safe default — the microphone is never opened. Same "off means off, safely" posture as
/// [NullSpeechInputModel]/[NullTtsModel]/[NullAiModel]: never throws past itself, never claims
/// availability.
class NullWakeWordModel implements WakeWordModel {
  @override
  String get driver => 'null';

  @override
  Future<bool> isAvailable() async => false;

  @override
  Future<void> start({required void Function() onDetected}) async {
    // A CALLER BUG, NOT A RUNTIME CONDITION — every real caller checks isAvailable() first (see
    // WakeWordModel's own doc comment); this adapter's isAvailable() is always false.
    throw StateError('NullWakeWordModel cannot listen — check isAvailable() before calling start().');
  }

  @override
  Future<void> stop() async {}

  @override
  bool get isListening => false;

  @override
  Future<void> dispose() async {}
}
