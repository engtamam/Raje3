// Uses the REAL shipped assets/knowledge/mobile_actions.json — the same pattern
// assistant_service_test.dart and kb_service_test.dart already use for their own real assets.
import 'package:flutter_test/flutter_test.dart';
import 'package:raje3_mobile/core/actions/action_registry.dart';
import 'package:raje3_mobile/models/catalog_model.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late ActionRegistry registry;

  setUpAll(() async {
    registry = ActionRegistry();
    await registry.init();
  });

  Catalog catalogWith(List<String> actionIds) => Catalog(
        services: [
          CatalogServiceEntry(
            service: 'operations',
            actions: [
              for (final id in actionIds)
                CatalogAction(id: id, label: id, method: 'GET', path: '/x', capability: id),
            ],
          ),
        ],
        unreachable: const [],
      );

  test('the real registry loads the visit-navigation action', () {
    final actions = registry.visibleActions(catalogWith(['operations.record_visit'])).toList();
    expect(actions.map((a) => a.name), contains('open_visit_app'));
  });

  test('an action gated by a capability the session lacks is invisible', () {
    final actions = registry.visibleActions(Catalog.empty).toList();
    // 'nav.home' has an empty `requires` (see mobile_actions.json) — always visible, same as
    // 'home' itself never being gated by a capability. Only the gated action is missing here.
    expect(actions.map((a) => a.name), isNot(contains('open_visit_app')));
  });

  test('byName only resolves an action the session may actually use', () {
    expect(registry.byName('open_visit_app', Catalog.empty), isNull);
    expect(
      registry.byName('open_visit_app', catalogWith(['operations.record_visit'])),
      isNotNull,
    );
  });

  test('byName never resolves a name that does not exist', () {
    expect(registry.byName('delete_everything', catalogWith(['operations.record_visit'])), isNull);
  });
}
