// The action registry's own contract — the Dart mirror of kb_model_test.dart's own tests, same
// questions: what is required, and that one malformed entry fails the whole load rather than
// silently vanishing.
import 'package:flutter_test/flutter_test.dart';
import 'package:raje3_mobile/core/actions/action_model.dart';

Map<String, dynamic> _validJson() => {
      'name': 'open_visit_app',
      'description': 'Open the visit screen.',
      'scope': 'navigation',
      'route': 'visit',
      'kb_entry': 'visit.register',
      'enabled': true,
      'requires_confirmation': false,
    };

void main() {
  group('AppAction.fromJson', () {
    test('name, description, scope, kb_entry, enabled and requires_confirmation are all '
        'required', () {
      final a = AppAction.fromJson('nav.visit', _validJson());
      expect(a.id, 'nav.visit');
      expect(a.name, 'open_visit_app');
      expect(a.scope, ActionScope.navigation);
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
      final json = _validJson()
        ..['requires_confirmation'] = true
        ..['confirm_message'] = 'سيتم تنفيذ هذا الفعل.';
      final a = AppAction.fromJson('nav.visit', json);
      expect(a.requiresConfirmation, isTrue);
      expect(a.confirmMessage, 'سيتم تنفيذ هذا الفعل.');
    });

    test('requires_confirmation: true with no confirm_message throws ActionError', () {
      final json = _validJson()..['requires_confirmation'] = true;
      expect(() => AppAction.fromJson('nav.visit', json), throwsA(isA<ActionError>()));
    });

    test('confirm_message set while requires_confirmation is false throws ActionError', () {
      final json = _validJson()..['confirm_message'] = 'لن يظهر أبدًا.';
      expect(() => AppAction.fromJson('nav.visit', json), throwsA(isA<ActionError>()));
    });

    for (final field in [
      'name',
      'description',
      'scope',
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

    test('an unrecognized "scope" throws ActionError', () {
      final json = _validJson()..['scope'] = 'wat';
      expect(() => AppAction.fromJson('nav.visit', json), throwsA(isA<ActionError>()));
    });

    test('scope "navigation" with no route throws ActionError — nothing to navigate to', () {
      final json = _validJson()..remove('route');
      expect(() => AppAction.fromJson('nav.visit', json), throwsA(isA<ActionError>()));
    });

    test('scope "system" needs no route at all', () {
      final json = _validJson()
        ..['scope'] = 'system'
        ..remove('route');
      final a = AppAction.fromJson('sys.stop', json);
      expect(a.scope, ActionScope.system);
      expect(a.route, isNull);
    });

    test('scope "app" needs no route at all', () {
      final json = _validJson()
        ..['scope'] = 'app'
        ..remove('route');
      final a = AppAction.fromJson('app.visit.pick_service', json);
      expect(a.scope, ActionScope.app);
      expect(a.route, isNull);
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
