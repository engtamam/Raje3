/// Speech OUTPUT — a PORT, entirely separate from [AiModel] (lib/core/ai/ai_model.dart).
///
/// WHY A SECOND PORT, NOT A METHOD ON [AiModel]. Gemma understands speech natively (audio IN),
/// but it never generates speech — its own answer is always text. Turning that text into a
/// spoken voice is a completely different runtime with a completely different failure mode (an
/// unsupported device locale, not a missing model file), so folding it into the same interface
/// would force every AI adapter to also carry TTS concerns it has nothing to do with. One port
/// per real capability, exactly the reasoning [AiModel]'s own doc comment gives for existing at
/// all.
///
/// STILL ENTIRELY ON-DEVICE. The default adapter wraps the PLATFORM's own TTS engine (Android's
/// TextToSpeech, iOS's AVSpeechSynthesizer via the `flutter_tts` plugin) — no model download, no
/// server call, the same "nothing about this ever leaves the device" posture [AiModel] holds to.
abstract class TtsModel {
  /// 'null' (feature off) or 'platform' (the device's own TTS engine). Diagnostics only.
  String get driver;

  /// Whether this device can actually speak the requested language right now. A caller should
  /// check this before [speak] — a language with no installed voice is a real, common case
  /// (many Android builds ship no Arabic voice pack at all), never a bug to work around silently.
  Future<bool> isLanguageAvailable(String languageCode);

  /// Speak `text` aloud in `languageCode` (a BCP-47 tag, e.g. 'ar-SA'). Completes once speech
  /// finishes — a caller awaiting this may safely start the NEXT utterance right after. NEVER
  /// THROWS: an engine failure is swallowed and simply produces no sound, because a broken voice
  /// output must degrade the assistant to text-only, not crash whatever screen asked for it.
  Future<void> speak(String text, {required String languageCode});

  /// Stop whatever is currently being spoken — e.g. the user navigated away mid-sentence.
  Future<void> stop();

  /// Release any engine resources this adapter holds. Called when the assistant surface is no
  /// longer reachable at all, never on ordinary navigation away and back.
  Future<void> dispose();
}
