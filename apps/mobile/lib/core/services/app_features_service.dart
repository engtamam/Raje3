import 'package:dio/dio.dart';
import 'package:raje3_mobile/core/network/api_client.dart';
import 'package:raje3_mobile/models/app_store_model.dart';

/// Fetches one app's real feature list from its own owning service — `AppRow.featuresPath`,
/// resolved straight to the real gateway path (campaigns/loyalty/insights/bookings/whatsapp each
/// expose `GET .../features`; every app operations itself owns carries its features INLINE on
/// `Owned.apps[].features` instead and never calls this). Mirrors the console's own
/// `AppFeatureList`/`AppDetailsModal` fetch seam — same `{features: AppFeature[]}` envelope,
/// same "degrade quietly" posture: a failed read shows fewer lines than it should, never an
/// error banner on a screen meant to be selling something.
class AppFeaturesService {
  final ApiClient apiClient;

  AppFeaturesService({required this.apiClient});

  Future<List<AppFeature>?> fetch(String path) async {
    try {
      final response = await apiClient.dio.get<dynamic>(path);
      final body = response.data;
      if (body is! Map) return null;
      final rows = (body['features'] as List?) ?? const [];
      return rows
          .whereType<Map>()
          .map((m) => AppFeature.fromJson(Map<String, dynamic>.from(m)))
          .toList(growable: false);
    } on DioException {
      return null;
    }
  }

  /// `GET /api/v1/subscription/apps/static-features` — the ONE tenant-free read of every
  /// operations-owned app's real feature list (services/operations/app/api/v1/subscription.py's
  /// own docstring). Fetched ONCE, regardless of ownership, so a shop still deciding whether to
  /// BUY one of these (تسجيل زيارة/جهات الاتصال/التقييم/ولاء الشركاء/خدمات متنقلة/تبادل منافع/
  /// الإحالة والمسوّقين) sees its real features too — `Owned.apps[].features` only ever answers
  /// for an app already owned, the exact gap found live on both the console and this screen.
  Future<Map<String, List<AppFeature>>?> fetchStatic() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/subscription/apps/static-features');
      final body = response.data;
      if (body is! Map) return null;
      return body.map((key, value) => MapEntry(
          key as String,
          ((value as List?) ?? const [])
              .whereType<Map>()
              .map((m) => AppFeature.fromJson(Map<String, dynamic>.from(m)))
              .toList(growable: false)));
    } on DioException {
      return null;
    }
  }
}
