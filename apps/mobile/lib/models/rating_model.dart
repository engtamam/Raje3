/// Lenient int read — see models/customer_model.dart's own `_toInt` doc comment for why this
/// exists at all (a real field came back as a string once, and a bare cast crashed the screen).
int _toInt(dynamic v) {
  if (v is num) return v.toInt();
  if (v is String) return int.tryParse(v) ?? 0;
  return 0;
}

/// A flagged procedure-checklist step on one rating — `severity` is `"normal"` or `"critical"`,
/// already resolved server-side from the visit's own `rating_issue_step_ids` (see
/// services/operations/app/api/v1/field.py's own `/ratings` route).
class RatingIssueStep {
  final String id;
  final String text;
  final String severity;

  const RatingIssueStep({required this.id, required this.text, required this.severity});

  factory RatingIssueStep.fromJson(Map<String, dynamic> json) {
    return RatingIssueStep(
      id: json['id'] as String? ?? '',
      text: json['text'] as String? ?? '',
      severity: json['severity'] as String? ?? 'normal',
    );
  }
}

/// `GET /api/v1/field/ratings` (`operations.ratings`) — a rated visit. Ratings are NOT a
/// separate entity server-side, they're fields on a Visit; this is that same row, trimmed to the
/// rating-relevant subset the real endpoint actually returns.
class RatingRow {
  final String id; // the visit id — also what mark-handled's path param needs, verbatim
  final String customerId;
  final String customerName;
  final String customerPhone;
  final String operatorName;
  final int rating; // 1..5 always, for anything this endpoint returns
  final String feedbackText;
  final int ratedAt;
  final int ratingHandledAt; // 0 = unhandled
  final String ratingHandledNote;
  final List<RatingIssueStep> issueSteps;

  const RatingRow({
    required this.id,
    required this.customerId,
    required this.customerName,
    required this.customerPhone,
    required this.operatorName,
    required this.rating,
    required this.feedbackText,
    required this.ratedAt,
    required this.ratingHandledAt,
    required this.ratingHandledNote,
    required this.issueSteps,
  });

  bool get isHandled => ratingHandledAt > 0;

  factory RatingRow.fromJson(Map<String, dynamic> json) {
    return RatingRow(
      id: json['id'] as String? ?? '',
      customerId: json['customer_id'] as String? ?? '',
      customerName: json['customer_name'] as String? ?? '',
      customerPhone: json['customer_phone'] as String? ?? '',
      operatorName: json['operator_name'] as String? ?? '',
      rating: _toInt(json['rating']),
      feedbackText: json['feedback_text'] as String? ?? '',
      ratedAt: _toInt(json['rated_at']),
      ratingHandledAt: _toInt(json['rating_handled_at']),
      ratingHandledNote: json['rating_handled_note'] as String? ?? '',
      issueSteps: ((json['rating_issue_steps'] as List?) ?? const [])
          .whereType<Map>()
          .map((m) => RatingIssueStep.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false),
    );
  }
}

/// `GET /api/v1/field/staff/performance` (`operations.staff_performance`) — one operator's
/// aggregate over the requested window.
class StaffPerformance {
  final String operatorId;
  final String operatorName;
  final int visits;
  final int ratings;
  final double averageRating;
  final double noShowRate;

  const StaffPerformance({
    required this.operatorId,
    required this.operatorName,
    required this.visits,
    required this.ratings,
    required this.averageRating,
    required this.noShowRate,
  });

  factory StaffPerformance.fromJson(Map<String, dynamic> json) {
    return StaffPerformance(
      operatorId: json['operator_id'] as String? ?? '',
      operatorName: json['operator_name'] as String? ?? '',
      visits: _toInt(json['visits']),
      ratings: _toInt(json['ratings']),
      averageRating: (json['average_rating'] as num?)?.toDouble() ?? 0,
      noShowRate: (json['no_show_rate'] as num?)?.toDouble() ?? 0,
    );
  }
}

/// `GET /api/v1/staff/operators/{id}/step-stats` (`operations.list_operator_step_stats`) — one
/// operator's own training record: an INCREMENTALLY-MAINTAINED counter row per procedure step,
/// never re-derived by scanning visit history.
class OperatorStepStat {
  final String stepId;
  final String stepText;
  final String stepSeverity;
  final int timesFlagged;
  final int timesFlaggedCritical;
  final int lastFlaggedAt;

  const OperatorStepStat({
    required this.stepId,
    required this.stepText,
    required this.stepSeverity,
    required this.timesFlagged,
    required this.timesFlaggedCritical,
    required this.lastFlaggedAt,
  });

  factory OperatorStepStat.fromJson(Map<String, dynamic> json) {
    return OperatorStepStat(
      stepId: json['step_id'] as String? ?? '',
      stepText: json['step_text'] as String? ?? '',
      stepSeverity: json['step_severity'] as String? ?? '',
      timesFlagged: _toInt(json['times_flagged']),
      timesFlaggedCritical: _toInt(json['times_flagged_critical']),
      lastFlaggedAt: _toInt(json['last_flagged_at']),
    );
  }
}
