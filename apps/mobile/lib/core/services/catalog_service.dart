import 'package:dio/dio.dart';
import 'package:raje3_mobile/core/network/api_client.dart';
import 'package:raje3_mobile/models/catalog_model.dart';

/// Fetches this session's action catalogue — the same `GET /api/v1/app/catalog` the web
/// console reads (see apps/console/src/catalog.ts's own doc comment for why it is one
/// aggregated call: the gateway has already filtered by capability, so this app never needs
/// a role check to decide what to show).
///
/// NOT CALLED THROUGH [ApiClient.get]'S NORMAL ENVELOPE. `/api/v1/app/catalog` is a shared,
/// cross-client-type route — it answers `{services: [...], unreachable: [...]}` directly, not
/// wrapped in this app's own `{success, data, ...}` shape (that shape belongs to routes this
/// app's OWN backend surface was built for; the real fleet's routes predate it and were never
/// changed to match). So this goes straight through [ApiClient.dio] and parses the raw body.
class CatalogService {
  final ApiClient apiClient;

  CatalogService({required this.apiClient});

  static const String path = '/api/v1/app/catalog';

  /// Returns the fetched catalogue, or `null` on any failure (network error, 401 the caller
  /// could not recover from, unexpected shape) — the caller (NavProvider) treats `null` the
  /// same as an empty catalogue: nothing extra shows, nothing crashes.
  Future<Catalog?> fetchCatalog() async {
    try {
      final response = await apiClient.dio.get<dynamic>(path);
      final body = response.data;
      if (body is Map<String, dynamic>) {
        return Catalog.fromJson(body);
      }
      return null;
    } on DioException {
      return null;
    }
  }
}
