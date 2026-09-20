import 'package:raje3_mobile/core/ai/adapters/gemma_ai_model.dart';
import 'package:raje3_mobile/core/ai/adapters/null_ai_model.dart';
import 'package:raje3_mobile/core/ai/ai_config.dart';
import 'package:raje3_mobile/core/ai/ai_model.dart';

/// Build the one [AiModel] this session uses — the mobile mirror of every backend service's own
/// `build_plans`/`build_connections` factory (services/operations/app/core/subscribe.py and
/// friends): a driver string picks an adapter, and nothing else in the app constructs one by hand.
///
/// A HALF-CONFIGURED 'gemma' DRIVER IS STILL OFF. Choosing 'gemma' without setting
/// [AiConfig.gemmaModelUrl] would otherwise build an adapter that can never actually download
/// anything — worse than the null adapter, because its `status` would claim `needsDownload`
/// forever rather than the honest `unavailable`. So this falls back to [NullAiModel] in that
/// case, the same "half-configured must not half-work" rule [AiConfig]'s own doc comment states.
AiModel buildAiModel() {
  switch (AiConfig.modelDriver) {
    case 'gemma':
      if (AiConfig.gemmaModelUrl.isEmpty) return NullAiModel();
      return GemmaAiModel(modelUrl: AiConfig.gemmaModelUrl, token: AiConfig.gemmaModelToken);
    default:
      return NullAiModel();
  }
}
