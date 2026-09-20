import 'package:raje3_mobile/core/voice/adapters/null_speech_input_model.dart';
import 'package:raje3_mobile/core/voice/adapters/platform_speech_input_model.dart';
import 'package:raje3_mobile/core/voice/speech_input_config.dart';
import 'package:raje3_mobile/core/voice/speech_input_model.dart';

/// Build the one [SpeechInputModel] this session uses — the mobile mirror of [buildAiModel]
/// (lib/core/ai/ai_container.dart) and [buildTtsModel] (lib/core/tts/tts_container.dart): a
/// driver string picks an adapter, nothing else constructs one by hand.
SpeechInputModel buildSpeechInputModel() {
  switch (SpeechInputConfig.modelDriver) {
    case 'platform':
      return PlatformSpeechInputModel();
    default:
      return NullSpeechInputModel();
  }
}
