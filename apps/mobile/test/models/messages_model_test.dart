// «القوالب» merge rule and campaign scheduling logic — the same real bugs the console's own
// history warns about (a wrong `state === 'running'` comparison hid the pause button forever;
// `fire_at == 0` silently means "never fires" for a scheduled campaign) live as PURE functions
// here so a test can hold them without building a screen.
import 'package:flutter_test/flutter_test.dart';
import 'package:raje3_mobile/models/messages_model.dart';

ReasonRow _reason(String id, {String cls = 'service'}) => ReasonRow(
      id: id,
      label: id,
      when: 'when',
      on: true,
      canSwitch: true,
      canRetext: false,
      cls: cls,
      clsLabel: cls,
      templateStatus: 'unknown',
    );

GoalRow _goal(String goal, {List<String> blanks = const []}) => GoalRow(
      goal: goal,
      title: goal,
      line: 'line',
      templateStatus: 'unknown',
      uses: 0,
      reach: 0,
      available: true,
      unavailableReason: '',
      icon: '',
      blanks: blanks,
    );

void main() {
  group('mergeTemplateCards', () {
    test('a reason sharing REASON_GOAL carries both auto and manual', () {
      final cards = mergeTemplateCards([_reason('gone_missing')], [_goal('win_back')]);
      expect(cards, hasLength(1));
      expect(cards.single.auto, isTrue);
      expect(cards.single.manual, isTrue);
      expect(cards.single.goal, 'win_back');
    });

    test('a goal already carried by its reason is never duplicated', () {
      final cards = mergeTemplateCards(
        [_reason('gone_missing'), _reason('personal_occasion'), _reason('loyal_customer')],
        [_goal('win_back'), _goal('occasion'), _goal('reward_loyal'), _goal('announce')],
      );
      // 3 shared reason cards + 1 goal-only card (announce) — never 3 + 4.
      expect(cards, hasLength(4));
      expect(cards.where((c) => c.goal == 'win_back'), hasLength(1));
    });

    test('an automatic-only reason with no linked goal stays auto-only', () {
      final cards = mergeTemplateCards([_reason('visit_recorded')], []);
      expect(cards.single.auto, isTrue);
      expect(cards.single.manual, isFalse);
      expect(cards.single.goal, isNull);
    });

    test('a goal with no automatic counterpart stays manual-only', () {
      final cards = mergeTemplateCards([], [_goal('service_offer')]);
      expect(cards.single.auto, isFalse);
      expect(cards.single.manual, isTrue);
    });
  });

  group('GoalRow.hasBlank', () {
    test('a goal with no date blank never asks for an end date', () {
      final g = _goal('announce', blanks: ['owner']);
      expect(g.hasBlank('date'), isFalse);
      expect(g.hasBlank('owner'), isTrue);
    });
  });

  group('Campaign.isScheduled', () {
    test('a future fire_at never yet evaluated is scheduled', () {
      final future = DateTime.now().add(const Duration(days: 3)).millisecondsSinceEpoch ~/ 1000;
      final c = Campaign.fromJson({
        'id': 'c1', 'goal': 'occasion', 'state': 'active', 'sent': 0,
        'fire_at': future, 'last_evaluated': 0,
      });
      expect(c.isScheduled, isTrue);
    });

    test('a campaign already fired at least once is never "scheduled" again', () {
      final future = DateTime.now().add(const Duration(days: 3)).millisecondsSinceEpoch ~/ 1000;
      final c = Campaign.fromJson({
        'id': 'c2', 'goal': 'occasion', 'state': 'active', 'sent': 5,
        'fire_at': future, 'last_evaluated': 1700000000,
      });
      expect(c.isScheduled, isFalse);
    });

    test('a bare fire_at of 0 (no schedule at all) is never "scheduled"', () {
      final c = Campaign.fromJson({
        'id': 'c3', 'goal': 'win_back', 'state': 'active', 'sent': 3,
        'fire_at': 0, 'last_evaluated': 0,
      });
      expect(c.isScheduled, isFalse);
    });
  });
}
