import 'dart:ui';

import 'package:flutter/foundation.dart';
import 'package:raje3_mobile/core/storage/local_storage.dart';

/// Provider that manages the app's locale (language) setting.
///
/// Supports Arabic (ar) as the primary language and English (en)
/// as the secondary language. The locale preference is persisted
/// in local storage and restored on app restart.
///
/// Setup:
/// ```dart
/// ChangeNotifierProvider(
///   create: (context) => LocaleProvider(localStorage: localStorage),
/// )
/// ```
///
/// Usage in widgets:
/// ```dart
/// final localeProvider = context.watch<LocaleProvider>();
/// Text(localeProvider.isArabic ? 'مرحبا' : 'Hello');
///
/// // Toggle language
/// ElevatedButton(
///   onPressed: () => localeProvider.toggleLocale(),
///   child: Text(localeProvider.isArabic ? 'English' : 'العربية'),
/// );
/// ```
class LocaleProvider extends ChangeNotifier {
  final LocalStorage localStorage;

  late Locale _locale;

  LocaleProvider({required this.localStorage}) {
    // Initialize from stored preference, default to Arabic
    final storedLocale = localStorage.getLocale();
    _locale = Locale(storedLocale);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // GETTERS
  // ─────────────────────────────────────────────────────────────────────────

  /// The current locale.
  Locale get locale => _locale;

  /// Whether the current locale is Arabic.
  bool get isArabic => _locale.languageCode == 'ar';

  /// The current language code ('ar' or 'en').
  String get languageCode => _locale.languageCode;

  // ─────────────────────────────────────────────────────────────────────────
  // SETTERS
  // ─────────────────────────────────────────────────────────────────────────

  /// Set the locale to a specific value.
  ///
  /// Persists the choice to local storage and notifies listeners.
  /// No-op if the locale is already set to the given value.
  void setLocale(Locale locale) {
    if (_locale == locale) return;

    _locale = locale;
    localStorage.setLocale(locale.languageCode);
    notifyListeners();
  }

  /// Toggle between Arabic and English.
  ///
  /// If currently Arabic, switches to English, and vice versa.
  void toggleLocale() {
    if (isArabic) {
      setLocale(const Locale('en'));
    } else {
      setLocale(const Locale('ar'));
    }
  }
}
