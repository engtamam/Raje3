import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/providers/nav_provider.dart';
import 'package:raje3_mobile/core/services/freelancers_service.dart';
import 'package:raje3_mobile/core/utils/formatters.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/widgets/capability_gate.dart';
import 'package:raje3_mobile/widgets/effects/game_effects.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';
import 'package:raje3_mobile/widgets/rj_sheen.dart';

/// «خدمات ما بعد البيع» — mobile mirror of apps/console/src/screens/Freelancers.tsx. Two tabs,
/// one engine (api/v1/freelancer_portal.py's own module docstring): «المستقلون» is link
/// management (shop-staff-only — add/deactivate, rules, reward catalog, escalation inbox);
/// «سجل العمل» is the SAME daily-follow-up actions a freelancer's own phone would show, built
/// here so staff can do everything a freelancer can, from this one screen.
///
/// OWNER'S OWN INSTRUCTION (2026-10-05): "الجوال ... يبغاله تصميم مناسب له باحترافية عالية لانه
/// اللي غالبا بيتخدم" — mobile is the device actually used day to day, so this screen reaches
/// for the SAME visual craft `features/points/points_screen.dart`'s own "vault" hero and
/// `GameEffects`/`RjSheen` already prove out elsewhere in this app, not a plainer "backend
/// screen" treatment.
class FreelancersScreen extends StatefulWidget {
  const FreelancersScreen({super.key});

  @override
  State<FreelancersScreen> createState() => _FreelancersScreenState();
}

enum _Tab { roster, workbench }

class _FreelancersScreenState extends State<FreelancersScreen> {
  late final FreelancersService _service;
  _Tab _tab = _Tab.roster;

  List<FreelancerLink>? _freelancers;
  bool _freelancersFailed = false;
  FreelancerRules? _rules;
  List<RewardOption> _options = [];
  List<FreelancerEscalation>? _escalations;

  List<FreelancerCustomerRow>? _customers;
  bool _customersFailed = false;
  String _search = '';
  String _statusFilter = '';

  @override
  void initState() {
    super.initState();
    _service = FreelancersService(apiClient: context.read<AuthProvider>().apiClient);
    _loadRoster();
    _loadRules();
    _loadOptions();
    _loadEscalations();
    _loadCustomers();
  }

  Future<void> _loadRoster() async {
    final result = await _service.list();
    if (!mounted) return;
    setState(() {
      if (result == null) {
        _freelancersFailed = true;
      } else {
        _freelancers = result;
        _freelancersFailed = false;
      }
    });
  }

  Future<void> _loadRules() async {
    final r = await _service.getRules();
    if (r != null && mounted) setState(() => _rules = r);
  }

  Future<void> _loadOptions() async {
    final r = await _service.listRewardOptions();
    if (r != null && mounted) setState(() => _options = r);
  }

  Future<void> _loadEscalations() async {
    final r = await _service.listEscalations(statusFilter: 'open');
    if (mounted) setState(() => _escalations = r);
  }

  Future<void> _loadCustomers() async {
    final result = await _service.listCustomers(search: _search, statusFilter: _statusFilter);
    if (!mounted) return;
    setState(() {
      if (result == null) {
        _customersFailed = true;
      } else {
        _customers = result;
        _customersFailed = false;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    return KbAnchor(
      id: 'freelancers',
      child: Scaffold(
        backgroundColor: AppColors.surface0,
        appBar: AppBar(title: Text(s.freelancersTitle)),
        body: RefreshIndicator(
          onRefresh: () async {
            await Future.wait([_loadRoster(), _loadRules(), _loadOptions(), _loadEscalations(), _loadCustomers()]);
          },
          child: CustomScrollView(
            slivers: [
              SliverToBoxAdapter(
                child: _FreelancersHero(
                  activeCount: _freelancers?.where((f) => f.active).length ?? 0,
                  waitingToday: _customers?.length ?? 0,
                  openEscalations: _escalations?.length ?? 0,
                ),
              ),
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(AppSpacing.md, AppSpacing.md, AppSpacing.md, 0),
                sliver: SliverToBoxAdapter(
                  child: SegmentedFilter<_Tab>(
                    value: _tab,
                    onChanged: (v) => setState(() => _tab = v),
                    options: [
                      SegmentedFilterOption(value: _Tab.roster, label: s.freelancersTabRoster),
                      SegmentedFilterOption(value: _Tab.workbench, label: s.freelancersTabWorkbench),
                    ],
                  ),
                ),
              ),
              if (_tab == _Tab.roster) ..._rosterSlivers(s) else ..._workbenchSlivers(s),
            ],
          ),
        ),
      ),
    );
  }

  // ── «المستقلون» ─────────────────────────────────────────────────────────────────────────────
  List<Widget> _rosterSlivers(S s) {
    final catalog = context.watch<NavProvider>().catalog;
    final canManage = catalog.hasAll(['operations.freelancer_list']);
    if (!canManage) return const [SliverToBoxAdapter(child: SizedBox.shrink())];

    final open = _escalations;
    final active = _freelancers?.where((f) => f.active).toList() ?? const [];
    final slotsOpen = 3 - active.length;

    return [
      SliverPadding(
        padding: const EdgeInsets.fromLTRB(AppSpacing.md, AppSpacing.md, AppSpacing.md, 0),
        sliver: SliverToBoxAdapter(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (open != null && open.isNotEmpty) ...[
                _EscalationsBox(
                  escalations: open,
                  onResolve: (id) async {
                    final ok = await _service.resolveEscalation(id);
                    if (ok && mounted) {
                      GameEffects.celebrate(context);
                      _loadEscalations();
                    }
                  },
                ),
                const SizedBox(height: AppSpacing.md),
              ],
              Row(
                children: [
                  Expanded(
                    child: SecondaryButton(
                      text: s.freelancersRosterRulesButton,
                      onPressed: () => _openRulesSheet(s),
                    ),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: SecondaryButton(
                      text: s.freelancersRosterOptionsButton,
                      onPressed: () => _openOptionsSheet(s),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.sm),
              SizedBox(
                width: double.infinity,
                child: SecondaryButton(
                  text: s.freelancersRosterExportButton,
                  onPressed: () => _openExportSheet(s),
                ),
              ),
            ],
          ),
        ),
      ),
      if (_freelancersFailed)
        SliverPadding(
          padding: const EdgeInsets.all(AppSpacing.xl),
          sliver: SliverToBoxAdapter(
            child: EmptyState(
              icon: Icons.cloud_off_rounded,
              title: s.freelancersRosterFailedTitle,
              actionText: s.freelancersRetry,
              onAction: _loadRoster,
            ),
          ),
        )
      else if (_freelancers == null)
        const SliverPadding(
          padding: EdgeInsets.all(AppSpacing.xl),
          sliver: SliverToBoxAdapter(child: AppLoadingIndicator()),
        )
      else if (active.isEmpty)
        SliverPadding(
          padding: const EdgeInsets.all(AppSpacing.xl),
          sliver: SliverToBoxAdapter(
            child: EmptyState(
              icon: Icons.support_agent_rounded,
              title: s.freelancersRosterEmptyTitle,
              message: s.freelancersRosterEmptyBody,
            ),
          ),
        )
      else
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(AppSpacing.md, AppSpacing.sm, AppSpacing.md, AppSpacing.xxl),
          sliver: SliverList.separated(
            itemCount: active.length,
            separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
            itemBuilder: (context, i) => _FreelancerCard(
              freelancer: active[i],
              onDeactivate: () => _confirmDeactivate(s, active[i]),
            ),
          ),
        ),
      if (slotsOpen > 0)
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.xxl),
          sliver: SliverToBoxAdapter(
            child: _AddFreelancerTile(onTap: () => _openAddSheet(s)),
          ),
        ),
    ];
  }

  Future<void> _confirmDeactivate(S s, FreelancerLink f) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(s.freelancersRosterConfirmDeactivateTitle),
        content: Text(s.freelancersRosterConfirmDeactivateBody),
        actions: [
          TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(false),
              child: Text(s.freelancersRosterConfirmDeactivateCancel)),
          TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(true),
              child: Text(s.freelancersRosterConfirmDeactivateConfirm)),
        ],
      ),
    );
    if (confirmed == true) {
      final ok = await _service.deactivate(f.id);
      if (ok) _loadRoster();
    }
  }

  Future<void> _openAddSheet(S s) async {
    final added = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _AddFreelancerSheet(service: _service),
    );
    if (added == true) _loadRoster();
  }

  Future<void> _openRulesSheet(S s) async {
    final rules = _rules;
    if (rules == null) return;
    final saved = await showModalBottomSheet<FreelancerRules>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _RulesSheet(service: _service, rules: rules),
    );
    if (saved != null && mounted) setState(() => _rules = saved);
  }

  Future<void> _openOptionsSheet(S s) async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _OptionsSheet(
        service: _service,
        options: _options,
        onAdded: (o) => setState(() => _options = [..._options, o]),
      ),
    );
  }

  Future<void> _openExportSheet(S s) async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _ExportSheet(service: _service),
    );
  }

  // ── «سجل العمل» ─────────────────────────────────────────────────────────────────────────────
  List<Widget> _workbenchSlivers(S s) {
    return [
      SliverPadding(
        padding: const EdgeInsets.fromLTRB(AppSpacing.md, AppSpacing.md, AppSpacing.md, 0),
        sliver: SliverToBoxAdapter(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              AppTextField(
                hintText: s.freelancersWorkSearchHint,
                prefixIcon: Icons.search_rounded,
                onChanged: (v) {
                  _search = v;
                  _loadCustomers();
                },
              ),
              const SizedBox(height: AppSpacing.sm),
              SizedBox(
                height: 36,
                child: ListView(
                  scrollDirection: Axis.horizontal,
                  children: [
                    _StatusChip(
                        label: s.freelancersWorkFilterAll,
                        selected: _statusFilter.isEmpty,
                        onTap: () => _setStatusFilter('')),
                    _StatusChip(
                        label: s.freelancersWorkFilterNew,
                        selected: _statusFilter == 'new',
                        onTap: () => _setStatusFilter('new')),
                    _StatusChip(
                        label: s.freelancersRatingSatisfied,
                        selected: _statusFilter == 'satisfied',
                        onTap: () => _setStatusFilter('satisfied')),
                    _StatusChip(
                        label: s.freelancersRatingNeutral,
                        selected: _statusFilter == 'neutral',
                        onTap: () => _setStatusFilter('neutral')),
                    _StatusChip(
                        label: s.freelancersRatingUnsatisfied,
                        selected: _statusFilter == 'unsatisfied',
                        onTap: () => _setStatusFilter('unsatisfied')),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
      if (_customersFailed)
        SliverPadding(
          padding: const EdgeInsets.all(AppSpacing.xl),
          sliver: SliverToBoxAdapter(
            child: EmptyState(
              icon: Icons.cloud_off_rounded,
              title: s.freelancersWorkFailedTitle,
              actionText: s.freelancersRetry,
              onAction: _loadCustomers,
            ),
          ),
        )
      else if (_customers == null)
        const SliverPadding(
          padding: EdgeInsets.all(AppSpacing.xl),
          sliver: SliverToBoxAdapter(child: AppLoadingIndicator()),
        )
      else if (_customers!.isEmpty)
        SliverPadding(
          padding: const EdgeInsets.all(AppSpacing.xl),
          sliver: SliverToBoxAdapter(
            child: EmptyState(
              icon: Icons.task_alt_rounded,
              title: s.freelancersWorkEmptyTitle,
              message: s.freelancersWorkEmptyBody,
            ),
          ),
        )
      else
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(AppSpacing.md, AppSpacing.sm, AppSpacing.md, AppSpacing.xxl),
          sliver: SliverList.separated(
            itemCount: _customers!.length,
            separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
            itemBuilder: (context, i) => _CustomerCard(
              customer: _customers![i],
              options: _options,
              onOpen: () => _openCustomerSheet(s, _customers![i]),
            ),
          ),
        ),
    ];
  }

  void _setStatusFilter(String v) {
    setState(() => _statusFilter = v);
    _loadCustomers();
  }

  Future<void> _openCustomerSheet(S s, FreelancerCustomerRow c) async {
    final acted = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _CustomerActionsSheet(service: _service, customer: c, options: _options),
    );
    if (acted == true) {
      _loadCustomers();
      _loadEscalations();
    }
  }
}

// ── hero ──────────────────────────────────────────────────────────────────────────────────────
class _FreelancersHero extends StatelessWidget {
  const _FreelancersHero({
    required this.activeCount,
    required this.waitingToday,
    required this.openEscalations,
  });
  final int activeCount;
  final int waitingToday;
  final int openEscalations;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final dark = context.isDark;
    // A calm blue-violet treatment — "ثقة ومتابعة" — deliberately distinct from the points
    // screen's own gold/violet "vault" so the two never read as the same product area.
    final gradient = LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: dark
          ? [const Color(0xFF1E3A6D), const Color(0xFF0B1730)]
          : [const Color(0xFF2A5298), const Color(0xFF17253F)],
    );

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
                    shape: BoxShape.circle, color: const Color(0xFF6FA8F5).withValues(alpha: 0.16)),
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
                                colors: [Color(0xFF6FA8F5), Color(0xFF2E5CA8)]),
                            shape: BoxShape.circle,
                            boxShadow: [
                              BoxShadow(
                                  color: const Color(0xFF6FA8F5).withValues(alpha: 0.5),
                                  blurRadius: 12,
                                  offset: const Offset(0, 3)),
                            ],
                          ),
                          child: const Icon(Icons.headset_mic_rounded, color: Colors.white, size: 20),
                        ),
                        const SizedBox(width: AppSpacing.sm),
                        Expanded(
                          child: Text(s.freelancersTitle,
                              style: AppTextStyles.displaySmall.copyWith(color: Colors.white)),
                        ),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.md),
                    Text(
                      s.freelancersHeroActiveCount(activeCount, 3),
                      style: AppTextStyles.displaySmall.copyWith(color: Colors.white, fontSize: 22, height: 1),
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    Row(
                      children: [
                        _HeroStat(
                          icon: Icons.groups_rounded,
                          label: s.freelancersHeroWaitingToday(waitingToday),
                        ),
                      ],
                    ),
                    if (openEscalations > 0) ...[
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
                            const SizedBox(width: 6),
                            Text(s.freelancersHeroEscalationsWarning(openEscalations),
                                style: AppTextStyles.caption
                                    .copyWith(color: Colors.white, fontWeight: FontWeight.w700)),
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

// ── escalations box ───────────────────────────────────────────────────────────────────────────
class _EscalationsBox extends StatelessWidget {
  const _EscalationsBox({required this.escalations, required this.onResolve});
  final List<FreelancerEscalation> escalations;
  final ValueChanged<String> onResolve;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final colors = context.appColors;
    final danger = context.isDark ? AppDarkColors.danger : AppColors.danger;
    final dangerSoft = context.isDark ? AppDarkColors.dangerSoft : AppColors.dangerSoft;
    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: dangerSoft,
        border: Border.all(color: danger.withValues(alpha: 0.3)),
        borderRadius: AppRadius.standardRadius,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.warning_amber_rounded, color: danger, size: 18),
              const SizedBox(width: 6),
              Text(s.freelancersEscalationsOpenTitle(escalations.length),
                  style: AppTextStyles.labelMedium.copyWith(color: danger, fontWeight: FontWeight.w700)),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          for (final e in escalations)
            Container(
              margin: const EdgeInsets.only(bottom: AppSpacing.sm),
              padding: const EdgeInsets.all(AppSpacing.sm),
              decoration: BoxDecoration(color: colors.surface, borderRadius: AppRadius.standardRadius),
              child: Row(
                children: [
                  Expanded(
                    child: Text(e.note, style: AppTextStyles.bodySmall, maxLines: 2, overflow: TextOverflow.ellipsis),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  SizedBox(
                    height: 32,
                    child: PrimaryButton(text: s.freelancersEscalationsResolve, onPressed: () => onResolve(e.id)),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

// ── freelancer card ───────────────────────────────────────────────────────────────────────────
class _FreelancerCard extends StatelessWidget {
  const _FreelancerCard({required this.freelancer, required this.onDeactivate});
  final FreelancerLink freelancer;
  final VoidCallback onDeactivate;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final colors = context.appColors;
    return RjSheen(
      borderRadius: AppRadius.cardRadius,
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
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: context.isDark ? AppDarkColors.successSoft : AppColors.successSoft,
              ),
              child: Icon(Icons.person_rounded,
                  color: context.isDark ? AppDarkColors.successOnSoft : AppColors.successOnSoft),
            ),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(freelancer.displayName, style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w700)),
                  Text(freelancer.phone,
                      style: AppTextStyles.caption.copyWith(
                          color: colors.textSecondary, fontFamily: AppTextStyles.englishFont)),
                ],
              ),
            ),
            IconButton(
              onPressed: onDeactivate,
              icon: Icon(Icons.person_off_outlined, color: colors.textMuted, size: 20),
              tooltip: s.freelancersRosterDeactivate,
            ),
          ],
        ),
      ),
    );
  }
}

class _AddFreelancerTile extends StatelessWidget {
  const _AddFreelancerTile({required this.onTap});
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final colors = context.appColors;
    return CapabilityGate(
      requires: const ['operations.freelancer_add'],
      child: InkWell(
        onTap: onTap,
        borderRadius: AppRadius.cardRadius,
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: AppSpacing.lg),
          decoration: BoxDecoration(
            borderRadius: AppRadius.cardRadius,
            border: Border.all(color: colors.borderSubtle, width: 1.5, style: BorderStyle.solid),
          ),
          child: Column(
            children: [
              Icon(Icons.person_add_alt_1_rounded, color: colors.textMuted),
              const SizedBox(height: 4),
              Text(s.freelancersRosterAddButton,
                  style: AppTextStyles.labelMedium.copyWith(color: colors.textSecondary)),
            ],
          ),
        ),
      ),
    );
  }
}

// ── add freelancer sheet ──────────────────────────────────────────────────────────────────────
class _AddFreelancerSheet extends StatefulWidget {
  const _AddFreelancerSheet({required this.service});
  final FreelancersService service;

  @override
  State<_AddFreelancerSheet> createState() => _AddFreelancerSheetState();
}

class _AddFreelancerSheetState extends State<_AddFreelancerSheet> {
  final _nameController = TextEditingController();
  final _phoneController = TextEditingController();
  bool _busy = false;
  bool _failed = false;

  bool get _valid => _nameController.text.trim().isNotEmpty && _phoneController.text.trim().length >= 9;

  Future<void> _submit() async {
    if (!_valid || _busy) return;
    setState(() {
      _busy = true;
      _failed = false;
    });
    final result = await widget.service
        .add(phone: _phoneController.text.trim(), displayName: _nameController.text.trim());
    if (!mounted) return;
    setState(() => _busy = false);
    if (result != null) {
      Navigator.of(context).pop(true);
    } else {
      setState(() => _failed = true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final colors = context.appColors;
    return Container(
      constraints: BoxConstraints(maxHeight: appSheetMaxHeight(context)),
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        color: colors.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
      ),
      child: Padding(
        padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
        child: SafeArea(
          top: false,
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Center(
                  child: Container(
                      width: 40, height: 4,
                      decoration: BoxDecoration(color: colors.borderSubtle, borderRadius: BorderRadius.circular(4))),
                ),
                const SizedBox(height: AppSpacing.md),
                Text(s.freelancersAddTitle, style: AppTextStyles.headlineSmall),
                const SizedBox(height: AppSpacing.md),
                AppTextField(labelText: s.freelancersAddNameLabel, hintText: s.freelancersAddNameHint, controller: _nameController),
                const SizedBox(height: AppSpacing.sm),
                AppTextField(
                  labelText: s.freelancersAddPhoneLabel, hintText: s.freelancersAddPhoneHint,
                  controller: _phoneController, keyboardType: TextInputType.phone,
                ),
                const SizedBox(height: AppSpacing.sm),
                Text(s.freelancersAddNote, style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
                if (_failed) ...[
                  const SizedBox(height: AppSpacing.sm),
                  AppAlert(type: AlertType.error, message: s.freelancersAddFailed),
                ],
                const SizedBox(height: AppSpacing.lg),
                SizedBox(
                  width: double.infinity, height: 44,
                  child: PrimaryButton(text: s.freelancersAddSubmit, isLoading: _busy, onPressed: _valid ? _submit : null),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ── business rules sheet ──────────────────────────────────────────────────────────────────────
class _RulesSheet extends StatefulWidget {
  const _RulesSheet({required this.service, required this.rules});
  final FreelancersService service;
  final FreelancerRules rules;

  @override
  State<_RulesSheet> createState() => _RulesSheetState();
}

class _RulesSheetState extends State<_RulesSheet> {
  late int _cooldown = widget.rules.cooldownDays;
  late int _cap = widget.rules.dailyCap;
  bool _busy = false;

  Future<void> _save() async {
    setState(() => _busy = true);
    final r = await widget.service.setRules(cooldownDays: _cooldown, dailyCap: _cap);
    if (!mounted) return;
    setState(() => _busy = false);
    if (r != null) Navigator.of(context).pop(r);
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final colors = context.appColors;
    return Container(
      constraints: BoxConstraints(maxHeight: appSheetMaxHeight(context)),
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(color: colors.surface, borderRadius: const BorderRadius.vertical(top: Radius.circular(AppRadius.card))),
      child: SafeArea(
        top: false,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(s.freelancersRulesTitle, style: AppTextStyles.headlineSmall),
              const SizedBox(height: AppSpacing.lg),
              _NumberField(
                label: s.freelancersRulesCooldownLabel, help: s.freelancersRulesCooldownHelp,
                value: _cooldown, onChanged: (v) => setState(() => _cooldown = v),
              ),
              const SizedBox(height: AppSpacing.md),
              _NumberField(
                label: s.freelancersRulesCapLabel, help: s.freelancersRulesCapHelp,
                value: _cap, onChanged: (v) => setState(() => _cap = v),
              ),
              const SizedBox(height: AppSpacing.lg),
              SizedBox(
                width: double.infinity, height: 44,
                child: PrimaryButton(text: s.freelancersRulesSave, isLoading: _busy, onPressed: _save),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _NumberField extends StatelessWidget {
  const _NumberField({required this.label, required this.help, required this.value, required this.onChanged});
  final String label;
  final String help;
  final int value;
  final ValueChanged<int> onChanged;

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: AppTextStyles.labelMedium.copyWith(fontWeight: FontWeight.w700)),
        const SizedBox(height: 4),
        Row(
          children: [
            IconButton(onPressed: () => onChanged((value - 1).clamp(0, 9999)), icon: const Icon(Icons.remove_circle_outline)),
            SizedBox(
              width: 56,
              child: Text('$value', textAlign: TextAlign.center, style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w800)),
            ),
            IconButton(onPressed: () => onChanged((value + 1).clamp(0, 9999)), icon: const Icon(Icons.add_circle_outline)),
          ],
        ),
        Text(help, style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
      ],
    );
  }
}

// ── reward options sheet ──────────────────────────────────────────────────────────────────────
class _OptionsSheet extends StatefulWidget {
  const _OptionsSheet({required this.service, required this.options, required this.onAdded});
  final FreelancersService service;
  final List<RewardOption> options;
  final ValueChanged<RewardOption> onAdded;

  @override
  State<_OptionsSheet> createState() => _OptionsSheetState();
}

class _OptionsSheetState extends State<_OptionsSheet> {
  String _kind = 'gift';
  final _labelController = TextEditingController();
  int _percent = 10;
  int _points = 50;
  bool _busy = false;
  late List<RewardOption> _options = widget.options;

  bool get _valid =>
      _labelController.text.trim().isNotEmpty &&
      (_kind != 'discount' || (_percent > 0 && _percent <= 100)) &&
      (_kind != 'points' || _points > 0);

  Future<void> _submit() async {
    if (!_valid || _busy) return;
    setState(() => _busy = true);
    final o = await widget.service.addRewardOption(
      kind: _kind, label: _labelController.text.trim(),
      percent: _kind == 'discount' ? _percent : 0, points: _kind == 'points' ? _points : 0,
    );
    if (!mounted) return;
    setState(() => _busy = false);
    if (o != null) {
      widget.onAdded(o);
      setState(() {
        _options = [..._options, o];
        _labelController.clear();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final colors = context.appColors;
    return Container(
      constraints: BoxConstraints(maxHeight: appSheetMaxHeight(context)),
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(color: colors.surface, borderRadius: const BorderRadius.vertical(top: Radius.circular(AppRadius.card))),
      child: Padding(
        padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
        child: SafeArea(
          top: false,
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(s.freelancersOptionsTitle, style: AppTextStyles.headlineSmall),
                const SizedBox(height: AppSpacing.md),
                if (_options.isEmpty)
                  Text(s.freelancersOptionsEmpty, style: AppTextStyles.caption.copyWith(color: colors.textMuted))
                else
                  for (final o in _options)
                    Container(
                      margin: const EdgeInsets.only(bottom: AppSpacing.xs),
                      padding: const EdgeInsets.all(AppSpacing.sm),
                      decoration: BoxDecoration(color: colors.surfaceAlt, borderRadius: AppRadius.standardRadius),
                      child: Row(
                        children: [
                          Icon(
                            o.kind == 'gift' ? Icons.card_giftcard_rounded
                                : o.kind == 'points' ? Icons.stars_rounded : Icons.percent_rounded,
                            size: 16, color: colors.textSecondary,
                          ),
                          const SizedBox(width: AppSpacing.sm),
                          Expanded(child: Text(o.label, style: AppTextStyles.bodySmall)),
                        ],
                      ),
                    ),
                const Divider(height: AppSpacing.lg),
                DropdownButtonFormField<String>(
                  initialValue: _kind,
                  items: [
                    DropdownMenuItem(value: 'gift', child: Text(s.freelancersOptionsKindGift)),
                    DropdownMenuItem(value: 'points', child: Text(s.freelancersOptionsKindPoints)),
                    DropdownMenuItem(value: 'discount', child: Text(s.freelancersOptionsKindDiscount)),
                  ],
                  onChanged: (v) => setState(() => _kind = v ?? 'gift'),
                ),
                const SizedBox(height: AppSpacing.sm),
                AppTextField(hintText: s.freelancersOptionsLabelHint, controller: _labelController),
                if (_kind == 'discount') ...[
                  const SizedBox(height: AppSpacing.sm),
                  _NumberField(label: s.freelancersOptionsPercentLabel, help: '', value: _percent,
                      onChanged: (v) => setState(() => _percent = v.clamp(0, 100))),
                ],
                if (_kind == 'points') ...[
                  const SizedBox(height: AppSpacing.sm),
                  _NumberField(label: s.freelancersOptionsPointsLabel, help: '', value: _points,
                      onChanged: (v) => setState(() => _points = v)),
                ],
                const SizedBox(height: AppSpacing.lg),
                SizedBox(
                  width: double.infinity, height: 44,
                  child: PrimaryButton(text: s.freelancersOptionsSubmit, isLoading: _busy, onPressed: _valid ? _submit : null),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ── export sheet ──────────────────────────────────────────────────────────────────────────────
class _ExportSheet extends StatefulWidget {
  const _ExportSheet({required this.service});
  final FreelancersService service;

  @override
  State<_ExportSheet> createState() => _ExportSheetState();
}

class _ExportSheetState extends State<_ExportSheet> {
  String _preset = 'month';
  DateTime? _customStart;
  DateTime? _customEnd;
  bool _includePii = false;
  bool _busy = false;
  String? _text;

  Future<void> _run() async {
    setState(() {
      _busy = true;
      _text = null;
    });
    final now = DateTime.now().millisecondsSinceEpoch ~/ 1000;
    int since, until;
    switch (_preset) {
      case 'week':
        since = now - 7 * 86400;
        until = now;
      case '90d':
        since = now - 90 * 86400;
        until = now;
      case 'year':
        since = now - 365 * 86400;
        until = now;
      case 'custom':
        since = _customStart != null ? _customStart!.millisecondsSinceEpoch ~/ 1000 : 0;
        until = _customEnd != null ? _customEnd!.millisecondsSinceEpoch ~/ 1000 + 86400 : now;
      default:
        since = now - 30 * 86400;
        until = now;
    }
    final text = await widget.service.exportNotes(since: since, until: until, includePii: _includePii);
    if (!mounted) return;
    setState(() {
      _busy = false;
      _text = text ?? '';
    });
  }

  Future<void> _pickDate({required bool start}) async {
    final picked = await showDatePicker(
      context: context,
      firstDate: DateTime(2020),
      lastDate: DateTime.now(),
      initialDate: DateTime.now(),
    );
    if (picked != null) {
      setState(() {
        if (start) {
          _customStart = picked;
        } else {
          _customEnd = picked;
        }
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final colors = context.appColors;
    final locale = Localizations.localeOf(context).languageCode;
    final presets = <(String, String)>[
      ('week', s.freelancersExportPresetWeek),
      ('month', s.freelancersExportPresetMonth),
      ('90d', s.freelancersExportPreset90d),
      ('year', s.freelancersExportPresetYear),
      ('custom', s.freelancersExportPresetCustom),
    ];

    return Container(
      constraints: BoxConstraints(maxHeight: appSheetMaxHeight(context)),
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(color: colors.surface, borderRadius: const BorderRadius.vertical(top: Radius.circular(AppRadius.card))),
      child: SafeArea(
        top: false,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(s.freelancersExportTitle, style: AppTextStyles.headlineSmall),
              const SizedBox(height: AppSpacing.md),
              Wrap(
                spacing: AppSpacing.xs, runSpacing: AppSpacing.xs,
                children: [
                  for (final (value, label) in presets)
                    ChoiceChip(
                      label: Text(label), selected: _preset == value,
                      onSelected: (_) => setState(() => _preset = value),
                    ),
                ],
              ),
              if (_preset == 'custom') ...[
                const SizedBox(height: AppSpacing.sm),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton(
                        onPressed: () => _pickDate(start: true),
                        child: Text(_customStart != null
                            ? Formatters.formatDate(_customStart!, locale: locale)
                            : s.freelancersExportFromLabel),
                      ),
                    ),
                    const SizedBox(width: AppSpacing.sm),
                    Expanded(
                      child: OutlinedButton(
                        onPressed: () => _pickDate(start: false),
                        child: Text(_customEnd != null
                            ? Formatters.formatDate(_customEnd!, locale: locale)
                            : s.freelancersExportToLabel),
                      ),
                    ),
                  ],
                ),
              ],
              const SizedBox(height: AppSpacing.sm),
              CheckboxListTile(
                contentPadding: EdgeInsets.zero,
                value: _includePii,
                onChanged: (v) => setState(() => _includePii = v ?? false),
                title: Text(s.freelancersExportIncludePii, style: AppTextStyles.bodySmall),
              ),
              const SizedBox(height: AppSpacing.sm),
              SizedBox(
                width: double.infinity, height: 44,
                child: PrimaryButton(text: s.freelancersExportRun, isLoading: _busy, onPressed: _run),
              ),
              if (_text != null) ...[
                const SizedBox(height: AppSpacing.md),
                if (_text!.isEmpty)
                  Text(s.freelancersExportEmpty, style: AppTextStyles.caption.copyWith(color: colors.textMuted))
                else
                  Container(
                    padding: const EdgeInsets.all(AppSpacing.sm),
                    decoration: BoxDecoration(color: colors.surfaceAlt, borderRadius: AppRadius.standardRadius),
                    child: Text(_text!, style: AppTextStyles.caption),
                  ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

// ── workbench: status chip ───────────────────────────────────────────────────────────────────
class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.label, required this.selected, required this.onTap});
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(left: 6),
      child: ChoiceChip(label: Text(label), selected: selected, onSelected: (_) => onTap()),
    );
  }
}

// ── customer card ─────────────────────────────────────────────────────────────────────────────
const Map<String, Color> _ratingColors = {
  'satisfied': Color(0xFF2F9E44),
  'neutral': Color(0xFF868E96),
  'unsatisfied': Color(0xFFE03131),
};

class _CustomerCard extends StatelessWidget {
  const _CustomerCard({required this.customer, required this.options, required this.onOpen});
  final FreelancerCustomerRow customer;
  final List<RewardOption> options;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final colors = context.appColors;
    final locale = Localizations.localeOf(context).languageCode;
    final ratingColor = _ratingColors[customer.lastStatus];
    final ratingLabel = customer.lastStatus == 'satisfied'
        ? s.freelancersRatingSatisfied
        : customer.lastStatus == 'neutral'
            ? s.freelancersRatingNeutral
            : customer.lastStatus == 'unsatisfied'
                ? s.freelancersRatingUnsatisfied
                : s.freelancersWorkFilterNew;

    return Material(
      color: Colors.transparent,
      borderRadius: AppRadius.cardRadius,
      child: InkWell(
        onTap: onOpen,
        borderRadius: AppRadius.cardRadius,
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
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(customer.name.isNotEmpty ? customer.name : customer.phone,
                        style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w700),
                        maxLines: 1, overflow: TextOverflow.ellipsis),
                    const SizedBox(height: 2),
                    Text(s.freelancersWorkLastVisit(
                            Formatters.formatDate(DateTime.fromMillisecondsSinceEpoch(customer.lastVisit * 1000), locale: locale)),
                        style: AppTextStyles.caption.copyWith(color: colors.textSecondary)),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                decoration: BoxDecoration(
                  color: (ratingColor ?? colors.textMuted).withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(AppRadius.pill),
                ),
                child: Text(ratingLabel,
                    style: AppTextStyles.caption.copyWith(color: ratingColor ?? colors.textSecondary, fontWeight: FontWeight.w700)),
              ),
              Icon(Icons.chevron_right_rounded, color: colors.textMuted),
            ],
          ),
        ),
      ),
    );
  }
}

// ── customer actions sheet (rate / dnd / reward / escalate / note) ─────────────────────────────
class _CustomerActionsSheet extends StatefulWidget {
  const _CustomerActionsSheet({required this.service, required this.customer, required this.options});
  final FreelancersService service;
  final FreelancerCustomerRow customer;
  final List<RewardOption> options;

  @override
  State<_CustomerActionsSheet> createState() => _CustomerActionsSheetState();
}

class _CustomerActionsSheetState extends State<_CustomerActionsSheet> {
  bool _busy = false;
  String? _error;
  final _noteController = TextEditingController();
  final _escalateController = TextEditingController();

  Future<void> _rate(String status) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    final ok = await widget.service.rateCustomer(widget.customer.customerId, status);
    if (!mounted) return;
    setState(() => _busy = false);
    if (ok) {
      Navigator.of(context).pop(true);
    } else {
      setState(() => _error = S.of(context)!.freelancersWorkActionFailed);
    }
  }

  Future<void> _dnd() async {
    final s = S.of(context)!;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(s.freelancersWorkConfirmDndTitle),
        content: Text(s.freelancersWorkConfirmDndBody),
        actions: [
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(false), child: Text(s.freelancersRosterConfirmDeactivateCancel)),
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(true), child: Text(s.freelancersWorkDnd)),
        ],
      ),
    );
    if (confirmed != true) return;
    setState(() => _busy = true);
    final ok = await widget.service.doNotDisturb(widget.customer.customerId);
    if (!mounted) return;
    setState(() => _busy = false);
    if (ok) Navigator.of(context).pop(true);
  }

  Future<void> _grant(RewardOption o) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    final ok = await widget.service.grantReward(widget.customer.customerId, o.id);
    if (!mounted) return;
    setState(() => _busy = false);
    if (ok) {
      GameEffects.celebrate(context);
      Navigator.of(context).pop(true);
    } else {
      setState(() => _error = S.of(context)!.freelancersWorkCapReached);
    }
  }

  Future<void> _escalate() async {
    if (_escalateController.text.trim().isEmpty) return;
    setState(() => _busy = true);
    final ok = await widget.service.escalate(widget.customer.customerId, _escalateController.text.trim());
    if (!mounted) return;
    setState(() => _busy = false);
    if (ok) Navigator.of(context).pop(true);
  }

  Future<void> _addNote() async {
    if (_noteController.text.trim().isEmpty) return;
    setState(() => _busy = true);
    final ok = await widget.service.addNote(widget.customer.customerId,
        text: _noteController.text.trim(), status: widget.customer.lastStatus.isEmpty ? 'neutral' : widget.customer.lastStatus);
    if (!mounted) return;
    setState(() => _busy = false);
    if (ok) _noteController.clear();
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final colors = context.appColors;

    return Container(
      constraints: BoxConstraints(maxHeight: appSheetMaxHeight(context)),
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(color: colors.surface, borderRadius: const BorderRadius.vertical(top: Radius.circular(AppRadius.card))),
      child: Padding(
        padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
        child: SafeArea(
          top: false,
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Center(
                  child: Container(width: 40, height: 4,
                      decoration: BoxDecoration(color: colors.borderSubtle, borderRadius: BorderRadius.circular(4))),
                ),
                const SizedBox(height: AppSpacing.md),
                Text(widget.customer.name.isNotEmpty ? widget.customer.name : widget.customer.phone,
                    style: AppTextStyles.headlineSmall),
                const SizedBox(height: AppSpacing.md),
                Wrap(
                  spacing: AppSpacing.sm, runSpacing: AppSpacing.sm,
                  children: [
                    _RateButton(label: s.freelancersRatingSatisfied, icon: Icons.thumb_up_alt_rounded,
                        color: _ratingColors['satisfied']!, onTap: _busy ? null : () => _rate('satisfied')),
                    _RateButton(label: s.freelancersRatingNeutral, icon: Icons.remove_circle_outline_rounded,
                        color: _ratingColors['neutral']!, onTap: _busy ? null : () => _rate('neutral')),
                    _RateButton(label: s.freelancersRatingUnsatisfied, icon: Icons.thumb_down_alt_rounded,
                        color: _ratingColors['unsatisfied']!, onTap: _busy ? null : () => _rate('unsatisfied')),
                    OutlinedButton.icon(
                      onPressed: _busy ? null : _dnd,
                      icon: const Icon(Icons.block_rounded, size: 16),
                      label: Text(s.freelancersWorkDnd),
                    ),
                  ],
                ),
                if (widget.options.isNotEmpty) ...[
                  const SizedBox(height: AppSpacing.lg),
                  Text(s.freelancersWorkRewardTitle, style: AppTextStyles.labelMedium.copyWith(fontWeight: FontWeight.w700)),
                  const SizedBox(height: AppSpacing.sm),
                  Wrap(
                    spacing: AppSpacing.sm, runSpacing: AppSpacing.sm,
                    children: [
                      for (final o in widget.options)
                        OutlinedButton.icon(
                          onPressed: _busy ? null : () => _grant(o),
                          icon: Icon(
                              o.kind == 'gift' ? Icons.card_giftcard_rounded
                                  : o.kind == 'points' ? Icons.stars_rounded : Icons.percent_rounded,
                              size: 16),
                          label: Text(o.label),
                        ),
                    ],
                  ),
                ],
                const SizedBox(height: AppSpacing.lg),
                AppTextField(hintText: s.freelancersWorkNoteHint, controller: _noteController),
                const SizedBox(height: AppSpacing.sm),
                SizedBox(
                  width: double.infinity, height: 40,
                  child: SecondaryButton(text: s.freelancersWorkNoteSave, onPressed: _busy ? null : _addNote),
                ),
                const Divider(height: AppSpacing.lg),
                AppTextField(hintText: s.freelancersWorkEscalateHint, controller: _escalateController),
                const SizedBox(height: AppSpacing.sm),
                SizedBox(
                  width: double.infinity, height: 40,
                  child: SecondaryButton(text: s.freelancersWorkEscalate, onPressed: _busy ? null : _escalate),
                ),
                if (_error != null) ...[
                  const SizedBox(height: AppSpacing.sm),
                  AppAlert(type: AlertType.error, message: _error!),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _RateButton extends StatelessWidget {
  const _RateButton({required this.label, required this.icon, required this.color, required this.onTap});
  final String label;
  final IconData icon;
  final Color color;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return OutlinedButton.icon(
      onPressed: onTap,
      icon: Icon(icon, size: 16, color: color),
      label: Text(label, style: TextStyle(color: color)),
      style: OutlinedButton.styleFrom(side: BorderSide(color: color.withValues(alpha: 0.4))),
    );
  }
}
