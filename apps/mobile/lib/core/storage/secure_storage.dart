import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:raje3_mobile/core/config/app_config.dart';
import 'package:raje3_mobile/core/constants/app_constants.dart';

/// Wrapper around [FlutterSecureStorage] for encrypted key-value storage.
///
/// Used primarily for sensitive data: access tokens, refresh tokens,
/// and user credentials. All values are encrypted at rest using the
/// platform's native keychain/keystore.
///
/// Usage:
/// ```dart
/// final storage = SecureStorage();
///
/// // Store token
/// await storage.setAccessToken('eyJ...');
///
/// // Read token
/// final token = await storage.getAccessToken();
///
/// // Clear on logout
/// await storage.clearTokens();
/// ```
class SecureStorage {
  late final FlutterSecureStorage _storage;

  SecureStorage({FlutterSecureStorage? storage}) {
    _storage = storage ??
        const FlutterSecureStorage(
          aOptions: AndroidOptions(
            encryptedSharedPreferences: true,
          ),
          iOptions: IOSOptions(
            accessibility: KeychainAccessibility.first_unlock_this_device,
          ),
        );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // GENERIC OPERATIONS
  // ─────────────────────────────────────────────────────────────────────────

  /// Read a value by key. Returns null if the key doesn't exist.
  Future<String?> read(String key) async {
    try {
      return await _storage.read(key: key);
    } catch (e) {
      // If there's a decryption error (e.g. after app reinstall),
      // delete the corrupt value and return null.
      await _storage.delete(key: key);
      return null;
    }
  }

  /// Write a key-value pair. Overwrites if the key already exists.
  Future<void> write(String key, String value) async {
    await _storage.write(key: key, value: value);
  }

  /// Delete a single key.
  Future<void> delete(String key) async {
    await _storage.delete(key: key);
  }

  /// Delete all stored values. Use with caution.
  Future<void> deleteAll() async {
    await _storage.deleteAll();
  }

  /// Check if a key exists and has a non-null value.
  Future<bool> containsKey(String key) async {
    return await _storage.containsKey(key: key);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // ACCESS TOKEN
  // ─────────────────────────────────────────────────────────────────────────

  /// Get the stored access token (JWT).
  Future<String?> getAccessToken() async {
    return await read(AppConstants.accessTokenKey);
  }

  /// Store a new access token.
  Future<void> setAccessToken(String token) async {
    await write(AppConstants.accessTokenKey, token);
  }

  /// Check if an access token exists.
  Future<bool> hasAccessToken() async {
    final token = await getAccessToken();
    return token != null && token.isNotEmpty;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // REFRESH TOKEN
  // ─────────────────────────────────────────────────────────────────────────

  /// Get the stored refresh token.
  Future<String?> getRefreshToken() async {
    return await read(AppConstants.refreshTokenKey);
  }

  /// Store a new refresh token.
  Future<void> setRefreshToken(String token) async {
    await write(AppConstants.refreshTokenKey, token);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // TOKEN EXPIRY
  // ─────────────────────────────────────────────────────────────────────────

  /// Get the stored token expiry timestamp (ISO 8601 string).
  Future<String?> getTokenExpiry() async {
    return await read(AppConstants.tokenExpiryKey);
  }

  /// Store the token expiry timestamp.
  Future<void> setTokenExpiry(String expiry) async {
    await write(AppConstants.tokenExpiryKey, expiry);
  }

  /// Check if the stored access token is expired.
  ///
  /// Returns `true` if:
  /// - No expiry is stored
  /// - The expiry timestamp has passed
  /// - The expiry string can't be parsed
  Future<bool> isTokenExpired() async {
    final expiryStr = await getTokenExpiry();
    if (expiryStr == null || expiryStr.isEmpty) return true;

    try {
      final expiry = DateTime.parse(expiryStr);
      // Consider expired early to account for clock skew. Source: AppConfig.authTokenExpiryBufferSec
      return DateTime.now().isAfter(
        expiry.subtract(const Duration(seconds: AppConfig.authTokenExpiryBufferSec)),
      );
    } catch (e) {
      return true;
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // BULK OPERATIONS
  // ─────────────────────────────────────────────────────────────────────────

  /// Store both tokens at once (after login or refresh).
  Future<void> setTokens({
    required String accessToken,
    required String refreshToken,
    String? tokenExpiry,
  }) async {
    await Future.wait([
      setAccessToken(accessToken),
      setRefreshToken(refreshToken),
      if (tokenExpiry != null) setTokenExpiry(tokenExpiry),
    ]);
  }

  /// Clear all authentication tokens (on logout).
  Future<void> clearTokens() async {
    await Future.wait([
      delete(AppConstants.accessTokenKey),
      delete(AppConstants.refreshTokenKey),
      delete(AppConstants.tokenExpiryKey),
    ]);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // USER DATA
  // ─────────────────────────────────────────────────────────────────────────

  /// Get stored user data (JSON string).
  Future<String?> getUserData() async {
    return await read(AppConstants.userDataKey);
  }

  /// Store user data as a JSON string.
  Future<void> setUserData(String jsonString) async {
    await write(AppConstants.userDataKey, jsonString);
  }

  /// Clear user data.
  Future<void> clearUserData() async {
    await delete(AppConstants.userDataKey);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // FULL CLEAR (LOGOUT)
  // ─────────────────────────────────────────────────────────────────────────

  /// Clear all secure storage data. Call on logout to remove all
  /// sensitive information.
  Future<void> clearAll() async {
    await deleteAll();
  }
}
