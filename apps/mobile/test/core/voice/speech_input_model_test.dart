import 'package:flutter_test/flutter_test.dart';
import 'package:raje3_mobile/core/voice/adapters/null_speech_input_model.dart';
import 'package:raje3_mobile/core/voice/speech_input_config.dart';

void main() {
  group('NullSpeechInputModel', () {
    test('never claims availability and never listens', () async {
      final speech = NullSpeechInputModel();
      expect(speech.driver, 'null');
      expect(await speech.isAvailable(), isFalse);
    });

    test('startListening() is a caller bug, not a runtime condition', () async {
      final speech = NullSpeechInputModel();
      expect(
        () => speech.startListening(languageCode: 'ar-SA', onResult: (_, {required isFinal}) {}),
        throwsA(isA<StateError>()),
      );
    });

    test('cancel/dispose never throw even though nothing was ever opened', () async {
      final speech = NullSpeechInputModel();
      await speech.cancel();
      await speech.dispose();
    });
  });

  group('buildSpeechInputModel', () {
    // THE REAL DEFAULT NOW (owner's own decision, 2026-09-21) — 'platform'.
    test('defaults to platform driver with nothing configured', () {
      expect(SpeechInputConfig.modelDriver, 'platform');
    });
  });
}
