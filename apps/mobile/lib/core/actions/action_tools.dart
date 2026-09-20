import 'package:raje3_mobile/core/actions/action_model.dart';
import 'package:raje3_mobile/core/ai/ai_model.dart';

/// The connector between our own action registry and [AiModel]'s own tool shape ([AiTool]) —
/// pure translation, no logic of its own. The model only ever sees [AppAction.name] and
/// [AppAction.description]; everything else about an action (its route, its KB pairing, whether
/// it needs a real tap to actually run) stays on our side and is never exposed to the model.
///
/// [AiTool], NEVER A CONCRETE ADAPTER'S OWN TOOL TYPE. This file has no reason to know
/// `flutter_gemma` exists — [GemmaAiModel] is the only place that ever converts [AiTool] into
/// its own plugin's `Tool`, per [AiModel]'s own doc comment on why concrete adapter types must
/// never leak past their own adapter file.
///
/// NO PARAMETERS TODAY, HONESTLY SO. Every action registered so far (`open_visit_app`) takes no
/// arguments — it either runs or it doesn't. Guessing a parameter schema now for nothing that
/// reads it would be exactly the "half-configured must not half-work" mistake this codebase's
/// own port/adapter files already warn against elsewhere.
List<AiTool> actionTools(Iterable<AppAction> actions) {
  return [
    for (final action in actions) AiTool(name: action.name, description: action.description),
  ];
}
