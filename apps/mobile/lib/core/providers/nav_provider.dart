import 'package:flutter/material.dart';
import 'package:raje3_mobile/core/nav/nav_sections.g.dart';
import 'package:raje3_mobile/core/network/api_client.dart';
import 'package:raje3_mobile/core/services/auth_service.dart';
import 'package:raje3_mobile/core/services/catalog_service.dart';
import 'package:raje3_mobile/core/storage/local_storage.dart';
import 'package:raje3_mobile/core/storage/secure_storage.dart';
import 'package:raje3_mobile/models/app_store_model.dart';
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
  late final AuthService _authService;

  NavProvider({required this.apiClient, required this.localStorage}) {
    _catalogService = CatalogService(apiClient: apiClient);
    // OWN INSTANCE, NOT INJECTED — same "build the one small service this provider needs"
    // pattern _catalogService already uses. SecureStorage's no-arg constructor is safe here:
    // fetchOwnership() never reads/writes tokens, it just needs an ApiClient with the request
    // interceptor already attached (see AuthProvider's own real instance for that wiring).
    _authService = AuthService(apiClient: apiClient, secureStorage: SecureStorage());
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
  Owned _owned = Owned.empty;
  late String _customSlotId;

  NavLoadState get state => _state;
  bool get isLoading => _state == NavLoadState.loading;

  /// The real, already capability-filtered catalogue — the same source [visibleSections] and
  /// [KbService]'s own visibility check both trust, so a KB entry never claims a capability this
  /// session does not actually hold.
  Catalog get catalog => _catalog;

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

  /// Every app store row ([kAppRows], the SAME catalogue "تطبيقاتي" reads) this shop actually
  /// bought, that HAS a real mobile screen ([AppRow.route] is not null), and that [kNavSections]
  /// does not already cover — found live (2026-09-29), the owner's own report: the home grid
  /// showed a fixed, curated subset (mirroring the console's own sidebar) while "تطبيقاتي" showed
  /// every app actually sold, and a shop that bought «المساعد الذكي عبر واتساب» never saw it on
  /// the home screen at all, only inside the store. Kept as a SEPARATE list from
  /// [visibleSections] rather than merged into `kNavSections` itself — that list is still the
  /// generated, capability-gated mirror of nav.ts and must stay exactly that; this is home's own
  /// addition on top, ownership-gated instead of capability-gated (an app store row has no
  /// `requires` of its own — [Owned.owns] is the one real ownership check "تطبيقاتي" itself
  /// already uses).
  List<NavSectionDef> get extraOwnedSections {
    final coveredRoutes = kNavSections.map((s) => s.id).toSet();
    return kAppRows
        .where((row) =>
            row.route != null &&
            !coveredRoutes.contains(row.route) &&
            _owned.owns(row.key ?? '') == true)
        .map((row) => NavSectionDef(
              id: row.route!,
              path: '/${row.route}',
              label: row.name,
              icon: kAppTileIcons[row.icon] ?? Icons.apps_rounded,
              requires: const [],
            ))
        .toList(growable: false);
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

    // PARALLEL, NOT SEQUENTIAL — same reasoning shop_identity_screen.dart's own "one initial
    // load, not two" fix gives: two independent reads, no reason to make one wait on the other.
    final results = await Future.wait([
      _catalogService.fetchCatalog(),
      _authService.fetchOwnership(),
    ]);
    final catalog = results[0] as Catalog?;
    final owned = results[1] as Owned?;
    if (catalog != null) {
      _catalog = catalog;
    }
    // A FAILED OWNERSHIP READ NEVER HIDES A SECTION [visibleSections] ALREADY SHOWS — it only
    // means extraOwnedSections finds nothing extra this time, same "fail into nothing added, not
    // into a crash or a false negative" rule the catalogue itself follows below.
    if (owned != null) {
      _owned = owned;
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
