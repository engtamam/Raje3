import 'dart:ui';

import 'package:flutter/foundation.dart';
import 'package:raje3_mobile/core/storage/local_storage.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';

/// Provider that manages the app's locale (language) setting.
///
/// Supports all six of S.supportedLocales (ar/en/ur/ha/fil/bn) — WIDENED from an ar/en-only
/// toggle (FOUND LIVE, owner's own report 2026-09-29: this provider and its own persisted
/// preference already existed, but nothing in the app ever exposed a way to reach it — a shop
/// stuck on whichever locale its device booted into, with no in-app escape). The locale
/// preference is persisted in local storage and restored on app restart.
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
/// localeProvider.setLocale(const Locale('ur'));
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

  /// The current language code (one of S.supportedLocales' own codes).
  String get languageCode => _locale.languageCode;

  // ─────────────────────────────────────────────────────────────────────────
  // SETTERS
  // ─────────────────────────────────────────────────────────────────────────

  /// Set the locale to a specific value.
  ///
  /// Persists the choice to local storage and notifies listeners. No-op if the locale is
  /// already set to the given value, or if it is not one of S.supportedLocales — the account
  /// screen's own picker only ever offers those, so reaching this with anything else would be a
  /// caller bug, not a real user choice to honour.
  void setLocale(Locale locale) {
    if (_locale == locale) return;
    if (!S.supportedLocales.contains(locale)) return;

    _locale = locale;
    localStorage.setLocale(locale.languageCode);
    notifyListeners();
  }
}
