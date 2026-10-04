import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show Clipboard, ClipboardData;
import 'package:provider/provider.dart';

import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/providers/nav_provider.dart';
import 'package:raje3_mobile/core/services/mobile_requests_service.dart';
import 'package:raje3_mobile/core/utils/formatters.dart';
import 'package:raje3_mobile/core/utils/maps_link.dart';
import 'package:raje3_mobile/core/utils/snackbar_helper.dart';
import 'package:raje3_mobile/core/utils/url_helper.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/models/mobile_request_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/widgets/brand_loading_indicator.dart';
import 'package:raje3_mobile/widgets/capability_gate.dart';
import 'package:raje3_mobile/widgets/date_time_picker_sheet.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';

/// «خدمات متنقلة» — mobile mirror of apps/console/src/screens/MobileRequests.tsx: the shop's own
/// review queue for a service that travels TO the customer. Same state machine, same real
/// endpoints (services/operations/app/core/mobile_requests.py), same "طلبات تترص وانتهينا" rule
/// (no staff distribution/slot booking — a request lands, the shop accepts/rejects, then marks
/// «تم»/«لم يتم»). Built fresh for this screen's own touch-first shape — cards you tap and swipe,
/// a bottom sheet instead of a modal — never a literal copy of the console's layout.
class MobileRequestsScreen extends StatefulWidget {
  const MobileRequestsScreen({super.key});

  @override
  State<MobileRequestsScreen> createState() => _MobileRequestsScreenState();
}

const int _needsDecisionGraceMinutes = 30;

bool _isNeedsDecision(MobileServiceRequest r, int nowSeconds) {
  return r.status == 'accepted' &&
      nowSeconds - r.requestedTime > _needsDecisionGraceMinutes * 60;
}

enum _Filter { all, pending, accepted, needsDecision, completed, closed }

class _MobileRequestsScreenState extends State<MobileRequestsScreen> {
  late final MobileRequestsService _service;

  List<MobileServiceRequest>? _rows; // null while loading
  bool _loadFailed = false;
  Map<String, String> _services = {};
  List<MobileRequestOperator> _operators = [];
  final Map<String, NoShowRisk> _risks = {};
  _Filter _filter = _Filter.all;
  String _search = '';
  String? _busyId;
  int _now = DateTime.now().millisecondsSinceEpoch ~/ 1000;
  Timer? _clock;

  @override
  void initState() {
    super.initState();
    _service = MobileRequestsService(apiClient: context.read<AuthProvider>().apiClient);
    _clock = Timer.periodic(const Duration(seconds: 60), (_) {
      if (mounted) setState(() => _now = DateTime.now().millisecondsSinceEpoch ~/ 1000);
    });
    _load();
    _loadSideData();
  }

  @override
  void dispose() {
    _clock?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _rows = null;
      _loadFailed = false;
    });
    final result = await _service.list();
    if (!mounted) return;
    setState(() {
      _rows = result ?? [];
      _loadFailed = result == null;
    });
    _loadRisksFor(result ?? []);
  }

  Future<void> _loadSideData() async {
    final catalog = context.read<NavProvider>().catalog;
    if (catalog.hasAll(['operations.list_services']) ||
        catalog.hasAll(['operations.manage_services'])) {
      dynamic body;
      try {
        final response = await context
            .read<AuthProvider>()
            .apiClient
            .dio
            .get<dynamic>('/api/v1/field/catalogue');
        body = response.data;
      } on DioException {
        body = null;
      }
      if (body is Map && mounted) {
        final list = (body['services'] as List?) ?? const [];
        setState(() {
          _services = {
            for (final s in list.whereType<Map>())
              (s['id'] as String? ?? ''): (s['name'] as String? ?? ''),
          };
        });
      }
    }
    if (catalog.hasAll(['operations.list_operators'])) {
      final ops = await _service.operators();
      if (ops != null && mounted) setState(() => _operators = ops);
    }
  }

  Future<void> _loadRisksFor(List<MobileServiceRequest> rows) async {
    final catalog = context.read<NavProvider>().catalog;
    if (!catalog.hasAll(['operations.mobile_request_risk'])) return;
    final pending = rows.where((r) => r.status == 'pending' && !_risks.containsKey(r.id));
    for (final r in pending) {
      final risk = await _service.risk(r.id);
      if (risk != null && mounted) setState(() => _risks[r.id] = risk);
    }
  }

  List<MobileServiceRequest> get _list => _rows ?? const [];

  /// How many OPEN requests each operator currently carries — pending + accepted only, a closed
  /// request is no longer "load" on anyone. Computed from the same list already on screen, same
  /// as MobileRequests.tsx's own `assignedCounts` — never a second, staler read.
  Map<String, int> get _assignedCounts {
    final m = <String, int>{};
    for (final r in _list) {
      if (r.assignedTo.isEmpty) continue;
      if (r.status != 'pending' && r.status != 'accepted') continue;
      m[r.assignedTo] = (m[r.assignedTo] ?? 0) + 1;
    }
    return m;
  }

  List<MobileServiceRequest> get _needsDecisionRows =>
      _list.where((r) => _isNeedsDecision(r, _now)).toList(growable: false);

  int get _pendingCount => _list.where((r) => r.status == 'pending').length;

  int get _completedThisMonth {
    final monthStart = DateTime(DateTime.now().year, DateTime.now().month, 1);
    final cutoff = monthStart.millisecondsSinceEpoch ~/ 1000;
    return _list.where((r) => r.status == 'completed' && r.created >= cutoff).length;
  }

  List<MobileServiceRequest> get _filtered {
    var out = _list;
    switch (_filter) {
      case _Filter.pending:
        out = out.where((r) => r.status == 'pending').toList();
      case _Filter.accepted:
        out = out.where((r) => r.status == 'accepted').toList();
      case _Filter.needsDecision:
        out = out.where((r) => _isNeedsDecision(r, _now)).toList();
      case _Filter.completed:
        out = out.where((r) => r.status == 'completed').toList();
      case _Filter.closed:
        out = out.where((r) => r.status == 'rejected' || r.status == 'no_show').toList();
      case _Filter.all:
        break;
    }
    if (_search.trim().isNotEmpty) {
      final q = _search.trim();
      out = out.where((r) => r.customerName.contains(q) || r.phone.contains(q)).toList();
    }
    return [...out]..sort((a, b) => b.created.compareTo(a.created));
  }

  Future<void> _run(String requestId, Future<MobileServiceRequest?> Function() action) async {
    if (_busyId != null) return;
    setState(() => _busyId = requestId);
    final result = await action();
    if (!mounted) return;
    setState(() => _busyId = null);
    if (result != null) {
      _load();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(S.of(context)!.mobileRequestsActionFailed)),
      );
    }
  }

  Future<void> _onReject(MobileServiceRequest r) async {
    final reason = await _askRejectReason();
    if (reason == null) return;
    _run(r.id, () => _service.reject(r.id, reason));
  }

  Future<String?> _askRejectReason() async {
    final s = S.of(context)!;
    final controller = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(s.mobileRequestsRejectTitle),
        content: KbAnchor(
          id: 'mobile-requests.reject_reason_field',
          child: TextField(
          controller: controller,
          decoration: InputDecoration(hintText: s.mobileRequestsRejectHint),
          autofocus: true,
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(), child: Text(s.mobileRequestsRejectCancel)),
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(controller.text.trim()), child: Text(s.mobileRequestsRejectConfirm)),
        ],
      ),
    );
  }

  Future<void> _openAddSheet() async {
    final created = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _AddRequestSheet(
        service: _service,
        services: _services,
        operators: _operators,
      ),
    );
    if (created == true) _load();
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final catalog = context.watch<NavProvider>().catalog;
    // KEPT AS `hasAll`, NOT `CapabilityGate`, ON PURPOSE — each of these five feeds a spacer
    // between two buttons that only appears when BOTH show (e.g. `if (canAccept && canReject)
    // SizedBox(width:...)`, below). `CapabilityGate` swaps one widget for `SizedBox.shrink()`;
    // it cannot answer "are both of these two OTHER gates open", so the spacing logic still
    // needs the plain booleans. Converting only the individual buttons and leaving the spacer
    // reading a mix of the old and new mechanism would be more confusing, not less.
    final canAccept = catalog.hasAll(['operations.mobile_request_accept']);
    final canReject = catalog.hasAll(['operations.mobile_request_reject']);
    final canComplete = catalog.hasAll(['operations.mobile_request_complete']);
    final canNoShow = catalog.hasAll(['operations.mobile_request_no_show']);
    final canAssign = catalog.hasAll(['operations.mobile_request_assign']);

    return KbAnchor(
      id: 'mobile-requests',
      child: Scaffold(
        backgroundColor: AppColors.surface0,
        appBar: AppBar(title: Text(s.mobileRequestsTitle)),
        floatingActionButton: CapabilityGate(
          requires: const ['operations.mobile_request_create'],
          child: KbAnchor(
            id: 'mobile-requests.add_button',
            child: FloatingActionButton.extended(
              onPressed: _openAddSheet,
              icon: const Icon(Icons.add_rounded),
              label: Text(s.mobileRequestsAddOpen),
            ),
          ),
        ),
        body: RefreshIndicator(
          onRefresh: _load,
          child: CustomScrollView(
            slivers: [
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(
                    AppSpacing.md, AppSpacing.md, AppSpacing.md, AppSpacing.sm),
                sliver: SliverToBoxAdapter(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(s.mobileRequestsSubtitle,
                          style:
                              AppTextStyles.bodySmall.copyWith(color: AppColors.textSecondary)),
                      const SizedBox(height: AppSpacing.md),
                      Row(
                        children: [
                          Expanded(
                            child: KpiTile(
                              icon: Icons.schedule_rounded,
                              label: s.mobileRequestsKpiPending,
                              value: Formatters.formatNumber(_pendingCount),
                              tone: KpiTone.info,
                            ),
                          ),
                          const SizedBox(width: AppSpacing.sm),
                          Expanded(
                            child: KpiTile(
                              icon: Icons.warning_amber_rounded,
                              label: s.mobileRequestsKpiNeedsDecision,
                              value: Formatters.formatNumber(_needsDecisionRows.length),
                              tone: KpiTone.warning,
                            ),
                          ),
                          const SizedBox(width: AppSpacing.sm),
                          Expanded(
                            child: KpiTile(
                              icon: Icons.event_available_rounded,
                              label: s.mobileRequestsKpiCompletedMonth,
                              value: Formatters.formatNumber(_completedThisMonth),
                              tone: KpiTone.success,
                            ),
                          ),
                        ],
                      ),
                      if (_needsDecisionRows.isNotEmpty) ...[
                        const SizedBox(height: AppSpacing.sm),
                        _NeedsDecisionBanner(
                          count: _needsDecisionRows.length,
                          onTap: () => setState(() => _filter = _Filter.needsDecision),
                        ),
                      ],
                      const SizedBox(height: AppSpacing.md),
                      SegmentedFilter<_Filter>(
                        value: _filter,
                        onChanged: (v) => setState(() => _filter = v),
                        options: [
                          SegmentedFilterOption(
                              value: _Filter.all, label: s.mobileRequestsFilterAll, badge: _list.length),
                          SegmentedFilterOption(
                              value: _Filter.pending,
                              label: s.mobileRequestsFilterPending,
                              badge: _pendingCount),
                          SegmentedFilterOption(
                              value: _Filter.accepted,
                              label: s.mobileRequestsFilterAccepted,
                              badge: _list.where((r) => r.status == 'accepted').length),
                          SegmentedFilterOption(
                              value: _Filter.needsDecision,
                              label: s.mobileRequestsFilterNeedsDecision,
                              badge: _needsDecisionRows.length),
                          SegmentedFilterOption(
                              value: _Filter.completed,
                              label: s.mobileRequestsFilterCompleted,
                              badge: _list.where((r) => r.status == 'completed').length),
                          SegmentedFilterOption(
                              value: _Filter.closed,
                              label: s.mobileRequestsFilterClosed,
                              badge: _list
                                  .where((r) => r.status == 'rejected' || r.status == 'no_show')
                                  .length),
                        ],
                      ),
                      const SizedBox(height: AppSpacing.sm),
                      KbAnchor(
                        id: 'mobile-requests.search_field',
                        child: AppTextField(
                          hintText: s.mobileRequestsSearchHint,
                          prefixIcon: Icons.search_rounded,
                          onChanged: (v) => setState(() => _search = v),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              if (_rows == null)
                const SliverFillRemaining(hasScrollBody: false, child: BrandLoadingIndicator())
              else if (_loadFailed)
                SliverFillRemaining(
                  hasScrollBody: false,
                  child: EmptyState(
                    icon: Icons.cloud_off_rounded,
                    title: s.mobileRequestsLoadFailedTitle,
                    message: s.mobileRequestsLoadFailedBody,
                    actionText: s.mobileRequestsRetry,
                    onAction: _load,
                  ),
                )
              else if (_filtered.isEmpty)
                SliverFillRemaining(
                  hasScrollBody: false,
                  child: EmptyState(
                    icon: Icons.local_shipping_outlined,
                    title: s.mobileRequestsEmptyTitle,
                    message: s.mobileRequestsEmptyBody,
                  ),
                )
              else
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(
                      AppSpacing.md, 0, AppSpacing.md, AppSpacing.xxl),
                  sliver: SliverList.separated(
                    itemCount: _filtered.length,
                    separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
                    itemBuilder: (context, i) {
                      final r = _filtered[i];
                      return _RequestCard(
                        r: r,
                        now: _now,
                        serviceNames: r.serviceIds.map((id) => _services[id] ?? id).toList(),
                        risk: _risks[r.id],
                        busy: _busyId == r.id,
                        canAccept: canAccept,
                        canReject: canReject,
                        canComplete: canComplete,
                        canNoShow: canNoShow,
                        canAssign: canAssign,
                        operators: _operators,
                        assignedCounts: _assignedCounts,
                        onAccept: () => _run(r.id, () => _service.accept(r.id)),
                        onReject: () => _onReject(r),
                        onComplete: () => _run(r.id, () => _service.complete(r.id)),
                        onNoShow: () => _run(r.id, () => _service.noShow(r.id)),
                        onAssign: (opId) => _run(r.id, () => _service.assign(r.id, opId)),
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

class _NeedsDecisionBanner extends StatelessWidget {
  const _NeedsDecisionBanner({required this.count, required this.onTap});
  final int count;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    return Material(
      color: Colors.transparent,
      borderRadius: AppRadius.standardRadius,
      child: InkWell(
        onTap: onTap,
        borderRadius: AppRadius.standardRadius,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: 10),
          decoration: BoxDecoration(
            color: AppColors.warningSoft,
            border: Border.all(color: AppColors.warning.withValues(alpha: 0.35)),
            borderRadius: AppRadius.standardRadius,
          ),
          child: Row(
            children: [
              const Icon(Icons.warning_amber_rounded, size: 18, color: AppColors.warningOnSoft),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Text(
                  s.mobileRequestsBannerText(count),
                  style:
                      AppTextStyles.labelMedium.copyWith(color: AppColors.warningOnSoft),
                ),
              ),
              Text(s.mobileRequestsBannerGo,
                  style: AppTextStyles.labelMedium
                      .copyWith(color: AppColors.warningOnSoft, fontWeight: FontWeight.w800)),
            ],
          ),
        ),
      ),
    );
  }
}

String _statusLabel(S s, MobileServiceRequest r, bool needsDecision) {
  if (r.status == 'pending') return s.mobileRequestsStatusPending;
  if (r.status == 'accepted' && needsDecision) return s.mobileRequestsStatusNeedsDecision;
  if (r.status == 'accepted') return s.mobileRequestsStatusAccepted;
  if (r.status == 'completed') return s.mobileRequestsStatusCompleted;
  if (r.status == 'no_show') return s.mobileRequestsStatusNoShow;
  return s.mobileRequestsStatusRejected;
}

(Color, Color, IconData?) _statusColors(BuildContext context, MobileServiceRequest r, bool needsDecision) {
  final isDark = context.isDark;
  if (r.status == 'pending') {
    return (isDark ? AppDarkColors.infoSoft : AppColors.infoSoft,
        isDark ? AppDarkColors.infoOnSoft : AppColors.infoOnSoft, null);
  }
  if (r.status == 'accepted' && needsDecision) {
    return (isDark ? AppDarkColors.warningSoft : AppColors.warningSoft,
        isDark ? AppDarkColors.warningOnSoft : AppColors.warningOnSoft, Icons.warning_amber_rounded);
  }
  if (r.status == 'accepted') {
    return (isDark ? AppDarkColors.accentSoft : AppColors.accentSoft,
        isDark ? AppDarkColors.accentOnSoft : AppColors.accentOnSoft, null);
  }
  if (r.status == 'completed') {
    return (isDark ? AppDarkColors.successSoft : AppColors.successSoft,
        isDark ? AppDarkColors.successOnSoft : AppColors.successOnSoft, Icons.check_circle_rounded);
  }
  if (r.status == 'no_show') {
    return (isDark ? AppDarkColors.dangerSoft : AppColors.dangerSoft,
        isDark ? AppDarkColors.dangerOnSoft : AppColors.dangerOnSoft, Icons.cancel_rounded);
  }
  final surfaceAlt = context.appColors.surfaceAlt;
  return (surfaceAlt, context.appColors.textSecondary, null);
}

class _RequestCard extends StatelessWidget {
  const _RequestCard({
    required this.r,
    required this.now,
    required this.serviceNames,
    required this.risk,
    required this.busy,
    required this.canAccept,
    required this.canReject,
    required this.canComplete,
    required this.canNoShow,
    required this.canAssign,
    required this.operators,
    required this.assignedCounts,
    required this.onAccept,
    required this.onReject,
    required this.onComplete,
    required this.onNoShow,
    required this.onAssign,
  });

  final MobileServiceRequest r;
  final int now;
  final List<String> serviceNames;
  final NoShowRisk? risk;
  final bool busy;
  final bool canAccept;
  final bool canReject;
  final bool canComplete;
  final bool canNoShow;
  final bool canAssign;
  final List<MobileRequestOperator> operators;
  final Map<String, int> assignedCounts;
  final VoidCallback onAccept;
  final VoidCallback onReject;
  final VoidCallback onComplete;
  final VoidCallback onNoShow;
  final ValueChanged<String> onAssign;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final locale = Localizations.localeOf(context).languageCode;
    final needsDecision = _isNeedsDecision(r, now);
    final (statusBg, statusFg, statusIcon) = _statusColors(context, r, needsDecision);
    final colors = context.appColors;

    return KbAnchor(
      id: 'mobile-requests.request_card',
      child: Container(
        decoration: BoxDecoration(
          color: colors.surface,
          borderRadius: AppRadius.cardRadius,
          border: Border.all(
            color: needsDecision ? AppColors.warning.withValues(alpha: 0.4) : colors.borderSubtle,
          ),
          boxShadow: context.isDark ? AppShadows.darkCard : AppShadows.card,
        ),
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        r.customerName.isNotEmpty ? r.customerName : s.mobileRequestsUnnamed,
                        style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w700),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 2),
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          InkWell(
                            onTap: () => openWhatsApp(r.phone),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                const Icon(Icons.chat_bubble_rounded,
                                    size: 12, color: Color(0xFF25D366)),
                                const SizedBox(width: 4),
                                Text(r.phone,
                                    style: AppTextStyles.caption.copyWith(
                                      color: colors.textSecondary,
                                      fontFamily: AppTextStyles.englishFont,
                                      fontFeatures: const [FontFeature.tabularFigures()],
                                    )),
                              ],
                            ),
                          ),
                          const SizedBox(width: 6),
                          InkWell(
                            onTap: () async {
                              await Clipboard.setData(ClipboardData(text: r.phone));
                              if (context.mounted) {
                                SnackbarHelper.showSuccess(context, s.mobileRequestsPhoneCopied);
                              }
                            },
                            child: Icon(Icons.copy_rounded, size: 13, color: colors.textMuted),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                  decoration:
                      BoxDecoration(color: statusBg, borderRadius: BorderRadius.circular(AppRadius.pill)),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      if (statusIcon != null) ...[
                        Icon(statusIcon, size: 12, color: statusFg),
                        const SizedBox(width: 4),
                      ],
                      Text(_statusLabel(s, r, needsDecision),
                          style: AppTextStyles.caption
                              .copyWith(color: statusFg, fontWeight: FontWeight.w700)),
                    ],
                  ),
                ),
              ],
            ),
            if (serviceNames.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.sm),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: [
                  for (final name in serviceNames)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: colors.surfaceAlt,
                        borderRadius: BorderRadius.circular(AppRadius.sm),
                      ),
                      child: Text(name,
                          style: AppTextStyles.caption.copyWith(color: colors.textSecondary)),
                    ),
                ],
              ),
            ],
            const SizedBox(height: AppSpacing.sm),
            Row(
              children: [
                Icon(Icons.schedule_rounded, size: 13, color: colors.textMuted),
                const SizedBox(width: 4),
                Expanded(
                  child: Text(
                    Formatters.formatDateTime(
                        DateTime.fromMillisecondsSinceEpoch(r.requestedTime * 1000), locale: locale),
                    style: AppTextStyles.caption.copyWith(color: colors.textSecondary),
                  ),
                ),
                InkWell(
                  onTap: () => openUrl(r.mapsUrl, context),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.location_on_rounded,
                          size: 14, color: context.isDark ? AppDarkColors.accent : AppColors.accent),
                      const SizedBox(width: 2),
                      Text(s.mobileRequestsOpenMap,
                          style: AppTextStyles.caption.copyWith(
                              color: context.isDark ? AppDarkColors.accent : AppColors.accent,
                              fontWeight: FontWeight.w700)),
                    ],
                  ),
                ),
              ],
            ),
            if (risk?.risky == true) ...[
              const SizedBox(height: 6),
              Row(
                children: [
                  const Icon(Icons.error_outline_rounded, size: 13, color: AppColors.danger),
                  const SizedBox(width: 4),
                  Text(s.mobileRequestsRiskyCustomer,
                      style: AppTextStyles.caption
                          .copyWith(color: AppColors.danger, fontWeight: FontWeight.w700)),
                ],
              ),
            ],
            if (r.rejectReason.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(s.mobileRequestsRejectReasonLine(r.rejectReason),
                  style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
            ],
            if (canAssign && (r.status == 'pending' || r.status == 'accepted') && operators.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.sm),
              _AssignRow(
                assignedTo: r.assignedTo,
                operators: operators,
                assignedCounts: assignedCounts,
                busy: busy,
                onAssign: onAssign,
              ),
            ],
            if ((r.status == 'pending' && (canAccept || canReject)) ||
                (r.status == 'accepted' && (canComplete || canNoShow))) ...[
              const SizedBox(height: AppSpacing.md),
              KbAnchor(
                id: 'mobile-requests.card_actions',
                child: Row(
                  children: [
                    if (r.status == 'pending' && canAccept)
                      Expanded(
                        child: SizedBox(
                          height: 40,
                          child: PrimaryButton(
                            text: s.mobileRequestsActionAccept,
                            isLoading: busy,
                            onPressed: busy ? null : onAccept,
                          ),
                        ),
                      ),
                    if (r.status == 'pending' && canAccept && canReject)
                      const SizedBox(width: AppSpacing.sm),
                    if (r.status == 'pending' && canReject)
                      Expanded(
                        child: SizedBox(
                          height: 40,
                          child: _DangerButton(
                            text: s.mobileRequestsActionReject,
                            onPressed: busy ? null : onReject,
                          ),
                        ),
                      ),
                    if (r.status == 'accepted' && canComplete)
                      Expanded(
                        child: SizedBox(
                          height: 40,
                          child: PrimaryButton(
                            text: s.mobileRequestsActionComplete,
                            isLoading: busy,
                            onPressed: busy ? null : onComplete,
                          ),
                        ),
                      ),
                    if (r.status == 'accepted' && canComplete && canNoShow)
                      const SizedBox(width: AppSpacing.sm),
                    if (r.status == 'accepted' && canNoShow)
                      Expanded(
                        child: SizedBox(
                          height: 40,
                          child: _DangerButton(
                            text: s.mobileRequestsActionNoShow,
                            onPressed: busy ? null : onNoShow,
                          ),
                        ),
                      ),
                  ],
                ),
              ),
            ],
            const SizedBox(height: 6),
            Text(
              Formatters.formatTimeAgo(
                  DateTime.fromMillisecondsSinceEpoch(
                      (r.status == 'pending' ? r.created : (r.decidedAt > 0 ? r.decidedAt : r.created)) *
                          1000),
                  locale: locale),
              style: AppTextStyles.caption.copyWith(color: colors.textMuted),
            ),
          ],
        ),
      ),
    );
  }
}

/// A compact danger-toned outline button — the two spots (reject/no-show) [SecondaryButton]'s
/// neutral-accent border does not fit; kept local rather than growing the shared library for a
/// single tint variant no other screen has needed yet.
class _DangerButton extends StatelessWidget {
  const _DangerButton({required this.text, required this.onPressed});
  final String text;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    final danger = context.isDark ? AppDarkColors.danger : AppColors.danger;
    return OutlinedButton(
      onPressed: onPressed,
      style: OutlinedButton.styleFrom(
        foregroundColor: danger,
        side: BorderSide(color: danger.withValues(alpha: onPressed == null ? 0.3 : 0.6)),
        shape: RoundedRectangleBorder(borderRadius: AppRadius.standardRadius),
      ),
      child: Text(text, style: AppTextStyles.button.copyWith(color: danger)),
    );
  }
}

class _AssignRow extends StatelessWidget {
  const _AssignRow({
    required this.assignedTo,
    required this.operators,
    required this.assignedCounts,
    required this.busy,
    required this.onAssign,
  });

  final String assignedTo;
  final List<MobileRequestOperator> operators;
  final Map<String, int> assignedCounts;
  final bool busy;
  final ValueChanged<String> onAssign;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final colors = context.appColors;
    return Row(
      children: [
        Icon(Icons.person_pin_circle_outlined, size: 15, color: colors.textMuted),
        const SizedBox(width: 6),
        Expanded(
          child: DropdownButtonHideUnderline(
            child: DropdownButton<String>(
              isExpanded: true,
              isDense: true,
              value: assignedTo.isEmpty ? '' : assignedTo,
              items: [
                DropdownMenuItem(value: '', child: Text(s.mobileRequestsAssignUnassigned)),
                for (final op in operators)
                  DropdownMenuItem(
                    value: op.id,
                    child: Text(
                      assignedCounts.containsKey(op.id)
                          ? '${op.name} (${assignedCounts[op.id]})'
                          : op.name,
                    ),
                  ),
              ],
              onChanged: busy ? null : (v) => onAssign(v ?? ''),
              style: AppTextStyles.bodySmall.copyWith(color: colors.textPrimary),
            ),
          ),
        ),
      ],
    );
  }
}

/// Plain `HH:MM`, always Western digits — never `TimeOfDay.format(context)`, which resolves
/// through `MaterialLocalizations` and hits the same Eastern-Arabic-digit bug [pickDaySheet]'s
/// own doc comment explains.
String _formatTimeOfDay(TimeOfDay t) =>
    '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';

/// A real Riyadh-local instant, regardless of the device's own timezone — the fixed +03:00 offset
/// services/operations/app/core/riyadh.py already uses (Saudi Arabia observes no DST).
int? _riyadhEpoch(DateTime? day, TimeOfDay? time) {
  if (day == null || time == null) return null;
  final riyadh = DateTime.utc(day.year, day.month, day.day, time.hour, time.minute)
      .subtract(const Duration(hours: 3));
  return riyadh.millisecondsSinceEpoch ~/ 1000;
}

class _AddRequestSheet extends StatefulWidget {
  const _AddRequestSheet({required this.service, required this.services, required this.operators});
  final MobileRequestsService service;
  final Map<String, String> services;
  final List<MobileRequestOperator> operators;

  @override
  State<_AddRequestSheet> createState() => _AddRequestSheetState();
}

class _AddRequestSheetState extends State<_AddRequestSheet> {
  final _phoneController = TextEditingController();
  final _nameController = TextEditingController();
  final _mapsController = TextEditingController();
  final Set<String> _selectedServices = {};
  DateTime? _day;
  TimeOfDay? _time;
  String _operatorId = '';
  bool _submitting = false;
  bool _resolvingLink = false;
  String? _error;

  @override
  void dispose() {
    _phoneController.dispose();
    _nameController.dispose();
    _mapsController.dispose();
    super.dispose();
  }

  /// Cheap, SYNC checks only — a short link's own coordinates are not known until [_submit]
  /// actually resolves it (a real HTTP round trip to Google), the same "resolve at submit time,
  /// not on every keystroke" rule branches_screen.dart's own `_AddBranchSheet` already holds to.
  bool get _canSubmit =>
      _phoneController.text.trim().isNotEmpty &&
      _selectedServices.isNotEmpty &&
      _riyadhEpoch(_day, _time) != null &&
      _mapsController.text.trim().isNotEmpty &&
      !_submitting &&
      !_resolvingLink;

  Future<void> _submit() async {
    final s = S.of(context)!;
    final requestedTime = _riyadhEpoch(_day, _time);
    if (!_canSubmit || requestedTime == null) return;

    final mapsLink = _mapsController.text.trim();
    final resolving = isShortGoogleMapsLink(mapsLink);
    if (resolving) setState(() => _resolvingLink = true);
    final location = await resolveGoogleMapsLink(mapsLink);
    if (!mounted) return;
    if (resolving) setState(() => _resolvingLink = false);
    if (location == null) {
      setState(() => _error = resolving ? s.mobileRequestsAddMapsLinkShort : s.mobileRequestsAddMapsLinkInvalid);
      return;
    }

    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await widget.service.create(
        phone: _phoneController.text.trim(),
        customerName: _nameController.text.trim(),
        serviceIds: _selectedServices.toList(),
        requestedTime: requestedTime,
        lat: location.lat,
        lng: location.lng,
        operatorId: _operatorId,
      );
      if (mounted) Navigator.of(context).pop(true);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e is Exception ? e.toString().replaceFirst('Exception: ', '') : s.mobileRequestsAddError;
        _submitting = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final locale = Localizations.localeOf(context).languageCode;

    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: DraggableScrollableSheet(
        initialChildSize: 0.9,
        maxChildSize: 0.95,
        minChildSize: 0.5,
        expand: false,
        builder: (context, scrollController) {
          return KbAnchor(
            id: 'mobile-requests.add_sheet',
            child: Container(
              decoration: const BoxDecoration(
                color: AppColors.surface1,
                borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
              ),
              child: ListView(
                controller: scrollController,
                padding:
                    const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.lg, AppSpacing.lg, AppSpacing.xl),
                children: [
                  Text(s.mobileRequestsAddTitle, style: AppTextStyles.headlineSmall),
                  const SizedBox(height: AppSpacing.lg),
                  AppTextField(
                    labelText: s.mobileRequestsAddPhoneLabel,
                    hintText: '05xxxxxxxx',
                    controller: _phoneController,
                    keyboardType: TextInputType.phone,
                    textDirection: TextDirection.ltr,
                    onChanged: (_) => setState(() {}),
                  ),
                  const SizedBox(height: AppSpacing.md),
                  AppTextField(
                    labelText: s.mobileRequestsAddNameLabel,
                    controller: _nameController,
                  ),
                  const SizedBox(height: AppSpacing.md),
                  Text(s.mobileRequestsAddServicesLabel, style: AppTextStyles.labelMedium),
                  const SizedBox(height: AppSpacing.sm),
                  if (widget.services.isEmpty)
                    Text(s.mobileRequestsAddServicesEmpty,
                        style: AppTextStyles.bodySmall.copyWith(color: AppColors.textMuted))
                  else
                    Wrap(
                      spacing: AppSpacing.sm,
                      runSpacing: AppSpacing.sm,
                      children: [
                        for (final entry in widget.services.entries)
                          _ServicePickChip(
                            label: entry.value,
                            selected: _selectedServices.contains(entry.key),
                            onTap: () => setState(() {
                              _selectedServices.contains(entry.key)
                                  ? _selectedServices.remove(entry.key)
                                  : _selectedServices.add(entry.key);
                            }),
                          ),
                      ],
                    ),
                  const SizedBox(height: AppSpacing.md),
                  Row(
                    children: [
                      Expanded(
                        child: _PickerField(
                          label: s.mobileRequestsAddDayLabel,
                          value: _day == null ? null : Formatters.formatDateShort(_day!, locale: locale),
                          icon: Icons.calendar_today_rounded,
                          onTap: () async {
                            final picked = await pickDaySheet(
                              context,
                              initial: _day,
                              firstDate: DateTime.now().subtract(const Duration(days: 1)),
                              lastDate: DateTime.now().add(const Duration(days: 90)),
                            );
                            if (picked != null) setState(() => _day = picked);
                          },
                        ),
                      ),
                      const SizedBox(width: AppSpacing.sm),
                      Expanded(
                        child: _PickerField(
                          label: s.mobileRequestsAddTimeLabel,
                          value: _time == null ? null : _formatTimeOfDay(_time!),
                          icon: Icons.schedule_rounded,
                          onTap: () async {
                            final picked = await pickTimeSheet(context, initial: _time);
                            if (picked != null) setState(() => _time = picked);
                          },
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.md),
                  AppTextField(
                    labelText: s.mobileRequestsAddMapsLinkLabel,
                    hintText: 'https://maps.google.com/...',
                    controller: _mapsController,
                    textDirection: TextDirection.ltr,
                    onChanged: (_) => setState(() {}),
                  ),
                  Padding(
                    padding: const EdgeInsets.only(top: 4, right: 4, left: 4),
                    child: Text(
                      _resolvingLink
                          ? s.mobileRequestsAddMapsLinkResolving
                          : s.mobileRequestsAddMapsLinkHint,
                      style: AppTextStyles.caption.copyWith(color: AppColors.textMuted),
                    ),
                  ),
                  if (widget.operators.isNotEmpty) ...[
                    const SizedBox(height: AppSpacing.md),
                    Text(s.mobileRequestsAddAssignLabel, style: AppTextStyles.labelMedium),
                    const SizedBox(height: AppSpacing.xs),
                    DropdownButtonHideUnderline(
                      child: DropdownButton<String>(
                        isExpanded: true,
                        value: _operatorId,
                        items: [
                          DropdownMenuItem(value: '', child: Text(s.mobileRequestsAssignUnassigned)),
                          for (final op in widget.operators)
                            DropdownMenuItem(value: op.id, child: Text(op.name)),
                        ],
                        onChanged: (v) => setState(() => _operatorId = v ?? ''),
                      ),
                    ),
                  ],
                  if (_error != null) ...[
                    const SizedBox(height: AppSpacing.md),
                    AppAlert(type: AlertType.error, message: _error!),
                  ],
                  const SizedBox(height: AppSpacing.lg),
                  PrimaryButton(
                    text: _submitting ? s.mobileRequestsAddSubmitting : s.mobileRequestsAddSubmit,
                    isLoading: _submitting || _resolvingLink,
                    isDisabled: !_canSubmit,
                    onPressed: _canSubmit ? _submit : null,
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}

class _ServicePickChip extends StatelessWidget {
  const _ServicePickChip({required this.label, required this.selected, required this.onTap});
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final accent = context.isDark ? AppDarkColors.accent : AppColors.accent;
    final colors = context.appColors;
    return Material(
      color: selected ? accent.withValues(alpha: 0.14) : colors.surfaceAlt,
      borderRadius: BorderRadius.circular(AppRadius.pill),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppRadius.pill),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(AppRadius.pill),
            border: Border.all(color: selected ? accent : Colors.transparent),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (selected) ...[
                Icon(Icons.check_rounded, size: 14, color: accent),
                const SizedBox(width: 4),
              ],
              Text(label,
                  style: AppTextStyles.labelMedium
                      .copyWith(color: selected ? accent : colors.textSecondary)),
            ],
          ),
        ),
      ),
    );
  }
}

class _PickerField extends StatelessWidget {
  const _PickerField({
    required this.label,
    required this.value,
    required this.icon,
    required this.onTap,
  });

  final String label;
  final String? value;
  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    return InkWell(
      onTap: onTap,
      borderRadius: AppRadius.standardRadius,
      child: Container(
        padding: const EdgeInsets.all(AppSpacing.md),
        decoration: BoxDecoration(
          color: colors.inputFill,
          borderRadius: AppRadius.standardRadius,
        ),
        child: Row(
          children: [
            Icon(icon, size: 18, color: colors.textSecondary),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: Text(
                value ?? label,
                style: AppTextStyles.bodyMedium.copyWith(
                  color: value != null ? colors.textPrimary : colors.textMuted,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
