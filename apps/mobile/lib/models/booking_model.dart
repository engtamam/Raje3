int _toInt(dynamic v) {
  if (v is num) return v.toInt();
  if (v is String) return int.tryParse(v) ?? 0;
  return 0;
}

/// Mirrors apps/console/src/api.ts's own `Booking` interface exactly — same contract
/// services/bookings/app/core/models.py's `Booking.public()` already gives every caller.
class Booking {
  final String id;
  final String branchId;
  final String operatorId;
  final String customerId;
  final List<String> serviceIds;
  final int startsAt;
  final int durationMinutes;
  final String status; // booked | attended | no_show | cancelled
  final String paymentStatus; // none | deposit | paid
  final int? depositAmountMinor;
  final int? priceOverrideMinor;
  final String? intendedRewardId;
  /// THE BEST LIVE CAMPAIGN/REFERRAL/MUTUAL-BENEFIT DISCOUNT, APPLIED AUTOMATICALLY AT attend()
  /// (2026-10-05) — unlike [intendedRewardId] above, there is no separate "intent" step: which
  /// one is worth the most is only decided by comparing real value once the visit becomes real.
  /// `null` means nothing was live, never a failure to check. Mirrors
  /// `apps/console/src/api.ts`'s own `Booking.applied_offer_ref`/`applied_offer_text`.
  final String? appliedOfferRef;
  final String? appliedOfferText;
  final String note;
  final String? cancelledReason;
  final Map<String, int> quantities; // service_id -> quantity, absent = 1

  const Booking({
    required this.id,
    required this.branchId,
    required this.operatorId,
    required this.customerId,
    required this.serviceIds,
    required this.startsAt,
    required this.durationMinutes,
    required this.status,
    required this.paymentStatus,
    this.depositAmountMinor,
    this.priceOverrideMinor,
    this.intendedRewardId,
    this.appliedOfferRef,
    this.appliedOfferText,
    this.note = '',
    this.cancelledReason,
    this.quantities = const {},
  });

  int quantityOf(String serviceId) => quantities[serviceId] ?? 1;

  factory Booking.fromJson(Map<String, dynamic> json) => Booking(
        id: json['id'] as String? ?? '',
        branchId: json['branch_id'] as String? ?? '',
        operatorId: json['operator_id'] as String? ?? '',
        customerId: json['customer_id'] as String? ?? '',
        serviceIds: ((json['service_ids'] as List?) ?? const [])
            .map((e) => e.toString())
            .toList(growable: false),
        startsAt: _toInt(json['starts_at']),
        durationMinutes: _toInt(json['duration_minutes']),
        status: json['status'] as String? ?? 'booked',
        paymentStatus: json['payment_status'] as String? ?? 'none',
        depositAmountMinor:
            json['deposit_amount_minor'] == null ? null : _toInt(json['deposit_amount_minor']),
        priceOverrideMinor:
            json['price_override_minor'] == null ? null : _toInt(json['price_override_minor']),
        intendedRewardId: json['intended_reward_id'] as String?,
        appliedOfferRef: json['applied_offer_ref'] as String?,
        appliedOfferText: json['applied_offer_text'] as String?,
        note: json['note'] as String? ?? '',
        cancelledReason: json['cancelled_reason'] as String?,
        quantities: ((json['quantities'] as Map?) ?? const {}).map(
          (k, v) => MapEntry(k.toString(), _toInt(v)),
        ),
      );
}

/// «مؤشّر عدم الحضور» — a number beside her name, never a verdict (docs/وصف-تطبيق-الحجوزات.md
/// §2.6), the same contract `noShowRisk` gives the console.
class NoShowRisk {
  final int considered;
  final int noShows;
  final bool risky;
  final int thresholdPercent;

  const NoShowRisk({
    required this.considered,
    required this.noShows,
    required this.risky,
    required this.thresholdPercent,
  });

  factory NoShowRisk.fromJson(Map<String, dynamic> json) => NoShowRisk(
        considered: _toInt(json['considered']),
        noShows: _toInt(json['no_shows']),
        risky: json['risky'] as bool? ?? false,
        thresholdPercent: _toInt(json['threshold_percent']),
      );
}

/// The shop's own "auto" tie-breaker — which of an "auto" service's several free, eligible
/// operators actually gets a given slot. Mirrors `AssignmentSettings` in apps/console/src/api.ts
/// exactly. `manualOrder` only means anything when `algorithm == 'manual_order'`.
class AssignmentSettings {
  final String algorithm; // nearest | least_loaded | manual_order
  final List<String> manualOrder;

  const AssignmentSettings({required this.algorithm, required this.manualOrder});

  factory AssignmentSettings.fromJson(Map<String, dynamic> json) => AssignmentSettings(
        algorithm: json['algorithm'] as String? ?? 'nearest',
        manualOrder: ((json['manual_order'] as List?) ?? const [])
            .map((e) => e.toString())
            .toList(growable: false),
      );

  Map<String, dynamic> toJson() => {'algorithm': algorithm, 'manual_order': manualOrder};

  AssignmentSettings copyWith({String? algorithm, List<String>? manualOrder}) => AssignmentSettings(
        algorithm: algorithm ?? this.algorithm,
        manualOrder: manualOrder ?? this.manualOrder,
      );
}

/// One real, open slot the «أي متاح» merge found — always names the operator it belongs to.
class BookingSlot {
  final String operatorId;
  final int startsAt;
  const BookingSlot({required this.operatorId, required this.startsAt});

  factory BookingSlot.fromJson(Map<String, dynamic> json) => BookingSlot(
        operatorId: json['operator_id'] as String? ?? '',
        startsAt: _toInt(json['starts_at']),
      );
}
