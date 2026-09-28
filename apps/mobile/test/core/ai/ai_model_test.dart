import 'package:flutter_test/flutter_test.dart';
import 'package:raje3_mobile/core/ai/adapters/gemma_ai_model.dart';
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
    // THE REAL DEFAULT NOW (owner's own decision, 2026-09-21: "خلي الميزة مفعلة كليا") — 'gemma',
    // sourced via a Play Asset Delivery pack by default (owner's own later decision, 2026-09-22:
    // see AiConfig's own doc comment), so a build with nothing set actually builds the real
    // adapter, not the null one.
    test('defaults to GemmaAiModel, sourced from the Play Asset Delivery pack, with nothing set', () {
      expect(AiConfig.modelDriver, 'gemma');
      expect(AiConfig.modelSource, 'pack');
      final model = buildAiModel();
      expect(model, isA<GemmaAiModel>());
      expect(model.status, AiModelStatus.needsDownload);
    });
  });
}
