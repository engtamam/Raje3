/// Wire shapes for the referral program's owner-facing monitoring/management surface.
/// Mirrors two real, separate backend services exactly, field for field — never invented shapes:
///   - services/referrals/app/api/v1/admin.py (`Campaign.to_dict()`, services/referrals/app/core/models.py)
///   - services/operations/app/api/v1/referral_reports.py (services/operations/app/core/referral_reports.py)
library;

// ── campaign modes (services/referrals/app/core/models.py::MODES) ──────────────────────────────
const String kReferralModeOnce = 'once';
const String kReferralModeXTimes = 'x_times';
const String kReferralModeLifetime = 'lifetime';

// ── usage-cap scope (services/referrals/app/core/models.py::CAP_SCOPE_*) ────────────────────────
const String kCapScopeCampaign = 'campaign';
const String kCapScopeLifetime = 'lifetime';

// ── the referrer's own reward — all eight real shapes, config only (rewards.py) ─────────────────
const String kRewardFixedPoints = 'fixed_points';
const String kRewardInvoicePercentage = 'invoice_percentage';
const String kRewardPointsMatch = 'points_match';
const String kRewardMilestoneFreeItem = 'milestone_free_item';
const String kRewardCashbackPoints = 'cashback_points';
const String kRewardStatusMultiplier = 'status_multiplier';
const String kRewardTimeBoost = 'time_boost';
const String kRewardMysteryBox = 'mystery_box';
const List<String> kReferrerRewardTypes = [
  kRewardFixedPoints, kRewardInvoicePercentage, kRewardPointsMatch, kRewardMilestoneFreeItem,
  kRewardCashbackPoints, kRewardStatusMultiplier, kRewardTimeBoost, kRewardMysteryBox,
];

// ── the mandatory "win-win" new-customer reward — a separate, smaller catalogue (rewards.py) ────
const String kNewCustomerDiscountPercent = 'discount_percent';
const String kNewCustomerWelcomePoints = 'welcome_points';
const List<String> kNewCustomerRewardTypes = [kNewCustomerDiscountPercent, kNewCustomerWelcomePoints];

const List<String> kUsageCapPeriods = ['day', 'week', 'month'];

/// `Campaign.to_dict()` — CAMPAIGN TERMS ARE IMMUTABLE ONCE CREATED (services/referrals/app/core/models.py's
/// own module docstring). The only field this app ever PATCHes after creation is `active`
/// (`PUT /api/v1/referrals/campaigns/{id}/active`) — there is deliberately no edit-terms UI here.
class ReferralCampaign {
  const ReferralCampaign({
    required this.id,
    required this.createdAt,
    required this.mode,
    required this.xTimesLimit,
    required this.minSpendMinor,
    required this.usageCapPeriod,
    required this.usageCapLimit,
    required this.rewardType,
    required this.rewardParams,
    required this.newCustomerRewardType,
    required this.newCustomerRewardParams,
    required this.active,
    required this.capScope,
  });

  final String id;
  final int createdAt;
  final String mode;
  final int xTimesLimit;
  final int minSpendMinor;
  final String usageCapPeriod;
  final int usageCapLimit;
  final String rewardType;
  final Map<String, dynamic> rewardParams;
  final String newCustomerRewardType;
  final Map<String, dynamic> newCustomerRewardParams;
  final bool active;
  final String capScope;

  factory ReferralCampaign.fromJson(Map<String, dynamic> j) => ReferralCampaign(
        id: (j['id'] as String?) ?? '',
        createdAt: (j['created_at'] as num?)?.toInt() ?? 0,
        mode: (j['mode'] as String?) ?? kReferralModeOnce,
        xTimesLimit: (j['x_times_limit'] as num?)?.toInt() ?? 0,
        minSpendMinor: (j['min_spend_minor'] as num?)?.toInt() ?? 0,
        usageCapPeriod: (j['usage_cap_period'] as String?) ?? '',
        usageCapLimit: (j['usage_cap_limit'] as num?)?.toInt() ?? 0,
        rewardType: (j['reward_type'] as String?) ?? '',
        rewardParams: Map<String, dynamic>.from(j['reward_params'] as Map? ?? const {}),
        newCustomerRewardType: (j['new_customer_reward_type'] as String?) ?? '',
        newCustomerRewardParams:
            Map<String, dynamic>.from(j['new_customer_reward_params'] as Map? ?? const {}),
        active: (j['active'] as bool?) ?? true,
        capScope: (j['cap_scope'] as String?) ?? kCapScopeCampaign,
      );
}

/// `GET /api/v1/referrals/reports/summary` — services/operations/app/core/referral_reports.py::summary.
/// `cost_ratio` (reward cost ÷ revenue) is the one figure that module weighs every other number
/// against — a redemption count alone is exactly the vanity metric its own docstring warns about.
class ReferralSummary {
  const ReferralSummary({
    required this.registeredCount,
    required this.redeemedCount,
    required this.conversionRate,
    required this.newCustomersAcquired,
    required this.revenueMinor,
    required this.rewardCostMinor,
    required this.costRatio,
  });

  final int registeredCount;
  final int redeemedCount;
  final double conversionRate;
  final int newCustomersAcquired;
  final int revenueMinor;
  final int rewardCostMinor;
  final double costRatio;

  factory ReferralSummary.fromJson(Map<String, dynamic> j) => ReferralSummary(
        registeredCount: (j['registered_count'] as num?)?.toInt() ?? 0,
        redeemedCount: (j['redeemed_count'] as num?)?.toInt() ?? 0,
        conversionRate: (j['conversion_rate'] as num?)?.toDouble() ?? 0,
        newCustomersAcquired: (j['new_customers_acquired'] as num?)?.toInt() ?? 0,
        revenueMinor: (j['revenue_minor'] as num?)?.toInt() ?? 0,
        rewardCostMinor: (j['reward_cost_minor'] as num?)?.toInt() ?? 0,
        costRatio: (j['cost_ratio'] as num?)?.toDouble() ?? 0,
      );
}

/// `GET /api/v1/referrals/reports/leaderboard` — RANKED BY REVENUE, never redemption count alone
/// (referral_reports.py's own rule, preserved here: never re-sort this list client-side).
class ReferralLeaderboardRow {
  const ReferralLeaderboardRow({
    required this.referrerPhone,
    required this.source,
    required this.redemptions,
    required this.revenueMinor,
    required this.rewardCostMinor,
    required this.lastRedeemedAt,
  });

  final String referrerPhone;
  final String source;
  final int redemptions;
  final int revenueMinor;
  final int rewardCostMinor;
  final int lastRedeemedAt;

  factory ReferralLeaderboardRow.fromJson(Map<String, dynamic> j) => ReferralLeaderboardRow(
        referrerPhone: (j['referrer_phone'] as String?) ?? '',
        source: (j['source'] as String?) ?? 'referral',
        redemptions: (j['redemptions'] as num?)?.toInt() ?? 0,
        revenueMinor: (j['revenue_minor'] as num?)?.toInt() ?? 0,
        rewardCostMinor: (j['reward_cost_minor'] as num?)?.toInt() ?? 0,
        lastRedeemedAt: (j['last_redeemed_at'] as num?)?.toInt() ?? 0,
      );
}

/// `GET /api/v1/referrals/reports/affiliates` — services/operations/app/core/referral_reports.py::affiliate_breakdown.
/// EVERY affiliate ever added, active or not, is returned — a paused one can still hold a real
/// unsettled balance (that module's own reasoning, preserved here: never filtered to active-only).
class ReferralAffiliateRow {
  const ReferralAffiliateRow({
    required this.affiliateId,
    required this.phone,
    required this.code,
    required this.active,
    required this.redemptions,
    required this.revenueMinor,
    required this.lastRedeemedAt,
    required this.unsettledPoints,
    required this.totalEarnedPoints,
  });

  final String affiliateId;
  final String phone;
  final String code;
  final bool active;
  final int redemptions;
  final int revenueMinor;
  final int lastRedeemedAt;
  final int unsettledPoints;
  final int totalEarnedPoints;

  factory ReferralAffiliateRow.fromJson(Map<String, dynamic> j) => ReferralAffiliateRow(
        affiliateId: (j['affiliate_id'] as String?) ?? '',
        phone: (j['phone'] as String?) ?? '',
        code: (j['code'] as String?) ?? '',
        active: (j['active'] as bool?) ?? true,
        redemptions: (j['redemptions'] as num?)?.toInt() ?? 0,
        revenueMinor: (j['revenue_minor'] as num?)?.toInt() ?? 0,
        lastRedeemedAt: (j['last_redeemed_at'] as num?)?.toInt() ?? 0,
        unsettledPoints: (j['unsettled_points'] as num?)?.toInt() ?? 0,
        totalEarnedPoints: (j['total_earned_points'] as num?)?.toInt() ?? 0,
      );
}
