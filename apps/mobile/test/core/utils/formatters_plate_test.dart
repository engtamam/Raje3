import 'package:flutter_test/flutter_test.dart';
import 'package:raje3_mobile/core/utils/formatters.dart';

// arabic-indic-digits: intentional — these feed the folder the exact input it exists to convert.

/// Mirrors apps/console/src/screens/plate.test.ts's own cases exactly — the same rule matters
/// twice now (this screen and the console's own), and a plate typed on either must read the same
/// way. A wrong rule here splits one car into two customers.
void main() {
  group('Formatters.formatPlate', () {
    test('places the separator so he never types it', () {
      expect(Formatters.formatPlate('1234ABC'), '1234 ABC');
    });

    test('accepts a short plate, because a short plate is a real plate', () {
      expect(Formatters.formatPlate('12'), '12');
      expect(Formatters.formatPlate('12A'), '12 A');
    });

    test('holds the Saudi maximum: four digits, three letters', () {
      expect(Formatters.formatPlate('123456ABCDE'), '1234 ABC');
    });

    test('drops stray characters rather than refusing the whole entry', () {
      expect(Formatters.formatPlate('12-34 /a b c'), '1234 ABC');
    });

    test('uppercases, because two scripts for one car is two customers', () {
      expect(Formatters.formatPlate('1234abc'), '1234 ABC');
    });

    test('folds Arabic-Indic digits before stripping, same real bug the console side fixed once', () {
      expect(Formatters.formatPlate('١٢٣٤ابج'), isNotEmpty);
      expect(Formatters.formatPlate('١٢٣٤ABC'), '1234 ABC');
    });
  });

  group('Formatters.isPlatePlausible', () {
    test('one letter and one digit, in any script, anywhere — matches core/plate.py exactly', () {
      expect(Formatters.isPlatePlausible('1234 ABC'), isTrue);
      expect(Formatters.isPlatePlausible('A1'), isTrue);
      expect(Formatters.isPlatePlausible('1A'), isTrue);
    });

    test('digits alone are not plausible — no letter', () {
      expect(Formatters.isPlatePlausible('1234'), isFalse);
    });

    test('letters alone are not plausible — no digit', () {
      expect(Formatters.isPlatePlausible('ABC'), isFalse);
    });

    test('empty is not plausible', () {
      expect(Formatters.isPlatePlausible(''), isFalse);
    });
  });
}
