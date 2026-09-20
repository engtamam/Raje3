import 'package:flutter/foundation.dart';
import 'package:raje3_mobile/core/nav/nav_sections.g.dart';
import 'package:raje3_mobile/core/network/api_client.dart';
import 'package:raje3_mobile/core/services/catalog_service.dart';
import 'package:raje3_mobile/core/storage/local_storage.dart';
import 'package:raje3_mobile/models/catalog_model.dart';

enum NavLoadState { initial, loading, ready, error }

/// Drives the two dynamic parts of the shell's fixed bottom bar: the session's real action
/// catalogue (what "تطبيقاتي"/the launcher may offer at all) and the operator's own choice for
/// the bar's one customizable slot (default: 'visit').
///
/// THE BAR ITSELF IS NO LONGER PERSONALISED PER SECTION — an earlier pass here mirrored
/// apps/console/src/nav.ts's `visibleSections(catalog)` into several pinned bottom-bar icons,
/// the same shape the console's own sidebar uses. The owner changed that philosophy: a bottom
/// bar showing installed "apps" reads as a list of apps, not a navigation bar — every super-app
/// case study researched for this pass (WeChat, Grab, Careem) keeps its bar to a handful of
/// FIXED anchors (home, account, discovery) and surfaces the actual services from the home
/// screen's own launcher grid instead. See MainShell for the new fixed 5-slot bar and
/// AppsScreen ("تطبيقاتي") for the launcher grid + slot picker.
///
/// The customizable slot's choice is stored LOCALLY (SharedPreferences via [LocalStorage]), not
/// synced through the backend's `pinned_nav_ids` field — that field was shaped for up to 4 ids
/// for the old per-section bar; repurposing it awkwardly for one id isn't worth it here. A
/// later pass can add a dedicated single-id backend field if cross-device sync of this one
/// preference turns out to matter.
///
/// Follows AuthProvider's exact shape: a state enum, a disposed guard, plain getters, and
/// methods that never throw past themselves.
class NavProvider extends ChangeNotifier {
  final ApiClient apiClient;
  final LocalStorage localStorage;
  late final CatalogService _catalogService;

  NavProvider({required this.apiClient, required this.localStorage}) {
    _catalogService = CatalogService(apiClient: apiClient);
    _customSlotId = localStorage.getCustomNavSlot();
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
  late String _customSlotId;

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

  /// The section id currently pinned to the bar's customizable slot.
  String get customSlotId => _customSlotId;

  /// The [NavSectionDef] for the customizable slot — the operator's own choice when it is
  /// still visible today (a capability since revoked drops silently), otherwise the first
  /// visible section, otherwise null when nothing is visible at all (an account with no
  /// capabilities: the shell renders the 4 fixed tabs only — see MainShell).
  NavSectionDef? get customSlotSection {
    final visible = visibleSections;
    if (visible.isEmpty) return null;
    for (final s in visible) {
      if (s.id == _customSlotId) return s;
    }
    return visible.first;
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

  /// Pin a different section to the bar's customizable slot ("تطبيقاتي" own picker). Persists
  /// locally (see [LocalStorage.setCustomNavSlot]'s own doc comment for why this is per-device
  /// rather than synced through the backend).
  Future<void> setCustomSlot(String sectionId) async {
    if (_customSlotId == sectionId) return;
    _customSlotId = sectionId;
    await localStorage.setCustomNavSlot(sectionId);
    notifyListeners();
  }
}
