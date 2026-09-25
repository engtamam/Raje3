int _toInt(dynamic v) => v is num ? v.toInt() : int.tryParse('$v') ?? 0;

/// The three real kinds `services/loyalty/app/api/v1/loyalty.py`'s own `RewardIn.type` accepts —
/// never a fourth invented one. A shop calls its catalogue "services" or "products"; nothing here
/// reads that word, so `service` covers both — see apps/console/src/screens/Points.tsx's own note
/// on why the old service/item split decided nothing real.
enum RewardType { service, item, discount }

extension RewardTypeValue on RewardType {
  String get value => switch (this) {
        RewardType.service => 'service',
        RewardType.item => 'item',
        RewardType.discount => 'discount',
      };
}

RewardType rewardTypeFromValue(String value) => switch (value) {
      'service' => RewardType.service,
      'discount' => RewardType.discount,
      _ => RewardType.item,
    };

/// `Reward.to_dict()` — `cost`, never `cost_points` (a field the real API does not have, per
/// Points.tsx's own module note on a bug that shipped from guessing it).
class Reward {
  final String id;
  final String name;
  final int cost;
  final RewardType type;
  final String serviceId;
  final int discountHalalas;
  final bool active;

  const Reward({
    required this.id,
    required this.name,
    required this.cost,
    required this.type,
    required this.serviceId,
    required this.discountHalalas,
    required this.active,
  });

  factory Reward.fromJson(Map<String, dynamic> json) => Reward(
        id: json['id'] as String? ?? '',
        name: json['name'] as String? ?? '',
        cost: _toInt(json['cost']),
        type: rewardTypeFromValue(json['type'] as String? ?? 'item'),
        serviceId: json['service_id'] as String? ?? '',
        discountHalalas: _toInt(json['discount_halalas']),
        active: json['active'] as bool? ?? true,
      );
}

/// `services/loyalty/app/core/report.py::build`'s own real output — every field it returns, none
/// invented. `expiredShare` is its own docstring's "the one indicator that is a warning": how
/// much of everything ever granted died unspent, unclaimed.
class LoyaltyReport {
  final int outstanding;
  final int granted;
  final int consumed;
  final int expiredUnredeemed;
  final double expiredShare;
  final int redemptions;
  final int customers;
  final List<(String, int)> topRewards;

  const LoyaltyReport({
    required this.outstanding,
    required this.granted,
    required this.consumed,
    required this.expiredUnredeemed,
    required this.expiredShare,
    required this.redemptions,
    required this.customers,
    required this.topRewards,
  });

  factory LoyaltyReport.fromJson(Map<String, dynamic> json) => LoyaltyReport(
        outstanding: _toInt(json['outstanding']),
        granted: _toInt(json['granted']),
        consumed: _toInt(json['consumed']),
        expiredUnredeemed: _toInt(json['expired_unredeemed']),
        expiredShare: (json['expired_share'] as num?)?.toDouble() ?? 0.0,
        redemptions: _toInt(json['redemptions']),
        customers: _toInt(json['customers']),
        topRewards: ((json['top_rewards'] as List?) ?? const [])
            .whereType<List>()
            .where((row) => row.length >= 2)
            .map((row) => (row[0].toString(), _toInt(row[1])))
            .toList(),
      );
}
