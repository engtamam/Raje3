import 'package:dio/dio.dart';

import 'package:raje3_mobile/core/network/api_client.dart';
import 'package:raje3_mobile/models/mutual_benefit_model.dart';

/// «تبادل منافع» — mirrors `services/operations/app/api/v1/staff.py`'s own
/// `/mutual-benefit/*` routes exactly (9 real endpoints, all already live and proven by the
/// console screen; zero backend work for this mobile build — see parity/mutual-benefit.md). Terms are
/// immutable once proposed: no update route exists anywhere here, on purpose — a different grant
/// is a new agreement, never an edit to this one.
class MutualBenefitService {
  MutualBenefitService({required this.apiClient});
  final ApiClient apiClient;

  Future<List<MutualBenefitAgreement>?> list() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/staff/mutual-benefit/agreements');
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['agreements'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .map((m) => MutualBenefitAgreement.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false);
    } on DioException {
      return null;
    }
  }

  Future<MutualBenefitKpis?> kpis() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/staff/mutual-benefit/kpis');
      final body = response.data;
      if (body is! Map) return null;
      return MutualBenefitKpis.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  Future<List<MutualBenefitAuditEntry>?> auditLog(String agreementId) async {
    try {
      final response =
          await apiClient.dio.get<dynamic>('/api/v1/staff/mutual-benefit/agreements/$agreementId/audit-log');
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['entries'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .map((m) => MutualBenefitAuditEntry.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false);
    } on DioException {
      return null;
    }
  }

  /// `POST /mutual-benefit/agreements` — NO FREE TEXT ANYWHERE for what the grant is: a
  /// gift/discount-item names a real service id, a discount-group names a real package id, a
  /// blanket discount names neither.
  ///
  /// Returns `(agreement, null)` on success, `(null, statusCode)` on a refusal. The status CODE
  /// is real and usable — only the TEXT `detail` is stripped by the platform's own global error
  /// handler (the same CWE-209 posture this app already works around elsewhere, confirmed live: a
  /// real refusal came back as `{"error":"ERROR"}`, no reason string). `_mutual_benefit_error()` on the
  /// server maps every real refusal onto one of a handful of HTTP statuses (402/403/404/409/...),
  /// so the status alone is still enough to tell the owner something true and specific, never a
  /// guessed reason — see the UI's own status→sentence mapping.
  Future<(MutualBenefitAgreement?, int?)> propose({
    required String shopBPhone,
    required String conditionType,
    required String conditionValue,
    required int grantValidityDays,
    required int agreementDurationDays,
    int perPeriodCap = 0,
    String grantType = 'discount',
    String giftServiceId = '',
    String discountScope = 'blanket',
    String discountGroupId = '',
  }) async {
    try {
      final response = await apiClient.dio.post<dynamic>('/api/v1/staff/mutual-benefit/agreements', data: {
        'shop_b_phone': shopBPhone,
        'condition_type': conditionType,
        'condition_value': conditionValue,
        'grant_validity_days': grantValidityDays,
        'agreement_duration_days': agreementDurationDays,
        'per_period_cap': perPeriodCap,
        'grant_type': grantType,
        'gift_service_id': giftServiceId,
        'discount_scope': discountScope,
        'discount_group_id': discountGroupId,
      });
      final status = response.statusCode ?? 0;
      final body = response.data;
      // ApiClient's own `validateStatus` accepts every status under 500 except 401 as a
      // "successful" response (see its own doc comment) — a real refusal (402 not-subscribed,
      // 403/400/404/409) never throws a DioException here at all, so the status must be read off
      // the response itself, not assumed to only ever arrive via a catch block.
      if (status >= 400 || body is! Map) return (null, status >= 400 ? status : null);
      return (MutualBenefitAgreement.fromJson(Map<String, dynamic>.from(body)), null);
    } on DioException catch (e) {
      return (null, e.response?.statusCode);
    }
  }

  Future<bool> accept(String id) => _act('accept', id);
  Future<bool> reject(String id) => _act('reject', id);
  Future<bool> cancelRequest(String id) => _act('cancel-request', id);
  Future<bool> cancelConfirm(String id) => _act('cancel-confirm', id);

  Future<bool> _act(String verb, String id) async {
    try {
      final response =
          await apiClient.dio.post<dynamic>('/api/v1/staff/mutual-benefit/agreements/$id/$verb');
      // Same permissive `validateStatus` as `propose()` above — a real refusal (403 forbidden,
      // 409 wrong-state) resolves here rather than throwing, so success is never assumed from
      // reaching this line alone; the status itself is what decides it.
      return (response.statusCode ?? 0) < 400;
    } on DioException {
      return false;
    }
  }
}
