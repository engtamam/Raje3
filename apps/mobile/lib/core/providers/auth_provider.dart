import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:raje3_mobile/core/network/api_client.dart';
import 'package:raje3_mobile/core/services/auth_service.dart';
import 'package:raje3_mobile/core/storage/local_storage.dart';
import 'package:raje3_mobile/core/storage/secure_storage.dart';
import 'package:raje3_mobile/models/user_model.dart';

/// Authentication states for the app lifecycle.
enum AuthState {
  /// Initial state before any check has been performed.
  initial,

  /// An authentication operation is in progress.
  loading,

  /// The user is authenticated with a valid session.
  authenticated,

  /// The user is not authenticated (no token or token expired).
  unauthenticated,

  /// An error occurred during authentication.
  error,
}

/// Provider that manages global authentication state.
///
/// Wraps [AuthService] and exposes reactive state for the widget tree.
/// Used by the router to decide between auth and main screens,
/// and by widgets to display user info or trigger login/logout.
///
/// PHONE-ONLY, END TO END — see auth_service.dart's own docstring. There is
/// no email field anywhere in this provider because there is none on the
/// real backend doors it calls (`services/operations/app/api/v1/signup.py`).
class AuthProvider extends ChangeNotifier {
  final ApiClient apiClient;
  final SecureStorage secureStorage;
  final LocalStorage localStorage;

  late final AuthService _authService;

  AuthState _state = AuthState.initial;
  UserModel? _user;
  String? _error;
  /// Stable code alongside [_error] for the ONE refusal that is a step and
  /// not a wall — `unverified`/`otp_required`/`unverified_hold`, all of
  /// which mean "go prove this phone number", not "this attempt failed for
  /// good". See services/operations/app/core/signup.py's own `SignupRefused`
  /// docstring for why the code exists at all: a screen cannot route on
  /// Arabic sentence text that somebody will improve one day.
  String? _errorReason;
  /// The phone number an OTP screen should verify, when [_errorReason]
  /// points at one. Carried here rather than re-typed by the caller so the
  /// login/signup screen and the OTP screen agree on which number is live.
  String? _pendingPhone;
  /// Guard flag to prevent notifyListeners after widget disposal.
  bool _disposed = false;

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }

  /// Safe notify — skips if provider was already disposed.
  @override
  void notifyListeners() {
    if (!_disposed) super.notifyListeners();
  }

  AuthProvider({
    required this.apiClient,
    required this.secureStorage,
    required this.localStorage,
  }) {
    _authService = AuthService(
      apiClient: apiClient,
      secureStorage: secureStorage,
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // GETTERS
  // ─────────────────────────────────────────────────────────────────────────

  /// Current authentication state.
  AuthState get state => _state;

  /// The authenticated user, or null if not logged in.
  UserModel? get user => _user;

  /// Whether the user is fully authenticated.
  bool get isAuthenticated => _state == AuthState.authenticated && _user != null;

  /// Whether an auth operation is in progress.
  bool get isLoading => _state == AuthState.loading;

  /// The last error message, or null.
  String? get error => _error;

  /// The stable reason code beside [error] — `unverified`, `otp_required` or
  /// `unverified_hold` mean "take him to the code screen", never "print this
  /// and stop". Empty/null for every other refusal.
  String? get errorReason => _errorReason;

  /// The phone number the pending OTP step (if any) applies to.
  String? get pendingPhone => _pendingPhone;

  // ─────────────────────────────────────────────────────────────────────────
  // AUTO LOGIN
  // ─────────────────────────────────────────────────────────────────────────

  /// Attempt to restore a previous session from stored tokens.
  ///
  /// Called once on app startup. Checks for a valid, non-expired access
  /// token and restores the tenant scope. There is no refresh-token exchange
  /// wired here — `/api/v1/signup/signin` mints a bare access token with no
  /// documented expiry contract on this door yet, so a token is trusted
  /// until the server itself answers 401 (AuthInterceptor's own force-logout
  /// handles that moment).
  Future<bool> tryAutoLogin() async {
    _setState(AuthState.loading);

    try {
      final hasToken = await secureStorage.hasAccessToken();
      if (!hasToken) {
        _setState(AuthState.unauthenticated);
        return false;
      }

      final tenantId = await secureStorage.getTenantId();
      if (tenantId == null || tenantId.isEmpty) {
        // A token with no remembered tenant cannot scope a single request —
        // treat it the same as no session at all rather than send requests
        // with no X-Tenant-Id and let every one of them fail confusingly.
        await secureStorage.clearAll();
        _setState(AuthState.unauthenticated);
        return false;
      }
      apiClient.setActiveTenantId(tenantId);

      final userDataStr = await secureStorage.getUserData();
      if (userDataStr != null && userDataStr.isNotEmpty) {
        try {
          final userJson = jsonDecode(userDataStr) as Map<String, dynamic>;
          _user = UserModel.fromJson(userJson);
        } catch (_) {
          _user = UserModel(id: tenantId, phone: '');
        }
      } else {
        _user = UserModel(id: tenantId, phone: '');
      }

      apiClient.resetAuthState();
      _setState(AuthState.authenticated);
      unawaited(_refreshOwnerName());
      return true;
    } catch (e) {
      _error = e.toString();
      _setState(AuthState.unauthenticated);
      return false;
    }
  }

  /// Fetches the account holder's own name and folds it into [_user] once it resolves — NOT
  /// awaited by any caller, so a slow or failed read never blocks reaching the home screen; the
  /// greeting simply keeps showing the phone number until this lands (or forever, if he never
  /// set one). May pick up a change made from the console's own «حسابي» since this device last
  /// signed in — this is a real fetch, never the cached copy [tryAutoLogin] restored.
  Future<void> _refreshOwnerName() async {
    final name = await _authService.fetchOwnerName();
    if (name == null || _user == null) return;
    _user = _user!.copyWith(ownerName: name);
    await secureStorage.setUserData(jsonEncode(_user!.toJson()));
    notifyListeners();
  }

  /// «حسابي»'s own edit — writes the account holder's name, and only updates local state once the
  /// server confirms it actually took (never optimistic: an offline save that silently reverted
  /// on the next launch would be a worse surprise than the extra round trip). Returns whether it
  /// actually saved, so the screen can tell a real failure from a quiet no-op.
  Future<bool> updateOwnerName(String name) async {
    final trimmed = name.trim();
    final saved = await _authService.setOwnerName(trimmed);
    if (saved == null || _user == null) return false;
    _user = _user!.copyWith(ownerName: saved);
    await secureStorage.setUserData(jsonEncode(_user!.toJson()));
    notifyListeners();
    return true;
  }

  /// «منشأتي»'s own controls — thin passthroughs, not stored on [_user]: unlike the owner's own
  /// name, these are a live per-request read the shop identity screen owns and refreshes itself,
  /// never part of the cached session shape every screen reads.
  Future<bool?> fetchTracksVehicle() => _authService.fetchTracksVehicle();
  Future<bool?> setTracksVehicle(bool tracksVehicle) =>
      _authService.setTracksVehicle(tracksVehicle);
  Future<TenantIdentity?> fetchTenant() => _authService.fetchTenant();
  Future<bool> setShopName(String name) => _authService.setShopName(name);
  Future<bool> setBranding({
    required Map<String, dynamic> current,
    String? logoUrl,
    String? accent,
  }) =>
      _authService.setBranding(current: current, logoUrl: logoUrl, accent: accent);

  /// «الفروع» — thin passthroughs, same live-per-request shape as the shop identity controls
  /// above.
  Future<BranchesResult?> fetchBranches() => _authService.fetchBranches();
  Future<BranchWriteResult> addBranch({required String name, String city = '', double? lat, double? lng}) =>
      _authService.addBranch(name: name, city: city, lat: lat, lng: lng);
  Future<BranchWriteResult> patchBranch(String branchId,
          {String? name, bool? active, String? city, double? lat, double? lng}) =>
      _authService.patchBranch(branchId, name: name, active: active, city: city, lat: lat, lng: lng);
  Future<List<BranchTeamMember>?> fetchOperators() => _authService.fetchOperators();
  Future<BranchConnectStatus?> fetchBranchConnectStatus(String branchId) =>
      _authService.fetchBranchConnectStatus(branchId);
  Future<bool> fetchIsPerBranchMode() => _authService.fetchIsPerBranchMode();
  Future<HireResult> hireMember({
    required String name,
    required String phone,
    required String password,
    required StaffRole role,
    required String branchId,
  }) =>
      _authService.hireMember(
          name: name, phone: phone, password: password, role: role, branchId: branchId);
  Future<ChangePasswordResult> changePassword({required String oldPassword, required String newPassword}) =>
      _authService.changePassword(oldPassword: oldPassword, newPassword: newPassword);
  Future<BillingOverview> fetchBillingOverview() => _authService.fetchBillingOverview();
  Future<bool> cancelSubscription(String subscriptionId) =>
      _authService.cancelSubscription(subscriptionId);
  Future<bool> undoCancelSubscription(String subscriptionId) =>
      _authService.undoCancelSubscription(subscriptionId);
  Future<String?> invoicePayLink(String invoiceId) => _authService.invoicePayLink(invoiceId);
  Future<List<String>> renewSubscriptionsNow() => _authService.renewSubscriptionsNow();

  // ─────────────────────────────────────────────────────────────────────────
  // LOGIN
  // ─────────────────────────────────────────────────────────────────────────

  /// Sign in with phone + password (+ an OTP [code], only when a previous
  /// attempt was refused with reason `unverified` — see [errorReason]).
  ///
  /// Returns `true` on success, `false` on failure. On failure, the message
  /// is in [error] and, when the refusal is a step rather than a wall, the
  /// stable code is in [errorReason] with [pendingPhone] set so the screen
  /// can route to OTP entry.
  Future<bool> login(String phone, String password, {String code = ''}) async {
    _setState(AuthState.loading);
    _errorReason = null;

    final result = await _authService.signIn(phone, password, code: code);

    if (result.ok) {
      await _persistSession(result, phone: phone);
      _error = null;
      apiClient.resetAuthState();
      _setState(AuthState.authenticated);
      unawaited(_refreshOwnerName());
      return true;
    }

    _error = result.message.isNotEmpty ? result.message : 'فشل تسجيل الدخول';
    _errorReason = result.reason;
    if (result.reason == 'unverified') {
      _pendingPhone = phone;
    }
    _setState(AuthState.error);
    return false;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // OPEN A NEW SHOP (account creation)
  // ─────────────────────────────────────────────────────────────────────────

  /// Open a brand-new shop: phone + password + shop name. On success, signs
  /// straight in through the same door [login] uses (no second mint path —
  /// see AuthService.openShop's own note), so a successful call here leaves
  /// the caller fully authenticated, not merely "account created".
  Future<bool> openShop({
    required String phone,
    required String password,
    required String shopName,
    String ownerName = '',
    String affiliateRef = '',
    String code = '',
  }) async {
    _setState(AuthState.loading);
    _errorReason = null;

    final opened = await _authService.openShop(
      phone: phone,
      password: password,
      shopName: shopName,
      ownerName: ownerName,
      affiliateRef: affiliateRef,
      code: code,
    );

    if (!opened.ok) {
      _error = opened.message.isNotEmpty ? opened.message : 'فشل إنشاء الحساب';
      _errorReason = opened.reason;
      if (opened.reason == 'otp_required' || opened.reason == 'unverified_hold') {
        _pendingPhone = phone;
      }
      _setState(AuthState.error);
      return false;
    }

    // THE SHOP EXISTS NOW — sign in through the ordinary door, exactly as
    // apps/console/src/auth.ts's own `openShop()` does. A refusal here
    // (almost always `unverified`, when the deployment requires OTP) must
    // not read as "signup failed": the account and its trial already exist.
    final signed = await _authService.signIn(phone, password);
    if (!signed.ok) {
      _error = signed.message.isNotEmpty ? signed.message : 'أُنشئ الحساب، أكّد رقمك للدخول.';
      _errorReason = signed.reason;
      if (signed.reason == 'unverified') {
        _pendingPhone = phone;
      }
      _setState(AuthState.error);
      return false;
    }

    await _persistSession(signed, phone: phone, shopName: shopName);
    _error = null;
    apiClient.resetAuthState();
    _setState(AuthState.authenticated);
    unawaited(_refreshOwnerName());
    return true;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // PROVING THE PHONE NUMBER (OTP)
  // ─────────────────────────────────────────────────────────────────────────

  /// Ask the server to send a verification code to [phone]. Only meaningful
  /// once the deployment has WhatsApp/SMS delivery wired
  /// (`SIGNUP_OTP_DELIVERABLE`) — otherwise the server refuses honestly
  /// with reason `undeliverable` rather than pretending to have sent one.
  Future<bool> requestCode(String phone) async {
    final result = await _authService.requestCode(phone);
    if (!result.ok) {
      _error = result.message;
      _errorReason = result.reason;
      notifyListeners();
      return false;
    }
    _error = null;
    notifyListeners();
    return true;
  }

  /// Spend a code sent by [requestCode]. Does NOT itself sign the caller in
  /// — the caller re-runs [login] or [openShop] afterwards with the same
  /// phone/password, and the server no longer refuses with `unverified`.
  Future<bool> verifyCode(String phone, String code) async {
    final result = await _authService.verifyCode(phone, code);
    if (!result.ok) {
      _error = result.message;
      _errorReason = result.reason;
      notifyListeners();
      return false;
    }
    _error = null;
    _errorReason = null;
    notifyListeners();
    return true;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // LOGOUT
  // ─────────────────────────────────────────────────────────────────────────

  /// Force logout without calling the backend (used when session is already expired).
  Future<void> forceLogout() async {
    _user = null;
    _error = null;
    _errorReason = null;
    await secureStorage.clearAll();
    await localStorage.clearUserData();
    apiClient.setActiveTenantId(null);
    _setState(AuthState.unauthenticated);
  }

  /// Logout the current user. There is no server-side logout route on this
  /// door today (`signup.py` declares only sign-in/sign-up) — logout is a
  /// purely local clear.
  Future<void> logout() async {
    _user = null;
    _error = null;
    _errorReason = null;
    await _authService.logout();
    await localStorage.clearUserData();
    apiClient.setActiveTenantId(null);
    _setState(AuthState.unauthenticated);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // ERROR MANAGEMENT
  // ─────────────────────────────────────────────────────────────────────────

  /// Clear the current error message.
  void clearError() {
    if (_error != null || _errorReason != null) {
      _error = null;
      _errorReason = null;
      notifyListeners();
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // INTERNAL
  // ─────────────────────────────────────────────────────────────────────────

  /// Store the tokens and tenant a successful sign-in/signup minted, and
  /// build the local [UserModel] — see user_model.dart's own note on why
  /// this is built here rather than parsed off the response.
  Future<void> _persistSession(AuthResult result, {required String phone, String? shopName}) async {
    await secureStorage.setAccessToken(result.accessToken);
    if (result.refreshToken.isNotEmpty) {
      await secureStorage.setRefreshToken(result.refreshToken);
    }
    await secureStorage.setTenantId(result.tenant);
    apiClient.setActiveTenantId(result.tenant);

    _user = UserModel(id: result.tenant, phone: phone, fullName: shopName);
    await secureStorage.setUserData(jsonEncode(_user!.toJson()));
    _pendingPhone = null;
  }

  /// Update the auth state and notify listeners.
  void _setState(AuthState newState) {
    if (_state != newState) {
      _state = newState;
      notifyListeners();
    } else {
      notifyListeners();
    }
  }
}
