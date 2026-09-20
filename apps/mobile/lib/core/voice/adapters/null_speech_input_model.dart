import 'package:raje3_mobile/core/voice/speech_input_model.dart';

/// The safe default — the microphone is never opened. Same "off means off, safely" posture as
/// [NullAiModel]/[NullTtsModel]: never throws past itself, never claims availability.
class NullSpeechInputModel implements SpeechInputModel {
  @override
  String get driver => 'null';

  @override
  Future<bool> isAvailable() async => false;

  @override
  Future<void> startListening({
    required String languageCode,
    required void Function(String text, {required bool isFinal}) onResult,
  }) async {
    // A CALLER BUG, NOT A RUNTIME CONDITION — every real caller checks isAvailable() first
    // (see SpeechInputModel's own doc comment); this adapter's isAvailable() is always false.
    throw StateError('NullSpeechInputModel cannot listen — check isAvailable() before calling startListening().');
  }

  @override
  Future<void> cancel() async {}

  @override
  Future<void> dispose() async {}
}
