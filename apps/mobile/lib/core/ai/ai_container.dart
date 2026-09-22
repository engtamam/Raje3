import 'package:raje3_mobile/core/ai/adapters/gemma_ai_model.dart';
import 'package:raje3_mobile/core/ai/adapters/null_ai_model.dart';
import 'package:raje3_mobile/core/ai/ai_config.dart';
import 'package:raje3_mobile/core/ai/ai_model.dart';

/// Build the one [AiModel] this session uses — the mobile mirror of every backend service's own
/// `build_plans`/`build_connections` factory (services/operations/app/core/subscribe.py and
/// friends): a driver string picks an adapter, and nothing else in the app constructs one by hand.
///
/// NO SYNCHRONOUS "IS IT REALLY THERE" CHECK HERE, UNLIKE THE OLD URL-BASED DESIGN (an empty
/// string was checkable in one line; a bundled asset's real presence is not — Flutter only
/// exposes that through `rootBundle`, asynchronously). `GemmaAiModel.ensureReady()`'s own
/// try/catch is where a genuinely missing asset (a dev who forgot scripts/fetch_ai_model.sh
/// before `flutter run`) surfaces as `AiModelStatus.error` instead — a build-time mistake for
/// that dev to see immediately, not a silent fallback to [NullAiModel] that would hide it.
AiModel buildAiModel() {
  switch (AiConfig.modelDriver) {
    case 'gemma':
      return GemmaAiModel(modelAssetPath: AiConfig.gemmaModelAssetPath);
    default:
      return NullAiModel();
  }
}
