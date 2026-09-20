import 'package:raje3_mobile/core/voice/speech_input_model.dart';
import 'package:speech_to_text/speech_to_text.dart';

/// The device's own speech recognizer (Android SpeechRecognizer, iOS SFSpeechRecognizer) via the
/// `speech_to_text` plugin — no model to download, entirely on-device already (subject to the OS
/// vendor's own recognizer behaviour, see SpeechInputModel's own doc comment).
class PlatformSpeechInputModel implements SpeechInputModel {
  final SpeechToText _speech = SpeechToText();
  bool _initialized = false;

  @override
  String get driver => 'platform';

  @override
  Future<bool> isAvailable() async {
    if (_initialized) return true;
    try {
      _initialized = await _speech.initialize();
      return _initialized;
    } catch (_) {
      return false;
    }
  }

  @override
  Future<void> startListening({
    required String languageCode,
    required void Function(String text, {required bool isFinal}) onResult,
  }) async {
    if (!_initialized && !await isAvailable()) return;
    await _speech.listen(
      onResult: (result) => onResult(result.recognizedWords, isFinal: result.finalResult),
      listenOptions: SpeechListenOptions(localeId: languageCode, cancelOnError: true),
    );
  }

  @override
  Future<void> cancel() async {
    try {
      await _speech.cancel();
    } catch (_) {
      // NEVER RETHROWN — see SpeechInputModel.cancel's own doc comment: this is the "tap to
      // cancel" action and must always succeed from the caller's point of view.
    }
  }

  @override
  Future<void> dispose() async {
    await cancel();
  }
}
