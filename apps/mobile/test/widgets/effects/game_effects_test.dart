// Proves GameEffects is genuinely callable from anywhere with just a BuildContext — no Provider,
// no screen-specific plumbing — and that it cleans up after itself (no leaked OverlayEntry).
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:raje3_mobile/widgets/effects/game_effects.dart';
import 'package:raje3_mobile/widgets/effects/points_fly_text.dart';

void main() {
  Widget harness(void Function(BuildContext) onBuild) {
    return MaterialApp(
      home: Builder(
        builder: (context) {
          // Captured the instant this subtree builds — a plain screen BuildContext, no button
          // tap needed: the point being proven is that GameEffects works from ANY context, not
          // that a specific gesture wires up correctly.
          onBuild(context);
          return const Scaffold(body: SizedBox.shrink());
        },
      ),
    );
  }

  testWidgets('pointsEarned renders a "+N" badge above the screen from a plain BuildContext',
      (tester) async {
    late BuildContext ctx;
    await tester.pumpWidget(harness((c) => ctx = c));

    GameEffects.pointsEarned(ctx, amount: 42);
    await tester.pump();

    expect(find.text('+42'), findsOneWidget);
  });

  testWidgets('offerApplied never throws and never requires a points count', (tester) async {
    late BuildContext ctx;
    await tester.pumpWidget(harness((c) => ctx = c));

    expect(() => GameEffects.offerApplied(ctx), returnsNormally);
    await tester.pump();
    // No crash, no "+N" text (this path carries no amount).
    expect(find.textContaining('+'), findsNothing);
  });

  testWidgets('the overlay entry removes itself once the animation finishes — no leak',
      (tester) async {
    late BuildContext ctx;
    await tester.pumpWidget(harness((c) => ctx = c));

    GameEffects.pointsEarned(ctx, amount: 7);
    await tester.pump();
    expect(find.byType(PointsFlyText), findsOneWidget);

    // Past both effects' own real durations (1200ms text, 1100ms confetti).
    await tester.pump(const Duration(milliseconds: 1300));
    await tester.pump();

    expect(find.byType(PointsFlyText), findsNothing);
  });

  testWidgets('calling it twice in a row shows two independent effects, never crashes',
      (tester) async {
    late BuildContext ctx;
    await tester.pumpWidget(harness((c) => ctx = c));

    GameEffects.pointsEarned(ctx, amount: 5);
    await tester.pump();
    GameEffects.pointsEarned(ctx, amount: 10);
    await tester.pump();

    expect(find.text('+5'), findsOneWidget);
    expect(find.text('+10'), findsOneWidget);
  });
}
