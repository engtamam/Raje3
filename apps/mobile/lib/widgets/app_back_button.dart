import 'package:flutter/material.dart';
import 'package:raje3_mobile/theme/app_theme.dart';

/// A back button that actually reads as "go back", not a bare directionless chevron in dead
/// space — a soft circular chip (the same "tone-washed icon chip" language `account_screen.dart`'s
/// own `_Row` and `_BranchRow` already established) instead of a plain `IconButton`, matching the
/// rest of the app's own premium visual language.
///
/// DIRECTION VERIFIED LIVE — the `_ios_`-variant chevrons (`arrow_back_ios_new_rounded`,
/// `arrow_forward_ios_rounded`) render UNRELIABLY in this web build regardless of which literal
/// constant the code names (found live: switching between the two produced no visible change at
/// all, both a fresh cache-busted load away from any staleness). Switched to
/// `chevron_left_rounded`/`chevron_right_rounded` instead.
///
/// RE-VERIFIED LIVE AGAIN, 2026-09-22 — the owner's own catch, a zoomed screenshot on «الفوترة»'s
/// own AppBar leading slot: with the assignment this file HAD (`rtl → chevron_right_rounded`),
/// the glyph actually drawn was unambiguously "‹" (LEFT), the wrong direction for a back button in
/// RTL. `Directionality.of(context)` inside `AppBar.leading`'s own slot reads differently than it
/// does at an ordinary body-level `Icon` (`account_screen.dart`'s own `_Row` trailing chevron,
/// confirmed correct there) — never fully explained, but re-verified by direct swap-and-screenshot
/// exactly like the `_ios_` finding above: swapping the two assignments below is what actually
/// produces "›" (RIGHT) for RTL now. `ci/check_mobile_no_broken_directional_icons.py` only checks
/// that a chevron pair exists together, never which one names which literal, so it stays green
/// through this swap — the swap IS the fix, not a workaround the gate should catch.
class AppBackButton extends StatelessWidget {
  final VoidCallback onPressed;
  const AppBackButton({super.key, required this.onPressed});

  @override
  Widget build(BuildContext context) {
    final dark = context.isDark;
    final surface = dark ? AppDarkColors.surface2 : AppColors.surface2;
    final ink = dark ? AppDarkColors.textPrimary : AppColors.textPrimary;

    return Padding(
      padding: const EdgeInsets.all(AppSpacing.xs),
      child: Material(
        color: surface,
        shape: const CircleBorder(),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onPressed,
          child: SizedBox(
            width: 40,
            height: 40,
            child: Icon(
              Directionality.of(context) == TextDirection.rtl
                  ? Icons.chevron_left_rounded
                  : Icons.chevron_right_rounded,
              size: 22,
              color: ink,
            ),
          ),
        ),
      ),
    );
  }
}
