// The action registry's own contract — the Dart mirror of kb_model_test.dart's own tests, same
// questions: what is required, and that one malformed entry fails the whole load rather than
// silently vanishing.
import 'package:flutter_test/flutter_test.dart';
import 'package:raje3_mobile/core/actions/action_model.dart';

void main() {
  group('AppAction.fromJson', () {
    test('name, description, route and kb_entry are all required', () {
      final a = AppAction.fromJson('nav.visit', {
        'name': 'navigate_to_visit',
        'description': 'Open the visit screen.',
        'route': 'visit',
        'kb_entry': 'visit.register',
      });
      expect(a.id, 'nav.visit');
      expect(a.name, 'navigate_to_visit');
      expect(a.route, 'visit');
      expect(a.kbEntryId, 'visit.register');
      expect(a.requires, isEmpty);
    });

    test('requires is parsed when present', () {
      final a = AppAction.fromJson('nav.visit', {
        'name': 'navigate_to_visit',
        'description': 'd',
        'route': 'visit',
        'kb_entry': 'visit.register',
        'requires': ['operations.record_visit'],
      });
      expect(a.requires, ['operations.record_visit']);
    });

    for (final field in ['name', 'description', 'route', 'kb_entry']) {
      test('missing "$field" throws ActionError', () {
        final json = {
          'name': 'navigate_to_visit',
          'description': 'd',
          'route': 'visit',
          'kb_entry': 'visit.register',
        }..remove(field);
        expect(() => AppAction.fromJson('nav.visit', json), throwsA(isA<ActionError>()));
      });
    }
  });

  group('parseActions', () {
    test('parses a map of actions', () {
      final actions = parseActions({
        'nav.visit': {
          'name': 'navigate_to_visit',
          'description': 'd',
          'route': 'visit',
          'kb_entry': 'visit.register',
        },
      });
      expect(actions.map((a) => a.id), ['nav.visit']);
    });

    test('one malformed entry fails the whole load', () {
      expect(
        () => parseActions({
          'nav.visit': {
            'name': 'navigate_to_visit',
            'description': 'd',
            'route': 'visit',
            'kb_entry': 'visit.register',
          },
          'nav.broken': {'name': 'x'},
        }),
        throwsA(isA<ActionError>()),
      );
    });

    test('two actions sharing the same model-facing name fail the whole load', () {
      expect(
        () => parseActions({
          'nav.a': {
            'name': 'same_name',
            'description': 'd',
            'route': 'visit',
            'kb_entry': 'visit.register',
          },
          'nav.b': {
            'name': 'same_name',
            'description': 'd2',
            'route': 'home',
            'kb_entry': 'auth.login',
          },
        }),
        throwsA(isA<ActionError>()),
      );
    });
  });
}
