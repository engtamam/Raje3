import 'package:flutter_test/flutter_test.dart';
import 'package:raje3_mobile/core/ai/adapters/null_ai_model.dart';
import 'package:raje3_mobile/core/ai/ai_config.dart';
import 'package:raje3_mobile/core/ai/ai_container.dart';
import 'package:raje3_mobile/core/ai/ai_model.dart';

void main() {
  group('NullAiModel', () {
    test('is always unavailable and never downloads', () async {
      final model = NullAiModel();
      expect(model.driver, 'null');
      expect(model.status, AiModelStatus.unavailable);
      await model.ensureReady();
      expect(model.status, AiModelStatus.unavailable);
    });

    test('generate() is a caller bug, not a runtime condition', () {
      final model = NullAiModel();
      expect(() => model.generate('hi'), throwsStateError);
    });

    test('dispose() never throws even though nothing was ever opened', () async {
      await NullAiModel().dispose();
    });
  });

  group('buildAiModel', () {
    test('defaults to NullAiModel with nothing configured', () {
      expect(AiConfig.modelDriver, 'null');
      expect(buildAiModel(), isA<NullAiModel>());
    });
  });
}
