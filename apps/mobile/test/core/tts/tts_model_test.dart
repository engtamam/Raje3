import 'package:flutter_test/flutter_test.dart';
import 'package:raje3_mobile/core/tts/adapters/null_tts_model.dart';
import 'package:raje3_mobile/core/tts/tts_config.dart';
import 'package:raje3_mobile/core/tts/tts_container.dart';

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
    test('defaults to NullTtsModel with nothing configured', () {
      expect(TtsConfig.modelDriver, 'null');
      expect(buildTtsModel(), isA<NullTtsModel>());
    });
  });
}
