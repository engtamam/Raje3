import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:raje3_mobile/widgets/premium/active_offer_banner.dart';

Widget _wrap(Widget child) => MaterialApp(home: Scaffold(body: child));

void main() {
  testWidgets('shows the offer text alone when there is no separate value', (tester) async {
    await tester.pumpWidget(_wrap(const ActiveOfferBanner(text: 'خصم الصيف')));
    expect(find.text('خصم الصيف'), findsOneWidget);
  });

  testWidgets('shows text and value together when both are real', (tester) async {
    await tester.pumpWidget(
        _wrap(const ActiveOfferBanner(text: 'خصم الصيف', value: '20%')));
    expect(find.text('خصم الصيف — 20%'), findsOneWidget);
  });

  testWidgets('an empty value never leaves a dangling "— " after the text', (tester) async {
    await tester.pumpWidget(_wrap(const ActiveOfferBanner(text: 'خصم الصيف', value: '')));
    expect(find.text('خصم الصيف'), findsOneWidget);
    expect(find.text('خصم الصيف — '), findsNothing);
  });
}
