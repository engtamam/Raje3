import 'package:flutter/material.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/theme/app_theme.dart';

/// THE PAGE-LEVEL LOADING STATE IS OUR OWN WORDMARK, NEVER A GENERIC SPINNER (owner's own
/// instruction, 2026-09-22) — the same "راجِع, set in type, IS the logo" treatment
/// `login_screen.dart`'s own `_buildLogo()` already established (no icon, no box, no glyph — see
/// apps/console/src/brand/Mark.tsx's own note), reused here as a gentle pulse instead of the
/// entrance scale-in that screen uses, since this widget appears and disappears repeatedly rather
/// than once per app launch.
///
/// FOR A SCREEN-LEVEL WAIT, NOT AN INLINE BUSY STATE — a tiny 18px spinner inside a button (a
/// save action already in flight) stays a small circular indicator: the wordmark cannot read at
/// that size, and the established pattern there is universal already. This widget is for the
/// "still loading the whole section" moment a full-screen or full-card centered spinner used to
/// own — a mobile-native list assembling itself from several small loaders now shows exactly one.
class BrandLoadingIndicator extends StatefulWidget {
  const BrandLoadingIndicator({super.key});

  @override
  State<BrandLoadingIndicator> createState() => _BrandLoadingIndicatorState();
}

class _BrandLoadingIndicatorState extends State<BrandLoadingIndicator>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(vsync: this, duration: const Duration(milliseconds: 1100))
      ..repeat(reverse: true);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final accent = context.isDark ? AppDarkColors.accent : AppColors.accent;
    return Center(
      child: FadeTransition(
        opacity: Tween(begin: 0.35, end: 1.0).animate(
          CurvedAnimation(parent: _controller, curve: Curves.easeInOut),
        ),
        child: Text(
          S.of(context)!.appName,
          style: TextStyle(
            fontFamily: AppTextStyles.arabicFont,
            fontWeight: FontWeight.w800,
            fontSize: 28,
            color: accent,
            height: 1,
          ),
        ),
      ),
    );
  }
}
