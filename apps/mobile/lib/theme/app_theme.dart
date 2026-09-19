// Raje3 mobile theme.
//
// PATTERN ported from the reference project's `lib/theme/flutterflow_theme.dart`
// (a token-based AppColors/AppSpacing/AppTextStyles file) — the SHAPE only,
// not their colours. Every value below comes from THIS product's own design
// system instead: `ui/packages/ui/src/theme/theme.config.ts` (the web
// console's single source of truth for the whole brand) and
// `config/product.json`'s `brand.accent` (the one brand-owned colour, from
// which the console derives hover/soft/on-soft tints). Semantic colours
// (success/warning/danger/info) are copied from theme.config.ts's `light`
// palette so a status reads the same on web and mobile.
//
// Only the LIGHT palette is ported — the console's own theme.config.ts
// documents why light is not a default here but a requirement: "unreadable
// on a tablet in an open workshop at noon". Dark mode can be added later
// following the same token shape if the product ever needs it on mobile.

import 'package:flutter/material.dart';

/// ═══════════════════════════════════════════════════════════════════════════
/// COLORS — mirrors theme.config.ts's `Palette` interface (light appearance).
/// ═══════════════════════════════════════════════════════════════════════════
class AppColors {
  // ── BRAND ACCENT — config/product.json → brand.accent.light ─────────────
  // The ONE brand-owned colour; everything else here is the console's own
  // derived/semantic palette. A rebrand changes only this one line (plus
  // its console-side counterpart in product.json) — same contract as web.
  static const Color accent = Color(0xFF7C3AED);
  static const Color accentHover = Color(0xFF621EBD); // mix(accent, black, 0.22)
  static const Color accentSoft = Color(0xFFF1E9FC); // mix(accent, white, 0.88)
  static const Color accentOnSoft = Color(0xFF621EBD);
  static const Color accentContrast = Color(0xFFFFFFFF);

  // ── SURFACES — theme.config.ts `light` palette ──────────────────────────
  static const Color surface0 = Color(0xFFFFFFFF); // page background
  static const Color surface1 = Color(0xFFFFFFFF); // card
  static const Color surface2 = Color(0xFFF1F1F4); // chip off-state / unselected tab
  static const Color surface3 = Color(0xFFE4E4EA);

  // ── TEXT ──────────────────────────────────────────────────────────────
  static const Color textPrimary = Color(0xFF17171F);
  static const Color textSecondary = Color(0xFF63636F);
  static const Color textMuted = Color(0xFF96969F);

  // ── BORDERS ───────────────────────────────────────────────────────────
  static const Color borderSubtle = Color(0xFFE9E9EE);
  static const Color borderStrong = Color(0xFFD3D3DC);

  // ── SEMANTIC ──────────────────────────────────────────────────────────
  static const Color success = Color(0xFF12B886);
  static const Color successSoft = Color(0xFFDCF3EC);
  static const Color successOnSoft = Color(0xFF0E8A64);

  static const Color warning = Color(0xFFF59F00);
  static const Color warningSoft = Color(0xFFF7ECD2);
  static const Color warningOnSoft = Color(0xFFA0680A);

  // DANGER = coral (not brick-red) — matches the console's own churn/at-risk hue.
  static const Color danger = Color(0xFFE8590C);
  static const Color dangerSoft = Color(0xFFFBE1DD);
  static const Color dangerOnSoft = Color(0xFFB7412F);
  static const Color dangerContrast = Color(0xFFFFFFFF);

  static const Color info = Color(0xFF5A96DC);
  static const Color infoSoft = Color(0xFFE3EDFA);
  static const Color infoOnSoft = Color(0xFF2F5F8F);

  static const Color overlay = Color(0x73161328); // rgb(22 19 40 / 0.45)

  // Convenience aliases matching common Material naming, so widgets that
  // expect AppColors.primary/error/white (a common pattern) keep working.
  static const Color primary = accent;
  static const Color error = danger;
  static const Color white = Color(0xFFFFFFFF);
  static const Color black = Color(0xFF000000);
}

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
}

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
