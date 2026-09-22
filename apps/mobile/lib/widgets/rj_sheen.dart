import 'package:flutter/material.dart';
import 'package:raje3_mobile/theme/app_theme.dart';

/// A diagonal, animated light sweep over [child] — the Flutter port of
/// `apps/console/src/index.css`'s own `.rj-sheen` (the owner's own general-purpose gloss
/// primitive, confirmed 2026-09-22: "ما ابغ شي باهت كلها لازم تكون لميعه" / "الوان لميعه تعطي
/// لمعه ... تحسسك بمرايا" — a mirror-like reflection, not a flat fill). Composes ON TOP of
/// whatever palette the wrapped surface already has (light or dark, any tone) — never overrides
/// tokens the way the console's old `.rj-gold-card` did before `.rj-sheen` was generalised out of
/// it; this widget is that same generalised primitive, not the gold-only original.
///
/// Same numbers as the CSS original: a 115°-equivalent diagonal band, transparent → accent-tinted
/// highlight (~22% alpha) → transparent, sweeping once every 6 seconds, easing in/out
/// (`Curves.easeInOut`), disabled entirely when the platform asks for reduced motion
/// (`MediaQuery.disableAnimations` — the CSS original's own `prefers-reduced-motion` guard).
class RjSheen extends StatefulWidget {
  final Widget child;
  final BorderRadius? borderRadius;
  final Color? tint;
  final Duration duration;

  const RjSheen({
    super.key,
    required this.child,
    this.borderRadius,
    this.tint,
    this.duration = const Duration(seconds: 6),
  });

  @override
  State<RjSheen> createState() => _RjSheenState();
}

class _RjSheenState extends State<RjSheen> with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(vsync: this, duration: widget.duration)..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final reduceMotion = MediaQuery.of(context).disableAnimations;
    final dark = context.isDark;
    final tint = widget.tint ?? (dark ? AppDarkColors.accent : AppColors.accent);

    return ClipRRect(
      borderRadius: widget.borderRadius ?? BorderRadius.zero,
      child: Stack(
        children: [
          widget.child,
          if (!reduceMotion)
            Positioned.fill(
              child: IgnorePointer(
                child: AnimatedBuilder(
                  animation: _controller,
                  builder: (context, _) {
                    // 200% -> -80% background-position over the cycle, same sweep shape the CSS
                    // keyframes describe, expressed as a moving gradient center instead.
                    final t = Curves.easeInOut.transform(_controller.value);
                    final sweep = 2.0 - (2.8 * t);
                    return DecoratedBox(
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          begin: Alignment(-1 + sweep, -1),
                          end: Alignment(1 + sweep, 1),
                          colors: [
                            Colors.transparent,
                            tint.withValues(alpha: 0.22),
                            Colors.transparent,
                          ],
                          stops: const [0.35, 0.48, 0.62],
                        ),
                      ),
                    );
                  },
                ),
              ),
            ),
        ],
      ),
    );
  }
}
