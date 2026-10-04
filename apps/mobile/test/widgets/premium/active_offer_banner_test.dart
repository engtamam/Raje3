import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:raje3_mobile/widgets/premium/active_offer_banner.dart';

Widget _wrap(Widget child) => MaterialApp(home: Scaffold(body: child));

void main() {
  // `text` IS THE WHOLE SENTENCE NOW (2026-10-05) — each source (campaign/referral/mutual-benefit)
  // composes its own complete Arabic sentence server-side, already stating its own amount; there
  // is no separate `value` field left on the widget to combine with it.
  testWidgets('shows the whole offer sentence as-is', (tester) async {
    await tester.pumpWidget(_wrap(const ActiveOfferBanner(text: 'خصم الصيف 20%')));
    expect(find.text('خصم الصيف 20%'), findsOneWidget);
  });

  testWidgets('a referral/mutual-benefit sentence renders exactly like a campaign one', (tester) async {
    await tester.pumpWidget(
        _wrap(const ActiveOfferBanner(text: 'خصم شراكة إحالة نشط — خصم شامل')));
    expect(find.text('خصم شراكة إحالة نشط — خصم شامل'), findsOneWidget);
  });
}
