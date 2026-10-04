import 'package:flutter/widgets.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'package:raje3_mobile/core/actions/action_model.dart';
import 'package:raje3_mobile/core/actions/action_registry.dart';
import 'package:raje3_mobile/core/ai/ai_model.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/providers/branch_provider.dart';
import 'package:raje3_mobile/core/services/customers_service.dart';
import 'package:raje3_mobile/core/services/mobile_requests_service.dart';
import 'package:raje3_mobile/core/services/ratings_service.dart';
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
    final readHandler = _readHandlers[action.id];
    if (readHandler != null) return readHandler(context);
    final writeHandler = _writeHandlers[action.id];
    if (writeHandler != null) return writeHandler(context);
    // NO HANDLER YET FOR THIS NON-NAVIGATION ACTION. Every "system"/"app" action registered so
    // far is either a read (above) or a write (below); the day a THIRD shape is needed, it gets
    // its own map here too — never guessed ahead of that action actually existing.
    return null;
  }

  /// The selected branch, when this shop has more than one — the same [BranchProvider] the home
  /// hero's own switcher and visit_screen.dart's today's-bookings card already read from, so an
  /// answer spoken here never disagrees with the branch the operator is currently looking at.
  static String _branchId(BuildContext context) => context.read<BranchProvider>().selectedId ?? '';

  /// One entry per "system"-scope READ action's own `id` (mobile_actions.json) — each fetches the
  /// exact same real endpoint the matching screen itself calls (AuthProvider's own passthroughs),
  /// never a second, parallel data path. Kept as a map rather than a switch so a new read action
  /// is "add a JSON entry + one line here", the same low-friction shape [ActionRegistry] itself
  /// already holds action DEFINITIONS to.
  static final Map<String, Future<String> Function(BuildContext)> _readHandlers = {
    'read.billing_status': _readBillingStatus,
    'read.branch_count': _readBranchCount,
    'read.vehicle_tracking_status': _readVehicleTrackingStatus,
    'read.customers_total': _readCustomersTotal,
    'read.customers_overdue_count': _readCustomersOverdueCount,
    'read.mobile_requests_pending_count': _readMobileRequestsPendingCount,
    'read.mobile_requests_needs_decision_count': _readMobileRequestsNeedsDecisionCount,
    'read.rating_average': _readRatingAverage,
    'read.rating_unhandled_count': _readRatingUnhandledCount,
    'read.rating_top_staff': _readRatingTopStaff,
    'read.mobile_requests_completed_count': _readMobileRequestsCompletedCount,
    'read.mobile_requests_today_count': _readMobileRequestsTodayCount,
    'read.operators_count': _readOperatorsCount,
    'read.branches_disconnected_count': _readBranchesDisconnectedCount,
    'read.customers_recent_name': _readCustomersRecentName,
    'read.rating_critical_issues_count': _readRatingCriticalIssuesCount,
    'read.per_branch_mode': _readPerBranchMode,
    'read.billing_overdue': _readBillingOverdue,
    'read.services_count': _readServicesCount,
    'read.customers_today_count': _readCustomersTodayCount,
    'read.mobile_requests_rejected_count': _readMobileRequestsRejectedCount,
    'read.mobile_requests_no_show_count': _readMobileRequestsNoShowCount,
    'read.rating_five_star_count': _readRatingFiveStarCount,
    'read.branches_active_count': _readBranchesActiveCount,
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

  static Future<String> _readCustomersTotal(BuildContext context) async {
    final s = S.of(context)!;
    final service = CustomersService(apiClient: context.read<AuthProvider>().apiClient);
    try {
      final list = await service.recent(branchId: _branchId(context));
      if (list == null) return s.readCustomersFailed;
      return s.readCustomersTotal(list.length);
    } catch (_) {
      return s.readCustomersFailed;
    }
  }

  static Future<String> _readCustomersOverdueCount(BuildContext context) async {
    final s = S.of(context)!;
    final service = CustomersService(apiClient: context.read<AuthProvider>().apiClient);
    final branchId = _branchId(context);
    try {
      final refs = await service.overdueSubjectRefs();
      if (refs == null) return s.readCustomersFailed;
      // THE SCHEDULE ITSELF CARRIES NO BRANCH (pseudonyms only) — the same resolve-step narrowing
      // customers_screen.dart's own overdue tab applies.
      final resolved = await service.byRefs(refs, branchId: branchId);
      if (resolved == null) return s.readCustomersFailed;
      return s.readCustomersOverdueCount(resolved.length);
    } catch (_) {
      return s.readCustomersFailed;
    }
  }

  static Future<String> _readMobileRequestsPendingCount(BuildContext context) async {
    final s = S.of(context)!;
    final service = MobileRequestsService(apiClient: context.read<AuthProvider>().apiClient);
    try {
      final list = await service.list();
      if (list == null) return s.readMobileRequestsFailed;
      final pending = list.where((r) => r.status == 'pending').length;
      return s.readMobileRequestsPendingCount(pending);
    } catch (_) {
      return s.readMobileRequestsFailed;
    }
  }

  // Same grace window mobile_requests_screen.dart's own `_isNeedsDecision` uses — an accepted
  // request whose own real appointment moment already passed, with a small buffer so a request
  // due two minutes ago is not flagged before the shop had a real chance to act.
  static const _needsDecisionGraceSeconds = 30 * 60;

  static Future<String> _readMobileRequestsNeedsDecisionCount(BuildContext context) async {
    final s = S.of(context)!;
    final service = MobileRequestsService(apiClient: context.read<AuthProvider>().apiClient);
    try {
      final list = await service.list();
      if (list == null) return s.readMobileRequestsFailed;
      final now = DateTime.now().millisecondsSinceEpoch ~/ 1000;
      final needsDecision = list
          .where((r) =>
              r.status == 'accepted' && now - r.requestedTime > _needsDecisionGraceSeconds)
          .length;
      return s.readMobileRequestsNeedsDecisionCount(needsDecision);
    } catch (_) {
      return s.readMobileRequestsFailed;
    }
  }

  static Future<String> _readRatingAverage(BuildContext context) async {
    final s = S.of(context)!;
    final service = RatingsService(apiClient: context.read<AuthProvider>().apiClient);
    try {
      final now = DateTime.now();
      final since = now.subtract(const Duration(days: 30)).millisecondsSinceEpoch ~/ 1000;
      final until = now.millisecondsSinceEpoch ~/ 1000;
      final staff =
          await service.staffPerformance(since: since, until: until, branchId: _branchId(context));
      if (staff == null) return s.readRatingFailed;
      final totalRatings = staff.fold<int>(0, (a, b) => a + b.ratings);
      if (totalRatings == 0) return s.readRatingNone;
      final weightedAvg =
          staff.fold<double>(0, (a, b) => a + b.averageRating * b.ratings) / totalRatings;
      return s.readRatingAverage(weightedAvg.toStringAsFixed(1), totalRatings);
    } catch (_) {
      return s.readRatingFailed;
    }
  }

  static Future<String> _readRatingUnhandledCount(BuildContext context) async {
    final s = S.of(context)!;
    final service = RatingsService(apiClient: context.read<AuthProvider>().apiClient);
    try {
      final result = await service.list(handled: 'false', branchId: _branchId(context));
      if (result == null) return s.readRatingFailed;
      return s.readRatingUnhandledCount(result.rows.length);
    } catch (_) {
      return s.readRatingFailed;
    }
  }

  static Future<String> _readRatingTopStaff(BuildContext context) async {
    final s = S.of(context)!;
    final service = RatingsService(apiClient: context.read<AuthProvider>().apiClient);
    try {
      final now = DateTime.now();
      final since = now.subtract(const Duration(days: 30)).millisecondsSinceEpoch ~/ 1000;
      final until = now.millisecondsSinceEpoch ~/ 1000;
      final staff =
          await service.staffPerformance(since: since, until: until, branchId: _branchId(context));
      if (staff == null) return s.readRatingFailed;
      final ranked = staff.where((x) => x.ratings > 0).toList()
        ..sort((a, b) => b.averageRating.compareTo(a.averageRating));
      if (ranked.isEmpty) return s.readRatingNone;
      return s.readRatingTopStaff(ranked.first.operatorName, ranked.first.averageRating.toStringAsFixed(1));
    } catch (_) {
      return s.readRatingFailed;
    }
  }

  static Future<String> _readMobileRequestsCompletedCount(BuildContext context) async {
    final s = S.of(context)!;
    final service = MobileRequestsService(apiClient: context.read<AuthProvider>().apiClient);
    try {
      final list = await service.list();
      if (list == null) return s.readMobileRequestsFailed;
      final monthStart = DateTime(DateTime.now().year, DateTime.now().month, 1);
      final cutoff = monthStart.millisecondsSinceEpoch ~/ 1000;
      final completed =
          list.where((r) => r.status == 'completed' && r.created >= cutoff).length;
      return s.readMobileRequestsCompletedCount(completed);
    } catch (_) {
      return s.readMobileRequestsFailed;
    }
  }

  static Future<String> _readMobileRequestsTodayCount(BuildContext context) async {
    final s = S.of(context)!;
    final service = MobileRequestsService(apiClient: context.read<AuthProvider>().apiClient);
    try {
      final list = await service.list();
      if (list == null) return s.readMobileRequestsFailed;
      final now = DateTime.now();
      final dayStart = DateTime(now.year, now.month, now.day);
      final cutoff = dayStart.millisecondsSinceEpoch ~/ 1000;
      final today = list.where((r) => r.created >= cutoff).length;
      return s.readMobileRequestsTodayCount(today);
    } catch (_) {
      return s.readMobileRequestsFailed;
    }
  }

  static Future<String> _readOperatorsCount(BuildContext context) async {
    final s = S.of(context)!;
    final auth = context.read<AuthProvider>();
    try {
      final operators = await auth.fetchOperators();
      if (operators == null) return s.readOperatorsFailed;
      return s.readOperatorsCount(operators.length);
    } catch (_) {
      return s.readOperatorsFailed;
    }
  }

  static Future<String> _readBranchesDisconnectedCount(BuildContext context) async {
    final s = S.of(context)!;
    final auth = context.read<AuthProvider>();
    try {
      final result = await auth.fetchBranches();
      if (result == null) return s.readBranchFailed;
      final active = result.branches.where((b) => b.active).toList();
      var disconnected = 0;
      for (final b in active) {
        final status = await auth.fetchBranchConnectStatus(b.id);
        if (status == null || !status.canSend) disconnected++;
      }
      return s.readBranchesDisconnectedCount(disconnected);
    } catch (_) {
      return s.readBranchFailed;
    }
  }

  static Future<String> _readCustomersRecentName(BuildContext context) async {
    final s = S.of(context)!;
    final service = CustomersService(apiClient: context.read<AuthProvider>().apiClient);
    try {
      final list = await service.recent(branchId: _branchId(context));
      if (list == null) return s.readCustomersFailed;
      if (list.isEmpty) return s.readCustomersRecentNone;
      final latest = list.reduce((a, b) => a.created > b.created ? a : b);
      final label = latest.name.isNotEmpty ? latest.name : latest.phone;
      return s.readCustomersRecentName(label);
    } catch (_) {
      return s.readCustomersFailed;
    }
  }

  static Future<String> _readRatingCriticalIssuesCount(BuildContext context) async {
    final s = S.of(context)!;
    final service = RatingsService(apiClient: context.read<AuthProvider>().apiClient);
    try {
      final result = await service.list(handled: 'false', branchId: _branchId(context));
      if (result == null) return s.readRatingFailed;
      final critical = result.rows
          .where((r) => r.issueSteps.any((step) => step.severity == 'critical'))
          .length;
      return s.readRatingCriticalIssuesCount(critical);
    } catch (_) {
      return s.readRatingFailed;
    }
  }

  static Future<String> _readPerBranchMode(BuildContext context) async {
    final s = S.of(context)!;
    final auth = context.read<AuthProvider>();
    try {
      final isPerBranch = await auth.fetchIsPerBranchMode();
      return isPerBranch ? s.readPerBranchModeOn : s.readPerBranchModeOff;
    } catch (_) {
      return s.readBranchFailed;
    }
  }

  static Future<String> _readBillingOverdue(BuildContext context) async {
    final s = S.of(context)!;
    final auth = context.read<AuthProvider>();
    try {
      final overview = await auth.fetchBillingOverview();
      // Same real signal billing_screen.dart's own "عندك فاتورة متأخرة السداد" banner reads —
      // never a second, guessed definition of "overdue".
      final pastDue = overview.subscriptions.any((sub) => sub.status == 'past_due');
      return pastDue ? s.readBillingOverdueYes : s.readBillingOverdueNo;
    } catch (_) {
      return s.readBillingFailed;
    }
  }

  static Future<String> _readServicesCount(BuildContext context) async {
    final s = S.of(context)!;
    try {
      // Same real endpoint visit_screen.dart/mobile_requests_screen.dart already read services
      // from — never a second, parallel catalogue.
      final response =
          await context.read<AuthProvider>().apiClient.dio.get<dynamic>('/api/v1/field/catalogue');
      final body = response.data;
      if (body is! Map) return s.readServicesFailed;
      final services = (body['services'] as List?) ?? const [];
      return s.readServicesCount(services.length);
    } catch (_) {
      return s.readServicesFailed;
    }
  }

  static Future<String> _readCustomersTodayCount(BuildContext context) async {
    final s = S.of(context)!;
    final service = CustomersService(apiClient: context.read<AuthProvider>().apiClient);
    try {
      final list = await service.recent(branchId: _branchId(context));
      if (list == null) return s.readCustomersFailed;
      final now = DateTime.now();
      final dayStart = DateTime(now.year, now.month, now.day);
      final cutoff = dayStart.millisecondsSinceEpoch ~/ 1000;
      final today = list.where((c) => c.created >= cutoff).length;
      return s.readCustomersTodayCount(today);
    } catch (_) {
      return s.readCustomersFailed;
    }
  }

  static Future<String> _readMobileRequestsRejectedCount(BuildContext context) async {
    final s = S.of(context)!;
    final service = MobileRequestsService(apiClient: context.read<AuthProvider>().apiClient);
    try {
      final list = await service.list();
      if (list == null) return s.readMobileRequestsFailed;
      final monthStart = DateTime(DateTime.now().year, DateTime.now().month, 1);
      final cutoff = monthStart.millisecondsSinceEpoch ~/ 1000;
      final rejected =
          list.where((r) => r.status == 'rejected' && r.created >= cutoff).length;
      return s.readMobileRequestsRejectedCount(rejected);
    } catch (_) {
      return s.readMobileRequestsFailed;
    }
  }

  static Future<String> _readMobileRequestsNoShowCount(BuildContext context) async {
    final s = S.of(context)!;
    final service = MobileRequestsService(apiClient: context.read<AuthProvider>().apiClient);
    try {
      final list = await service.list();
      if (list == null) return s.readMobileRequestsFailed;
      final monthStart = DateTime(DateTime.now().year, DateTime.now().month, 1);
      final cutoff = monthStart.millisecondsSinceEpoch ~/ 1000;
      final noShow =
          list.where((r) => r.status == 'no_show' && r.created >= cutoff).length;
      return s.readMobileRequestsNoShowCount(noShow);
    } catch (_) {
      return s.readMobileRequestsFailed;
    }
  }

  static Future<String> _readRatingFiveStarCount(BuildContext context) async {
    final s = S.of(context)!;
    final service = RatingsService(apiClient: context.read<AuthProvider>().apiClient);
    try {
      final result = await service.list(stars: 5, branchId: _branchId(context));
      if (result == null) return s.readRatingFailed;
      return s.readRatingFiveStarCount(result.rows.length);
    } catch (_) {
      return s.readRatingFailed;
    }
  }

  static Future<String> _readBranchesActiveCount(BuildContext context) async {
    final s = S.of(context)!;
    final auth = context.read<AuthProvider>();
    try {
      final result = await auth.fetchBranches();
      if (result == null) return s.readBranchFailed;
      final active = result.branches.where((b) => b.active).length;
      return s.readBranchesActiveCount(active);
    } catch (_) {
      return s.readBranchFailed;
    }
  }

  /// One entry per "system"-scope WRITE action's own `id` — every one of these is
  /// [AppAction.requiresConfirmation]==true (enforced at parse time, see [ActionModel]'s own
  /// note), so [execute] only ever reaches these AFTER a real tap on [_ActionConfirmCard] — never
  /// from the model's own output directly. Same map shape as [_readHandlers], same reason.
  static final Map<String, Future<String> Function(BuildContext)> _writeHandlers = {
    'write.enable_vehicle_tracking': (c) => _setVehicleTracking(c, true),
    'write.disable_vehicle_tracking': (c) => _setVehicleTracking(c, false),
  };

  static Future<String> _setVehicleTracking(BuildContext context, bool enable) async {
    final s = S.of(context)!;
    final auth = context.read<AuthProvider>();
    try {
      final saved = await auth.setTracksVehicle(enable);
      if (saved == null) return s.writeVehicleTrackingFailed;
      return enable ? s.writeVehicleTrackingEnabledDone : s.writeVehicleTrackingDisabledDone;
    } catch (_) {
      return s.writeVehicleTrackingFailed;
    }
  }
}
