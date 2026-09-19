// Raje3 mobile theme.
//
// PATTERN ported from the reference project's `lib/theme/flutterflow_theme.dart`
// (a token-based AppColors/AppSpacing/AppTextStyles file) — the SHAPE only,
// not their colours.
//
// COLORS ARE GENERATED, NOT HAND-COPIED. `AppColors` used to be typed out
// here as literal `Color(0xFF...)` values, copied once from theme.config.ts
// and product.json — exactly the drift class
// ci/check_a_hardcoded_color_does_not_shadow_a_token.py already exists to
// catch on the web side. `AppColors` now lives in `app_colors.g.dart`,
// produced by `scripts/gen_mobile_theme.py` from THIS product's own design
// system: `ui/packages/ui/src/theme/theme.config.ts` (the web console's
// single source of truth for the whole brand) and `config/product.json`'s
// `brand.accent` (the one brand-owned colour, from which hover/soft/on-soft
// tints are derived — same `mix()` formula as theme.config.ts's own). After
// either source changes, re-run that script; `ci/check_mobile_theme_is_generated.py`
// fails the build if the checked-in file and the script's current output
// ever disagree.
//
// Only the LIGHT palette is ported — the console's own theme.config.ts
// documents why light is not a default here but a requirement: "unreadable
// on a tablet in an open workshop at noon". Dark mode can be added later
// following the same token shape if the product ever needs it on mobile.

import 'package:flutter/material.dart';

import 'app_colors.g.dart';
export 'app_colors.g.dart';

/// ═══════════════════════════════════════════════════════════════════════════
/// SCALE — mirrors theme.config.ts's `Scale` interface (radius/shadow/motion).
/// ═══════════════════════════════════════════════════════════════════════════
class AppRadius {
  static const double sm = 8;
  static const double md = 10;
  static const double lg = 14;
  static const double card = 20; // theme.config.ts: 1.25rem
  static const double pill = 9999;

  static BorderRadius get standardRadius => BorderRadius.circular(md);
  static BorderRadius get cardRadius => BorderRadius.circular(card);
}

class AppSpacing {
  static const double xs = 4;
  static const double sm = 8;
  static const double md = 16;
  static const double lg = 24;
  static const double xl = 32;
  static const double xxl = 48;
}

class AppIconSizes {
  static const double small = 16;
  static const double medium = 24;
  static const double large = 32;
}

/// Motion durations — theme.config.ts's `Scale.motion`.
class AppMotion {
  static const Duration fast = Duration(milliseconds: 120);
  static const Duration base = Duration(milliseconds: 200);
  static const Duration slow = Duration(milliseconds: 360);
}

/// ═══════════════════════════════════════════════════════════════════════════
/// TEXT STYLES
/// ═══════════════════════════════════════════════════════════════════════════
class AppTextStyles {
  // theme.config.ts pairs a heavier display face (Cairo, headings/numbers)
  // with a lighter body face (Tajawal). Flutter apps bundle font assets
  // separately from the web's webfont links — Raje3's own font files (if
  // bundled) go under assets/fonts/ and get registered in pubspec.yaml;
  // until then this falls back to the platform default, same as any
  // unbundled fontFamily.
  static const String arabicFont = 'Cairo';
  static const String englishFont = 'Inter';

  static const TextStyle headlineMedium = TextStyle(
    fontFamily: arabicFont,
    fontSize: 22,
    fontWeight: FontWeight.w700,
    color: AppColors.textPrimary,
  );

  static const TextStyle headlineSmall = TextStyle(
    fontFamily: arabicFont,
    fontSize: 18,
    fontWeight: FontWeight.w600,
    color: AppColors.textPrimary,
  );

  static const TextStyle bodyMedium = TextStyle(
    fontFamily: arabicFont,
    fontSize: 14,
    fontWeight: FontWeight.w400,
    color: AppColors.textPrimary,
  );

  static const TextStyle bodySmall = TextStyle(
    fontFamily: arabicFont,
    fontSize: 12,
    fontWeight: FontWeight.w400,
    color: AppColors.textSecondary,
  );

  static const TextStyle displaySmall = TextStyle(
    fontFamily: arabicFont,
    fontSize: 26,
    fontWeight: FontWeight.w700,
    color: AppColors.textPrimary,
  );

  static const TextStyle labelMedium = TextStyle(
    fontFamily: arabicFont,
    fontSize: 13,
    fontWeight: FontWeight.w600,
    color: AppColors.textPrimary,
  );

  static const TextStyle button = TextStyle(
    fontFamily: arabicFont,
    fontSize: 14,
    fontWeight: FontWeight.w700,
  );

  static const TextStyle caption = TextStyle(
    fontFamily: arabicFont,
    fontSize: 11,
    fontWeight: FontWeight.w400,
    color: AppColors.textMuted,
  );
}

/// ═══════════════════════════════════════════════════════════════════════════
/// AUTH-SCREEN CRAFT — same visual language pattern ported from the reference
/// project's own login/register screens (elevated card, gradient primary
/// action, filled input fields), our own tokens throughout. Kept here, not
/// hand-repeated per screen, so every auth screen reads as one product.
/// ═══════════════════════════════════════════════════════════════════════════
class AppCardDecorations {
  static BoxDecoration get elevated => BoxDecoration(
        color: AppColors.surface1,
        borderRadius: AppRadius.cardRadius,
        border: Border.all(color: AppColors.borderSubtle),
        boxShadow: [
          BoxShadow(
            color: AppColors.textPrimary.withValues(alpha: 0.06),
            blurRadius: 24,
            offset: const Offset(0, 8),
          ),
        ],
      );
}

class AppInputDecorations {
  static InputDecoration get standard => InputDecoration(
        filled: true,
        fillColor: AppColors.surface2,
        border: OutlineInputBorder(
          borderRadius: AppRadius.standardRadius,
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: AppRadius.standardRadius,
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: AppRadius.standardRadius,
          borderSide: const BorderSide(color: AppColors.accent, width: 1.5),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: AppRadius.standardRadius,
          borderSide: const BorderSide(color: AppColors.danger, width: 1),
        ),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: AppSpacing.md,
        ),
        labelStyle: AppTextStyles.bodyMedium.copyWith(color: AppColors.textSecondary),
      );
}

/// One brand gradient, derived from the same accent/hover tokens
/// `app_colors.g.dart` already generates — never a second literal colour.
LinearGradient get appPrimaryGradient => const LinearGradient(
      colors: [AppColors.accent, AppColors.accentHover],
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
    );

/// ═══════════════════════════════════════════════════════════════════════════
/// MATERIAL THEME
/// ═══════════════════════════════════════════════════════════════════════════
class AppTheme {
  AppTheme._();

  static ThemeData get light {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      scaffoldBackgroundColor: AppColors.surface0,
      colorScheme: const ColorScheme.light(
        primary: AppColors.accent,
        onPrimary: AppColors.accentContrast,
        primaryContainer: AppColors.accentSoft,
        onPrimaryContainer: AppColors.accentOnSoft,
        secondary: AppColors.accent,
        surface: AppColors.surface1,
        onSurface: AppColors.textPrimary,
        error: AppColors.danger,
        onError: AppColors.dangerContrast,
      ),
      fontFamily: AppTextStyles.arabicFont,
      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.surface1,
        foregroundColor: AppColors.textPrimary,
        elevation: 0,
      ),
      cardTheme: CardThemeData(
        color: AppColors.surface1,
        shape: RoundedRectangleBorder(borderRadius: AppRadius.cardRadius),
      ),
    );
  }
}
