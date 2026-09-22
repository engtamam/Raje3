import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:raje3_mobile/widgets/premium/loyalty_balance_card.dart';

Widget _wrap(Widget child) => MaterialApp(home: Scaffold(body: child));

void main() {
  testWidgets('shows the points balance, counted up to its real value', (tester) async {
    await tester.pumpWidget(_wrap(const LoyaltyBalanceCard(points: 120, toNextReward: 30)));
    await tester.pump(const Duration(milliseconds: 700));
    expect(find.text('120'), findsOneWidget);
  });

  testWidgets('shows a progress bar and "left to go" line when a reward is in reach', (tester) async {
    await tester.pumpWidget(_wrap(const LoyaltyBalanceCard(points: 120, toNextReward: 30)));
    await tester.pump(const Duration(milliseconds: 700));
    expect(find.byType(LinearProgressIndicator), findsOneWidget);
    expect(find.textContaining('30'), findsWidgets);
  });

  testWidgets('no progress bar at all when nothing is left to reach — never a zero-width bar',
      (tester) async {
    await tester.pumpWidget(_wrap(const LoyaltyBalanceCard(points: 500, toNextReward: 0)));
    await tester.pump(const Duration(milliseconds: 700));
    expect(find.byType(LinearProgressIndicator), findsNothing);
  });

  testWidgets('shows up to two reward chips, never more', (tester) async {
    await tester.pumpWidget(_wrap(const LoyaltyBalanceCard(
      points: 500,
      toNextReward: 0,
      rewards: [
        {'id': 'r1', 'name': 'غسلة مجانية', 'cost': 100},
        {'id': 'r2', 'name': 'تلميع', 'cost': 200},
        {'id': 'r3', 'name': 'تعطير', 'cost': 300},
      ],
    )));
    await tester.pump(const Duration(milliseconds: 700));
    expect(find.text('غسلة مجانية'), findsOneWidget);
    expect(find.text('تلميع'), findsOneWidget);
    expect(find.text('تعطير'), findsNothing);
  });

  testWidgets('renders with zero points and no rewards without throwing', (tester) async {
    await tester.pumpWidget(_wrap(const LoyaltyBalanceCard(points: 0, toNextReward: 0)));
    await tester.pump(const Duration(milliseconds: 700));
    expect(find.text('0'), findsOneWidget);
  });
}
