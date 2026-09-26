/// «ولاء الشركاء» (renamed 2026-09-22 from «تحالف استراتيجي» — key/route names below stayed
/// `coupon*` on purpose, matching `services/operations/app/core/coupons.py`'s own module/route
/// names; only what the owner reads changed). A shop grants ANOTHER registered shop a discount
/// on THAT shop's own subscription with us, applied automatically at its next renewal — never a
/// discount for the end customer (that is [[task-referral-partnership-backend]]'s own feature —
/// a different backend module entirely). Mirrors `CouponAttempt.public()`'s plain `asdict` shape.
class CouponAttempt {
  final String id;
  final String beneficiaryPhoneLast4;
  final int percentRequested;
  final String scope;
  final String outcome;
  final int created;
  final Map<String, String> perApp;

  const CouponAttempt({
    required this.id,
    required this.beneficiaryPhoneLast4,
    required this.percentRequested,
    required this.scope,
    required this.outcome,
    required this.created,
    required this.perApp,
  });

  bool get granted => outcome == 'granted';

  factory CouponAttempt.fromJson(Map<String, dynamic> json) {
    final perApp = json['per_app'];
    return CouponAttempt(
      id: json['id'] as String? ?? '',
      beneficiaryPhoneLast4: json['beneficiary_phone_last4'] as String? ?? '',
      percentRequested: (json['percent_requested'] as num?)?.toInt() ?? 0,
      scope: json['scope'] as String? ?? '',
      outcome: json['outcome'] as String? ?? '',
      created: (json['created'] as num?)?.toInt() ?? 0,
      perApp: perApp is Map
          ? perApp.map((k, v) => MapEntry(k.toString(), v.toString()))
          : const {},
    );
  }
}

class CouponMonthCount {
  final String monthKey;
  final int grants;
  const CouponMonthCount({required this.monthKey, required this.grants});

  factory CouponMonthCount.fromJson(Map<String, dynamic> json) => CouponMonthCount(
        monthKey: json['month_key'] as String? ?? '',
        grants: (json['grants'] as num?)?.toInt() ?? 0,
      );
}

/// `GET /coupons/stats` — mirrors `CouponService.stats()` exactly (own doc comment there: the
/// ladder never walks the platform's full tier table, just the two numbers either side of where
/// this shop already sits).
class CouponStats {
  final int grantsThisMonth;
  final int currentCapPercent;
  final int ceilingPercent;
  final int? nextTierPercent;
  final int? nextTierGrantsNeeded;
  final List<CouponMonthCount> history;

  const CouponStats({
    required this.grantsThisMonth,
    required this.currentCapPercent,
    required this.ceilingPercent,
    required this.nextTierPercent,
    required this.nextTierGrantsNeeded,
    required this.history,
  });

  factory CouponStats.fromJson(Map<String, dynamic> json) {
    final history = (json['history'] as List?) ?? const [];
    return CouponStats(
      grantsThisMonth: (json['grants_this_month'] as num?)?.toInt() ?? 0,
      currentCapPercent: (json['current_cap_percent'] as num?)?.toInt() ?? 100,
      ceilingPercent: (json['ceiling_percent'] as num?)?.toInt() ?? 100,
      nextTierPercent: (json['next_tier_percent'] as num?)?.toInt(),
      nextTierGrantsNeeded: (json['next_tier_grants_needed'] as num?)?.toInt(),
      history: history
          .whereType<Map>()
          .map((m) => CouponMonthCount.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false),
    );
  }
}

/// `GET /coupons/check` — the grant form's own live hint as the operator types a phone number,
/// same minimal-disclosure answer `CouponService.check()`'s own doc comment describes (never
/// naming the beneficiary beyond these three facts).
class CouponCheck {
  final bool registered;
  final bool alreadyGrantedThisMonth;
  final bool isSelf;
  const CouponCheck({
    required this.registered,
    required this.alreadyGrantedThisMonth,
    required this.isSelf,
  });

  factory CouponCheck.fromJson(Map<String, dynamic> json) => CouponCheck(
        registered: json['registered'] as bool? ?? false,
        alreadyGrantedThisMonth: json['already_granted_this_month'] as bool? ?? false,
        isSelf: json['is_self'] as bool? ?? false,
      );
}
