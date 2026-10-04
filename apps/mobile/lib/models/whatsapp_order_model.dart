/// «طلبات التوصيل عبر الواتساب» — mirrors services/operations/app/core/orders.py's own
/// `Order.public()` shape exactly, the same subset apps/console/src/screens/WhatsAppOrders.tsx's
/// own `Order` interface already reads.
class OrderLine {
  final String serviceId;
  final String name;
  final int quantity;
  final int unitPriceMinor;
  final int lineTotalMinor;

  const OrderLine({
    required this.serviceId,
    required this.name,
    required this.quantity,
    required this.unitPriceMinor,
    required this.lineTotalMinor,
  });

  factory OrderLine.fromJson(Map<String, dynamic> json) => OrderLine(
        serviceId: json['service_id'] as String? ?? '',
        name: json['name'] as String? ?? '',
        quantity: (json['quantity'] as num?)?.toInt() ?? 0,
        unitPriceMinor: (json['unit_price_minor'] as num?)?.toInt() ?? 0,
        lineTotalMinor: (json['line_total_minor'] as num?)?.toInt() ?? 0,
      );
}

class WhatsAppOrder {
  final String id;
  final String tenant;
  final String branchId;
  final String phone;
  final String customerName;
  final List<OrderLine> lines;
  final int totalMinor;
  final int amountDueMinor;
  final int discountMinor;
  final String discountSource;
  final String pointsRewardName;
  final int pointsRewardMinor;
  final double lat;
  final double lng;
  final String mapsUrl;
  final String status;
  final int created;
  final int paidAmountMinor;
  final String paymentRef;
  final String cancelReason;
  final String note;

  const WhatsAppOrder({
    required this.id,
    required this.tenant,
    required this.branchId,
    required this.phone,
    required this.customerName,
    required this.lines,
    required this.totalMinor,
    required this.amountDueMinor,
    required this.discountMinor,
    required this.discountSource,
    required this.pointsRewardName,
    required this.pointsRewardMinor,
    required this.lat,
    required this.lng,
    required this.mapsUrl,
    required this.status,
    required this.created,
    required this.paidAmountMinor,
    required this.paymentRef,
    required this.cancelReason,
    required this.note,
  });

  factory WhatsAppOrder.fromJson(Map<String, dynamic> json) {
    return WhatsAppOrder(
      id: json['id'] as String? ?? '',
      tenant: json['tenant'] as String? ?? '',
      branchId: json['branch_id'] as String? ?? '',
      phone: json['phone'] as String? ?? '',
      customerName: json['customer_name'] as String? ?? '',
      lines: ((json['lines'] as List?) ?? const [])
          .whereType<Map>()
          .map((m) => OrderLine.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false),
      totalMinor: (json['total_minor'] as num?)?.toInt() ?? 0,
      amountDueMinor: (json['amount_due_minor'] as num?)?.toInt() ?? 0,
      discountMinor: (json['discount_minor'] as num?)?.toInt() ?? 0,
      discountSource: json['discount_source'] as String? ?? '',
      pointsRewardName: json['points_reward_name'] as String? ?? '',
      pointsRewardMinor: (json['points_reward_minor'] as num?)?.toInt() ?? 0,
      lat: (json['lat'] as num?)?.toDouble() ?? 0,
      lng: (json['lng'] as num?)?.toDouble() ?? 0,
      mapsUrl: json['maps_url'] as String? ?? '',
      status: json['status'] as String? ?? 'received',
      created: (json['created'] as num?)?.toInt() ?? 0,
      paidAmountMinor: (json['paid_amount_minor'] as num?)?.toInt() ?? 0,
      paymentRef: json['payment_ref'] as String? ?? '',
      cancelReason: json['cancel_reason'] as String? ?? '',
      note: json['note'] as String? ?? '',
    );
  }
}
