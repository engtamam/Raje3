import 'package:raje3_mobile/core/ai/ai_model.dart';

/// The safe default — the on-device assistant simply is not there. Never downloads anything,
/// never pretends to be ready, never throws past itself. Exactly the same "off means off,
/// safely" posture every other null adapter in this product already holds to (NullPlans,
/// NullConnections, NullEntitlements on the platform side, ...).
class NullAiModel implements AiModel {
  @override
  String get driver => 'null';

  @override
  AiModelStatus get status => AiModelStatus.unavailable;

  @override
  Stream<AiModelStatus> get statusStream => Stream.value(AiModelStatus.unavailable);

  @override
  Stream<int> get downloadProgress => const Stream.empty();

  @override
  Future<void> ensureReady({List<AiTool> tools = const []}) async {}

  @override
  Stream<AiEvent> generate(String prompt, {String systemInstruction = ''}) {
    // A CALLER BUG, NOT A RUNTIME CONDITION — every real screen checks `status` before calling
    // this (see AiModel's own doc comment); the null adapter's status is always `unavailable`,
    // so reaching here means that check was skipped.
    throw StateError('NullAiModel cannot generate — check AiModel.status before calling generate().');
  }

  @override
  Future<void> dispose() async {}
}
