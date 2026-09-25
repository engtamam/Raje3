import 'package:dio/dio.dart';
import 'package:raje3_mobile/core/network/api_client.dart';
import 'package:raje3_mobile/models/rating_model.dart';

/// «التقييم» — every real route this screen needs (`operations.ratings`,
/// `operations.mark_rating_handled`, `operations.staff_performance`), same contract
/// apps/console/src/screens/Rating.tsx already calls. RAW `apiClient.dio` calls, same convention
/// every other mobile service in this app already holds to.
class RatingsService {
  final ApiClient apiClient;

  RatingsService({required this.apiClient});

  /// `GET /api/v1/field/ratings` — `stars` 0 means "all"; `handled` is the literal string
  /// `"true"`/`"false"`/`""` the real query param expects, never a Dart bool. Returns `null` on
  /// any failure; the caller tells that apart from "empty page" itself.
  Future<({List<RatingRow> rows, String? nextCursor})?> list({
    int stars = 0,
    String handled = '',
    String stepId = '',
    String cursor = '',
    String branchId = '',
  }) async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/field/ratings', queryParameters: {
        if (stars > 0) 'stars': stars,
        if (handled.isNotEmpty) 'handled': handled,
        if (stepId.isNotEmpty) 'step_id': stepId,
        if (cursor.isNotEmpty) 'after': cursor,
        if (branchId.isNotEmpty) 'branch_id': branchId,
        'limit': 30,
      });
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['ratings'] as List?) ?? const [];
      return (
        rows: rows
            .whereType<Map>()
            .map((m) => RatingRow.fromJson(Map<String, dynamic>.from(m)))
            .toList(growable: false),
        nextCursor: body['next_cursor'] as String?,
      );
    } on DioException {
      return null;
    }
  }

  /// `PATCH /api/v1/field/ratings/{visit_id}/handled` — `null` on success, the server's own
  /// refusal sentence otherwise (e.g. "هذي الزيارة ما فيها تقييم لتُعالَج.").
  Future<String?> markHandled(String visitId, {String note = ''}) async {
    try {
      final response = await apiClient.dio
          .patch<dynamic>('/api/v1/field/ratings/$visitId/handled', data: {'note': note});
      final body = response.data;
      if (body is Map && body['handled'] == true) return null;
      return (body is Map ? body['reason'] as String? : null) ?? '';
    } on DioException {
      return '';
    }
  }

  /// `GET /api/v1/field/staff/performance` — `since`/`until` in epoch seconds. `null` on any
  /// failure (including this operator lacking `operations.manage`, which the caller should have
  /// already checked via the catalogue before calling this at all).
  Future<List<StaffPerformance>?> staffPerformance(
      {required int since, required int until, String branchId = ''}) async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/field/staff/performance',
          queryParameters: {
            'since': since,
            'until': until,
            if (branchId.isNotEmpty) 'branch_id': branchId,
          });
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['staff'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .map((m) => StaffPerformance.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false);
    } on DioException {
      return null;
    }
  }

  /// `GET /api/v1/staff/operators/{id}/step-stats` — fetched lazily, only once an operator is
  /// actually opened (never prefetched for every row), same "ask only when asked" rule the
  /// console's own quadrant UI already holds to.
  Future<List<OperatorStepStat>?> operatorStepStats(String operatorId) async {
    try {
      final response =
          await apiClient.dio.get<dynamic>('/api/v1/staff/operators/$operatorId/step-stats');
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['step_stats'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .map((m) => OperatorStepStat.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false);
    } on DioException {
      return null;
    }
  }

  /// `POST /api/v1/field/staff/performance/export` — the report as raw bytes (PDF or DOCX), not
  /// JSON; the caller writes them to a temp file and hands that to the OS share sheet. `null` on
  /// any failure.
  Future<List<int>?> exportStaffPerformance({
    required int since,
    required int until,
    required String fileFormat, // "pdf" | "docx"
    String locale = 'ar',
    String branchId = '',
  }) async {
    try {
      final response = await apiClient.dio.post<List<int>>(
        '/api/v1/field/staff/performance/export',
        data: {
          'since': since,
          'until': until,
          'file_format': fileFormat,
          'locale': locale,
          if (branchId.isNotEmpty) 'branch_id': branchId,
        },
        options: Options(responseType: ResponseType.bytes),
      );
      return response.data;
    } on DioException {
      return null;
    }
  }
}
