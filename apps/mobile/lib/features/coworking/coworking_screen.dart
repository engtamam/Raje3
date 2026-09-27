import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

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
/// mobile screen at all — it is a plain shared web link, spec §4). Two tabs, same
/// `SegmentedFilter` idiom `points_screen.dart` already uses:
///
/// «الموارد» — branch-scoped automatically (this app's own [BranchProvider]/branch-chip
/// convention), photo-first resource cards, a quick active/paused toggle, and a tap that opens
/// the full edit/availability/photo sheet.
///
/// «طلبات الانضمام» — DELIBERATELY carries NO branch filter at all, mirroring
/// `core/joins.py`'s own module doc: the gate is per-shop, never per-chair.
///
/// Bookings are reached from a resource card's own «الحجوزات» button (a sheet), never a third
/// tab — same pattern `booking_details_sheet.dart` already establishes for this app.
///
/// THE SHOP-WIDE PAUSE SWITCH sits in the hero, above both tabs and outside any branch context —
/// `core/models.py`'s own module doc is explicit that pausing is a single, shop-wide switch, and
/// putting it inside a branch-scoped tab would misstate what it actually does.
class CoworkingScreen extends StatefulWidget {
  const CoworkingScreen({super.key});

  @override
  State<CoworkingScreen> createState() => _CoworkingScreenState();
}

enum _Tab { resources, joins }

class _CoworkingScreenState extends State<CoworkingScreen> {
  late final CoworkingService _service;

  List<CoworkingResource>? _resources;
  bool _resourcesFailed = false;
  List<CoworkingJoin>? _joins;
  bool _joinsFailed = false;
  bool? _paused;
  bool _pauseBusy = false;
  _Tab _tab = _Tab.resources;

  @override
  void initState() {
    super.initState();
    _service = CoworkingService(apiClient: context.read<AuthProvider>().apiClient);
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _resources = null;
      _resourcesFailed = false;
      _joins = null;
      _joinsFailed = false;
    });
    final results = await Future.wait([
      _service.listResources(),
      _service.listJoins(),
      _service.isPaused(),
    ]);
    if (!mounted) return;
    setState(() {
      _resources = results[0] as List<CoworkingResource>?;
      _resourcesFailed = _resources == null;
      _joins = results[1] as List<CoworkingJoin>?;
      _joinsFailed = _joins == null;
      _paused = results[2] as bool?;
    });
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
      builder: (_) => ResourceSheet(service: _service, branches: branchProvider.branches),
    );
    if (created == true && mounted) _load();
  }

  Future<void> _openEditSheet(CoworkingResource r) async {
    final branchProvider = context.read<BranchProvider>();
    final changed = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => ResourceSheet(service: _service, branches: branchProvider.branches, existing: r),
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
    final canManage = catalog.hasAll(['coworking.manage']);
    final branchProvider = context.watch<BranchProvider>();

    // The list is already branch-scoped server-side; a resource with `branch_id == ""` is
    // ALWAYS visible too (unassigned rows stay shared, same rule the backend itself documents),
    // so the mobile-side filter mirrors that exactly rather than a plain equality check.
    final selectedBranchId = branchProvider.selected?.id;
    final visibleResources = (_resources ?? const [])
        .where((r) => !branchProvider.hasChoice || selectedBranchId == null || r.branchId.isEmpty || r.branchId == selectedBranchId)
        .toList();

    return KbAnchor(
      id: 'coworking',
      child: Scaffold(
        backgroundColor: AppColors.surface0,
        floatingActionButton: CapabilityGate(
          requires: const ['coworking.manage'],
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
                padding: const EdgeInsets.fromLTRB(AppSpacing.md, AppSpacing.sm, AppSpacing.md, AppSpacing.sm),
                sliver: SliverToBoxAdapter(
                  child: KbAnchor(
                    id: 'coworking.main_tabs',
                    child: SegmentedFilter<_Tab>(
                      value: _tab,
                      onChanged: (v) => setState(() => _tab = v),
                      options: const [
                        SegmentedFilterOption(value: _Tab.resources, label: 'الموارد'),
                        SegmentedFilterOption(value: _Tab.joins, label: 'طلبات الانضمام'),
                      ],
                    ),
                  ),
                ),
              ),
              if (_tab == _Tab.resources)
                ..._resourcesSlivers(visibleResources, canManage)
              else
                ..._joinsSlivers(canManage),
            ],
          ),
        ),
      ),
    );
  }

  List<Widget> _resourcesSlivers(List<CoworkingResource> visible, bool canManage) {
    if (_resources == null) {
      return [
        const SliverPadding(
            padding: EdgeInsets.all(AppSpacing.xl), sliver: SliverToBoxAdapter(child: AppLoadingIndicator())),
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
            child: EmptyState(icon: Icons.meeting_room_outlined, title: 'لا يوجد موارد بعد'),
          ),
        ),
      ];
    }
    return [
      SliverPadding(
        padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.xxl),
        sliver: SliverList.separated(
          itemCount: visible.length,
          separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
          itemBuilder: (context, i) => _ResourceCard(
            resource: visible[i],
            canManage: canManage,
            onTap: canManage ? () => _openEditSheet(visible[i]) : null,
            onToggleActive: canManage ? () => _quickToggleActive(visible[i]) : null,
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
            padding: EdgeInsets.all(AppSpacing.xl), sliver: SliverToBoxAdapter(child: AppLoadingIndicator())),
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
            child: EmptyState(icon: Icons.how_to_reg_outlined, title: 'لا يوجد طلبات انضمام'),
          ),
        ),
      ];
    }
    final sorted = [..._joins!]..sort((a, b) => b.createdAt.compareTo(a.createdAt));
    return [
      SliverPadding(
        padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.xxl),
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

  Future<void> _actOnJoin(CoworkingJoin j, Future<bool> Function(String) action) async {
    final ok = await action(j.phone);
    if (ok && mounted) _load();
  }
}

/// The hero — carries only the shop-wide pause switch, deliberately with no branch chip inside
/// it (see this file's own header doc on why pause is never branch-scoped).
class _CoworkingHero extends StatelessWidget {
  const _CoworkingHero({required this.paused, required this.busy, required this.canManage, required this.onChanged});
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
              Row(
                children: [
                  Container(
                    width: 40,
                    height: 40,
                    decoration: const BoxDecoration(color: Colors.white24, shape: BoxShape.circle),
                    child: const Icon(Icons.meeting_room_rounded, color: Colors.white, size: 20),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  const Text('الاستضافة المهنية',
                      style: TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.w800)),
                ],
              ),
              const SizedBox(height: AppSpacing.md),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.sm),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(AppRadius.card),
                ),
                child: Row(
                  children: [
                    Icon(isPaused ? Icons.pause_circle_rounded : Icons.play_circle_rounded,
                        color: Colors.white, size: 20),
                    const SizedBox(width: AppSpacing.sm),
                    Expanded(
                      child: Text(
                        isPaused ? 'إيقاف استقبال حجوزات جديدة — مفعّل' : 'استقبال حجوزات جديدة يعمل',
                        style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 13),
                      ),
                    ),
                    if (canManage)
                      KbAnchor(
                        id: 'coworking.pause_switch',
                        child: paused == null
                            ? const SizedBox(
                                width: 20, height: 20,
                                child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                            : IgnorePointer(
                                ignoring: busy,
                                child: Switch(value: isPaused, onChanged: onChanged, activeThumbColor: Colors.white),
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
              border: Border.all(color: colors.borderSubtle),
              boxShadow: dark ? AppShadows.darkCard : AppShadows.card,
            ),
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
                              style: AppTextStyles.bodyMedium.copyWith(fontWeight: FontWeight.w700)),
                          if (resource.description.isNotEmpty)
                            Text(resource.description,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
                          Text('${(resource.hourlyPriceMinor / 100).toStringAsFixed(0)} ر.س / ساعة',
                              style: AppTextStyles.caption.copyWith(color: colors.textSecondary)),
                        ],
                      ),
                    ),
                    AppBadge(
                      text: active ? 'نشط' : 'متوقف',
                      backgroundColor: active ? AppColors.successSoft : colors.surfaceAlt,
                      textColor: active ? AppColors.successOnSoft : colors.textMuted,
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
                          requires: const ['coworking.manage'],
                          child: SecondaryButton(
                            text: active ? 'إيقاف' : 'تفعيل',
                            icon: active ? Icons.pause_circle_outline : Icons.play_circle_outline,
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
              child: Icon(Icons.photo_rounded, color: colors.textMuted, size: 22),
            )
          : Icon(Icons.chair_alt_rounded, color: colors.textMuted, size: 22),
    );
  }
}
