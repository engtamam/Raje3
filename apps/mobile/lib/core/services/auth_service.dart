import 'dart:convert';

import 'package:raje3_mobile/core/network/api_client.dart';
import 'package:raje3_mobile/core/network/api_response.dart';
import 'package:raje3_mobile/core/storage/secure_storage.dart';
import 'package:raje3_mobile/models/user_model.dart';

/// Service layer for all authentication operations.
///
/// Handles login, registration, OTP verification, password management,
/// and token lifecycle. Stores tokens securely via [SecureStorage].
///
/// The backend returns a session_id (UUID) as the auth token.
/// This is stored as the access_token and sent as Bearer header.
class AuthService {
  final ApiClient apiClient;
  final SecureStorage secureStorage;

  AuthService({
    required this.apiClient,
    required this.secureStorage,
  });

  // NOTE: endpoint paths below ('/auth/...') are placeholders in this
  // infra-only pass — Raje3's real auth endpoints aren't decided yet.
  // The shape (REST verb + path + typed response) is what matters here.

  /// Login with phone number and password.
  Future<ApiResponse<UserModel>> login(String phone, String password) async {
    final raw = await apiClient.post<Map<String, dynamic>>(
      '/auth/login',
      data: {
        'phone': phone,
        'password': password,
      },
      fromJson: (json) => json,
    );

    return _handleAuthResponse(raw);
  }

  /// Request an OTP code to be sent to the given phone number.
  Future<ApiResponse> requestOtp(String phone) async {
    return await apiClient.post('/auth/otp/request', data: {'phone': phone});
  }

  /// Request an OTP for phone verification after registration.
  Future<ApiResponse> requestPhoneVerifyOtp(String phone) async {
    return await apiClient.post(
      '/auth/phone/verify-request',
      data: {'phone': phone, 'purpose': 'phone_verify'},
    );
  }

  /// Verify phone number with OTP code after registration.
  Future<ApiResponse> verifyPhone(String phone, String otp) async {
    return await apiClient.post(
      '/auth/phone/verify',
      data: {'phone': phone, 'otp_code': otp},
    );
  }

  /// Verify the OTP code and complete login.
  Future<ApiResponse<UserModel>> verifyOtp(String phone, String otp) async {
    final raw = await apiClient.post<Map<String, dynamic>>(
      '/auth/otp/verify',
      data: {
        'phone': phone,
        'otp': otp,
      },
      fromJson: (json) => json,
    );

    return _handleAuthResponse(raw);
  }

  /// Register a new user account.
  Future<ApiResponse<UserModel>> register({
    required String phone,
    required String password,
    String? fullName,
    String? email,
    bool termsAccepted = false,
  }) async {
    final raw = await apiClient.post<Map<String, dynamic>>(
      '/auth/register',
      data: {
        'phone': phone,
        'password': password,
        if (fullName != null) 'full_name': fullName,
        if (email != null) 'email': email,
        'terms_accepted': termsAccepted,
      },
      fromJson: (json) => json,
    );

    return _handleAuthResponse(raw);
  }

  /// Request a password reset OTP for the given phone number.
  Future<ApiResponse> forgotPassword(String phone) async {
    return await apiClient.post('/auth/password/forgot', data: {'phone': phone});
  }

  /// Reset password using the OTP received via [forgotPassword].
  Future<ApiResponse> resetPassword(
    String phone,
    String otp,
    String newPassword,
  ) async {
    return await apiClient.post(
      '/auth/password/reset',
      data: {
        'phone': phone,
        'otp': otp,
        'new_password': newPassword,
      },
    );
  }

  /// Change the current user's password.
  Future<ApiResponse> changePassword(
    String oldPassword,
    String newPassword,
  ) async {
    return await apiClient.post(
      '/auth/password/change',
      data: {
        'old_password': oldPassword,
        'new_password': newPassword,
      },
    );
  }

  /// Logout the current user.
  Future<void> logout() async {
    try {
      await apiClient.post('/auth/logout');
    } catch (_) {
      // Proceed with local cleanup even if the API call fails
    } finally {
      await secureStorage.clearAll();
    }
  }

  /// Check whether the user has a valid, non-expired access token.
  Future<bool> isLoggedIn() async {
    final hasToken = await secureStorage.hasAccessToken();
    if (!hasToken) return false;

    final isExpired = await secureStorage.isTokenExpired();
    return !isExpired;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // INTERNAL HELPERS
  // ─────────────────────────────────────────────────────────────────────────

  /// Parse auth response: extract user from data.user, session from data.session.
  ///
  /// The backend returns:
  /// ```json
  /// { "data": { "user": {...}, "session": {"session_id":"uuid","expires_at":"..."} } }
  /// ```
  /// The session_id is used as the Bearer token for all subsequent requests.
  Future<ApiResponse<UserModel>> _handleAuthResponse(
    ApiResponse<Map<String, dynamic>> raw,
  ) async {
    if (!raw.success || raw.data == null) {
      return ApiResponse<UserModel>.failure(
        messageAr: raw.messageAr,
        messageEn: raw.messageEn,
      );
    }

    final data = raw.data!;
    final userJson = data['user'] as Map<String, dynamic>? ?? data;
    final user = UserModel.fromJson(userJson);
    final session = data['session'] as Map<String, dynamic>?;

    // Persist session_id as the access token.
    // Note: session-based auth has no separate refresh token — only
    // the session_id is used as Bearer token for all requests.
    if (session != null) {
      final sessionId = session['session_id'] as String?;
      final expiresAt = session['expires_at'] as String?;
      if (sessionId != null) {
        await secureStorage.setAccessToken(sessionId);
        if (expiresAt != null) {
          await secureStorage.setTokenExpiry(expiresAt);
        }
      }
    }

    // Persist user data
    await secureStorage.setUserData(jsonEncode(user.toJson()));

    return ApiResponse<UserModel>.success(
      data: user,
      messageAr: raw.messageAr,
      messageEn: raw.messageEn,
      meta: raw.meta,
    );
  }
}
