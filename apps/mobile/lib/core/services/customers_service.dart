import 'package:dio/dio.dart';
import 'package:raje3_mobile/core/network/api_client.dart';
import 'package:raje3_mobile/models/customer_model.dart';

/// «عملائي» — every real route this screen needs, same catalog action ids
/// apps/console/src/screens/Customers.tsx/Customer.tsx already call (`operations.recent`,
/// `operations.customer_suggest`, `operations.customer`, `operations.ensure_customer`,
/// `operations.rename_customer`, `operations.erase_customer`, `reminders.customer_offers`,
/// `loyalty.balance`, `loyalty.history`, `loyalty.adjust`) — see the research pass behind this
/// file for the full contract. RAW `apiClient.dio` calls, same convention every other mobile
/// service in this app already holds to (auth_service.dart, mobile_requests_service.dart).
class CustomersService {
  final ApiClient apiClient;

  CustomersService({required this.apiClient});

  /// `GET /api/v1/field/customers/recent` — a fixed "recent up to 50," no cursor pagination
  /// (the real server has none to page through yet).
  Future<List<Customer>?> recent({String branchId = ''}) async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/field/customers/recent',
          queryParameters: {'limit': 50, if (branchId.isNotEmpty) 'branch_id': branchId});
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['customers'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .map((m) => Customer.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false);
    } on DioException {
      return null;
    }
  }

  /// `GET /api/v1/field/customers/suggest` — a REAL server prefix search, never a client-side
  /// filter of [recent]'s own list; `ok: false` means the search index itself is unreachable,
  /// told apart from "no matches" by the caller checking that flag, not an empty list alone.
  Future<({List<CustomerHit> hits, bool ok})> suggest(String prefix, {String branchId = ''}) async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/field/customers/suggest',
          queryParameters: {'prefix': prefix, if (branchId.isNotEmpty) 'branch_id': branchId});
      final body = response.data;
      if (body is! Map) return (hits: <CustomerHit>[], ok: false);
      final rows = (body['customers'] as List?) ?? const [];
      return (
        hits: rows
            .whereType<Map>()
            .map((m) => CustomerHit.fromJson(Map<String, dynamic>.from(m)))
            .toList(growable: false),
        ok: body['ok'] as bool? ?? true,
      );
    } on DioException {
      return (hits: <CustomerHit>[], ok: false);
    }
  }

  /// `POST /api/v1/field/customers/ensure` — resolve-or-create, no visit attached.
  Future<Customer?> ensure({required String phone, String name = ''}) async {
    try {
      final response = await apiClient.dio.post<dynamic>('/api/v1/field/customers/ensure',
          data: {'phone': phone, if (name.isNotEmpty) 'name': name});
      final body = response.data;
      if (body is! Map || body['customer'] == null) return null;
      return Customer.fromJson(Map<String, dynamic>.from(body['customer'] as Map));
    } on DioException {
      return null;
    }
  }

  /// `GET /api/v1/field/customers/by-phone` — resolves an already-picked customer's own
  /// `subject_ref`, the pseudonym offers/loyalty balance are actually keyed on. `null` on no
  /// match, same as a phone nobody has ever ensured.
  Future<Customer?> byPhone(String phone) async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/field/customers/by-phone',
          queryParameters: {'phone': phone});
      final body = response.data;
      if (body is! Map || body['customer'] == null) return null;
      return Customer.fromJson(Map<String, dynamic>.from(body['customer'] as Map));
    } on DioException {
      return null;
    }
  }

  /// `GET /api/v1/field/customers/{id}` — 404 (deliberately) if the customer isn't this tenant's.
  Future<CustomerRecord?> record(String customerId) async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/field/customers/$customerId');
      final body = response.data;
      if (body is! Map) return null;
      return CustomerRecord.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  /// `PATCH /api/v1/field/customers/{id}` — name only; phone is never editable (it's the
  /// identity every other record — points, offers, history — hangs off).
  Future<bool> rename(String customerId, String name) async {
    try {
      final response = await apiClient.dio
          .patch<dynamic>('/api/v1/field/customers/$customerId', data: {'name': name});
      final body = response.data;
      return body is Map && body['ok'] == true;
    } on DioException {
      return false;
    }
  }

  /// `POST /api/v1/field/customers/{id}/erase` — PDPL erasure, irreversible. Returns the
  /// server's own refusal sentence on failure (e.g. compliance unreachable), or `null` on
  /// success — the caller shows that sentence verbatim rather than a generic failure line.
  Future<String?> erase(String customerId) async {
    try {
      final response =
          await apiClient.dio.post<dynamic>('/api/v1/field/customers/$customerId/erase');
      final body = response.data;
      if (body is Map && body['ok'] == true) return null;
      return (body is Map ? body['reason'] as String? : null) ?? '';
    } on DioException {
      return '';
    }
  }

  /// `GET /api/v1/reminders/schedule?state=pending&limit=200` — the raw "due" schedule, keyed by
  /// pseudonym only (no name). "Overdue" is filtered from this by the caller: `due_at > 0 &&
  /// due_at <= now` (pending but the moment already passed), never re-derived any other way —
  /// the same set that badges "متأخر" on a plain list row, so both must read this one source.
  Future<List<String>?> overdueSubjectRefs() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/reminders/schedule',
          queryParameters: {'state': 'pending', 'limit': 200});
      final body = response.data;
      if (body is! Map) return null;
      final now = DateTime.now().millisecondsSinceEpoch ~/ 1000;
      final rows = (body['schedule'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .where((m) {
            final due = (m['due_at'] as num?)?.toInt() ?? 0;
            return due > 0 && due <= now;
          })
          .map((m) => m['subject_ref'] as String? ?? '')
          .where((ref) => ref.isNotEmpty)
          .toList(growable: false);
    } on DioException {
      return null;
    }
  }

  /// `POST /api/v1/field/customers/resolve` — turns a batch of pseudonyms back into real
  /// customer rows; an unknown ref is silently omitted, never reported as an error.
  Future<List<Customer>?> byRefs(List<String> refs, {String branchId = ''}) async {
    if (refs.isEmpty) return const [];
    try {
      final response = await apiClient.dio.post<dynamic>('/api/v1/field/customers/resolve',
          data: {'refs': refs},
          queryParameters: {if (branchId.isNotEmpty) 'branch_id': branchId});
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['customers'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .map((m) => Customer.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false);
    } on DioException {
      return null;
    }
  }

  /// `GET /api/v1/field/privacy-requests` — every pending PDPL request, resolved to real
  /// customers via [byRefs] by the caller (never a second parser here).
  Future<List<PrivacyRequest>?> privacyRequests() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/field/privacy-requests');
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['requests'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .map((m) => PrivacyRequest.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false);
    } on DioException {
      return null;
    }
  }

  /// `POST /api/v1/field/privacy-requests/{id}/close` — marks the request answered. Does NOT
  /// erase anything; actual erasure is [erase] on the customer's own detail screen.
  Future<bool> closePrivacyRequest(String requestId) async {
    try {
      final response =
          await apiClient.dio.post<dynamic>('/api/v1/field/privacy-requests/$requestId/close');
      final body = response.data;
      return body is Map && body['ok'] == true;
    } on DioException {
      return false;
    }
  }

  /// `GET /api/v1/reminders/offers` — live + expired, joined by the customer's own pseudonym.
  Future<List<CustomerOffer>?> offers(String subjectRef) async {
    if (subjectRef.isEmpty) return const [];
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/reminders/offers',
          queryParameters: {'subject_ref': subjectRef, 'include_expired': true});
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['offers'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .map((m) => CustomerOffer.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false);
    } on DioException {
      return null;
    }
  }

  /// `GET /api/v1/loyalty/balance/{subject_ref}` — gated SEPARATELY from the rest of the
  /// record: a failed/absent call here never blanks the customer's profile or visit history.
  Future<LoyaltyBalance?> loyaltyBalance(String subjectRef) async {
    if (subjectRef.isEmpty) return null;
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/loyalty/balance/$subjectRef');
      final body = response.data;
      if (body is! Map) return null;
      return LoyaltyBalance.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  Future<List<LoyaltyMove>?> loyaltyHistory(String subjectRef) async {
    if (subjectRef.isEmpty) return const [];
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/loyalty/history/$subjectRef');
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['entries'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .map((m) => LoyaltyMove.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false);
    } on DioException {
      return null;
    }
  }

  /// `POST /api/v1/loyalty/adjust` — the manual "apology" tool, `loyalty.manage`-gated (stricter
  /// than reading a balance). Returns the server's own refusal sentence on failure, `null` on
  /// success with the new balance carried alongside.
  Future<({bool ok, int? newBalance, String? reason})> adjustLoyalty({
    required String subjectRef,
    required int delta,
    required String note,
  }) async {
    try {
      final response = await apiClient.dio.post<dynamic>('/api/v1/loyalty/adjust', data: {
        'subject_ref': subjectRef,
        'delta': delta,
        'note': note,
        'idempotency_key': '${subjectRef}_${DateTime.now().microsecondsSinceEpoch}',
      });
      final body = response.data;
      if (body is! Map) return (ok: false, newBalance: null, reason: null);
      if (body['ok'] == true) {
        return (ok: true, newBalance: (body['balance'] as num?)?.toInt(), reason: null);
      }
      return (ok: false, newBalance: null, reason: body['reason'] as String?);
    } on DioException {
      return (ok: false, newBalance: null, reason: null);
    }
  }

  /// `GET /api/v1/reminders/rules?subject_ref=` — this customer's own adaptive reminder cycle
  /// per service, sorted by the server `updated desc`.
  Future<List<ReminderRule>?> reminderRules(String subjectRef) async {
    if (subjectRef.isEmpty) return const [];
    try {
      final response = await apiClient.dio
          .get<dynamic>('/api/v1/reminders/rules', queryParameters: {'subject_ref': subjectRef});
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['rules'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .map((m) => ReminderRule.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false);
    } on DioException {
      return null;
    }
  }

  /// `PUT /api/v1/reminders/rules/{rule_key}` — pins the interval, stops adaptive learning for
  /// that service/customer pair. `ruleKey` is [ReminderRule.key] verbatim, never recomputed.
  Future<bool> setReminderRule(String ruleKey, {required int intervalDays, int leadDays = 7}) async {
    try {
      final response = await apiClient.dio.put<dynamic>('/api/v1/reminders/rules/$ruleKey',
          data: {'interval_days': intervalDays, 'lead_days': leadDays});
      return response.data is Map && (response.data as Map)['rule'] != null;
    } on DioException {
      return false;
    }
  }

  /// `GET /api/v1/reminders/log?subject_ref=&limit=20` — what was actually sent to this
  /// customer. `unavailable` carries the server's own refusal sentence when a branch-scope check
  /// blocks the read — distinct from "nothing was ever sent" (an empty, non-null list).
  Future<({List<ReminderLogEntry>? entries, String? unavailable})> reminderLog(
      String subjectRef) async {
    if (subjectRef.isEmpty) return (entries: <ReminderLogEntry>[], unavailable: null);
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/reminders/log',
          queryParameters: {'subject_ref': subjectRef, 'limit': 20});
      final body = response.data;
      if (body is! Map) return (entries: null, unavailable: null);
      final rows = (body['log'] as List?) ?? const [];
      return (
        entries: rows
            .whereType<Map>()
            .map((m) => ReminderLogEntry.fromJson(Map<String, dynamic>.from(m)))
            .toList(growable: false),
        unavailable: body['unavailable'] as String?,
      );
    } on DioException {
      return (entries: null, unavailable: null);
    }
  }

  /// `GET /api/v1/bookings/for-customer?customer_id=` — NOT catalog-gated (same undeclared-route
  /// pattern console's own `bookingsForCustomer` uses): a shop with no bookings app simply gets
  /// `null` here, rendered as nothing, never an error.
  Future<List<CustomerBooking>?> bookingsForCustomer(String customerId) async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/bookings/for-customer',
          queryParameters: {'customer_id': customerId});
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['bookings'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .map((m) => CustomerBooking.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false);
    } on DioException {
      return null;
    }
  }

  /// `GET /api/v1/field/catalogue` — id→name for this shop's services, the SAME real endpoint
  /// visit_screen.dart and mobile_requests_screen.dart already fetch this from. Used to resolve
  /// [ReminderRule.serviceId] into a real name when the reminders service itself didn't carry
  /// one — never displaying the raw id on screen (see models/customer_model.dart's own doc
  /// comment on why that field exists as a client-side fallback at all).
  Future<Map<String, String>> serviceNames() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/field/catalogue');
      final body = response.data;
      if (body is! Map) return const {};
      final rows = (body['services'] as List?) ?? const [];
      return {
        for (final s in rows.whereType<Map>())
          (s['id'] as String? ?? ''): (s['name'] as String? ?? ''),
      };
    } on DioException {
      return const {};
    }
  }
}
