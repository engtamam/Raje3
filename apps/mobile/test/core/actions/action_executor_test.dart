import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:raje3_mobile/core/actions/action_executor.dart';
import 'package:raje3_mobile/core/actions/action_registry.dart';
import 'package:raje3_mobile/core/ai/ai_model.dart';
import 'package:raje3_mobile/models/catalog_model.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late ActionRegistry registry;
  late ActionExecutor executor;

  setUpAll(() async {
    registry = ActionRegistry();
    await registry.init();
    executor = ActionExecutor(registry: registry);
  });

  Catalog catalogWith(List<String> ids) => Catalog(
        services: [
          CatalogServiceEntry(
            service: 'operations',
            actions: [
              for (final id in ids)
                CatalogAction(id: id, label: id, method: 'GET', path: '/x', capability: id),
            ],
          ),
        ],
        unreachable: const [],
      );

  group('ActionExecutor.resolve', () {
    test('an unknown action name is unavailable', () {
      final decision = executor.resolve(
        AiActionProposed('delete_everything', const {}),
        catalogWith(['operations.record_visit']),
      );
      expect(decision, isA<ActionUnavailable>());
    });

    test('a real action without the capability is unavailable — never trusted from an old '
        'tool list', () {
      final decision = executor.resolve(AiActionProposed('open_visit_app', const {}), Catalog.empty);
      expect(decision, isA<ActionUnavailable>());
    });

    test('a real action with the capability, requiring no confirmation, runs now', () {
      final decision = executor.resolve(
        AiActionProposed('open_visit_app', const {}),
        catalogWith(['operations.record_visit']),
      );
      expect(decision, isA<ActionRunNow>());
      expect((decision as ActionRunNow).action.name, 'open_visit_app');
    });
  });

  group('ActionExecutor.execute', () {
    testWidgets('navigates to the action\'s own route', (tester) async {
      final router = GoRouter(
        initialLocation: '/a',
        routes: [
          GoRoute(path: '/a', name: 'a', builder: (_, __) => const Text('screen a')),
          GoRoute(path: '/visit', name: 'visit', builder: (_, __) => const Text('screen visit')),
        ],
      );
      await tester.pumpWidget(MaterialApp.router(routerConfig: router));
      expect(find.text('screen a'), findsOneWidget);

      final context = tester.element(find.text('screen a'));
      final decision = executor.resolve(
        AiActionProposed('open_visit_app', const {}),
        catalogWith(['operations.record_visit']),
      );
      executor.execute(context, (decision as ActionRunNow).action);
      await tester.pumpAndSettle();

      expect(find.text('screen visit'), findsOneWidget);
    });
  });

  group('ActionExecutor — read actions resolve to a run-now, no-route action', () {
    // NOT a full execute() round trip here — that hits AuthProvider's real network calls, and
    // this file's own job is proving the REGISTRY/EXECUTOR wiring (route is null so navigation
    // never fires, requires_confirmation is false so no tap is needed), not re-testing
    // AuthProvider's own already-covered HTTP methods against a live or mocked server.
    for (final name in [
      'read_billing_status',
      'read_branch_count',
      'read_vehicle_tracking_status',
    ]) {
      test('$name resolves to ActionRunNow with no route', () {
        final decision = executor.resolve(AiActionProposed(name, const {}), catalogWith(const []));
        expect(decision, isA<ActionRunNow>());
        expect((decision as ActionRunNow).action.route, isNull);
        expect(decision.action.requiresConfirmation, isFalse);
      });
    }
  });

  group('ActionExecutor — write actions resolve to ActionNeedsConfirmation, no route', () {
    for (final name in [
      'enable_vehicle_tracking',
      'disable_vehicle_tracking',
    ]) {
      test('$name resolves to ActionNeedsConfirmation with no route and its own message', () {
        final decision = executor.resolve(
          AiActionProposed(name, const {}),
          catalogWith(['operations.manage']),
        );
        expect(decision, isA<ActionNeedsConfirmation>());
        final action = (decision as ActionNeedsConfirmation).action;
        expect(action.route, isNull);
        expect(action.confirmMessage, isNotNull);
        expect(action.confirmMessage, isNotEmpty);
      });

      test('$name is unavailable without operations.manage — never trusted from a stale tool '
          'list', () {
        final decision = executor.resolve(AiActionProposed(name, const {}), Catalog.empty);
        expect(decision, isA<ActionUnavailable>());
      });
    }
  });
}
