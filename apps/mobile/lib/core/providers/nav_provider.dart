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
class NavProvider extends ChangeNotifier with WidgetsBindingObserver {
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
    // RE-FETCH ON RESUME, NOT ONLY ONCE PER COLD START (found live, 2026-10-06): `load()` below
    // was gated by `state == initial`, which is true exactly once in this provider's whole
    // lifetime — so a capability granted, an app subscribed, or a plan changed WHILE the
    // operator's session stayed open (backgrounded, not killed) never reached the catalogue
    // this provider holds, no matter how long the app sat open. The owner saw a dead "add" button
    // (and no error — the button was simply never in the catalogue) until he force-closed and
    // reopened the app, which is the one thing that rebuilds this provider from scratch. A
    // customer hitting this has no reason to know a full close+reopen is the fix.
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed && _state != NavLoadState.initial) {
      load();
    }
  }

  bool _disposed = false;

  @override
  void dispose() {
    _disposed = true;
    WidgetsBinding.instance.removeObserver(this);
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

  /// nav.ts's own capability-gated SECTIONS list, in its own priority order — NO LONGER the home
  /// grid's source (see [ownedSections] for that, and its own doc comment on why); kept only for
  /// [customSlotSection], the bottom bar's one customizable-slot picker, which still offers a
  /// pinnable CORE nav destination rather than every owned app. Mirrors `visibleSections(catalog)`
  /// EXACTLY: visible = section.service is unreachable OR section.requires is empty OR
  /// hasAll(requires).
  List<NavSectionDef> get visibleSections {
    return kNavSections.where((s) {
      if (s.service != null && _catalog.unreachable.contains(s.service)) return true;
      if (s.requires.isEmpty) return true;
      return _catalog.hasAll(s.requires);
    }).toList(growable: false);
  }

  /// EVERY app the shop actually bought, and NOTHING it didn't — the home grid's own source,
  /// distinct from [visibleSections] (kept below only for the bottom bar's customizable-slot
  /// picker, see [customSlotSection]'s own doc comment on why that one stays capability-only).
  ///
  /// Owner's own explicit call (2026-09-29), after finding the home grid showed a fixed curated
  /// subset (mirroring the console's own sidebar SECTIONS) while "تطبيقاتي" showed every app
  /// actually sold — a shop that bought «المساعد الذكي عبر واتساب» never saw it on the home
  /// screen. First fix ADDED owned-but-uncovered apps on top of the fixed list; the owner then
  /// asked for the fixed list to be DROPPED entirely — home shows exactly what "تطبيقاتي" shows as
  /// owned, nothing more.
  ///
  /// STILL ROLE-GATED, NOT OWNERSHIP-ALONE — "مع مراعاة الصلاحيات والأدوار" was the owner's own
  /// explicit condition: a shop can own an app while today's signed-in STAFF MEMBER still lacks
  /// the specific capability that app's own kNavSections entry names (e.g. a cashier account
  /// without `bookings.list`). [kAppRows] itself carries no such per-action capability (it is a
  /// billing/ownership catalogue only) — a route that already has a [kNavSections] entry reuses
  /// that entry's own `requires` as the real role gate; a route with none (today, only
  /// `whatsapp-assistant`) has never had one defined anywhere in this app, so ownership is the
  /// only check that has ever gated it — same posture its own GoRoute already takes.
  List<NavSectionDef> get ownedSections {
    final requiresByRoute = {for (final s in kNavSections) s.id: s.requires};
    return kAppRows.where((row) {
      if (row.route == null) return false;
      if (_owned.owns(row.key ?? '') != true) return false;
      final requires = requiresByRoute[row.route];
      return requires == null || requires.isEmpty || _catalog.hasAll(requires);
    }).map((row) {
      final existing = kNavSections.where((s) => s.id == row.route).firstOrNull;
      // PREFER THE REAL NavSectionDef WHEN ONE EXISTS — same id/path/icon "تطبيقاتي"'s own row
      // resolves to today, not a second, possibly-drifted copy of the same facts.
      return existing ??
          NavSectionDef(
            id: row.route!,
            path: '/${row.route}',
            label: row.name,
            icon: kAppTileIcons[row.icon] ?? Icons.apps_rounded,
            requires: const [],
          );
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

  /// Fetch the catalogue — on cold start (app_router.dart's `state == initial` guard), every
  /// resume from background (didChangeAppLifecycleState above), and safe to call again for
  /// anything else (e.g. pull-to-refresh); it always starts from a clean loading state.
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
