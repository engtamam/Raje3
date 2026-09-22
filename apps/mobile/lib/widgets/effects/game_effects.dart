import 'package:flutter/material.dart';
import 'package:raje3_mobile/widgets/effects/confetti_burst.dart';
import 'package:raje3_mobile/widgets/effects/points_fly_text.dart';

/// THE ONE CALLABLE-FROM-ANYWHERE ENTRY POINT for every celebratory effect in this app — the
/// infrastructure the owner asked for: "نبغ نسويها بنية تحتية ومكونات وحركات نقدر نناديها من اي
/// مكان" (one piece of infrastructure, callable from anywhere). A screen that earns a customer
/// points, applies an offer, or hands out a gift calls exactly one of these three static methods
/// with a [BuildContext] — it never builds [ConfettiBurst]/[PointsFlyText] itself, and never
/// needs its own [Overlay] plumbing.
///
/// WHY AN [Overlay] ENTRY, NOT A WIDGET IN THE SCREEN'S OWN TREE. An effect must render ABOVE
/// everything (app bar, bottom nav, any dialog already open) and must outlive whatever
/// micro-interaction triggered it (a button's own `onPressed` returns immediately; the effect
/// keeps animating after). [Overlay.of(context)] is the one surface in Flutter that is both
/// already part of every real screen (`MaterialApp`/`Navigator` install one) and sits above the
/// whole route stack — the same mechanism [SnackBar]/[Tooltip] themselves are built on.
///
/// EVERY EFFECT REMOVES ITSELF WHEN DONE. Nothing here leaks an [OverlayEntry] — each widget's
/// own `onDone` callback (see [ConfettiBurst]/[PointsFlyText]) is exactly this class's own
/// `entry.remove()`, so a screen that fires ten effects in a row never accumulates ten
/// still-mounted overlays.
///
/// GROUNDED IN REAL 2026 GAMIFICATION UX RESEARCH, not invented: instantaneous feedback
/// (mindinventory.com's own "the feedback loop must be instantaneous to trigger the dopamine
/// response"), spring/physics-felt motion rather than linear tweens (60fps.design's own
/// gamification pattern library, techqware.com's own 2026 motion-design note), and restraint —
/// "meaningful progress, not volume" (mindinventory.com again) is why this stays THREE effects,
/// not a library of twenty.
class GameEffects {
  GameEffects._();

  /// A customer just earned points — confetti plus a rising "+N" badge, centred on the screen.
  static void pointsEarned(BuildContext context, {required int amount}) {
    _showCentered(context, (onDone) => _Combined(onDone: onDone, amount: amount));
  }

  /// An offer/gift/coupon was just applied to a visit — the same celebratory language as
  /// [pointsEarned], without a number (an offer has no "+N" to show).
  static void offerApplied(BuildContext context) {
    _showCentered(context, (onDone) => ConfettiBurst(onDone: onDone));
  }

  /// The generic form — any other "something good just happened" moment a future screen needs,
  /// with no points count attached. Kept separate from [offerApplied] only in NAME, so a call
  /// site reads as what it means; both render identically today.
  static void celebrate(BuildContext context) {
    _showCentered(context, (onDone) => ConfettiBurst(onDone: onDone));
  }

  static void _showCentered(BuildContext context, Widget Function(VoidCallback onDone) builder) {
    final overlay = Overlay.maybeOf(context, rootOverlay: true);
    if (overlay == null) return; // no Overlay yet (e.g. a widget test with no MaterialApp) — never crash
    late final OverlayEntry entry;
    entry = OverlayEntry(
      builder: (context) => Positioned.fill(
        child: Center(child: builder(() => entry.remove())),
      ),
    );
    overlay.insert(entry);
  }
}

class _Combined extends StatefulWidget {
  final VoidCallback onDone;
  final int amount;
  const _Combined({required this.onDone, required this.amount});

  @override
  State<_Combined> createState() => _CombinedState();
}

class _CombinedState extends State<_Combined> {
  bool _confettiDone = false;
  bool _textDone = false;

  void _checkDone() {
    if (_confettiDone && _textDone) widget.onDone();
  }

  @override
  Widget build(BuildContext context) {
    return Stack(
      alignment: Alignment.center,
      children: [
        ConfettiBurst(onDone: () {
          _confettiDone = true;
          _checkDone();
        }),
        PointsFlyText(
          amount: widget.amount,
          onDone: () {
            _textDone = true;
            _checkDone();
          },
        ),
      ],
    );
  }
}
