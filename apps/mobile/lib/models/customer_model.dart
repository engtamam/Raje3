import 'package:raje3_mobile/models/points_model.dart' show Reward;

/// Lenient int read — found live: `CustomerAsset.year` came back as `""` (empty string) on a
/// real record, not `0` or absent, and a bare `as num?` cast throws a real `TypeError` on any
/// String value rather than returning null. Every numeric field in this file reads through this
/// instead of a direct cast, so a field the server sends as a string (or an empty one) degrades
/// to the same "no data" `0`, never crashes the screen.
int _toInt(dynamic v) {
  if (v is num) return v.toInt();
  if (v is String) return int.tryParse(v) ?? 0;
  return 0;
}

/// «عملائي» — mirrors services/operations/app's own `Customer.public()`/customer-record shape,
/// the same contract apps/console/src/screens/Customers.tsx and Customer.tsx already read.
class Customer {
  final String id;
  final String phone;
  final String name;
  final int created;
  final int lastVisit;
  final int visitCount;
  final String lastBranchId;
  final String source;
  final String subjectRef;

  const Customer({
    required this.id,
    required this.phone,
    required this.name,
    required this.created,
    required this.lastVisit,
    required this.visitCount,
    required this.lastBranchId,
    required this.source,
    required this.subjectRef,
  });

  factory Customer.fromJson(Map<String, dynamic> json) {
    return Customer(
      id: json['id'] as String? ?? '',
      phone: json['phone'] as String? ?? '',
      name: json['name'] as String? ?? '',
      created: _toInt(json['created']),
      lastVisit: _toInt(json['last_visit']),
      visitCount: _toInt(json['visit_count']),
      lastBranchId: json['last_branch_id'] as String? ?? '',
      source: json['source'] as String? ?? '',
      subjectRef: json['subject_ref'] as String? ?? '',
    );
  }
}

/// A search-suggest hit — a DELIBERATELY trimmer shape than [Customer]: the search index never
/// carries `last_visit`/`visit_count`, so those fields render as "no data," never a guessed 0 —
/// see Customers.tsx's own header note on this distinction.
class CustomerHit {
  final String id;
  final String phone;
  final String name;

  const CustomerHit({required this.id, required this.phone, required this.name});

  factory CustomerHit.fromJson(Map<String, dynamic> json) {
    return CustomerHit(
      id: json['id'] as String? ?? '',
      phone: json['phone'] as String? ?? '',
      name: json['name'] as String? ?? '',
    );
  }
}

class CustomerAsset {
  final String id;
  final String plate;
  final String make;
  final String model;
  final int year;

  const CustomerAsset({
    required this.id,
    required this.plate,
    required this.make,
    required this.model,
    required this.year,
  });

  factory CustomerAsset.fromJson(Map<String, dynamic> json) {
    return CustomerAsset(
      id: json['id'] as String? ?? '',
      plate: json['plate'] as String? ?? '',
      make: json['make'] as String? ?? '',
      model: json['model'] as String? ?? '',
      year: _toInt(json['year']),
    );
  }
}

class CustomerVisit {
  final String id;
  final int occurredAt;
  final int totalMinor;
  final String services;
  final int? rating;
  final String note;
  final bool free;
  final int meter;

  const CustomerVisit({
    required this.id,
    required this.occurredAt,
    required this.totalMinor,
    required this.services,
    required this.rating,
    required this.note,
    required this.free,
    required this.meter,
  });

  factory CustomerVisit.fromJson(Map<String, dynamic> json) {
    return CustomerVisit(
      id: json['id'] as String? ?? '',
      occurredAt: _toInt(json['occurred_at']),
      totalMinor: _toInt(json['total_minor']),
      services: json['services'] as String? ?? '',
      rating: json['rating'] == null ? null : _toInt(json['rating']),
      note: json['note'] as String? ?? '',
      free: json['free'] as bool? ?? false,
      meter: _toInt(json['meter']),
    );
  }
}

class RepeatedIssue {
  final String id;
  final String text;
  final String severity;
  final int count;

  const RepeatedIssue(
      {required this.id, required this.text, required this.severity, required this.count});

  factory RepeatedIssue.fromJson(Map<String, dynamic> json) {
    return RepeatedIssue(
      id: json['id'] as String? ?? '',
      text: json['text'] as String? ?? '',
      severity: json['severity'] as String? ?? 'normal',
      count: _toInt(json['count']),
    );
  }
}

/// The full customer record — `GET /api/v1/field/customers/{id}` (`operations.customer`).
class CustomerRecord {
  final Customer customer;
  final List<CustomerAsset> assets;
  final List<CustomerVisit> visits;
  final List<RepeatedIssue> repeatedIssues;

  const CustomerRecord({
    required this.customer,
    required this.assets,
    required this.visits,
    required this.repeatedIssues,
  });

  factory CustomerRecord.fromJson(Map<String, dynamic> json) {
    return CustomerRecord(
      customer: Customer.fromJson(Map<String, dynamic>.from(json['customer'] as Map)),
      assets: ((json['assets'] as List?) ?? const [])
          .whereType<Map>()
          .map((m) => CustomerAsset.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false),
      visits: ((json['visits'] as List?) ?? const [])
          .whereType<Map>()
          .map((m) => CustomerVisit.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false),
      repeatedIssues: ((json['repeated_issues'] as List?) ?? const [])
          .whereType<Map>()
          .map((m) => RepeatedIssue.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false),
    );
  }
}

/// `GET /api/v1/reminders/offers` (`reminders.customer_offers`) — one live or expired offer.
class CustomerOffer {
  final String text;
  final int expiresAt;
  final int sentAt;
  final bool live;

  const CustomerOffer(
      {required this.text, required this.expiresAt, required this.sentAt, required this.live});

  factory CustomerOffer.fromJson(Map<String, dynamic> json) {
    return CustomerOffer(
      text: json['text'] as String? ?? '',
      expiresAt: _toInt(json['expires_at']),
      sentAt: _toInt(json['sent_at']),
      live: json['live'] as bool? ?? false,
    );
  }
}

/// `GET /api/v1/loyalty/balance/{subject_ref}` (`loyalty.balance`). THE REAL SERVER FIELD IS
/// `points`, NOT `balance` — apps/console/src/screens/Customer.tsx's own local `Balance` type
/// reads `.balance`, a latent bug in the console that this mobile model does not repeat.
class LoyaltyBalance {
  final int points;
  final int toNextReward;
  final int expiresAt;
  /// Redeemable rewards — the SAME route console's `balanceFor` already reads this field from;
  /// this model simply used to stop at `points` and never parse it, so nothing on mobile could
  /// ever offer «نية استرجاع مكافأة» at booking time.
  final List<Reward> rewards;

  const LoyaltyBalance({
    required this.points,
    required this.toNextReward,
    required this.expiresAt,
    this.rewards = const [],
  });

  factory LoyaltyBalance.fromJson(Map<String, dynamic> json) {
    return LoyaltyBalance(
      points: _toInt(json['points']),
      toNextReward: _toInt(json['to_next_reward']),
      expiresAt: _toInt(json['expires_at']),
      rewards: ((json['rewards'] as List?) ?? const [])
          .whereType<Map>()
          .map((m) => Reward.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false),
    );
  }
}

/// `GET /api/v1/loyalty/history/{subject_ref}` (`loyalty.history`) — the real field is
/// `entries`, not `history`/`moves` (another console-side latent mismatch this model avoids).
class LoyaltyMove {
  final int at;
  final int delta;
  /// The real ledger's own fixed category — `"redeem"`, `"adjust"`, etc. — never free text.
  final String reason;
  /// The actual human-written note, when the entry has one (a manual adjustment's own reason
  /// text) — separate from [reason]. Empty for entries no one wrote a note on (e.g. an automatic
  /// redemption).
  final String note;

  const LoyaltyMove({
    required this.at,
    required this.delta,
    required this.reason,
    required this.note,
  });

  factory LoyaltyMove.fromJson(Map<String, dynamic> json) {
    return LoyaltyMove(
      // THE REAL FIELD IS `created_at`, NOT `at` — found live, 2026-09-22: every history row
      // rendered "56 years ago" because this read a field that doesn't exist and silently fell
      // back to epoch zero.
      at: _toInt(json['created_at']),
      delta: _toInt(json['delta']),
      reason: json['reason'] as String? ?? '',
      note: json['note'] as String? ?? '',
    );
  }
}

/// `GET /api/v1/field/privacy-requests` (`operations.privacy_requests`) — a pending PDPL
/// request (access/copy/correction/erasure) a customer raised, waiting on the shop to answer.
/// Closing it here is purely "we answered" — it does NOT erase anything; actual erasure only
/// happens via [Customer]'s own erase action on their detail screen.
class PrivacyRequest {
  final String id;
  final String subjectRef;
  final String type; // "erase" | "copy" | ...
  final int at;
  final String status;
  final int closedAt;

  const PrivacyRequest({
    required this.id,
    required this.subjectRef,
    required this.type,
    required this.at,
    required this.status,
    required this.closedAt,
  });

  bool get isClosed => closedAt > 0;

  factory PrivacyRequest.fromJson(Map<String, dynamic> json) {
    return PrivacyRequest(
      id: json['id'] as String? ?? '',
      subjectRef: json['subject_ref'] as String? ?? '',
      type: json['type'] as String? ?? '',
      at: _toInt(json['at']),
      status: json['status'] as String? ?? '',
      closedAt: _toInt(json['closed_at']),
    );
  }
}

/// `GET /api/v1/reminders/rules?subject_ref=` (`reminders.list_rules`) — how often this
/// customer's own service reminder cycle is set, per service. `key` IS WHATEVER THE ROW'S OWN
/// `id`/`service_id` FIELD HOLDS — the real key `PUT /api/v1/reminders/rules/{rule_key}` needs,
/// never recomputed client-side (mirrors apps/console/src/screens/Customer.tsx's own call).
class ReminderRule {
  final String key;
  final String serviceId;
  /// The reminders service's OWN name for this row, when it sent one — `null`, never the raw
  /// `serviceId`, when it didn't. A raw id is never a display value; the caller resolves a real
  /// name from the shop's own service catalogue (see CustomersService.serviceNames) and only
  /// falls back to an honest "unknown service" label if even that lookup comes up empty.
  final String? serviceName;
  final int intervalDays;
  final int leadDays;
  final int observations;
  final bool learned;

  const ReminderRule({
    required this.key,
    required this.serviceId,
    required this.serviceName,
    required this.intervalDays,
    required this.leadDays,
    required this.observations,
    required this.learned,
  });

  factory ReminderRule.fromJson(Map<String, dynamic> json) {
    final id = json['id'] as String? ?? '';
    final serviceId = json['service_id'] as String? ?? '';
    final rawName = json['service_name'] as String?;
    return ReminderRule(
      key: id.isNotEmpty ? id : serviceId,
      serviceId: serviceId,
      serviceName: (rawName != null && rawName.isNotEmpty) ? rawName : null,
      intervalDays: _toInt(json['interval_days']),
      leadDays: _toInt(json['lead_days']),
      observations: _toInt(json['observations']),
      learned: json['learned'] as bool? ?? false,
    );
  }
}

/// `GET /api/v1/reminders/log?subject_ref=` (`reminders.log`) — what was actually sent to this
/// customer, chronologically. `unavailable` (a real sentence, not a bool) means a branch-scope
/// check refused the read — told apart from "nothing was ever sent."
class ReminderLogEntry {
  final int at;
  final String templateType;
  final String outcome;
  final String reason;

  const ReminderLogEntry({
    required this.at,
    required this.templateType,
    required this.outcome,
    required this.reason,
  });

  factory ReminderLogEntry.fromJson(Map<String, dynamic> json) {
    return ReminderLogEntry(
      at: _toInt(json['at']),
      templateType: json['template_type'] as String? ?? '',
      outcome: json['outcome'] as String? ?? '',
      reason: json['reason'] as String? ?? '',
    );
  }
}

/// `GET /api/v1/bookings/for-customer?customer_id=` — NOT catalog-gated (see
/// core/services/customers_service.dart's own doc comment on this route). Across every branch
/// the customer was ever served at, never scoped to the caller's own branch.
class CustomerBooking {
  final String id;
  final int startsAt;
  final String status; // booked|attended|no_show|cancelled

  const CustomerBooking({required this.id, required this.startsAt, required this.status});

  factory CustomerBooking.fromJson(Map<String, dynamic> json) {
    return CustomerBooking(
      id: json['id'] as String? ?? '',
      startsAt: _toInt(json['starts_at']),
      status: json['status'] as String? ?? 'booked',
    );
  }
}
