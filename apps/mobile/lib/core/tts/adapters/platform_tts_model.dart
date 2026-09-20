import 'dart:async';

import 'package:flutter_tts/flutter_tts.dart';
import 'package:raje3_mobile/core/tts/tts_model.dart';

/// The device's own TTS engine (Android's TextToSpeech, iOS's AVSpeechSynthesizer) via the
/// `flutter_tts` plugin — no model to download, entirely on-device already.
///
/// NOT A SINGLETON QUEUE OF ITS OWN. `flutter_tts`'s own `speak()` already returns a Future that
/// resolves once the engine reports completion (via its internal completion handler) — this
/// adapter wires that same handler into [speak]'s own Future rather than adding a second queue on
/// top of the plugin's, which is exactly the kind of duplicated state that drifts.
class PlatformTtsModel implements TtsModel {
  PlatformTtsModel() : _tts = FlutterTts() {
    _tts.setCompletionHandler(() => _resolveCurrent());
    _tts.setCancelHandler(() => _resolveCurrent());
    _tts.setErrorHandler((_) => _resolveCurrent());
  }

  final FlutterTts _tts;
  Completer<void>? _current;

  void _resolveCurrent() {
    if (_current != null && !_current!.isCompleted) _current!.complete();
  }

  @override
  String get driver => 'platform';

  @override
  Future<bool> isLanguageAvailable(String languageCode) async {
    try {
      final result = await _tts.isLanguageAvailable(languageCode);
      return result == true || result == 1;
    } catch (_) {
      return false;
    }
  }

  @override
  Future<void> speak(String text, {required String languageCode}) async {
    if (text.trim().isEmpty) return;
    try {
      await _tts.setLanguage(languageCode);
      final completer = Completer<void>();
      _current = completer;
      await _tts.speak(text);
      await completer.future;
    } catch (_) {
      // NEVER RETHROWN — see TtsModel.speak's own doc comment: a broken voice engine degrades
      // to text-only silently, it does not crash whatever screen asked for it to speak.
    }
  }

  @override
  Future<void> stop() async {
    try {
      await _tts.stop();
    } catch (_) {}
    _resolveCurrent();
  }

  @override
  Future<void> dispose() async {
    await stop();
  }
}
