// Real-shape parsing tests for the referral program's wire models — the exact class of bug this
// review found once already in a sibling screen (coworking's own console `weekly` field: the
// screen assumed the PUT request body's own shape instead of what the GET response actually
// returns). These tests pin every field name to what the real backend routes actually emit
// (services/referrals/app/core/models.py::Campaign.to_dict(),
// services/operations/app/core/referral_reports.py's own summary/leaderboard/campaign_breakdown/
// affiliate_breakdown dicts) — never an invented shape.
import 'package:flutter_test/flutter_test.dart';
import 'package:raje3_mobile/models/referral_model.dart';

void main() {
  group('ReferralCampaign.fromJson', () {
    test('reads every real Campaign.to_dict() field', () {
      final campaign = ReferralCampaign.fromJson({
        'id': 'camp_1',
        'tenant': 'tnt_a',
        'created_at': 1700000000,
        'mode': kReferralModeXTimes,
        'x_times_limit': 5,
        'min_spend_minor': 1000,
        'usage_cap_period': 'month',
        'usage_cap_limit': 50,
        'reward_type': kRewardFixedPoints,
        'reward_params': {'points': 200},
        'new_customer_reward_type': kNewCustomerWelcomePoints,
        'new_customer_reward_params': {'points': 100},
        'active': true,
        'created_ns': 123456,
        'cap_scope': kCapScopeLifetime,
      });

      expect(campaign.id, 'camp_1');
      expect(campaign.createdAt, 1700000000);
      expect(campaign.mode, kReferralModeXTimes);
      expect(campaign.xTimesLimit, 5);
      expect(campaign.minSpendMinor, 1000);
      expect(campaign.usageCapPeriod, 'month');
      expect(campaign.usageCapLimit, 50);
      expect(campaign.rewardType, kRewardFixedPoints);
      expect(campaign.rewardParams, {'points': 200});
      expect(campaign.newCustomerRewardType, kNewCustomerWelcomePoints);
      expect(campaign.newCustomerRewardParams, {'points': 100});
      expect(campaign.active, isTrue);
      expect(campaign.capScope, kCapScopeLifetime);
    });

    test('a campaign with no cap_scope defaults to "campaign", the same default the backend '
        'gives a row created before the field existed', () {
      final campaign = ReferralCampaign.fromJson({
        'id': 'camp_old',
        'mode': kReferralModeOnce,
        'reward_type': kRewardFixedPoints,
        'new_customer_reward_type': kNewCustomerDiscountPercent,
      });
      expect(campaign.capScope, kCapScopeCampaign);
      expect(campaign.active, isTrue); // absent 'active' also defaults true, matching the model
      expect(campaign.rewardParams, isEmpty);
    });
  });

  group('ReferralSummary.fromJson', () {
    test('reads every real referral_reports.py::summary() field, including cost_ratio', () {
      final summary = ReferralSummary.fromJson({
        'registered_count': 40,
        'redeemed_count': 25,
        'conversion_rate': 0.625,
        'new_customers_acquired': 25,
        'revenue_minor': 500000,
        'reward_cost_minor': 30000,
        'cost_ratio': 0.06,
      });
      expect(summary.registeredCount, 40);
      expect(summary.redeemedCount, 25);
      expect(summary.conversionRate, 0.625);
      expect(summary.newCustomersAcquired, 25);
      expect(summary.revenueMinor, 500000);
      expect(summary.rewardCostMinor, 30000);
      expect(summary.costRatio, 0.06);
    });

    test('a brand-new shop with zero grants parses to real zeros, not nulls crashing the screen',
        () {
      final summary = ReferralSummary.fromJson(const {});
      expect(summary.registeredCount, 0);
      expect(summary.redeemedCount, 0);
      expect(summary.conversionRate, 0);
      expect(summary.costRatio, 0);
    });
  });

  group('ReferralLeaderboardRow.fromJson', () {
    test('reads every real leaderboard() grouped-row field', () {
      final row = ReferralLeaderboardRow.fromJson({
        'referrer_phone': '966501234567',
        'source': 'affiliate',
        'redemptions': 12,
        'revenue_minor': 90000,
        'reward_cost_minor': 4500,
        'last_redeemed_at': 1700000999,
      });
      expect(row.referrerPhone, '966501234567');
      expect(row.source, 'affiliate');
      expect(row.redemptions, 12);
      expect(row.revenueMinor, 90000);
      expect(row.rewardCostMinor, 4500);
      expect(row.lastRedeemedAt, 1700000999);
    });

    test('an ordinary (non-affiliate) referral defaults source to "referral"', () {
      final row = ReferralLeaderboardRow.fromJson({'referrer_phone': '966500000000'});
      expect(row.source, 'referral');
    });
  });

  group('ReferralAffiliateRow.fromJson', () {
    test('reads every real affiliate_breakdown() field — no reward_cost_minor, that key '
        "genuinely does not exist on this route's own response shape", () {
      final row = ReferralAffiliateRow.fromJson({
        'affiliate_id': 'aff_1',
        'phone': '966511111111',
        'code': 'ABC123',
        'active': false,
        'redemptions': 3,
        'revenue_minor': 15000,
        'last_redeemed_at': 1700001000,
        'unsettled_points': 400,
        'total_earned_points': 1200,
      });
      expect(row.affiliateId, 'aff_1');
      expect(row.phone, '966511111111');
      expect(row.code, 'ABC123');
      expect(row.active, isFalse);
      expect(row.redemptions, 3);
      expect(row.revenueMinor, 15000);
      expect(row.lastRedeemedAt, 1700001000);
      expect(row.unsettledPoints, 400);
      expect(row.totalEarnedPoints, 1200);
    });

    test('a paused affiliate with zero redemptions still parses (never filtered client-side — '
        'affiliate_breakdown never excludes an inactive affiliate)', () {
      final row = ReferralAffiliateRow.fromJson({
        'affiliate_id': 'aff_paused',
        'phone': '966522222222',
        'code': 'XYZ999',
        'active': false,
      });
      expect(row.active, isFalse);
      expect(row.redemptions, 0);
      expect(row.unsettledPoints, 0);
    });
  });

  group('reward-type catalogues stay in sync with the real backend enum', () {
    test('all 8 referrer reward types are present, exactly once each', () {
      expect(kReferrerRewardTypes.toSet().length, 8);
      expect(kReferrerRewardTypes, contains(kRewardMysteryBox));
      expect(kReferrerRewardTypes, contains(kRewardTimeBoost));
    });

    test('the new-customer catalogue is the separate, smaller, mandatory-reward set', () {
      expect(kNewCustomerRewardTypes, hasLength(2));
      expect(kNewCustomerRewardTypes, isNot(contains(kRewardFixedPoints)));
    });
  });
}
