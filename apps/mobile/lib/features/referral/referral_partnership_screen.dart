import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/services/referral_partnership_service.dart';
import 'package:raje3_mobile/core/services/services_catalogue_service.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/models/referral_partnership_model.dart';
import 'package:raje3_mobile/models/service_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/widgets/effects/game_effects.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';
import 'package:raje3_mobile/widgets/rj_sheen.dart';

/// «شراكة استراتيجية» — mobile mirror of apps/console/src/screens/ReferralPartnership.tsx's own
/// real, decided design: a PARTNER-CENTRIC view (every agreement with the same other shop groups
/// under one card, because the real question is "how is this relationship doing", never "what
/// does row 14 say"), a scorecard computed CLIENT-SIDE per partner on demand (the server only
/// aggregates across every partner at once — see `_scorecardFor` below), and terms that are
/// immutable once proposed (no edit route exists anywhere; a different grant is a new agreement).
///
/// NOT «ولاء الشركاء» (`partner-loyalty`, a subscription-price discount between our own two
/// shops) — this moves real customers between two real shops on their own catalogues, mutual
/// consent only. Zero backend work here: the 9-route contract already exists and is proven live
/// by the console (parity/referral.md).
class ReferralPartnershipScreen extends StatefulWidget {
  const ReferralPartnershipScreen({super.key});

  @override
  State<ReferralPartnershipScreen> createState() => _ReferralPartnershipScreenState();
}

class _ReferralPartnershipScreenState extends State<ReferralPartnershipScreen> {
  late final _service = ReferralPartnershipService(apiClient: context.read<AuthProvider>().apiClient);
  late final _catalogue = ServicesCatalogueService(apiClient: context.read<AuthProvider>().apiClient);

  List<ReferralAgreement>? _rows;
  bool _failed = false;
  ReferralKpis? _kpis;
  bool _kpiAsReferrer = true;
  String _roleFilter = 'all'; // all | referrer | beneficiary

  @override
  void initState() {
    super.initState();
    _load();
    _service.kpis().then((k) {
      if (mounted) setState(() => _kpis = k);
    });
  }

  Future<void> _load() async {
    final result = await _service.list();
    if (!mounted) return;
    setState(() {
      _rows = result;
      _failed = result == null;
    });
  }

  String get _myTenant => context.read<AuthProvider>().user?.id ?? '';

  Map<String, List<ReferralAgreement>> get _groups {
    final map = <String, List<ReferralAgreement>>{};
    for (final r in _rows ?? const <ReferralAgreement>[]) {
      if (_roleFilter != 'all' && r.myRole(_myTenant) != _roleFilter) continue;
      final key = r.otherParty(_myTenant);
      (map[key] ??= []).add(r);
    }
    for (final list in map.values) {
      list.sort((a, b) => b.startedAt.compareTo(a.startedAt));
    }
    return map;
  }

  String _activityFor(List<ReferralAgreement> rows) {
    if (rows.any((r) => r.status == 'active')) return 'active';
    if (rows.any((r) => r.status == 'paused' || r.status == 'cancel_requested')) return 'paused';
    if (rows.any((r) => r.status == 'proposed')) return 'pending';
    return 'inactive';
  }

  void _openPropose() {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _ProposeSheet(service: _service, catalogue: _catalogue, onDone: _load),
    );
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final dark = context.isDark;
    final accent = dark ? AppDarkColors.accent : AppColors.accent;

    final groupsEntries = _groups.entries.toList()
      ..sort((a, b) {
        const rank = {'active': 0, 'paused': 1, 'pending': 2, 'inactive': 3};
        final ra = rank[_activityFor(a.value)] ?? 3;
        final rb = rank[_activityFor(b.value)] ?? 3;
        if (ra != rb) return ra.compareTo(rb);
        return b.value.length.compareTo(a.value.length);
      });

    return KbAnchor(
      id: 'referral-partnership',
      child: Scaffold(
      backgroundColor: AppColors.surface0,
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _openPropose,
        icon: const Icon(Icons.add_rounded),
        label: Text(s.referralProposeButton),
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          await _load();
          final k = await _service.kpis();
          if (mounted) setState(() => _kpis = k);
        },
        child: CustomScrollView(
          slivers: [
            SliverToBoxAdapter(
              child: Container(
                decoration: BoxDecoration(
                  gradient: primaryGradient(dark: dark),
                  borderRadius: const BorderRadius.vertical(bottom: Radius.circular(AppRadius.card)),
                  boxShadow: dark ? AppShadows.darkButton : AppShadows.button,
                ),
                child: SafeArea(
                  bottom: false,
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.md, AppSpacing.lg, AppSpacing.lg),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(s.referralTitle,
                            style: AppTextStyles.displaySmall.copyWith(color: AppColors.accentContrast)),
                        const SizedBox(height: 2),
                        Text(s.referralSubtitle,
                            style: AppTextStyles.bodySmall.copyWith(color: AppColors.accentContrast.withValues(alpha: 0.85))),
                        const SizedBox(height: AppSpacing.md),
                        if (_kpis != null) _KpiPanel(kpis: _kpis!, asReferrer: _kpiAsReferrer,
                            onToggle: (v) => setState(() => _kpiAsReferrer = v), s: s),
                      ],
                    ),
                  ),
                ),
              ),
            ),
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(AppSpacing.md, AppSpacing.md, AppSpacing.md, 0),
              sliver: SliverToBoxAdapter(
                child: SegmentedFilter<String>(
                  value: _roleFilter,
                  onChanged: (v) => setState(() => _roleFilter = v),
                  options: [
                    SegmentedFilterOption(value: 'all', label: s.referralRoleAll),
                    SegmentedFilterOption(value: 'referrer', label: s.referralRoleReferrer),
                    SegmentedFilterOption(value: 'beneficiary', label: s.referralRoleBeneficiary),
                  ],
                ),
              ),
            ),
            if (_rows == null && !_failed)
              const SliverFillRemaining(hasScrollBody: false, child: AppLoadingIndicator())
            else if (_failed)
              SliverFillRemaining(
                hasScrollBody: false,
                child: EmptyState(
                  icon: Icons.cloud_off_rounded,
                  title: s.referralLoadFailed,
                  actionText: s.mobileRequestsRetry,
                  onAction: _load,
                ),
              )
            else if (groupsEntries.isEmpty)
              SliverFillRemaining(
                hasScrollBody: false,
                child: EmptyState(icon: Icons.volunteer_activism_outlined, title: s.referralEmptyTitle),
              )
            else
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(AppSpacing.md, AppSpacing.sm, AppSpacing.md, AppSpacing.xxl),
                sliver: SliverList.separated(
                  itemCount: groupsEntries.length,
                  separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
                  itemBuilder: (context, i) {
                    final entry = groupsEntries[i];
                    return _PartnerCard(
                      partnerId: entry.key,
                      agreements: entry.value,
                      activity: _activityFor(entry.value),
                      myTenant: _myTenant,
                      service: _service,
                      accent: accent,
                      onActed: _load,
                    );
                  },
                ),
              ),
          ],
        ),
      ),
      ),
    );
  }
}

class _KpiPanel extends StatelessWidget {
  const _KpiPanel({required this.kpis, required this.asReferrer, required this.onToggle, required this.s});
  final ReferralKpis kpis;
  final bool asReferrer;
  final ValueChanged<bool> onToggle;
  final S s;

  @override
  Widget build(BuildContext context) {
    final data = asReferrer ? kpis.asReferrer : kpis.asBeneficiary;
    return Container(
      padding: const EdgeInsets.all(AppSpacing.sm),
      decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.12), borderRadius: AppRadius.standardRadius),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(2),
            decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.14), borderRadius: BorderRadius.circular(AppRadius.pill)),
            child: Row(
              children: [
                Expanded(child: _kpiTab(context, s.referralKpiAsReferrer, asReferrer, () => onToggle(true))),
                Expanded(child: _kpiTab(context, s.referralKpiAsBeneficiary, !asReferrer, () => onToggle(false))),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
          Row(
            children: [
              Expanded(child: _stat(s.referralKpiSent, data.referralsSent)),
              Expanded(child: _stat(s.referralKpiRedeemed, data.redeemed)),
              Expanded(child: _stat(s.referralKpiRate, (data.redemptionRate * 100).round(), suffix: '%')),
            ],
          ),
        ],
      ),
    );
  }

  Widget _kpiTab(BuildContext context, String label, bool selected, VoidCallback onTap) {
    return Material(
      color: selected ? Colors.white.withValues(alpha: 0.22) : Colors.transparent,
      borderRadius: BorderRadius.circular(AppRadius.pill),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppRadius.pill),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 7),
          child: Text(label, textAlign: TextAlign.center,
              style: AppTextStyles.caption.copyWith(color: Colors.white, fontWeight: selected ? FontWeight.w800 : FontWeight.w500)),
        ),
      ),
    );
  }

  Widget _stat(String label, int value, {String suffix = ''}) {
    return Column(
      children: [
        // A COUNT-UP, not a static number — this row is the first thing an owner's eye lands on
        // after every pull-to-refresh, and a moving number reads as "this is live data", the same
        // reason the console's own dashboard tiles animate.
        TweenAnimationBuilder<int>(
          tween: IntTween(begin: 0, end: value),
          duration: const Duration(milliseconds: 700),
          curve: Curves.easeOutCubic,
          builder: (context, v, _) => Text('$v$suffix', style: AppTextStyles.headlineSmall.copyWith(color: Colors.white)),
        ),
        const SizedBox(height: 2),
        Text(label, style: AppTextStyles.caption.copyWith(color: Colors.white.withValues(alpha: 0.8))),
      ],
    );
  }
}

const Map<String, Color> _statusTone = {
  'proposed': AppColors.accent,
  'active': AppColors.success,
  'paused': AppColors.warning,
  'cancel_requested': AppColors.warning,
  'ended': AppColors.textMuted,
  'rejected': AppColors.danger,
  'expired_unanswered': AppColors.textMuted,
};

const Map<String, Color> _activityDot = {
  'active': AppColors.success,
  'paused': AppColors.warning,
  'pending': AppColors.accent,
  'inactive': AppColors.textMuted,
};

class _PartnerCard extends StatefulWidget {
  const _PartnerCard({
    required this.partnerId, required this.agreements, required this.activity,
    required this.myTenant, required this.service, required this.accent, required this.onActed,
  });
  final String partnerId;
  final List<ReferralAgreement> agreements;
  final String activity;
  final String myTenant;
  final ReferralPartnershipService service;
  final Color accent;
  final VoidCallback onActed;

  @override
  State<_PartnerCard> createState() => _PartnerCardState();
}

class _PartnerCardState extends State<_PartnerCard> {
  bool _expanded = false;
  Map<String, List<ReferralAuditEntry>>? _entriesByAgreement;
  bool _entriesFailed = false;
  String? _busyId;

  Future<void> _loadEntries() async {
    if (_entriesByAgreement != null || _entriesFailed) return;
    final results = await Future.wait(widget.agreements.map((a) => widget.service.auditLog(a.id)));
    if (!mounted) return;
    if (results.any((r) => r == null)) {
      setState(() => _entriesFailed = true);
      return;
    }
    final map = <String, List<ReferralAuditEntry>>{};
    for (var i = 0; i < widget.agreements.length; i++) {
      map[widget.agreements[i].id] = results[i]!;
    }
    setState(() => _entriesByAgreement = map);
  }

  ({int granted, int redeemed})? get _scorecard {
    final entries = _entriesByAgreement;
    if (entries == null) return null;
    var granted = 0, redeemed = 0;
    for (final list in entries.values) {
      for (final e in list) {
        if (e.event == 'grant_created') granted++;
        if (e.event == 'grant_redeemed') redeemed++;
      }
    }
    return (granted: granted, redeemed: redeemed);
  }

  List<ReferralAuditEntry>? get _timeline {
    final entries = _entriesByAgreement;
    if (entries == null) return null;
    final all = entries.values.expand((x) => x).toList()..sort((a, b) => b.created.compareTo(a.created));
    return all.take(12).toList();
  }

  Future<void> _act(Future<bool> Function(String) call, String id, {String? confirmMessage, bool celebrateOnSuccess = false}) async {
    final s = S.of(context)!;
    if (_busyId != null) return;
    if (confirmMessage != null) {
      final ok = await showDialog<bool>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          content: Text(confirmMessage),
          actions: [
            TextButton(onPressed: () => Navigator.of(dialogContext).pop(false), child: Text(s.mobileRequestsRejectCancel)),
            TextButton(onPressed: () => Navigator.of(dialogContext).pop(true), child: Text(s.referralConfirm)),
          ],
        ),
      );
      if (ok != true) return;
    }
    setState(() => _busyId = id);
    final ok = await call(id);
    if (!mounted) return;
    setState(() {
      _busyId = null;
      if (ok) {
        _entriesByAgreement = null;
        _entriesFailed = false;
      }
    });
    // A new partnership going live is the one real "win" moment on this screen — restrained to
    // just this, per GameEffects's own doctrine (meaningful progress, not volume on every tap).
    if (ok && celebrateOnSuccess) GameEffects.celebrate(context);
    if (ok) widget.onActed();
  }

  String _activityLabel(String activity, S s) {
    switch (activity) {
      case 'active': return s.referralActivityActive;
      case 'paused': return s.referralActivityPaused;
      case 'pending': return s.referralActivityPending;
      default: return s.referralActivityInactive;
    }
  }

  String _grantLine(ReferralAgreement a, S s) {
    if (a.grantType == 'gift') return s.referralGrantGift(a.giftServiceName);
    if (a.discountScope == 'item') return s.referralGrantDiscountItem(a.giftServiceName);
    if (a.discountScope == 'group') return s.referralGrantDiscountGroup(a.discountGroupName);
    return s.referralGrantDiscountBlanket;
  }

  String _statusLabel(String status, S s) {
    switch (status) {
      case 'proposed': return s.referralStatusProposed;
      case 'active': return s.referralStatusActive;
      case 'paused': return s.referralStatusPaused;
      case 'cancel_requested': return s.referralStatusCancelRequested;
      case 'ended': return s.referralStatusEnded;
      case 'rejected': return s.referralStatusRejected;
      case 'expired_unanswered': return s.referralStatusExpiredUnanswered;
      default: return status;
    }
  }

  String _eventLabel(String event, S s) {
    switch (event) {
      case 'proposed': return s.referralEventProposed;
      case 'accepted': return s.referralEventAccepted;
      case 'rejected': return s.referralEventRejected;
      case 'activated': return s.referralEventActivated;
      case 'cancel_requested': return s.referralEventCancelRequested;
      case 'cancel_confirmed': return s.referralEventCancelConfirmed;
      case 'expired_unanswered': return s.referralEventExpiredUnanswered;
      case 'paused': return s.referralEventPaused;
      case 'resumed': return s.referralEventResumed;
      case 'ended_term': return s.referralEventEndedTerm;
      case 'grant_created': return s.referralEventGrantCreated;
      case 'grant_redeemed': return s.referralEventGrantRedeemed;
      default: return event;
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final colors = context.appColors;
    final dark = context.isDark;
    final dot = _activityDot[widget.activity] ?? AppColors.textMuted;

    return RjSheen(
      borderRadius: AppRadius.cardRadius,
      tint: widget.accent,
      child: Container(
        decoration: BoxDecoration(
          color: colors.surface,
          borderRadius: AppRadius.cardRadius,
          // A COLORED LEADING STRIPE per activity — the same "color says state at a glance"
          // convention procedures_tab's severity stripe already established, so a busy owner
          // scanning ten partner cards reads active/paused/pending/inactive from the edge alone,
          // not from a small centred dot that reads the same at any scroll speed.
          border: BorderDirectional(
            start: BorderSide(color: dot, width: 3),
            top: BorderSide(color: colors.borderSubtle),
            end: BorderSide(color: colors.borderSubtle),
            bottom: BorderSide(color: colors.borderSubtle),
          ),
          boxShadow: dark ? AppShadows.darkCard : AppShadows.card,
        ),
        clipBehavior: Clip.antiAlias,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Material(
              color: Colors.transparent,
              child: InkWell(
                onTap: () {
                  setState(() => _expanded = !_expanded);
                  if (_expanded) _loadEntries();
                },
                child: Padding(
                  padding: const EdgeInsets.all(AppSpacing.md),
                  child: Row(
                    children: [
                      Container(
                        width: 10, height: 10,
                        decoration: BoxDecoration(shape: BoxShape.circle, color: dot, boxShadow: [
                          BoxShadow(color: dot.withValues(alpha: 0.5), blurRadius: 6, spreadRadius: 1),
                        ]),
                      ),
                      const SizedBox(width: AppSpacing.sm),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(widget.partnerId,
                                maxLines: 1, overflow: TextOverflow.ellipsis,
                                style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w700)),
                            const SizedBox(height: 2),
                            Text('${_activityLabel(widget.activity, s)} · ${s.referralPartnerCount(widget.agreements.length)}',
                                style: AppTextStyles.caption.copyWith(color: colors.textSecondary)),
                          ],
                        ),
                      ),
                      AnimatedRotation(
                        turns: _expanded ? 0.5 : 0,
                        duration: const Duration(milliseconds: 180),
                        child: Icon(Icons.expand_more_rounded, color: colors.textMuted),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            if (_expanded)
              Padding(
                padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.md),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Divider(),
                    Text(s.referralScorecardTitle, style: AppTextStyles.labelMedium),
                    const SizedBox(height: 6),
                    if (_entriesFailed)
                      Text(s.referralScorecardFailed, style: AppTextStyles.caption.copyWith(color: AppColors.danger))
                    else if (_scorecard == null)
                      const Padding(padding: EdgeInsets.symmetric(vertical: 4), child: AppLoadingIndicator())
                    else
                      Row(
                        children: [
                          Expanded(child: _miniStat(s.referralKpiSent, _scorecard!.granted, widget.accent)),
                          Expanded(child: _miniStat(s.referralKpiRedeemed, _scorecard!.redeemed, AppColors.success)),
                          Expanded(child: _miniStatText(s.referralKpiRate, _scorecard!.granted > 0
                              ? '${(_scorecard!.redeemed / _scorecard!.granted * 100).round()}%' : '—', colors.textSecondary)),
                        ],
                      ),
                    const SizedBox(height: AppSpacing.md),
                    Text(s.referralActivityTitle, style: AppTextStyles.labelMedium),
                    const SizedBox(height: 6),
                    if (_timeline != null && _timeline!.isEmpty)
                      Text(s.referralActivityEmpty, style: AppTextStyles.caption.copyWith(color: colors.textMuted))
                    else if (_timeline != null)
                      Column(
                        children: [
                          for (final e in _timeline!)
                            Padding(
                              padding: const EdgeInsets.symmetric(vertical: 3),
                              child: Row(
                                children: [
                                  Expanded(child: Text(_eventLabel(e.event, s), style: AppTextStyles.caption)),
                                  Text(_formatDateTime(e.created), style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
                                ],
                              ),
                            ),
                        ],
                      ),
                    const SizedBox(height: AppSpacing.md),
                    Text(s.referralAgreementsTitle, style: AppTextStyles.labelMedium),
                    const SizedBox(height: 6),
                    for (final a in widget.agreements) ...[
                      _AgreementRow(
                        agreement: a,
                        myTenant: widget.myTenant,
                        statusLabel: _statusLabel(a.status, s),
                        statusColor: _statusTone[a.status] ?? colors.textSecondary,
                        grantLine: _grantLine(a, s),
                        busy: _busyId == a.id,
                        s: s,
                        onAccept: () => _act(widget.service.accept, a.id, celebrateOnSuccess: true),
                        onReject: () => _act(widget.service.reject, a.id),
                        onCancelRequest: () => _act(widget.service.cancelRequest, a.id),
                        onCancelConfirm: () => _act(widget.service.cancelConfirm, a.id, confirmMessage: s.referralConfirmCancel),
                      ),
                      const SizedBox(height: 6),
                    ],
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _miniStat(String label, int value, Color color) {
    return Column(
      children: [
        TweenAnimationBuilder<int>(
          tween: IntTween(begin: 0, end: value),
          duration: const Duration(milliseconds: 500),
          curve: Curves.easeOutCubic,
          builder: (context, v, _) =>
              Text('$v', style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w800, color: color)),
        ),
        Text(label, style: AppTextStyles.caption.copyWith(color: context.appColors.textSecondary)),
      ],
    );
  }

  Widget _miniStatText(String label, String value, Color color) {
    return Column(
      children: [
        Text(value, style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w800, color: color)),
        Text(label, style: AppTextStyles.caption.copyWith(color: context.appColors.textSecondary)),
      ],
    );
  }

  String _formatDateTime(int ts) {
    if (ts == 0) return '';
    final d = DateTime.fromMillisecondsSinceEpoch(ts * 1000);
    return '${d.day}/${d.month} ${d.hour.toString().padLeft(2, '0')}:${d.minute.toString().padLeft(2, '0')}';
  }
}

class _AgreementRow extends StatelessWidget {
  const _AgreementRow({
    required this.agreement, required this.myTenant, required this.statusLabel, required this.statusColor,
    required this.grantLine, required this.busy, required this.s,
    required this.onAccept, required this.onReject, required this.onCancelRequest, required this.onCancelConfirm,
  });
  final ReferralAgreement agreement;
  final String myTenant;
  final String statusLabel;
  final Color statusColor;
  final String grantLine;
  final bool busy;
  final S s;
  final VoidCallback onAccept;
  final VoidCallback onReject;
  final VoidCallback onCancelRequest;
  final VoidCallback onCancelConfirm;

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final role = agreement.myRole(myTenant);
    final roleColor = role == 'referrer' ? (context.isDark ? AppDarkColors.accent : AppColors.accent) : AppColors.success;
    return Container(
      padding: const EdgeInsets.all(AppSpacing.sm),
      decoration: BoxDecoration(
        color: roleColor.withValues(alpha: 0.05),
        border: Border.all(color: colors.borderSubtle),
        borderRadius: AppRadius.standardRadius,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              // A FULL COLORED PILL, not a 14px icon — the icon alone read as decoration at a
              // glance; the role (who moves the customer, who pays the grant) is the first thing
              // an owner needs to tell two rows apart by, so it now carries the same visual weight
              // as the status pill beside it.
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(color: roleColor.withValues(alpha: 0.14), borderRadius: BorderRadius.circular(AppRadius.pill)),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(role == 'referrer' ? Icons.north_east_rounded : Icons.south_west_rounded, size: 12, color: roleColor),
                    const SizedBox(width: 3),
                    Text(role == 'referrer' ? s.referralRoleReferrer : s.referralRoleBeneficiary,
                        style: AppTextStyles.caption.copyWith(color: roleColor, fontWeight: FontWeight.w700)),
                  ],
                ),
              ),
              const SizedBox(width: 6),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(color: statusColor.withValues(alpha: 0.14), borderRadius: BorderRadius.circular(AppRadius.pill)),
                child: Text(statusLabel, style: AppTextStyles.caption.copyWith(color: statusColor, fontWeight: FontWeight.w700)),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(grantLine, style: AppTextStyles.caption.copyWith(color: colors.textSecondary)),
          if (busy)
            const Padding(padding: EdgeInsets.only(top: 6), child: SizedBox(height: 16, width: 16, child: CircularProgressIndicator(strokeWidth: 2)))
          else if (agreement.status == 'proposed' && agreement.shopB == myTenant)
            KbAnchor(
              id: 'referral.row_accept_reject',
              child: Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Row(
                children: [
                  TextButton(onPressed: onAccept, child: Text(s.referralActionAccept)),
                  TextButton(onPressed: onReject, child: Text(s.referralActionReject, style: const TextStyle(color: AppColors.danger))),
                ],
              ),
              ),
            )
          else if (agreement.status == 'proposed')
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(s.referralActionWaitingThem, style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
            )
          else if (agreement.status == 'active')
            KbAnchor(
              id: 'referral.row_cancel_request',
              child: Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Align(
                alignment: AlignmentDirectional.centerStart,
                child: TextButton(onPressed: onCancelRequest, child: Text(s.referralActionCancelRequest)),
              ),
              ),
            )
          else if (agreement.status == 'cancel_requested')
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: agreement.cancelRequestedBy == myTenant
                  ? Text(s.referralActionWaitingThem, style: AppTextStyles.caption.copyWith(color: colors.textMuted))
                  : KbAnchor(
                      id: 'referral.row_cancel_confirm',
                      child: Align(
                      alignment: AlignmentDirectional.centerStart,
                      child: TextButton(
                          onPressed: onCancelConfirm,
                          child: Text(s.referralActionCancelConfirm, style: const TextStyle(color: AppColors.danger))),
                      ),
                    ),
            ),
        ],
      ),
    );
  }
}

class _ProposeSheet extends StatefulWidget {
  const _ProposeSheet({required this.service, required this.catalogue, required this.onDone});
  final ReferralPartnershipService service;
  final ServicesCatalogueService catalogue;
  final VoidCallback onDone;

  @override
  State<_ProposeSheet> createState() => _ProposeSheetState();
}

class _ProposeSheetState extends State<_ProposeSheet> {
  final _phoneController = TextEditingController();
  final _riyalsController = TextEditingController(text: '50');
  final _grantValidityController = TextEditingController(text: '30');
  final _durationController = TextEditingController(text: '90');
  final _capController = TextEditingController(text: '0');

  String _conditionType = 'min_total_minor';
  String _conditionServiceId = '';
  String _grantType = 'discount';
  String _discountScope = 'blanket';
  String _giftServiceId = '';
  String _discountGroupId = '';

  List<ServiceItem>? _services;
  List<ServicePackage>? _packages;
  bool _submitting = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    widget.catalogue.list().then((v) { if (mounted) setState(() => _services = (v ?? const []).where((x) => x.active).toList()); });
    widget.catalogue.listPackages().then((v) { if (mounted) setState(() => _packages = (v ?? const []).where((x) => x.active).toList()); });
  }

  @override
  void dispose() {
    _phoneController.dispose();
    _riyalsController.dispose();
    _grantValidityController.dispose();
    _durationController.dispose();
    _capController.dispose();
    super.dispose();
  }

  bool get _needsService => _grantType == 'gift' || (_grantType == 'discount' && _discountScope == 'item');
  bool get _needsGroup => _grantType == 'discount' && _discountScope == 'group';

  bool get _valid =>
      _phoneController.text.trim().length >= 9 &&
      (_conditionType == 'min_total_minor' ? (int.tryParse(_riyalsController.text) ?? 0) > 0 : _conditionServiceId.isNotEmpty) &&
      (!_needsService || _giftServiceId.isNotEmpty) &&
      (!_needsGroup || _discountGroupId.isNotEmpty);

  Future<void> _submit() async {
    final s = S.of(context)!;
    if (!_valid || _submitting) return;
    setState(() { _submitting = true; _error = null; });
    final riyals = int.tryParse(_riyalsController.text) ?? 0;
    final (agreement, statusCode) = await widget.service.propose(
      shopBPhone: _phoneController.text.trim(),
      conditionType: _conditionType,
      conditionValue: _conditionType == 'min_total_minor' ? '${riyals * 100}' : _conditionServiceId,
      grantValidityDays: int.tryParse(_grantValidityController.text) ?? 30,
      agreementDurationDays: int.tryParse(_durationController.text) ?? 90,
      perPeriodCap: int.tryParse(_capController.text) ?? 0,
      grantType: _grantType,
      giftServiceId: _needsService ? _giftServiceId : '',
      discountScope: _grantType == 'discount' ? _discountScope : 'blanket',
      discountGroupId: _needsGroup ? _discountGroupId : '',
    );
    if (!mounted) return;
    setState(() => _submitting = false);
    if (agreement == null) {
      setState(() => _error = _refusalMessage(statusCode, s));
      return;
    }
    widget.onDone();
    Navigator.of(context).pop();
  }

  /// THE TEXT REASON NEVER REACHES THIS CLIENT (see `ReferralPartnershipService.propose`'s own
  /// note), but the HTTP status is real and `_referral_error()` on the server maps every actual
  /// refusal onto one of a handful of statuses — so this names the REAL possibilities behind
  /// that exact status, never a guessed single cause.
  String _refusalMessage(int? statusCode, S s) {
    switch (statusCode) {
      case 402: return s.referralRefusal402;
      case 403: return s.referralRefusal403;
      case 400: return s.referralRefusal400;
      case 404: return s.referralRefusal404;
      case 409: return s.referralRefusal409;
      case 503: return s.referralRefusal503;
      default: return s.referralProposeResultFail;
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final colors = context.appColors;
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: Container(
        constraints: BoxConstraints(maxHeight: appSheetMaxHeight(context)),
        decoration: const BoxDecoration(
          color: AppColors.surface1,
          borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(height: 10),
            Container(width: 36, height: 4, decoration: BoxDecoration(color: colors.borderSubtle, borderRadius: BorderRadius.circular(2))),
            // `Flexible` (loose fit), never `Expanded` — `Expanded` forces this to always consume
            // the FULL `appSheetMaxHeight` cap even when the form's real content is shorter, which
            // is the bug this replaced: a two-field form opening as tall as a twelve-field one.
            // `Flexible` lets the sheet hug its own content and only grow up to the cap.
            Flexible(
              child: SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.md, AppSpacing.lg, AppSpacing.lg),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(s.referralProposeTitle, style: AppTextStyles.headlineSmall),
                    const SizedBox(height: AppSpacing.md),
                    KbAnchor(
                      id: 'referral.propose_phone_field',
                      child: AppTextField(labelText: s.referralProposePhoneLabel, controller: _phoneController,
                          keyboardType: TextInputType.phone, onChanged: (_) => setState(() {})),
                    ),
                    const SizedBox(height: AppSpacing.md),
                    Text(s.referralProposeConditionLabel, style: AppTextStyles.labelMedium),
                    const SizedBox(height: 6),
                    SegmentedFilter<String>(
                      value: _conditionType,
                      onChanged: (v) => setState(() => _conditionType = v),
                      options: [
                        SegmentedFilterOption(value: 'min_total_minor', label: s.referralConditionMinTotal),
                        SegmentedFilterOption(value: 'service_id', label: s.referralConditionServiceId),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    KbAnchor(
                      id: 'referral.propose_condition_fields',
                      child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                    if (_conditionType != 'min_total_minor')
                      _picker(
                        label: s.referralProposeConditionValueService,
                        items: (_services ?? const []).map((x) => (x.id, x.name)).toList(),
                        value: _conditionServiceId,
                        onChanged: (v) => setState(() => _conditionServiceId = v ?? ''),
                      ),
                    if (_conditionType != 'min_total_minor') const SizedBox(height: AppSpacing.sm),
                    Row(
                      children: [
                        if (_conditionType == 'min_total_minor') ...[
                          Expanded(child: AppTextField(labelText: s.referralProposeConditionValueRiyals, controller: _riyalsController,
                              keyboardType: TextInputType.number, onChanged: (_) => setState(() {}))),
                          const SizedBox(width: 8),
                        ],
                        Expanded(child: AppTextField(labelText: s.referralProposeValidityLabel, controller: _grantValidityController,
                            keyboardType: TextInputType.number)),
                        const SizedBox(width: 8),
                        Expanded(child: AppTextField(labelText: s.referralProposeDurationLabel, controller: _durationController,
                            keyboardType: TextInputType.number)),
                        const SizedBox(width: 8),
                        Expanded(child: AppTextField(labelText: s.referralProposeCapLabel, controller: _capController,
                            keyboardType: TextInputType.number)),
                      ],
                    ),
                      ],
                      ),
                    ),
                    const SizedBox(height: AppSpacing.md),
                    Text(s.referralProposeGrantTypeLabel, style: AppTextStyles.labelMedium),
                    const SizedBox(height: 6),
                    SegmentedFilter<String>(
                      value: _grantType,
                      onChanged: (v) => setState(() => _grantType = v),
                      options: [
                        SegmentedFilterOption(value: 'discount', label: s.referralGrantTypeDiscount),
                        SegmentedFilterOption(value: 'gift', label: s.referralGrantTypeGift),
                      ],
                    ),
                    if (_grantType == 'discount') ...[
                      const SizedBox(height: AppSpacing.sm),
                      SegmentedFilter<String>(
                        value: _discountScope,
                        onChanged: (v) => setState(() => _discountScope = v),
                        options: [
                          SegmentedFilterOption(value: 'blanket', label: s.referralScopeBlanket),
                          SegmentedFilterOption(value: 'item', label: s.referralScopeItem),
                          if ((_packages ?? const []).isNotEmpty)
                            SegmentedFilterOption(value: 'group', label: s.referralScopeGroup),
                        ],
                      ),
                    ],
                    if (_needsService) ...[
                      const SizedBox(height: AppSpacing.sm),
                      _picker(
                        label: s.referralProposeServiceLabel,
                        items: (_services ?? const []).map((x) => (x.id, x.name)).toList(),
                        value: _giftServiceId,
                        onChanged: (v) => setState(() => _giftServiceId = v ?? ''),
                      ),
                    ],
                    if (_needsGroup) ...[
                      const SizedBox(height: AppSpacing.sm),
                      _picker(
                        label: s.referralProposeGroupLabel,
                        items: (_packages ?? const []).map((x) => (x.id, x.name)).toList(),
                        value: _discountGroupId,
                        onChanged: (v) => setState(() => _discountGroupId = v ?? ''),
                      ),
                    ],
                    const SizedBox(height: 4),
                    Text(s.referralProposeImmutableNote, style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
                    if (_error != null) ...[
                      const SizedBox(height: 6),
                      Text(_error!, style: AppTextStyles.caption.copyWith(color: AppColors.danger)),
                    ],
                    const SizedBox(height: AppSpacing.lg),
                    SizedBox(
                      width: double.infinity,
                      child: PrimaryButton(
                        text: _submitting ? s.referralProposeSubmitting : s.referralProposeSubmit,
                        onPressed: (!_valid || _submitting) ? null : _submit,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _picker({required String label, required List<(String, String)> items, required String value, required ValueChanged<String?> onChanged}) {
    return DropdownButtonFormField<String>(
      initialValue: value.isEmpty ? null : value,
      decoration: InputDecoration(labelText: label),
      items: [for (final (id, name) in items) DropdownMenuItem(value: id, child: Text(name, overflow: TextOverflow.ellipsis))],
      onChanged: onChanged,
    );
  }
}
