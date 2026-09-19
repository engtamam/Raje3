import 'package:flutter/foundation.dart';
import 'package:raje3_mobile/core/network/api_client.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/services/tenant_service.dart';
import 'package:raje3_mobile/core/storage/cache_manager.dart';
import 'package:raje3_mobile/core/storage/local_storage.dart';
import 'package:raje3_mobile/models/tenant_model.dart';

/// Provider that manages the user's active tenant (shop/branch).
///
/// ADAPTED from the reference project's `ContextProvider` (which modeled
/// "individual vs. business" — that split was specific to their product).
/// This is generalized to a plain list of tenants the signed-in account
/// can act as, with one active at a time; the disposed-guard, generation
/// counter (discard stale async loads), and "sync to ApiClient before any
/// await" ordering are all kept verbatim — they were the genuinely
/// valuable correctness fixes in the original.
///
/// Typically set up as a [ProxyProvider] that depends on [AuthProvider]:
///
/// ```dart
/// ChangeNotifierProxyProvider<AuthProvider, TenantProvider>(
///   create: (context) => TenantProvider(
///     apiClient: apiClient,
///     localStorage: localStorage,
///   ),
///   update: (context, auth, previous) => previous!..updateAuth(auth),
/// )
/// ```
class TenantProvider extends ChangeNotifier {
  final ApiClient apiClient;
  final LocalStorage localStorage;
  final CacheManager? cacheManager;

  late final TenantService _tenantService;

  List<TenantModel> _tenants = [];
  TenantModel? _activeTenant;
  bool _isLoading = false;
  String? _error;
  /// Generation counter to discard stale async results after rapid reloads.
  int _loadGeneration = 0;
  bool _disposed = false;

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }

  @override
  void notifyListeners() {
    if (!_disposed) super.notifyListeners();
  }

  TenantProvider({
    required this.apiClient,
    required this.localStorage,
    this.cacheManager,
  }) {
    _tenantService = TenantService(apiClient: apiClient);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // GETTERS
  // ─────────────────────────────────────────────────────────────────────────

  /// All available tenants for the user.
  List<TenantModel> get tenants => List.unmodifiable(_tenants);

  /// The currently active tenant.
  TenantModel? get activeTenant => _activeTenant;

  /// Whether tenants are being loaded.
  bool get isLoading => _isLoading;

  /// The last error message, or null.
  String? get error => _error;

  /// Whether the user has multiple tenants to choose from.
  bool get hasMultipleTenants => _tenants.length > 1;

  // ─────────────────────────────────────────────────────────────────────────
  // AUTH SYNC
  // ─────────────────────────────────────────────────────────────────────────

  /// Called by ProxyProvider when AuthProvider changes.
  ///
  /// Loads tenants when the user becomes authenticated,
  /// clears them when the user logs out.
  void updateAuth(AuthProvider auth) {
    if (auth.isAuthenticated && _tenants.isEmpty) {
      loadTenants();
    } else if (!auth.isAuthenticated) {
      _loadGeneration++; // Invalidate any pending loads
      _tenants = [];
      _activeTenant = null;
      _error = null;
      apiClient.setActiveTenantId(null);
      notifyListeners();
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // LOAD TENANTS
  // ─────────────────────────────────────────────────────────────────────────

  /// Load all available tenants from the server.
  ///
  /// Automatically selects the active tenant based on:
  /// 1. Previously stored tenant ID in local storage.
  /// 2. The first tenant marked as active by the server.
  /// 3. The first tenant in the list (fallback).
  Future<void> loadTenants() async {
    final generation = ++_loadGeneration;
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final response = await _tenantService.getTenants();

      // Discard stale results if a newer load was triggered
      if (generation != _loadGeneration) return;

      if (response.success && response.data != null && response.data!.isNotEmpty) {
        _tenants = response.data!;

        // Try to restore previously active tenant
        final savedTenantId = localStorage.getActiveContextId();
        if (savedTenantId != null) {
          final savedTenant = _tenants.where((t) => t.id == savedTenantId).firstOrNull;
          if (savedTenant != null) {
            _activeTenant = savedTenant;
          }
        }

        // Fallback: use the server-designated active tenant
        _activeTenant ??= _tenants.where((t) => t.isActive).firstOrNull;

        // Last resort: use the first tenant
        _activeTenant ??= _tenants.first;

        // Persist the active tenant ID
        await localStorage.setActiveContextId(_activeTenant!.id);

        // Sync to API client so all requests scope correctly
        apiClient.setActiveTenantId(_activeTenant!.id);
      } else {
        _error = response.messageAr ?? response.messageEn;
      }
    } catch (e) {
      _error = e.toString();
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // SWITCH TENANT
  // ─────────────────────────────────────────────────────────────────────────

  /// Switch the active tenant to the given [tenantId].
  ///
  /// Notifies the backend and updates local state. Triggers a full
  /// data refresh in the app since all data is tenant-scoped.
  Future<void> switchTenant(String tenantId) async {
    if (_activeTenant?.id == tenantId) return;

    final target = _tenants.where((t) => t.id == tenantId).firstOrNull;
    if (target == null) return;

    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      // Clear all cached data — everything is tenant-scoped and must be
      // re-fetched after switching.
      cacheManager?.clear();

      // Always use the local tenant object (complete data with id) —
      // the server call just persists the switch.
      _activeTenant = target;

      // Sync to API client BEFORE any async yield point. notifyListeners()
      // above schedules a rebuild; after the first await Flutter can
      // process that rebuild and create the home screen, which may
      // immediately fetch tenant-scoped data. If the active tenant hasn't
      // been synced yet, that fetch would return stale data.
      apiClient.setActiveTenantId(target.id);

      await localStorage.setActiveContextId(tenantId);

      // Notify backend of the switch (best-effort)
      await _tenantService.switchTenant(tenantId);
    } catch (e) {
      // Backend notification failed but local switch still works
      _error = null;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }
}
