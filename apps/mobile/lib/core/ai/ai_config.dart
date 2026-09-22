/// Which [AiModel] adapter to build, and where the 'gemma' adapter finds its model file —
/// compile-time only (`--dart-define`), the same convention `ApiConstants._envUrl` already uses.
///
/// DEFAULTS TO ON (owner's own explicit decision, 2026-09-21: "خلي الميزة مفعلة كليا" — the
/// feature stays enabled by default, no `--dart-define` to remember on every run/build).
/// `modelDriver` defaults to 'gemma'; `AI_MODEL_DRIVER=null` remains the escape hatch for a build
/// that must not carry the model at all (a CI run, say — see scripts/fetch_ai_model.sh's own
/// note on skipping the fetch for that build). The 'gemma' driver with the asset genuinely
/// missing on disk is STILL treated as off by `buildAiModel()` (see ai_container.dart) — a
/// half-configured driver must never half-work, default or not.
class AiConfig {
  AiConfig._();

  /// 'gemma' (default, on-device Gemma 4 via flutter_gemma) | 'null' (feature off — the owner's
  /// own decision to turn this OFF for a specific build, e.g. a CI run that must not carry the
  /// model): flutter run --dart-define=AI_MODEL_DRIVER=null
  static const String modelDriver = String.fromEnvironment('AI_MODEL_DRIVER', defaultValue: 'gemma');

  /// Where the app-bundled model file lives — a real Flutter asset (`pubspec.yaml`'s own
  /// `flutter: assets:` list), NOT a URL. `GemmaAiModel` installs it via `flutter_gemma`'s own
  /// `.fromAsset(...)`, a local copy out of the app package, never a network request.
  ///
  /// THE OWNER'S OWN EXPLICIT REVERSAL (2026-09-22) of the earlier "download after install"
  /// design (that version's own `gemmaModelUrl`/`gemmaModelToken` are gone — see git history for
  /// the shape this replaced). Owner's own words: "لا نبغ التطبيق ينزل معاه... مافي رابط ينزل
  /// منه" — the model ships WITH the app, no separate download, ever. Accepted trade-off, stated
  /// back to the owner and confirmed before this landed: the shipped app is now ~2.77GB heavier,
  /// and a model UPDATE needs a full store release (no more "change the URL, nobody re-installs
  /// anything") — see [scripts/fetch_ai_model.sh] for the one place that trade-off is paid at
  /// BUILD time instead of every user's own install time.
  ///
  /// THE FILE ITSELF IS NEVER COMMITTED TO GIT (`.gitignore` excludes `assets/models/`) — a
  /// 2.77GB binary in source control is its own real problem (repo size forever, every clone,
  /// every CI checkout) independent of the "bundled vs downloaded AT RUNTIME" decision above.
  /// [scripts/fetch_ai_model.sh] fetches the real file from litert-community's own HuggingFace
  /// host (litert-community/gemma-4-E4B-it-litert-lm, the "-gpu" file, Apache-2.0, confirmed
  /// ungated) to exactly this path BEFORE `flutter build`/`flutter run` — a real build-time step,
  /// documented there, not assumed.
  static const String gemmaModelAssetPath = 'assets/models/gemma-4-E4B-it-gpu.litertlm';
}
