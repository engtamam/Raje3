// Raje3 mobile theme.
//
// PATTERN ported from the reference project's `lib/theme/flutterflow_theme.dart`
// (a token-based AppColors/AppSpacing/AppTextStyles file) — the SHAPE only,
// not their colours.
//
// COLORS ARE GENERATED, NOT HAND-COPIED. `AppColors`/`AppDarkColors` used to
// be typed out here as literal `Color(0xFF...)` values, copied once from
// theme.config.ts and product.json — exactly the drift class
// ci/check_a_hardcoded_color_does_not_shadow_a_token.py already exists to
// catch on the web side. Both now live in `app_colors.g.dart`, produced by
// `scripts/gen_mobile_theme.py` from THIS product's own design system:
// `ui/packages/ui/src/theme/theme.config.ts` (the web console's single
// source of truth for the whole brand, `light` AND `dark` palettes) and
// `config/product.json`'s `brand.accent.light`/`.dark` (the one brand-owned
// colour per mode, from which hover/soft/on-soft tints are derived — same
// `mix()` formula theme.config.ts itself uses). After either source
// changes, re-run that script; `ci/check_mobile_theme_is_generated.py`
// fails the build if the checked-in file and the script's current output
// ever disagree.
//
// LIGHT DEFAULTS, DARK AVAILABLE — the console's own theme.config.ts
// documents why light is the requirement, not merely the default:
// "unreadable on a tablet in an open workshop at noon". `ThemeProvider`
// persists the shop's own choice; `AppTheme.light`/`.dark` below are what it
// switches between.

import 'package:flutter/cupertino.dart' show CupertinoPageTransitionsBuilder;
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
  // with a lighter body face (Tajawal). These names resolve to the real
  // Google Fonts typefaces because main.dart's GoogleFonts.cairo()/.inter()
  // calls register them globally at startup — same fonts, same weights, as
  // apps/console/index.html's own fonts.googleapis.com link.
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
/// SHADOWS — one place, so `AppCard`/`AppCardDecorations` and any future
/// surface never hand-tune a second `BoxShadow` that quietly drifts from it.
/// ═══════════════════════════════════════════════════════════════════════════
class AppShadows {
  static List<BoxShadow> get card => [
        BoxShadow(
          color: AppColors.textPrimary.withValues(alpha: 0.06),
          blurRadius: 24,
          offset: const Offset(0, 8),
        ),
      ];

  /// Dark-mode card shadow uses the DARK palette's own lighter accent tint —
  /// a light-mode shadow colour reads as nearly invisible on a dark surface.
  static List<BoxShadow> get darkCard => [
        BoxShadow(
          color: AppDarkColors.accent.withValues(alpha: 0.20),
          blurRadius: 24,
          offset: const Offset(0, 8),
        ),
      ];

  static List<BoxShadow> get button => [
        BoxShadow(
          color: AppColors.accent.withValues(alpha: 0.24),
          blurRadius: 16,
          offset: const Offset(0, 6),
        ),
      ];

  static List<BoxShadow> get darkButton => [
        BoxShadow(
          color: AppDarkColors.accent.withValues(alpha: 0.30),
          blurRadius: 16,
          offset: const Offset(0, 6),
        ),
      ];
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
        boxShadow: AppShadows.card,
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

/// One brand gradient — light or dark, so a widget asks for the gradient
/// that matches the surface it is drawn on rather than assuming light.
LinearGradient primaryGradient({bool dark = false}) => LinearGradient(
      colors: dark
          ? [AppDarkColors.accent, AppDarkColors.accentHover]
          : [AppColors.accent, AppColors.accentHover],
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
    );

/// Kept for existing call sites written before dark mode existed — always
/// the light gradient. New code should call `primaryGradient(dark: ...)`.
LinearGradient get appPrimaryGradient => primaryGradient();

/// ═══════════════════════════════════════════════════════════════════════════
/// THEME EXTENSION — the fields `app_widgets.dart`'s shared components read
/// through `context.appColors`, so a component never chooses between
/// `AppColors`/`AppDarkColors` itself; `Theme.of(context)` already resolved
/// that the moment the app switched modes.
/// ═══════════════════════════════════════════════════════════════════════════
class AppThemeColors extends ThemeExtension<AppThemeColors> {
  const AppThemeColors({
    required this.surface,
    required this.surfaceAlt,
    required this.textPrimary,
    required this.textSecondary,
    required this.textMuted,
    required this.borderSubtle,
    required this.inputFill,
    required this.inputFillDisabled,
  });

  final Color surface;
  final Color surfaceAlt;
  final Color textPrimary;
  final Color textSecondary;
  final Color textMuted;
  final Color borderSubtle;
  final Color inputFill;
  final Color inputFillDisabled;

  static const light = AppThemeColors(
    surface: AppColors.surface1,
    surfaceAlt: AppColors.surface2,
    textPrimary: AppColors.textPrimary,
    textSecondary: AppColors.textSecondary,
    textMuted: AppColors.textMuted,
    borderSubtle: AppColors.borderSubtle,
    inputFill: AppColors.surface2,
    inputFillDisabled: AppColors.surface3,
  );

  static const dark = AppThemeColors(
    surface: AppDarkColors.surface1,
    surfaceAlt: AppDarkColors.surface2,
    textPrimary: AppDarkColors.textPrimary,
    textSecondary: AppDarkColors.textSecondary,
    textMuted: AppDarkColors.textMuted,
    borderSubtle: AppDarkColors.borderSubtle,
    inputFill: AppDarkColors.surface2,
    inputFillDisabled: AppDarkColors.surface3,
  );

  @override
  AppThemeColors copyWith({
    Color? surface,
    Color? surfaceAlt,
    Color? textPrimary,
    Color? textSecondary,
    Color? textMuted,
    Color? borderSubtle,
    Color? inputFill,
    Color? inputFillDisabled,
  }) {
    return AppThemeColors(
      surface: surface ?? this.surface,
      surfaceAlt: surfaceAlt ?? this.surfaceAlt,
      textPrimary: textPrimary ?? this.textPrimary,
      textSecondary: textSecondary ?? this.textSecondary,
      textMuted: textMuted ?? this.textMuted,
      borderSubtle: borderSubtle ?? this.borderSubtle,
      inputFill: inputFill ?? this.inputFill,
      inputFillDisabled: inputFillDisabled ?? this.inputFillDisabled,
    );
  }

  @override
  AppThemeColors lerp(ThemeExtension<AppThemeColors>? other, double t) {
    if (other is! AppThemeColors) return this;
    return AppThemeColors(
      surface: Color.lerp(surface, other.surface, t)!,
      surfaceAlt: Color.lerp(surfaceAlt, other.surfaceAlt, t)!,
      textPrimary: Color.lerp(textPrimary, other.textPrimary, t)!,
      textSecondary: Color.lerp(textSecondary, other.textSecondary, t)!,
      textMuted: Color.lerp(textMuted, other.textMuted, t)!,
      borderSubtle: Color.lerp(borderSubtle, other.borderSubtle, t)!,
      inputFill: Color.lerp(inputFill, other.inputFill, t)!,
      inputFillDisabled: Color.lerp(inputFillDisabled, other.inputFillDisabled, t)!,
    );
  }
}

/// Every screen/widget reads mode-aware colours through these three getters
/// instead of importing `ThemeProvider` directly — `Theme.of(context)`
/// already carries the answer once `AppTheme.light`/`.dark` are wired to
/// `MaterialApp.theme`/`darkTheme`/`themeMode`.
extension ContextExtension on BuildContext {
  ThemeData get appTheme => Theme.of(this);
  ColorScheme get colorScheme => Theme.of(this).colorScheme;
  bool get isDark => Theme.of(this).brightness == Brightness.dark;

  /// Context-aware colour set — switches between light and dark automatically.
  AppThemeColors get appColors =>
      Theme.of(this).extension<AppThemeColors>() ?? AppThemeColors.light;
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
      inputDecorationTheme: _inputDecorationTheme(
        fill: AppColors.surface2,
        border: AppColors.borderSubtle,
        accent: AppColors.accent,
        danger: AppColors.danger,
        textSecondary: AppColors.textSecondary,
        textMuted: AppColors.textMuted,
      ),
      pageTransitionsTheme: _swipeBackPageTransitions,
      extensions: const [AppThemeColors.light],
    );
  }

  static ThemeData get dark {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: AppDarkColors.surface0,
      colorScheme: const ColorScheme.dark(
        primary: AppDarkColors.accent,
        onPrimary: AppDarkColors.accentContrast,
        primaryContainer: AppDarkColors.accentSoft,
        onPrimaryContainer: AppDarkColors.accentOnSoft,
        secondary: AppDarkColors.accent,
        surface: AppDarkColors.surface1,
        onSurface: AppDarkColors.textPrimary,
        error: AppDarkColors.danger,
        onError: AppDarkColors.dangerContrast,
      ),
      fontFamily: AppTextStyles.arabicFont,
      appBarTheme: const AppBarTheme(
        backgroundColor: AppDarkColors.surface1,
        foregroundColor: AppDarkColors.textPrimary,
        elevation: 0,
      ),
      cardTheme: CardThemeData(
        color: AppDarkColors.surface1,
        shape: RoundedRectangleBorder(borderRadius: AppRadius.cardRadius),
      ),
      inputDecorationTheme: _inputDecorationTheme(
        fill: AppDarkColors.surface2,
        border: AppDarkColors.borderSubtle,
        accent: AppDarkColors.accent,
        danger: AppDarkColors.danger,
        textSecondary: AppDarkColors.textSecondary,
        textMuted: AppDarkColors.textMuted,
      ),
      pageTransitionsTheme: _swipeBackPageTransitions,
      extensions: const [AppThemeColors.dark],
    );
  }

  /// EDGE SWIPE-TO-GO-BACK, ON EVERY PLATFORM — never just a tap on [AppBackButton] (the owner's
  /// own request, 2026-09-22: "يعني مو لازم يضغط على الازرار يقدر يسحب للرجوع"). Flutter's own
  /// default `PageTransitionsTheme` already gives this for free on real iOS (the framework's own
  /// `CupertinoPageTransitionsBuilder` handles the gesture, RTL mirroring, and conflicts with a
  /// horizontally-scrollable child — none of that is hand-rolled here); the gap is Android, whose
  /// default `ZoomPageTransitionsBuilder` carries no in-app swipe gesture at all — a phone without
  /// the OS-level gesture-nav bar (older Android, some OEM skins) would have NO swipe-back
  /// whatsoever. Forcing the Cupertino builder for every platform closes that gap the same way —
  /// reusing Flutter's own tested implementation, never a custom `Dismissible`/`DragGesture`
  /// re-implementation that would have to re-solve RTL and scroll-conflict handling itself.
  static const PageTransitionsTheme _swipeBackPageTransitions = PageTransitionsTheme(
    builders: <TargetPlatform, PageTransitionsBuilder>{
      TargetPlatform.android: CupertinoPageTransitionsBuilder(),
      TargetPlatform.iOS: CupertinoPageTransitionsBuilder(),
      TargetPlatform.fuchsia: CupertinoPageTransitionsBuilder(),
      TargetPlatform.linux: CupertinoPageTransitionsBuilder(),
      TargetPlatform.macOS: CupertinoPageTransitionsBuilder(),
      TargetPlatform.windows: CupertinoPageTransitionsBuilder(),
    },
  );

  /// EVERY TEXT FIELD IN THE APP, ONE PLACE — found live (the owner's own words): almost every
  /// screen built a bare `InputDecoration(isDense: true, hintText: ...)` with no border/fill of
  /// its own, so Flutter's raw Material default (a plain grey underline) is what actually shipped
  /// everywhere except the two screens (`login_screen.dart`/`signup_screen.dart`) that happened to
  /// apply [AppInputDecorations.standard] by hand. Setting `ThemeData.inputDecorationTheme` once
  /// here upgrades every field across the whole app at once — the SAME reasoning
  /// `AppInputDecorations.standard` already existed for, just applied at the one layer that
  /// actually reaches every call site instead of the ones a screen remembered to opt into.
  /// Craft pattern (tonal resting border, a real width-2 focus ring, a distinct error state)
  /// ported from the reference project's own `app_theme_data.dart` — its shape, our tokens.
  static InputDecorationTheme _inputDecorationTheme({
    required Color fill,
    required Color border,
    required Color accent,
    required Color danger,
    required Color textSecondary,
    required Color textMuted,
  }) {
    OutlineInputBorder side(Color color, {double width = 1}) => OutlineInputBorder(
          borderRadius: AppRadius.standardRadius,
          borderSide: BorderSide(color: color, width: width),
        );
    return InputDecorationTheme(
      filled: true,
      fillColor: fill,
      contentPadding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: AppSpacing.md,
      ),
      border: side(border),
      enabledBorder: side(border),
      focusedBorder: side(accent, width: 1.5),
      errorBorder: side(danger),
      focusedErrorBorder: side(danger, width: 1.5),
      disabledBorder: side(border.withValues(alpha: 0.5)),
      labelStyle: AppTextStyles.bodyMedium.copyWith(color: textSecondary),
      hintStyle: AppTextStyles.bodyMedium.copyWith(color: textMuted),
      errorStyle: AppTextStyles.caption.copyWith(color: danger),
      prefixIconColor: accent,
      suffixIconColor: textSecondary,
    );
  }
}
