/// Which [AiModel] adapter to build — compile-time only (`--dart-define`), the same convention
/// `ApiConstants._envUrl` already uses.
///
/// DEFAULTS TO ON (owner's own explicit decision, 2026-09-21: "خلي الميزة مفعلة كليا" — the
/// feature stays enabled by default, no `--dart-define` to remember on every run/build).
/// `modelDriver` defaults to 'gemma'; `AI_MODEL_DRIVER=null` remains the escape hatch for a build
/// that must not carry the model at all (a CI run, say — see scripts/fetch_ai_model.sh's own
/// note on skipping the fetch for that build).
///
/// ON GOOGLE PLAY, THE MODEL SHIPS WITH THE APP — owner's own explicit decision (2026-09-22):
/// "لا نبغ التطبيق ينزل معاه... مافي رابط ينزل منه" — no separate download, ever. It ships as a
/// Play Asset Delivery install-time pack (android/ai_model_pack) rather than a plain Flutter
/// asset — the raw ~2.77GB file put the whole app over Google Play's 200MB base-module cap when
/// it lived under `assets:`. `GemmaAiModel` resolves the real on-device path at runtime via
/// `MainActivity.kt`'s own MethodChannel; there is no static asset key to name here any more.
///
/// THE DIRECT-DOWNLOAD BUILD (scripts/build_apk_direct.sh) IS THE ONE EXCEPTION, AND THAT ONLY
/// GOT A NAME AFTER A REAL FAILURE (2026-09-28): its APK first shipped with the model bundled in
/// (`modelSource = 'asset'`), then `mobile_release_publish` refused it outright — GitHub Releases
/// caps a single asset at 2GB, the bundled APK was 2.6GB. `modelSource = 'download'` is the
/// owner's own fix, scoped to this one build only: the APK ships small, and `GemmaAiModel` fetches
/// the same public Hugging Face file post-install instead (flutter_gemma's own `.fromNetwork`,
/// resumable). Deliberately a FLAG, not a rewrite — the owner's own words: "نسويها بطريقة بسيطة
/// نسوي flag عليها عشان ممكن مستقبلا نغير رأينا ونخلي مدمج" (a flag, so bundled stays one build-arg
/// switch away if that changes again). `build_apk_direct.sh` defaults to `download`; passing
/// `AI_MODEL_SOURCE=asset` to it still produces the old bundled-but-oversized build for anyone who
/// needs to reproduce that failure or has a distribution channel without GitHub's cap.
///
/// See [scripts/fetch_ai_model.sh] for where the same file is fetched at BUILD time (pack/asset
/// modes), android/ai_model_pack/build.gradle.kts for the Play delivery mechanism, and
/// [GemmaAiModel] for how each of the three modes resolves the on-device path.
class AiConfig {
  AiConfig._();

  /// 'gemma' (default, on-device Gemma 4 via flutter_gemma) | 'null' (feature off — the owner's
  /// own decision to turn this OFF for a specific build, e.g. a CI run that must not carry the
  /// model): flutter run --dart-define=AI_MODEL_DRIVER=null
  static const String modelDriver = String.fromEnvironment('AI_MODEL_DRIVER', defaultValue: 'gemma');

  /// 'pack' (default, Google Play build) | 'asset' (direct-download APK, model bundled in — only
  /// still used for a channel without GitHub's 2GB asset cap) | 'download' (direct-download APK,
  /// model fetched post-install — scripts/build_apk_direct.sh's own default). See [GemmaAiModel]
  /// for how each mode resolves the on-device path.
  static const String modelSource = String.fromEnvironment('AI_MODEL_SOURCE', defaultValue: 'pack');
}
