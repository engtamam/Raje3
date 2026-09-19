import 'package:raje3_mobile/core/constants/app_constants.dart';
import 'package:raje3_mobile/core/network/api_client.dart';
import 'package:raje3_mobile/core/storage/cache_manager.dart';
import 'package:raje3_mobile/models/app_config_model.dart';

/// Fetches and caches the mobile app's server-driven runtime config.
///
/// ADAPTED from the reference project's `AppConfigService` — same
/// in-memory + [CacheManager] double-cache idea (sync access after the
/// first fetch, silent failure to hardcoded fallbacks), moved off the
/// unified execute endpoint onto plain REST, and scoped per-tenant instead
/// of per-business (see tenant_provider.dart).
///
/// Usage:
/// ```dart
/// final configService = context.read<AppConfigService>();
/// await configService.getConfig();
/// ```
class AppConfigService {
  final ApiClient apiClient;
  final CacheManager cache;

  static const String _configCacheKey = 'app_config';
  static const Duration _configCacheTtl = Duration(hours: 4);

  /// In-memory reference for sync access (no async needed after first fetch).
  AppConfigModel? _cachedConfig;

  /// The tenant ID used for the current cached config (null = no tenant).
  String? _cachedTenantId;

  AppConfigService({required this.apiClient, required this.cache});

  /// Get cached config synchronously. Returns null if not yet fetched.
  AppConfigModel? get cachedConfig => _cachedConfig;

  /// Fetch app config from backend. Cached for 4 hours.
  ///
  /// On success, also applies region config (currency, VAT) to [AppConstants].
  /// Returns null on failure (callers should use hardcoded fallbacks).
  Future<AppConfigModel?> getConfig({
    bool forceRefresh = false,
    String? tenantId,
  }) async {
    final cacheKey = tenantId != null ? '${_configCacheKey}_$tenantId' : _configCacheKey;

    // If the active tenant changed, force refresh
    if (tenantId != _cachedTenantId) {
      forceRefresh = true;
    }

    // Check in-memory cache first
    if (!forceRefresh && _cachedConfig != null) {
      return _cachedConfig;
    }

    // Check CacheManager
    if (!forceRefresh) {
      final cached = cache.get<AppConfigModel>(cacheKey);
      if (cached != null) {
        _cachedConfig = cached;
        _cachedTenantId = tenantId;
        return cached;
      }
    }

    try {
      final response = await apiClient.get<AppConfigModel>(
        '/config/mobile',
        fromJson: (json) => AppConfigModel.fromJson(json),
      );

      if (response.success && response.data != null) {
        final config = response.data!;
        _cachedConfig = config;
        _cachedTenantId = tenantId;
        cache.put(cacheKey, config, duration: _configCacheTtl);

        // Apply region config to AppConstants
        AppConstants.loadRegionConfig({
          'currency': config.region.currency,
          'currency_symbol': config.region.currencySymbol,
          'tax_rate': config.region.taxRate,
        });

        return config;
      }
    } catch (_) {
      // Silent failure — callers use hardcoded fallbacks
    }

    return _cachedConfig;
  }

  /// Clear cached config (e.g. on logout).
  void clearCache() {
    _cachedConfig = null;
    _cachedTenantId = null;
    cache.remove(_configCacheKey);
  }
}
