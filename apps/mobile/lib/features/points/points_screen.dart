import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/providers/nav_provider.dart';
import 'package:raje3_mobile/core/services/points_service.dart';
import 'package:raje3_mobile/core/services/services_catalogue_service.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/models/points_model.dart';
import 'package:raje3_mobile/models/service_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/widgets/capability_gate.dart';
import 'package:raje3_mobile/widgets/effects/game_effects.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';

/// «نقاط الولاء» — the shop's own reward catalogue: what a customer's points actually buy, and how the
/// programme is doing. Mirrors apps/console/src/screens/Points.tsx's own DATA contract exactly
/// (`loyalty.rewards.list/create/update`, `loyalty.report`) — every field real, nothing invented
/// — but built with an ENTIRELY different visual language: a treasure-vault identity (deep violet
/// + gold, tiered reward "cards" by cost, a real leaderboard), because a rewards catalogue is the
/// one screen in this whole app that genuinely IS a game to the customer redeeming it, and the
/// owner configuring it deserves to feel that too — never a plain settings table.
///
/// EARNING SETTINGS (points per service/group/general) ARE DELIBERATELY NOT REBUILT HERE — same
/// real data, same real routes, already built under «خدماتي ومنتجاتي»
/// (services_screen.dart's own reminders/loyalty tree). This screen offers a real link to it
/// instead of a second editor for the same numbers, which is how two on-screen editors for one
/// value quietly drift apart — one is the truth and the screen is never told which.
///
/// THE EARNING *MODE* (points per visit vs. per riyal spent) IS BUILT HERE, though, since it is
/// the programme's own real switch (`loyalty.settings.mode`) and belongs beside the report that
/// explains what it changes, not buried inside the catalogue screen.
class PointsScreen extends StatefulWidget {
  const PointsScreen({super.key});

  @override
  State<PointsScreen> createState() => _PointsScreenState();
}

enum _Tab { rewards, leaderboard }

class _PointsScreenState extends State<PointsScreen> {
  late final PointsService _service;
  late final ServicesCatalogueService _catalogueService;

  List<Reward>? _rewards;
  bool _rewardsFailed = false;
  LoyaltyReport? _report;
  List<ServiceItem> _services = const [];
  EarnSettingsTree? _earnTree;
  bool _savingMode = false;
  String? _modeError;
  _Tab _tab = _Tab.rewards;

  @override
  void initState() {
    super.initState();
    final apiClient = context.read<AuthProvider>().apiClient;
    _service = PointsService(apiClient: apiClient);
    _catalogueService = ServicesCatalogueService(apiClient: apiClient);
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _rewards = null;
      _rewardsFailed = false;
    });
    final results = await Future.wait([
      _service.list(),
      _service.report(),
      _catalogueService.list(includeRetired: false),
      _catalogueService.earnSettings(),
    ]);
    if (!mounted) return;
    setState(() {
      _rewards = results[0] as List<Reward>?;
      _rewardsFailed = _rewards == null;
      _report = results[1] as LoyaltyReport?;
      _services = (results[2] as List<ServiceItem>?) ?? const [];
      _earnTree = results[3] as EarnSettingsTree?;
    });
  }

  Future<void> _openAddSheet() async {
    final created = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _RewardSheet(service: _service, services: _services),
    );
    if (created == true && mounted) {
      GameEffects.celebrate(context);
      _load();
    }
  }

  Future<void> _setMode(String mode) async {
    setState(() {
      _savingMode = true;
      _modeError = null;
    });
    final reason = await _catalogueService.setEarnMode(
        mode: mode, pointsPerRiyal: _earnTree?.pointsPerRiyal ?? 1);
    if (!mounted) return;
    if (reason == null) {
      final tree = await _catalogueService.earnSettings();
      if (!mounted) return;
      setState(() {
        _savingMode = false;
        if (tree != null) _earnTree = tree;
      });
      return;
    }
    final s = S.of(context)!;
    setState(() {
      _savingMode = false;
      _modeError = reason.isNotEmpty ? reason : s.pointsSaveFailed;
    });
  }

  Future<void> _openEditSheet(Reward r) async {
    final changed = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _RewardSheet(service: _service, services: _services, existing: r),
    );
    if (changed == true && mounted) _load();
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final catalog = context.watch<NavProvider>().catalog;
    // REAL GAP FOUND AND CLOSED HERE (2026-09-26, permission-gate unification pass) — a reward
    // card's tap opened a fully editable/savable sheet regardless of `loyalty.rewards.update`,
    // matching the console's own `canEdit` gate (Points.tsx) which this mobile screen had never
    // mirrored. Disables the tap rather than hiding the card entirely — there is no separate
    // read-only view mode built here, same reasoning `procedures_tab.dart`'s own edit-disable
    // already uses, never `CapabilityGate` (which hides, not disables).
    final canEditRewards = catalog.hasAll(['loyalty.rewards.update']);

    return KbAnchor(
      id: 'points',
      child: Scaffold(
        backgroundColor: AppColors.surface0,
        floatingActionButton: CapabilityGate(
          requires: const ['loyalty.rewards.create'],
          child: KbAnchor(
            id: 'points.add_button',
            child: FloatingActionButton.extended(
              onPressed: _openAddSheet,
              icon: const Icon(Icons.auto_awesome_rounded),
              label: Text(s.pointsAddReward),
            ),
          ),
        ),
        body: RefreshIndicator(
          onRefresh: _load,
          child: CustomScrollView(
            slivers: [
              SliverToBoxAdapter(child: _PointsHero(report: _report)),
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(AppSpacing.md, AppSpacing.sm, AppSpacing.md, AppSpacing.sm),
                sliver: SliverToBoxAdapter(
                  child: KbAnchor(
                    id: 'points.main_tabs',
                    child: SegmentedFilter<_Tab>(
                      value: _tab,
                      onChanged: (v) => setState(() => _tab = v),
                      options: [
                        SegmentedFilterOption(value: _Tab.rewards, label: s.pointsTabRewards),
                        SegmentedFilterOption(value: _Tab.leaderboard, label: s.pointsTabLeaderboard),
                      ],
                    ),
                  ),
                ),
              ),
              if (_earnTree != null)
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.sm),
                  sliver: SliverToBoxAdapter(
                    child: _EarningSettingsCard(
                      tree: _earnTree!,
                      saving: _savingMode,
                      error: _modeError,
                      canSetMode: catalog.hasAll(['loyalty.settings.mode']),
                      onModeChanged: _setMode,
                      onOpenEarnSettings: () => context.goNamed('services'),
                    ),
                  ),
                ),
              if (_tab == _Tab.rewards)
                ..._rewardsSlivers(s, canEditRewards)
              else
                ..._leaderboardSlivers(s),
            ],
          ),
        ),
      ),
    );
  }

  List<Widget> _rewardsSlivers(S s, bool canEditRewards) {
    if (_rewards == null) {
      return [
        const SliverPadding(
            padding: EdgeInsets.all(AppSpacing.xl), sliver: SliverToBoxAdapter(child: AppLoadingIndicator())),
      ];
    }
    if (_rewardsFailed) {
      return [
        SliverPadding(
          padding: const EdgeInsets.all(AppSpacing.xl),
          sliver: SliverToBoxAdapter(
            child: EmptyState(
              icon: Icons.cloud_off_rounded,
              title: s.pointsLoadFailedTitle,
              actionText: s.mobileRequestsRetry,
              onAction: _load,
            ),
          ),
        ),
      ];
    }
    if (_rewards!.isEmpty) {
      return [
        SliverPadding(
          padding: const EdgeInsets.all(AppSpacing.xl),
          sliver: SliverToBoxAdapter(
            child: EmptyState(icon: Icons.card_giftcard_outlined, title: s.pointsRewardsEmpty),
          ),
        ),
      ];
    }
    final sorted = [..._rewards!]..sort((a, b) {
        if (a.active != b.active) return a.active ? -1 : 1;
        return a.cost.compareTo(b.cost);
      });
    return [
      SliverPadding(
        padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.xxl),
        sliver: SliverList.separated(
          itemCount: sorted.length,
          separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
          itemBuilder: (context, i) => _RewardCard(
            reward: sorted[i],
            serviceName: sorted[i].type == RewardType.service
                ? (_services.where((sv) => sv.id == sorted[i].serviceId).map((sv) => sv.name).firstOrNull ?? '')
                : '',
            onTap: canEditRewards ? () => _openEditSheet(sorted[i]) : null,
          ),
        ),
      ),
    ];
  }

  List<Widget> _leaderboardSlivers(S s) {
    final report = _report;
    if (report == null) {
      return [
        const SliverPadding(
            padding: EdgeInsets.all(AppSpacing.xl), sliver: SliverToBoxAdapter(child: AppLoadingIndicator())),
      ];
    }
    if (report.topRewards.isEmpty) {
      return [
        SliverPadding(
          padding: const EdgeInsets.all(AppSpacing.xl),
          sliver: SliverToBoxAdapter(
            child: EmptyState(icon: Icons.emoji_events_outlined, title: s.pointsLeaderboardEmpty),
          ),
        ),
      ];
    }
    return [
      SliverPadding(
        padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.xxl),
        sliver: SliverToBoxAdapter(child: _LeaderboardCard(topRewards: report.topRewards)),
      ),
    ];
  }
}

extension _FirstOrNull<T> on Iterable<T> {
  T? get firstOrNull => isEmpty ? null : first;
}

/// The vault hero — deep violet→gold, a glowing coin stack, the outstanding balance as the one
/// number that matters most (what the shop still owes its customers in points), never a plain KPI
/// row. `expiredShare` above a real threshold gets its own honest warning chip — the report's own
/// "programme is annoying customers, not holding them" signal, never hidden.
class _PointsHero extends StatelessWidget {
  const _PointsHero({required this.report});
  final LoyaltyReport? report;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final dark = context.isDark;
    final gradient = LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: dark
          ? [const Color(0xFF3D1E6D), const Color(0xFF15092B)]
          : [const Color(0xFF5B2A9E), const Color(0xFF2A1152)],
    );
    final report = this.report;
    final expiredWarn = report != null && report.expiredShare >= 0.15;

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
            Positioned.directional(
              textDirection: Directionality.of(context),
              top: -36,
              end: -30,
              child: Container(
                width: 150,
                height: 150,
                decoration: BoxDecoration(
                    shape: BoxShape.circle, color: const Color(0xFFF6B93B).withValues(alpha: 0.16)),
              ),
            ),
            Positioned.directional(
              textDirection: Directionality.of(context),
              bottom: -50,
              start: -30,
              child: Container(
                width: 130,
                height: 130,
                decoration:
                    BoxDecoration(shape: BoxShape.circle, color: Colors.white.withValues(alpha: 0.05)),
              ),
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
                            gradient: const LinearGradient(
                                colors: [Color(0xFFF6B93B), Color(0xFFE08E0B)]),
                            shape: BoxShape.circle,
                            boxShadow: [
                              BoxShadow(
                                  color: const Color(0xFFF6B93B).withValues(alpha: 0.5),
                                  blurRadius: 12,
                                  offset: const Offset(0, 3)),
                            ],
                          ),
                          child: const Icon(Icons.diamond_rounded, color: Colors.white, size: 20),
                        ),
                        const SizedBox(width: AppSpacing.sm),
                        Text(s.pointsTitle,
                            style: AppTextStyles.displaySmall.copyWith(color: Colors.white)),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.md),
                    Text(
                      report != null ? '${report.outstanding}' : '—',
                      style: AppTextStyles.displaySmall
                          .copyWith(color: Colors.white, fontSize: 40, height: 1),
                    ),
                    const SizedBox(height: 2),
                    Text(s.pointsOutstandingHint,
                        style:
                            AppTextStyles.bodySmall.copyWith(color: Colors.white.withValues(alpha: 0.85))),
                    const SizedBox(height: AppSpacing.md),
                    Row(
                      children: [
                        _HeroStat(
                          icon: Icons.redeem_rounded,
                          label: s.pointsRedemptionsCount(report?.redemptions ?? 0),
                        ),
                        const SizedBox(width: AppSpacing.sm),
                        _HeroStat(
                          icon: Icons.groups_rounded,
                          label: s.pointsCustomersCount(report?.customers ?? 0),
                        ),
                      ],
                    ),
                    if (expiredWarn) ...[
                      const SizedBox(height: AppSpacing.md),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.16),
                          borderRadius: BorderRadius.circular(AppRadius.pill),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Icon(Icons.warning_amber_rounded, size: 14, color: Color(0xFFF6B93B)),
                            const SizedBox(width: 4),
                            Text(
                              s.pointsExpiredWarning((report.expiredShare * 100).round()),
                              style: AppTextStyles.caption
                                  .copyWith(color: Colors.white, fontWeight: FontWeight.w700),
                            ),
                          ],
                        ),
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

class _HeroStat extends StatelessWidget {
  const _HeroStat({required this.icon, required this.label});
  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(AppRadius.pill),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 13, color: Colors.white),
          const SizedBox(width: 4),
          Text(label,
              style: AppTextStyles.caption.copyWith(color: Colors.white, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }
}

/// The cost tier's own colour — a pure game convention (bronze/silver/gold/diamond), never a
/// product fact: a reward's real data has no "tier" field, this is purely how far a customer
/// climbs to reach it, drawn the way any points shop draws that ladder.
({Color color, IconData icon}) _tierFor(int cost) {
  if (cost >= 600) return (color: const Color(0xFF7C5CFC), icon: Icons.diamond_rounded);
  if (cost >= 300) return (color: const Color(0xFFF6B93B), icon: Icons.emoji_events_rounded);
  if (cost >= 100) return (color: const Color(0xFFB8C0CC), icon: Icons.military_tech_rounded);
  return (color: const Color(0xFFCD8B5C), icon: Icons.stars_rounded);
}

class _RewardCard extends StatelessWidget {
  const _RewardCard({required this.reward, required this.serviceName, required this.onTap});
  final Reward reward;
  final String serviceName;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final colors = context.appColors;
    final dark = context.isDark;
    final tier = _tierFor(reward.cost);
    final active = reward.active;

    final typeIcon = switch (reward.type) {
      RewardType.service => Icons.build_rounded,
      RewardType.discount => Icons.percent_rounded,
      RewardType.item => Icons.card_giftcard_rounded,
    };
    final subtitle = switch (reward.type) {
      RewardType.service => serviceName.isNotEmpty ? s.pointsRewardServiceHint(serviceName) : '',
      RewardType.discount => s.pointsRewardDiscountHint((reward.discountHalalas / 100).toStringAsFixed(2)),
      RewardType.item => s.pointsRewardItemHint,
    };

    return KbAnchor(
      id: 'points.reward_card',
      child: Opacity(
        opacity: active ? 1 : 0.55,
        child: Material(
          color: Colors.transparent,
          borderRadius: AppRadius.cardRadius,
          child: InkWell(
            borderRadius: AppRadius.cardRadius,
            onTap: onTap,
            child: Container(
              decoration: BoxDecoration(
                color: colors.surface,
                borderRadius: AppRadius.cardRadius,
                border: Border.all(color: active ? tier.color.withValues(alpha: 0.5) : colors.borderSubtle,
                    width: active ? 1.5 : 1),
                boxShadow: active
                    ? [BoxShadow(color: tier.color.withValues(alpha: 0.18), blurRadius: 14, offset: const Offset(0, 5))]
                    : (dark ? AppShadows.darkCard : AppShadows.card),
              ),
              padding: const EdgeInsets.all(AppSpacing.md),
              child: Row(
                children: [
                  Container(
                    width: 48,
                    height: 48,
                    decoration: BoxDecoration(
                      gradient: LinearGradient(colors: [tier.color, tier.color.withValues(alpha: 0.7)]),
                      shape: BoxShape.circle,
                      boxShadow: [
                        BoxShadow(color: tier.color.withValues(alpha: 0.4), blurRadius: 10, offset: const Offset(0, 3)),
                      ],
                    ),
                    child: Icon(typeIcon, color: Colors.white, size: 22),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(reward.name,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w700)),
                            ),
                            if (!active)
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                                decoration: BoxDecoration(
                                  color: colors.surfaceAlt,
                                  borderRadius: BorderRadius.circular(AppRadius.pill),
                                ),
                                child: Text(s.pointsRewardRetired,
                                    style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
                              ),
                          ],
                        ),
                        if (subtitle.isNotEmpty)
                          Text(subtitle,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
                      ],
                    ),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                    decoration: BoxDecoration(
                      color: tier.color.withValues(alpha: dark ? 0.22 : 0.14),
                      borderRadius: BorderRadius.circular(AppRadius.pill),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(tier.icon, size: 13, color: tier.color),
                        const SizedBox(width: 3),
                        Text('${reward.cost}',
                            style: AppTextStyles.bodySmall.copyWith(color: tier.color, fontWeight: FontWeight.w800)),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// The top-5 most-redeemed rewards, ranked with real medal colours — the report's own
/// `top_rewards`, a genuine leaderboard rather than a bar chart, matching the vault identity.
class _LeaderboardCard extends StatelessWidget {
  const _LeaderboardCard({required this.topRewards});
  final List<(String, int)> topRewards;

  static const _medalColors = [
    Color(0xFFF6B93B), Color(0xFFB8C0CC), Color(0xFFCD8B5C), Color(0xFF8E8E93), Color(0xFF8E8E93),
  ];

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final colors = context.appColors;
    final maxCount = topRewards.map((e) => e.$2).fold(1, (a, b) => a > b ? a : b);
    return KbAnchor(
      id: 'points.leaderboard',
      child: AppCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(s.pointsLeaderboardTitle, style: AppTextStyles.labelMedium),
            const SizedBox(height: AppSpacing.xs),
            Text(s.pointsLeaderboardHint,
                style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
            const SizedBox(height: AppSpacing.md),
            for (var i = 0; i < topRewards.length; i++)
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
                        color: _medalColors[i].withValues(alpha: 0.18),
                        border: Border.all(color: _medalColors[i], width: 1.5),
                      ),
                      child: Center(
                        child: i < 3
                            ? Icon(Icons.emoji_events_rounded, size: 15, color: _medalColors[i])
                            : Text('${i + 1}',
                                style: AppTextStyles.caption
                                    .copyWith(fontWeight: FontWeight.w800, color: _medalColors[i])),
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
                                child: Text(topRewards[i].$1,
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: AppTextStyles.bodySmall.copyWith(fontWeight: FontWeight.w700)),
                              ),
                              Text(s.pointsTimesRedeemed(topRewards[i].$2),
                                  style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
                            ],
                          ),
                          const SizedBox(height: 4),
                          ClipRRect(
                            borderRadius: BorderRadius.circular(AppRadius.pill),
                            child: LinearProgressIndicator(
                              value: topRewards[i].$2 / maxCount,
                              minHeight: 6,
                              backgroundColor: colors.surfaceAlt,
                              valueColor: AlwaysStoppedAnimation(_medalColors[i]),
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

class _RewardSheet extends StatefulWidget {
  const _RewardSheet({required this.service, required this.services, this.existing});
  final PointsService service;
  final List<ServiceItem> services;
  final Reward? existing;

  @override
  State<_RewardSheet> createState() => _RewardSheetState();
}

class _RewardSheetState extends State<_RewardSheet> {
  late final TextEditingController _nameController;
  late final TextEditingController _costController;
  late final TextEditingController _riyalsController;
  RewardType _type = RewardType.item;
  String _serviceId = '';
  bool _active = true;
  bool _saving = false;
  String? _error;

  bool get _isEdit => widget.existing != null;

  @override
  void initState() {
    super.initState();
    final r = widget.existing;
    _nameController = TextEditingController(text: r?.name ?? '');
    _costController = TextEditingController(text: r != null ? '${r.cost}' : '');
    _riyalsController =
        TextEditingController(text: r != null && r.discountHalalas > 0 ? (r.discountHalalas / 100).toStringAsFixed(2) : '');
    _type = r?.type ?? RewardType.item;
    _serviceId = r?.serviceId ?? (widget.services.isNotEmpty ? widget.services.first.id : '');
    _active = r?.active ?? true;
  }

  @override
  void dispose() {
    _nameController.dispose();
    _costController.dispose();
    _riyalsController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final s = S.of(context)!;
    final name = _nameController.text.trim();
    final cost = int.tryParse(_costController.text.trim()) ?? 0;
    if (name.isEmpty || cost <= 0) {
      setState(() => _error = s.pointsRewardInvalid);
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    final discountHalalas = _type == RewardType.discount
        ? ((double.tryParse(_riyalsController.text.trim()) ?? 0) * 100).round()
        : 0;

    String? reason;
    if (_isEdit) {
      reason = await widget.service.update(
        widget.existing!.id,
        name: name,
        cost: cost,
        active: _active,
        discountHalalas: _type == RewardType.discount ? discountHalalas : null,
      );
    } else {
      reason = await widget.service.create(
        name: name,
        cost: cost,
        type: _type,
        serviceId: _type == RewardType.service ? _serviceId : '',
        discountHalalas: discountHalalas,
      );
    }
    if (!mounted) return;
    if (reason == null) {
      Navigator.of(context).pop(true);
      return;
    }
    setState(() {
      _saving = false;
      _error = reason!.isNotEmpty ? reason : s.pointsSaveFailed;
    });
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
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
              Text(_isEdit ? s.pointsEditReward : s.pointsAddReward, style: AppTextStyles.headlineSmall),
              const SizedBox(height: AppSpacing.lg),
              KbAnchor(
                id: 'points.reward_sheet.name_field',
                child: TextField(
                  controller: _nameController,
                  decoration: InputDecoration(isDense: true, hintText: s.pointsRewardNameLabel),
                ),
              ),
              const SizedBox(height: AppSpacing.md),
              if (!_isEdit) ...[
                Text(s.pointsRewardTypeLabel,
                    style: AppTextStyles.bodySmall.copyWith(color: AppColors.textSecondary)),
                const SizedBox(height: AppSpacing.xs),
                KbAnchor(
                  id: 'points.reward_sheet.type_field',
                  child: SegmentedButton<RewardType>(
                    segments: [
                      ButtonSegment(value: RewardType.item, label: Text(s.pointsTypeItem)),
                      ButtonSegment(value: RewardType.discount, label: Text(s.pointsTypeDiscount)),
                      ButtonSegment(value: RewardType.service, label: Text(s.pointsTypeService)),
                    ],
                    selected: {_type},
                    onSelectionChanged: (v) => setState(() => _type = v.first),
                  ),
                ),
                const SizedBox(height: AppSpacing.md),
              ],
              if (_type == RewardType.service && widget.services.isNotEmpty) ...[
                Text(s.pointsRewardServiceLabel,
                    style: AppTextStyles.bodySmall.copyWith(color: AppColors.textSecondary)),
                const SizedBox(height: AppSpacing.xs),
                KbAnchor(
                  id: 'points.reward_sheet.service_field',
                  child: DropdownButtonFormField<String>(
                    initialValue: _serviceId,
                    isExpanded: true,
                    decoration: const InputDecoration(isDense: true),
                    items: [
                      for (final sv in widget.services)
                        DropdownMenuItem(value: sv.id, child: Text(sv.name)),
                    ],
                    onChanged: (v) => setState(() => _serviceId = v ?? _serviceId),
                  ),
                ),
                const SizedBox(height: AppSpacing.md),
              ],
              if (_type == RewardType.discount) ...[
                KbAnchor(
                  id: 'points.reward_sheet.discount_field',
                  child: TextField(
                    controller: _riyalsController,
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    decoration: InputDecoration(isDense: true, hintText: s.pointsRewardDiscountLabel),
                  ),
                ),
                const SizedBox(height: AppSpacing.md),
              ],
              KbAnchor(
                id: 'points.reward_sheet.cost_field',
                child: TextField(
                  controller: _costController,
                  keyboardType: TextInputType.number,
                  decoration: InputDecoration(isDense: true, hintText: s.pointsRewardCostLabel),
                ),
              ),
              if (_isEdit) ...[
                const SizedBox(height: AppSpacing.md),
                KbAnchor(
                  id: 'points.reward_sheet.active_toggle',
                  child: SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text(s.pointsRewardActiveLabel, style: AppTextStyles.bodyMedium),
                    value: _active,
                    onChanged: (v) => setState(() => _active = v),
                  ),
                ),
              ],
              if (_error != null) ...[
                const SizedBox(height: AppSpacing.sm),
                AppAlert(type: AlertType.error, message: _error!),
              ],
              const SizedBox(height: AppSpacing.lg),
              KbAnchor(
                id: 'points.reward_sheet.submit',
                child: SizedBox(
                  width: double.infinity,
                  child: PrimaryButton(text: s.save, isLoading: _saving, onPressed: _saving ? null : _submit),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// «طريقة الاحتساب» (spec §9.3) + a real link to the earning-per-service editor — never a second
/// copy of it. Sits above both tabs since it is a shop-wide switch, not something either tab owns.
class _EarningSettingsCard extends StatelessWidget {
  const _EarningSettingsCard({
    required this.tree,
    required this.saving,
    required this.error,
    required this.canSetMode,
    required this.onModeChanged,
    required this.onOpenEarnSettings,
  });
  final EarnSettingsTree tree;
  final bool saving;
  final String? error;
  final bool canSetMode;
  final ValueChanged<String> onModeChanged;
  final VoidCallback onOpenEarnSettings;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final colors = context.appColors;
    final invoiceMode = tree.mode == 'invoice';

    return KbAnchor(
      id: 'points.earning_settings_card',
      child: AppCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(s.pointsModeTitle, style: AppTextStyles.labelMedium),
            const SizedBox(height: 2),
            Text(s.pointsModeHint,
                style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
            const SizedBox(height: AppSpacing.sm),
            if (canSetMode)
              KbAnchor(
                id: 'points.mode_field',
                child: IgnorePointer(
                  ignoring: saving,
                  child: Opacity(
                    opacity: saving ? 0.6 : 1,
                    child: SegmentedButton<String>(
                      segments: [
                        ButtonSegment(value: 'services', label: Text(s.pointsModeServices)),
                        ButtonSegment(value: 'invoice', label: Text(s.pointsModeInvoice)),
                      ],
                      selected: {invoiceMode ? 'invoice' : 'services'},
                      onSelectionChanged: (v) => onModeChanged(v.first),
                    ),
                  ),
                ),
              )
            else
              Text(invoiceMode ? s.pointsModeInvoice : s.pointsModeServices,
                  style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w700)),
            if (!invoiceMode) ...[
              const SizedBox(height: 6),
              Text(
                s.pointsModeNeedsPricedServices,
                style: AppTextStyles.caption
                    .copyWith(color: error != null ? AppColors.danger : colors.textMuted),
              ),
            ],
            if (error != null) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(error!, style: AppTextStyles.caption.copyWith(color: AppColors.danger)),
            ],
            const Divider(height: AppSpacing.lg),
            KbAnchor(
              id: 'points.open_earn_settings_button',
              child: InkWell(
                onTap: onOpenEarnSettings,
                borderRadius: BorderRadius.circular(AppRadius.sm),
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Row(
                    children: [
                      Icon(Icons.tune_rounded, size: 18, color: colors.textSecondary),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(s.pointsOpenEarnSettings,
                            style: AppTextStyles.bodySmall.copyWith(fontWeight: FontWeight.w600)),
                      ),
                      Icon(
                          Directionality.of(context) == TextDirection.rtl
                              ? Icons.chevron_left_rounded
                              : Icons.chevron_right_rounded,
                          size: 18, color: colors.textMuted),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
