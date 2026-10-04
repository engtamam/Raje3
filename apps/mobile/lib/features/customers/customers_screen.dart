import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/providers/branch_provider.dart';
import 'package:raje3_mobile/core/providers/nav_provider.dart';
import 'package:raje3_mobile/core/router/route_names.dart';
import 'package:raje3_mobile/core/services/customers_service.dart';
import 'package:raje3_mobile/core/utils/formatters.dart';
import 'package:raje3_mobile/core/utils/validators.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/models/customer_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/widgets/capability_gate.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';

/// Per-avatar identity color, cycling a fixed palette by the customer's own id — never random
/// per rebuild, and never one flat repeated tone for every row (found live, 2026-09-22: the
/// owner's own "ما فيها جمالية ولا تمايز لوني" — every avatar wore the exact same accent chip).
const List<Color> _avatarPaletteLight = [
  AppColors.accent,
  Color(0xFF0E8A64), // success-on-soft family, deeper
  Color(0xFFA0680A), // warning-on-soft family, deeper
  Color(0xFF2F5F8F), // info-on-soft family, deeper
  Color(0xFFB7412F), // danger-on-soft family, deeper
];

const List<Color> _avatarPaletteDark = [
  AppDarkColors.accent,
  AppDarkColors.success,
  AppDarkColors.warning,
  AppDarkColors.info,
  AppDarkColors.danger,
];

Color _avatarColor(BuildContext context, String id) {
  final palette = context.isDark ? _avatarPaletteDark : _avatarPaletteLight;
  final idx = id.isEmpty ? 0 : id.codeUnits.fold<int>(0, (a, b) => a + b) % palette.length;
  return palette[idx];
}

/// «عملائي» — mobile mirror of apps/console/src/screens/Customers.tsx: the shop's own customer
/// book. Real server search (not a client-side filter), a real "من تأخّر" tab (reminders' own
/// due-schedule join, the same source that badges rows across the whole screen), and a real add-
/// customer flow. Built fresh for touch — a search-first screen, not a translated table.
class CustomersScreen extends StatefulWidget {
  const CustomersScreen({super.key});

  @override
  State<CustomersScreen> createState() => _CustomersScreenState();
}

enum _Tab { all, overdue }

class _CustomersScreenState extends State<CustomersScreen> {
  late final CustomersService _service;

  List<Customer>? _recent; // null while loading
  bool _recentFailed = false;
  bool _recentDenied = false;
  Set<String> _overdueIds = {};
  List<Customer>? _overdueCustomers;
  bool _overdueFailed = false;
  bool _overdueDenied = false;
  bool _loadingOverdue = false;

  final _searchController = TextEditingController();
  List<CustomerHit> _hits = [];
  bool _searching = false;
  bool _searchFailed = false;
  Timer? _debounce;

  _Tab _tab = _Tab.all;

  List<({PrivacyRequest request, Customer? customer})>? _privacyRequests;

  @override
  void initState() {
    super.initState();
    _service = CustomersService(apiClient: context.read<AuthProvider>().apiClient);
    // NEVER ASKED FOR, SO NEVER FAILED AND NEVER EMPTY — the same distinction
    // Customers.tsx's own `DENIED` sentinel makes: a role that never held this capability at all
    // gets told so plainly, instead of reading like the server itself just failed to answer.
    if (context.read<NavProvider>().catalog.hasAll(['operations.recent'])) {
      _loadRecent();
    } else {
      _recentDenied = true;
    }
    _loadPrivacyRequests();
    // A BRANCH SWITCH ELSEWHERE (the home hero's own chip) MUST REACH THIS LIST TOO — same
    // pattern visit_screen.dart's own today's-bookings card already holds to.
    context.read<BranchProvider>().addListener(_onBranchChanged);
  }

  void _onBranchChanged() {
    if (!mounted) return;
    if (!_recentDenied) _loadRecent();
    if (_tab == _Tab.overdue) {
      setState(() => _overdueCustomers = null);
      _loadOverdue();
    }
  }

  Future<void> _loadPrivacyRequests() async {
    final catalog = context.read<NavProvider>().catalog;
    if (!catalog.hasAll(['operations.privacy_requests'])) return;
    final requests = await _service.privacyRequests();
    if (!mounted || requests == null || requests.isEmpty) return;
    final refs = requests.map((r) => r.subjectRef).where((r) => r.isNotEmpty).toList();
    // branch-scope-exempt: PDPL requests are account-wide, not per-branch — the owner must see
    // and answer every privacy request regardless of which branch the customer last visited.
    final customers = await _service.byRefs(refs);
    if (!mounted) return;
    final byRef = {for (final c in customers ?? const <Customer>[]) c.subjectRef: c};
    setState(() {
      _privacyRequests = [
        for (final r in requests) (request: r, customer: byRef[r.subjectRef]),
      ];
    });
  }

  Future<void> _closePrivacyRequest(String requestId) async {
    final s = S.of(context)!;
    final ok = await _service.closePrivacyRequest(requestId);
    if (!mounted) return;
    if (ok) {
      setState(() => _privacyRequests =
          _privacyRequests!.where((x) => x.request.id != requestId).toList());
    } else {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(s.customersActionFailed)));
    }
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _searchController.dispose();
    context.read<BranchProvider>().removeListener(_onBranchChanged);
    super.dispose();
  }

  String get _branchId => context.read<BranchProvider>().selectedId ?? '';

  Future<void> _loadRecent() async {
    setState(() {
      _recent = null;
      _recentFailed = false;
    });
    final result = await _service.recent(branchId: _branchId);
    if (!mounted) return;
    setState(() {
      _recent = result ?? [];
      _recentFailed = result == null;
    });
  }

  Future<void> _loadOverdue() async {
    if (_overdueCustomers != null || _loadingOverdue) return;
    final catalog = context.read<NavProvider>().catalog;
    if (!catalog.hasAll(['reminders.list_schedule']) ||
        !catalog.hasAll(['operations.customers_by_refs'])) {
      setState(() => _overdueDenied = true);
      return;
    }
    setState(() {
      _loadingOverdue = true;
      _overdueFailed = false;
    });
    final refs = await _service.overdueSubjectRefs();
    if (refs == null) {
      if (!mounted) return;
      setState(() {
        _loadingOverdue = false;
        _overdueFailed = true;
      });
      return;
    }
    // THE SCHEDULE ITSELF CARRIES NO BRANCH (reminders holds pseudonyms only) — narrowing to the
    // selected branch happens on the RESOLVE step below, the same place `resolve_customers`
    // already applies `branch_scope()` server-side.
    final customers = await _service.byRefs(refs, branchId: _branchId);
    if (!mounted) return;
    setState(() {
      _loadingOverdue = false;
      _overdueFailed = customers == null;
      _overdueCustomers = customers ?? [];
      _overdueIds = (customers ?? []).map((c) => c.id).toSet();
    });
  }

  void _onSearchChanged(String raw) {
    final q = raw.trim();
    _debounce?.cancel();
    if (q.length < 3) {
      setState(() {
        _hits = [];
        _searching = false;
        _searchFailed = false;
      });
      return;
    }
    _debounce = Timer(const Duration(milliseconds: 180), () async {
      setState(() => _searching = true);
      final result = await _service.suggest(q, branchId: _branchId);
      if (!mounted || _searchController.text.trim() != q) return;
      setState(() {
        _searching = false;
        _hits = result.hits;
        _searchFailed = !result.ok;
      });
    });
  }

  Future<void> _openAddCustomer() async {
    final created = await showModalBottomSheet<Customer>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _AddCustomerSheet(service: _service),
    );
    if (created != null && mounted) {
      _loadRecent();
      context.pushNamed(RouteNames.customerDetail,
          pathParameters: {'customerId': created.id});
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final catalog = context.watch<NavProvider>().catalog;
    // BOOLEAN, NOT A WIDGET GATE — decides which list-OPTION exists inside SegmentedFilter's own
    // `options:` array below, not whether a widget renders. `CapabilityGate` wraps a widget it can
    // hide; it cannot stand in for one entry of a data list, so this stays a plain `hasAll` check.
    final canOverdue =
        catalog.hasAll(['reminders.list_schedule']) && catalog.hasAll(['operations.customers_by_refs']);
    final query = _searchController.text.trim();
    final isSearching = query.length >= 3;

    final total = _recent?.length;
    final dark = context.isDark;

    return KbAnchor(
      id: 'customers',
      child: Scaffold(
        backgroundColor: AppColors.surface0,
        floatingActionButton: CapabilityGate(
          requires: const ['operations.ensure_customer'],
          child: KbAnchor(
            id: 'customers.add_button',
            child: FloatingActionButton.extended(
              onPressed: _openAddCustomer,
              icon: const Icon(Icons.person_add_alt_1_rounded),
              label: Text(s.customersAddOpen),
            ),
          ),
        ),
        body: Column(
          children: [
            // ── HERO — the same gradient identity language home_screen's own header wears,
            // brought here instead of a bare AppBar: a count that says something real (never
            // invented), and the search field surfaced as a floating "peeking" card rather than
            // a plain text field sitting flush under a title.
            Container(
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
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: Colors.white.withValues(alpha: 0.08),
                        ),
                      ),
                    ),
                    SafeArea(
                      bottom: false,
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(
                            AppSpacing.lg, AppSpacing.md, AppSpacing.lg, AppSpacing.xl + 8),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(s.customersTitle,
                                      style: AppTextStyles.displaySmall
                                          .copyWith(color: AppColors.accentContrast)),
                                  const SizedBox(height: 2),
                                  Text(
                                    total != null
                                        ? s.customersCountLabel(total)
                                        : s.customersLoyaltyLoading,
                                    style: AppTextStyles.bodySmall.copyWith(
                                        color: AppColors.accentContrast.withValues(alpha: 0.85)),
                                  ),
                                ],
                              ),
                            ),
                            Container(
                              width: 44,
                              height: 44,
                              decoration: BoxDecoration(
                                color: Colors.white.withValues(alpha: 0.18),
                                borderRadius: BorderRadius.circular(AppRadius.md),
                              ),
                              child: const Icon(Icons.people_alt_rounded, color: Colors.white),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            Transform.translate(
              offset: const Offset(0, -22),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
                child: Column(
                  children: [
                    Container(
                      decoration: BoxDecoration(
                        color: dark ? AppDarkColors.surface1 : AppColors.surface1,
                        borderRadius: AppRadius.cardRadius,
                        boxShadow: dark ? AppShadows.darkCard : AppShadows.card,
                      ),
                      child: KbAnchor(
                        id: 'customers.search_field',
                        child: AppTextField(
                          controller: _searchController,
                          hintText: s.customersSearchHint,
                          prefixIcon: Icons.search_rounded,
                          onChanged: _onSearchChanged,
                        ),
                      ),
                    ),
                    if (!isSearching && _privacyRequests != null && _privacyRequests!.isNotEmpty) ...[
                      const SizedBox(height: AppSpacing.sm),
                      _PrivacyRequestsBanner(
                        requests: _privacyRequests!,
                        onClose: _closePrivacyRequest,
                        onOpenCustomer: (id) => context.pushNamed(RouteNames.customerDetail,
                            pathParameters: {'customerId': id}),
                      ),
                    ],
                    if (!isSearching) ...[
                      const SizedBox(height: AppSpacing.sm),
                      SegmentedFilter<_Tab>(
                        value: _tab,
                        onChanged: (v) {
                          setState(() => _tab = v);
                          if (v == _Tab.overdue) _loadOverdue();
                        },
                        options: [
                          SegmentedFilterOption(value: _Tab.all, label: s.customersTabAll),
                          if (canOverdue)
                            SegmentedFilterOption(value: _Tab.overdue, label: s.customersTabOverdue),
                        ],
                      ),
                    ],
                  ],
                ),
              ),
            ),
            Expanded(
              child: Transform.translate(
                offset: const Offset(0, -14),
                child: isSearching
                    ? _buildSearchResults(s)
                    : (_tab == _Tab.all ? _buildRecentList(s) : _buildOverdueList(s)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSearchResults(S s) {
    if (_searching) return const AppLoadingIndicator();
    if (_searchFailed) {
      return EmptyState(
        icon: Icons.search_off_rounded,
        title: s.customersSearchFailedTitle,
        message: s.customersSearchFailedBody,
      );
    }
    if (_hits.isEmpty) {
      return EmptyState(icon: Icons.person_search_rounded, title: s.customersSearchEmpty);
    }
    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.xxl),
      itemCount: _hits.length,
      separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.xs),
      itemBuilder: (context, i) {
        final hit = _hits[i];
        return _CustomerRow(
          id: hit.id,
          name: hit.name,
          phone: hit.phone,
          lastVisit: null,
          visitCount: null,
          overdue: false,
        );
      },
    );
  }

  Widget _buildRecentList(S s) {
    if (_recentDenied) {
      return EmptyState(
        icon: Icons.lock_outline_rounded,
        title: s.customersDeniedAllTitle,
        message: s.customersDeniedDesc,
      );
    }
    if (_recent == null) return const AppLoadingIndicator();
    if (_recentFailed) {
      return EmptyState(
        icon: Icons.cloud_off_rounded,
        title: s.customersLoadFailedTitle,
        actionText: s.mobileRequestsRetry,
        onAction: _loadRecent,
      );
    }
    if (_recent!.isEmpty) {
      return EmptyState(icon: Icons.people_outline_rounded, title: s.customersEmptyTitle);
    }
    return RefreshIndicator(
      onRefresh: _loadRecent,
      child: ListView.separated(
        padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.xxl),
        itemCount: _recent!.length,
        separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.xs),
        itemBuilder: (context, i) {
          final c = _recent![i];
          return _CustomerRow(
            id: c.id,
            name: c.name,
            phone: c.phone,
            lastVisit: c.lastVisit,
            visitCount: c.visitCount,
            overdue: _overdueIds.contains(c.id),
          );
        },
      ),
    );
  }

  Widget _buildOverdueList(S s) {
    if (_overdueDenied) {
      return EmptyState(
        icon: Icons.lock_outline_rounded,
        title: s.customersDeniedOverdueTitle,
        message: s.customersDeniedDesc,
      );
    }
    if (_loadingOverdue) return const AppLoadingIndicator();
    if (_overdueFailed) {
      return EmptyState(
        icon: Icons.cloud_off_rounded,
        title: s.customersLoadFailedTitle,
        actionText: s.mobileRequestsRetry,
        onAction: () {
          setState(() => _overdueCustomers = null);
          _loadOverdue();
        },
      );
    }
    final list = _overdueCustomers ?? [];
    if (list.isEmpty) {
      return EmptyState(icon: Icons.event_available_rounded, title: s.customersOverdueEmpty);
    }
    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.xxl),
      itemCount: list.length,
      separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.xs),
      itemBuilder: (context, i) {
        final c = list[i];
        return _CustomerRow(
          id: c.id,
          name: c.name,
          phone: c.phone,
          lastVisit: c.lastVisit,
          visitCount: c.visitCount,
          overdue: true,
        );
      },
    );
  }
}

class _CustomerRow extends StatelessWidget {
  const _CustomerRow({
    required this.id,
    required this.name,
    required this.phone,
    required this.lastVisit,
    required this.visitCount,
    required this.overdue,
  });

  final String id;
  final String name;
  final String phone;
  final int? lastVisit;
  final int? visitCount;
  final bool overdue;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final locale = Localizations.localeOf(context).languageCode;
    final colors = context.appColors;
    final dark = context.isDark;
    final label = (name.isNotEmpty ? name : phone).trim();
    final initial = label.isEmpty ? '?' : label.substring(0, 1).toUpperCase();
    final tint = _avatarColor(context, id.isNotEmpty ? id : phone);

    return Container(
      decoration: BoxDecoration(
        color: colors.surface,
        borderRadius: AppRadius.cardRadius,
        border: Border.all(color: overdue ? tint.withValues(alpha: 0.35) : colors.borderSubtle),
        boxShadow: dark ? AppShadows.darkCard : AppShadows.card,
      ),
      child: Material(
        color: Colors.transparent,
        borderRadius: AppRadius.cardRadius,
        child: InkWell(
          borderRadius: AppRadius.cardRadius,
          onTap: () =>
              context.pushNamed(RouteNames.customerDetail, pathParameters: {'customerId': id}),
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: Row(
              children: [
                Container(
                  width: 46,
                  height: 46,
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [tint, tint.withValues(alpha: 0.78)],
                    ),
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(color: tint.withValues(alpha: 0.35), blurRadius: 10, offset: const Offset(0, 4)),
                    ],
                  ),
                  child: Center(
                    child: Text(initial,
                        style: AppTextStyles.bodyMedium
                            .copyWith(fontWeight: FontWeight.w800, color: Colors.white)),
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(name.isNotEmpty ? name : s.customersUnnamed,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w700)),
                      const SizedBox(height: 2),
                      Text(phone,
                          style: AppTextStyles.caption.copyWith(
                            color: colors.textSecondary,
                            fontFamily: AppTextStyles.englishFont,
                          )),
                    ],
                  ),
                ),
                if (visitCount != null) ...[
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      if (lastVisit != null && lastVisit! > 0)
                        Text(
                          Formatters.formatTimeAgo(
                              DateTime.fromMillisecondsSinceEpoch(lastVisit! * 1000), locale: locale),
                          style: AppTextStyles.caption.copyWith(color: colors.textMuted),
                        ),
                      const SizedBox(height: 2),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                        decoration: BoxDecoration(
                          color: tint.withValues(alpha: dark ? 0.22 : 0.12),
                          borderRadius: BorderRadius.circular(AppRadius.pill),
                        ),
                        child: Text(s.customersVisitCount(visitCount!),
                            style: AppTextStyles.caption
                                .copyWith(color: tint, fontWeight: FontWeight.w700)),
                      ),
                    ],
                  ),
                ],
                if (overdue) ...[
                  const SizedBox(width: 6),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
                    decoration: BoxDecoration(
                      color: dark ? AppDarkColors.warningSoft : AppColors.warningSoft,
                      borderRadius: BorderRadius.circular(AppRadius.pill),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.schedule_rounded,
                            size: 10,
                            color: dark ? AppDarkColors.warningOnSoft : AppColors.warningOnSoft),
                        const SizedBox(width: 3),
                        Text(s.customersOverdueBadge,
                            style: AppTextStyles.caption.copyWith(
                              color: dark ? AppDarkColors.warningOnSoft : AppColors.warningOnSoft,
                              fontWeight: FontWeight.w700,
                            )),
                      ],
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

/// PDPL requests a customer raised, waiting on the shop to answer — "إغلاق" here only records
/// that the shop answered; it never erases anything itself (real erasure is the customer's own
/// detail-screen action, a separate, two-step-confirmed, irreversible call).
class _PrivacyRequestsBanner extends StatelessWidget {
  const _PrivacyRequestsBanner({
    required this.requests,
    required this.onClose,
    required this.onOpenCustomer,
  });

  final List<({PrivacyRequest request, Customer? customer})> requests;
  final ValueChanged<String> onClose;
  final ValueChanged<String> onOpenCustomer;

  String _typeLabel(S s, String type) => switch (type) {
        'erase' => s.customersPrivacyRequestErase,
        'copy' => s.customersPrivacyRequestCopy,
        _ => s.customersPrivacyRequestGeneric(type),
      };

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final dark = context.isDark;
    return KbAnchor(
      id: 'customers.privacy_requests',
      child: Container(
        decoration: BoxDecoration(
          color: dark ? AppDarkColors.dangerSoft : AppColors.dangerSoft,
          border: Border.all(color: AppColors.danger.withValues(alpha: 0.3)),
          borderRadius: AppRadius.standardRadius,
        ),
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.privacy_tip_outlined,
                    size: 15, color: dark ? AppDarkColors.dangerOnSoft : AppColors.dangerOnSoft),
                const SizedBox(width: 6),
                Text(s.customersPrivacyRequestsTitle,
                    style: AppTextStyles.labelMedium
                        .copyWith(color: dark ? AppDarkColors.dangerOnSoft : AppColors.dangerOnSoft)),
              ],
            ),
            for (final item in requests)
              Padding(
                padding: const EdgeInsets.only(top: AppSpacing.sm),
                child: Row(
                  children: [
                    Expanded(
                      child: InkWell(
                        onTap: item.customer == null
                            ? null
                            : () => onOpenCustomer(item.customer!.id),
                        child: Text(
                          item.customer != null
                              ? '${item.customer!.name.isNotEmpty ? item.customer!.name : item.customer!.phone} — ${_typeLabel(s, item.request.type)}'
                              : _typeLabel(s, item.request.type),
                          style: AppTextStyles.bodySmall,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ),
                    CapabilityGate(
                      requires: const ['operations.close_privacy_request'],
                      child: TextButton(
                        onPressed: () => onClose(item.request.id),
                        child: Text(s.customersPrivacyRequestClose),
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

class _AddCustomerSheet extends StatefulWidget {
  const _AddCustomerSheet({required this.service});
  final CustomersService service;

  @override
  State<_AddCustomerSheet> createState() => _AddCustomerSheetState();
}

class _AddCustomerSheetState extends State<_AddCustomerSheet> {
  final _phoneController = TextEditingController();
  final _nameController = TextEditingController();
  bool _saving = false;
  String? _error;

  @override
  void dispose() {
    _phoneController.dispose();
    _nameController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final s = S.of(context)!;
    final phone = _phoneController.text.trim();
    if (Validators.validatePhone(phone) != null) {
      setState(() => _error = s.customersAddPhoneInvalid);
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    final result = await widget.service.ensure(phone: phone, name: _nameController.text.trim());
    final customer = result.customer;
    if (!mounted) return;
    if (customer == null) {
      setState(() {
        _saving = false;
        _error = s.customersAddFailed;
      });
      return;
    }
    Navigator.of(context).pop(customer);
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: KbAnchor(
        id: 'customers.add_sheet',
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
              Text(s.customersAddTitle, style: AppTextStyles.headlineSmall),
              const SizedBox(height: AppSpacing.lg),
              AppTextField(
                labelText: s.customersAddPhoneLabel,
                hintText: '05xxxxxxxx',
                controller: _phoneController,
                keyboardType: TextInputType.phone,
                textDirection: TextDirection.ltr,
              ),
              const SizedBox(height: AppSpacing.md),
              AppTextField(labelText: s.customersAddNameLabel, controller: _nameController),
              if (_error != null) ...[
                const SizedBox(height: AppSpacing.md),
                AppAlert(type: AlertType.error, message: _error!),
              ],
              const SizedBox(height: AppSpacing.lg),
              PrimaryButton(
                text: _saving ? s.customersAddSubmitting : s.customersAddSubmit,
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
