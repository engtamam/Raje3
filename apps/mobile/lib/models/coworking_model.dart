// Mirrors services/coworking/app/core/models.py's own `Resource.public()`/booking dict/join row
// exactly — no field invented here that the backend does not actually send.

int _toInt(dynamic v) {
  if (v is num) return v.toInt();
  if (v is String) return int.tryParse(v) ?? 0;
  return 0;
}

/// A window in minutes-since-midnight, e.g. `[540, 780]` == 09:00-13:00.
class CoworkingWindow {
  final int startMinute;
  final int endMinute;
  const CoworkingWindow({required this.startMinute, required this.endMinute});

  factory CoworkingWindow.fromList(dynamic pair) =>
      CoworkingWindow(startMinute: _toInt(pair[0]), endMinute: _toInt(pair[1]));

  List<int> toList() => [startMinute, endMinute];
  Map<String, dynamic> toJson() => {'start_minute': startMinute, 'end_minute': endMinute};
}

/// «مورد» — one bookable chair/room/desk. Mirrors `Resource.public()` field for field
/// (`image_key` never leaves the backend — `has_image` is the one signal this app gets).
class CoworkingResource {
  final String id;
  final String name;
  final bool active;
  final int hourlyPriceMinor;
  final Map<int, List<CoworkingWindow>> weekly; // weekday 0=Monday..6=Sunday
  final Map<String, dynamic> exceptions; // date -> {closed, windows}
  final int createdAt;
  final String branchId; // "" == unassigned, visible to every branch
  final String description;
  final bool hasImage;

  const CoworkingResource({
    required this.id,
    required this.name,
    required this.active,
    required this.hourlyPriceMinor,
    required this.weekly,
    required this.exceptions,
    required this.createdAt,
    required this.branchId,
    required this.description,
    required this.hasImage,
  });

  factory CoworkingResource.fromJson(Map<String, dynamic> j) {
    final rawWeekly = (j['weekly'] as Map?) ?? const {};
    final weekly = <int, List<CoworkingWindow>>{};
    for (final entry in rawWeekly.entries) {
      final day = int.tryParse(entry.key.toString()) ?? -1;
      if (day < 0) continue;
      weekly[day] = ((entry.value as List?) ?? const [])
          .map((w) => CoworkingWindow.fromList(w))
          .toList(growable: false);
    }
    return CoworkingResource(
      id: (j['id'] as String?) ?? '',
      name: (j['name'] as String?) ?? '',
      active: j['active'] as bool? ?? true,
      hourlyPriceMinor: _toInt(j['hourly_price_minor']),
      weekly: weekly,
      exceptions: Map<String, dynamic>.from((j['exceptions'] as Map?) ?? const {}),
      createdAt: _toInt(j['created_at']),
      branchId: (j['branch_id'] as String?) ?? '',
      description: (j['description'] as String?) ?? '',
      hasImage: j['has_image'] as bool? ?? false,
    );
  }
}

/// «طلب انضمام» — one freelancer phone's own gate row. Mirrors `core/joins.py`'s own row shape
/// (`{tenant, phone, status, created_at, decided_at}`) minus `tenant` (never sent to a client).
class CoworkingJoin {
  final String phone;
  final String status; // pending | approved | blocked
  final int createdAt;
  final int decidedAt;

  const CoworkingJoin({
    required this.phone,
    required this.status,
    required this.createdAt,
    required this.decidedAt,
  });

  factory CoworkingJoin.fromJson(Map<String, dynamic> j) => CoworkingJoin(
        phone: (j['phone'] as String?) ?? '',
        status: (j['status'] as String?) ?? 'pending',
        createdAt: _toInt(j['created_at']),
        decidedAt: _toInt(j['decided_at']),
      );
}

/// «حجز مساحة العمل» — mirrors `core/bookings.py`'s own stored dict exactly (never `Booking`
/// from booking_model.dart — this app has its own, deliberately smaller, lifecycle; see
/// `core/models.py`'s own module doc on why the two are not shared).
class CoworkingBooking {
  final String id;
  final String resourceId;
  final String freelancerPhone;
  final int startsAt;
  final int endsAt;
  final int hourlyPriceMinor;
  final String branchId;
  final String status; // confirmed | cancelled
  final int createdAt;

  const CoworkingBooking({
    required this.id,
    required this.resourceId,
    required this.freelancerPhone,
    required this.startsAt,
    required this.endsAt,
    required this.hourlyPriceMinor,
    required this.branchId,
    required this.status,
    required this.createdAt,
  });

  factory CoworkingBooking.fromJson(Map<String, dynamic> j) => CoworkingBooking(
        id: (j['id'] as String?) ?? '',
        resourceId: (j['resource_id'] as String?) ?? '',
        freelancerPhone: (j['freelancer_phone'] as String?) ?? '',
        startsAt: _toInt(j['starts_at']),
        endsAt: _toInt(j['ends_at']),
        hourlyPriceMinor: _toInt(j['hourly_price_minor']),
        branchId: (j['branch_id'] as String?) ?? '',
        status: (j['status'] as String?) ?? 'confirmed',
        createdAt: _toInt(j['created_at']),
      );
}
