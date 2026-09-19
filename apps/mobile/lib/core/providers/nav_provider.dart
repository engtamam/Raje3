import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:raje3_mobile/core/nav/nav_sections.g.dart';
import 'package:raje3_mobile/core/network/api_client.dart';
import 'package:raje3_mobile/core/services/catalog_service.dart';
import 'package:raje3_mobile/models/catalog_model.dart';

/// Where the operator's own pinned-nav preference lives, and the cap the backend also
/// enforces (see services/operations/app/api/v1/staff.py's `_MAX_PINNED_NAV`).
const int kMaxPinnedNav = 4;

enum NavLoadState { initial, loading, ready, error }

/// Personalises the bottom navigation from the session's real action catalogue — the mobile
/// mirror of apps/console/src/nav.ts's `visibleSections(catalog)` plus the pin preference the
/// backend now stores per operator.
///
/// Follows AuthProvider's exact shape: a state enum, a disposed guard, plain getters, and
/// methods that never throw past themselves.
class NavProvider extends ChangeNotifier {
  final ApiClient apiClient;
  late final CatalogService _catalogService;

  NavProvider({required this.apiClient}) {
    _catalogService = CatalogService(apiClient: apiClient);
  }

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

  NavLoadState _state = NavLoadState.initial;
  Catalog _catalog = Catalog.empty;
  List<String> _pinnedIds = [];
  /// True once we know this account has no operator row at all (e.g. the owner) — the
  /// pinned-nav read 404s for that case (see staff.py's `get_my_operator_row` docstring) and
  /// that is a real, expected answer, not a fault; we fall back to the default pin order.
  bool _hasOperatorRow = true;

  NavLoadState get state => _state;
  bool get isLoading => _state == NavLoadState.loading;

  /// Every section this session's catalogue makes visible, in nav.ts's own priority order —
  /// mirrors `visibleSections(catalog)` EXACTLY:
  ///   visible = section.service is unreachable OR section.requires is empty OR hasAll(requires)
  List<NavSectionDef> get visibleSections {
    return kNavSections.where((s) {
      if (s.service != null && _catalog.unreachable.contains(s.service)) return true;
      if (s.requires.isEmpty) return true;
      return _catalog.hasAll(s.requires);
    }).toList(growable: false);
  }

  /// The landing route — the first visible section's path (mirrors nav.ts's own comment on
  /// Home.tsx: «تسجيل زيارة» lands first because it is first in SECTIONS and requires nothing
  /// but the one capability most operators hold). Null when nothing is visible at all — the
  /// caller falls back to a bare, chrome-less screen rather than a broken route.
  String? get landingPath {
    final visible = visibleSections;
    return visible.isEmpty ? null : visible.first.path;
  }

  /// Up to [kMaxPinnedNav] sections to show as bottom-bar icons: the operator's own saved pins,
  /// filtered to what is STILL visible today (a capability since revoked drops silently, same
  /// discipline the backend's own docstring describes for `pinned_nav_ids`); falls back to the
  /// first [kMaxPinnedNav] visible sections, in kNavSections order, when there is no saved pin.
  List<NavSectionDef> get pinnedSections {
    final visible = visibleSections;
    final visibleIds = visible.map((s) => s.id).toSet();
    final fromPins = _pinnedIds
        .where(visibleIds.contains)
        .map((id) => visible.firstWhere((s) => s.id == id))
        .take(kMaxPinnedNav)
        .toList();
    if (fromPins.isNotEmpty) return fromPins;
    return visible.take(kMaxPinnedNav).toList(growable: false);
  }

  /// The rest of what is visible but not pinned — the "More" tab's own list.
  List<NavSectionDef> get overflowSections {
    final pinnedIds = pinnedSections.map((s) => s.id).toSet();
    return visibleSections.where((s) => !pinnedIds.contains(s.id)).toList(growable: false);
  }

  /// Fetch the catalogue once per session, then the operator's own saved pin order. Safe to
  /// call again (e.g. pull-to-refresh); it always starts from a clean loading state.
  Future<void> load() async {
    _state = NavLoadState.loading;
    notifyListeners();

    final catalog = await _catalogService.fetchCatalog();
    if (catalog != null) {
      _catalog = catalog;
    }
    // AN UNREACHABLE CATALOGUE STILL RENDERS SOMETHING — an empty one shows no sections rather
    // than crashing the shell; the login/redirect layer is what actually gates entry.

    await _loadPinnedIds();

    _state = catalog != null ? NavLoadState.ready : NavLoadState.error;
    notifyListeners();
  }

  Future<void> _loadPinnedIds() async {
    try {
      final response = await apiClient.dio.get<dynamic>('/api/v1/staff/operators/me');
      final body = response.data;
      if (body is Map<String, dynamic>) {
        _hasOperatorRow = true;
        final raw = body['pinned_nav_ids'] as List<dynamic>? ?? const [];
        _pinnedIds = raw.map((e) => e.toString()).toList();
      }
    } on DioException catch (e) {
      if (e.response?.statusCode == 404) {
        // The owner himself has no operator row — see staff.py's own docstring. Not an error:
        // fall back to the default pin order silently.
        _hasOperatorRow = false;
        _pinnedIds = [];
      }
      // Any other failure (network, 5xx) just leaves the previous/default pins in place —
      // pinning is a convenience, not something worth blocking the shell over.
    }
  }

  /// Save a new pin order (backend caps at [kMaxPinnedNav] too). Updates local state only
  /// after the write succeeds — optimistic-after-success, never before, so a failed write
  /// never shows the operator a bar that does not match what is actually saved.
  Future<bool> setPinnedSections(List<String> sectionIds) async {
    if (!_hasOperatorRow) {
      // Nothing to PATCH for an account with no operator row (the owner) — there is no row
      // to store the preference on. Treat as a silent no-op rather than surfacing a 404.
      return false;
    }
    final capped = sectionIds.take(kMaxPinnedNav).toList();
    try {
      await apiClient.dio.patch<dynamic>(
        '/api/v1/staff/operators/me/pinned-nav',
        data: {'pinned_nav_ids': capped},
      );
      _pinnedIds = capped;
      notifyListeners();
      return true;
    } on DioException {
      return false;
    }
  }
}
