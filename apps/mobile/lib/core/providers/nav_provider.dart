import 'package:flutter/foundation.dart';
import 'package:raje3_mobile/core/nav/nav_sections.g.dart';
import 'package:raje3_mobile/core/network/api_client.dart';
import 'package:raje3_mobile/core/services/catalog_service.dart';
import 'package:raje3_mobile/models/catalog_model.dart';

enum NavLoadState { initial, loading, ready, error }

/// The session's real action catalogue — what the app router/shell may reach at all
/// ([MainShell]'s own bottom bar, and the landing screen this drives).
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

  /// Where a caller freshly landing on the app goes — the first section THIS session's real
  /// catalogue makes visible, in kNavSections's own priority order (mirrors nav.ts's own
  /// comment: «تسجيل زيارة» lands first because it needs only the one capability most
  /// operators hold, not because it is special-cased anywhere). `null` only while the
  /// catalogue is still loading or unreachable with nothing visible — the router holds the
  /// caller on login rather than guessing.
  String? get landingPath {
    final visible = visibleSections;
    return visible.isEmpty ? null : visible.first.path;
  }

  /// Fetch the catalogue once per session. Safe to call again (e.g. pull-to-refresh); it
  /// always starts from a clean loading state.
  Future<void> load() async {
    _state = NavLoadState.loading;
    notifyListeners();

    final catalog = await _catalogService.fetchCatalog();
    if (catalog != null) {
      _catalog = catalog;
    }
    // AN UNREACHABLE CATALOGUE STILL RENDERS SOMETHING — an empty one shows no sections rather
    // than crashing the shell; the login/redirect layer is what actually gates entry.

    _state = catalog != null ? NavLoadState.ready : NavLoadState.error;
    notifyListeners();
  }
}
