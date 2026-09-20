// The mobile KB entry contract — the Dart mirror of
// platform/services/assistant-service/app/core/kb.py's own test_kb_model.py. Same questions:
// what is required, what an omitted field means, and that a malformed entry fails the whole
// load rather than silently vanishing.
import 'package:flutter_test/flutter_test.dart';
import 'package:raje3_mobile/core/knowledge/kb_model.dart';
import 'package:raje3_mobile/models/catalog_model.dart';

void main() {
  group('KbEntry.fromJson', () {
    test('title and body are the only required fields', () {
      final e = KbEntry.fromJson('x.y', {'title': 'T', 'body': 'B'});
      expect(e.text('en'), ('T', 'B'));
      expect(e.requires, isEmpty);
      expect(e.anchor, isEmpty);
      expect(e.kind, isEmpty);
      expect(e.related, isEmpty);
      expect(e.cta, isNull);
    });

    test('a bare string is accepted as the default language', () {
      final e = KbEntry.fromJson('x', {'title': 'T', 'body': 'B'});
      expect(e.title, {'ar': 'T'});
    });

    test('missing title throws KbError', () {
      expect(() => KbEntry.fromJson('x', {'body': 'B'}), throwsA(isA<KbError>()));
    });

    test('missing body throws KbError', () {
      expect(() => KbEntry.fromJson('x', {'title': 'T'}), throwsA(isA<KbError>()));
    });

    test('an empty body string throws KbError', () {
      expect(() => KbEntry.fromJson('x', {'title': 'T', 'body': ''}), throwsA(isA<KbError>()));
    });

    test('an empty translation throws KbError', () {
      expect(
        () => KbEntry.fromJson('x', {
          'title': 'T',
          'body': {'en': ''},
        }),
        throwsA(isA<KbError>()),
      );
    });

    test('cta without a route throws KbError', () {
      expect(
        () => KbEntry.fromJson('x', {
          'title': 'T',
          'body': 'B',
          'cta': {'label': 'Go'},
        }),
        throwsA(isA<KbError>()),
      );
    });

    test('parses requires, anchor, kind, related and cta together', () {
      final e = KbEntry.fromJson('visit.register', {
        'title': {'ar': 'زيارة', 'en': 'Visit'},
        'body': {'ar': 'شرح', 'en': 'Explanation'},
        'kind': 'screen',
        'anchor': 'visit.register',
        'requires': ['operations.record_visit'],
        'related': ['auth.login'],
        'cta': {'label': 'افتح', 'route': '/visit'},
      });
      expect(e.kind, 'screen');
      expect(e.anchor, 'visit.register');
      expect(e.requires, ['operations.record_visit']);
      expect(e.related, ['auth.login']);
      expect(e.cta!.route, '/visit');
    });
  });

  group('KbEntry.text language fallback', () {
    test('falls back to the default language, then to any language present', () {
      final e = KbEntry.fromJson('x', {
        'title': {'en': 'Title'},
        'body': {'en': 'Body'},
      });
      // asked for 'ar', has only 'en' — falls back rather than answering nothing.
      expect(e.text('ar'), ('Title', 'Body'));
    });

    test('a regional tag like ar-SA finds the base language', () {
      final e = KbEntry.fromJson('x', {
        'title': {'ar': 'عنوان'},
        'body': {'ar': 'نص'},
      });
      expect(e.text('ar-SA'), ('عنوان', 'نص'));
    });
  });

  group('parseKb', () {
    test('parses a map of entries', () {
      final entries = parseKb({
        'a': {'title': 'A', 'body': 'body a'},
        'b': {'title': 'B', 'body': 'body b'},
      });
      expect(entries.map((e) => e.id).toSet(), {'a', 'b'});
    });

    test('one malformed entry fails the whole load', () {
      expect(
        () => parseKb({
          'a': {'title': 'A', 'body': 'body a'},
          'b': {'title': 'B'},
        }),
        throwsA(isA<KbError>()),
      );
    });
  });

  group('visibility against the real capability catalogue', () {
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

    test('an entry with no requires is always visible', () {
      final e = KbEntry.fromJson('x', {'title': 'T', 'body': 'B'});
      expect(e.requires.isEmpty ? true : catalogWith([]).hasAll(e.requires), isTrue);
    });

    test('an entry requiring a capability the session lacks is not held by the catalogue', () {
      final e = KbEntry.fromJson('visit.register', {
        'title': 'T',
        'body': 'B',
        'requires': ['operations.record_visit'],
      });
      expect(catalogWith([]).hasAll(e.requires), isFalse);
      expect(catalogWith(['operations.record_visit']).hasAll(e.requires), isTrue);
    });
  });
}
