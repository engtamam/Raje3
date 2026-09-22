import 'dart:ui' show Offset;

import 'package:shared_preferences/shared_preferences.dart';
import 'package:raje3_mobile/core/constants/app_constants.dart';

/// Wrapper around [SharedPreferences] for non-sensitive local storage.
///
/// Used for user preferences, flags, cached settings, and other
/// non-sensitive data that doesn't need encryption.
///
/// Must call [init] before using. This is done once in `main.dart`.
///
/// Usage:
/// ```dart
/// final storage = LocalStorage();
/// await storage.init();
///
/// // User preferences
/// await storage.setLocale('ar');
/// final locale = storage.getLocale(); // 'ar'
///
/// // Onboarding
/// await storage.setOnboardingComplete(true);
/// if (storage.isOnboardingComplete) { ... }
/// ```
class LocalStorage {
  SharedPreferences? _prefs;

  /// Initialize SharedPreferences. Must be called before any other method.
  Future<void> init() async {
    _prefs = await SharedPreferences.getInstance();
  }

  /// Verify that [init] has been called.
  SharedPreferences get _safePrefs {
    if (_prefs == null) {
      throw StateError(
        'LocalStorage not initialized. Call LocalStorage.init() first.',
      );
    }
    return _prefs!;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // GENERIC OPERATIONS
  // ─────────────────────────────────────────────────────────────────────────

  /// Read a string value by key. Returns null if not found.
  String? getString(String key) {
    return _safePrefs.getString(key);
  }

  /// Write a string value.
  Future<bool> setString(String key, String value) {
    return _safePrefs.setString(key, value);
  }

  /// Read a bool value by key. Returns null if not found.
  bool? getBool(String key) {
    return _safePrefs.getBool(key);
  }

  /// Write a bool value.
  Future<bool> setBool(String key, bool value) {
    return _safePrefs.setBool(key, value);
  }

  /// Read an int value by key. Returns null if not found.
  int? getInt(String key) {
    return _safePrefs.getInt(key);
  }

  /// Write an int value.
  Future<bool> setInt(String key, int value) {
    return _safePrefs.setInt(key, value);
  }

  /// Read a double value by key. Returns null if not found.
  double? getDouble(String key) {
    return _safePrefs.getDouble(key);
  }

  /// Write a double value.
  Future<bool> setDouble(String key, double value) {
    return _safePrefs.setDouble(key, value);
  }

  /// Read a string list by key. Returns null if not found.
  List<String>? getStringList(String key) {
    return _safePrefs.getStringList(key);
  }

  /// Write a string list.
  Future<bool> setStringList(String key, List<String> value) {
    return _safePrefs.setStringList(key, value);
  }

  /// Remove a key.
  Future<bool> remove(String key) {
    return _safePrefs.remove(key);
  }

  /// Clear all stored data.
  Future<bool> clear() {
    return _safePrefs.clear();
  }

  /// Check if a key exists.
  bool containsKey(String key) {
    return _safePrefs.containsKey(key);
  }

  /// Get all stored keys.
  Set<String> getKeys() {
    return _safePrefs.getKeys();
  }

  // ─────────────────────────────────────────────────────────────────────────
  // LOCALE
  // ─────────────────────────────────────────────────────────────────────────

  /// Get the user's preferred locale code ('ar' or 'en').
  /// Defaults to 'ar' (Arabic) if not set.
  String getLocale() {
    return getString(AppConstants.localeKey) ?? 'ar';
  }

  /// Set the user's preferred locale code.
  Future<bool> setLocale(String locale) {
    return setString(AppConstants.localeKey, locale);
  }

  /// Whether the current locale is Arabic.
  bool get isArabic => getLocale() == 'ar';

  // ─────────────────────────────────────────────────────────────────────────
  // THEME MODE
  // ─────────────────────────────────────────────────────────────────────────

  /// Get the user's preferred theme mode ('light' or 'dark').
  /// Defaults to 'light' if not set.
  String? getThemeMode() {
    return getString(AppConstants.themeModeKey);
  }

  /// Set the user's preferred theme mode.
  Future<bool> setThemeMode(String mode) {
    return setString(AppConstants.themeModeKey, mode);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // CUSTOM NAV SLOT
  // ─────────────────────────────────────────────────────────────────────────

  /// The nav section id pinned to the bottom bar's one customizable slot.
  /// Defaults to 'visit' when unset.
  String getCustomNavSlot() {
    return getString(AppConstants.customNavSlotKey) ?? 'visit';
  }

  /// Set the nav section id pinned to the bottom bar's customizable slot.
  Future<bool> setCustomNavSlot(String sectionId) {
    return setString(AppConstants.customNavSlotKey, sectionId);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // FLOATING MIC BUTTON POSITION
  // ─────────────────────────────────────────────────────────────────────────

  /// The floating AI mic button's last dragged position, as (dx, dy)
  /// fractions of the screen (0.0–1.0). Null when never dragged — the
  /// widget picks its own default (left side) in that case.
  Offset? getMicButtonPosition() {
    final raw = getString(AppConstants.micButtonPositionKey);
    if (raw == null) return null;
    final parts = raw.split(',');
    if (parts.length != 2) return null;
    final dx = double.tryParse(parts[0]);
    final dy = double.tryParse(parts[1]);
    if (dx == null || dy == null) return null;
    return Offset(dx, dy);
  }

  /// Persist the floating AI mic button's dragged position.
  Future<bool> setMicButtonPosition(Offset fraction) {
    return setString(AppConstants.micButtonPositionKey, '${fraction.dx},${fraction.dy}');
  }

  // ─────────────────────────────────────────────────────────────────────────
  // MOBILE AI ASSISTANT ENTITLEMENT (cached, fallback-only — see AiEntitlementProvider)
  // ─────────────────────────────────────────────────────────────────────────

  /// The last confirmed answer, or null if never successfully checked. Read only when a fresh
  /// check could not be made.
  bool? getMobileAiAssistantSubscribed() {
    return getBool(AppConstants.mobileAiAssistantSubscribedKey);
  }

  /// Persist the last CONFIRMED (`checked: true`) answer only — never a guess.
  Future<bool> setMobileAiAssistantSubscribed(bool subscribed) {
    return setBool(AppConstants.mobileAiAssistantSubscribedKey, subscribed);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // ONBOARDING
  // ─────────────────────────────────────────────────────────────────────────

  /// Whether the user has completed onboarding.
  bool get isOnboardingComplete {
    return getBool(AppConstants.onboardingCompleteKey) ?? false;
  }

  /// Mark onboarding as complete.
  Future<bool> setOnboardingComplete(bool complete) {
    return setBool(AppConstants.onboardingCompleteKey, complete);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // ACTIVE CONTEXT
  // ─────────────────────────────────────────────────────────────────────────

  /// Get the active context ID (the current hair/skin analysis profile).
  String? getActiveContextId() {
    return getString(AppConstants.activeContextKey);
  }

  /// Set the active context ID.
  Future<bool> setActiveContextId(String contextId) {
    return setString(AppConstants.activeContextKey, contextId);
  }

  /// Clear the active context ID.
  Future<bool> clearActiveContextId() {
    return remove(AppConstants.activeContextKey);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // LAST SYNC
  // ─────────────────────────────────────────────────────────────────────────

  /// Get the last sync timestamp as an ISO 8601 string.
  String? getLastSync() {
    return getString(AppConstants.lastSyncKey);
  }

  /// Set the last sync timestamp.
  Future<bool> setLastSync(DateTime dateTime) {
    return setString(AppConstants.lastSyncKey, dateTime.toIso8601String());
  }

  /// Get the last sync as a DateTime. Returns null if never synced.
  DateTime? getLastSyncDateTime() {
    final str = getLastSync();
    if (str == null) return null;
    return DateTime.tryParse(str);
  }

  // NOTE: the reference project also had a "card display settings" and a
  // "streak/donation info hint" section here — both belonged to its own
  // gamification feature (streak cards), not to reusable storage
  // infrastructure, so they are dropped rather than ported.

  // ─────────────────────────────────────────────────────────────────────────
  // CLEAR USER DATA (on logout, but keep preferences)
  // ─────────────────────────────────────────────────────────────────────────

  /// Clear user-specific data but preserve app preferences (locale, etc.).
  Future<void> clearUserData() async {
    await Future.wait([
      remove(AppConstants.activeContextKey),
      remove(AppConstants.lastSyncKey),
    ]);
  }
}
