import 'package:flutter/widgets.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/actions/action_model.dart';
import 'package:raje3_mobile/core/actions/action_registry.dart';
import 'package:raje3_mobile/core/ai/ai_model.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/utils/formatters.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
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
  ///
  /// RETURNS A SPOKEN/DISPLAYED ANSWER, OR `null`. `null` for every navigation action (nothing to
  /// say — the screen itself is the answer) and for any action with no read handler; a real
  /// sentence for a "system"-scope READ action (see [_readHandlers] below), fetched from the
  /// server FRESH on every call — never cached, never guessed from whatever a screen happened to
  /// show last, the same "ask the server, not the screen" rule every other real read in this app
  /// already holds to.
  Future<String?> execute(BuildContext context, AppAction action) async {
    final route = action.route;
    if (route != null) {
      context.goNamed(route);
      return null;
    }
    final handler = _readHandlers[action.id];
    if (handler != null) return handler(context);
    // NO HANDLER YET FOR THIS NON-NAVIGATION ACTION. The day a real WRITE "system"/"app" action
    // (no route, but a mutation rather than a read) is added, its own effect gets its own
    // handler here — never guessed ahead of that action actually existing.
    return null;
  }

  /// One entry per "system"-scope READ action's own `id` (mobile_actions.json) — each fetches the
  /// exact same real endpoint the matching screen itself calls (AuthProvider's own passthroughs),
  /// never a second, parallel data path. Kept as a map rather than a switch so a new read action
  /// is "add a JSON entry + one line here", the same low-friction shape [ActionRegistry] itself
  /// already holds action DEFINITIONS to.
  static final Map<String, Future<String> Function(BuildContext)> _readHandlers = {
    'read.billing_status': _readBillingStatus,
    'read.branch_count': _readBranchCount,
    'read.vehicle_tracking_status': _readVehicleTrackingStatus,
  };

  static Future<String> _readBillingStatus(BuildContext context) async {
    final s = S.of(context)!;
    final locale = Localizations.localeOf(context).languageCode;
    final auth = context.read<AuthProvider>();
    try {
      final overview = await auth.fetchBillingOverview();
      final active = overview.subscriptions.where((sub) => sub.status == 'active').toList();
      if (active.isEmpty) return s.readBillingNone;
      final parts = <String>[s.readBillingActiveCount(active.length)];
      // THE EARLIEST period_end AMONG ACTIVE, NOT-CANCELLING SUBSCRIPTIONS — the same "next real
      // charge" fact the renewal-preview card itself is built from, never every subscription's
      // own separate date read aloud one after another.
      final upcoming = active
          .where((sub) => !sub.cancelAtPeriodEnd && sub.currentPeriodEnd > 0)
          .map((sub) => sub.currentPeriodEnd)
          .toList()
        ..sort();
      if (upcoming.isNotEmpty) {
        final date = Formatters.formatDateFull(
            DateTime.fromMillisecondsSinceEpoch((upcoming.first * 1000).toInt()),
            locale: locale);
        parts.add(s.readBillingRenewsSoon(date));
      }
      return parts.join(' ');
    } catch (_) {
      return s.readBillingFailed;
    }
  }

  static Future<String> _readBranchCount(BuildContext context) async {
    final s = S.of(context)!;
    final auth = context.read<AuthProvider>();
    try {
      final result = await auth.fetchBranches();
      if (result == null) return s.readBranchFailed;
      return s.readBranchCount(result.branches.length);
    } catch (_) {
      return s.readBranchFailed;
    }
  }

  static Future<String> _readVehicleTrackingStatus(BuildContext context) async {
    final s = S.of(context)!;
    final auth = context.read<AuthProvider>();
    try {
      final tracks = await auth.fetchTracksVehicle();
      if (tracks == null) return s.readVehicleTrackingFailed;
      return tracks ? s.readVehicleTrackingOn : s.readVehicleTrackingOff;
    } catch (_) {
      return s.readVehicleTrackingFailed;
    }
  }
}
