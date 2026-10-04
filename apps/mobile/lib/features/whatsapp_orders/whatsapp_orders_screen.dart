import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show Clipboard, ClipboardData;
import 'package:provider/provider.dart';

import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/providers/branch_provider.dart';
import 'package:raje3_mobile/core/providers/nav_provider.dart';
import 'package:raje3_mobile/core/services/whatsapp_orders_service.dart';
import 'package:raje3_mobile/core/utils/formatters.dart';
import 'package:raje3_mobile/core/utils/snackbar_helper.dart';
import 'package:raje3_mobile/core/utils/url_helper.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/models/whatsapp_order_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/widgets/brand_loading_indicator.dart';
import 'package:raje3_mobile/widgets/capability_gate.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';

/// «طلبات التوصيل عبر الواتساب» — mobile mirror of
/// apps/console/src/screens/WhatsAppOrders.tsx, built on the SAME everyday shape every other
/// screen in this app already uses (the owner's own instruction, 2026-10-05: "الجوال يحتاج
/// تجربة معتادة وبسيطة جدا") — status TABS, not the console's Kanban columns (a Kanban board is
/// the kitchen-tablet shape, not the one-handed-phone shape; the online research behind this
/// pass found every mobile order app, Toast included, drops to a single scrolling list with
/// simple status tabs on a phone). Same filter/card/sheet skeleton as mobile_requests_screen.dart.
///
/// STANDALONE DELIVERY PRODUCT, never confused with «خدمات متنقلة» — same real state machine,
/// same real endpoints (services/operations/app/core/orders.py), gated on the SAME
/// `operations.record` capability recording a visit already uses (api/v1/whatsapp_orders.py's own
/// module docstring).
///
/// THE PAUSE SWITCH IS A PLAIN SWITCH TILE, NOT A BIG RED CIRCLE — the console's own big red
/// button fits a cashier staring at a monitor; a phone-sized screen reads a small switch with a
/// label just as clearly, and a switch is the one control every phone user already knows.
class WhatsAppOrdersScreen extends StatefulWidget {
  const WhatsAppOrdersScreen({super.key});

  @override
  State<WhatsAppOrdersScreen> createState() => _WhatsAppOrdersScreenState();
}

enum _Filter { all, incoming, confirmed, preparing, ready, delivery, closed }

// STUCK = sitting in the same working status too long with no progress — same 25-minute
// threshold WhatsAppOrders.tsx's own `STUCK_MINUTES` uses, so a phone and a console reader agree
// on what "overdue" means for the identical order.
const int _stuckMinutes = 25;

bool _isWorking(String status) =>
    status == 'confirmed' || status == 'preparing' || status == 'ready' || status == 'out_for_delivery';

bool _isStuck(WhatsAppOrder o, int nowSeconds) =>
    _isWorking(o.status) && nowSeconds - o.created > _stuckMinutes * 60;

class _WhatsAppOrdersScreenState extends State<WhatsAppOrdersScreen> {
  late final WhatsAppOrdersService _service;

  List<WhatsAppOrder>? _rows; // null while loading
  bool _loadFailed = false;
  _Filter _filter = _Filter.incoming;
  String? _busyId;
  int _now = DateTime.now().millisecondsSinceEpoch ~/ 1000;
  Timer? _clock;
  Timer? _poll;
  Set<String>? _seenIds; // null until the first successful load
  bool _paused = false;
  String _pauseReason = '';
  // STEP 9'S OWN ON/OFF SWITCH — defaults to shown (same "absent means on" the backend store
  // itself takes) until the real read lands.
  bool _shareEnabled = true;

  @override
  void initState() {
    super.initState();
    _service = WhatsAppOrdersService(apiClient: context.read<AuthProvider>().apiClient);
    _clock = Timer.periodic(const Duration(seconds: 30), (_) {
      if (mounted) setState(() => _now = DateTime.now().millisecondsSinceEpoch ~/ 1000);
    });
    _load();
    _loadPause();
    _loadShareToggle();
    // SAME 8s POLL THE CONSOLE'S OWN BOARD USES — this product has no websocket/live-push infra
    // yet, so a short poll is the honest "live" a phone screen can actually offer today.
    _poll = Timer.periodic(const Duration(seconds: 8), (_) => _load());
  }

  @override
  void dispose() {
    _clock?.cancel();
    _poll?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    final result = await _service.list();
    if (!mounted) return;
    if (result == null) {
      setState(() {
        if (_rows == null) _loadFailed = true;
      });
      return;
    }
    setState(() {
      _rows = result;
      _loadFailed = false;
      _seenIds = result.map((o) => o.id).toSet();
    });
  }

  String? get _branchId => context.read<BranchProvider>().selectedId;

  Future<void> _loadPause() async {
    final branchId = _branchId;
    if (branchId == null || branchId.isEmpty) return;
    final result = await _service.getPause(branchId);
    if (result != null && mounted) {
      setState(() {
        _paused = result.paused;
        _pauseReason = result.reason;
      });
    }
  }

  Future<void> _togglePause() async {
    final branchId = _branchId;
    if (branchId == null || branchId.isEmpty) return;
    final s = S.of(context)!;
    final next = !_paused;
    final result = await _service.setPause(branchId,
        paused: next, reason: next ? s.whatsappOrdersPauseDefaultReason : '');
    if (result != null && mounted) {
      setState(() {
        _paused = result.paused;
        _pauseReason = result.reason;
      });
    }
  }

  Future<void> _loadShareToggle() async {
    final enabled = await _service.getShareToggle();
    if (enabled != null && mounted) setState(() => _shareEnabled = enabled);
  }

  Future<void> _toggleShare() async {
    final next = !_shareEnabled;
    final result = await _service.setShareToggle(next);
    if (result != null && mounted) setState(() => _shareEnabled = result);
  }

  List<WhatsAppOrder> get _list => _rows ?? const [];

  int get _waitingCount =>
      _list.where((o) => o.status == 'received' || o.status == 'payment_mismatch').length;

  int get _stuckCount => _list.where((o) => _isStuck(o, _now)).length;

  int get _deliveredToday {
    final dayStart = DateTime(DateTime.now().year, DateTime.now().month, DateTime.now().day);
    final cutoff = dayStart.millisecondsSinceEpoch ~/ 1000;
    return _list.where((o) => o.status == 'delivered' && o.created >= cutoff).length;
  }

  List<WhatsAppOrder> get _filtered {
    var out = _list;
    switch (_filter) {
      case _Filter.incoming:
        out = out.where((o) => o.status == 'received' || o.status == 'payment_mismatch').toList();
      case _Filter.confirmed:
        out = out.where((o) => o.status == 'confirmed').toList();
      case _Filter.preparing:
        out = out.where((o) => o.status == 'preparing').toList();
      case _Filter.ready:
        out = out.where((o) => o.status == 'ready').toList();
      case _Filter.delivery:
        out = out.where((o) => o.status == 'out_for_delivery').toList();
      case _Filter.closed:
        out = out.where((o) => o.status == 'delivered' || o.status == 'cancelled').toList();
      case _Filter.all:
        break;
    }
    final sorted = [...out];
    if (_filter == _Filter.closed) {
      sorted.sort((a, b) => b.created.compareTo(a.created));
    } else {
      sorted.sort((a, b) => a.created.compareTo(b.created));
    }
    return sorted;
  }

  Future<void> _run(String orderId, Future<WhatsAppOrder?> Function() action) async {
    if (_busyId != null) return;
    setState(() => _busyId = orderId);
    final result = await action();
    if (!mounted) return;
    setState(() => _busyId = null);
    if (result != null) {
      _load();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(S.of(context)!.whatsappOrdersActionFailed)),
      );
    }
  }

  ({String label, Future<WhatsAppOrder?> Function() action})? _nextAction(S s, WhatsAppOrder o) {
    if (o.status == 'confirmed') {
      return (label: s.whatsappOrdersActionStartPreparing, action: () => _service.startPreparing(o.id));
    }
    if (o.status == 'preparing') {
      return (label: s.whatsappOrdersActionMarkReady, action: () => _service.markReady(o.id));
    }
    if (o.status == 'ready') {
      return (label: s.whatsappOrdersActionStartDelivery, action: () => _service.startDelivery(o.id));
    }
    if (o.status == 'out_for_delivery') {
      return (label: s.whatsappOrdersActionMarkDelivered, action: () => _service.markDelivered(o.id));
    }
    return null;
  }

  Future<void> _openDetails(WhatsAppOrder o) async {
    final updated = await showModalBottomSheet<WhatsAppOrder>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _OrderDetailsSheet(order: o, service: _service, shareEnabled: _shareEnabled),
    );
    if (updated != null) _load();
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final catalog = context.watch<NavProvider>().catalog;
    final canPause = catalog.hasAll(['whatsapp_order.pause_set']);
    final canToggleShare = catalog.hasAll(['whatsapp_order.share_toggle_set']);

    return KbAnchor(
      id: 'whatsapp-orders',
      child: Scaffold(
        backgroundColor: AppColors.surface0,
        appBar: AppBar(title: Text(s.whatsappOrdersTitle)),
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
                      Text(s.whatsappOrdersSubtitle,
                          style:
                              AppTextStyles.bodySmall.copyWith(color: AppColors.textSecondary)),
                      const SizedBox(height: AppSpacing.md),
                      if (canPause)
                        CapabilityGate(
                          requires: const ['whatsapp_order.pause_set'],
                          child: KbAnchor(
                            id: 'whatsapp-orders.pause_switch',
                            child: _PauseSwitchTile(
                              paused: _paused,
                              reason: _pauseReason,
                              onChanged: (_) => _togglePause(),
                            ),
                          ),
                        ),
                      if (canPause) const SizedBox(height: AppSpacing.md),
                      if (canToggleShare)
                        CapabilityGate(
                          requires: const ['whatsapp_order.share_toggle_set'],
                          child: KbAnchor(
                            id: 'whatsapp-orders.share_toggle_switch',
                            child: _ShareToggleTile(
                              enabled: _shareEnabled,
                              onChanged: (_) => _toggleShare(),
                            ),
                          ),
                        ),
                      if (canToggleShare) const SizedBox(height: AppSpacing.md),
                      Row(
                        children: [
                          Expanded(
                            child: KpiTile(
                              icon: Icons.mark_email_unread_outlined,
                              label: s.whatsappOrdersKpiWaiting,
                              value: Formatters.formatNumber(_waitingCount),
                              tone: KpiTone.info,
                            ),
                          ),
                          const SizedBox(width: AppSpacing.sm),
                          Expanded(
                            child: KpiTile(
                              icon: Icons.warning_amber_rounded,
                              label: s.whatsappOrdersKpiStuck,
                              value: Formatters.formatNumber(_stuckCount),
                              tone: _stuckCount > 0 ? KpiTone.warning : KpiTone.neutral,
                            ),
                          ),
                          const SizedBox(width: AppSpacing.sm),
                          Expanded(
                            child: KpiTile(
                              icon: Icons.check_circle_outline_rounded,
                              label: s.whatsappOrdersKpiDeliveredToday,
                              value: Formatters.formatNumber(_deliveredToday),
                              tone: KpiTone.success,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: AppSpacing.md),
                      SegmentedFilter<_Filter>(
                        value: _filter,
                        onChanged: (v) => setState(() => _filter = v),
                        options: [
                          SegmentedFilterOption(
                              value: _Filter.incoming,
                              label: s.whatsappOrdersFilterIncoming,
                              badge: _waitingCount),
                          SegmentedFilterOption(
                              value: _Filter.confirmed,
                              label: s.whatsappOrdersFilterConfirmed,
                              badge: _list.where((o) => o.status == 'confirmed').length),
                          SegmentedFilterOption(
                              value: _Filter.preparing,
                              label: s.whatsappOrdersFilterPreparing,
                              badge: _list.where((o) => o.status == 'preparing').length),
                          SegmentedFilterOption(
                              value: _Filter.ready,
                              label: s.whatsappOrdersFilterReady,
                              badge: _list.where((o) => o.status == 'ready').length),
                          SegmentedFilterOption(
                              value: _Filter.delivery,
                              label: s.whatsappOrdersFilterDelivery,
                              badge: _list.where((o) => o.status == 'out_for_delivery').length),
                          SegmentedFilterOption(
                              value: _Filter.closed,
                              label: s.whatsappOrdersFilterClosed,
                              badge: _list
                                  .where((o) => o.status == 'delivered' || o.status == 'cancelled')
                                  .length),
                          SegmentedFilterOption(
                              value: _Filter.all, label: s.whatsappOrdersFilterAll, badge: _list.length),
                        ],
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
                    title: s.whatsappOrdersLoadFailedTitle,
                    message: s.whatsappOrdersLoadFailedBody,
                    actionText: s.whatsappOrdersRetry,
                    onAction: _load,
                  ),
                )
              else if (_filtered.isEmpty)
                SliverFillRemaining(
                  hasScrollBody: false,
                  child: EmptyState(
                    icon: Icons.receipt_long_outlined,
                    title: s.whatsappOrdersEmptyTitle,
                    message: s.whatsappOrdersEmptyBody,
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
                      final o = _filtered[i];
                      final next = _nextAction(s, o);
                      return _OrderCard(
                        o: o,
                        now: _now,
                        isNew: _seenIds != null && !_seenIds!.contains(o.id),
                        busy: _busyId == o.id,
                        nextLabel: next?.label,
                        onTap: () => _openDetails(o),
                        onNext: next == null ? null : () => _run(o.id, next.action),
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

class _ShareToggleTile extends StatelessWidget {
  const _ShareToggleTile({required this.enabled, required this.onChanged});
  final bool enabled;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final colors = context.appColors;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.sm),
      decoration: BoxDecoration(
        color: colors.surface,
        border: Border.all(color: colors.borderSubtle),
        borderRadius: AppRadius.standardRadius,
      ),
      child: Row(
        children: [
          Icon(Icons.share_rounded, color: colors.textSecondary, size: 20),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Text(s.whatsappOrdersShareToggleLabel,
                style: AppTextStyles.labelMedium.copyWith(color: colors.textPrimary, fontWeight: FontWeight.w700)),
          ),
          Switch(value: enabled, onChanged: onChanged),
        ],
      ),
    );
  }
}

class _PauseSwitchTile extends StatelessWidget {
  const _PauseSwitchTile({required this.paused, required this.reason, required this.onChanged});
  final bool paused;
  final String reason;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final colors = context.appColors;
    final danger = context.isDark ? AppDarkColors.danger : AppColors.danger;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.sm),
      decoration: BoxDecoration(
        color: paused ? (context.isDark ? AppDarkColors.dangerSoft : AppColors.dangerSoft) : colors.surface,
        border: Border.all(color: paused ? danger.withValues(alpha: 0.35) : colors.borderSubtle),
        borderRadius: AppRadius.standardRadius,
      ),
      child: Row(
        children: [
          Icon(paused ? Icons.pause_circle_rounded : Icons.play_circle_outline_rounded,
              color: paused ? danger : colors.textSecondary, size: 22),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(s.whatsappOrdersPauseLabel,
                    style: AppTextStyles.labelMedium.copyWith(
                        color: paused ? danger : colors.textPrimary, fontWeight: FontWeight.w700)),
                if (paused && reason.isNotEmpty)
                  Text(reason, style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
              ],
            ),
          ),
          Switch(value: paused, onChanged: onChanged, activeThumbColor: danger),
        ],
      ),
    );
  }
}

String _statusLabel(S s, String status) {
  switch (status) {
    case 'received':
      return s.whatsappOrdersStatusReceived;
    case 'payment_mismatch':
      return s.whatsappOrdersStatusPaymentMismatch;
    case 'confirmed':
      return s.whatsappOrdersStatusConfirmed;
    case 'preparing':
      return s.whatsappOrdersStatusPreparing;
    case 'ready':
      return s.whatsappOrdersStatusReady;
    case 'out_for_delivery':
      return s.whatsappOrdersStatusOutForDelivery;
    case 'delivered':
      return s.whatsappOrdersStatusDelivered;
    default:
      return s.whatsappOrdersStatusCancelled;
  }
}

(Color, Color) _statusColors(BuildContext context, String status) {
  final isDark = context.isDark;
  switch (status) {
    case 'received':
      return (isDark ? AppDarkColors.infoSoft : AppColors.infoSoft,
          isDark ? AppDarkColors.infoOnSoft : AppColors.infoOnSoft);
    case 'payment_mismatch':
      return (isDark ? AppDarkColors.dangerSoft : AppColors.dangerSoft,
          isDark ? AppDarkColors.dangerOnSoft : AppColors.dangerOnSoft);
    case 'confirmed':
    case 'ready':
      return (isDark ? AppDarkColors.accentSoft : AppColors.accentSoft,
          isDark ? AppDarkColors.accentOnSoft : AppColors.accentOnSoft);
    case 'preparing':
      return (isDark ? AppDarkColors.warningSoft : AppColors.warningSoft,
          isDark ? AppDarkColors.warningOnSoft : AppColors.warningOnSoft);
    case 'out_for_delivery':
      return (isDark ? AppDarkColors.infoSoft : AppColors.infoSoft,
          isDark ? AppDarkColors.infoOnSoft : AppColors.infoOnSoft);
    case 'delivered':
      return (isDark ? AppDarkColors.successSoft : AppColors.successSoft,
          isDark ? AppDarkColors.successOnSoft : AppColors.successOnSoft);
    default:
      final colors = context.appColors;
      return (colors.surfaceAlt, colors.textSecondary);
  }
}

class _OrderCard extends StatelessWidget {
  const _OrderCard({
    required this.o,
    required this.now,
    required this.isNew,
    required this.busy,
    required this.nextLabel,
    required this.onTap,
    required this.onNext,
  });

  final WhatsAppOrder o;
  final int now;
  final bool isNew;
  final bool busy;
  final String? nextLabel;
  final VoidCallback onTap;
  final VoidCallback? onNext;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final locale = Localizations.localeOf(context).languageCode;
    final colors = context.appColors;
    final stuck = _isStuck(o, now);
    final (statusBg, statusFg) = _statusColors(context, o.status);

    return KbAnchor(
      id: 'whatsapp-orders.order_card',
      child: Material(
        color: Colors.transparent,
        borderRadius: AppRadius.cardRadius,
        child: InkWell(
          onTap: onTap,
          borderRadius: AppRadius.cardRadius,
          child: Container(
            decoration: BoxDecoration(
              color: colors.surface,
              borderRadius: AppRadius.cardRadius,
              border: Border.all(
                color: stuck
                    ? (context.isDark ? AppDarkColors.danger : AppColors.danger).withValues(alpha: 0.4)
                    : isNew
                        ? (context.isDark ? AppDarkColors.accent : AppColors.accent).withValues(alpha: 0.45)
                        : colors.borderSubtle,
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
                      child: Text(
                        o.customerName.isNotEmpty ? o.customerName : s.whatsappOrdersUnnamed,
                        style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w700),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                      decoration: BoxDecoration(
                          color: statusBg, borderRadius: BorderRadius.circular(AppRadius.pill)),
                      child: Text(_statusLabel(s, o.status),
                          style: AppTextStyles.caption
                              .copyWith(color: statusFg, fontWeight: FontWeight.w700)),
                    ),
                  ],
                ),
                if (stuck) ...[
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      Icon(Icons.warning_amber_rounded,
                          size: 13, color: context.isDark ? AppDarkColors.danger : AppColors.danger),
                      const SizedBox(width: 4),
                      Text(s.whatsappOrdersStuckBadge,
                          style: AppTextStyles.caption.copyWith(
                              color: context.isDark ? AppDarkColors.danger : AppColors.danger,
                              fontWeight: FontWeight.w700)),
                    ],
                  ),
                ],
                if (o.lines.isNotEmpty) ...[
                  const SizedBox(height: AppSpacing.sm),
                  Text(
                    o.lines.map((l) => '${l.quantity}× ${l.name}').join('، '),
                    style: AppTextStyles.caption.copyWith(color: colors.textSecondary),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
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
                            DateTime.fromMillisecondsSinceEpoch(o.created * 1000), locale: locale),
                        style: AppTextStyles.caption.copyWith(color: colors.textSecondary),
                      ),
                    ),
                    Text(
                      Formatters.formatCurrency(o.amountDueMinor / 100),
                      style: AppTextStyles.bodySmall.copyWith(fontWeight: FontWeight.w800),
                    ),
                  ],
                ),
                if (onNext != null) ...[
                  const SizedBox(height: AppSpacing.sm),
                  SizedBox(
                    height: 40,
                    width: double.infinity,
                    child: PrimaryButton(
                      text: nextLabel ?? '',
                      isLoading: busy,
                      onPressed: busy ? null : onNext,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _OrderDetailsSheet extends StatefulWidget {
  const _OrderDetailsSheet({required this.order, required this.service, required this.shareEnabled});
  final WhatsAppOrder order;
  final WhatsAppOrdersService service;
  final bool shareEnabled;

  @override
  State<_OrderDetailsSheet> createState() => _OrderDetailsSheetState();
}

class _OrderDetailsSheetState extends State<_OrderDetailsSheet> {
  bool _busy = false;

  Future<void> _act(Future<WhatsAppOrder?> Function() fn) async {
    setState(() => _busy = true);
    final updated = await fn();
    if (!mounted) return;
    setState(() => _busy = false);
    if (updated != null) Navigator.of(context).pop(updated);
  }

  Future<void> _askCancel() async {
    final s = S.of(context)!;
    final controller = TextEditingController();
    final reason = await showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(s.whatsappOrdersActionCancel),
        content: TextField(
          controller: controller,
          decoration: InputDecoration(hintText: s.whatsappOrdersCancelReasonPrompt),
          autofocus: true,
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(),
              child: Text(s.whatsappOrdersCancelReasonCancel)),
          TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(controller.text.trim()),
              child: Text(s.whatsappOrdersCancelReasonConfirm)),
        ],
      ),
    );
    if (reason == null) return;
    _act(() => widget.service.cancel(widget.order.id, reason));
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final o = widget.order;
    final colors = context.appColors;
    final (statusBg, statusFg) = _statusColors(context, o.status);

    final actionRows = <Widget>[];
    final next = _nextActionFor(s, o, widget.service);
    if (next != null) {
      actionRows.add(SizedBox(
        width: double.infinity,
        height: 44,
        child: PrimaryButton(text: next.label, isLoading: _busy, onPressed: _busy ? null : () => _act(next.action)),
      ));
    }
    if (o.status == 'payment_mismatch') {
      actionRows.add(const SizedBox(height: AppSpacing.sm));
      actionRows.add(SizedBox(
        width: double.infinity,
        height: 44,
        child: SecondaryButton(
          text: s.whatsappOrdersActionResolveMismatch,
          onPressed: _busy ? null : () => _act(() => widget.service.resolveMismatch(o.id)),
        ),
      ));
    }
    if (o.status == 'received' || o.status == 'payment_mismatch' || o.status == 'confirmed') {
      actionRows.add(const SizedBox(height: AppSpacing.sm));
      actionRows.add(SizedBox(
        width: double.infinity,
        height: 44,
        child: SecondaryButton(
          text: s.whatsappOrdersActionCancel,
          onPressed: _busy ? null : _askCancel,
        ),
      ));
    }
    if (widget.shareEnabled && _isWorking(o.status)) {
      actionRows.add(const SizedBox(height: AppSpacing.sm));
      actionRows.add(SizedBox(
        width: double.infinity,
        height: 44,
        child: SecondaryButton(
          text: s.whatsappOrdersActionShareWithRep,
          onPressed: () => openWhatsAppCompose(_buildShareText(s, o)),
        ),
      ));
    }

    return Container(
      constraints: BoxConstraints(maxHeight: appSheetMaxHeight(context)),
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        color: colors.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
      ),
      child: SafeArea(
        top: false,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                    width: 40,
                    height: 4,
                    decoration: BoxDecoration(
                        color: colors.borderSubtle, borderRadius: BorderRadius.circular(4))),
              ),
              const SizedBox(height: AppSpacing.md),
              Row(
                children: [
                  Expanded(
                    child: Text(o.customerName.isNotEmpty ? o.customerName : s.whatsappOrdersUnnamed,
                        style: AppTextStyles.headlineSmall),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                    decoration:
                        BoxDecoration(color: statusBg, borderRadius: BorderRadius.circular(AppRadius.pill)),
                    child: Text(_statusLabel(s, o.status),
                        style:
                            AppTextStyles.caption.copyWith(color: statusFg, fontWeight: FontWeight.w700)),
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.sm),
              Row(
                children: [
                  InkWell(
                    onTap: () => openWhatsApp(o.phone),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.chat_bubble_rounded, size: 14, color: Color(0xFF25D366)),
                        const SizedBox(width: 4),
                        Text(o.phone,
                            style: AppTextStyles.bodySmall.copyWith(
                                color: colors.textSecondary, fontFamily: AppTextStyles.englishFont)),
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),
                  InkWell(
                    onTap: () async {
                      await Clipboard.setData(ClipboardData(text: o.phone));
                      if (context.mounted) {
                        SnackbarHelper.showSuccess(context, s.whatsappOrdersPhoneCopied);
                      }
                    },
                    child: Icon(Icons.copy_rounded, size: 14, color: colors.textMuted),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              InkWell(
                onTap: () => openUrl(o.mapsUrl, context),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.location_on_rounded,
                        size: 14, color: context.isDark ? AppDarkColors.accent : AppColors.accent),
                    const SizedBox(width: 4),
                    Text(s.whatsappOrdersOpenMap,
                        style: AppTextStyles.caption.copyWith(
                            color: context.isDark ? AppDarkColors.accent : AppColors.accent,
                            fontWeight: FontWeight.w700)),
                  ],
                ),
              ),
              const SizedBox(height: AppSpacing.md),
              Container(
                padding: const EdgeInsets.all(AppSpacing.md),
                decoration: BoxDecoration(
                  color: colors.surfaceAlt,
                  borderRadius: AppRadius.standardRadius,
                ),
                child: Column(
                  children: [
                    for (final line in o.lines)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 6),
                        child: Row(
                          children: [
                            Expanded(child: Text('${line.quantity}× ${line.name}', style: AppTextStyles.bodySmall)),
                            Text(Formatters.formatCurrency(line.lineTotalMinor / 100),
                                style: AppTextStyles.bodySmall.copyWith(color: colors.textSecondary)),
                          ],
                        ),
                      ),
                    const Divider(height: 16),
                    Row(
                      children: [
                        Expanded(child: Text(s.whatsappOrdersDrawerSubtotal, style: AppTextStyles.bodySmall.copyWith(color: colors.textSecondary))),
                        Text(Formatters.formatCurrency(o.totalMinor / 100), style: AppTextStyles.bodySmall),
                      ],
                    ),
                    if (o.discountMinor > 0) ...[
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          Expanded(
                              child: Text(s.whatsappOrdersDrawerDiscount,
                                  style: AppTextStyles.bodySmall.copyWith(
                                      color: context.isDark ? AppDarkColors.success : AppColors.success))),
                          Text('-${Formatters.formatCurrency(o.discountMinor / 100)}',
                              style: AppTextStyles.bodySmall.copyWith(
                                  color: context.isDark ? AppDarkColors.success : AppColors.success)),
                        ],
                      ),
                    ],
                    if (o.pointsRewardMinor > 0) ...[
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          Expanded(
                              child: Text(
                                  o.pointsRewardName.isNotEmpty
                                      ? o.pointsRewardName
                                      : s.whatsappOrdersDrawerPointsReward,
                                  style: AppTextStyles.bodySmall.copyWith(
                                      color: context.isDark ? AppDarkColors.success : AppColors.success))),
                          Text('-${Formatters.formatCurrency(o.pointsRewardMinor / 100)}',
                              style: AppTextStyles.bodySmall.copyWith(
                                  color: context.isDark ? AppDarkColors.success : AppColors.success)),
                        ],
                      ),
                    ],
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Expanded(
                            child: Text(s.whatsappOrdersDrawerTotal,
                                style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w800))),
                        Text(Formatters.formatCurrency(o.amountDueMinor / 100),
                            style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w800)),
                      ],
                    ),
                  ],
                ),
              ),
              if (o.status == 'payment_mismatch') ...[
                const SizedBox(height: AppSpacing.md),
                AppAlert(
                  type: AlertType.error,
                  message: s.whatsappOrdersDrawerMismatchHint(Formatters.formatCurrency(o.paidAmountMinor / 100)),
                ),
              ],
              if (o.cancelReason.isNotEmpty) ...[
                const SizedBox(height: AppSpacing.sm),
                Text(s.whatsappOrdersDrawerCancelReason(o.cancelReason),
                    style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
              ],
              if (o.note.isNotEmpty) ...[
                const SizedBox(height: AppSpacing.sm),
                Text(s.whatsappOrdersDrawerNote(o.note),
                    style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
              ],
              if (actionRows.isNotEmpty) ...[
                const SizedBox(height: AppSpacing.lg),
                ...actionRows,
              ],
            ],
          ),
        ),
      ),
    );
  }
}

({String label, Future<WhatsAppOrder?> Function() action})? _nextActionFor(
    S s, WhatsAppOrder o, WhatsAppOrdersService service) {
  if (o.status == 'confirmed') {
    return (label: s.whatsappOrdersActionStartPreparing, action: () => service.startPreparing(o.id));
  }
  if (o.status == 'preparing') {
    return (label: s.whatsappOrdersActionMarkReady, action: () => service.markReady(o.id));
  }
  if (o.status == 'ready') {
    return (label: s.whatsappOrdersActionStartDelivery, action: () => service.startDelivery(o.id));
  }
  if (o.status == 'out_for_delivery') {
    return (label: s.whatsappOrdersActionMarkDelivered, action: () => service.markDelivered(o.id));
  }
  return null;
}

/// Step 9 — «مشاركة الطلب مع المندوب». Same "no stored rep number anywhere in this product"
/// reasoning the console's own `shareWithRepLink` carries: `openWhatsAppCompose` opens WhatsApp's
/// own contact picker with this text already filled in, so the merchant picks whichever rep he is
/// using for this delivery, never a fixed number this product has no data to back.
String _buildShareText(S s, WhatsAppOrder o) {
  final lines = o.lines.map((l) => '${l.quantity}× ${l.name}').join('\n');
  return [
    s.whatsappOrdersShareHeading,
    s.whatsappOrdersShareCustomer(o.customerName.isNotEmpty ? o.customerName : s.whatsappOrdersUnnamed),
    s.whatsappOrdersSharePhone(o.phone),
    s.whatsappOrdersShareAddress(o.mapsUrl),
    '',
    lines,
    '',
    s.whatsappOrdersShareTotal(Formatters.formatCurrency(o.amountDueMinor / 100)),
  ].join('\n');
}
