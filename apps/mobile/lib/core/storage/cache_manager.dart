import 'package:raje3_mobile/core/config/app_config.dart';

/// Simple in-memory cache with TTL (time-to-live) expiration.
///
/// Used for short-lived data caching to reduce API calls for
/// frequently accessed data (e.g., lists, lookups, configuration).
///
/// Usage:
/// ```dart
/// final cache = CacheManager();
///
/// // Store data with default 5-minute TTL
/// cache.put('user_profile', userMap);
///
/// // Store with custom TTL
/// cache.put('config', configMap, duration: Duration(hours: 1));
///
/// // Retrieve (returns null if expired or not found)
/// final profile = cache.get<Map<String, dynamic>>('user_profile');
///
/// // Check existence
/// if (cache.has('user_profile')) { ... }
/// ```
class CacheManager {
  /// Default cache duration: 5 minutes.
  static const Duration defaultTtl = Duration(minutes: AppConfig.cacheDefaultTtlMin);

  /// Internal storage: key -> CacheEntry.
  final Map<String, _CacheEntry> _cache = {};

  /// Maximum number of entries allowed in the cache.
  /// When exceeded, the oldest entries are evicted.
  final int maxEntries;

  CacheManager({this.maxEntries = AppConfig.cacheMaxEntries});

  // ─────────────────────────────────────────────────────────────────────────
  // PUT
  // ─────────────────────────────────────────────────────────────────────────

  /// Store a value in the cache.
  ///
  /// [key] — Unique cache key.
  /// [data] — The data to cache.
  /// [duration] — How long to keep it. Defaults to [defaultTtl] (5 minutes).
  void put(String key, dynamic data, {Duration? duration}) {
    // Evict oldest entries if at capacity
    if (!_cache.containsKey(key) && _cache.length >= maxEntries) {
      _evictOldest();
    }

    _cache[key] = _CacheEntry(
      data: data,
      expiresAt: DateTime.now().add(duration ?? defaultTtl),
      createdAt: DateTime.now(),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // GET
  // ─────────────────────────────────────────────────────────────────────────

  /// Retrieve a cached value.
  ///
  /// Returns null if the key doesn't exist or the entry has expired.
  /// Expired entries are automatically removed on access.
  T? get<T>(String key) {
    final entry = _cache[key];

    if (entry == null) return null;

    if (entry.isExpired) {
      _cache.remove(key);
      return null;
    }

    return entry.data as T?;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // HAS
  // ─────────────────────────────────────────────────────────────────────────

  /// Check if a valid (non-expired) entry exists for the key.
  bool has(String key) {
    final entry = _cache[key];

    if (entry == null) return false;

    if (entry.isExpired) {
      _cache.remove(key);
      return false;
    }

    return true;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // REMOVE / CLEAR
  // ─────────────────────────────────────────────────────────────────────────

  /// Remove a specific cache entry.
  void remove(String key) {
    _cache.remove(key);
  }

  /// Remove all entries matching a key prefix.
  ///
  /// Useful for invalidating all cache entries for a module:
  /// ```dart
  /// cache.removeByPrefix('scans_'); // Removes all scan-related cache
  /// ```
  void removeByPrefix(String prefix) {
    _cache.removeWhere((key, _) => key.startsWith(prefix));
  }

  /// Clear all cached entries.
  void clear() {
    _cache.clear();
  }

  // ─────────────────────────────────────────────────────────────────────────
  // INFO
  // ─────────────────────────────────────────────────────────────────────────

  /// Number of entries currently in the cache (including possibly expired).
  int get length => _cache.length;

  /// Number of valid (non-expired) entries.
  int get validLength {
    _purgeExpired();
    return _cache.length;
  }

  /// Whether the cache is empty.
  bool get isEmpty => _cache.isEmpty;

  /// All current cache keys.
  Iterable<String> get keys => _cache.keys;

  // ─────────────────────────────────────────────────────────────────────────
  // GET OR PUT
  // ─────────────────────────────────────────────────────────────────────────

  /// Get a cached value, or compute and store it if not found/expired.
  ///
  /// This is the recommended pattern for caching API results:
  /// ```dart
  /// final categories = await cache.getOrPut<List<Category>>(
  ///   'categories',
  ///   () async => await apiClient.fetchCategories(),
  ///   duration: Duration(hours: 1),
  /// );
  /// ```
  Future<T> getOrPut<T>(
    String key,
    Future<T> Function() compute, {
    Duration? duration,
  }) async {
    final cached = get<T>(key);
    if (cached != null) return cached;

    final value = await compute();
    put(key, value, duration: duration);
    return value;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // INTERNAL
  // ─────────────────────────────────────────────────────────────────────────

  /// Remove all expired entries.
  void _purgeExpired() {
    _cache.removeWhere((_, entry) => entry.isExpired);
  }

  /// Evict the oldest entry to make room for new ones.
  void _evictOldest() {
    if (_cache.isEmpty) return;

    String? oldestKey;
    DateTime? oldestTime;

    for (final entry in _cache.entries) {
      if (oldestTime == null || entry.value.createdAt.isBefore(oldestTime)) {
        oldestKey = entry.key;
        oldestTime = entry.value.createdAt;
      }
    }

    if (oldestKey != null) {
      _cache.remove(oldestKey);
    }
  }
}

/// Internal cache entry with expiration metadata.
class _CacheEntry {
  final dynamic data;
  final DateTime expiresAt;
  final DateTime createdAt;

  const _CacheEntry({
    required this.data,
    required this.expiresAt,
    required this.createdAt,
  });

  /// Whether this entry has expired.
  bool get isExpired => DateTime.now().isAfter(expiresAt);
}
