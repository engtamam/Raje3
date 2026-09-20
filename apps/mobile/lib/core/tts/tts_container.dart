import 'package:raje3_mobile/core/tts/adapters/null_tts_model.dart';
import 'package:raje3_mobile/core/tts/adapters/platform_tts_model.dart';
import 'package:raje3_mobile/core/tts/tts_config.dart';
import 'package:raje3_mobile/core/tts/tts_model.dart';

/// Build the one [TtsModel] this session uses — the mobile mirror of [buildAiModel]
/// (lib/core/ai/ai_container.dart): a driver string picks an adapter, nothing else constructs
/// one by hand.
TtsModel buildTtsModel() {
  switch (TtsConfig.modelDriver) {
    case 'platform':
      return PlatformTtsModel();
    default:
      return NullTtsModel();
  }
}
