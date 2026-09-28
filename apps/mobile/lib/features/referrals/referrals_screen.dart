import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:share_plus/share_plus.dart';

import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/providers/nav_provider.dart';
import 'package:raje3_mobile/core/services/referrals_service.dart';
import 'package:raje3_mobile/models/referral_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/widgets/capability_gate.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';

/// «نظام الإحالة» — the owner/staff-facing monitoring + management surface for the referral
/// program. STAFF-FACING, never the end-customer's own referral screen (that is a different,
/// not-yet-built surface reached from the customer side, out of scope here).
///
/// ITS OWN VISUAL IDENTITY, deliberately never a reskin of points_screen.dart's treasure-vault
/// language: a referral is fundamentally a NETWORK growing outward from one shop — a referrer
/// bringing in a new customer, who can in turn refer another — so the hero and every accent here
/// draw from a tree/network motif (branching nodes, a teal-to-blue "growth" gradient), the same
/// "bespoke literal gradient for this screen's own identity" precedent points_screen.dart's own
/// `_PointsHero` already sets (its violet/gold is not a generated theme token either).
///
/// COMPANY-WIDE, NO BRANCH FILTER — referrals has no `branch_id` scoping anywhere in its domain
/// (services/referrals + services/operations/app/core/referral_redemption.py), matching every
/// other campaign-shaped feature in this fleet. Never add a branch picker here.
///
/// CAMPAIGN TERMS ARE IMMUTABLE ONCE CREATED — the only PATCH this screen or its sheet ever sends
/// after creation is `active` (pause/resume). There is deliberately no edit-terms UI.
///
/// A REAL GAP FOUND WHILE BUILDING THIS: services/operations/app/core/referral_redemption.py
/// refuses a "prior dealing" redemption SYNCHRONOUSLY, before any grant row is ever written (see
/// its own `existing Customer row` checks) — so there is no stored, listable "rejected" event
/// anywhere in this fleet, and no endpoint returns individual grant events at all (only the
/// aggregate summary/leaderboard/campaign/affiliate reports do). A "recent events feed" with
/// pending/success/rejected status pills was part of this task's own brief, but building it would
/// mean inventing data no real endpoint provides — this screen reports only what is real: the
/// campaign's own live state and the two real breakdown reports (leaderboard, affiliates).
class ReferralsScreen extends StatefulWidget {
  const ReferralsScreen({super.key});

  @override
  State<ReferralsScreen> createState() => _ReferralsScreenState();
}

enum _Tab { campaign, leaderboard }

class _ReferralsScreenState extends State<ReferralsScreen> {
  late final ReferralsService _service;

  List<ReferralCampaign>? _campaigns;
  bool _campaignsFailed = false;
  ReferralSummary? _summary;
  List<ReferralLeaderboardRow>? _leaderboard;
  List<ReferralAffiliateRow>? _affiliates;
  bool _leaderboardForbidden = false;
  bool _togglingActive = false;
  _Tab _tab = _Tab.campaign;

  @override
  void initState() {
    super.initState();
    _service = ReferralsService(apiClient: context.read<AuthProvider>().apiClient);
    _load();
  }

  int get _startOfThisMonth {
    final now = DateTime.now();
    return DateTime(now.year, now.month, 1).millisecondsSinceEpoch ~/ 1000;
  }

  Future<void> _load() async {
    setState(() {
      _campaigns = null;
      _campaignsFailed = false;
    });
    final results = await Future.wait([
      _service.listCampaigns(),
      _service.summary(since: _startOfThisMonth),
      _service.leaderboard(),
      _service.affiliates(),
    ]);
    if (!mounted) return;
    setState(() {
      _campaigns = results[0] as List<ReferralCampaign>?;
      _campaignsFailed = _campaigns == null;
      _summary = results[1] as ReferralSummary?;
      _leaderboard = results[2] as List<ReferralLeaderboardRow>?;
      _affiliates = results[3] as List<ReferralAffiliateRow>?;
      // Both reads share the same narrower `operations.affiliates_read` gate — a `null` on both
      // together (rather than a plain network hiccup on one) reads as a real permission refusal.
      _leaderboardForbidden = _leaderboard == null && _affiliates == null;
    });
  }

  ReferralCampaign? get _activeCampaign {
    final list = _campaigns;
    if (list == null || list.isEmpty) return null;
    final active = list.where((c) => c.active).toList()
      ..sort((a, b) => b.createdAt.compareTo(a.createdAt));
    return active.isNotEmpty ? active.first : (list..sort((a, b) => b.createdAt.compareTo(a.createdAt))).first;
  }

  Future<void> _toggleActive(ReferralCampaign campaign) async {
    setState(() => _togglingActive = true);
    await _service.setActive(campaign.id, active: !campaign.active);
    if (!mounted) return;
    setState(() => _togglingActive = false);
    await _load();
  }

  Future<void> _openCreateSheet() async {
    final created = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _CampaignWizardSheet(service: _service),
    );
    if (created == true && mounted) _load();
  }

  Future<void> _shareAffiliateCode(ReferralAffiliateRow row) async {
    if (row.code.isEmpty) return;
    await SharePlus.instance.share(
      ShareParams(text: 'استخدم كود الإحالة "${row.code}" عند زيارتك القادمة واحصل على مكافأتك!'),
    );
  }

  Future<void> _openAddAffiliateSheet() async {
    final added = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _AffiliateWizardSheet(service: _service),
    );
    if (added == true && mounted) _load();
  }

  @override
  Widget build(BuildContext context) {
    // SCREEN-LEVEL GATE, HIDE NOT DISABLE — same precedent points_screen.dart's own FAB uses,
    // applied here to the WHOLE screen (this task's own explicit instruction): an operator
    // without `referrals.manage` sees nothing this route would otherwise render, not a disabled
    // shell of one. Real navigation entry points into this route are ALSO filtered by the same
    // capability (apps_store_screen.dart's own `kAppRows` row filter) — this is defense in depth
    // for anyone who reaches the route directly.
    return CapabilityGate(
      requires: const ['referrals.manage'],
      child: KbAnchor(id: 'referrals', child: _buildScaffold(context)),
    );
  }

  Widget _buildScaffold(BuildContext context) {
    final catalog = context.watch<NavProvider>().catalog;
    final canManage = catalog.hasAll(['referrals.manage']);
    final campaign = _activeCampaign;

    return Scaffold(
      backgroundColor: AppColors.surface0,
      floatingActionButton: CapabilityGate(
        requires: const ['referrals.manage'],
        child: KbAnchor(
          id: 'referrals.add_button',
          child: FloatingActionButton.extended(
            onPressed: _openCreateSheet,
            icon: const Icon(Icons.account_tree_rounded),
            label: const Text('حملة جديدة'),
          ),
        ),
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: CustomScrollView(
          slivers: [
            SliverToBoxAdapter(child: _ReferralHero(campaign: campaign, summary: _summary)),
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(AppSpacing.md, AppSpacing.sm, AppSpacing.md, AppSpacing.sm),
              sliver: SliverToBoxAdapter(
                child: KbAnchor(
                  id: 'referrals.main_tabs',
                  child: SegmentedFilter<_Tab>(
                    value: _tab,
                    onChanged: (v) => setState(() => _tab = v),
                    options: const [
                      SegmentedFilterOption(value: _Tab.campaign, label: 'الحملة'),
                      SegmentedFilterOption(value: _Tab.leaderboard, label: 'المتصدرون'),
                    ],
                  ),
                ),
              ),
            ),
            if (_tab == _Tab.campaign)
              ..._campaignSlivers(canManage, campaign)
            else
              ..._leaderboardSlivers(canManage),
          ],
        ),
      ),
    );
  }

  List<Widget> _campaignSlivers(bool canManage, ReferralCampaign? campaign) {
    if (_campaigns == null) {
      return const [
        SliverPadding(padding: EdgeInsets.all(AppSpacing.xl), sliver: SliverToBoxAdapter(child: AppLoadingIndicator())),
      ];
    }
    if (_campaignsFailed) {
      return [
        SliverPadding(
          padding: const EdgeInsets.all(AppSpacing.xl),
          sliver: SliverToBoxAdapter(
            child: EmptyState(icon: Icons.cloud_off_rounded, title: 'تعذّر تحميل الحملة', actionText: 'إعادة المحاولة', onAction: _load),
          ),
        ),
      ];
    }
    if (campaign == null) {
      return [
        const SliverPadding(
          padding: EdgeInsets.all(AppSpacing.xl),
          sliver: SliverToBoxAdapter(
            child: EmptyState(icon: Icons.account_tree_outlined, title: 'لا توجد حملة إحالة بعد — أنشئ أول حملة لك'),
          ),
        ),
      ];
    }
    return [
      SliverPadding(
        padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.xxl),
        sliver: SliverToBoxAdapter(
          child: _CampaignDetailCard(
            campaign: campaign,
            canManage: canManage,
            busy: _togglingActive,
            onToggleActive: () => _toggleActive(campaign),
          ),
        ),
      ),
    ];
  }

  List<Widget> _leaderboardSlivers(bool canManage) {
    if (_leaderboardForbidden) {
      return const [
        SliverPadding(
          padding: EdgeInsets.all(AppSpacing.xl),
          sliver: SliverToBoxAdapter(
            child: EmptyState(icon: Icons.lock_outline_rounded, title: 'لا تملك صلاحية عرض بيانات المتصدرين'),
          ),
        ),
      ];
    }
    if (_leaderboard == null || _affiliates == null) {
      return const [
        SliverPadding(padding: EdgeInsets.all(AppSpacing.xl), sliver: SliverToBoxAdapter(child: AppLoadingIndicator())),
      ];
    }
    if (_leaderboard!.isEmpty && _affiliates!.isEmpty) {
      return const [
        SliverPadding(
          padding: EdgeInsets.all(AppSpacing.xl),
          sliver: SliverToBoxAdapter(child: EmptyState(icon: Icons.emoji_events_outlined, title: 'لا توجد إحالات ناجحة بعد')),
        ),
      ];
    }
    return [
      if (_leaderboard!.isNotEmpty)
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.md),
          sliver: SliverToBoxAdapter(child: _LeaderboardCard(rows: _leaderboard!)),
        ),
      if (canManage)
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.sm),
          sliver: SliverToBoxAdapter(
            child: Align(
              alignment: AlignmentDirectional.centerStart,
              child: KbAnchor(
                id: 'referrals.add_affiliate_button',
                child: OutlinedButton.icon(
                  onPressed: _openAddAffiliateSheet,
                  icon: const Icon(Icons.person_add_alt_1_rounded, size: 18),
                  label: const Text('مسوّق جديد'),
                ),
              ),
            ),
          ),
        ),
      if (_affiliates!.isNotEmpty)
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.xxl),
          sliver: SliverList.separated(
            itemCount: _affiliates!.length,
            separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
            itemBuilder: (context, i) =>
                _AffiliateCard(row: _affiliates![i], onShare: () => _shareAffiliateCode(_affiliates![i])),
          ),
        ),
    ];
  }
}

/// THE NETWORK HERO — a teal-to-deep-blue gradient with faint branching nodes, this screen's own
/// distinct identity (never points_screen.dart's violet/gold vault look). Shows the live
/// active/inactive state and this month's real successful-referral count front and centre — the
/// two facts an owner actually opens this screen to check.
class _ReferralHero extends StatelessWidget {
  const _ReferralHero({required this.campaign, required this.summary});
  final ReferralCampaign? campaign;
  final ReferralSummary? summary;

  String get _modeLabel {
    switch (campaign?.mode) {
      case kReferralModeOnce:
        return 'مرة واحدة لكل عميل';
      case kReferralModeXTimes:
        return 'حتى ${campaign?.xTimesLimit ?? 0} مرات';
      case kReferralModeLifetime:
        return 'بلا حد — مدى الحياة';
      default:
        return '—';
    }
  }

  String get _capLabel {
    final c = campaign;
    if (c == null || c.usageCapLimit <= 0) return 'بلا سقف استخدام';
    final period = switch (c.usageCapPeriod) {
      'day' => 'يوميًا',
      'week' => 'أسبوعيًا',
      'month' => 'شهريًا',
      _ => '',
    };
    final scope = c.capScope == kCapScopeLifetime ? '(مدى الحياة)' : '(لكل حملة)';
    return 'سقف ${c.usageCapLimit} $period $scope';
  }

  @override
  Widget build(BuildContext context) {
    final dark = context.isDark;
    final gradient = LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: dark
          ? [const Color(0xFF0C3B3A), const Color(0xFF0A2540)]
          : [const Color(0xFF11736E), const Color(0xFF12406B)],
    );
    final active = campaign?.active ?? false;

    return Container(
      decoration: BoxDecoration(
        gradient: gradient,
        borderRadius: const BorderRadius.vertical(bottom: Radius.circular(AppRadius.card)),
        boxShadow: dark ? AppShadows.darkButton : AppShadows.button,
      ),
      child: ClipRRect(
        borderRadius: const BorderRadius.vertical(bottom: Radius.circular(AppRadius.card)),
        child: Stack(
          children: [
            // Faint branching-node motif — the network/tree identity, never the vault's coin glow.
            Positioned.directional(
              textDirection: Directionality.of(context),
              top: -20,
              end: -20,
              child: Icon(Icons.account_tree_rounded, size: 130, color: Colors.white.withValues(alpha: 0.08)),
            ),
            SafeArea(
              bottom: false,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.md, AppSpacing.lg, AppSpacing.lg),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          width: 40,
                          height: 40,
                          decoration: BoxDecoration(
                            gradient: const LinearGradient(colors: [Color(0xFF3DD9C6), Color(0xFF1FA8D8)]),
                            shape: BoxShape.circle,
                            boxShadow: [
                              BoxShadow(color: const Color(0xFF3DD9C6).withValues(alpha: 0.45), blurRadius: 12, offset: const Offset(0, 3)),
                            ],
                          ),
                          child: const Icon(Icons.share_rounded, color: Colors.white, size: 20),
                        ),
                        const SizedBox(width: AppSpacing.sm),
                        const Text('نظام الإحالة', style: AppTextStyles.displaySmall, textAlign: TextAlign.start),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.md),
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                          decoration: BoxDecoration(
                            color: (active ? const Color(0xFF3DD9C6) : Colors.white).withValues(alpha: 0.18),
                            borderRadius: BorderRadius.circular(AppRadius.pill),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(active ? Icons.play_circle_rounded : Icons.pause_circle_rounded,
                                  size: 14, color: active ? const Color(0xFF3DD9C6) : Colors.white70),
                              const SizedBox(width: 4),
                              Text(active ? 'الحملة نشطة' : 'الحملة متوقفة',
                                  style: AppTextStyles.caption.copyWith(color: Colors.white, fontWeight: FontWeight.w700)),
                            ],
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.md),
                    Text('${summary?.redeemedCount ?? '—'}',
                        style: AppTextStyles.displaySmall.copyWith(color: Colors.white, fontSize: 40, height: 1)),
                    const SizedBox(height: 2),
                    Text('إحالة ناجحة هذا الشهر', style: AppTextStyles.bodySmall.copyWith(color: Colors.white.withValues(alpha: 0.85))),
                    if (campaign != null) ...[
                      const SizedBox(height: AppSpacing.md),
                      Wrap(
                        spacing: AppSpacing.sm,
                        runSpacing: AppSpacing.xs,
                        children: [
                          _HeroChip(icon: Icons.repeat_rounded, label: _modeLabel),
                          _HeroChip(icon: Icons.speed_rounded, label: _capLabel),
                        ],
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _HeroChip extends StatelessWidget {
  const _HeroChip({required this.icon, required this.label});
  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.14), borderRadius: BorderRadius.circular(AppRadius.pill)),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 13, color: Colors.white),
          const SizedBox(width: 4),
          Text(label, style: AppTextStyles.caption.copyWith(color: Colors.white, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }
}

/// One reward type's own short, honest label — services/referrals/app/core/models.py's own
/// REWARD_TYPES, all eight, plus the two new-customer reward shapes.
String rewardTypeLabel(String type) {
  switch (type) {
    case kRewardFixedPoints: return 'نقاط ثابتة';
    case kRewardInvoicePercentage: return 'نسبة من الفاتورة';
    case kRewardPointsMatch: return 'مطابقة نقاط العميل الجديد';
    case kRewardMilestoneFreeItem: return 'خدمة مجانية عند بلوغ عدد إحالات';
    case kRewardCashbackPoints: return 'نقاط كاش باك';
    case kRewardStatusMultiplier: return 'مضاعف نقاط عند الترقية';
    case kRewardTimeBoost: return 'مضاعف نقاط بأوقات محددة';
    case kRewardMysteryBox: return 'صندوق حظ';
    case kNewCustomerDiscountPercent: return 'خصم على الفاتورة';
    case kNewCustomerWelcomePoints: return 'نقاط ترحيبية';
    default: return type;
  }
}

/// A short, real sentence describing the reward's own params — never a raw JSON dump.
String rewardDetail(String type, Map<String, dynamic> params) {
  switch (type) {
    case kRewardFixedPoints:
    case kRewardCashbackPoints:
      return '${params['points'] ?? 0} نقطة لكل إحالة ناجحة';
    case kRewardInvoicePercentage:
    case kRewardPointsMatch:
      return '${params['percent'] ?? 0}٪';
    case kRewardMilestoneFreeItem:
      return 'بعد ${params['referrals_required'] ?? 0} إحالة — ${params['service_name'] ?? ''}';
    case kRewardStatusMultiplier:
      return 'بعد ${params['referrals_required'] ?? 0} إحالة — × ${params['multiplier'] ?? 1}';
    case kRewardTimeBoost:
      return '× ${params['multiplier'] ?? 1} في أوقات محددة';
    case kRewardMysteryBox:
      return '${(params['outcomes'] as List?)?.length ?? 0} احتمالات';
    case kNewCustomerDiscountPercent:
      return '${params['percent'] ?? 0}٪ على فاتورته الأولى';
    case kNewCustomerWelcomePoints:
      return '${params['points'] ?? 0} نقطة ترحيبية';
    default:
      return '';
  }
}

/// THE CAMPAIGN'S OWN «قاعدة الطرفين» CARD — redesigned for real colour differentiation between
/// its two halves (owner's own request): the REFERRER's reward reads in the emerald "success"
/// register (the money coming BACK to the shop's own customer), the NEW CUSTOMER's reward reads
/// in the sapphire "info" register (the win handed to a stranger walking in) — never the same
/// grey row twice, so the eye sorts "whose reward is this" before it reads a single word, the
/// same "colour before number" precedent Shop.tsx's own Tile already sets for this fleet.
///
/// A THIN GRADIENT BORDER AND A FAINT CORNER MEDALLION give the card its own premium presence,
/// echoing the hero's teal-to-blue "growth" identity one level down, rather than sitting as one
/// more plain grey `AppCard` among the screen's other panels.
class _CampaignDetailCard extends StatelessWidget {
  const _CampaignDetailCard({required this.campaign, required this.canManage, required this.busy, required this.onToggleActive});
  final ReferralCampaign campaign;
  final bool canManage;
  final bool busy;
  final VoidCallback onToggleActive;

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final dark = context.isDark;
    final active = campaign.active;
    final borderTint = (dark ? const Color(0xFF3DD9C6) : const Color(0xFF12406B))
        .withValues(alpha: dark ? 0.35 : 0.16);

    return KbAnchor(
      id: 'referrals.campaign_card',
      child: Container(
        decoration: BoxDecoration(
          color: colors.surface,
          borderRadius: AppRadius.cardRadius,
          border: Border.all(color: borderTint, width: 1.4),
          boxShadow: dark ? AppShadows.darkCard : AppShadows.card,
        ),
        child: ClipRRect(
          borderRadius: AppRadius.cardRadius,
          child: Stack(
            children: [
              // A FAINT PREMIUM MEDALLION, THE SAME "BRANCHING NODE" MOTIF THE HERO ALREADY
              // OWNS — never a second, competing icon language on the same screen.
              Positioned.directional(
                textDirection: Directionality.of(context),
                top: -14,
                end: -14,
                child: Icon(Icons.workspace_premium_rounded, size: 76,
                    color: (dark ? const Color(0xFF3DD9C6) : const Color(0xFF12406B))
                        .withValues(alpha: 0.07)),
              ),
              Padding(
                padding: const EdgeInsets.all(AppSpacing.md),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Row(
                            children: [
                              const Flexible(
                                child: Text('تفاصيل حملة الإحالة', style: AppTextStyles.headlineSmall,
                                    maxLines: 1, overflow: TextOverflow.ellipsis),
                              ),
                              const SizedBox(width: AppSpacing.sm),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                decoration: BoxDecoration(
                                  color: (active ? AppColors.success : colors.textMuted).withValues(alpha: 0.14),
                                  borderRadius: BorderRadius.circular(AppRadius.pill),
                                ),
                                child: Text(active ? 'نشطة' : 'متوقفة',
                                    style: AppTextStyles.caption.copyWith(
                                        color: active ? AppColors.success : colors.textMuted,
                                        fontWeight: FontWeight.w800)),
                              ),
                            ],
                          ),
                        ),
                        if (canManage)
                          KbAnchor(
                            id: 'referrals.toggle_active',
                            child: Switch(value: campaign.active, onChanged: busy ? null : (_) => onToggleActive()),
                          ),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.md),
                    _RewardBand(
                      color: AppColors.success, onColor: AppColors.successOnSoft, softColor: AppColors.successSoft,
                      icon: Icons.card_giftcard_rounded,
                      label: 'مكافأة صاحب الإحالة',
                      value: '${rewardTypeLabel(campaign.rewardType)} — ${rewardDetail(campaign.rewardType, campaign.rewardParams)}',
                    ),
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 6),
                      child: Row(
                        children: [
                          Expanded(child: Divider(height: 1, color: colors.borderSubtle)),
                          Padding(
                            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm),
                            child: Icon(Icons.swap_vert_rounded, size: 16, color: colors.textMuted),
                          ),
                          Expanded(child: Divider(height: 1, color: colors.borderSubtle)),
                        ],
                      ),
                    ),
                    _RewardBand(
                      color: AppColors.info, onColor: AppColors.infoOnSoft, softColor: AppColors.infoSoft,
                      icon: Icons.person_add_alt_1_rounded,
                      label: 'مكافأة العميل الجديد (إلزامية — قاعدة الطرفين)',
                      value: '${rewardTypeLabel(campaign.newCustomerRewardType)} — '
                          '${rewardDetail(campaign.newCustomerRewardType, campaign.newCustomerRewardParams)}',
                    ),
                    if (campaign.minSpendMinor > 0) ...[
                      const SizedBox(height: AppSpacing.sm),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                        decoration: BoxDecoration(
                          color: colors.surfaceAlt,
                          borderRadius: BorderRadius.circular(AppRadius.pill),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.receipt_long_rounded, size: 13, color: colors.textMuted),
                            const SizedBox(width: 4),
                            Text('حد أدنى للفاتورة: ${(campaign.minSpendMinor / 100).toStringAsFixed(2)} ﷼',
                                style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
                          ],
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// One coloured half of the campaign card — a soft-tinted band with its own circular icon badge,
/// never sharing a colour with the other half. `softColor`/`onColor` are the SAME semantic
/// soft/on-soft pair the console's own Badge/KpiCard already use for success/info, so this reads
/// as one consistent brand vocabulary, not a bespoke palette invented for this one card.
class _RewardBand extends StatelessWidget {
  const _RewardBand({
    required this.color, required this.onColor, required this.softColor,
    required this.icon, required this.label, required this.value,
  });
  final Color color;
  final Color onColor;
  final Color softColor;
  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.sm),
      decoration: BoxDecoration(
        color: softColor,
        borderRadius: BorderRadius.circular(AppRadius.lg),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 34,
            height: 34,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
            child: Icon(icon, size: 17, color: Colors.white),
          ),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: AppTextStyles.caption.copyWith(color: onColor, fontWeight: FontWeight.w700)),
                const SizedBox(height: 2),
                Text(value, style: AppTextStyles.bodyMedium.copyWith(color: onColor, fontWeight: FontWeight.w700)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Ranked by REVENUE (never redemption count alone) — same preserved ordering
/// services/operations/app/core/referral_reports.py::leaderboard already returns.
class _LeaderboardCard extends StatelessWidget {
  const _LeaderboardCard({required this.rows});
  final List<ReferralLeaderboardRow> rows;

  static const _medalColors = [Color(0xFF3DD9C6), Color(0xFFB8C0CC), Color(0xFFCD8B5C), Color(0xFF8E8E93), Color(0xFF8E8E93)];

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final maxRevenue = rows.map((e) => e.revenueMinor).fold(1, (a, b) => a > b ? a : b);
    return KbAnchor(
      id: 'referrals.leaderboard',
      child: AppCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('الأعلى إيرادًا', style: AppTextStyles.labelMedium),
            const SizedBox(height: AppSpacing.xs),
            Text('مرتّبون بالإيراد الفعلي الذي جلبوه، لا بعدد مرات الاستخدام فقط',
                style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
            const SizedBox(height: AppSpacing.md),
            for (var i = 0; i < rows.length; i++)
              Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.md),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    Container(
                      width: 30,
                      height: 30,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: _medalColors[i % _medalColors.length].withValues(alpha: 0.18),
                        border: Border.all(color: _medalColors[i % _medalColors.length], width: 1.5),
                      ),
                      child: Center(
                        child: i < 3
                            ? Icon(Icons.emoji_events_rounded, size: 15, color: _medalColors[i])
                            : Text('${i + 1}', style: AppTextStyles.caption.copyWith(fontWeight: FontWeight.w800, color: _medalColors[i % _medalColors.length])),
                      ),
                    ),
                    const SizedBox(width: AppSpacing.sm),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Expanded(
                                child: Text(rows[i].referrerPhone.isNotEmpty ? rows[i].referrerPhone : '—',
                                    maxLines: 1, overflow: TextOverflow.ellipsis,
                                    style: AppTextStyles.bodySmall.copyWith(fontWeight: FontWeight.w700)),
                              ),
                              Text('${(rows[i].revenueMinor / 100).toStringAsFixed(0)} ﷼',
                                  style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
                            ],
                          ),
                          const SizedBox(height: 4),
                          ClipRRect(
                            borderRadius: BorderRadius.circular(AppRadius.pill),
                            child: LinearProgressIndicator(
                              value: rows[i].revenueMinor / maxRevenue,
                              minHeight: 6,
                              backgroundColor: colors.surfaceAlt,
                              valueColor: AlwaysStoppedAnimation(_medalColors[i % _medalColors.length]),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}

/// One affiliate's own real balance (services/operations/app/core/affiliates.py's own row) — with
/// a real native share sheet for their code, never a copy-to-clipboard-only affordance.
class _AffiliateCard extends StatelessWidget {
  const _AffiliateCard({required this.row, required this.onShare});
  final ReferralAffiliateRow row;
  final VoidCallback onShare;

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    return KbAnchor(
      id: 'referrals.affiliate_card',
      child: Container(
        padding: const EdgeInsets.all(AppSpacing.md),
        decoration: BoxDecoration(
          color: colors.surface,
          borderRadius: AppRadius.cardRadius,
          border: Border.all(color: colors.borderSubtle),
          boxShadow: context.isDark ? AppShadows.darkCard : AppShadows.card,
        ),
        child: Row(
          children: [
            Container(
              width: 44,
              height: 44,
              decoration: const BoxDecoration(
                gradient: LinearGradient(colors: [Color(0xFF3DD9C6), Color(0xFF12406B)]),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.handshake_rounded, color: Colors.white, size: 20),
            ),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(row.code.isNotEmpty ? row.code : row.phone,
                            maxLines: 1, overflow: TextOverflow.ellipsis,
                            style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w700)),
                      ),
                      if (!row.active)
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                          decoration: BoxDecoration(color: colors.surfaceAlt, borderRadius: BorderRadius.circular(AppRadius.pill)),
                          child: Text('متوقف', style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
                        ),
                    ],
                  ),
                  Text('رصيد غير مسوّى: ${row.unsettledPoints} نقطة — إجمالي مكتسب: ${row.totalEarnedPoints}',
                      maxLines: 1, overflow: TextOverflow.ellipsis,
                      style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
                ],
              ),
            ),
            IconButton(
              onPressed: row.code.isNotEmpty ? onShare : null,
              icon: const Icon(Icons.ios_share_rounded, size: 20),
              tooltip: 'مشاركة الكود',
            ),
          ],
        ),
      ),
    );
  }
}

/// THE MULTI-STEP CREATION SHEET — mode selection, then rewards config. Respects
/// [appSheetMaxHeight] exactly like every other sheet in this app (`ci/check_mobile_sheet_max_height.py`
/// enforces this at the gate). CAMPAIGN TERMS ARE IMMUTABLE ONCE CREATED — this sheet is
/// creation-only, there is no equivalent edit sheet.
class _CampaignWizardSheet extends StatefulWidget {
  const _CampaignWizardSheet({required this.service});
  final ReferralsService service;

  @override
  State<_CampaignWizardSheet> createState() => _CampaignWizardSheetState();
}

class _CampaignWizardSheetState extends State<_CampaignWizardSheet> {
  int _step = 0; // 0 = mode, 1 = rewards
  String _mode = kReferralModeOnce;
  int _xTimesLimit = 3;
  String _capScope = kCapScopeCampaign;
  String _capPeriod = '';
  final _capLimitController = TextEditingController();
  final _minSpendController = TextEditingController();

  String _rewardType = kRewardFixedPoints;
  final _rewardPointsController = TextEditingController(text: '50');
  final _rewardPercentController = TextEditingController(text: '10');

  String _newCustomerType = kNewCustomerWelcomePoints;
  final _newCustomerPointsController = TextEditingController(text: '20');
  final _newCustomerPercentController = TextEditingController(text: '10');

  // WHO MAY REDEEM (owner instruction, 2026-09-27) — a real, independent question from `_mode`
  // above (that caps how many times the REFERRER's own code pays out).
  String _eligibility = kEligibilityNew;
  final _eligibilityMaxVisitsController = TextEditingController(text: '1');

  bool _saving = false;
  String? _error;

  @override
  void dispose() {
    _capLimitController.dispose();
    _minSpendController.dispose();
    _rewardPointsController.dispose();
    _rewardPercentController.dispose();
    _newCustomerPointsController.dispose();
    _newCustomerPercentController.dispose();
    _eligibilityMaxVisitsController.dispose();
    super.dispose();
  }

  Map<String, dynamic> get _rewardParams {
    switch (_rewardType) {
      case kRewardInvoicePercentage:
      case kRewardPointsMatch:
        return {'percent': int.tryParse(_rewardPercentController.text.trim()) ?? 0};
      default:
        return {'points': int.tryParse(_rewardPointsController.text.trim()) ?? 0};
    }
  }

  Map<String, dynamic> get _newCustomerParams => _newCustomerType == kNewCustomerDiscountPercent
      ? {'percent': int.tryParse(_newCustomerPercentController.text.trim()) ?? 0}
      : {'points': int.tryParse(_newCustomerPointsController.text.trim()) ?? 0};

  Future<void> _submit() async {
    setState(() { _saving = true; _error = null; });
    final reason = await widget.service.createCampaign(
      mode: _mode,
      rewardType: _rewardType,
      rewardParams: _rewardParams,
      newCustomerRewardType: _newCustomerType,
      newCustomerRewardParams: _newCustomerParams,
      xTimesLimit: _mode == kReferralModeXTimes ? _xTimesLimit : 0,
      minSpendMinor: ((double.tryParse(_minSpendController.text.trim()) ?? 0) * 100).round(),
      usageCapPeriod: _capPeriod,
      usageCapLimit: int.tryParse(_capLimitController.text.trim()) ?? 0,
      capScope: _capScope,
      beneficiaryEligibility: _eligibility,
      beneficiaryMaxVisits: _eligibility == kEligibilityMaxVisits
          ? (int.tryParse(_eligibilityMaxVisitsController.text.trim()) ?? 1) : 0,
    );
    if (!mounted) return;
    if (reason == null) {
      Navigator.of(context).pop(true);
      return;
    }
    setState(() { _saving = false; _error = reason.isNotEmpty ? reason : 'تعذّر حفظ الحملة'; });
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: Container(
        constraints: BoxConstraints(maxHeight: appSheetMaxHeight(context)),
        padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.lg, AppSpacing.lg, AppSpacing.xl),
        decoration: const BoxDecoration(
          color: AppColors.surface1,
          borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
        ),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(_step == 0 ? 'حملة إحالة جديدة — النمط' : 'المكافآت', style: AppTextStyles.headlineSmall),
              const SizedBox(height: AppSpacing.lg),
              if (_step == 0) ..._modeStep() else ..._rewardsStep(),
              if (_error != null) ...[
                const SizedBox(height: AppSpacing.sm),
                AppAlert(type: AlertType.error, message: _error!),
              ],
              const SizedBox(height: AppSpacing.lg),
              Row(
                children: [
                  if (_step == 1)
                    Expanded(
                      child: KbAnchor(
                        id: 'referrals.wizard_back_button',
                        child: OutlinedButton(onPressed: _saving ? null : () => setState(() => _step = 0), child: const Text('السابق')),
                      ),
                    ),
                  if (_step == 1) const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: PrimaryButton(
                      text: _step == 0 ? 'التالي' : 'إنشاء الحملة',
                      isLoading: _saving,
                      onPressed: _saving ? null : () => _step == 0 ? setState(() => _step = 1) : _submit(),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  List<Widget> _modeStep() {
    return [
      Text('عدد مرات مكافأة العميل الواحد', style: AppTextStyles.bodySmall.copyWith(color: AppColors.textSecondary)),
      const SizedBox(height: AppSpacing.xs),
      KbAnchor(
        id: 'referrals.wizard_mode',
        child: SegmentedButton<String>(
          segments: const [
            ButtonSegment(value: kReferralModeOnce, label: Text('مرة واحدة')),
            ButtonSegment(value: kReferralModeXTimes, label: Text('عدد محدد')),
            ButtonSegment(value: kReferralModeLifetime, label: Text('بلا حد')),
          ],
          selected: {_mode},
          onSelectionChanged: (v) => setState(() => _mode = v.first),
        ),
      ),
      if (_mode == kReferralModeXTimes) ...[
        const SizedBox(height: AppSpacing.md),
        Text('عدد المرات: $_xTimesLimit', style: AppTextStyles.bodySmall),
        Slider(
          value: _xTimesLimit.toDouble(), min: 1, max: 20, divisions: 19,
          label: '$_xTimesLimit', onChanged: (v) => setState(() => _xTimesLimit = v.round()),
        ),
      ],
      const SizedBox(height: AppSpacing.md),
      Text('سقف الاستخدام (اختياري)', style: AppTextStyles.bodySmall.copyWith(color: AppColors.textSecondary)),
      const SizedBox(height: AppSpacing.xs),
      Row(
        children: [
          Expanded(
            child: KbAnchor(
              id: 'referrals.wizard_cap_limit_field',
              child: TextField(
                controller: _capLimitController,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(isDense: true, hintText: 'عدد الإحالات'),
              ),
            ),
          ),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: DropdownButtonFormField<String>(
              initialValue: _capPeriod.isEmpty ? null : _capPeriod,
              decoration: const InputDecoration(isDense: true, hintText: 'الفترة'),
              items: const [
                DropdownMenuItem(value: 'day', child: Text('يوميًا')),
                DropdownMenuItem(value: 'week', child: Text('أسبوعيًا')),
                DropdownMenuItem(value: 'month', child: Text('شهريًا')),
              ],
              onChanged: (v) => setState(() => _capPeriod = v ?? ''),
            ),
          ),
        ],
      ),
      const SizedBox(height: AppSpacing.md),
      Text('نطاق السقف', style: AppTextStyles.bodySmall.copyWith(color: AppColors.textSecondary)),
      const SizedBox(height: AppSpacing.xs),
      SegmentedButton<String>(
        segments: const [
          ButtonSegment(value: kCapScopeCampaign, label: Text('لكل حملة')),
          ButtonSegment(value: kCapScopeLifetime, label: Text('مدى الحياة')),
        ],
        selected: {_capScope},
        onSelectionChanged: (v) => setState(() => _capScope = v.first),
      ),
      const SizedBox(height: AppSpacing.md),
      KbAnchor(
        id: 'referrals.wizard_min_spend_field',
        child: TextField(
          controller: _minSpendController,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          decoration: const InputDecoration(isDense: true, hintText: 'حد أدنى للفاتورة (ريال، اختياري)'),
        ),
      ),
    ];
  }

  List<Widget> _rewardsStep() {
    return [
      Text('مكافأة صاحب الإحالة', style: AppTextStyles.bodySmall.copyWith(color: AppColors.textSecondary)),
      const SizedBox(height: AppSpacing.xs),
      KbAnchor(
        id: 'referrals.wizard_reward_type',
        child: DropdownButtonFormField<String>(
          initialValue: _rewardType,
          isExpanded: true,
          decoration: const InputDecoration(isDense: true),
          items: [for (final t in kReferrerRewardTypes) DropdownMenuItem(value: t, child: Text(rewardTypeLabel(t)))],
          onChanged: (v) => setState(() => _rewardType = v ?? _rewardType),
        ),
      ),
      const SizedBox(height: AppSpacing.sm),
      KbAnchor(
        id: 'referrals.wizard_reward_value_field',
        child: (_rewardType == kRewardInvoicePercentage || _rewardType == kRewardPointsMatch)
            ? TextField(
                controller: _rewardPercentController,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(isDense: true, hintText: 'النسبة %'),
              )
            : TextField(
                controller: _rewardPointsController,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(isDense: true, hintText: 'عدد النقاط'),
              ),
      ),
      const SizedBox(height: AppSpacing.lg),
      const Divider(),
      const SizedBox(height: AppSpacing.sm),
      Text('مكافأة العميل الجديد — إلزامية (قاعدة الطرفين)', style: AppTextStyles.bodySmall.copyWith(color: AppColors.textSecondary)),
      const SizedBox(height: AppSpacing.xs),
      KbAnchor(
        id: 'referrals.wizard_new_customer_type',
        child: SegmentedButton<String>(
          segments: const [
            ButtonSegment(value: kNewCustomerWelcomePoints, label: Text('نقاط ترحيبية')),
            ButtonSegment(value: kNewCustomerDiscountPercent, label: Text('خصم على الفاتورة')),
          ],
          selected: {_newCustomerType},
          onSelectionChanged: (v) => setState(() => _newCustomerType = v.first),
        ),
      ),
      const SizedBox(height: AppSpacing.sm),
      KbAnchor(
        id: 'referrals.wizard_new_customer_value_field',
        child: (_newCustomerType == kNewCustomerDiscountPercent)
            ? TextField(
                controller: _newCustomerPercentController,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(isDense: true, hintText: 'النسبة %'),
              )
            : TextField(
                controller: _newCustomerPointsController,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(isDense: true, hintText: 'عدد النقاط'),
              ),
      ),
      const SizedBox(height: AppSpacing.lg),
      const Divider(),
      const SizedBox(height: AppSpacing.sm),
      Text('من يقدر يستخدم الكود', style: AppTextStyles.bodySmall.copyWith(color: AppColors.textSecondary)),
      const SizedBox(height: AppSpacing.xs),
      KbAnchor(
        id: 'referrals.wizard_eligibility',
        child: SegmentedButton<String>(
          segments: const [
            ButtonSegment(value: kEligibilityNew, label: Text('عميل جديد')),
            ButtonSegment(value: kEligibilityMaxVisits, label: Text('عدد زيارات')),
            ButtonSegment(value: kEligibilityOpen, label: Text('مفتوح')),
          ],
          selected: {_eligibility},
          onSelectionChanged: (v) => setState(() => _eligibility = v.first),
        ),
      ),
      if (_eligibility == kEligibilityMaxVisits) ...[
        const SizedBox(height: AppSpacing.sm),
        KbAnchor(
          id: 'referrals.wizard_max_visits_field',
          child: TextField(
            controller: _eligibilityMaxVisitsController,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(isDense: true, hintText: 'أقصى عدد زيارات مسموح'),
          ),
        ),
      ],
    ];
  }
}

/// The marketer/influencer tier's own add sheet — the backend route (`POST /api/v1/affiliates`,
/// `affiliate.add`) already existed with zero mobile UI before this. [appSheetMaxHeight] exactly
/// like every other sheet in this app. AN AFFILIATE'S TERMS ARE FULLY INDEPENDENT OF ANY CAMPAIGN
/// (core/affiliates.py's own module docstring) — this sheet never reads or touches a campaign.
class _AffiliateWizardSheet extends StatefulWidget {
  const _AffiliateWizardSheet({required this.service});
  final ReferralsService service;

  @override
  State<_AffiliateWizardSheet> createState() => _AffiliateWizardSheetState();
}

class _AffiliateWizardSheetState extends State<_AffiliateWizardSheet> {
  final _phoneController = TextEditingController();
  final _codeController = TextEditingController();
  final _discountController = TextEditingController(text: '15');

  String _rewardType = kAffiliateRewardFixedPoints;
  final _rewardPointsController = TextEditingController(text: '40');
  final _rewardPercentController = TextEditingController(text: '10');

  String _eligibility = kEligibilityNew;
  final _eligibilityMaxVisitsController = TextEditingController(text: '1');

  bool _saving = false;
  String? _error;

  @override
  void dispose() {
    _phoneController.dispose();
    _codeController.dispose();
    _discountController.dispose();
    _rewardPointsController.dispose();
    _rewardPercentController.dispose();
    _eligibilityMaxVisitsController.dispose();
    super.dispose();
  }

  Map<String, dynamic> get _rewardParams => _rewardType == kAffiliateRewardInvoicePercentage
      ? {'percent': int.tryParse(_rewardPercentController.text.trim()) ?? 0}
      : {'points': int.tryParse(_rewardPointsController.text.trim()) ?? 0};

  Future<void> _submit() async {
    setState(() { _saving = true; _error = null; });
    final reason = await widget.service.addAffiliate(
      phone: _phoneController.text.trim(),
      code: _codeController.text.trim(),
      discountPercent: int.tryParse(_discountController.text.trim()) ?? 0,
      rewardType: _rewardType,
      rewardParams: _rewardParams,
      beneficiaryEligibility: _eligibility,
      beneficiaryMaxVisits: _eligibility == kEligibilityMaxVisits
          ? (int.tryParse(_eligibilityMaxVisitsController.text.trim()) ?? 1) : 0,
    );
    if (!mounted) return;
    if (reason == null) {
      Navigator.of(context).pop(true);
      return;
    }
    setState(() { _saving = false; _error = reason.isNotEmpty ? reason : 'تعذّر إضافة المسوّق'; });
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: Container(
        constraints: BoxConstraints(maxHeight: appSheetMaxHeight(context)),
        padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.lg, AppSpacing.lg, AppSpacing.xl),
        decoration: const BoxDecoration(
          color: AppColors.surface1,
          borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
        ),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('مسوّق جديد', style: AppTextStyles.headlineSmall),
              const SizedBox(height: AppSpacing.lg),
              KbAnchor(
                id: 'referrals.add_affiliate_sheet.phone_field',
                child: TextField(
                  controller: _phoneController,
                  keyboardType: TextInputType.phone,
                  decoration: const InputDecoration(isDense: true, hintText: 'جوال المسوّق'),
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              KbAnchor(
                id: 'referrals.add_affiliate_sheet.code_field',
                child: TextField(
                  controller: _codeController,
                  textCapitalization: TextCapitalization.characters,
                  decoration: const InputDecoration(isDense: true, hintText: 'كوده الخاص'),
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              KbAnchor(
                id: 'referrals.add_affiliate_sheet.discount_field',
                child: TextField(
                  controller: _discountController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(isDense: true, hintText: 'خصم العميل الجديد %'),
                ),
              ),
              const SizedBox(height: AppSpacing.lg),
              Text('نوع مكافأة المسوّق', style: AppTextStyles.bodySmall.copyWith(color: AppColors.textSecondary)),
              const SizedBox(height: AppSpacing.xs),
              SegmentedButton<String>(
                segments: [
                  for (final r in kAffiliateRewardTypes) ButtonSegment(value: r, label: Text(rewardTypeLabel(r))),
                ],
                selected: {_rewardType},
                onSelectionChanged: (v) => setState(() => _rewardType = v.first),
              ),
              const SizedBox(height: AppSpacing.sm),
              KbAnchor(
                id: 'referrals.add_affiliate_sheet.reward_amount_field',
                child: (_rewardType == kAffiliateRewardInvoicePercentage)
                    ? TextField(
                        controller: _rewardPercentController,
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(isDense: true, hintText: 'النسبة %'),
                      )
                    : TextField(
                        controller: _rewardPointsController,
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(isDense: true, hintText: 'عدد النقاط'),
                      ),
              ),
              const SizedBox(height: AppSpacing.lg),
              const Divider(),
              const SizedBox(height: AppSpacing.sm),
              Text('من يقدر يستخدم كود هذا المسوّق', style: AppTextStyles.bodySmall.copyWith(color: AppColors.textSecondary)),
              const SizedBox(height: AppSpacing.xs),
              SegmentedButton<String>(
                segments: const [
                  ButtonSegment(value: kEligibilityNew, label: Text('عميل جديد')),
                  ButtonSegment(value: kEligibilityMaxVisits, label: Text('عدد زيارات')),
                  ButtonSegment(value: kEligibilityOpen, label: Text('مفتوح')),
                ],
                selected: {_eligibility},
                onSelectionChanged: (v) => setState(() => _eligibility = v.first),
              ),
              if (_eligibility == kEligibilityMaxVisits) ...[
                const SizedBox(height: AppSpacing.sm),
                KbAnchor(
                  id: 'referrals.add_affiliate_sheet.max_visits_field',
                  child: TextField(
                    controller: _eligibilityMaxVisitsController,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(isDense: true, hintText: 'أقصى عدد زيارات مسموح'),
                  ),
                ),
              ],
              if (_error != null) ...[
                const SizedBox(height: AppSpacing.sm),
                AppAlert(type: AlertType.error, message: _error!),
              ],
              const SizedBox(height: AppSpacing.lg),
              PrimaryButton(
                text: 'إضافة المسوّق',
                isLoading: _saving,
                onPressed: _saving ? null : _submit,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
