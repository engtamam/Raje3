import 'package:flutter/material.dart';
import 'package:raje3_mobile/theme/app_theme.dart';

/// Which semantic tone each app's tile reads in — the SAME real per-app tone
/// `apps/console/src/apps.ts` already assigns (`icon`/`tone` fields, keyed by that file's own
/// `section`, which matches this file's own [NavSectionDef.id] one for one: 'messages',
/// 'points', 'bookings', 'customers'→'contacts', 'rating', 'coupons', 'mobile-requests',
/// 'visit'→'feature.visit'). Reused here as real product data, not invented for this screen —
/// every app already wears this color identity on the web console; this keeps the two products'
/// visual language consistent instead of each screen inventing its own.
///
/// A tile with no distinct tone assigned below (an id apps.ts itself has no matching entry for,
/// e.g. 'shop'/'services'/'support' — bundled/internal sections with no single feature card of
/// their own) falls back to the brand accent, same as any semantic-tone system's own default.
enum AppTone { accent, success, warning, danger, info }

const Map<String, AppTone> _toneById = {
  'visit': AppTone.success,
  'bookings': AppTone.accent,
  'customers': AppTone.accent,
  'rating': AppTone.warning,
  'coupons': AppTone.danger,
  'mobile-requests': AppTone.warning,
  'messages': AppTone.danger,
  'points': AppTone.warning,
  'shop': AppTone.info,
  'services': AppTone.accent,
  'support': AppTone.info,
};

AppTone toneForSection(String id) => _toneById[id] ?? AppTone.accent;

/// The tone's own solid/soft/on-soft triad — same naming AppColors already uses per tone, just
/// resolved from the enum in one place instead of a switch repeated at every call site.
class ToneColors {
  final Color solid;
  final Color soft;
  final Color onSoft;
  const ToneColors({required this.solid, required this.soft, required this.onSoft});

  factory ToneColors.of(BuildContext context, AppTone tone) {
    final dark = context.isDark;
    switch (tone) {
      case AppTone.accent:
        return ToneColors(
          solid: dark ? AppDarkColors.accent : AppColors.accent,
          soft: dark ? AppDarkColors.accentSoft : AppColors.accentSoft,
          onSoft: dark ? AppDarkColors.accentHover : AppColors.accentHover,
        );
      case AppTone.success:
        return ToneColors(
          solid: dark ? AppDarkColors.success : AppColors.success,
          soft: dark ? AppDarkColors.successSoft : AppColors.successSoft,
          onSoft: dark ? AppDarkColors.successOnSoft : AppColors.successOnSoft,
        );
      case AppTone.warning:
        return ToneColors(
          solid: dark ? AppDarkColors.warning : AppColors.warning,
          soft: dark ? AppDarkColors.warningSoft : AppColors.warningSoft,
          onSoft: dark ? AppDarkColors.warningOnSoft : AppColors.warningOnSoft,
        );
      case AppTone.danger:
        return ToneColors(
          solid: dark ? AppDarkColors.danger : AppColors.danger,
          soft: dark ? AppDarkColors.dangerSoft : AppColors.dangerSoft,
          onSoft: dark ? AppDarkColors.dangerOnSoft : AppColors.dangerOnSoft,
        );
      case AppTone.info:
        return ToneColors(
          solid: dark ? AppDarkColors.info : AppColors.info,
          soft: (dark ? AppDarkColors.info : AppColors.info).withValues(alpha: 0.14),
          onSoft: dark ? AppDarkColors.info : AppColors.info,
        );
    }
  }
}

/// Button colour by WHAT THE ACTION DOES, never the app's single flat brand colour — the same
/// gap `ThemeData` itself never closes (no `OutlinedButtonThemeData`/`TextButtonThemeData`/
/// `ElevatedButtonThemeData` is set anywhere in `app_theme.dart`, so every button app-wide falls
/// back to one identical `colorScheme.primary`; found live, the owner's own catch, 2026-09-22:
/// "إيقاف الاشتراك" and "جدّد الآن" — a stop and a positive continue — rendered as the exact same
/// colour). Reuses the SAME [ToneColors] triad the icon chips/status badges already wear, so a
/// destructive control and its own status badge always agree — never invented per screen.
extension ToneButtonStyles on ToneColors {
  /// An outlined control — «إيقاف»/«تراجع»-shaped secondary actions.
  ButtonStyle outlinedStyle() => OutlinedButton.styleFrom(
        foregroundColor: solid,
        side: BorderSide(color: solid.withValues(alpha: 0.45)),
      );

  /// A text-only control — the lighter-weight sibling action beside an outlined one.
  ButtonStyle textStyle() => TextButton.styleFrom(foregroundColor: solid);

  /// A filled control — the single primary action on a card (e.g. «ادفع الآن»).
  ButtonStyle filledStyle() => ElevatedButton.styleFrom(
        backgroundColor: solid,
        foregroundColor: Colors.white,
      );
}
