import 'package:flutter/material.dart';
import 'package:raje3_mobile/theme/app_theme.dart';

/// A "+N" badge that rises, springs slightly on entry, and fades — the instant-feedback moment
/// 2026 gamification research keeps coming back to (mindinventory.com: "the feedback loop must
/// be instantaneous to trigger the dopamine response"). Deliberately text, not a number that
/// counts up from zero — a counting animation reads right on a BALANCE screen (see
/// [AnimatedPointsCounter] below) where the viewer watches a total change; a single earn moment
/// reads right as one clear "+N" that appears and leaves, not a ticking clock.
class PointsFlyText extends StatefulWidget {
  final int amount;
  final VoidCallback? onDone;
  const PointsFlyText({super.key, required this.amount, this.onDone});

  @override
  State<PointsFlyText> createState() => _PointsFlyTextState();
}

class _PointsFlyTextState extends State<PointsFlyText> with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _rise;
  late final Animation<double> _scale;
  late final Animation<double> _fade;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(vsync: this, duration: const Duration(milliseconds: 1200));
    _rise = Tween<double>(begin: 0, end: -70)
        .animate(CurvedAnimation(parent: _controller, curve: const Interval(0.0, 1.0, curve: Curves.easeOutCubic)));
    // A SPRING OVERSHOOT ON ENTRY (elasticOut), never a flat linear scale-up — the exact "feels
    // alive, not mechanical" distinction the 2026 micro-interaction research draws.
    _scale = TweenSequence<double>([
      TweenSequenceItem(tween: Tween(begin: 0.4, end: 1.15).chain(CurveTween(curve: Curves.easeOutBack)), weight: 35),
      TweenSequenceItem(tween: Tween(begin: 1.15, end: 1.0), weight: 15),
      TweenSequenceItem(tween: ConstantTween(1.0), weight: 30),
      TweenSequenceItem(tween: Tween(begin: 1.0, end: 0.9), weight: 20),
    ]).animate(_controller);
    _fade = TweenSequence<double>([
      TweenSequenceItem(tween: ConstantTween(1.0), weight: 70),
      TweenSequenceItem(tween: Tween(begin: 1.0, end: 0.0), weight: 30),
    ]).animate(_controller);
    _controller.forward();
    _controller.addStatusListener((status) {
      if (status == AnimationStatus.completed) widget.onDone?.call();
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final dark = context.isDark;
    return IgnorePointer(
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, _) => Opacity(
          opacity: _fade.value,
          child: Transform.translate(
            offset: Offset(0, _rise.value),
            child: Transform.scale(
              scale: _scale.value,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.sm),
                decoration: BoxDecoration(
                  gradient: primaryGradient(dark: dark),
                  borderRadius: AppRadius.standardRadius,
                  boxShadow: dark ? AppShadows.darkButton : AppShadows.button,
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.stars_rounded, color: AppColors.accentContrast, size: 18),
                    const SizedBox(width: 4),
                    Text('+${widget.amount}',
                        style: AppTextStyles.button.copyWith(color: AppColors.accentContrast)),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// A points TOTAL that counts smoothly from its old value to its new one — the "balance just
/// changed" moment, distinct from [PointsFlyText]'s one-shot "+N" (see that widget's own doc
/// comment on when each is right). Spring-curved (`Curves.easeOutCubic`), never a linear tween.
class AnimatedPointsCounter extends StatelessWidget {
  final int value;
  final TextStyle? style;
  final Duration duration;
  const AnimatedPointsCounter({
    super.key,
    required this.value,
    this.style,
    this.duration = const Duration(milliseconds: 700),
  });

  @override
  Widget build(BuildContext context) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: value.toDouble()),
      duration: duration,
      curve: Curves.easeOutCubic,
      builder: (context, animatedValue, _) => Text(
        animatedValue.round().toString(),
        style: style ?? AppTextStyles.displaySmall,
      ),
    );
  }
}
