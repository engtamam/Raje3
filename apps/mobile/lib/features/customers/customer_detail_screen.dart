import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/providers/nav_provider.dart';
import 'package:raje3_mobile/core/services/customers_service.dart';
import 'package:raje3_mobile/core/utils/formatters.dart';
import 'package:raje3_mobile/core/utils/url_helper.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/models/customer_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/widgets/brand_loading_indicator.dart';
import 'package:raje3_mobile/widgets/capability_gate.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';

/// This customer's own rhythm, computed client-side from his real visits — the exact formula
/// Customer.tsx's own `everyDays`/`sinceDays`/`overdue` uses, never a second server read. Late
/// only against his OWN rhythm, never a number we chose: a customer who comes twice a year is not
/// overdue in month three.
({int everyDays, int sinceDays, bool overdue}) _visitRhythm(List<CustomerVisit> visits) {
  final times = visits.map((v) => v.occurredAt).where((t) => t > 0).toList()
    ..sort((a, b) => b.compareTo(a));
  if (times.isEmpty) return (everyDays: 0, sinceDays: 0, overdue: false);
  final gaps = <int>[];
  for (var i = 0; i < times.length - 1; i++) {
    final gap = times[i] - times[i + 1];
    if (gap > 0) gaps.add(gap);
  }
  final everyDays =
      gaps.isEmpty ? 0 : (gaps.reduce((a, b) => a + b) / gaps.length / 86400).round();
  final sinceDays = (DateTime.now().millisecondsSinceEpoch ~/ 1000 - times.first) ~/ 86400;
  final overdue = everyDays > 0 && sinceDays > everyDays * 1.5;
  return (everyDays: everyDays, sinceDays: sinceDays, overdue: overdue);
}

/// «عملائي» — customer detail, mobile mirror of apps/console/src/screens/Customer.tsx: profile,
/// vehicles, visit history, loyalty, offers, adaptive reminder cycles, the reminder send log,
/// booking history, and rename/erase.
class CustomerDetailScreen extends StatefulWidget {
  const CustomerDetailScreen({super.key, required this.customerId});
  final String customerId;

  @override
  State<CustomerDetailScreen> createState() => _CustomerDetailScreenState();
}

class _CustomerDetailScreenState extends State<CustomerDetailScreen> {
  late final CustomersService _service;

  CustomerRecord? _record;
  bool _loadFailed = false;
  List<CustomerOffer>? _offers;
  LoyaltyBalance? _balance;
  List<LoyaltyMove>? _loyaltyHistory;
  List<ReminderRule>? _rules;
  List<ReminderLogEntry>? _log;
  String? _logUnavailable;
  List<CustomerBooking>? _bookings;
  Map<String, String> _serviceNames = {};

  @override
  void initState() {
    super.initState();
    _service = CustomersService(apiClient: context.read<AuthProvider>().apiClient);
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _record = null;
      _loadFailed = false;
    });
    final record = await _service.record(widget.customerId);
    if (!mounted) return;
    if (record == null) {
      setState(() => _loadFailed = true);
      return;
    }
    setState(() => _record = record);

    final catalog = context.read<NavProvider>().catalog;
    final ref = record.customer.subjectRef;
    if (ref.isNotEmpty && catalog.hasAll(['reminders.customer_offers'])) {
      _service.offers(ref).then((v) {
        if (mounted) setState(() => _offers = v);
      });
    }
    if (ref.isNotEmpty && catalog.hasAll(['loyalty.balance'])) {
      _service.loyaltyBalance(ref).then((v) {
        if (mounted) setState(() => _balance = v);
      });
    }
    if (ref.isNotEmpty && catalog.hasAll(['loyalty.history'])) {
      _service.loyaltyHistory(ref).then((v) {
        if (mounted) setState(() => _loyaltyHistory = v);
      });
    }
    if (ref.isNotEmpty && catalog.hasAll(['reminders.list_rules'])) {
      _service.reminderRules(ref).then((v) {
        if (mounted) setState(() => _rules = v);
      });
      if (catalog.hasAll(['operations.list_services']) ||
          catalog.hasAll(['operations.manage_services'])) {
        _service.serviceNames().then((v) {
          if (mounted) setState(() => _serviceNames = v);
        });
      }
    }
    if (ref.isNotEmpty && catalog.hasAll(['reminders.log'])) {
      _service.reminderLog(ref).then((v) {
        if (mounted) {
          setState(() {
            _log = v.entries;
            _logUnavailable = v.unavailable;
          });
        }
      });
    }
    _service.bookingsForCustomer(widget.customerId).then((v) {
      if (mounted) setState(() => _bookings = v);
    });
  }

  Future<void> _openEditRule(ReminderRule rule, String label) async {
    final s = S.of(context)!;
    final saved = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _EditRuleSheet(service: _service, rule: rule, label: label),
    );
    if (saved != true || !mounted) return;
    final ref = _record!.customer.subjectRef;
    final rules = await _service.reminderRules(ref);
    if (mounted && rules != null) {
      setState(() => _rules = rules);
    } else if (mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(s.customersActionFailed)));
    }
  }

  Future<void> _openRename() async {
    final s = S.of(context)!;
    final catalog = context.read<NavProvider>().catalog;
    if (!catalog.hasAll(['operations.rename_customer'])) return;
    final controller = TextEditingController(text: _record!.customer.name);
    final newName = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _RenameSheet(controller: controller),
    );
    if (newName == null || !mounted) return;
    final ok = await _service.rename(widget.customerId, newName);
    if (!mounted) return;
    if (ok) {
      _load();
    } else {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(s.customersActionFailed)));
    }
  }

  Future<void> _openAdjustLoyalty() async {
    final catalog = context.read<NavProvider>().catalog;
    if (!catalog.hasAll(['loyalty.adjust'])) return;
    final result = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) =>
          _AdjustLoyaltySheet(service: _service, subjectRef: _record!.customer.subjectRef),
    );
    if (result == true && mounted) {
      final ref = _record!.customer.subjectRef;
      final b = await _service.loyaltyBalance(ref);
      final h = await _service.loyaltyHistory(ref);
      if (mounted) {
        setState(() {
          _balance = b;
          _loyaltyHistory = h;
        });
      }
    }
  }

  Future<void> _openErase() async {
    final s = S.of(context)!;
    final catalog = context.read<NavProvider>().catalog;
    if (!catalog.hasAll(['operations.erase_customer'])) return;
    final confirmed = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _EraseConfirmSheet(customerName: _record!.customer.name),
    );
    if (confirmed != true || !mounted) return;
    final reason = await _service.erase(widget.customerId);
    if (!mounted) return;
    if (reason == null) {
      Navigator.of(context).pop();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(reason.isNotEmpty ? reason : s.customersActionFailed)),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final catalog = context.watch<NavProvider>().catalog;
    // A SPREAD, NOT A SINGLE WIDGET — gates two list items (a spacer + the button) inside a
    // `...[...]` section below, which `CapabilityGate` (one widget in, one widget out) cannot
    // stand in for without leaving a stray gap when hidden. Stays a plain `hasAll` check.
    final canErase = catalog.hasAll(['operations.manage']) &&
        catalog.hasAll(['operations.erase_customer']);

    return KbAnchor(
      id: 'customer_detail',
      child: Scaffold(
        backgroundColor: AppColors.surface0,
        body: Column(
          children: [
            _DetailHero(
              record: _record,
              onBack: () => Navigator.of(context).pop(),
              onRename: _openRename,
            ),
            Expanded(
              child: Transform.translate(
                offset: Offset(0, _record != null ? -18 : 0),
                child: _record == null
                    ? (_loadFailed
                        ? EmptyState(
                            icon: Icons.cloud_off_rounded,
                            title: s.customersLoadFailedTitle,
                            actionText: s.mobileRequestsRetry,
                            onAction: _load,
                          )
                        : const BrandLoadingIndicator())
                    : RefreshIndicator(
                        onRefresh: _load,
                        child: ListView(
                          padding: const EdgeInsets.fromLTRB(
                              AppSpacing.md, AppSpacing.sm, AppSpacing.md, AppSpacing.xxl),
                          children: [
                    if (_visitRhythm(_record!.visits).overdue) ...[
                      const SizedBox(height: AppSpacing.sm),
                      _OverdueBanner(rhythm: _visitRhythm(_record!.visits)),
                    ],
                    if (_record!.repeatedIssues.isNotEmpty) ...[
                      const SizedBox(height: AppSpacing.sm),
                      _RepeatedIssuesBanner(issues: _record!.repeatedIssues),
                    ],
                    if (_record!.assets.isNotEmpty) ...[
                      const SizedBox(height: AppSpacing.sm),
                      _AssetsCard(assets: _record!.assets),
                    ],
                    if (catalog.hasAll(['loyalty.balance'])) ...[
                      const SizedBox(height: AppSpacing.sm),
                      _LoyaltyCard(
                        balance: _balance,
                        onAdjust: _openAdjustLoyalty,
                      ),
                    ],
                    if (_loyaltyHistory != null && _loyaltyHistory!.isNotEmpty) ...[
                      const SizedBox(height: AppSpacing.sm),
                      _LoyaltyHistoryCard(moves: _loyaltyHistory!),
                    ],
                    if (_offers != null && _offers!.isNotEmpty) ...[
                      const SizedBox(height: AppSpacing.sm),
                      _OffersCard(offers: _offers!),
                    ],
                    if (_bookings != null && _bookings!.isNotEmpty) ...[
                      const SizedBox(height: AppSpacing.sm),
                      _BookingsCard(bookings: _bookings!),
                    ],
                    if (_rules != null && _rules!.isNotEmpty) ...[
                      const SizedBox(height: AppSpacing.sm),
                      _RulesCard(rules: _rules!, serviceNames: _serviceNames, onEdit: _openEditRule),
                    ],
                    const SizedBox(height: AppSpacing.sm),
                    _VisitsCard(visits: _record!.visits),
                    if (_log != null && _log!.isNotEmpty || _logUnavailable != null) ...[
                      const SizedBox(height: AppSpacing.sm),
                      _LogCard(entries: _log ?? const [], unavailable: _logUnavailable),
                    ],
                            if (canErase) ...[
                              const SizedBox(height: AppSpacing.lg),
                              KbAnchor(
                                id: 'customer_detail.erase_button',
                                child: SizedBox(
                                  width: double.infinity,
                                  child: TextButton.icon(
                                    onPressed: _openErase,
                                    icon: const Icon(Icons.delete_outline_rounded,
                                        color: AppColors.danger),
                                    label: Text(s.customersEraseButton,
                                        style: const TextStyle(color: AppColors.danger)),
                                  ),
                                ),
                              ),
                            ],
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

/// The gradient identity hero — same brand-gradient language [HomeScreen]'s own header and
/// [CustomersScreen]'s own hero wear, brought to a detail screen: avatar, name, phone, and quick
/// stat chips glass-styled over the gradient rather than a bare `AppBar` title.
class _DetailHero extends StatelessWidget {
  const _DetailHero({
    required this.record,
    required this.onBack,
    required this.onRename,
  });

  final CustomerRecord? record;
  final VoidCallback onBack;
  final VoidCallback onRename;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final dark = context.isDark;
    final c = record?.customer;
    final name = c != null && c.name.isNotEmpty ? c.name : s.customersUnnamed;
    final label = (c != null && c.name.isNotEmpty ? c.name : (c?.phone ?? '')).trim();
    final initial = label.isEmpty ? '?' : label.substring(0, 1).toUpperCase();
    final rhythm = record != null ? _visitRhythm(record!.visits) : null;

    return Container(
      decoration: BoxDecoration(
        gradient: primaryGradient(dark: dark),
        borderRadius: const BorderRadius.vertical(bottom: Radius.circular(AppRadius.card)),
        boxShadow: dark ? AppShadows.darkButton : AppShadows.button,
      ),
      child: ClipRRect(
        borderRadius: const BorderRadius.vertical(bottom: Radius.circular(AppRadius.card)),
        child: Stack(
          children: [
            Positioned.directional(
              textDirection: Directionality.of(context),
              top: -30,
              end: -24,
              child: Container(
                width: 120,
                height: 120,
                decoration:
                    BoxDecoration(shape: BoxShape.circle, color: Colors.white.withValues(alpha: 0.08)),
              ),
            ),
            SafeArea(
              bottom: false,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(
                    AppSpacing.sm, AppSpacing.xs, AppSpacing.sm, AppSpacing.xl),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        _GlassIconButton(
                          // Same body-level mapping AppBackButton itself verified live and
                          // documents as correct (never the AppBar-leading-slot swap, which
                          // reads backwards in this build).
                          icon: Directionality.of(context) == TextDirection.rtl
                              ? Icons.chevron_left_rounded
                              : Icons.chevron_right_rounded,
                          onTap: onBack,
                        ),
                        const Spacer(),
                        if (record != null)
                          CapabilityGate(
                            requires: const ['operations.rename_customer'],
                            child: KbAnchor(
                              id: 'customer_detail.rename_button',
                              child: _GlassIconButton(icon: Icons.edit_outlined, onTap: onRename),
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.center,
                        children: [
                          Container(
                            width: 52,
                            height: 52,
                            decoration: BoxDecoration(
                              color: Colors.white.withValues(alpha: 0.2),
                              shape: BoxShape.circle,
                              border: Border.all(color: Colors.white.withValues(alpha: 0.35)),
                            ),
                            child: Center(
                              child: Text(initial,
                                  style: AppTextStyles.headlineMedium.copyWith(color: Colors.white)),
                            ),
                          ),
                          const SizedBox(width: AppSpacing.sm),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(name,
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: AppTextStyles.headlineSmall
                                        .copyWith(color: AppColors.accentContrast)),
                                if (c != null) ...[
                                  const SizedBox(height: 2),
                                  InkWell(
                                    onTap: () => openWhatsApp(c.phone),
                                    child: Row(
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        const Icon(Icons.chat_bubble_rounded,
                                            size: 12, color: Colors.white70),
                                        const SizedBox(width: 4),
                                        Text(c.phone,
                                            style: AppTextStyles.bodySmall.copyWith(
                                              color: Colors.white.withValues(alpha: 0.9),
                                              fontFamily: AppTextStyles.englishFont,
                                            )),
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
                    if (c != null) ...[
                      const SizedBox(height: AppSpacing.md),
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm),
                        child: Row(
                          children: [
                            _GlassStat(
                              icon: Icons.event_repeat_rounded,
                              label: s.customersVisitCount(c.visitCount),
                            ),
                            if (c.lastVisit > 0) ...[
                              const SizedBox(width: AppSpacing.sm),
                              _GlassStat(
                                icon: Icons.schedule_rounded,
                                label: Formatters.formatTimeAgo(
                                    DateTime.fromMillisecondsSinceEpoch(c.lastVisit * 1000),
                                    locale: Localizations.localeOf(context).languageCode),
                              ),
                            ],
                            if (rhythm != null && rhythm.everyDays > 0) ...[
                              const SizedBox(width: AppSpacing.sm),
                              _GlassStat(
                                icon: Icons.repeat_rounded,
                                label: s.customersStatEveryDays(rhythm.everyDays),
                              ),
                            ],
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

class _GlassIconButton extends StatelessWidget {
  const _GlassIconButton({required this.icon, required this.onTap});
  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white.withValues(alpha: 0.16),
      shape: const CircleBorder(),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: SizedBox(width: 38, height: 38, child: Icon(icon, size: 20, color: Colors.white)),
      ),
    );
  }
}

class _GlassStat extends StatelessWidget {
  const _GlassStat({required this.icon, required this.label});
  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.16),
        borderRadius: BorderRadius.circular(AppRadius.pill),
      ),
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

class _OverdueBanner extends StatelessWidget {
  const _OverdueBanner({required this.rhythm});
  final ({int everyDays, int sinceDays, bool overdue}) rhythm;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final dark = context.isDark;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.sm),
      decoration: BoxDecoration(
        color: dark ? AppDarkColors.warningSoft : AppColors.warningSoft,
        borderRadius: AppRadius.standardRadius,
      ),
      child: Row(
        children: [
          Icon(Icons.schedule_rounded,
              size: 15, color: dark ? AppDarkColors.warningOnSoft : AppColors.warningOnSoft),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              s.customersOverdueBanner(rhythm.everyDays, rhythm.sinceDays),
              style: AppTextStyles.bodySmall
                  .copyWith(color: dark ? AppDarkColors.warningOnSoft : AppColors.warningOnSoft),
            ),
          ),
        ],
      ),
    );
  }
}

class _RepeatedIssuesBanner extends StatelessWidget {
  const _RepeatedIssuesBanner({required this.issues});
  final List<RepeatedIssue> issues;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: AppColors.dangerSoft,
        border: Border.all(color: AppColors.danger.withValues(alpha: 0.3)),
        borderRadius: AppRadius.standardRadius,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.report_problem_rounded, size: 16, color: AppColors.dangerOnSoft),
              const SizedBox(width: 6),
              Text(s.customersRepeatedIssuesTitle,
                  style: AppTextStyles.labelMedium.copyWith(color: AppColors.dangerOnSoft)),
            ],
          ),
          const SizedBox(height: 6),
          for (final issue in issues)
            Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Text('• ${issue.text} (${issue.count})',
                  style: AppTextStyles.bodySmall.copyWith(color: AppColors.dangerOnSoft)),
            ),
        ],
      ),
    );
  }
}

class _AssetsCard extends StatelessWidget {
  const _AssetsCard({required this.assets});
  final List<CustomerAsset> assets;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(s.customersVehiclesTitle, style: AppTextStyles.labelMedium),
          const SizedBox(height: AppSpacing.sm),
          Wrap(
            spacing: AppSpacing.sm,
            runSpacing: AppSpacing.sm,
            children: [
              for (final a in assets)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: context.appColors.surfaceAlt,
                    borderRadius: BorderRadius.circular(AppRadius.sm),
                  ),
                  child: Text(
                    [a.plate, if (a.make.isNotEmpty) a.make, if (a.model.isNotEmpty) a.model]
                        .where((p) => p.isNotEmpty)
                        .join(' — '),
                    style: AppTextStyles.bodySmall,
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _LoyaltyCard extends StatelessWidget {
  const _LoyaltyCard({required this.balance, required this.onAdjust});
  final LoyaltyBalance? balance;
  final VoidCallback onAdjust;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    return AppCard(
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: context.isDark ? AppDarkColors.warningSoft : AppColors.warningSoft,
              borderRadius: BorderRadius.circular(AppRadius.sm),
            ),
            child: Icon(Icons.stars_rounded,
                color: context.isDark ? AppDarkColors.warningOnSoft : AppColors.warningOnSoft),
          ),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(s.customersLoyaltyTitle, style: AppTextStyles.labelMedium),
                Text(
                  balance == null
                      ? s.customersLoyaltyLoading
                      : s.customersLoyaltyPoints(balance!.points),
                  style: AppTextStyles.bodySmall.copyWith(color: context.appColors.textSecondary),
                ),
              ],
            ),
          ),
          CapabilityGate(
            requires: const ['loyalty.adjust'],
            child: KbAnchor(
              id: 'customer_detail.adjust_loyalty_button',
              child: TextButton(onPressed: onAdjust, child: Text(s.customersLoyaltyAdjust)),
            ),
          ),
        ],
      ),
    );
  }
}

class _LoyaltyHistoryCard extends StatelessWidget {
  const _LoyaltyHistoryCard({required this.moves});
  final List<LoyaltyMove> moves;

  /// The written [LoyaltyMove.note] when there is one (a manual adjustment's own reason text);
  /// otherwise a real label for the ledger's own fixed [LoyaltyMove.reason] category, falling
  /// back to that raw category rather than a blank line for one this screen doesn't name yet.
  String _describe(S s, LoyaltyMove m) {
    if (m.note.isNotEmpty) return m.note;
    return switch (m.reason) {
      'redeem' => s.customersLoyaltyReasonRedeem,
      'adjust' => s.customersLoyaltyReasonAdjust,
      'earn' => s.customersLoyaltyReasonEarn,
      'expire' => s.customersLoyaltyReasonExpire,
      '' => s.customersLoyaltyHistoryNoReason,
      _ => m.reason,
    };
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final locale = Localizations.localeOf(context).languageCode;
    final dark = context.isDark;
    final sorted = [...moves]..sort((a, b) => b.at.compareTo(a.at));
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(s.customersLoyaltyHistoryTitle, style: AppTextStyles.labelMedium),
          const SizedBox(height: AppSpacing.sm),
          for (final m in sorted.take(10))
            Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.xs),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: m.delta >= 0
                          ? (dark ? AppDarkColors.successSoft : AppColors.successSoft)
                          : (dark ? AppDarkColors.dangerSoft : AppColors.dangerSoft),
                      borderRadius: BorderRadius.circular(AppRadius.pill),
                    ),
                    child: Text(
                      '${m.delta >= 0 ? '+' : ''}${m.delta}',
                      style: AppTextStyles.caption.copyWith(
                        fontWeight: FontWeight.w800,
                        color: m.delta >= 0
                            ? (dark ? AppDarkColors.successOnSoft : AppColors.successOnSoft)
                            : (dark ? AppDarkColors.dangerOnSoft : AppColors.dangerOnSoft),
                      ),
                    ),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: Text(_describe(s, m),
                        style: AppTextStyles.bodySmall, maxLines: 1, overflow: TextOverflow.ellipsis),
                  ),
                  Text(
                    Formatters.formatTimeAgo(
                        DateTime.fromMillisecondsSinceEpoch(m.at * 1000), locale: locale),
                    style: AppTextStyles.caption.copyWith(color: context.appColors.textMuted),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _OffersCard extends StatelessWidget {
  const _OffersCard({required this.offers});
  final List<CustomerOffer> offers;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final locale = Localizations.localeOf(context).languageCode;
    final live = offers.where((o) => o.live).toList();
    final expired = offers.where((o) => !o.live).toList();
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(s.customersOffersTitle, style: AppTextStyles.labelMedium),
          const SizedBox(height: AppSpacing.sm),
          for (final o in live)
            Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.xs),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.local_offer_rounded, size: 14, color: context.appColors.textMuted),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(o.text, style: AppTextStyles.bodySmall),
                        if (o.expiresAt > 0)
                          Text(
                            s.customersOfferExpires(Formatters.formatDateShort(
                                DateTime.fromMillisecondsSinceEpoch(o.expiresAt * 1000),
                                locale: locale)),
                            style: AppTextStyles.caption.copyWith(color: context.appColors.textMuted),
                          ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          // DIMMED AND LABELLED, NEVER REMOVED — the same owner-visible history Customer.tsx's own
          // past-offers section keeps: "did he get last month's offer?" is a question the shop
          // still asks after it ran out.
          for (final o in expired)
            Opacity(
              opacity: 0.6,
              child: Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.xs),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Icons.local_offer_outlined, size: 14, color: context.appColors.textMuted),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(o.text, style: AppTextStyles.bodySmall),
                          Row(
                            children: [
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                                decoration: BoxDecoration(
                                  color: context.appColors.surfaceAlt,
                                  borderRadius: BorderRadius.circular(AppRadius.pill),
                                ),
                                child: Text(s.customersOfferExpiredBadge,
                                    style: AppTextStyles.caption
                                        .copyWith(color: context.appColors.textSecondary)),
                              ),
                              const SizedBox(width: 6),
                              Text(
                                Formatters.formatDateShort(
                                    DateTime.fromMillisecondsSinceEpoch(o.expiresAt * 1000),
                                    locale: locale),
                                style:
                                    AppTextStyles.caption.copyWith(color: context.appColors.textMuted),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _VisitsCard extends StatelessWidget {
  const _VisitsCard({required this.visits});
  final List<CustomerVisit> visits;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final locale = Localizations.localeOf(context).languageCode;
    final sorted = [...visits]..sort((a, b) => b.occurredAt.compareTo(a.occurredAt));
    final shown = sorted.take(20).toList();
    // THE GAP BEFORE EACH VISIT, NOT JUST ITS DATE — the owner's own ask: seeing "21/09" tells
    // an operator nothing about this customer's real routine; seeing "كل ~21 يوم" next to it does,
    // at a glance, without doing the subtraction in his head. Computed against the next OLDER
    // visit in this same sorted list (never a second fetch) — the oldest row shown has nothing
    // earlier to compare against, so it carries no gap.
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(s.customersVisitsTitle, style: AppTextStyles.labelMedium),
          const SizedBox(height: AppSpacing.sm),
          if (shown.isEmpty)
            Text(s.customersVisitsEmpty,
                style: AppTextStyles.bodySmall.copyWith(color: context.appColors.textMuted))
          else
            for (var i = 0; i < shown.length; i++)
              Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(
                      shown[i].free ? Icons.card_giftcard_rounded : Icons.check_circle_outline_rounded,
                      size: 15,
                      color: shown[i].free
                          ? (context.isDark ? AppDarkColors.warningOnSoft : AppColors.warningOnSoft)
                          : (context.isDark ? AppDarkColors.successOnSoft : AppColors.successOnSoft),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(shown[i].services.isNotEmpty ? shown[i].services : s.customersVisitNoServices,
                              style: AppTextStyles.bodySmall.copyWith(fontWeight: FontWeight.w600)),
                          if (shown[i].meter > 0)
                            Text(
                              s.customersVisitMeter(shown[i].meter),
                              style: AppTextStyles.caption.copyWith(color: context.appColors.textMuted),
                            ),
                          if (shown[i].note.isNotEmpty)
                            Text(
                              shown[i].note,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: AppTextStyles.caption.copyWith(color: context.appColors.textSecondary),
                            ),
                          Row(
                            children: [
                              Text(
                                Formatters.formatDateTime(
                                    DateTime.fromMillisecondsSinceEpoch(shown[i].occurredAt * 1000),
                                    locale: locale),
                                style: AppTextStyles.caption.copyWith(color: context.appColors.textMuted),
                              ),
                              if (i + 1 < shown.length) ...[
                                const SizedBox(width: 6),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                                  decoration: BoxDecoration(
                                    color: context.appColors.surfaceAlt,
                                    borderRadius: BorderRadius.circular(AppRadius.pill),
                                  ),
                                  child: Text(
                                    s.customersVisitGapDays(
                                        ((shown[i].occurredAt - shown[i + 1].occurredAt) / 86400)
                                            .round()),
                                    style: AppTextStyles.caption
                                        .copyWith(color: context.appColors.textSecondary),
                                  ),
                                ),
                              ],
                            ],
                          ),
                        ],
                      ),
                    ),
                    if (shown[i].rating != null)
                      Row(
                        children: [
                          const Icon(Icons.star_rounded, size: 13, color: Color(0xFFF59F00)),
                          const SizedBox(width: 2),
                          Text('${shown[i].rating}', style: AppTextStyles.caption),
                        ],
                      ),
                  ],
                ),
              ),
        ],
      ),
    );
  }
}

/// Booking history + attendance rate — `attended / (attended+no_show)`, client-computed exactly
/// like Customer.tsx's own `CustomerBookingHistory` (only over CLOSED bookings; a still-open
/// `booked`/`cancelled` row never counts toward it).
class _BookingsCard extends StatelessWidget {
  const _BookingsCard({required this.bookings});
  final List<CustomerBooking> bookings;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final locale = Localizations.localeOf(context).languageCode;
    final now = DateTime.now().millisecondsSinceEpoch ~/ 1000;
    final upcoming = bookings.where((b) => b.status == 'booked' && b.startsAt >= now).toList()
      ..sort((a, b) => a.startsAt.compareTo(b.startsAt));
    final attended = bookings.where((b) => b.status == 'attended').length;
    final noShow = bookings.where((b) => b.status == 'no_show').length;
    final closed = attended + noShow;
    final rate = closed > 0 ? (attended / closed * 100).round() : null;

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                  child: Text(s.customersBookingsTitle, style: AppTextStyles.labelMedium)),
              if (rate != null)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: rate >= 80
                        ? (context.isDark ? AppDarkColors.successSoft : AppColors.successSoft)
                        : (context.isDark ? AppDarkColors.warningSoft : AppColors.warningSoft),
                    borderRadius: BorderRadius.circular(AppRadius.pill),
                  ),
                  child: Text(
                    s.customersAttendanceRate(rate),
                    style: AppTextStyles.caption.copyWith(
                      fontWeight: FontWeight.w700,
                      color: rate >= 80
                          ? (context.isDark ? AppDarkColors.successOnSoft : AppColors.successOnSoft)
                          : (context.isDark ? AppDarkColors.warningOnSoft : AppColors.warningOnSoft),
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          if (upcoming.isEmpty)
            Text(s.customersBookingsNoneUpcoming,
                style: AppTextStyles.bodySmall.copyWith(color: context.appColors.textMuted))
          else
            for (final b in upcoming.take(5))
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Row(
                  children: [
                    Icon(Icons.event_rounded, size: 13, color: context.appColors.textMuted),
                    const SizedBox(width: 6),
                    Text(
                      Formatters.formatDateTime(
                          DateTime.fromMillisecondsSinceEpoch(b.startsAt * 1000), locale: locale),
                      style: AppTextStyles.bodySmall,
                    ),
                  ],
                ),
              ),
        ],
      ),
    );
  }
}

/// Adaptive reminder cycles, one per service — `learned` rows are still being timed by real
/// visit gaps; a pinned row (edited here) stopped that learning for this customer/service pair.
class _RulesCard extends StatelessWidget {
  const _RulesCard({required this.rules, required this.serviceNames, required this.onEdit});
  final List<ReminderRule> rules;
  final Map<String, String> serviceNames;
  final void Function(ReminderRule rule, String label) onEdit;

  /// The real name if the reminders row carried one, else the shop's own service catalogue —
  /// NEVER the raw `serviceId` itself, which is an internal key, not something a person reads.
  String _label(S s, ReminderRule r) {
    final fromCatalogue = serviceNames[r.serviceId];
    return r.serviceName ??
        (fromCatalogue != null && fromCatalogue.isNotEmpty
            ? fromCatalogue
            : s.customersCyclesUnknownService);
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(s.customersCyclesTitle, style: AppTextStyles.labelMedium),
          const SizedBox(height: AppSpacing.sm),
          for (final r in rules)
            Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.xs),
              child: InkWell(
                onTap: () => onEdit(r, _label(s, r)),
                borderRadius: AppRadius.standardRadius,
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: Row(
                    children: [
                      Expanded(
                        child: Text(_label(s, r),
                            style: AppTextStyles.bodySmall, maxLines: 1, overflow: TextOverflow.ellipsis),
                      ),
                      if (!r.learned) ...[
                        Icon(Icons.psychology_outlined, size: 13, color: context.appColors.textMuted),
                        const SizedBox(width: 3),
                      ],
                      Text(s.customersCyclesEveryDays(r.intervalDays),
                          style: AppTextStyles.caption.copyWith(color: context.appColors.textSecondary)),
                      const SizedBox(width: 4),
                      Icon(
                        Directionality.of(context) == TextDirection.rtl
                            ? Icons.chevron_left_rounded
                            : Icons.chevron_right_rounded,
                        size: 16,
                        color: context.appColors.textMuted,
                      ),
                    ],
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _LogCard extends StatelessWidget {
  const _LogCard({required this.entries, required this.unavailable});
  final List<ReminderLogEntry> entries;
  final String? unavailable;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final locale = Localizations.localeOf(context).languageCode;
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(s.customersLogTitle, style: AppTextStyles.labelMedium),
          const SizedBox(height: AppSpacing.sm),
          if (unavailable != null)
            Text(unavailable!, style: AppTextStyles.bodySmall.copyWith(color: AppColors.warningOnSoft))
          else if (entries.isEmpty)
            Text(s.customersLogEmpty,
                style: AppTextStyles.bodySmall.copyWith(color: context.appColors.textMuted))
          else
            for (final e in entries)
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(
                      e.outcome == 'sent' ? Icons.send_rounded : Icons.error_outline_rounded,
                      size: 13,
                      color: e.outcome == 'sent'
                          ? context.appColors.textMuted
                          : AppColors.danger,
                    ),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(e.templateType.isNotEmpty ? e.templateType : e.outcome,
                              style: AppTextStyles.bodySmall),
                          // WHY IT DID NOT GO OUT — quiet hours, the daily cap, no consent, an
                          // unapproved template — the server's own real sentence, never a guess.
                          // Every correct refusal reads as a fault until it is named.
                          if (e.outcome != 'sent' && e.reason.isNotEmpty)
                            Text(e.reason,
                                style: AppTextStyles.caption
                                    .copyWith(color: context.appColors.textMuted)),
                        ],
                      ),
                    ),
                    Text(
                      Formatters.formatTimeAgo(
                          DateTime.fromMillisecondsSinceEpoch(e.at * 1000), locale: locale),
                      style: AppTextStyles.caption.copyWith(color: context.appColors.textMuted),
                    ),
                  ],
                ),
              ),
        ],
      ),
    );
  }
}

class _EditRuleSheet extends StatefulWidget {
  const _EditRuleSheet({required this.service, required this.rule, required this.label});
  final CustomersService service;
  final ReminderRule rule;
  final String label;

  @override
  State<_EditRuleSheet> createState() => _EditRuleSheetState();
}

class _EditRuleSheetState extends State<_EditRuleSheet> {
  late int _days;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _days = widget.rule.intervalDays > 0 ? widget.rule.intervalDays : 30;
  }

  Future<void> _submit() async {
    setState(() => _saving = true);
    final ok = await widget.service.setReminderRule(widget.rule.key, intervalDays: _days);
    if (!mounted) return;
    Navigator.of(context).pop(ok);
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: Container(
        padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.lg, AppSpacing.lg, AppSpacing.xl),
        decoration: const BoxDecoration(
          color: AppColors.surface1,
          borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(widget.label, style: AppTextStyles.headlineSmall),
            const SizedBox(height: 4),
            Text(s.customersCyclesEditHint, style: AppTextStyles.bodySmall.copyWith(color: AppColors.textMuted)),
            const SizedBox(height: AppSpacing.lg),
            KbAnchor(
              id: 'customer_detail.cycles_stepper',
              child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                IconButton(
                  onPressed: _days > 1 ? () => setState(() => _days -= 1) : null,
                  icon: const Icon(Icons.remove_circle_outline_rounded),
                ),
                SizedBox(
                  width: 90,
                  child: Text(s.customersCyclesEveryDays(_days),
                      textAlign: TextAlign.center, style: AppTextStyles.headlineSmall),
                ),
                IconButton(
                  onPressed: _days < 1095 ? () => setState(() => _days += 1) : null,
                  icon: const Icon(Icons.add_circle_outline_rounded),
                ),
              ],
              ),
            ),
            const SizedBox(height: AppSpacing.lg),
            PrimaryButton(
              text: s.customersCyclesSave,
              isLoading: _saving,
              onPressed: _saving ? null : _submit,
            ),
          ],
        ),
      ),
    );
  }
}

class _RenameSheet extends StatelessWidget {
  const _RenameSheet({required this.controller});
  final TextEditingController controller;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: Container(
        padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.lg, AppSpacing.lg, AppSpacing.xl),
        decoration: const BoxDecoration(
          color: AppColors.surface1,
          borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(s.customersRenameTitle, style: AppTextStyles.headlineSmall),
            const SizedBox(height: AppSpacing.lg),
            KbAnchor(
              id: 'customer_detail.rename_field',
              child: AppTextField(labelText: s.customersAddNameLabel, controller: controller),
            ),
            const SizedBox(height: AppSpacing.lg),
            PrimaryButton(
              text: s.customersRenameSubmit,
              onPressed: () => Navigator.of(context).pop(controller.text.trim()),
            ),
          ],
        ),
      ),
    );
  }
}

class _AdjustLoyaltySheet extends StatefulWidget {
  const _AdjustLoyaltySheet({required this.service, required this.subjectRef});
  final CustomersService service;
  final String subjectRef;

  @override
  State<_AdjustLoyaltySheet> createState() => _AdjustLoyaltySheetState();
}

class _AdjustLoyaltySheetState extends State<_AdjustLoyaltySheet> {
  final _noteController = TextEditingController();
  int _delta = 10;
  bool _saving = false;
  String? _error;

  @override
  void dispose() {
    _noteController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final s = S.of(context)!;
    if (_delta == 0 || _noteController.text.trim().length < 3) {
      setState(() => _error = s.customersLoyaltyAdjustNoteRequired);
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    final result = await widget.service.adjustLoyalty(
      subjectRef: widget.subjectRef,
      delta: _delta,
      note: _noteController.text.trim(),
    );
    if (!mounted) return;
    if (result.ok) {
      Navigator.of(context).pop(true);
    } else {
      setState(() {
        _saving = false;
        _error = result.reason ?? s.customersActionFailed;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: Container(
        padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.lg, AppSpacing.lg, AppSpacing.xl),
        decoration: const BoxDecoration(
          color: AppColors.surface1,
          borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(s.customersLoyaltyAdjustTitle, style: AppTextStyles.headlineSmall),
            const SizedBox(height: AppSpacing.lg),
            KbAnchor(
              id: 'customer_detail.loyalty_adjust_stepper',
              child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                IconButton(
                  onPressed: () => setState(() => _delta -= 10),
                  icon: const Icon(Icons.remove_circle_outline_rounded),
                ),
                SizedBox(
                  width: 70,
                  child: Text(
                    '${_delta > 0 ? '+' : ''}$_delta',
                    textAlign: TextAlign.center,
                    style: AppTextStyles.headlineMedium,
                  ),
                ),
                IconButton(
                  onPressed: () => setState(() => _delta += 10),
                  icon: const Icon(Icons.add_circle_outline_rounded),
                ),
              ],
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            KbAnchor(
              id: 'customer_detail.loyalty_adjust_note_field',
              child: AppTextField(labelText: s.customersLoyaltyAdjustNoteLabel, controller: _noteController),
            ),
            if (_error != null) ...[
              const SizedBox(height: AppSpacing.md),
              AppAlert(type: AlertType.error, message: _error!),
            ],
            const SizedBox(height: AppSpacing.lg),
            PrimaryButton(
              text: _saving ? s.customersAddSubmitting : s.customersLoyaltyAdjustSubmit,
              isLoading: _saving,
              onPressed: _saving ? null : _submit,
            ),
          ],
        ),
      ),
    );
  }
}

class _EraseConfirmSheet extends StatefulWidget {
  const _EraseConfirmSheet({required this.customerName});
  final String customerName;

  @override
  State<_EraseConfirmSheet> createState() => _EraseConfirmSheetState();
}

class _EraseConfirmSheetState extends State<_EraseConfirmSheet> {
  final _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final matches = _controller.text.trim() == widget.customerName.trim() &&
        widget.customerName.trim().isNotEmpty;
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: Container(
        padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.lg, AppSpacing.lg, AppSpacing.xl),
        decoration: const BoxDecoration(
          color: AppColors.surface1,
          borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.card)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(s.customersEraseTitle, style: AppTextStyles.headlineSmall),
            const SizedBox(height: AppSpacing.sm),
            AppAlert(type: AlertType.warning, message: s.customersEraseWarning),
            const SizedBox(height: AppSpacing.md),
            Text(s.customersEraseTypeNameLabel(widget.customerName),
                style: AppTextStyles.bodySmall),
            const SizedBox(height: AppSpacing.sm),
            KbAnchor(
              id: 'customer_detail.erase_confirm_field',
              child: AppTextField(controller: _controller, onChanged: (_) => setState(() {})),
            ),
            const SizedBox(height: AppSpacing.lg),
            KbAnchor(
              id: 'customer_detail.erase_confirm_button',
              child: SizedBox(
              width: double.infinity,
              child: TextButton(
                onPressed: matches ? () => Navigator.of(context).pop(true) : null,
                style: TextButton.styleFrom(
                  backgroundColor: matches ? AppColors.danger : AppColors.surface2,
                  foregroundColor: matches ? Colors.white : AppColors.textMuted,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(borderRadius: AppRadius.standardRadius),
                ),
                child: Text(s.customersEraseConfirm),
              ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
