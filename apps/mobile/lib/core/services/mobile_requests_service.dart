import 'package:dio/dio.dart';
import 'package:raje3_mobile/core/network/api_client.dart';
import 'package:raje3_mobile/models/mobile_request_model.dart';

/// «خدمات متنقلة» — every real route services/operations/app/api/v1/mobile_requests.py exposes,
/// same shape apps/console/src/screens/MobileRequests.tsx already calls through its catalogue
/// (`operations.mobile_requests_*`/`operations.mobile_request_*` action ids — see that screen's
/// own header for the full state machine this mirrors).
///
/// RAW `apiClient.dio` calls, not the wrapped `ApiClient.get<T>`/`post<T>` envelope — the SAME
/// choice `auth_service.dart`'s own fetchBranches/addBranch make for every `/api/v1/staff/...`
/// route: this service's real responses are plain JSON (`{"requests": [...]}`, a bare
/// `MobileServiceRequest.public()` object, ...), never this app's own `{success, data}` shape.
///
/// Every write is `_MANAGE`-only except accept/complete/no_show already declared reachable to a
/// plain field operator too, per the backend's own `_ANY` gate — but that operator-scoped
/// visibility is what the real capability catalogue already answers (`Catalog.hasAll`), not a
/// second check duplicated here. This class calls what it's told to; a screen that should not
/// show a button already never calls the method behind it.
class MobileRequestsService {
  final ApiClient apiClient;

  MobileRequestsService({required this.apiClient});

  static const String _base = '/api/v1/staff/mobile-requests';

  /// `GET /api/v1/staff/mobile-requests` — the server itself scopes an execute-tier caller to
  /// their own assigned requests; this never filters client-side on top of that.
  Future<List<MobileServiceRequest>?> list() async {
    try {
      final response = await apiClient.dio.get<dynamic>(_base);
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['requests'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .map((m) => MobileServiceRequest.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false);
    } on DioException {
      return null;
    }
  }

  /// `POST /api/v1/staff/mobile-requests` — manual/staff-typed creation. Lands `PENDING` always;
  /// never pre-approved just because a human at the shop typed it in (the server's own rule, this
  /// call simply carries it). Throws the server's own Arabic refusal sentence on failure (a bad
  /// time outside working hours, an invalid phone, …) so the caller can show it verbatim.
  Future<MobileServiceRequest> create({
    required String phone,
    required String customerName,
    required List<String> serviceIds,
    required int requestedTime,
    required double lat,
    required double lng,
    String operatorId = '',
  }) async {
    final response = await apiClient.dio.post<dynamic>(_base, data: {
      'phone': phone,
      'customer_name': customerName,
      'service_ids': serviceIds,
      'requested_time': requestedTime,
      'lat': lat,
      'lng': lng,
      if (operatorId.isNotEmpty) 'operator_id': operatorId,
    });
    return MobileServiceRequest.fromJson(Map<String, dynamic>.from(response.data as Map));
  }

  Future<NoShowRisk?> risk(String requestId) async {
    try {
      final response = await apiClient.dio.get<dynamic>('$_base/$requestId/risk');
      final body = response.data;
      if (body is! Map) return null;
      return NoShowRisk.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  Future<MobileServiceRequest?> assign(String requestId, String operatorId) =>
      _postAction('$_base/$requestId/assign', {'operator_id': operatorId});

  Future<MobileServiceRequest?> accept(String requestId) =>
      _postAction('$_base/$requestId/accept', const {});

  Future<MobileServiceRequest?> reject(String requestId, String reason) =>
      _postAction('$_base/$requestId/reject', {'reason': reason});

  Future<MobileServiceRequest?> complete(String requestId) =>
      _postAction('$_base/$requestId/complete', const {});

  Future<MobileServiceRequest?> noShow(String requestId) =>
      _postAction('$_base/$requestId/no-show', const {});

  Future<MobileServiceRequest?> _postAction(String path, Map<String, dynamic> data) async {
    try {
      final response = await apiClient.dio.post<dynamic>(path, data: data);
      final body = response.data;
      if (body is! Map) return null;
      return MobileServiceRequest.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  /// `GET /api/v1/staff/operators` — every candidate this tenant may assign a request to.
  Future<List<MobileRequestOperator>?> operators() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/staff/operators');
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['operators'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .where((m) => m['active'] != false)
          .map((m) => MobileRequestOperator.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false);
    } on DioException {
      return null;
    }
  }

  /// `GET /api/v1/bookings/working-hours` — a COURTESY read only, to steer the time picker away
  /// from an obviously-closed slot before the server's own `create()` call re-validates
  /// authoritatively. FAILS OPEN on purpose — a plain field operator may not hold `bookings.read`
  /// (the console's own DataPane-equivalent gate), and this screen's real time validation is, and
  /// must remain, the server's own `validate_requested_time()` — this never becomes a second
  /// source of truth a stale client copy could get wrong. `null` on ANY failure (network, 403,
  /// shape) simply means "no client-side hint available", not "the shop is closed".
  Future<Map<String, dynamic>?> workingHours() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/bookings/working-hours');
      final body = response.data;
      if (body is! Map) return null;
      final weekly = body['weekly'];
      return weekly is Map ? Map<String, dynamic>.from(weekly) : null;
    } on DioException {
      return null;
    }
  }
}
