// The action registry's own contract — the Dart mirror of kb_model_test.dart's own tests, same
// questions: what is required, and that one malformed entry fails the whole load rather than
// silently vanishing.
import 'package:flutter_test/flutter_test.dart';
import 'package:raje3_mobile/core/actions/action_model.dart';

Map<String, dynamic> _validJson() => {
      'name': 'navigate_to_visit',
      'description': 'Open the visit screen.',
      'route': 'visit',
      'kb_entry': 'visit.register',
      'enabled': true,
      'requires_confirmation': false,
    };

void main() {
  group('AppAction.fromJson', () {
    test('name, description, route, kb_entry, enabled and requires_confirmation are all '
        'required', () {
      final a = AppAction.fromJson('nav.visit', _validJson());
      expect(a.id, 'nav.visit');
      expect(a.name, 'navigate_to_visit');
      expect(a.route, 'visit');
      expect(a.kbEntryId, 'visit.register');
      expect(a.enabled, isTrue);
      expect(a.requiresConfirmation, isFalse);
      expect(a.requires, isEmpty);
    });

    test('requires is parsed when present', () {
      final json = _validJson()..['requires'] = ['operations.record_visit'];
      final a = AppAction.fromJson('nav.visit', json);
      expect(a.requires, ['operations.record_visit']);
    });

    test('requires_confirmation: true is parsed for a sensitive action', () {
      final json = _validJson()..['requires_confirmation'] = true;
      final a = AppAction.fromJson('nav.visit', json);
      expect(a.requiresConfirmation, isTrue);
    });

    for (final field in [
      'name',
      'description',
      'route',
      'kb_entry',
      'enabled',
      'requires_confirmation',
    ]) {
      test('missing "$field" throws ActionError — no silent default', () {
        final json = _validJson()..remove(field);
        expect(() => AppAction.fromJson('nav.visit', json), throwsA(isA<ActionError>()));
      });
    }

    test('a non-bool "enabled" throws ActionError', () {
      final json = _validJson()..['enabled'] = 'yes';
      expect(() => AppAction.fromJson('nav.visit', json), throwsA(isA<ActionError>()));
    });

    test('a non-bool "requires_confirmation" throws ActionError', () {
      final json = _validJson()..['requires_confirmation'] = 1;
      expect(() => AppAction.fromJson('nav.visit', json), throwsA(isA<ActionError>()));
    });
  });

  group('parseActions', () {
    test('parses a map of actions', () {
      final actions = parseActions({'nav.visit': _validJson()});
      expect(actions.map((a) => a.id), ['nav.visit']);
    });

    test('one malformed entry fails the whole load', () {
      expect(
        () => parseActions({
          'nav.visit': _validJson(),
          'nav.broken': {'name': 'x'},
        }),
        throwsA(isA<ActionError>()),
      );
    });

    test('two actions sharing the same model-facing name fail the whole load', () {
      expect(
        () => parseActions({
          'nav.a': _validJson(),
          'nav.b': _validJson()
            ..['route'] = 'home'
            ..['kb_entry'] = 'auth.login',
        }),
        throwsA(isA<ActionError>()),
      );
    });
  });
}
