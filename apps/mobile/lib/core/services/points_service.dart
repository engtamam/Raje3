import 'package:dio/dio.dart';
import 'package:raje3_mobile/core/network/api_client.dart';
import 'package:raje3_mobile/models/points_model.dart';

/// «نقاط الولاء» — the shop's own reward catalogue and its report, same real routes
/// apps/console/src/screens/Points.tsx already calls (`loyalty.rewards.list/create/update`,
/// `loyalty.report`). Earning settings (points per service/group/general) are deliberately NOT
/// here — that tree was already built under «خدماتي ومنتجاتي»
/// (services_catalogue_service.dart's own earnSettings/setGeneralPoints/setServicePoints), and
/// this file never re-reads or re-writes the same data through a second path.
class PointsService {
  final ApiClient apiClient;

  PointsService({required this.apiClient});

  /// `GET /api/v1/loyalty/rewards?include_retired=` — retired ones included by default HERE
  /// (unlike the redemption sheet's own default): «إيقاف» must not make a reward vanish, or
  /// there is nothing left on screen to press «تفعيل» on.
  Future<List<Reward>?> list({bool includeRetired = true}) async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/loyalty/rewards',
          queryParameters: {'include_retired': includeRetired});
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['rewards'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .map((m) => Reward.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false);
    } on DioException {
      return null;
    }
  }

  /// `POST /api/v1/loyalty/rewards` — `discountHalalas` only meaningful for
  /// [RewardType.discount], `serviceId` only for [RewardType.service]; the server itself ignores
  /// whichever does not apply to the chosen type. Returns the server's own real refusal sentence
  /// on failure, `null` on success.
  Future<String?> create({
    required String name,
    required int cost,
    required RewardType type,
    String serviceId = '',
    int discountHalalas = 0,
  }) async {
    try {
      final response = await apiClient.dio.post<dynamic>('/api/v1/loyalty/rewards', data: {
        'name': name,
        'cost': cost,
        'type': type.value,
        'service_id': serviceId,
        'discount_halalas': discountHalalas,
      });
      final status = response.statusCode ?? 0;
      if (status >= 200 && status < 300) return null;
      return _refusal(response.data);
    } on DioException catch (e) {
      return _refusal(e.response?.data);
    }
  }

  /// `PATCH /api/v1/loyalty/rewards/{id}` — every param `null` (the default) means "leave it";
  /// `active: false` retires it, `active: true` reinstates it. Same route for both.
  Future<String?> update(
    String rewardId, {
    String? name,
    int? cost,
    bool? active,
    int? discountHalalas,
  }) async {
    try {
      final response = await apiClient.dio.patch<dynamic>('/api/v1/loyalty/rewards/$rewardId',
          data: {
            if (name != null) 'name': name,
            if (cost != null) 'cost': cost,
            if (active != null) 'active': active,
            if (discountHalalas != null) 'discount_halalas': discountHalalas,
          });
      final status = response.statusCode ?? 0;
      if (status >= 200 && status < 300) return null;
      return _refusal(response.data);
    } on DioException catch (e) {
      return _refusal(e.response?.data);
    }
  }

  /// `GET /api/v1/loyalty/report` — the whole programme's own health, real numbers only.
  Future<LoyaltyReport?> report() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/loyalty/report');
      final body = response.data;
      if (body is! Map) return null;
      return LoyaltyReport.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  String _refusal(dynamic data) {
    if (data is! Map) return '';
    final message = data['message'] as String?;
    final reason = data['reason'] as String?;
    return (message?.isNotEmpty == true ? message : reason) ?? '';
  }
}
