import 'package:flutter/material.dart';
import 'package:raje3_mobile/core/storage/local_storage.dart';

/// Provider that manages the app's theme mode (light / dark).
///
/// The preference is persisted in local storage and restored on app restart.
///
/// Setup:
/// ```dart
/// ChangeNotifierProvider(
///   create: (context) => ThemeProvider(localStorage: localStorage),
/// )
/// ```
///
/// Usage in widgets:
/// ```dart
/// final themeProvider = context.watch<ThemeProvider>();
///
/// // Toggle
/// themeProvider.toggle();
///
/// // Check current mode
/// if (themeProvider.isDark) { ... }
/// ```
class ThemeProvider extends ChangeNotifier {
  final LocalStorage localStorage;

  late ThemeMode _mode;

  ThemeProvider({required this.localStorage}) {
    final stored = localStorage.getThemeMode();
    _mode = _fromString(stored);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // GETTERS
  // ─────────────────────────────────────────────────────────────────────────

  ThemeMode get mode => _mode;

  bool get isDark  => _mode == ThemeMode.dark;
  bool get isLight => _mode == ThemeMode.light;

  // ─────────────────────────────────────────────────────────────────────────
  // SETTERS
  // ─────────────────────────────────────────────────────────────────────────

  void setMode(ThemeMode mode) {
    if (_mode == mode) return;
    _mode = mode;
    localStorage.setThemeMode(_toString(mode));
    notifyListeners();
  }

  void toggle() {
    setMode(isDark ? ThemeMode.light : ThemeMode.dark);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // HELPERS
  // ─────────────────────────────────────────────────────────────────────────

  static ThemeMode _fromString(String? value) {
    switch (value) {
      case 'dark':
        return ThemeMode.dark;
      case 'light':
        return ThemeMode.light;
      default:
        return ThemeMode.light; // default to light (majestic light is the primary)
    }
  }

  static String _toString(ThemeMode mode) {
    switch (mode) {
      case ThemeMode.dark:
        return 'dark';
      case ThemeMode.light:
      case ThemeMode.system:
        return 'light';
    }
  }
}
