/// «خدمات متنقلة» — mirrors services/operations/app/core/mobile_requests.py's own
/// `MobileServiceRequest.public()` shape EXACTLY (same fields, same meaning), the same contract
/// apps/console/src/screens/MobileRequests.tsx's own `MobileServiceRequest` interface already
/// reads. One source of truth on the server; this is its Dart mirror, not a second model design.
class MobileServiceRequest {
  final String id;
  final String tenant;
  final String phone;
  final String customerName;
  final List<String> serviceIds;
  final int requestedTime;
  final double lat;
  final double lng;
  final String status;
  final int created;
  final int decidedAt;
  final String decidedBy;
  final String rejectReason;
  final String visitId;
  final String note;
  final String mapsUrl;
  final String assignedTo;

  const MobileServiceRequest({
    required this.id,
    required this.tenant,
    required this.phone,
    required this.customerName,
    required this.serviceIds,
    required this.requestedTime,
    required this.lat,
    required this.lng,
    required this.status,
    required this.created,
    required this.decidedAt,
    required this.decidedBy,
    required this.rejectReason,
    required this.visitId,
    required this.note,
    required this.mapsUrl,
    required this.assignedTo,
  });

  factory MobileServiceRequest.fromJson(Map<String, dynamic> json) {
    return MobileServiceRequest(
      id: json['id'] as String? ?? '',
      tenant: json['tenant'] as String? ?? '',
      phone: json['phone'] as String? ?? '',
      customerName: json['customer_name'] as String? ?? '',
      serviceIds: ((json['service_ids'] as List?) ?? const [])
          .map((e) => e.toString())
          .toList(growable: false),
      requestedTime: (json['requested_time'] as num?)?.toInt() ?? 0,
      lat: (json['lat'] as num?)?.toDouble() ?? 0,
      lng: (json['lng'] as num?)?.toDouble() ?? 0,
      status: json['status'] as String? ?? 'pending',
      created: (json['created'] as num?)?.toInt() ?? 0,
      decidedAt: (json['decided_at'] as num?)?.toInt() ?? 0,
      decidedBy: json['decided_by'] as String? ?? '',
      rejectReason: json['reject_reason'] as String? ?? '',
      visitId: json['visit_id'] as String? ?? '',
      note: json['note'] as String? ?? '',
      mapsUrl: json['maps_url'] as String? ?? '',
      assignedTo: json['assigned_to'] as String? ?? '',
    );
  }
}

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

  factory NoShowRisk.fromJson(Map<String, dynamic> json) {
    return NoShowRisk(
      considered: (json['considered'] as num?)?.toInt() ?? 0,
      noShows: (json['no_shows'] as num?)?.toInt() ?? 0,
      risky: json['risky'] as bool? ?? false,
      thresholdPercent: (json['threshold_percent'] as num?)?.toInt() ?? 0,
    );
  }
}

/// A candidate to assign a request to — mirrors MobileRequests.tsx's own `StaffMember`, kept
/// separate from any richer team model the rest of this app has, since this screen needs only
/// id/name/active.
class MobileRequestOperator {
  final String id;
  final String name;

  const MobileRequestOperator({required this.id, required this.name});

  factory MobileRequestOperator.fromJson(Map<String, dynamic> json) {
    return MobileRequestOperator(
      id: json['id'] as String? ?? '',
      name: json['name'] as String? ?? '',
    );
  }
}
