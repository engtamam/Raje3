import 'package:raje3_mobile/core/wakeword/adapters/null_wake_word_model.dart';
import 'package:raje3_mobile/core/wakeword/adapters/platform_wake_word_model.dart';
import 'package:raje3_mobile/core/wakeword/wake_word_config.dart';
import 'package:raje3_mobile/core/wakeword/wake_word_model.dart';

/// Build the one [WakeWordModel] this session uses — the mobile mirror of [buildAiModel]
/// (lib/core/ai/ai_container.dart), [buildTtsModel] (lib/core/tts/tts_container.dart), and
/// [buildSpeechInputModel] (lib/core/voice/speech_input_container.dart): a driver string picks
/// an adapter, nothing else constructs one by hand.
WakeWordModel buildWakeWordModel() {
  switch (WakeWordConfig.modelDriver) {
    case 'platform':
      return PlatformWakeWordModel();
    default:
      return NullWakeWordModel();
  }
}
