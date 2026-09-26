/// «محلّي» — mirrors `apps/console/src/screens/Shop.tsx`'s own wire shapes exactly (that screen's
/// interfaces are the real, trusted contract; the backend services never changed for this build).
/// This mobile pass covers the highest-value subset of the console's 24 real indicators — see
/// `shop_screen.dart`'s own header comment for exactly which ones, and which are a documented,
/// explicit gap for a later pass (never a silent omission).
library;

class TodayCeiling {
  final bool known;
  final bool unlimited;
  final int limit;
  final int reachedToday;
  final int remaining;
  final String quality;
  const TodayCeiling({
    required this.known,
    required this.unlimited,
    required this.limit,
    required this.reachedToday,
    required this.remaining,
    required this.quality,
  });

  factory TodayCeiling.fromJson(Map<String, dynamic> j) => TodayCeiling(
        known: j['known'] as bool? ?? false,
        unlimited: j['unlimited'] as bool? ?? false,
        limit: (j['limit'] as num?)?.toInt() ?? 0,
        reachedToday: (j['reached_today'] as num?)?.toInt() ?? 0,
        remaining: (j['remaining'] as num?)?.toInt() ?? 0,
        quality: j['quality'] as String? ?? '',
      );
}

class TodayStatus {
  final bool? canSend;
  final String? blocked;
  final int sentToday;
  final int waiting;
  final int? retrying;
  final String? retryingReason;
  final TodayCeiling ceiling;
  const TodayStatus({
    required this.canSend,
    required this.blocked,
    required this.sentToday,
    required this.waiting,
    required this.retrying,
    required this.retryingReason,
    required this.ceiling,
  });

  factory TodayStatus.fromJson(Map<String, dynamic> j) {
    final messages = (j['messages'] as Map?) ?? const {};
    return TodayStatus(
      canSend: j['can_send'] as bool?,
      blocked: j['blocked'] as String?,
      sentToday: (messages['sent_today'] as num?)?.toInt() ?? 0,
      waiting: (messages['waiting'] as num?)?.toInt() ?? 0,
      retrying: (messages['retrying'] as num?)?.toInt(),
      retryingReason: messages['retrying_reason'] as String?,
      ceiling: TodayCeiling.fromJson(Map<String, dynamic>.from((j['ceiling'] as Map?) ?? const {})),
    );
  }
}

class WaConnectStatus {
  final String state;
  final String message;
  final bool? canSend;
  const WaConnectStatus({required this.state, required this.message, required this.canSend});

  factory WaConnectStatus.fromJson(Map<String, dynamic> j) => WaConnectStatus(
        state: j['state'] as String? ?? '',
        message: j['message'] as String? ?? '',
        canSend: j['can_send'] as bool?,
      );
}

class SeriesPoint {
  final int at;
  final int customers;
  final double? value;
  const SeriesPoint({required this.at, required this.customers, required this.value});

  factory SeriesPoint.fromJson(Map<String, dynamic> j) => SeriesPoint(
        at: (j['at'] as num?)?.toInt() ?? 0,
        customers: (j['customers'] as num?)?.toInt() ?? 0,
        value: (j['value'] as num?)?.toDouble(),
      );
}

class RetentionSeries {
  final List<SeriesPoint> points;
  final bool learning;
  final double? first;
  final double? last;
  final double? delta;
  final int? months;
  const RetentionSeries({
    required this.points,
    required this.learning,
    required this.first,
    required this.last,
    required this.delta,
    required this.months,
  });

  factory RetentionSeries.fromJson(Map<String, dynamic> j) {
    final pts = (j['points'] as List?) ?? const [];
    return RetentionSeries(
      points: pts
          .whereType<Map>()
          .map((m) => SeriesPoint.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false),
      learning: j['learning'] as bool? ?? false,
      first: (j['first'] as num?)?.toDouble(),
      last: (j['last'] as num?)?.toDouble(),
      delta: (j['delta'] as num?)?.toDouble(),
      months: (j['months'] as num?)?.toInt(),
    );
  }
}

class EffectStat {
  final bool ready;
  final String? reason;
  final int? visits;
  final int? windowDays;
  final bool partial;
  const EffectStat({required this.ready, this.reason, this.visits, this.windowDays, this.partial = false});

  factory EffectStat.fromJson(Map<String, dynamic> j) => EffectStat(
        ready: j['ready'] as bool? ?? false,
        reason: j['reason'] as String?,
        visits: (j['visits'] as num?)?.toInt(),
        windowDays: (j['window_days'] as num?)?.toInt(),
        partial: j['partial'] as bool? ?? false,
      );
}

class OptOutStat {
  final bool ready;
  final String? reason;
  final double? rate;
  final int? per;
  final int? sent;
  final int? need;
  final int? optOuts;
  final bool partial;
  const OptOutStat({
    required this.ready,
    this.reason,
    this.rate,
    this.per,
    this.sent,
    this.need,
    this.optOuts,
    this.partial = false,
  });

  factory OptOutStat.fromJson(Map<String, dynamic> j) => OptOutStat(
        ready: j['ready'] as bool? ?? false,
        reason: j['reason'] as String?,
        rate: (j['rate'] as num?)?.toDouble(),
        per: (j['per'] as num?)?.toInt(),
        sent: (j['sent'] as num?)?.toInt(),
        need: (j['need'] as num?)?.toInt(),
        optOuts: (j['opt_outs'] as num?)?.toInt(),
        partial: j['partial'] as bool? ?? false,
      );
}

class HoldoutStat {
  final bool ready;
  final String? reason;
  final int? held;
  final int? reached;
  final int? need;
  final double? heldRate;
  final double? reachedRate;
  final double? gap;
  final int? windowDays;
  const HoldoutStat({
    required this.ready,
    this.reason,
    this.held,
    this.reached,
    this.need,
    this.heldRate,
    this.reachedRate,
    this.gap,
    this.windowDays,
  });

  factory HoldoutStat.fromJson(Map<String, dynamic> j) => HoldoutStat(
        ready: j['ready'] as bool? ?? false,
        reason: j['reason'] as String?,
        held: (j['held'] as num?)?.toInt(),
        reached: (j['reached'] as num?)?.toInt(),
        need: (j['need'] as num?)?.toInt(),
        heldRate: (j['held_rate'] as num?)?.toDouble(),
        reachedRate: (j['reached_rate'] as num?)?.toDouble(),
        gap: (j['gap'] as num?)?.toDouble(),
        windowDays: (j['window_days'] as num?)?.toInt(),
      );
}

class WeekWindow {
  final int visits;
  final int? previous;
  final int windowDays;
  const WeekWindow({required this.visits, required this.previous, required this.windowDays});

  factory WeekWindow.fromJson(Map<String, dynamic> j) => WeekWindow(
        visits: (j['visits'] as num?)?.toInt() ?? 0,
        previous: (j['previous'] as num?)?.toInt(),
        windowDays: (j['window_days'] as num?)?.toInt() ?? 7,
      );
}

class AtRiskRow {
  final String subjectRef;
  final int daysOverdue;
  final int ownCycleDays;
  final int visits;
  const AtRiskRow({
    required this.subjectRef,
    required this.daysOverdue,
    required this.ownCycleDays,
    required this.visits,
  });

  factory AtRiskRow.fromJson(Map<String, dynamic> j) => AtRiskRow(
        subjectRef: j['subject_ref'] as String? ?? '',
        daysOverdue: (j['days_overdue'] as num?)?.toInt() ?? 0,
        ownCycleDays: (j['own_cycle_days'] as num?)?.toInt() ?? 0,
        visits: (j['visits'] as num?)?.toInt() ?? 0,
      );
}

class BranchRow {
  final String branchId;
  final String name;
  final int visits;
  final int customers;
  final double? returnRate;
  const BranchRow({
    required this.branchId,
    required this.name,
    required this.visits,
    required this.customers,
    required this.returnRate,
  });

  factory BranchRow.fromJson(Map<String, dynamic> j) => BranchRow(
        branchId: j['branch_id'] as String? ?? '',
        name: j['name'] as String? ?? '',
        visits: (j['visits'] as num?)?.toInt() ?? 0,
        customers: (j['customers'] as num?)?.toInt() ?? 0,
        returnRate: (j['return_rate'] as num?)?.toDouble(),
      );
}

class Branches {
  final List<BranchRow> rows;
  final int unknown;
  final bool canRank;
  const Branches({required this.rows, required this.unknown, required this.canRank});

  factory Branches.fromJson(Map<String, dynamic> j) {
    final rows = (j['rows'] as List?) ?? const [];
    return Branches(
      rows: rows
          .whereType<Map>()
          .map((m) => BranchRow.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false),
      unknown: (j['unknown'] as num?)?.toInt() ?? 0,
      canRank: j['can_rank'] as bool? ?? true,
    );
  }
}

class OperatorRow {
  final String operatorId;
  final String name;
  final int visits;
  final int customers;
  final double? returnRate;
  const OperatorRow({
    required this.operatorId,
    required this.name,
    required this.visits,
    required this.customers,
    required this.returnRate,
  });

  factory OperatorRow.fromJson(Map<String, dynamic> j) => OperatorRow(
        operatorId: j['operator_id'] as String? ?? '',
        name: j['name'] as String? ?? '',
        visits: (j['visits'] as num?)?.toInt() ?? 0,
        customers: (j['customers'] as num?)?.toInt() ?? 0,
        returnRate: (j['return_rate'] as num?)?.toDouble(),
      );
}

class Blocked {
  final String indicator;
  final String? lost;
  final String? why;
  final String? doText;
  final String? owner;
  final String? request;
  final int? have;
  final int? need;
  const Blocked({
    required this.indicator,
    this.lost,
    this.why,
    this.doText,
    this.owner,
    this.request,
    this.have,
    this.need,
  });

  factory Blocked.fromJson(Map<String, dynamic> j) {
    final progress = (j['progress'] as Map?) ?? const {};
    return Blocked(
      indicator: j['indicator'] as String? ?? '',
      lost: j['lost'] as String?,
      why: j['why'] as String?,
      doText: j['do'] as String?,
      owner: j['owner'] as String?,
      request: j['request'] as String?,
      have: (progress['have'] as num?)?.toInt(),
      need: (progress['need'] as num?)?.toInt(),
    );
  }
}

class NextStepCard {
  final String id;
  final String category;
  final String categoryLabel;
  final String message;
  final String? ctaLabel;
  final String? ctaLink;
  final String tone; // info | warning | success
  const NextStepCard({
    required this.id,
    required this.category,
    required this.categoryLabel,
    required this.message,
    required this.ctaLabel,
    required this.ctaLink,
    required this.tone,
  });

  factory NextStepCard.fromJson(Map<String, dynamic> j) => NextStepCard(
        id: j['id'] as String? ?? '',
        category: j['category'] as String? ?? '',
        categoryLabel: j['category_label'] as String? ?? '',
        message: j['message'] as String? ?? '',
        ctaLabel: j['cta_label'] as String?,
        ctaLink: j['cta_link'] as String?,
        tone: j['tone'] as String? ?? 'info',
      );
}

class NextStep {
  final NextStepCard primary;
  final NextStepCard? secondary;
  const NextStep({required this.primary, required this.secondary});

  factory NextStep.fromJson(Map<String, dynamic> j) => NextStep(
        primary: NextStepCard.fromJson(Map<String, dynamic>.from(j['primary'] as Map)),
        secondary: j['secondary'] == null
            ? null
            : NextStepCard.fromJson(Map<String, dynamic>.from(j['secondary'] as Map)),
      );
}

class ServicePopularityRow {
  final String serviceId;
  final int count;
  final double share;
  const ServicePopularityRow({required this.serviceId, required this.count, required this.share});

  factory ServicePopularityRow.fromJson(Map<String, dynamic> j) => ServicePopularityRow(
        serviceId: j['service_id'] as String? ?? '',
        count: (j['count'] as num?)?.toInt() ?? 0,
        share: (j['share'] as num?)?.toDouble() ?? 0,
      );
}

class PeakMap {
  final Map<String, int> grid; // "day:hour" -> count
  final String? busiest; // "day:hour"
  const PeakMap({required this.grid, required this.busiest});

  factory PeakMap.fromJson(Map<String, dynamic> j) {
    final grid = (j['grid'] as Map?) ?? const {};
    return PeakMap(
      grid: grid.map((k, v) => MapEntry(k.toString(), (v as num?)?.toInt() ?? 0)),
      busiest: j['busiest'] as String?,
    );
  }
}

class DayHeatmapRow {
  final String label;
  final List<int> days; // days[0..6] = Sun..Sat
  const DayHeatmapRow({required this.label, required this.days});
}

/// Turns a flat `"entityId:day"` grid (`service_day_heatmap`/`branch_day_heatmap`) into the
/// top-N entities by total, same shape/limit logic as Shop.tsx's own `topEntitiesByDay()`.
List<DayHeatmapRow> topEntitiesByDay(Map<String, dynamic>? grid, Map<String, String> names, int limit) {
  if (grid == null) return const [];
  final totals = <String, List<int>>{};
  for (final entry in grid.entries) {
    final sep = entry.key.lastIndexOf(':');
    if (sep < 0) continue;
    final id = entry.key.substring(0, sep);
    final day = int.tryParse(entry.key.substring(sep + 1));
    if (day == null || day < 0 || day > 6) continue;
    final count = (entry.value as num?)?.toInt() ?? 0;
    final row = totals.putIfAbsent(id, () => List.filled(7, 0));
    row[day] += count;
  }
  final rows = totals.entries
      .map((e) => DayHeatmapRow(label: names[e.key] ?? e.key, days: e.value))
      .toList()
    ..sort((a, b) => b.days.reduce((x, y) => x + y).compareTo(a.days.reduce((x, y) => x + y)));
  return rows.take(limit).toList(growable: false);
}

class AssociationPair {
  final String a;
  final String b;
  final String verdict;
  final int customers;
  const AssociationPair({required this.a, required this.b, required this.verdict, required this.customers});

  factory AssociationPair.fromJson(Map<String, dynamic> j) => AssociationPair(
        a: j['a'] as String? ?? '',
        b: j['b'] as String? ?? '',
        verdict: j['verdict'] as String? ?? '',
        customers: (j['customers'] as num?)?.toInt() ?? 0,
      );
}

class Pairs {
  final bool learning;
  final int have;
  final int need;
  final List<AssociationPair> pairs;
  const Pairs({required this.learning, required this.have, required this.need, required this.pairs});

  factory Pairs.fromJson(Map<String, dynamic> j) {
    final list = (j['pairs'] as List?) ?? const [];
    return Pairs(
      learning: j['learning'] as bool? ?? false,
      have: (j['have'] as num?)?.toInt() ?? 0,
      need: (j['need'] as num?)?.toInt() ?? 0,
      pairs: list.whereType<Map>().map((m) => AssociationPair.fromJson(Map<String, dynamic>.from(m))).toList(growable: false),
    );
  }
}

class Bundle {
  final String? a;
  final String? b;
  final String? aName;
  final String? bName;
  final String? why;
  final int customers;
  final String? action;
  final String? actionLabel;
  final String? packageId;
  const Bundle({
    required this.a,
    required this.b,
    required this.aName,
    required this.bName,
    required this.why,
    required this.customers,
    required this.action,
    required this.actionLabel,
    required this.packageId,
  });

  factory Bundle.fromJson(Map<String, dynamic> j) => Bundle(
        a: j['a'] as String?,
        b: j['b'] as String?,
        aName: j['a_name'] as String?,
        bName: j['b_name'] as String?,
        why: j['why'] as String?,
        customers: (j['customers'] as num?)?.toInt() ?? 0,
        action: j['action'] as String?,
        actionLabel: j['action_label'] as String?,
        packageId: j['package_id'] as String?,
      );
}

/// `GET /api/v1/insights/dashboard` — the one call, everything computed server-side. `values` is
/// a loose bag keyed by indicator name (matches the console's own `Record<string, unknown>`);
/// this class only pulls out the fields this mobile pass's screen actually renders — see that
/// file's own header comment for the documented, explicit subset still deferred.
class ShopDashboard {
  final bool computing;
  final bool emptyBranch;
  final String? message;
  final Map<String, dynamic> values;
  final List<String> entitlements;
  final bool stale;
  final int asOfHoursAgo;
  final List<Blocked> notEnabled;
  final NextStep? nextStep;

  const ShopDashboard({
    required this.computing,
    required this.emptyBranch,
    required this.message,
    required this.values,
    required this.entitlements,
    required this.stale,
    required this.asOfHoursAgo,
    required this.notEnabled,
    required this.nextStep,
  });

  factory ShopDashboard.fromJson(Map<String, dynamic> j) {
    final notEnabled = (j['not_enabled'] as List?) ?? const [];
    return ShopDashboard(
      computing: j['computing'] as bool? ?? false,
      emptyBranch: j['empty_branch'] as bool? ?? false,
      message: j['message'] as String?,
      values: Map<String, dynamic>.from((j['values'] as Map?) ?? const {}),
      entitlements: ((j['entitlements'] as List?) ?? const []).map((e) => e.toString()).toList(),
      stale: j['stale'] as bool? ?? false,
      asOfHoursAgo: (j['as_of_hours_ago'] as num?)?.toInt() ?? 0,
      notEnabled: notEnabled
          .whereType<Map>()
          .map((m) => Blocked.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false),
      nextStep: j['next_step'] == null
          ? null
          : NextStep.fromJson(Map<String, dynamic>.from(j['next_step'] as Map)),
    );
  }

  double? get returnRate => (values['return_rate'] as num?)?.toDouble();
  int? get activeCustomers => (values['active_customers'] as num?)?.toInt();
  RetentionSeries? get retentionSeries {
    final v = values['retention_series'];
    return v is Map ? RetentionSeries.fromJson(Map<String, dynamic>.from(v)) : null;
  }

  List<AtRiskRow>? get atRisk {
    final v = values['at_risk'];
    if (v == null) return null;
    return (v as List)
        .whereType<Map>()
        .map((m) => AtRiskRow.fromJson(Map<String, dynamic>.from(m)))
        .toList(growable: false);
  }

  WeekWindow? get visitsWeek {
    final v = values['visits_week'];
    return v is Map ? WeekWindow.fromJson(Map<String, dynamic>.from(v)) : null;
  }

  ({int newCustomers, int returning})? get newVsReturning {
    final v = values['new_vs_returning'];
    if (v is! Map) return null;
    return (
      newCustomers: (v['new'] as num?)?.toInt() ?? 0,
      returning: (v['returning'] as num?)?.toInt() ?? 0,
    );
  }

  List<ServicePopularityRow>? get servicePopularity {
    final v = values['service_popularity'];
    if (v == null) return null;
    return (v as List)
        .whereType<Map>()
        .map((m) => ServicePopularityRow.fromJson(Map<String, dynamic>.from(m)))
        .toList(growable: false);
  }

  List<String>? get weakServices {
    final v = values['weak_services'];
    if (v == null) return null;
    return (v as List).map((e) => e.toString()).toList(growable: false);
  }

  Map<String, String> get serviceNames {
    final v = values['service_names'];
    if (v is! Map) return const {};
    return v.map((k, val) => MapEntry(k.toString(), val.toString()));
  }

  EffectStat? get returnedAfterReminder {
    final v = values['returned_after_reminder'];
    return v is Map ? EffectStat.fromJson(Map<String, dynamic>.from(v)) : null;
  }

  OptOutStat? get optOutRate {
    final v = values['opt_out_rate'];
    return v is Map ? OptOutStat.fromJson(Map<String, dynamic>.from(v)) : null;
  }

  HoldoutStat? get holdoutComparison {
    final v = values['holdout_comparison'];
    return v is Map ? HoldoutStat.fromJson(Map<String, dynamic>.from(v)) : null;
  }

  bool get aiEntitled => entitlements.contains('feature.whatsapp');

  PeakMap? get peakMap {
    final v = values['peak_map'];
    return v is Map ? PeakMap.fromJson(Map<String, dynamic>.from(v)) : null;
  }

  Map<String, String> get branchNames {
    final v = values['branch_names'];
    if (v is! Map) return const {};
    return v.map((k, val) => MapEntry(k.toString(), val.toString()));
  }

  List<DayHeatmapRow> get serviceDayRows {
    final v = values['service_day_heatmap'];
    return v is Map ? topEntitiesByDay(Map<String, dynamic>.from(v), serviceNames, 6) : const [];
  }

  List<DayHeatmapRow> get branchDayRows {
    final v = values['branch_day_heatmap'];
    return v is Map ? topEntitiesByDay(Map<String, dynamic>.from(v), branchNames, 6) : const [];
  }
}

/// `GET /api/v1/assistant/growth/my-impact` — `services/whatsapp-assistant/app/core/
/// shop_impact_report.py`'s own shape, this shop's own numbers only.
class ShopImpact {
  final int days;
  final bool aiEnabled;
  final int? conversations;
  final int aiBookings;
  final double? conversionRate;
  final int? avgInvoiceValueMinor;
  final int upsellOffered;
  final int upsellAccepted;
  final double? upsellAcceptanceRate;
  const ShopImpact({
    required this.days,
    required this.aiEnabled,
    required this.conversations,
    required this.aiBookings,
    required this.conversionRate,
    required this.avgInvoiceValueMinor,
    required this.upsellOffered,
    required this.upsellAccepted,
    required this.upsellAcceptanceRate,
  });

  factory ShopImpact.fromJson(Map<String, dynamic> j) => ShopImpact(
        days: (j['days'] as num?)?.toInt() ?? 30,
        aiEnabled: j['ai_enabled'] as bool? ?? false,
        conversations: (j['conversations'] as num?)?.toInt(),
        aiBookings: (j['ai_bookings'] as num?)?.toInt() ?? 0,
        conversionRate: (j['conversion_rate'] as num?)?.toDouble(),
        avgInvoiceValueMinor: (j['avg_invoice_value_minor'] as num?)?.toInt(),
        upsellOffered: (j['upsell_offered'] as num?)?.toInt() ?? 0,
        upsellAccepted: (j['upsell_accepted'] as num?)?.toInt() ?? 0,
        upsellAcceptanceRate: (j['upsell_acceptance_rate'] as num?)?.toDouble(),
      );
}
