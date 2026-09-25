/// «شراكة استراتيجية» — mirrors `services/operations/app/core/referral_partnership.py`'s own
/// real shape exactly (`ReferralAgreement.public()` is a plain `asdict`, no server-side
/// transformation), including its immutable-once-proposed grant terms.
class ReferralAgreement {
  final String id;
  final String shopA;
  final String shopB;
  final String status;
  final String conditionType;
  final String conditionValue;
  final int grantValidityDays;
  final int agreementDurationDays;
  final int perPeriodCap;
  final int startedAt;
  final int endsAt;
  final String cancelRequestedBy;
  final String grantType;
  final String giftServiceId;
  final String giftServiceName;
  final String discountScope;
  final String discountGroupId;
  final String discountGroupName;

  const ReferralAgreement({
    required this.id,
    required this.shopA,
    required this.shopB,
    required this.status,
    required this.conditionType,
    required this.conditionValue,
    required this.grantValidityDays,
    required this.agreementDurationDays,
    required this.perPeriodCap,
    required this.startedAt,
    required this.endsAt,
    required this.cancelRequestedBy,
    required this.grantType,
    required this.giftServiceId,
    required this.giftServiceName,
    required this.discountScope,
    required this.discountGroupId,
    required this.discountGroupName,
  });

  /// «هي الطرف الآخر» — NOT a name: no name or phone survives on the row after creation
  /// (`core/referral_partnership.py`'s own comment on this), so the raw tenant id IS the only
  /// real identity available, exactly what the console itself shows (`otherParty()`).
  String otherParty(String myTenant) => shopA == myTenant ? shopB : shopA;

  /// 'referrer' when this shop is shop_a (the condition happens here), 'beneficiary' when it is
  /// shop_b (the discount is redeemed here).
  String myRole(String myTenant) => shopA == myTenant ? 'referrer' : 'beneficiary';

  factory ReferralAgreement.fromJson(Map<String, dynamic> json) {
    return ReferralAgreement(
      id: json['id'] as String? ?? '',
      shopA: json['shop_a'] as String? ?? '',
      shopB: json['shop_b'] as String? ?? '',
      status: json['status'] as String? ?? '',
      conditionType: json['condition_type'] as String? ?? '',
      conditionValue: json['condition_value'] as String? ?? '',
      grantValidityDays: (json['grant_validity_days'] as num?)?.toInt() ?? 0,
      agreementDurationDays: (json['agreement_duration_days'] as num?)?.toInt() ?? 0,
      perPeriodCap: (json['per_period_cap'] as num?)?.toInt() ?? 0,
      startedAt: (json['started_at'] as num?)?.toInt() ?? 0,
      endsAt: (json['ends_at'] as num?)?.toInt() ?? 0,
      cancelRequestedBy: json['cancel_requested_by'] as String? ?? '',
      grantType: json['grant_type'] as String? ?? 'discount',
      giftServiceId: json['gift_service_id'] as String? ?? '',
      giftServiceName: json['gift_service_name'] as String? ?? '',
      discountScope: json['discount_scope'] as String? ?? '',
      discountGroupId: json['discount_group_id'] as String? ?? '',
      discountGroupName: json['discount_group_name'] as String? ?? '',
    );
  }
}

class ReferralAuditEntry {
  final String id;
  final String event;
  final String actorTenant;
  final int created;

  const ReferralAuditEntry({
    required this.id,
    required this.event,
    required this.actorTenant,
    required this.created,
  });

  factory ReferralAuditEntry.fromJson(Map<String, dynamic> json) {
    return ReferralAuditEntry(
      id: json['id'] as String? ?? '',
      event: json['event'] as String? ?? '',
      actorTenant: json['actor_tenant'] as String? ?? '',
      created: (json['created'] as num?)?.toInt() ?? 0,
    );
  }
}

/// One side (`as_referrer` or `as_beneficiary`) of `GET /referral-partnership/kpis` — the ONLY
/// server-computed aggregate; a single partner's own scorecard is computed client-side from real
/// audit-log events, same as the console (see `referral_partnership_screen.dart`'s own note).
class ReferralRoleKpis {
  final int referralsSent;
  final int redeemed;
  final int expiredUnused;
  final double redemptionRate;
  final Map<String, int> byMonth;

  const ReferralRoleKpis({
    required this.referralsSent,
    required this.redeemed,
    required this.expiredUnused,
    required this.redemptionRate,
    required this.byMonth,
  });

  factory ReferralRoleKpis.fromJson(Map<String, dynamic> json) {
    final byMonthRaw = (json['by_month'] as Map?) ?? const {};
    return ReferralRoleKpis(
      referralsSent: (json['referrals_sent'] as num?)?.toInt() ?? 0,
      redeemed: (json['redeemed'] as num?)?.toInt() ?? 0,
      expiredUnused: (json['expired_unused'] as num?)?.toInt() ?? 0,
      redemptionRate: (json['redemption_rate'] as num?)?.toDouble() ?? 0,
      byMonth: byMonthRaw.map((k, v) => MapEntry(k as String, (v as num).toInt())),
    );
  }
}

class ReferralKpis {
  final ReferralRoleKpis asReferrer;
  final ReferralRoleKpis asBeneficiary;

  const ReferralKpis({required this.asReferrer, required this.asBeneficiary});

  factory ReferralKpis.fromJson(Map<String, dynamic> json) {
    return ReferralKpis(
      asReferrer: ReferralRoleKpis.fromJson(Map<String, dynamic>.from(json['as_referrer'] as Map? ?? const {})),
      asBeneficiary: ReferralRoleKpis.fromJson(Map<String, dynamic>.from(json['as_beneficiary'] as Map? ?? const {})),
    );
  }
}
