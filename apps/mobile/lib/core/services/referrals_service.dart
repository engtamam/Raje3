import 'package:dio/dio.dart';
import 'package:raje3_mobile/core/network/api_client.dart';
import 'package:raje3_mobile/models/referral_model.dart';

/// «نظام الإحالة» — owner/staff-facing monitoring and campaign management, real routes only,
/// spanning TWO real backend services (never one, never invented):
///   - services/referrals/app/api/v1/admin.py (`referrals.manage`) — campaign create/list/toggle.
///   - services/operations/app/api/v1/referral_reports.py (`operations.read` /
///     `operations.affiliates_read`) — read-only performance reporting.
/// A campaign's own terms are IMMUTABLE once created (that module's own module docstring) — the
/// only mutation this file ever sends after creation is [setActive].
class ReferralsService {
  final ApiClient apiClient;

  ReferralsService({required this.apiClient});

  Future<List<ReferralCampaign>?> listCampaigns({bool activeOnly = false}) async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/referrals/campaigns',
          queryParameters: {'active_only': activeOnly});
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['campaigns'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .map((m) => ReferralCampaign.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false);
    } on DioException {
      return null;
    }
  }

  /// `POST /api/v1/referrals/campaigns` — every field below is real (`CampaignIn`, admin.py);
  /// returns the server's own real refusal sentence on failure, `null` on success.
  Future<String?> createCampaign({
    required String mode,
    required String rewardType,
    required Map<String, dynamic> rewardParams,
    required String newCustomerRewardType,
    required Map<String, dynamic> newCustomerRewardParams,
    int xTimesLimit = 0,
    int minSpendMinor = 0,
    String usageCapPeriod = '',
    int usageCapLimit = 0,
    String capScope = kCapScopeCampaign,
  }) async {
    try {
      final response = await apiClient.dio.post<dynamic>('/api/v1/referrals/campaigns', data: {
        'mode': mode,
        'reward_type': rewardType,
        'reward_params': rewardParams,
        'new_customer_reward_type': newCustomerRewardType,
        'new_customer_reward_params': newCustomerRewardParams,
        'x_times_limit': xTimesLimit,
        'min_spend_minor': minSpendMinor,
        'usage_cap_period': usageCapPeriod,
        'usage_cap_limit': usageCapLimit,
        'cap_scope': capScope,
      });
      final status = response.statusCode ?? 0;
      if (status >= 200 && status < 300) return null;
      return _refusal(response.data);
    } on DioException catch (e) {
      return _refusal(e.response?.data);
    }
  }

  /// `PUT /api/v1/referrals/campaigns/{id}/active` — pause/resume, the ONLY mutable field once a
  /// campaign exists (services/referrals/app/core/models.py's own module docstring).
  Future<String?> setActive(String campaignId, {required bool active}) async {
    try {
      final response = await apiClient.dio
          .put<dynamic>('/api/v1/referrals/campaigns/$campaignId/active', data: {'active': active});
      final status = response.statusCode ?? 0;
      if (status >= 200 && status < 300) return null;
      return _refusal(response.data);
    } on DioException catch (e) {
      return _refusal(e.response?.data);
    }
  }

  /// `GET /api/v1/referrals/reports/summary` — `since`/`until` in unix seconds, `since: 0` reads
  /// every grant ever registered at this shop.
  Future<ReferralSummary?> summary({int since = 0, int? until}) async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/referrals/reports/summary',
          queryParameters: {'since': since, if (until != null) 'until': until});
      final body = response.data;
      if (body is! Map) return null;
      return ReferralSummary.fromJson(Map<String, dynamic>.from(body));
    } on DioException {
      return null;
    }
  }

  /// `GET /api/v1/referrals/reports/leaderboard` — needs `operations.affiliates_read` (narrower
  /// than plain `operations.read`: this exposes real referrer phone numbers), so a shop with
  /// `referrals.manage` alone but not that capability gets a real 403 back — surfaced as `null`
  /// here, never silently swapped for an empty list pretending nothing exists.
  Future<List<ReferralLeaderboardRow>?> leaderboard({int since = 0, int? until, int limit = 20}) async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/referrals/reports/leaderboard',
          queryParameters: {'since': since, if (until != null) 'until': until, 'limit': limit});
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['leaderboard'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .map((m) => ReferralLeaderboardRow.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false);
    } on DioException {
      return null;
    }
  }

  /// `GET /api/v1/referrals/reports/affiliates` — same `operations.affiliates_read` gate as
  /// [leaderboard] (real payout balances, not aggregate-only figures).
  Future<List<ReferralAffiliateRow>?> affiliates() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/referrals/reports/affiliates');
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['affiliates'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .map((m) => ReferralAffiliateRow.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false);
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
