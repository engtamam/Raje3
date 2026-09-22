import 'package:intl/intl.dart';
import 'package:raje3_mobile/core/constants/app_constants.dart';

/// Formatting utilities for currency, dates, numbers, and phone numbers.
///
/// All formatters are locale-aware, defaulting to Arabic ('ar') to match
/// the app's primary audience in Saudi Arabia.
class Formatters {
  Formatters._(); // Prevent instantiation

  // ─────────────────────────────────────────────────────────────────────────
  // DIGITS
  // ─────────────────────────────────────────────────────────────────────────

  // arabic-indic-digits: intentional — this map is what CONVERTS them to 0-9,
  // the one legitimate reason a file may name them (see ci/check_deploy_wiring.py).
  //
  // intl's 'ar_SA' locale data renders Arabic-Indic digits (٠-٩) by default —
  // this product's own rule is every number is 0-9, even inside Arabic text
  // (same rule the web console enforces via toLocaleString('en-US'), see
  // apps/console/src/screens/Wallet.tsx). Rather than trust an ICU numbering-
  // system locale extension to be wired into the bundled locale data, convert
  // the characters directly after formatting — this is correct regardless of
  // which locale data intl ships.
  static const Map<String, String> _arabicIndicToWestern = {
    '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
    '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9',
  };

  static String _westernDigits(String input) {
    final buffer = StringBuffer();
    for (final char in input.split('')) {
      buffer.write(_arabicIndicToWestern[char] ?? char);
    }
    return buffer.toString();
  }

  // ─────────────────────────────────────────────────────────────────────────
  // PLATE — mirrors apps/console/src/screens/Visit.tsx::formatPlate exactly, digit for digit,
  // so a plate typed on either screen for the same car reads the same way.
  // ─────────────────────────────────────────────────────────────────────────

  /// Digits (max 4, folded from Arabic-Indic first) then letters (max 3, either script,
  /// uppercased), space-joined — "1234 ABC". Letters-only when there are no digits at all.
  ///
  /// FOLD BEFORE STRIPPING (same real bug console's own formatPlate fixed once): an Arabic-Indic
  /// digit is a real digit and must never be dropped along with punctuation.
  static String formatPlate(String raw) {
    final folded = _westernDigits(raw);
    final digits = folded.runes
        .map(String.fromCharCode)
        .where((ch) => RegExp(r'[0-9]').hasMatch(ch))
        .take(4)
        .join();
    final letters = folded.runes
        .map(String.fromCharCode)
        .where((ch) => RegExp(r'\p{L}', unicode: true).hasMatch(ch))
        .take(3)
        .join()
        .toUpperCase();
    return letters.isNotEmpty ? '$digits $letters'.trim() : digits;
  }

  /// One letter and one digit, in any script, anywhere — the EXACT rule
  /// `services/operations/app/core/plate.py::is_plausible` enforces server-side. Never the
  /// stricter Saudi format: temporary, transit, Gulf and diplomatic plates are all real.
  static bool isPlatePlausible(String plate) {
    final folded = _westernDigits(plate);
    final hasDigit = RegExp(r'[0-9]').hasMatch(folded);
    final hasLetter = RegExp(r'\p{L}', unicode: true).hasMatch(folded);
    return hasDigit && hasLetter;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // CURRENCY
  // ─────────────────────────────────────────────────────────────────────────

  /// Format a currency amount in Saudi Riyals.
  ///
  /// Arabic: "500.00 ر.س"
  /// English: "500.00 SAR"
  ///
  /// Examples:
  /// ```dart
  /// Formatters.formatCurrency(500)        // "500.00 ر.س"
  /// Formatters.formatCurrency(500, locale: 'en') // "500.00 SAR"
  /// Formatters.formatCurrency(1250.5)     // "1,250.50 ر.س"
  /// ```
  static String formatCurrency(double amount, {String locale = 'ar'}) {
    final formatter = NumberFormat('#,##0.00', locale == 'ar' ? 'ar_SA' : 'en');
    final formatted = _westernDigits(formatter.format(amount));
    final currencySymbol =
        locale == 'ar' ? AppConstants.currencyAr : AppConstants.currency;
    return '$formatted $currencySymbol';
  }

  /// Format currency without decimal places.
  ///
  /// Arabic: "500 ر.س"
  /// English: "500 SAR"
  static String formatCurrencyCompact(double amount, {String locale = 'ar'}) {
    final formatter = NumberFormat('#,##0', locale == 'ar' ? 'ar_SA' : 'en');
    final formatted = _westernDigits(formatter.format(amount));
    final currencySymbol =
        locale == 'ar' ? AppConstants.currencyAr : AppConstants.currency;
    return '$formatted $currencySymbol';
  }

  /// Format currency with VAT included.
  ///
  /// Returns the amount after adding 15% VAT.
  static String formatCurrencyWithVat(double amount, {String locale = 'ar'}) {
    final amountWithVat = amount * (1 + AppConstants.vatRate);
    return formatCurrency(amountWithVat, locale: locale);
  }

  /// Calculate and return the VAT amount.
  static double calculateVat(double amount) {
    return amount * AppConstants.vatRate;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // DATE & TIME
  // ─────────────────────────────────────────────────────────────────────────

  /// Format a DateTime with a custom pattern.
  ///
  /// Common patterns:
  /// - 'yyyy-MM-dd' → "2026-02-21"
  /// - 'dd/MM/yyyy' → "21/02/2026"
  /// - 'EEEE, d MMMM yyyy' → "السبت, 21 فبراير 2026"
  /// - 'h:mm a' → "3:30 م"
  ///
  /// Defaults to 'dd/MM/yyyy' pattern.
  static String formatDate(
    DateTime dateTime, {
    String locale = 'ar',
    String pattern = 'dd/MM/yyyy',
  }) {
    final formatter = DateFormat(pattern, locale == 'ar' ? 'ar_SA' : 'en');
    return _westernDigits(formatter.format(dateTime));
  }

  /// Format a DateTime as a full date string.
  ///
  /// Arabic: "السبت, 21 فبراير 2026"
  /// English: "Saturday, 21 February 2026"
  static String formatDateFull(DateTime dateTime, {String locale = 'ar'}) {
    return formatDate(
      dateTime,
      locale: locale,
      pattern: 'EEEE, d MMMM yyyy',
    );
  }

  /// Format a DateTime as a short date string.
  ///
  /// Arabic: "21 فبراير"
  /// English: "21 Feb"
  static String formatDateShort(DateTime dateTime, {String locale = 'ar'}) {
    return formatDate(
      dateTime,
      locale: locale,
      pattern: locale == 'ar' ? 'd MMMM' : 'd MMM',
    );
  }

  /// Format a DateTime as time only.
  ///
  /// Arabic: "3:30 م"
  /// English: "3:30 PM"
  static String formatTime(DateTime dateTime, {String locale = 'ar'}) {
    return formatDate(dateTime, locale: locale, pattern: 'h:mm a');
  }

  /// Format a DateTime as date and time.
  ///
  /// Arabic: "21/02/2026 - 3:30 م"
  /// English: "21/02/2026 - 3:30 PM"
  static String formatDateTime(DateTime dateTime, {String locale = 'ar'}) {
    final date = formatDate(dateTime, locale: locale);
    final time = formatTime(dateTime, locale: locale);
    return '$date - $time';
  }

  // ─────────────────────────────────────────────────────────────────────────
  // TIME AGO
  // ─────────────────────────────────────────────────────────────────────────

  /// Format a DateTime as a relative time string ("time ago").
  ///
  /// Arabic: "منذ 5 دقائق", "منذ ساعة", "منذ يومين"
  /// English: "5 minutes ago", "1 hour ago", "2 days ago"
  static String formatTimeAgo(DateTime dateTime, {String locale = 'ar'}) {
    final now = DateTime.now();
    final difference = now.difference(dateTime);

    if (locale == 'ar') {
      return _formatTimeAgoAr(difference);
    }
    return _formatTimeAgoEn(difference);
  }

  static String _formatTimeAgoAr(Duration difference) {
    if (difference.inSeconds < 60) {
      return 'الآن';
    } else if (difference.inMinutes < 2) {
      return 'منذ دقيقة';
    } else if (difference.inMinutes < 11) {
      return 'منذ ${difference.inMinutes} دقائق';
    } else if (difference.inMinutes < 60) {
      return 'منذ ${difference.inMinutes} دقيقة';
    } else if (difference.inHours < 2) {
      return 'منذ ساعة';
    } else if (difference.inHours < 11) {
      return 'منذ ${difference.inHours} ساعات';
    } else if (difference.inHours < 24) {
      return 'منذ ${difference.inHours} ساعة';
    } else if (difference.inDays < 2) {
      return 'أمس';
    } else if (difference.inDays < 11) {
      return 'منذ ${difference.inDays} أيام';
    } else if (difference.inDays < 30) {
      return 'منذ ${difference.inDays} يوم';
    } else if (difference.inDays < 60) {
      return 'منذ شهر';
    } else if (difference.inDays < 365) {
      final months = (difference.inDays / 30).floor();
      if (months < 11) {
        return 'منذ $months أشهر';
      }
      return 'منذ $months شهر';
    } else {
      final years = (difference.inDays / 365).floor();
      if (years < 2) {
        return 'منذ سنة';
      } else if (years < 11) {
        return 'منذ $years سنوات';
      }
      return 'منذ $years سنة';
    }
  }

  static String _formatTimeAgoEn(Duration difference) {
    if (difference.inSeconds < 60) {
      return 'Just now';
    } else if (difference.inMinutes < 2) {
      return '1 minute ago';
    } else if (difference.inMinutes < 60) {
      return '${difference.inMinutes} minutes ago';
    } else if (difference.inHours < 2) {
      return '1 hour ago';
    } else if (difference.inHours < 24) {
      return '${difference.inHours} hours ago';
    } else if (difference.inDays < 2) {
      return 'Yesterday';
    } else if (difference.inDays < 30) {
      return '${difference.inDays} days ago';
    } else if (difference.inDays < 60) {
      return '1 month ago';
    } else if (difference.inDays < 365) {
      final months = (difference.inDays / 30).floor();
      return '$months months ago';
    } else {
      final years = (difference.inDays / 365).floor();
      if (years < 2) {
        return '1 year ago';
      }
      return '$years years ago';
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // NUMBER
  // ─────────────────────────────────────────────────────────────────────────

  /// Format a number with locale-aware grouping.
  ///
  /// Arabic: "1,250"
  /// English: "1,250"
  static String formatNumber(num value, {String locale = 'ar'}) {
    final formatter = NumberFormat('#,##0', locale == 'ar' ? 'ar_SA' : 'en');
    return _westernDigits(formatter.format(value));
  }

  /// Format a number as a decimal with specific precision.
  ///
  /// Arabic: "4.5"
  /// English: "4.5"
  static String formatDecimal(
    num value, {
    String locale = 'ar',
    int decimalDigits = 1,
  }) {
    final pattern = '#,##0.${'0' * decimalDigits}';
    final formatter = NumberFormat(pattern, locale == 'ar' ? 'ar_SA' : 'en');
    return _westernDigits(formatter.format(value));
  }

  /// Format a number as a percentage.
  ///
  /// Arabic: "85٪"
  /// English: "85%"
  static String formatPercentage(num value, {String locale = 'ar'}) {
    final formatter = NumberFormat('#,##0', locale == 'ar' ? 'ar_SA' : 'en');
    return '${_westernDigits(formatter.format(value))}%';
  }

  /// Format a number in compact form (e.g., 1.2K, 3.5M).
  ///
  /// Arabic: "1.2 ألف"
  /// English: "1.2K"
  static String formatCompact(num value, {String locale = 'ar'}) {
    final formatter =
        NumberFormat.compact(locale: locale == 'ar' ? 'ar_SA' : 'en');
    return _westernDigits(formatter.format(value));
  }

  // ─────────────────────────────────────────────────────────────────────────
  // PHONE NUMBER
  // ─────────────────────────────────────────────────────────────────────────

  /// Format a Saudi phone number.
  ///
  /// Input: "966512345678" or "0512345678" or "+966512345678"
  /// Output: "+966 51 234 5678"
  static String formatPhoneNumber(String phone) {
    // Remove all non-digit characters
    String digits = phone.replaceAll(RegExp(r'[^\d]'), '');

    // Normalize to full Saudi format
    if (digits.startsWith('00966')) {
      digits = digits.substring(2); // Remove leading 00
    } else if (digits.startsWith('0') && digits.length == 10) {
      digits = '966${digits.substring(1)}'; // 05xxxxxxxx -> 9665xxxxxxxx
    } else if (!digits.startsWith('966') && digits.length == 9) {
      digits = '966$digits'; // 5xxxxxxxx -> 9665xxxxxxxx
    }

    // Format: +966 5X XXX XXXX
    if (digits.length == 12 && digits.startsWith('966')) {
      return '+${digits.substring(0, 3)} '
          '${digits.substring(3, 5)} '
          '${digits.substring(5, 8)} '
          '${digits.substring(8)}';
    }

    // Return original if format not recognized
    return phone;
  }

  /// Get a Saudi phone number in international format (digits only).
  ///
  /// Input: "0512345678" or "+966 51 234 5678"
  /// Output: "966512345678"
  static String normalizePhoneNumber(String phone) {
    String digits = phone.replaceAll(RegExp(r'[^\d]'), '');

    if (digits.startsWith('00966')) {
      digits = digits.substring(2);
    } else if (digits.startsWith('0') && digits.length == 10) {
      digits = '966${digits.substring(1)}';
    } else if (!digits.startsWith('966') && digits.length == 9) {
      digits = '966$digits';
    }

    return digits;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // FILE SIZE
  // ─────────────────────────────────────────────────────────────────────────

  /// Format a file size in bytes to a human-readable string.
  ///
  /// Examples: "1.2 MB", "500 KB", "2.3 GB"
  static String formatFileSize(int bytes, {String locale = 'ar'}) {
    if (bytes < 1024) {
      return '$bytes B';
    } else if (bytes < 1024 * 1024) {
      final kb = bytes / 1024;
      return '${formatDecimal(kb, locale: locale)} KB';
    } else if (bytes < 1024 * 1024 * 1024) {
      final mb = bytes / (1024 * 1024);
      return '${formatDecimal(mb, locale: locale)} MB';
    } else {
      final gb = bytes / (1024 * 1024 * 1024);
      return '${formatDecimal(gb, locale: locale)} GB';
    }
  }
}
