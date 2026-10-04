/// Maps this app's own bare language code (`S.supportedLocales`, e.g. `'ar'`) to a full BCP-47
/// speech-engine tag (e.g. `'ar-SA'`) — both [SpeechInputModel.startListening] and
/// [TtsModel.speak] document that they want one of these, never a bare ISO 639-1 code, and every
/// call site used to pass `Localizations.localeOf(context).languageCode` straight through instead.
///
/// FOUND LIVE (owner's own report, 2026-09-29): Arabic replies sounded badly synthesized — a bare
/// `'ar'` handed to Android's own `TextToSpeech.setLanguage` does not reliably resolve to the same
/// high-quality regional voice a full tag does; the engine falls back to whatever generic default
/// it has for the language family. This is the device's own native TTS (the same engine behind
/// TalkBack/VoiceOver), not a separate one this app ships — the missing region tag was the entire
/// gap.
///
/// One region per supported language, picked for the establishment's own real customer base
/// (Saudi-market product) rather than a language's most populous country in general.
String speechLocaleTag(String languageCode) => switch (languageCode) {
      'ar' => 'ar-SA',
      'en' => 'en-US',
      'ur' => 'ur-PK',
      'ha' => 'ha-NG',
      'fil' => 'fil-PH',
      'bn' => 'bn-BD',
      _ => languageCode,
    };
