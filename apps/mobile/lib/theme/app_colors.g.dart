// GENERATED FILE — DO NOT EDIT BY HAND.
//
// Produced by scripts/gen_mobile_theme.py from:
//   - config/product.json (brand.accent.light/.dark)
//   - ui/packages/ui/src/theme/theme.config.ts (the `light` AND `dark` palettes)
//
// Re-run `python scripts/gen_mobile_theme.py` after either source changes.
// ci/check_mobile_theme_is_generated.py fails the build if this file drifts
// from what the generator would currently produce.

import 'package:flutter/material.dart';

/// Light-mode colour tokens sourced from Raje3's own web design system —
/// see the header of this file for exactly where each value comes from.
class AppColors {
  static const Color accent = Color(0xFF7C3AED);
  static const Color accentHover = Color(0xFF612DB9);
  static const Color accentSoft = Color(0xFFEFE7FD);
  static const Color accentOnSoft = Color(0xFF612DB9);
  static const Color accentContrast = Color(0xFFFFFFFF);

  // SURFACES
  static const Color surface0 = Color(0xFFFFFFFF);
  static const Color surface1 = Color(0xFFFFFFFF);
  static const Color surface2 = Color(0xFFF1F1F4);
  static const Color surface3 = Color(0xFFE4E4EA);

  // TEXT
  static const Color textPrimary = Color(0xFF17171F);
  static const Color textSecondary = Color(0xFF63636F);
  static const Color textMuted = Color(0xFF96969F);

  // BORDERS
  static const Color borderSubtle = Color(0xFFE9E9EE);
  static const Color borderStrong = Color(0xFFD3D3DC);

  // SUCCESS
  static const Color success = Color(0xFF12B886);
  static const Color successSoft = Color(0xFFDCF3EC);
  static const Color successOnSoft = Color(0xFF0E8A64);

  // WARNING
  static const Color warning = Color(0xFFF59F00);
  static const Color warningSoft = Color(0xFFF7ECD2);
  static const Color warningOnSoft = Color(0xFFA0680A);

  // DANGER
  static const Color danger = Color(0xFFE8590C);
  static const Color dangerSoft = Color(0xFFFBE1DD);
  static const Color dangerOnSoft = Color(0xFFB7412F);
  static const Color dangerContrast = Color(0xFFFFFFFF);

  // INFO
  static const Color info = Color(0xFF5A96DC);
  static const Color infoSoft = Color(0xFFE3EDFA);
  static const Color infoOnSoft = Color(0xFF2F5F8F);

  static const Color overlay = Color(0x73161328);

  // Convenience aliases matching common Material naming, so widgets that
  // expect AppColors.primary/error/white keep working.
  static const Color primary = accent;
  static const Color error = danger;
  static const Color white = Color(0xFFFFFFFF);
  static const Color black = Color(0xFF000000);
}

/// Dark-mode colour tokens — same source, the palette's own `dark` block.
/// `accent*` derived from `product.json`'s `brand.accent.dark` by the exact
/// `ACCENT_DARK` formula theme.config.ts itself uses (mix ratios kept in step).
class AppDarkColors {
  static const Color accent = Color(0xFFA78BFA);
  static const Color accentHover = Color(0xFFC0ABFB);
  static const Color accentSoft = Color(0xFF292747);
  static const Color accentOnSoft = Color(0xFFCAB9FC);
  static const Color accentContrast = Color(0xFF1C1440);

  // SURFACES
  static const Color surface0 = Color(0xFF120A24);
  static const Color surface1 = Color(0xFF1C1440);
  static const Color surface2 = Color(0xFF241C4D);
  static const Color surface3 = Color(0xFF2D235C);

  // TEXT
  static const Color textPrimary = Color(0xFFF6EFDD);
  static const Color textSecondary = Color(0xFFCFC6E8);
  static const Color textMuted = Color(0xFF9C93B8);

  // BORDERS
  static const Color borderSubtle = Color(0xFF322A58);
  static const Color borderStrong = Color(0xFF443A72);

  // SUCCESS
  static const Color success = Color(0xFF3DDBA8);
  static const Color successSoft = Color(0xFF0E3229);
  static const Color successOnSoft = Color(0xFF8FE9CD);

  // WARNING
  static const Color warning = Color(0xFFE8C469);
  static const Color warningSoft = Color(0xFF3A2D0E);
  static const Color warningOnSoft = Color(0xFFF5D98D);

  // DANGER
  static const Color danger = Color(0xFFFF9585);
  static const Color dangerSoft = Color(0xFF3A1F16);
  static const Color dangerOnSoft = Color(0xFFFFB49F);
  static const Color dangerContrast = Color(0xFF1C1440);

  // INFO
  static const Color info = Color(0xFF6FA8EA);
  static const Color infoSoft = Color(0xFF1C2F4A);
  static const Color infoOnSoft = Color(0xFFA9CDF2);

  static const Color overlay = Color(0x9E0A0614);

  // Convenience aliases matching common Material naming, so widgets that
  // expect AppColors.primary/error/white keep working.
  static const Color primary = accent;
  static const Color error = danger;
  static const Color white = Color(0xFFFFFFFF);
  static const Color black = Color(0xFF000000);
}
