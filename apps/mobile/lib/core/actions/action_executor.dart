import 'package:flutter/widgets.dart';
import 'package:go_router/go_router.dart';
import 'package:raje3_mobile/core/actions/action_model.dart';
import 'package:raje3_mobile/core/actions/action_registry.dart';
import 'package:raje3_mobile/core/ai/ai_model.dart';
import 'package:raje3_mobile/models/catalog_model.dart';

/// What to do with an [AiActionProposed] event — the ONLY place a model's proposal turns into a
/// real effect. Nothing in [AiModel]/[AssistantService] ever executes anything itself; this is
/// the executor those doc comments both point to.
sealed class ActionDecision {
  const ActionDecision();
}

/// [proposed]'s own name did not resolve to a real, currently-usable action — an unknown name,
/// a disabled action, or (most likely) a capability the session no longer holds even though the
/// tool list once declared it. NEVER executed, never surfaced as if it were a real answer.
class ActionUnavailable extends ActionDecision {
  const ActionUnavailable();
}

/// [action] has no side effect ([AppAction.requiresConfirmation] is false) — safe to
/// [ActionExecutor.execute] immediately, no tap needed.
class ActionRunNow extends ActionDecision {
  final AppAction action;
  const ActionRunNow(this.action);
}

/// [action] changes something real ([AppAction.requiresConfirmation] is true) — MUST NOT run
/// until the operator's own tap calls [ActionExecutor.execute] themselves. The owner's own rule:
/// "تأكيده هو التنفيذ الفعلي مو الذكاء الاصطناعي".
class ActionNeedsConfirmation extends ActionDecision {
  final AppAction action;
  const ActionNeedsConfirmation(this.action);
}

/// Resolves an [AiActionProposed] event against the REAL, CURRENT [Catalog] — never trusted from
/// whenever the session's tool list was first built, since a capability can change mid-session —
/// and carries out an [AppAction] once it is actually safe (or confirmed) to.
class ActionExecutor {
  ActionExecutor({required this.registry});

  final ActionRegistry registry;

  /// What should happen with [proposed], given [catalog] as it stands RIGHT NOW.
  ActionDecision resolve(AiActionProposed proposed, Catalog catalog) {
    final action = registry.byName(proposed.name, catalog);
    if (action == null) return const ActionUnavailable();
    return action.requiresConfirmation ? ActionNeedsConfirmation(action) : ActionRunNow(action);
  }

  /// Actually carries out [action]. For [ActionNeedsConfirmation], the caller must only reach
  /// this after a real tap from the operator — this method itself does not re-check that; it
  /// trusts the caller the same way every other "confirm" button in this app is trusted once
  /// pressed.
  void execute(BuildContext context, AppAction action) {
    final route = action.route;
    if (route != null) {
      context.goNamed(route);
      return;
    }
    // NO HANDLER YET FOR A NON-NAVIGATION ACTION. Every action registered so far is scope
    // "navigation" (a route). The day a "system"/"app" action (no route) is added, its real
    // effect gets a handler here — never guessed ahead of that action actually existing.
  }
}
