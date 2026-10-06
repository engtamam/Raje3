import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show Clipboard, ClipboardData;
import 'package:provider/provider.dart';

import 'package:raje3_mobile/core/constants/api_constants.dart';
import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/providers/branch_provider.dart';
import 'package:raje3_mobile/core/providers/nav_provider.dart';
import 'package:raje3_mobile/core/services/coworking_service.dart';
import 'package:raje3_mobile/models/coworking_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/widgets/capability_gate.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';

import 'coworking_bookings_sheet.dart';
import 'coworking_join_row.dart';
import 'resource_sheet.dart';

/// «مساحة عمل مشتركة» (الاستضافة المهنية) — the SHOP OWNER/STAFF-facing admin screen for
/// services/coworking, never the freelancer-facing public booking link (that flow has no
/// mobile screen at all — it is a plain shared web link, spec §4). Three tabs, same
/// `SegmentedFilter` idiom `points_screen.dart` already uses — mirrors the console's own
/// `Coworking.tsx` (`resources`/`joins`/`bookings`), which this screen fell one tab short of
/// until now:
///
/// «الموارد» — branch-scoped automatically (this app's own [BranchProvider]/branch-chip
/// convention), photo-first resource cards, a quick active/paused toggle, and a tap that opens
/// the full edit/availability/photo sheet. Each card ALSO keeps its own quick «الحجوزات» button
/// (opens [CoworkingBookingsSheet], pre-filtered to that one resource) — a fast single-resource
/// look stays one tap away even with the full cross-resource tab below.
///
/// «طلبات الانضمام» — DELIBERATELY carries NO branch filter at all, mirroring
/// `core/joins.py`'s own module doc: the gate is per-shop, never per-chair.
///
/// «الحجوزات» — EVERY resource's bookings in one list (`coworking.list_bookings`, no
/// `resourceId`), grouped by day, newest first — the cross-resource view the console's own
/// `BookingsTab` already gives an owner; this mobile pass only ever had the per-resource sheet.
///
/// THE SHOP-WIDE PAUSE SWITCH sits in the hero, above every tab and outside any branch context —
/// `core/models.py`'s own module doc is explicit that pausing is a single, shop-wide switch, and
/// putting it inside a branch-scoped tab would misstate what it actually does.
class CoworkingScreen extends StatefulWidget {
  const CoworkingScreen({super.key});

  @override
  State<CoworkingScreen> createState() => _CoworkingScreenState();
}

enum _Tab { resources, joins, bookings }

// THREE REAL COLOUR IDENTITIES, ONE PER TAB — mirrors the console's own `TAB_ACCENT`
// (Coworking.tsx, the owner's own request for "تمايز لوني عالي"): الموارد (what you own) reads
// the hero's own violet, طلبات الانضمام (a pending decision) reads amber, الحجوزات (a settled
// fact — a calendar entry, not a decision waiting on anyone) reads the console's own "info" blue.
const _resourcesAccent = Color(0xFF6A4CF5);
const _joinsAccent = Color(0xFFE8A93A);
const _bookingsAccent = Color(0xFF3B82C4);

class _CoworkingScreenState extends State<CoworkingScreen> {
  late final CoworkingService _service;

  List<CoworkingResource>? _resources;
  bool _resourcesFailed = false;
  List<CoworkingJoin>? _joins;
  bool _joinsFailed = false;
  List<CoworkingBooking>? _bookings;
  bool _bookingsFailed = false;
  final Set<String> _cancellingBookings = {};
  bool? _paused;
  bool _pauseBusy = false;
  _Tab _tab = _Tab.resources;

  @override
  void initState() {
    super.initState();
    _service =
        CoworkingService(apiClient: context.read<AuthProvider>().apiClient);
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _resources = null;
      _resourcesFailed = false;
      _joins = null;
      _joinsFailed = false;
      _bookings = null;
      _bookingsFailed = false;
    });
    final results = await Future.wait([
      _service.listResources(),
      _service.listJoins(),
      _service.isPaused(),
      _service.listBookings(),
    ]);
    if (!mounted) return;
    setState(() {
      _resources = results[0] as List<CoworkingResource>?;
      _resourcesFailed = _resources == null;
      _joins = results[1] as List<CoworkingJoin>?;
      _joinsFailed = _joins == null;
      _paused = results[2] as bool?;
      _bookings = results[3] as List<CoworkingBooking>?;
      _bookingsFailed = _bookings == null;
    });
  }

  Future<void> _cancelBooking(CoworkingBooking b) async {
    setState(() => _cancellingBookings.add(b.id));
    await _service.cancelBooking(b.id);
    if (!mounted) return;
    setState(() => _cancellingBookings.remove(b.id));
    _load();
  }

  Future<void> _togglePause(bool value) async {
    setState(() {
      _pauseBusy = true;
    });
    final result = await _service.setPaused(value);
    if (!mounted) return;
    setState(() {
      _pauseBusy = false;
      if (result != null) _paused = result;
    });
  }

  Future<void> _openAddSheet() async {
    final branchProvider = context.read<BranchProvider>();
    final created = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) =>
          ResourceSheet(service: _service, branches: branchProvider.branches),
    );
    if (created == true && mounted) _load();
  }

  Future<void> _openEditSheet(CoworkingResource r) async {
    final branchProvider = context.read<BranchProvider>();
    final changed = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => ResourceSheet(
          service: _service, branches: branchProvider.branches, existing: r),
    );
    if (changed == true && mounted) _load();
  }

  Future<void> _openBookingsSheet(CoworkingResource r) async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => CoworkingBookingsSheet(service: _service, resource: r),
    );
  }

  Future<void> _quickToggleActive(CoworkingResource r) async {
    await _service.updateResource(r.id, active: !r.active);
    if (mounted) _load();
  }

  @override
  Widget build(BuildContext context) {
    final catalog = context.watch<NavProvider>().catalog;
    final canManage = catalog.hasAll(['coworking.update_resource']);
    final branchProvider = context.watch<BranchProvider>();

    // The list is already branch-scoped server-side; a resource with `branch_id == ""` is
    // ALWAYS visible too (unassigned rows stay shared, same rule the backend itself documents),
    // so the mobile-side filter mirrors that exactly rather than a plain equality check.
    final selectedBranchId = branchProvider.selected?.id;
    final visibleResources = (_resources ?? const [])
        .where((r) =>
            !branchProvider.hasChoice ||
            selectedBranchId == null ||
            r.branchId.isEmpty ||
            r.branchId == selectedBranchId)
        .toList();

    return KbAnchor(
      id: 'coworking',
      child: Scaffold(
        backgroundColor: AppColors.surface0,
        floatingActionButton: CapabilityGate(
          requires: const ['coworking.create_resource'],
          child: KbAnchor(
            id: 'coworking.add_button',
            child: FloatingActionButton.extended(
              onPressed: _openAddSheet,
              icon: const Icon(Icons.add_business_rounded),
              label: const Text('مورد جديد'),
            ),
          ),
        ),
        body: RefreshIndicator(
          onRefresh: _load,
          child: CustomScrollView(
            slivers: [
              SliverToBoxAdapter(
                child: _CoworkingHero(
                  paused: _paused,
                  busy: _pauseBusy,
                  canManage: canManage,
                  onChanged: _togglePause,
                ),
              ),
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(
                    AppSpacing.md, AppSpacing.sm, AppSpacing.md, 0),
                sliver: SliverToBoxAdapter(
                  child: _ShareLinkCard(
                      tenant: context.read<AuthProvider>().user?.id ?? ''),
                ),
              ),
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(
                    AppSpacing.md, AppSpacing.sm, AppSpacing.md, AppSpacing.sm),
                sliver: SliverToBoxAdapter(
                  child: KbAnchor(
                    id: 'coworking.main_tabs',
                    child: SegmentedFilter<_Tab>(
                      value: _tab,
                      onChanged: (v) => setState(() => _tab = v),
                      options: const [
                        SegmentedFilterOption(
                            value: _Tab.resources, label: 'الموارد'),
                        SegmentedFilterOption(
                            value: _Tab.joins, label: 'طلبات الانضمام'),
                        SegmentedFilterOption(
                            value: _Tab.bookings, label: 'الحجوزات'),
                      ],
                    ),
                  ),
                ),
              ),
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(
                    AppSpacing.md, 0, AppSpacing.md, AppSpacing.sm),
                sliver: SliverToBoxAdapter(
                  child: switch (_tab) {
                    _Tab.resources => const _TabSectionHeader(
                        accent: _resourcesAccent,
                        icon: Icons.chair_alt_rounded,
                        title: 'الموارد',
                        said: 'مواردك القابلة للتأجير بالساعة — صورها وأسعارها وأوقاتها',
                      ),
                    _Tab.joins => const _TabSectionHeader(
                        accent: _joinsAccent,
                        icon: Icons.how_to_reg_rounded,
                        title: 'طلبات الانضمام',
                        said: 'من يطلب الانضمام لأول مرة — وافق أو ارفض أو امنع',
                      ),
                    _Tab.bookings => const _TabSectionHeader(
                        accent: _bookingsAccent,
                        icon: Icons.event_note_rounded,
                        title: 'الحجوزات',
                        said: 'كل حجز على كل مورد، الأحدث أولاً',
                      ),
                  },
                ),
              ),
              if (_tab == _Tab.resources)
                ..._resourcesSlivers(visibleResources, canManage)
              else if (_tab == _Tab.joins)
                ..._joinsSlivers(canManage)
              else
                ..._bookingsSlivers(),
            ],
          ),
        ),
      ),
    );
  }

  List<Widget> _resourcesSlivers(
      List<CoworkingResource> visible, bool canManage) {
    if (_resources == null) {
      return [
        const SliverPadding(
            padding: EdgeInsets.all(AppSpacing.xl),
            sliver: SliverToBoxAdapter(child: AppLoadingIndicator())),
      ];
    }
    if (_resourcesFailed) {
      return [
        SliverPadding(
          padding: const EdgeInsets.all(AppSpacing.xl),
          sliver: SliverToBoxAdapter(
            child: EmptyState(
              icon: Icons.cloud_off_rounded,
              title: 'تعذر تحميل الموارد',
              actionText: 'إعادة المحاولة',
              onAction: _load,
            ),
          ),
        ),
      ];
    }
    if (visible.isEmpty) {
      return [
        const SliverPadding(
          padding: EdgeInsets.all(AppSpacing.xl),
          sliver: SliverToBoxAdapter(
            child: EmptyState(
                icon: Icons.meeting_room_outlined, title: 'لا يوجد موارد بعد'),
          ),
        ),
      ];
    }
    return [
      SliverPadding(
        padding: const EdgeInsets.fromLTRB(
            AppSpacing.md, 0, AppSpacing.md, AppSpacing.xxl),
        sliver: SliverList.separated(
          itemCount: visible.length,
          separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
          itemBuilder: (context, i) => _ResourceCard(
            resource: visible[i],
            canManage: canManage,
            onTap: canManage ? () => _openEditSheet(visible[i]) : null,
            onToggleActive:
                canManage ? () => _quickToggleActive(visible[i]) : null,
            onBookings: () => _openBookingsSheet(visible[i]),
          ),
        ),
      ),
    ];
  }

  List<Widget> _joinsSlivers(bool canManage) {
    if (_joins == null) {
      return [
        const SliverPadding(
            padding: EdgeInsets.all(AppSpacing.xl),
            sliver: SliverToBoxAdapter(child: AppLoadingIndicator())),
      ];
    }
    if (_joinsFailed) {
      return [
        SliverPadding(
          padding: const EdgeInsets.all(AppSpacing.xl),
          sliver: SliverToBoxAdapter(
            child: EmptyState(
              icon: Icons.cloud_off_rounded,
              title: 'تعذر تحميل طلبات الانضمام',
              actionText: 'إعادة المحاولة',
              onAction: _load,
            ),
          ),
        ),
      ];
    }
    if (_joins!.isEmpty) {
      return [
        const SliverPadding(
          padding: EdgeInsets.all(AppSpacing.xl),
          sliver: SliverToBoxAdapter(
            child: EmptyState(
                icon: Icons.how_to_reg_outlined, title: 'لا يوجد طلبات انضمام'),
          ),
        ),
      ];
    }
    final sorted = [..._joins!]
      ..sort((a, b) => b.createdAt.compareTo(a.createdAt));
    return [
      SliverPadding(
        padding: const EdgeInsets.fromLTRB(
            AppSpacing.md, 0, AppSpacing.md, AppSpacing.xxl),
        sliver: SliverList.separated(
          itemCount: sorted.length,
          separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
          itemBuilder: (context, i) => CoworkingJoinRow(
            join: sorted[i],
            canManage: canManage,
            onApprove: () => _actOnJoin(sorted[i], _service.approveJoin),
            onReject: () => _actOnJoin(sorted[i], _service.rejectJoin),
            onBlock: () => _actOnJoin(sorted[i], _service.blockPhone),
            onUnblock: () => _actOnJoin(sorted[i], _service.unblockPhone),
          ),
        ),
      ),
    ];
  }

  Future<void> _actOnJoin(
      CoworkingJoin j, Future<bool> Function(String) action) async {
    final ok = await action(j.phone);
    if (ok && mounted) _load();
  }

  String _resourceName(String id) {
    for (final r in _resources ?? const <CoworkingResource>[]) {
      if (r.id == id) return r.name;
    }
    return id;
  }

  List<Widget> _bookingsSlivers() {
    if (_bookings == null) {
      return [
        const SliverPadding(
            padding: EdgeInsets.all(AppSpacing.xl),
            sliver: SliverToBoxAdapter(child: AppLoadingIndicator())),
      ];
    }
    if (_bookingsFailed) {
      return [
        SliverPadding(
          padding: const EdgeInsets.all(AppSpacing.xl),
          sliver: SliverToBoxAdapter(
            child: EmptyState(
              icon: Icons.cloud_off_rounded,
              title: 'تعذر تحميل الحجوزات',
              actionText: 'إعادة المحاولة',
              onAction: _load,
            ),
          ),
        ),
      ];
    }
    if (_bookings!.isEmpty) {
      return [
        const SliverPadding(
          padding: EdgeInsets.all(AppSpacing.xl),
          sliver: SliverToBoxAdapter(
            child: EmptyState(
                icon: Icons.event_busy_outlined, title: 'لا يوجد حجوزات بعد'),
          ),
        ),
      ];
    }
    final sorted = [..._bookings!]
      ..sort((a, b) => b.startsAt.compareTo(a.startsAt));
    // GROUPED BY DAY, NEWEST FIRST — a flat list of forty bookings across a week of resources
    // reads as noise; a day header is the one extra fact ("هذا كله الثلاثاء") that turns it back
    // into something an owner can scan in a glance, same idiom `_DayHeader` establishes anywhere
    // else in this app a timeline needs one.
    final groups = <DateTime, List<CoworkingBooking>>{};
    for (final b in sorted) {
      final d = DateTime.fromMillisecondsSinceEpoch(b.startsAt * 1000);
      final day = DateTime(d.year, d.month, d.day);
      groups.putIfAbsent(day, () => []).add(b);
    }
    final days = groups.keys.toList();
    final widgets = <Widget>[];
    for (final day in days) {
      widgets.add(_BookingDayHeader(day: day));
      widgets.add(const SizedBox(height: AppSpacing.xs));
      for (final b in groups[day]!) {
        widgets.add(_BookingRow(
          booking: b,
          resourceName: _resourceName(b.resourceId),
          cancelling: _cancellingBookings.contains(b.id),
          onCancel: () => _cancelBooking(b),
        ));
        widgets.add(const SizedBox(height: AppSpacing.sm));
      }
      widgets.add(const SizedBox(height: AppSpacing.sm));
    }
    return [
      SliverPadding(
        padding: const EdgeInsets.fromLTRB(
            AppSpacing.md, 0, AppSpacing.md, AppSpacing.xxl),
        sliver: SliverList(delegate: SliverChildListDelegate(widgets)),
      ),
    ];
  }
}

/// The hero — carries only the shop-wide pause switch, deliberately with no branch chip inside
/// it (see this file's own header doc on why pause is never branch-scoped).
class _CoworkingHero extends StatelessWidget {
  const _CoworkingHero(
      {required this.paused,
      required this.busy,
      required this.canManage,
      required this.onChanged});
  final bool? paused;
  final bool busy;
  final bool canManage;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    final dark = context.isDark;
    final isPaused = paused == true;
    final gradient = LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: dark
          ? [const Color(0xFF241C4D), const Color(0xFF120A24)]
          : [const Color(0xFF3D2E7C), const Color(0xFF1C1440)],
    );

    return Container(
      decoration: BoxDecoration(
        gradient: gradient,
        borderRadius: const BorderRadius.vertical(
            bottom: Radius.circular(AppRadius.card)),
        boxShadow: dark ? AppShadows.darkButton : AppShadows.button,
      ),
      child: SafeArea(
        bottom: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(
              AppSpacing.lg, AppSpacing.md, AppSpacing.lg, AppSpacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    width: 40,
                    height: 40,
                    decoration: const BoxDecoration(
                        color: Colors.white24, shape: BoxShape.circle),
                    child: const Icon(Icons.meeting_room_rounded,
                        color: Colors.white, size: 20),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  const Text('الاستضافة المهنية',
                      style: TextStyle(
                          color: Colors.white,
                          fontSize: 22,
                          fontWeight: FontWeight.w800)),
                ],
              ),
              const SizedBox(height: AppSpacing.md),
              Container(
                padding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.md, vertical: AppSpacing.sm),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(AppRadius.card),
                ),
                child: Row(
                  children: [
                    Icon(
                        isPaused
                            ? Icons.pause_circle_rounded
                            : Icons.play_circle_rounded,
                        color: Colors.white,
                        size: 20),
                    const SizedBox(width: AppSpacing.sm),
                    Expanded(
                      child: Text(
                        isPaused
                            ? 'إيقاف استقبال حجوزات جديدة — مفعّل'
                            : 'استقبال حجوزات جديدة يعمل',
                        style: const TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.w700,
                            fontSize: 13),
                      ),
                    ),
                    if (canManage)
                      KbAnchor(
                        id: 'coworking.pause_switch',
                        child: paused == null
                            ? const SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(
                                    strokeWidth: 2, color: Colors.white))
                            : IgnorePointer(
                                ignoring: busy,
                                child: Switch(
                                    value: isPaused,
                                    onChanged: onChanged,
                                    activeThumbColor: Colors.white),
                              ),
                      ),
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

class _ResourceCard extends StatelessWidget {
  const _ResourceCard({
    required this.resource,
    required this.canManage,
    required this.onTap,
    required this.onToggleActive,
    required this.onBookings,
  });
  final CoworkingResource resource;
  final bool canManage;
  final VoidCallback? onTap;
  final VoidCallback? onToggleActive;
  final VoidCallback onBookings;

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final dark = context.isDark;
    final active = resource.active;

    return KbAnchor(
      id: 'coworking.resource_card',
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
              border: Border.all(
                  color: active
                      ? _resourcesAccent.withValues(alpha: 0.25)
                      : colors.borderSubtle),
              boxShadow: dark ? AppShadows.darkCard : AppShadows.card,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // A REAL ACCENT STRIP, NOT ANOTHER FLAT GREY TOP — echoes الموارد's own violet
                // identity (`_resourcesAccent`) on every card; a paused resource dims to the
                // ordinary border colour instead of losing the strip entirely.
                Container(
                  height: 4,
                  decoration: BoxDecoration(
                    color: active ? _resourcesAccent : colors.borderSubtle,
                    borderRadius: const BorderRadius.vertical(
                        top: Radius.circular(AppRadius.card)),
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.all(AppSpacing.md),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          _ResourceThumb(resource: resource),
                          const SizedBox(width: AppSpacing.sm),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(resource.name,
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: AppTextStyles.bodyMedium
                                        .copyWith(fontWeight: FontWeight.w700)),
                                if (resource.description.isNotEmpty)
                                  Text(resource.description,
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                      style: AppTextStyles.caption
                                          .copyWith(color: colors.textMuted)),
                                Text(
                                    '${(resource.hourlyPriceMinor / 100).toStringAsFixed(0)} ر.س / ساعة',
                                    style: AppTextStyles.caption
                                        .copyWith(color: colors.textSecondary)),
                              ],
                            ),
                          ),
                          AppBadge(
                            text: active ? 'نشط' : 'متوقف',
                            backgroundColor: active
                                ? AppColors.successSoft
                                : colors.surfaceAlt,
                            textColor: active
                                ? AppColors.successOnSoft
                                : colors.textMuted,
                          ),
                        ],
                      ),
                      const SizedBox(height: AppSpacing.sm),
                      Row(
                        children: [
                          Expanded(
                            child: SecondaryButton(
                              text: 'الحجوزات',
                              icon: Icons.event_note_outlined,
                              onPressed: onBookings,
                            ),
                          ),
                          if (onToggleActive != null) ...[
                            const SizedBox(width: AppSpacing.sm),
                            Expanded(
                              child: CapabilityGate(
                                requires: const ['coworking.update_resource'],
                                child: SecondaryButton(
                                  text: active ? 'إيقاف' : 'تفعيل',
                                  icon: active
                                      ? Icons.pause_circle_outline
                                      : Icons.play_circle_outline,
                                  onPressed: onToggleActive,
                                ),
                              ),
                            ),
                          ],
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// «الرابط المشترك» — one shareable link per shop (services/coworking/app/api/public.py's own
/// module docstring), handed to whichever freelancers the shop already works with. ALWAYS SHOWN,
/// regardless of tab — a shop-wide fact, same posture the hero's own pause switch already takes.
class _ShareLinkCard extends StatefulWidget {
  const _ShareLinkCard({required this.tenant});
  final String tenant;

  @override
  State<_ShareLinkCard> createState() => _ShareLinkCardState();
}

class _ShareLinkCardState extends State<_ShareLinkCard> {
  bool _copied = false;

  Future<void> _copy(String url) async {
    await Clipboard.setData(ClipboardData(text: url));
    if (!mounted) return;
    setState(() => _copied = true);
    Future.delayed(const Duration(seconds: 2), () {
      if (mounted) setState(() => _copied = false);
    });
  }

  @override
  Widget build(BuildContext context) {
    if (widget.tenant.isEmpty) return const SizedBox.shrink();
    final url = '${ApiConstants.baseUrl}/p/coworking/${widget.tenant}';
    final dark = context.isDark;
    return Container(
      padding: const EdgeInsets.all(AppSpacing.sm),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(AppRadius.card),
        border: Border.all(
            color: dark ? const Color(0xFF3A2D0E) : const Color(0xFFF3E3C2)),
        gradient: LinearGradient(
          colors: dark
              ? [const Color(0xFF2A2010), const Color(0xFF241C4D)]
              : [const Color(0xFFFFF6E6), const Color(0xFFFFEFDA)],
        ),
      ),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
                color: const Color(0xFFE8A93A).withValues(alpha: 0.18),
                shape: BoxShape.circle),
            child: const Icon(Icons.work_outline_rounded,
                color: Color(0xFFB5791C), size: 18),
          ),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('رابط المستقلين — شاركه مع من تثق به',
                    style: AppTextStyles.caption
                        .copyWith(fontWeight: FontWeight.w700)),
                const SizedBox(height: 2),
                Text(url,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    textDirection: TextDirection.ltr,
                    style: AppTextStyles.caption.copyWith(
                        color: context.appColors.textMuted,
                        fontFamily: 'monospace')),
              ],
            ),
          ),
          const SizedBox(width: AppSpacing.sm),
          KbAnchor(
            id: 'coworking.share_link_copy',
            child: IconButton(
              onPressed: () => _copy(url),
              icon: Icon(_copied ? Icons.check_rounded : Icons.copy_rounded,
                  color: _copied ? AppColors.success : const Color(0xFFB5791C),
                  size: 18),
              tooltip: 'نسخ الرابط',
            ),
          ),
        ],
      ),
    );
  }
}

/// One coloured section header — icon in a colour-matched circle, title + subtitle — mirrors the
/// console's own `TabSectionHeader` (Coworking.tsx), applied per active tab.
class _TabSectionHeader extends StatelessWidget {
  const _TabSectionHeader(
      {required this.accent,
      required this.icon,
      required this.title,
      required this.said});
  final Color accent;
  final IconData icon;
  final String title;
  final String said;

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    return Row(
      children: [
        Container(
          width: 34,
          height: 34,
          decoration: BoxDecoration(
              color: accent.withValues(alpha: 0.14),
              shape: BoxShape.circle,
              border:
                  Border.all(color: accent.withValues(alpha: 0.3), width: 1.5)),
          child: Icon(icon, color: accent, size: 16),
        ),
        const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title,
                  style: AppTextStyles.bodyMedium
                      .copyWith(fontWeight: FontWeight.w800)),
              Text(said,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.caption
                      .copyWith(color: colors.textSecondary)),
            ],
          ),
        ),
      ],
    );
  }
}

const _weekdaysAr = [
  'الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد',
];

class _BookingDayHeader extends StatelessWidget {
  const _BookingDayHeader({required this.day});
  final DateTime day;

  String _label() {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final yesterday = today.subtract(const Duration(days: 1));
    if (day == today) return 'اليوم';
    if (day == yesterday) return 'أمس';
    return '${_weekdaysAr[day.weekday - 1]} ${day.day}/${day.month}';
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
      child: Row(
        children: [
          Text(_label(),
              style: AppTextStyles.caption.copyWith(
                  color: colors.textMuted, fontWeight: FontWeight.w700)),
          const SizedBox(width: AppSpacing.sm),
          Expanded(child: Divider(color: colors.borderSubtle, height: 1)),
        ],
      ),
    );
  }
}

class _BookingRow extends StatelessWidget {
  const _BookingRow({
    required this.booking,
    required this.resourceName,
    required this.cancelling,
    required this.onCancel,
  });
  final CoworkingBooking booking;
  final String resourceName;
  final bool cancelling;
  final VoidCallback onCancel;

  ({String label, Color bg, Color fg}) _status(BuildContext context) {
    switch (booking.status) {
      case 'cancelled':
        final colors = context.appColors;
        return (label: 'ملغى', bg: colors.surfaceAlt, fg: colors.textMuted);
      case 'completed':
        return (
          label: 'منتهٍ',
          bg: _bookingsAccent.withValues(alpha: 0.14),
          fg: _bookingsAccent,
        );
      default:
        return (
          label: 'مؤكّد',
          bg: AppColors.successSoft,
          fg: AppColors.successOnSoft,
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final dark = context.isDark;
    final start = DateTime.fromMillisecondsSinceEpoch(booking.startsAt * 1000);
    final end = DateTime.fromMillisecondsSinceEpoch(booking.endsAt * 1000);
    String two(int n) => n.toString().padLeft(2, '0');
    final cancelled = booking.status == 'cancelled';
    final status = _status(context);

    return KbAnchor(
      id: 'coworking.booking_row',
      child: Container(
        decoration: BoxDecoration(
          color: colors.surface,
          borderRadius: AppRadius.cardRadius,
          border: Border.all(color: colors.borderSubtle),
          boxShadow: dark ? AppShadows.darkCard : AppShadows.card,
        ),
        child: Row(
          children: [
            // THE SAME ACCENT-STRIP IDIOM _ResourceCard USES, HERE ON THE LEADING EDGE — a
            // vertical bar reads as "this row belongs to this colour family" faster than any
            // badge does, and at a glance across a long day it is the thing the eye actually
            // scans for.
            Container(
              width: 4,
              height: 64,
              decoration: BoxDecoration(
                color: cancelled ? colors.borderSubtle : _bookingsAccent,
                borderRadius: const BorderRadiusDirectional.horizontal(
                    start: Radius.circular(AppRadius.card)),
              ),
            ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.all(AppSpacing.md),
                child: Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Expanded(
                                child: Text(resourceName,
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: AppTextStyles.bodyMedium
                                        .copyWith(fontWeight: FontWeight.w700)),
                              ),
                              AppBadge(
                                  text: status.label,
                                  backgroundColor: status.bg,
                                  textColor: status.fg),
                            ],
                          ),
                          const SizedBox(height: 2),
                          Text(
                            '${two(start.hour)}:${two(start.minute)} - '
                            '${two(end.hour)}:${two(end.minute)} · ${booking.freelancerPhone}',
                            style: AppTextStyles.caption
                                .copyWith(color: colors.textSecondary),
                          ),
                          Text(
                              '${(booking.hourlyPriceMinor / 100).toStringAsFixed(0)} ر.س / ساعة',
                              style: AppTextStyles.caption
                                  .copyWith(color: colors.textMuted)),
                        ],
                      ),
                    ),
                    if (!cancelled) ...[
                      const SizedBox(width: AppSpacing.sm),
                      CapabilityGate(
                        requires: const ['coworking.cancel_booking'],
                        child: KbAnchor(
                          id: 'coworking.bookings_tab.cancel',
                          child: IconButton(
                            tooltip: 'إلغاء الحجز',
                            onPressed: cancelling ? null : onCancel,
                            icon: cancelling
                                ? const SizedBox(
                                    width: 18,
                                    height: 18,
                                    child: CircularProgressIndicator(
                                        strokeWidth: 2))
                                : const Icon(Icons.close_rounded,
                                    color: AppColors.danger, size: 20),
                          ),
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

class _ResourceThumb extends StatelessWidget {
  const _ResourceThumb({required this.resource});
  final CoworkingResource resource;

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    return Container(
      width: 48,
      height: 48,
      decoration: BoxDecoration(
        color: colors.surfaceAlt,
        borderRadius: BorderRadius.circular(AppRadius.sm),
      ),
      child: resource.hasImage
          ? ClipRRect(
              borderRadius: BorderRadius.circular(AppRadius.sm),
              // Real photo bytes are fetched lazily inside the edit sheet only — the list card
              // shows the placeholder icon, never a per-row network call the sheet-height gate's
              // own "no unbounded content" reasoning would otherwise flag on a busy list.
              child:
                  Icon(Icons.photo_rounded, color: colors.textMuted, size: 22),
            )
          : Icon(Icons.chair_alt_rounded, color: colors.textMuted, size: 22),
    );
  }
}
