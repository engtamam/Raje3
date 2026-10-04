import 'package:flutter/foundation.dart';

import 'package:raje3_mobile/core/constants/app_constants.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/services/auth_service.dart' show Branch;
import 'package:raje3_mobile/core/storage/local_storage.dart';

/// The operator's own chosen branch — a real, app-wide equivalent of the console's own top-bar
/// switcher (apps/console's own shell, which the WHOLE session scopes to: every read the operator
/// makes narrows to that branch). The mobile app assumed exactly one branch everywhere until now
/// (see visit_screen.dart's own `_loadTodayBookings`, which silently skipped its own feature for
/// any shop with more than one) — this is the real fix, not another per-screen workaround.
///
/// A SINGLE-BRANCH SHOP NEVER SEES THE SWITCH AT ALL (§`hasChoice`) — the same "resolves silently"
/// rule this app already holds to everywhere branch scope comes up. A multi-branch shop's choice
/// persists per device (shared_preferences, [AppConstants.selectedBranchIdKey]) — there is no
/// backend field for "which branch is this phone looking at right now", same reasoning
/// [AppConstants.customNavSlotKey] already documents for the bottom bar's own device-local slot.
class BranchProvider extends ChangeNotifier {
  BranchProvider({required this.localStorage});

  final LocalStorage localStorage;
  AuthProvider? _auth;

  List<Branch>? _branches; // null = not loaded yet
  bool _failed = false;
  String? _selectedId;

  List<Branch> get branches => (_branches ?? const []).where((b) => b.active).toList();
  bool get loaded => _branches != null;
  bool get failed => _failed;
  bool get hasChoice => branches.length > 1;

  String? get selectedId => _selectedId;

  Branch? get selected {
    final id = _selectedId;
    if (id == null) return null;
    for (final b in branches) {
      if (b.id == id) return b;
    }
    return null;
  }

  /// Called from `main.dart`'s own `ChangeNotifierProxyProvider<AuthProvider, BranchProvider>` —
  /// same wiring [TenantProvider]/[AiEntitlementProvider] already use to react to a login/logout.
  void updateAuth(AuthProvider auth) {
    final wasSignedIn = _auth?.state == AuthState.authenticated;
    _auth = auth;
    if (auth.state == AuthState.authenticated && !wasSignedIn) {
      load();
    } else if (auth.state != AuthState.authenticated) {
      _branches = null;
      _selectedId = null;
      _failed = false;
    }
  }

  Future<void> load() async {
    final auth = _auth;
    if (auth == null) return;
    final result = await auth.fetchBranches();
    if (result == null) {
      _failed = true;
      notifyListeners();
      return;
    }
    _failed = false;
    _branches = result.branches;
    final active = result.branches.where((b) => b.active).toList();
    final stored = localStorage.getString(AppConstants.selectedBranchIdKey);
    final storedStillValid = stored != null && active.any((b) => b.id == stored);
    _selectedId = storedStillValid
        ? stored
        : (active.isNotEmpty ? active.first.id : null);
    notifyListeners();
  }

  Future<void> select(String branchId) async {
    if (_selectedId == branchId) return;
    _selectedId = branchId;
    notifyListeners();
    await localStorage.setString(AppConstants.selectedBranchIdKey, branchId);
  }
}
