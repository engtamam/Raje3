import 'package:raje3_mobile/core/tts/tts_model.dart';

/// The safe default — nothing ever speaks. Same "off means off, safely" posture as
/// [NullAiModel] (lib/core/ai/adapters/null_ai_model.dart): never throws, never claims a
/// language is available, never makes a sound.
class NullTtsModel implements TtsModel {
  @override
  String get driver => 'null';

  @override
  Future<bool> isLanguageAvailable(String languageCode) async => false;

  @override
  Future<void> speak(String text, {required String languageCode}) async {}

  @override
  Future<void> stop() async {}

  @override
  Future<void> dispose() async {}
}
