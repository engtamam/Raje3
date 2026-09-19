import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:raje3_mobile/core/constants/app_constants.dart';
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
/// Setup with Provider:
/// ```dart
/// ChangeNotifierProvider(
///   create: (context) => AuthProvider(
///     apiClient: apiClient,
///     secureStorage: secureStorage,
///     localStorage: localStorage,
///   ),
/// )
/// ```
class AuthProvider extends ChangeNotifier {
  final ApiClient apiClient;
  final SecureStorage secureStorage;
  final LocalStorage localStorage;

  late final AuthService _authService;

  AuthState _state = AuthState.initial;
  UserModel? _user;
  String? _error;
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

  // NOTE: the reference project also wired a PushNotificationService here
  // (FCM token registration on login/logout). Push notifications aren't
  // part of this infra-only pass — not excluded on principle, just not yet
  // decided/built. Add it back the same way if/when Raje3 gets push.

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

  // ─────────────────────────────────────────────────────────────────────────
  // AUTO LOGIN
  // ─────────────────────────────────────────────────────────────────────────

  /// Attempt to restore a previous session from stored tokens.
  ///
  /// Called once on app startup. Checks for a valid access token,
  /// loads cached user data, and optionally refreshes the token.
  ///
  /// Returns `true` if auto-login succeeds.
  Future<bool> tryAutoLogin() async {
    _setState(AuthState.loading);

    try {
      final isLoggedIn = await _authService.isLoggedIn();

      if (!isLoggedIn) {
        // Session-based auth: no refresh token mechanism.
        // If the session expired, the user must log in again.
        _setState(AuthState.unauthenticated);
        return false;
      }

      // If the user registered but never verified their phone,
      // don't auto-login — force them through verification again.
      final pendingVerify = await secureStorage.read(
        AppConstants.pendingPhoneVerifyKey,
      );
      if (pendingVerify == 'true') {
        await secureStorage.clearAll();
        _setState(AuthState.unauthenticated);
        return false;
      }

      // Load cached user data
      final userDataStr = await secureStorage.getUserData();
      if (userDataStr != null && userDataStr.isNotEmpty) {
        try {
          final userJson = jsonDecode(userDataStr) as Map<String, dynamic>;
          _user = UserModel.fromJson(userJson);
        } catch (_) {
          // Corrupted user data; will be refreshed
        }
      }

      // Reset interceptor state so 401s are handled properly
      apiClient.resetAuthState();
      _setState(AuthState.authenticated);
      // Refresh profile from server in background to get latest data
      refreshProfile();
      return true;
    } catch (e) {
      _error = e.toString();
      _setState(AuthState.unauthenticated);
      return false;
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // LOGIN
  // ─────────────────────────────────────────────────────────────────────────

  /// Login with phone number and password.
  ///
  /// Returns `true` on success, `false` on failure.
  /// On failure, the error message is available via [error].
  Future<bool> login(String phone, String password) async {
    _setState(AuthState.loading);

    try {
      final response = await _authService.login(phone, password);

      if (response.success && response.data != null) {
        _user = response.data;
        _error = null;

        // Reset interceptor state so 401s are handled properly
        apiClient.resetAuthState();
        _setState(AuthState.authenticated);
        return true;
      }

      _error = response.messageAr ?? response.messageEn ?? 'فشل تسجيل الدخول';
      _setState(AuthState.error);
      return false;
    } catch (e) {
      _error = _extractErrorMessage(e);
      _setState(AuthState.error);
      return false;
    }
  }

  /// Request an OTP code for passwordless login.
  ///
  /// Returns `true` if the OTP was sent successfully.
  Future<bool> requestOtp(String phone) async {
    _setState(AuthState.loading);

    try {
      final response = await _authService.requestOtp(phone);

      if (response.success) {
        _error = null;
        // Stay in loading state; the UI navigates to OTP entry
        _setState(AuthState.unauthenticated);
        return true;
      }

      _error = response.messageAr ?? response.messageEn ?? 'فشل إرسال رمز التحقق';
      _setState(AuthState.error);
      return false;
    } catch (e) {
      _error = _extractErrorMessage(e);
      _setState(AuthState.error);
      return false;
    }
  }

  /// Verify an OTP code and complete login.
  ///
  /// Returns `true` on success.
  Future<bool> verifyOtp(String phone, String otp) async {
    _setState(AuthState.loading);

    try {
      final response = await _authService.verifyOtp(phone, otp);

      if (response.success && response.data != null) {
        _user = response.data;
        _error = null;

        // Reset interceptor state so 401s are handled properly
        apiClient.resetAuthState();
        _setState(AuthState.authenticated);
        return true;
      }

      _error = response.messageAr ?? response.messageEn ?? 'رمز التحقق غير صحيح';
      _setState(AuthState.error);
      return false;
    } catch (e) {
      _error = _extractErrorMessage(e);
      _setState(AuthState.error);
      return false;
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // REGISTER
  // ─────────────────────────────────────────────────────────────────────────

  /// Register a new user account.
  ///
  /// Returns `true` on success. The user is automatically logged in.
  Future<bool> register({
    required String phone,
    required String password,
    String? fullName,
    String? email,
    bool termsAccepted = false,
  }) async {
    _setState(AuthState.loading);

    try {
      final response = await _authService.register(
        phone: phone,
        password: password,
        fullName: fullName,
        email: email,
        termsAccepted: termsAccepted,
      );

      if (response.success && response.data != null) {
        _user = response.data;
        _error = null;
        // Don't authenticate yet — phone verification required first.
        // Session is saved by AuthService._handleAuthResponse (needed for
        // the verify_phone API call) but we stay unauthenticated until OTP.
        // Set a flag so tryAutoLogin() won't bypass verification.
        await secureStorage.write(
          AppConstants.pendingPhoneVerifyKey, 'true',
        );
        _setState(AuthState.unauthenticated);
        return true;
      }

      _error = response.messageAr ?? response.messageEn ?? 'فشل التسجيل';
      _setState(AuthState.error);
      return false;
    } catch (e) {
      _error = _extractErrorMessage(e);
      _setState(AuthState.error);
      return false;
    }
  }

  /// Request OTP for phone verification (post-registration).
  Future<bool> requestPhoneVerifyOtp(String phone) async {
    try {
      final response = await _authService.requestPhoneVerifyOtp(phone);
      if (response.success) {
        _error = null;
        return true;
      }
      _error = response.messageAr ?? response.messageEn ?? 'فشل إرسال رمز التحقق';
      notifyListeners();
      return false;
    } catch (e) {
      _error = _extractErrorMessage(e);
      notifyListeners();
      return false;
    }
  }

  /// Verify phone OTP and complete registration flow.
  Future<bool> verifyPhone(String phone, String otp) async {
    try {
      final response = await _authService.verifyPhone(phone, otp);
      if (response.success) {
        _error = null;
        // Clear the pending-verification flag
        await secureStorage.delete(AppConstants.pendingPhoneVerifyKey);
        // Now complete authentication
        apiClient.resetAuthState();
        _setState(AuthState.authenticated);
        return true;
      }
      _error = response.messageAr ?? response.messageEn ?? 'رمز التحقق غير صحيح';
      notifyListeners();
      return false;
    } catch (e) {
      _error = _extractErrorMessage(e);
      notifyListeners();
      return false;
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // LOGOUT
  // ─────────────────────────────────────────────────────────────────────────

  /// Force logout without calling the backend (used when session is already expired).
  ///
  /// Only clears local state and redirects to login. Does NOT call auth.logout API
  /// to avoid cascading requests when the session is already invalid.
  Future<void> forceLogout() async {
    _user = null;
    _error = null;
    await secureStorage.clearAll();
    await localStorage.clearUserData();
    _setState(AuthState.unauthenticated);
  }

  /// Logout the current user.
  ///
  /// Clears all tokens, user data, and resets state to unauthenticated.
  Future<void> logout() async {
    try {
      await _authService.logout();
    } catch (_) {
      // Continue with local cleanup
    } finally {
      _user = null;
      _error = null;
      await localStorage.clearUserData();
      _setState(AuthState.unauthenticated);
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // PROFILE REFRESH
  // ─────────────────────────────────────────────────────────────────────────

  /// Refresh the user profile from the server.
  ///
  /// Updates the locally stored user data. Does not change auth state.
  Future<void> refreshProfile() async {
    try {
      final response = await apiClient.get<UserModel>(
        '/users/me',
        fromJson: (json) => UserModel.fromJson(json),
      );

      if (response.success && response.data != null) {
        _user = response.data;
        await secureStorage.setUserData(
          jsonEncode(response.data!.toJson()),
        );
        notifyListeners();
      }
    } catch (_) {
      // Silent failure; profile will refresh on next attempt
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // ERROR MANAGEMENT
  // ─────────────────────────────────────────────────────────────────────────

  /// Clear the current error message.
  ///
  /// Call this when the user dismisses an error dialog or navigates away.
  void clearError() {
    if (_error != null) {
      _error = null;
      notifyListeners();
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // INTERNAL
  // ─────────────────────────────────────────────────────────────────────────

  /// Update the auth state and notify listeners.
  void _setState(AuthState newState) {
    if (_state != newState) {
      _state = newState;
      notifyListeners();
    }
  }

  /// Extract a user-friendly error message from an exception.
  String _extractErrorMessage(Object e) {
    // Try to extract localized message from typed exceptions
    try {
      final dynamic ex = e;
      return (ex.messageAr as String?) ?? (ex.messageEn as String?) ?? e.toString();
    } catch (_) {
      return e.toString();
    }
  }
}
