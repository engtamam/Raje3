import 'package:flutter_test/flutter_test.dart';
import 'package:raje3_mobile/core/tts/adapters/null_tts_model.dart';
import 'package:raje3_mobile/core/tts/tts_config.dart';

void main() {
  group('NullTtsModel', () {
    test('never claims a language is available', () async {
      final tts = NullTtsModel();
      expect(tts.driver, 'null');
      expect(await tts.isLanguageAvailable('ar-SA'), isFalse);
    });

    test('speak/stop/dispose never throw even though nothing ever loaded', () async {
      final tts = NullTtsModel();
      await tts.speak('hello', languageCode: 'ar-SA');
      await tts.stop();
      await tts.dispose();
    });
  });

  group('buildTtsModel', () {
    // THE REAL DEFAULT NOW (owner's own decision, 2026-09-21) — 'platform'.
    test('defaults to platform driver with nothing configured', () {
      expect(TtsConfig.modelDriver, 'platform');
    });
  });
}
