import 'package:flutter_gemma/flutter_gemma.dart';
import 'package:raje3_mobile/core/actions/action_model.dart';

/// The connector between our own action registry and flutter_gemma's own tool-calling shape —
/// pure translation, no logic of its own. The model only ever sees [AppAction.name] and
/// [AppAction.description]; everything else about an action (its route, its KB pairing, whether
/// it needs a real tap to actually run) stays on our side and is never exposed to the model.
///
/// NO PARAMETERS TODAY, HONESTLY SO. Every action registered so far (`open_visit_app`) takes no
/// arguments — it either runs or it doesn't. [Tool.parameters] is left at its own empty default
/// until an action that genuinely needs one exists; guessing a parameter schema now for nothing
/// that reads it would be exactly the "half-configured must not half-work" mistake this
/// codebase's own port/adapter files already warn against elsewhere.
List<Tool> actionTools(Iterable<AppAction> actions) {
  return [
    for (final action in actions) Tool(name: action.name, description: action.description),
  ];
}
