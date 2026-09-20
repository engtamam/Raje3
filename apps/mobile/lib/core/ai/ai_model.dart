/// The on-device AI assistant — a PORT, never a concrete model.
///
/// EVERYTHING STAYS ON THE DEVICE. The prompt, the model's own weights, and the answer never
/// cross to our own servers — this is the owner's own explicit instruction (2026-09-20): "كل شي
/// بالكامل على الجهاز" (everything, entirely, on the device). There is no server-side counterpart
/// to gate, throttle or log against for this feature; a screen that wants the assistant talks to
/// this port and nothing else.
///
/// A PORT SO THE MODEL CAN BE SWAPPED WITHOUT TOUCHING A SCREEN. Today's concrete model is Gemma 4
/// E4B via the `flutter_gemma` plugin — chosen for its Apache 2.0 licence (Gemma 3 and earlier
/// carry Gemma's own Terms of Use with a Prohibited-Use Policy that would flow down onto our
/// shop-owner users; Apache 2.0 carries none). A bigger/smaller Gemma, or an entirely different
/// on-device runtime, becomes ONE new adapter implementing this same port — never a change to
/// whatever screen calls [generate].
///
/// MIRRORS THE SAME SHAPE ALREADY PROVEN SERVER-SIDE. `platform/services/assistant-service`'s own
/// `Model`/`EntitlementResolver` ports (a tiny interface, a `driver` name, a null adapter that is
/// always safe with nothing configured) are the exact pattern this file follows — same discipline,
/// same reason: a caller that could reach into concrete model internals is a caller that breaks
/// the moment the model changes.
abstract class AiModel {
  /// Which adapter this is — 'null' (feature off) or 'gemma' (on-device Gemma 4). Diagnostics
  /// only, never a branch outside this file — the same posture every backend port's own `driver`
  /// field already holds to.
  String get driver;

  /// The model's current lifecycle state. A caller reads this, never assumes [AiModelStatus.ready].
  AiModelStatus get status;

  /// Fires every time [status] changes.
  Stream<AiModelStatus> get statusStream;

  /// Download progress, 0–100. Only meaningful while [status] is [AiModelStatus.downloading] —
  /// a driver with nothing to download (the null adapter) never emits on this stream at all.
  Stream<int> get downloadProgress;

  /// Get the model into [AiModelStatus.ready] — downloads and loads it on the first call, a
  /// no-op once it already is ready. NEVER THROWS: a failure moves [status] to
  /// [AiModelStatus.error] instead, because a failed model load must silently degrade the
  /// assistant surface, not crash whatever screen happened to open it first.
  Future<void> ensureReady();

  /// Ask the model something, streaming its answer token by token. The caller must not call this
  /// before [status] is [AiModelStatus.ready] — see [ensureReady]; an adapter is free to throw
  /// [StateError] if it is called too early, since that is a caller bug, not a runtime condition
  /// a user can hit through the UI this port is meant to protect.
  Stream<String> generate(String prompt, {String systemInstruction = ''});

  /// Release the model's memory — called when the assistant surface is no longer reachable at
  /// all (e.g. the session signs out), never on ordinary navigation away and back.
  Future<void> dispose();
}

enum AiModelStatus {
  /// Nothing configured, or this device does not meet the model's own requirements. The null
  /// adapter's only state, and a real adapter's honest answer when the device itself cannot run
  /// the model — never a guess dressed up as [ready].
  unavailable,

  /// Configured and capable, but the model file has not been downloaded and loaded yet.
  needsDownload,

  /// [ensureReady] is fetching the model file. [AiModel.downloadProgress] is live during this
  /// state.
  downloading,

  /// The file is on disk; the runtime is loading it into memory.
  loading,

  /// [AiModel.generate] may be called.
  ready,

  /// [ensureReady] failed — a corrupt download, an unsupported device, a runtime crash. The
  /// assistant surface shows this as "not available right now", never a stack trace.
  error,
}
