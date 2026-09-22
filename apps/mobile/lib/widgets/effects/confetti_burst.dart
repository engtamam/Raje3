import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:raje3_mobile/theme/app_theme.dart';

/// A short, physics-driven particle burst — the "you won something" moment. Deliberately NOT
/// the `confetti` pub.dev package: a hand-rolled `CustomPainter` keeps this on our own theme
/// tokens (accent/success/warning, never an unbranded rainbow) and costs one small file instead
/// of a new pinned dependency for something this self-contained.
///
/// SPRING-FELT, NOT LINEAR — every particle's fall uses a quadratic ease (gravity), never a
/// straight `Curves.linear` interpolation; real 2026 UX research on reward micro-interactions
/// (mindinventory.com, 60fps.design gamification pattern library) is consistent on this: a
/// linear-feeling burst reads as mechanical, a gravity-felt one reads as a real celebration.
class ConfettiBurst extends StatefulWidget {
  final VoidCallback? onDone;
  const ConfettiBurst({super.key, this.onDone});

  @override
  State<ConfettiBurst> createState() => _ConfettiBurstState();
}

class _Particle {
  final double startX; // 0..1, fraction of width
  final double angle; // radians, launch direction
  final double speed; // fraction-of-height per second
  final double spin;
  final Color color;
  final double size;

  _Particle({
    required this.startX,
    required this.angle,
    required this.speed,
    required this.spin,
    required this.color,
    required this.size,
  });
}

class _ConfettiBurstState extends State<ConfettiBurst> with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final List<_Particle> _particles;

  static const _colors = [
    AppColors.accent,
    AppColors.success,
    AppColors.warning,
    AppColors.info,
    AppColors.danger,
  ];

  @override
  void initState() {
    super.initState();
    final rand = math.Random();
    _particles = List.generate(26, (_) {
      return _Particle(
        startX: 0.3 + rand.nextDouble() * 0.4,
        angle: -math.pi / 2 + (rand.nextDouble() - 0.5) * math.pi * 0.9,
        speed: 0.35 + rand.nextDouble() * 0.25,
        spin: (rand.nextDouble() - 0.5) * 10,
        color: _colors[rand.nextInt(_colors.length)],
        size: 6 + rand.nextDouble() * 5,
      );
    });
    _controller = AnimationController(vsync: this, duration: const Duration(milliseconds: 1100))
      ..forward();
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
    return IgnorePointer(
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, _) => CustomPaint(
          painter: _ConfettiPainter(particles: _particles, t: _controller.value),
          size: Size.infinite,
        ),
      ),
    );
  }
}

class _ConfettiPainter extends CustomPainter {
  final List<_Particle> particles;
  final double t;
  _ConfettiPainter({required this.particles, required this.t});

  @override
  void paint(Canvas canvas, Size size) {
    for (final p in particles) {
      // Gravity-felt fall: position eases out on the way up, accelerates on the way down —
      // a plain `t * t` fall factor mixed with the launch direction, not a straight line.
      final dx = p.startX * size.width + math.cos(p.angle) * p.speed * size.height * t;
      final dy = math.sin(p.angle) * p.speed * size.height * t + 0.5 * t * t * size.height * 0.9;
      final opacity = (1 - t).clamp(0.0, 1.0);
      if (dy > size.height || opacity <= 0) continue;
      final paint = Paint()..color = p.color.withValues(alpha: opacity);
      canvas.save();
      canvas.translate(dx, dy);
      canvas.rotate(p.spin * t);
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromCenter(center: Offset.zero, width: p.size, height: p.size * 0.6),
          const Radius.circular(2),
        ),
        paint,
      );
      canvas.restore();
    }
  }

  @override
  bool shouldRepaint(covariant _ConfettiPainter oldDelegate) => oldDelegate.t != t;
}
