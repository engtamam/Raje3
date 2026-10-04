import 'package:dio/dio.dart';

import 'package:raje3_mobile/core/network/api_client.dart';
import 'package:raje3_mobile/models/partner_loyalty_model.dart';

/// «ولاء الشركاء» — mirrors `services/operations/app/api/v1/staff.py`'s own `/coupons/*` routes
/// exactly (6 real endpoints, all already live and proven by the console screen — see
/// parity/account.md and `apps/console/src/screens/Coupons.tsx`). Zero backend work for this
/// mobile build. Salla linking and the platform-admin cap/exception settings stay console-only
/// by explicit owner decision — never ported here.
class PartnerLoyaltyService {
  PartnerLoyaltyService({required this.apiClient});
  final ApiClient apiClient;

  static const _base = '/api/v1/staff/coupons';

  Future<List<CouponAttempt>?> history({int limit = 100}) async {
    try {
      final response =
          await apiClient.dio.get<dynamic>('$_base/history', queryParameters: {'limit': limit});
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['attempts'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .map((m) => CouponAttempt.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false);
    } on DioException {
      return null;
    }
  }

  Future<CouponStats?> stats() async {
    try {
      final response = await apiClient.dio.get<dynamic>('$_base/stats');
      final body = response.data;
      if (body is! Map) return null;
      return CouponStats.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  /// The grant form's own live hint — debounced by the caller, same as `Coupons.tsx`'s own
  /// `useEffect` (a Saudi mobile number is 10 digits; anything shorter is not worth asking yet).
  Future<CouponCheck?> check(String phone) async {
    try {
      final response =
          await apiClient.dio.get<dynamic>('$_base/check', queryParameters: {'phone': phone});
      final body = response.data;
      if (body is! Map) return null;
      return CouponCheck.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  Future<bool?> preferencesGet() async {
    try {
      final response = await apiClient.dio.get<dynamic>('$_base/preferences');
      final body = response.data;
      if (body is! Map) return null;
      return body['visit_grant_enabled'] as bool?;
    } on DioException {
      return null;
    }
  }

  Future<bool?> preferencesSet(bool visitGrantEnabled) async {
    try {
      final response = await apiClient.dio
          .patch<dynamic>('$_base/preferences', data: {'visit_grant_enabled': visitGrantEnabled});
      final body = response.data;
      if (body is! Map) return null;
      return body['visit_grant_enabled'] as bool?;
    } on DioException {
      return null;
    }
  }

  /// `POST /coupons/grant` — returns `(attempt, null)` on a real answer (success OR a named
  /// refusal — [CouponAttempt.outcome] carries which), `(null, statusCode)` only when the server
  /// itself could not be reached at all. Never throws for an ordinary refusal, matching this
  /// app's other real-refusal-over-generic-error services (e.g. `MutualBenefitService`).
  Future<(CouponAttempt?, int?)> grant({
    required String phone,
    required int percent,
    required bool general,
    required List<String> appKeys,
  }) async {
    try {
      final response = await apiClient.dio.post<dynamic>('$_base/grant', data: {
        'phone': phone,
        'percent': percent,
        'general': general,
        'app_keys': general ? const [] : appKeys,
      });
      final body = response.data;
      if (body is! Map) return (null, response.statusCode);
      return (CouponAttempt.fromJson(Map<String, dynamic>.from(body)), null);
    } on DioException catch (e) {
      return (null, e.response?.statusCode);
    }
  }
}
