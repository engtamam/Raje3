// CapabilityGate is the one primitive every screen's write actions are meant to compose from
// now on (2026-09-24, phase 1 of the permission-gate effort) — these tests pin its ONLY real
// contract: hides [child] unless every required action id is present in the catalogue,
// mirroring `Catalog.hasAll`/apps/console/src/catalog.ts's own `hasAll` exactly.
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:raje3_mobile/models/catalog_model.dart';
import 'package:raje3_mobile/widgets/capability_gate.dart';

Catalog _catalogWith(List<String> ids) => Catalog(
      services: [
        CatalogServiceEntry(
          service: 'operations',
          actions: [
            for (final id in ids)
              CatalogAction(id: id, label: id, method: 'POST', path: '/x', capability: id),
          ],
        ),
      ],
      unreachable: const [],
    );

void main() {
  testWidgets('renders the child when every required id is present', (tester) async {
    await tester.pumpWidget(Directionality(
      textDirection: TextDirection.rtl,
      child: CapabilityGate(
        requires: const ['operations.update_service'],
        catalog: _catalogWith(['operations.update_service']),
        child: const Text('تعديل'),
      ),
    ));
    expect(find.text('تعديل'), findsOneWidget);
  });

  testWidgets('hides the child when the required id is absent', (tester) async {
    await tester.pumpWidget(Directionality(
      textDirection: TextDirection.rtl,
      child: CapabilityGate(
        requires: const ['operations.update_service'],
        catalog: _catalogWith(['operations.list_services']),
        child: const Text('تعديل'),
      ),
    ));
    expect(find.text('تعديل'), findsNothing);
  });

  testWidgets('is all-or-nothing across several required ids', (tester) async {
    await tester.pumpWidget(Directionality(
      textDirection: TextDirection.rtl,
      child: CapabilityGate(
        requires: const ['operations.update_service', 'operations.upload_service_image'],
        catalog: _catalogWith(['operations.update_service']),
        child: const Text('تعديل'),
      ),
    ));
    expect(find.text('تعديل'), findsNothing);
  });

  testWidgets('hides the child against an empty catalogue', (tester) async {
    await tester.pumpWidget(const Directionality(
      textDirection: TextDirection.rtl,
      child: CapabilityGate(
        requires: ['operations.update_service'],
        catalog: Catalog.empty,
        child: Text('تعديل'),
      ),
    ));
    expect(find.text('تعديل'), findsNothing);
  });
}
