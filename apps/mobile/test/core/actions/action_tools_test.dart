// The connector between our own registry and AiModel's own AiTool shape — pure translation,
// verified both as a standalone function and through ActionRegistry.toolsFor()'s own real asset.
import 'package:flutter_test/flutter_test.dart';
import 'package:raje3_mobile/core/actions/action_model.dart';
import 'package:raje3_mobile/core/actions/action_registry.dart';
import 'package:raje3_mobile/core/actions/action_tools.dart';
import 'package:raje3_mobile/models/catalog_model.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('actionTools', () {
    test('translates name and description, nothing else', () {
      const action = AppAction(
        id: 'nav.visit',
        name: 'open_visit_app',
        description: 'وصف الفعل',
        scope: ActionScope.navigation,
        route: 'visit',
        kbEntryId: 'visit.register',
        enabled: true,
        requiresConfirmation: false,
      );
      final tools = actionTools([action]);
      expect(tools, hasLength(1));
      expect(tools.single.name, 'open_visit_app');
      expect(tools.single.description, 'وصف الفعل');
    });

    test('an empty action list produces an empty tool list', () {
      expect(actionTools(const []), isEmpty);
    });
  });

  group('ActionRegistry.toolsFor (real registry)', () {
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

    test('a session with the capability gets the tool declared', () {
      final tools = registry.toolsFor(catalogWith(['operations.record_visit']));
      expect(tools.map((t) => t.name), contains('open_visit_app'));
    });

    test('a session without the capability gets no tools at all — never a leaked action name',
        () {
      final tools = registry.toolsFor(Catalog.empty);
      expect(tools, isEmpty);
    });
  });
}
