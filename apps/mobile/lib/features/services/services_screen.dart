import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import 'package:raje3_mobile/core/providers/auth_provider.dart';
import 'package:raje3_mobile/core/providers/nav_provider.dart';
import 'package:raje3_mobile/core/services/auth_service.dart' show BranchTeamMember;
import 'package:raje3_mobile/core/services/services_catalogue_service.dart';
import 'package:raje3_mobile/core/utils/formatters.dart';
import 'package:raje3_mobile/l10n/app_localizations.dart';
import 'package:raje3_mobile/models/service_model.dart';
import 'package:raje3_mobile/theme/app_theme.dart';
import 'package:raje3_mobile/widgets/app_widgets.dart';
import 'package:raje3_mobile/widgets/brand_loading_indicator.dart';
import 'package:raje3_mobile/widgets/capability_gate.dart';
import 'package:raje3_mobile/widgets/kb_anchor.dart';
import 'package:raje3_mobile/widgets/rj_sheen.dart';

import 'bulk_import_sheet.dart';
import 'packages_tab.dart';
import 'procedures_tab.dart';

/// «خدماتي ومنتجاتي» — mobile mirror of apps/console/src/screens/Services.tsx's own DATA
/// contract for the service catalogue itself: add, edit, stop/reactivate, staff assignment,
/// protocol checklist, photo, groups, the reminders/loyalty settings TREE (follow-up days,
/// per-service points, group membership, the general default card), «الباقات», and a CSV import.
/// Built with a fresh mobile-native structure — a hero, a page-level segmented switch
/// (خدمات/باقات), two real tabs (نشطة/متوقفة), colored group chips, a floating add button,
/// editable cards — never the console's own dense management table.
///
/// SCOPE, EXPLICIT: a real .xlsx reader is a separate, heavier dependency this pass does not
/// add — the import sheet reads CSV only, the working half of "CSV/Excel", not a stand-in for
/// both (see bulk_import_sheet.dart's own header).
class ServicesScreen extends StatefulWidget {
  const ServicesScreen({super.key});

  @override
  State<ServicesScreen> createState() => _ServicesScreenState();
}

enum _Tab { active, stopped }
enum _PageTab { services, packages, procedures }

class _ServicesScreenState extends State<ServicesScreen> {
  late final ServicesCatalogueService _service;

  List<ServiceItem>? _services;
  bool _failed = false;
  _Tab _tab = _Tab.active;
  _PageTab _pageTab = _PageTab.services;
  String? _groupFilter; // null = all groups
  final _searchController = TextEditingController();

  ReminderSettingsTree? _reminderTree;
  EarnSettingsTree? _earnTree;
  GroupSuggestion? _suggestion;

  @override
  void initState() {
    super.initState();
    _service = ServicesCatalogueService(apiClient: context.read<AuthProvider>().apiClient);
    _load();
    _loadTrees();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _services = null;
      _failed = false;
    });
    final result = await _service.list();
    if (!mounted) return;
    setState(() {
      _services = result ?? [];
      _failed = result == null;
    });
  }

  Future<void> _loadTrees() async {
    final results = await Future.wait([
      _service.reminderSettings(),
      _service.earnSettings(),
      _service.suggestReminderGroup(),
    ]);
    if (!mounted) return;
    setState(() {
      _reminderTree = results[0] as ReminderSettingsTree?;
      _earnTree = results[1] as EarnSettingsTree?;
      _suggestion = results[2] as GroupSuggestion?;
    });
  }

  List<String> get _groupNames {
    final tree = _reminderTree;
    if (tree == null) return const [];
    final names = tree.serviceGroup.values.toSet().toList()..sort();
    return names;
  }

  Future<void> _acceptSuggestion() async {
    final suggestion = _suggestion;
    if (suggestion == null) return;
    final s = S.of(context)!;
    final controller = TextEditingController();
    final name = await showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(s.servicesGroupThem),
        content: KbAnchor(
          id: 'services.group_name_field',
          child: TextField(
          controller: controller,
          autofocus: true,
          decoration: InputDecoration(hintText: s.servicesGroupNameHint),
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(), child: Text(s.mobileRequestsRejectCancel)),
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(controller.text.trim()), child: Text(s.servicesSave)),
        ],
      ),
    );
    if (name == null || name.isEmpty) return;
    final field = suggestion.field;
    final ok = await _service.setReminderGroup(
      name,
      serviceIds: suggestion.serviceIds,
      intervalDays: field == 'interval_days' ? suggestion.value.round() : null,
      followUpDays: field == 'follow_up_days' ? suggestion.value.round() : null,
    );
    if (!mounted) return;
    if (ok) {
      setState(() => _suggestion = null);
      _loadTrees();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(s.servicesActionFailed)));
    }
  }

  Future<void> _openGeneralSettings() async {
    final changed = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _GeneralSettingsSheet(
        service: _service,
        reminderTree: _reminderTree,
        earnTree: _earnTree,
      ),
    );
    if (changed == true) _loadTrees();
  }

  Future<void> _openImport() async {
    final done = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => BulkImportSheet(service: _service),
    );
    if (done == true) _load();
  }

  Future<void> _openAdd() async {
    final created = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _ServiceFormSheet(
        service: _service,
        reminderTree: _reminderTree,
        earnTree: _earnTree,
        groupNames: _groupNames,
      ),
    );
    if (created == true) {
      _load();
      _loadTrees();
    }
  }

  Future<void> _openEdit(ServiceItem item) async {
    final saved = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _ServiceFormSheet(
        service: _service,
        existing: item,
        reminderTree: _reminderTree,
        earnTree: _earnTree,
        groupNames: _groupNames,
      ),
    );
    if (saved == true) {
      _load();
      _loadTrees();
    }
  }

  Future<void> _toggleActive(ServiceItem item) async {
    final s = S.of(context)!;
    final willStop = item.active;
    if (willStop) {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: Text(s.servicesStopTitle),
          content: Text(s.servicesStopWarning(item.name)),
          actions: [
            TextButton(onPressed: () => Navigator.of(dialogContext).pop(false), child: Text(s.mobileRequestsRejectCancel)),
            TextButton(onPressed: () => Navigator.of(dialogContext).pop(true),
                child: Text(s.servicesStopConfirm, style: const TextStyle(color: AppColors.danger))),
          ],
        ),
      );
      if (confirmed != true) return;
    }
    final updated = await _service.update(item.id, active: !willStop);
    if (!mounted) return;
    if (updated == null) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(s.servicesActionFailed)));
      return;
    }
    setState(() {
      _services = _services!.map((x) => x.id == item.id ? updated : x).toList();
    });
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final dark = context.isDark;
    final activeCount = (_services ?? const []).where((x) => x.active).length;
    final query = _searchController.text.trim();

    final filtered = (_services ?? const [])
        .where((x) => _tab == _Tab.active ? x.active : !x.active)
        .where((x) => query.isEmpty || x.name.contains(query))
        .where((x) => _groupFilter == null || _reminderTree?.serviceGroup[x.id] == _groupFilter)
        .toList();

    return KbAnchor(
      id: 'services',
      child: Scaffold(
        backgroundColor: AppColors.surface0,
        floatingActionButton: _pageTab == _PageTab.services
            ? KbAnchor(
                id: 'services.add_button',
                child: FloatingActionButton.extended(
                  onPressed: _openAdd,
                  icon: const Icon(Icons.add_rounded),
                  label: Text(s.servicesAddOpen),
                ),
              )
            : null,
        body: Column(
          children: [
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
                            shape: BoxShape.circle, color: Colors.white.withValues(alpha: 0.08)),
                      ),
                    ),
                    SafeArea(
                      bottom: false,
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(
                            AppSpacing.lg, AppSpacing.md, AppSpacing.lg, AppSpacing.lg),
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
                                      Text(s.servicesTitle,
                                          style: AppTextStyles.displaySmall
                                              .copyWith(color: AppColors.accentContrast)),
                                      const SizedBox(height: 2),
                                      Text(
                                        _services != null
                                            ? s.servicesActiveCount(activeCount)
                                            : s.customersLoyaltyLoading,
                                        style: AppTextStyles.bodySmall.copyWith(
                                            color: AppColors.accentContrast.withValues(alpha: 0.85)),
                                      ),
                                    ],
                                  ),
                                ),
                                KbAnchor(
                                  id: 'services.import_button',
                                  child: _GlassRoundButton(icon: Icons.upload_file_rounded, onTap: _openImport),
                                ),
                                const SizedBox(width: AppSpacing.xs),
                                KbAnchor(
                                  id: 'services.general_settings_button',
                                  child: _GlassRoundButton(icon: Icons.tune_rounded, onTap: _openGeneralSettings),
                                ),
                              ],
                            ),
                            const SizedBox(height: AppSpacing.md),
                            KbAnchor(
                              id: 'services.page_tabs',
                              child: Container(
                                padding: const EdgeInsets.all(3),
                                decoration: BoxDecoration(
                                  color: Colors.white.withValues(alpha: 0.14),
                                  borderRadius: BorderRadius.circular(AppRadius.pill),
                                ),
                                child: Row(
                                  children: [
                                    Expanded(
                                      child: _PageTabButton(
                                        label: s.servicesPageTabServices,
                                        selected: _pageTab == _PageTab.services,
                                        onTap: () => setState(() => _pageTab = _PageTab.services),
                                      ),
                                    ),
                                    Expanded(
                                      child: _PageTabButton(
                                        label: s.servicesPageTabPackages,
                                        selected: _pageTab == _PageTab.packages,
                                        onTap: () => setState(() => _pageTab = _PageTab.packages),
                                      ),
                                    ),
                                    Expanded(
                                      child: _PageTabButton(
                                        label: s.proceduresTitle,
                                        selected: _pageTab == _PageTab.procedures,
                                        onTap: () => setState(() => _pageTab = _PageTab.procedures),
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            Expanded(
              child: _pageTab == _PageTab.packages
                  ? PackagesTab(
                      service: _service,
                      services: (_services ?? const []).where((x) => x.active).toList(),
                    )
                  : _pageTab == _PageTab.procedures
                      ? ProceduresTab(
                          service: _service,
                          services: _services ?? const [],
                          onChanged: _load,
                        )
                  : RefreshIndicator(
                      onRefresh: _load,
                      child: CustomScrollView(
                        slivers: [
                          SliverPadding(
                padding: const EdgeInsets.fromLTRB(AppSpacing.md, AppSpacing.sm, AppSpacing.md, AppSpacing.sm),
                sliver: SliverToBoxAdapter(
                  child: Column(
                    children: [
                      KbAnchor(
                        id: 'services.search_field',
                        child: AppTextField(
                          controller: _searchController,
                          hintText: s.servicesSearchHint,
                          prefixIcon: Icons.search_rounded,
                          onChanged: (_) => setState(() {}),
                        ),
                      ),
                      const SizedBox(height: AppSpacing.sm),
                      SegmentedFilter<_Tab>(
                        value: _tab,
                        onChanged: (v) => setState(() => _tab = v),
                        options: [
                          SegmentedFilterOption(
                              value: _Tab.active,
                              label: s.servicesTabActive,
                              badge: (_services ?? const []).where((x) => x.active).length),
                          SegmentedFilterOption(
                              value: _Tab.stopped,
                              label: s.servicesTabStopped,
                              badge: (_services ?? const []).where((x) => !x.active).length),
                        ],
                      ),
                      if (_groupNames.isNotEmpty) ...[
                        const SizedBox(height: AppSpacing.sm),
                        _GroupChipRow(
                          groups: _groupNames,
                          selected: _groupFilter,
                          onChanged: (g) => setState(() => _groupFilter = g),
                        ),
                      ],
                      if (_suggestion != null) ...[
                        const SizedBox(height: AppSpacing.sm),
                        _SuggestionBanner(
                          count: _suggestion!.serviceIds.length,
                          onAccept: _acceptSuggestion,
                          onDismiss: () => setState(() => _suggestion = null),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
              if (_services == null)
                const SliverFillRemaining(hasScrollBody: false, child: BrandLoadingIndicator())
              else if (_failed)
                SliverFillRemaining(
                  hasScrollBody: false,
                  child: EmptyState(
                    icon: Icons.cloud_off_rounded,
                    title: s.servicesLoadFailedTitle,
                    actionText: s.mobileRequestsRetry,
                    onAction: _load,
                  ),
                )
              else if (filtered.isEmpty)
                SliverFillRemaining(
                  hasScrollBody: false,
                  child: EmptyState(
                    icon: Icons.build_outlined,
                    title: _tab == _Tab.active ? s.servicesEmptyActive : s.servicesEmptyStopped,
                  ),
                )
              else
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.xxl),
                  // BACK TO A UNIFORM `SliverGrid`, not the two independent masonry columns this
                  // briefly became — masonry fixed the earlier dead-space complaint but broke a
                  // different, more visible thing: the active switch landed at a different height
                  // on every card, so a row of two cards never lined up (owner screenshot,
                  // 2026-09-23, "بطاقة أطول من بطاقة"). `_ServiceCard`'s own content is now built
                  // to a FIXED shape instead (a description line and a chip zone that always
                  // reserve the same height whether or not this particular service has either), so
                  // a uniform grid has no dead space to leave AND every switch sits at the same y.
                  sliver: SliverGrid(
                    gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: 2,
                      mainAxisSpacing: AppSpacing.sm,
                      crossAxisSpacing: AppSpacing.sm,
                      childAspectRatio: 0.68,
                    ),
                    delegate: SliverChildBuilderDelegate(
                      (context, i) {
                        final groupName = _reminderTree?.serviceGroup[filtered[i].id];
                        final groupIndex = groupName == null ? -1 : _groupNames.indexOf(groupName);
                        return _ServiceCard(
                          item: filtered[i],
                          groupName: groupName,
                          groupColor: groupIndex >= 0 ? _groupPalette[groupIndex % _groupPalette.length] : null,
                          followUpDays: _reminderTree?.resolve(filtered[i].id).$1.followUpDays,
                          points: _earnTree?.resolve(filtered[i].id).$1,
                          onTap: () => _openEdit(filtered[i]),
                          onToggleActive: () => _toggleActive(filtered[i]),
                        );
                      },
                      childCount: filtered.length,
                    ),
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
}

/// A "movie-poster" card, by explicit owner instruction ("تطبيق أفلام لا تطبيق تجاري"): a
/// full-bleed square image up top (never a thumbnail buried in a title row — that was the old
/// layout, and why photos read as "missing" even when they had uploaded fine) with the name
/// legible directly over it, then a compact facts strip below. Two per row (`SliverGrid` in the
/// parent), so every real field the old single-column row showed still shows — just laid out for
/// a poster instead of a table row.
class _ServiceCard extends StatelessWidget {
  const _ServiceCard({
    required this.item,
    required this.onTap,
    required this.onToggleActive,
    this.groupName,
    this.groupColor,
    this.followUpDays,
    this.points,
  });
  final ServiceItem item;
  final String? groupName;
  final Color? groupColor;
  final int? followUpDays;
  final int? points;
  final VoidCallback onTap;
  final VoidCallback onToggleActive;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final locale = Localizations.localeOf(context).languageCode;
    final colors = context.appColors;
    final dark = context.isDark;

    return KbAnchor(
      id: 'services.service_card',
      // THE WHOLE CARD IS THE PHOTO NOW — owner's own call, 2026-09-23: a card that was a photo
      // on top and a plain white strip underneath read as "a cover glued to a form", not a movie
      // poster. Every field that used to live in that white strip (price, duration, chips,
      // active switch) is now overlaid directly on the image, inside one deep gradient reaching
      // most of the way up — the same "everything printed on the poster itself" idiom an actual
      // film poster uses, not a card ABOUT a poster.
      child: Container(
        decoration: BoxDecoration(
          borderRadius: AppRadius.cardRadius,
          border: Border.all(color: colors.borderSubtle),
          boxShadow: dark ? AppShadows.darkCard : AppShadows.card,
        ),
        clipBehavior: Clip.antiAlias,
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            onTap: onTap,
            child: Stack(
              fit: StackFit.expand,
              children: [
                if (item.hasImage)
                  _ServicePosterImage(serviceId: item.id)
                else
                  _ServicePosterPlaceholder(name: item.name),
                const Positioned.fill(
                  child: DecoratedBox(
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        begin: Alignment.topCenter,
                        end: Alignment.bottomCenter,
                        colors: [Colors.transparent, Color(0xF2000000)],
                        stops: [0.28, 0.85],
                      ),
                    ),
                  ),
                ),
                if (groupName != null && groupName!.isNotEmpty)
                  Positioned.directional(
                    textDirection: Directionality.of(context),
                    top: 8,
                    start: 8,
                    child: _PosterBadge(label: groupName!, color: groupColor ?? colors.textSecondary),
                  ),
                PositionedDirectional(
                  top: 8,
                  end: 8,
                  child: Transform.scale(
                    scale: 0.72,
                    child: CapabilityGate(
                      requires: const ['operations.update_service'],
                      child: Switch(
                        value: item.active,
                        onChanged: (_) => onToggleActive(),
                        activeThumbColor: dark ? AppDarkColors.accent : AppColors.accent,
                      ),
                    ),
                  ),
                ),
                Positioned(
                  left: 10,
                  right: 10,
                  bottom: 8,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(item.name,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: AppTextStyles.bodyMedium
                              .copyWith(color: Colors.white, fontWeight: FontWeight.w800, height: 1.15)),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          const Icon(Icons.payments_outlined, size: 13, color: Colors.white),
                          const SizedBox(width: 4),
                          Expanded(
                            child: Text(
                              item.priceMinor > 0
                                  ? Formatters.formatCurrency(item.priceMinor / 100, locale: locale)
                                  : s.servicesNoPrice,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: AppTextStyles.bodySmall.copyWith(color: Colors.white, fontWeight: FontWeight.w800),
                            ),
                          ),
                          const Icon(Icons.schedule_outlined, size: 13, color: Colors.white70),
                          const SizedBox(width: 3),
                          Text(
                            item.durationMinutes > 0
                                ? s.servicesDurationMinutes(item.durationMinutes)
                                : s.servicesNoDuration,
                            style: AppTextStyles.caption.copyWith(color: Colors.white70),
                          ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      // FIXED-HEIGHT, CLIPPED — same reasoning as before this card became a full
                      // poster: every card must stay the same overall height so a row of cards
                      // lines up, and this is the one zone whose real content varies (a service
                      // with a follow-up badge or points badge is taller than one with neither).
                      SizedBox(
                        height: 44,
                        child: ClipRect(
                          child: Align(
                            alignment: AlignmentDirectional.topStart,
                            child: Wrap(
                              spacing: 6,
                              runSpacing: 6,
                              children: [
                                _InfoChip(
                                  icon: Icons.event_repeat_rounded,
                                  label: item.cycleDays > 0
                                      ? s.servicesCycleDays(item.cycleDays)
                                      : s.servicesNoCycle,
                                ),
                                if (followUpDays != null && followUpDays! > 0)
                                  _InfoChip(icon: Icons.forum_outlined, label: s.servicesFollowUpDays(followUpDays!)),
                                if (points != null && points! > 0)
                                  _InfoChip(icon: Icons.stars_rounded, label: s.servicesPointsPerVisit(points!)),
                              ],
                            ),
                          ),
                        ),
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

/// The group tag, redrawn as a poster badge (frosted pill over the image) instead of the tinted
/// chip the single-column row used — same color-by-position identity as `_GroupChip`.
class _PosterBadge extends StatelessWidget {
  const _PosterBadge({required this.label, required this.color});
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.4),
        borderRadius: BorderRadius.circular(AppRadius.pill),
        border: Border.all(color: color, width: 1),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(width: 6, height: 6, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
          const SizedBox(width: 4),
          Text(label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppTextStyles.caption.copyWith(color: Colors.white, fontWeight: FontWeight.w700)),
        ],
      ),
    );
  }
}

/// The one "empty square" surface for this whole screen — a loading photo, an unfilled photo
/// picker — drawn white-and-bordered-with-sheen instead of a flat grey fill, by explicit owner
/// instruction 2026-09-23: "الرمادي مخرب الابداع ... حتى هو لون بلمعه ولو فاضي خلاص يكون ابيض
/// والحواف فقط تميز انه مربع", same `RjSheen` primitive `branch_detail_screen.dart` already uses
/// for this exact "glossy, never flat" identity.
class _GlossySquare extends StatelessWidget {
  const _GlossySquare({required this.child, this.radius, this.dashed = false});
  final Widget child;
  final BorderRadius? radius;
  final bool dashed;

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final br = radius ?? BorderRadius.circular(AppRadius.sm);
    return RjSheen(
      borderRadius: br,
      child: Container(
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: br,
          border: Border.all(color: colors.borderSubtle, width: dashed ? 1.4 : 1),
        ),
        child: child,
      ),
    );
  }
}

/// A service with no photo yet, still shown as a poster — a soft gradient tinted from the
/// service's own name (so the grid still reads as varied rather than a wall of identical grey
/// tiles) with an initial letter and a camera glyph, never a blank box.
class _ServicePosterPlaceholder extends StatelessWidget {
  const _ServicePosterPlaceholder({required this.name});
  final String name;

  @override
  Widget build(BuildContext context) {
    final hue = (name.isEmpty ? 0 : name.codeUnitAt(0) * 37) % 360;
    final base = HSLColor.fromAHSL(1, hue.toDouble(), 0.42, 0.42).toColor();
    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [base.withValues(alpha: 0.85), base.withValues(alpha: 0.55)],
        ),
      ),
      alignment: Alignment.center,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            name.isEmpty ? S.of(context)!.servicesUnnamedGlyph : name.substring(0, 1),
            style: AppTextStyles.headlineSmall
                .copyWith(color: Colors.white.withValues(alpha: 0.85), fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 4),
          Icon(Icons.add_a_photo_outlined, size: 16, color: Colors.white.withValues(alpha: 0.7)),
        ],
      ),
    );
  }
}

/// The real uploaded photo, drawn full-bleed to fill its poster tile (`BoxFit.cover`, no fixed
/// size — unlike `_ServiceThumbnail`, which stays a small fixed square for the edit sheet's own
/// preview). Fetches lazily and caches only in this widget's own state, same idiom as
/// `_ServiceThumbnail` below.
class _ServicePosterImage extends StatefulWidget {
  const _ServicePosterImage({required this.serviceId});
  final String serviceId;

  @override
  State<_ServicePosterImage> createState() => _ServicePosterImageState();
}

class _ServicePosterImageState extends State<_ServicePosterImage> {
  Uint8List? _bytes;
  bool _failed = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final service = ServicesCatalogueService(apiClient: context.read<AuthProvider>().apiClient);
    final bytes = await service.fetchImage(widget.serviceId);
    if (!mounted) return;
    if (bytes == null) {
      setState(() => _failed = true);
    } else {
      setState(() => _bytes = bytes);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_bytes != null) return Image.memory(_bytes!, fit: BoxFit.cover);
    if (_failed) return const _ServicePosterPlaceholder(name: '');
    return const _GlossySquare(radius: BorderRadius.zero, child: SizedBox.expand());
  }
}

class _GlassRoundButton extends StatelessWidget {
  const _GlassRoundButton({required this.icon, required this.onTap});
  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white.withValues(alpha: 0.18),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(AppRadius.md)),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: SizedBox(width: 44, height: 44, child: Icon(icon, color: Colors.white)),
      ),
    );
  }
}

/// The page-level «خدمات/باقات» switch — a pill segmented control worn over the gradient hero,
/// never the console's own URL-param tab (`?tab=packages`), matching this screen's own idiom of
/// controls surfaced inside the hero rather than a bare tab bar under it.
class _PageTabButton extends StatelessWidget {
  const _PageTabButton({required this.label, required this.selected, required this.onTap});
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: selected ? Colors.white.withValues(alpha: 0.22) : Colors.transparent,
      borderRadius: BorderRadius.circular(AppRadius.pill),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppRadius.pill),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Text(label,
              textAlign: TextAlign.center,
              style: AppTextStyles.bodySmall.copyWith(
                  color: Colors.white, fontWeight: selected ? FontWeight.w800 : FontWeight.w500)),
        ),
      ),
    );
  }
}

/// The colored group navigation — mobile's own take on Services.tsx's own sidebar rail (a
/// dropdown/rail there; a horizontal scroll of colored pills here, matching this app's own
/// filter-chip idiom everywhere else). Colors cycle a fixed categorical palette by position —
/// never content-derived, so a group's color never collides with a semantic tone.
const List<Color> _groupPalette = [
  Color(0xFF6D5FE8),
  Color(0xFF0E8A64),
  Color(0xFFC2622B),
  Color(0xFF2F5F8F),
  Color(0xFFB7412F),
  Color(0xFFA0680A),
];

class _GroupChipRow extends StatelessWidget {
  const _GroupChipRow({required this.groups, required this.selected, required this.onChanged});
  final List<String> groups;
  final String? selected;
  final ValueChanged<String?> onChanged;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          _GroupChip(label: s.servicesAllGroups, color: context.appColors.textSecondary, selected: selected == null, onTap: () => onChanged(null)),
          const SizedBox(width: 6),
          for (var i = 0; i < groups.length; i++) ...[
            _GroupChip(
              label: groups[i],
              color: _groupPalette[i % _groupPalette.length],
              selected: selected == groups[i],
              onTap: () => onChanged(groups[i]),
            ),
            const SizedBox(width: 6),
          ],
        ],
      ),
    );
  }
}

class _GroupChip extends StatelessWidget {
  const _GroupChip({required this.label, required this.color, required this.selected, required this.onTap});
  final String label;
  final Color color;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: selected ? color.withValues(alpha: 0.16) : Colors.white.withValues(alpha: 0.14),
      borderRadius: BorderRadius.circular(AppRadius.pill),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppRadius.pill),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(AppRadius.pill),
            border: Border.all(color: selected ? color : Colors.transparent),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(width: 7, height: 7, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
              const SizedBox(width: 6),
              Text(label,
                  style: AppTextStyles.caption.copyWith(
                      color: selected ? color : context.appColors.textSecondary,
                      fontWeight: selected ? FontWeight.w700 : FontWeight.w500)),
            ],
          ),
        ),
      ),
    );
  }
}

/// The one proposal the engine ever makes on its own — several services already share the same
/// value on one field — and it only ever proposes; nothing changes until the owner agrees.
class _SuggestionBanner extends StatelessWidget {
  const _SuggestionBanner({required this.count, required this.onAccept, required this.onDismiss});
  final int count;
  final VoidCallback onAccept;
  final VoidCallback onDismiss;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    return KbAnchor(
      id: 'services.suggestion_banner',
      child: Container(
      padding: const EdgeInsets.all(AppSpacing.sm),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.14),
        borderRadius: AppRadius.standardRadius,
      ),
      child: Row(
        children: [
          const Icon(Icons.auto_awesome_rounded, size: 16, color: Colors.white),
          const SizedBox(width: 8),
          Expanded(
            child: Text(s.servicesSuggestionText(count),
                style: AppTextStyles.caption.copyWith(color: Colors.white)),
          ),
          TextButton(
            onPressed: onAccept,
            style: TextButton.styleFrom(foregroundColor: Colors.white),
            child: Text(s.servicesGroupThem, style: const TextStyle(fontWeight: FontWeight.w800)),
          ),
          IconButton(
            onPressed: onDismiss,
            icon: const Icon(Icons.close_rounded, size: 16, color: Colors.white70),
            visualDensity: VisualDensity.compact,
          ),
        ],
      ),
      ),
    );
  }
}

/// A frosted-glass chip, white-on-image — the whole card is a poster now (no separate white
/// content strip underneath), so every chip lives on top of the photo itself and needs to read
/// there rather than on a plain surface.
class _InfoChip extends StatelessWidget {
  const _InfoChip({required this.icon, required this.label});
  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.16),
        borderRadius: BorderRadius.circular(AppRadius.sm),
        border: Border.all(color: Colors.white.withValues(alpha: 0.22)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 11, color: Colors.white),
          const SizedBox(width: 4),
          Text(label, style: AppTextStyles.caption.copyWith(color: Colors.white, fontSize: 10.5)),
        ],
      ),
    );
  }
}

/// «الإعداد العام» — the default every service that has no override follows. A line, opened from
/// the hero's own tune icon, never a card sitting permanently on the main list (Services.tsx's
/// own note: as a bordered box it read like a field he had to fill).
class _GeneralSettingsSheet extends StatefulWidget {
  const _GeneralSettingsSheet({required this.service, required this.reminderTree, required this.earnTree});
  final ServicesCatalogueService service;
  final ReminderSettingsTree? reminderTree;
  final EarnSettingsTree? earnTree;

  @override
  State<_GeneralSettingsSheet> createState() => _GeneralSettingsSheetState();
}

class _GeneralSettingsSheetState extends State<_GeneralSettingsSheet> {
  late final _followUpController =
      TextEditingController(text: (widget.reminderTree?.general.followUpDays ?? 0) > 0
          ? widget.reminderTree!.general.followUpDays.toString()
          : '');
  late final _pointsController = TextEditingController(
      text: (widget.earnTree?.generalPoints ?? 0) > 0 ? widget.earnTree!.generalPoints.toString() : '');
  bool _saving = false;
  String? _error;

  @override
  void dispose() {
    _followUpController.dispose();
    _pointsController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final s = S.of(context)!;
    setState(() {
      _saving = true;
      _error = null;
    });
    final followUp = int.tryParse(_followUpController.text.trim());
    final points = int.tryParse(_pointsController.text.trim());
    var ok = true;
    if (followUp != null) {
      ok &= await widget.service.setGeneralReminderSettings(followUpDays: followUp);
    }
    if (points != null) {
      ok &= await widget.service.setGeneralPoints(points);
    }
    if (!mounted) return;
    if (!ok) {
      setState(() {
        _saving = false;
        _error = s.servicesActionFailed;
      });
      return;
    }
    Navigator.of(context).pop(true);
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
            Text(s.servicesGeneralSettingsTitle, style: AppTextStyles.headlineSmall),
            const SizedBox(height: 4),
            Text(s.servicesGeneralSettingsHint,
                style: AppTextStyles.bodySmall.copyWith(color: AppColors.textMuted)),
            const SizedBox(height: AppSpacing.lg),
            KbAnchor(
              id: 'services.general_settings_fields',
              child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
            AppTextField(
              labelText: s.servicesFollowUpLabel,
              controller: _followUpController,
              keyboardType: TextInputType.number,
            ),
            const SizedBox(height: AppSpacing.md),
            AppTextField(
              labelText: s.servicesPointsLabel,
              controller: _pointsController,
              keyboardType: TextInputType.number,
            ),
              ],
              ),
            ),
            if (_error != null) ...[
              const SizedBox(height: AppSpacing.md),
              AppAlert(type: AlertType.error, message: _error!),
            ],
            const SizedBox(height: AppSpacing.lg),
            CapabilityGate(
              requires: const ['operations.manage_services'],
              child: PrimaryButton(
                text: _saving ? s.servicesSaving : s.servicesSave,
                isLoading: _saving,
                onPressed: _saving ? null : _submit,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ServiceFormSheet extends StatefulWidget {
  const _ServiceFormSheet({
    required this.service,
    this.existing,
    this.reminderTree,
    this.earnTree,
    this.groupNames = const [],
  });
  final ServicesCatalogueService service;
  final ServiceItem? existing;
  final ReminderSettingsTree? reminderTree;
  final EarnSettingsTree? earnTree;
  final List<String> groupNames;

  @override
  State<_ServiceFormSheet> createState() => _ServiceFormSheetState();
}

class _ServiceFormSheetState extends State<_ServiceFormSheet> {
  late final _nameController =
      TextEditingController(text: widget.existing?.name ?? '');
  late final _priceController = TextEditingController(
      text: (widget.existing?.priceMinor ?? 0) > 0
          ? (widget.existing!.priceMinor / 100).toStringAsFixed(2)
          : '');
  late final _durationController = TextEditingController(
      text: (widget.existing?.durationMinutes ?? 0) > 0
          ? widget.existing!.durationMinutes.toString()
          : '');
  late final _cycleController = TextEditingController(
      text: (widget.existing?.cycleDays ?? 0) > 0 ? widget.existing!.cycleDays.toString() : '');
  late final _descriptionController =
      TextEditingController(text: widget.existing?.description ?? '');
  bool _saving = false;
  String? _error;

  late String _assignmentMode = widget.existing?.assignmentMode ?? 'auto';
  final Set<String> _eligibleStaffIds = {};
  List<BranchTeamMember>? _staff;

  late List<String> _selectedStepIds = [...(widget.existing?.procedureStepIds ?? const [])];
  List<ProcedureStep>? _steps;

  Uint8List? _newPhotoBytes;
  String? _newPhotoContentType;
  bool _uploadingPhoto = false;
  bool _pickingPhoto = false;
  bool _hasImage = false;

  // ── the reminders/loyalty settings tree, for THIS service only — Services.tsx's own
  // "two stores behind one form" doctrine: `cycle_days` above lives on the Service row itself,
  // these three live in reminders'/loyalty's own settings tree and are written as separate calls.
  late final (ReminderSetting, bool) _reminderResolved = widget.existing != null
      ? (widget.reminderTree?.resolve(widget.existing!.id) ?? (const ReminderSetting(), false))
      : (const ReminderSetting(), false);
  late final (int, bool) _earnResolved = widget.existing != null
      ? (widget.earnTree?.resolve(widget.existing!.id) ?? (0, false))
      : (0, false);
  late bool _followUpOwn = _reminderResolved.$2 && _reminderResolved.$1.followUpDays != null;
  late final _followUpController = TextEditingController(
      text: (_reminderResolved.$1.followUpDays ?? 0) > 0 ? _reminderResolved.$1.followUpDays.toString() : '');
  late bool _pointsOwn = _earnResolved.$2;
  late final _pointsController =
      TextEditingController(text: _earnResolved.$1 > 0 ? _earnResolved.$1.toString() : '');
  late String? _group = widget.existing != null ? widget.reminderTree?.serviceGroup[widget.existing!.id] : null;
  late final _newGroupController = TextEditingController();
  bool _addingNewGroup = false;

  @override
  void initState() {
    super.initState();
    _hasImage = widget.existing?.hasImage ?? false;
    _eligibleStaffIds.addAll(widget.existing?.eligibleStaffIds ?? const []);
    _loadStaff();
    _loadSteps();
  }

  Future<void> _loadStaff() async {
    final result = await context.read<AuthProvider>().fetchOperators();
    if (mounted) setState(() => _staff = result ?? const []);
  }

  Future<void> _loadSteps() async {
    final result = await widget.service.procedureSteps();
    if (mounted) setState(() => _steps = result ?? const []);
  }

  @override
  void dispose() {
    _nameController.dispose();
    _priceController.dispose();
    _durationController.dispose();
    _cycleController.dispose();
    _descriptionController.dispose();
    _followUpController.dispose();
    _pointsController.dispose();
    _newGroupController.dispose();
    super.dispose();
  }

  Future<void> _pickPhoto() async {
    final s = S.of(context)!;
    setState(() => _pickingPhoto = true);
    try {
      final picker = ImagePicker();
      final file = await picker.pickImage(source: ImageSource.gallery, maxWidth: 1080, imageQuality: 85);
      if (file == null) return;
      final bytes = await file.readAsBytes();
      if (!mounted) return;
      setState(() {
        _newPhotoBytes = bytes;
        _newPhotoContentType = file.mimeType ?? 'image/jpeg';
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _error = s.servicesPhotoPickFailed);
    } finally {
      if (mounted) setState(() => _pickingPhoto = false);
    }
  }

  Future<void> _createStep() async {
    final s = S.of(context)!;
    final controller = TextEditingController();
    final text = await showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(s.servicesStepAddTitle),
        content: KbAnchor(
          id: 'services.step_add_field',
          child: TextField(controller: controller, autofocus: true, maxLines: 2),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(), child: Text(s.mobileRequestsRejectCancel)),
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(controller.text.trim()), child: Text(s.servicesSave)),
        ],
      ),
    );
    if (text == null || text.isEmpty) return;
    final created = await widget.service.createProcedureStep(text: text);
    if (created == null || !mounted) return;
    setState(() {
      _steps = [...(_steps ?? const []), created];
      _selectedStepIds = [..._selectedStepIds, created.id];
    });
  }

  /// Long-press on a checklist chip: edit its shared text/severity, or retire it — the two real
  /// acts `ProcedureStepsTab.tsx` offers, missing from mobile's own first pass at this section.
  Future<void> _editStep(ProcedureStep step) async {
    final s = S.of(context)!;
    final controller = TextEditingController(text: step.text);
    var critical = step.severity == 'critical';
    final action = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (sheetContext) => StatefulBuilder(
        builder: (sheetContext, setSheetState) => Padding(
          padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(sheetContext).bottom),
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
                Text(s.servicesStepEditTitle, style: AppTextStyles.headlineSmall),
                const SizedBox(height: AppSpacing.lg),
                KbAnchor(
                  id: 'services.step_edit_field',
                  child: TextField(controller: controller, maxLines: 2, autofocus: true),
                ),
                const SizedBox(height: AppSpacing.md),
                Material(
                  color: Colors.transparent,
                  child: SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text(s.servicesStepCriticalLabel),
                    value: critical,
                    onChanged: (v) => setSheetState(() => critical = v),
                  ),
                ),
                const SizedBox(height: AppSpacing.md),
                PrimaryButton(
                  text: s.servicesSave,
                  onPressed: () => Navigator.of(sheetContext).pop('save'),
                ),
                const SizedBox(height: AppSpacing.sm),
                KbAnchor(
                  id: 'services.step_retire_button',
                  child: SizedBox(
                  width: double.infinity,
                  child: TextButton(
                    onPressed: () => Navigator.of(sheetContext).pop('retire'),
                    child: Text(s.servicesStepRetire, style: const TextStyle(color: AppColors.danger)),
                  ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
    if (action == null || !mounted) return;
    if (action == 'retire') {
      final updated = await widget.service.updateProcedureStep(step.id, active: false);
      if (updated == null || !mounted) return;
      setState(() {
        _steps = _steps!.where((st) => st.id != step.id).toList();
        _selectedStepIds.remove(step.id);
      });
      return;
    }
    final text = controller.text.trim();
    if (text.isEmpty) return;
    final updated = await widget.service.updateProcedureStep(
      step.id,
      text: text,
      severity: critical ? 'critical' : 'normal',
    );
    if (updated == null || !mounted) return;
    setState(() {
      _steps = _steps!.map((st) => st.id == step.id ? updated : st).toList();
    });
  }

  Future<void> _submit() async {
    final s = S.of(context)!;
    final name = _nameController.text.trim();
    if (name.isEmpty) {
      setState(() => _error = s.servicesNameRequired);
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    final priceSar = double.tryParse(_priceController.text.trim());
    final priceMinor = priceSar != null ? (priceSar * 100).round() : null;
    final duration = int.tryParse(_durationController.text.trim());
    final cycle = int.tryParse(_cycleController.text.trim());
    final description = _descriptionController.text.trim();

    ServiceItem? result;
    if (widget.existing != null) {
      result = await widget.service.update(
        widget.existing!.id,
        name: name,
        priceMinor: priceMinor,
        durationMinutes: duration,
        cycleDays: cycle,
        description: description,
        assignmentMode: _assignmentMode,
        eligibleStaffIds: _assignmentMode == 'named' ? _eligibleStaffIds.toList() : const [],
        procedureStepIds: _selectedStepIds,
      );
    } else {
      result = await widget.service.create(
        name: name,
        priceMinor: priceMinor,
        durationMinutes: duration,
        cycleDays: cycle,
        description: description,
      );
      if (result != null &&
          (_assignmentMode != 'auto' || _selectedStepIds.isNotEmpty || _eligibleStaffIds.isNotEmpty)) {
        result = await widget.service.update(
          result.id,
          assignmentMode: _assignmentMode,
          eligibleStaffIds: _assignmentMode == 'named' ? _eligibleStaffIds.toList() : const [],
          procedureStepIds: _selectedStepIds,
        );
      }
    }
    if (!mounted) return;
    if (result == null) {
      setState(() {
        _saving = false;
        _error = s.servicesActionFailed;
      });
      return;
    }
    if (_newPhotoBytes != null) {
      setState(() => _uploadingPhoto = true);
      final withPhoto = await widget.service.uploadImage(result.id,
          bytes: _newPhotoBytes!, contentType: _newPhotoContentType ?? 'image/jpeg');
      if (!mounted) return;
      if (withPhoto == null) {
        setState(() {
          _saving = false;
          _uploadingPhoto = false;
          _error = s.servicesPhotoUploadFailed;
        });
        return;
      }
    }

    // ── the reminders/loyalty settings tree writes — deliberately separate calls from the
    // service row above (Services.tsx's own "two stores behind one form" doctrine). A failure
    // here never rolls back the service itself, same "partial creation is fine, rest is editable
    // after" posture the photo upload above already takes.
    final followUp = _followUpOwn ? int.tryParse(_followUpController.text.trim()) : null;
    if (_followUpOwn && followUp != null) {
      await widget.service.setServiceReminderSettings(result.id, followUpDays: followUp);
    } else if (!_followUpOwn && _reminderResolved.$2) {
      await widget.service.followGeneralReminderSettings(result.id);
    }
    final points = _pointsOwn ? int.tryParse(_pointsController.text.trim()) : null;
    if (_pointsOwn && points != null) {
      await widget.service.setServicePoints(result.id, points);
    } else if (!_pointsOwn && _earnResolved.$2) {
      await widget.service.followGeneralPoints(result.id);
    }
    final newGroupName = _addingNewGroup ? _newGroupController.text.trim() : _group;
    final priorGroup = widget.existing != null ? widget.reminderTree?.serviceGroup[widget.existing!.id] : null;
    if (newGroupName != null && newGroupName.isNotEmpty && newGroupName != priorGroup) {
      await widget.service.setReminderGroup(newGroupName, serviceIds: [result.id]);
    } else if (newGroupName == null && priorGroup != null) {
      await widget.service.leaveReminderGroup(priorGroup, result.id);
    }

    if (!mounted) return;
    Navigator.of(context).pop(true);
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final isEdit = widget.existing != null;
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: DraggableScrollableSheet(
        initialChildSize: 0.85,
        maxChildSize: 0.95,
        minChildSize: 0.5,
        expand: false,
        builder: (context, scrollController) => KbAnchor(
          id: 'services.add_sheet',
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
                Text(isEdit ? s.servicesEditTitle : s.servicesAddTitle,
                    style: AppTextStyles.headlineSmall),
                const SizedBox(height: AppSpacing.lg),
                AppTextField(labelText: s.servicesNameLabel, controller: _nameController),
                const SizedBox(height: AppSpacing.md),
                Row(
                  children: [
                    Expanded(
                      child: AppTextField(
                        labelText: s.servicesPriceLabel,
                        controller: _priceController,
                        keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      ),
                    ),
                    const SizedBox(width: AppSpacing.sm),
                    Expanded(
                      child: AppTextField(
                        labelText: s.servicesDurationLabel,
                        controller: _durationController,
                        keyboardType: TextInputType.number,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: AppSpacing.md),
                AppTextField(
                  labelText: s.servicesCycleLabel,
                  controller: _cycleController,
                  keyboardType: TextInputType.number,
                ),
                const SizedBox(height: AppSpacing.md),
                AppTextField(
                  labelText: s.servicesDescriptionLabel,
                  controller: _descriptionController,
                  maxLines: 3,
                ),
                const SizedBox(height: AppSpacing.lg),
                Text(s.servicesPhotoLabel, style: AppTextStyles.labelMedium),
                const SizedBox(height: AppSpacing.sm),
                // Same shape as شخصيتي/`shop_identity_screen.dart`'s own logo picker — a real
                // labeled button next to the preview, never a bare tappable square (owner
                // 2026-09-23: a silent square read as broken/not-tappable, not as an upload
                // control — the button's own label is the affordance).
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    ClipRRect(
                      borderRadius: BorderRadius.circular(AppRadius.md),
                      child: SizedBox(
                        height: 72,
                        width: 72,
                        child: _newPhotoBytes != null
                            ? Image.memory(_newPhotoBytes!, fit: BoxFit.cover)
                            : (_hasImage && widget.existing != null)
                                ? _ServiceThumbnail(serviceId: widget.existing!.id, size: 72)
                                : _GlossySquare(
                                    radius: BorderRadius.circular(AppRadius.md),
                                    dashed: true,
                                    child: SizedBox(
                                      height: 72,
                                      width: 72,
                                      child: Icon(Icons.image_outlined,
                                          color: context.appColors.textSecondary),
                                    ),
                                  ),
                      ),
                    ),
                    const SizedBox(width: AppSpacing.md),
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: _pickingPhoto ? null : _pickPhoto,
                        icon: _pickingPhoto
                            ? const SizedBox(
                                width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                            : const Icon(Icons.image_rounded, size: 18),
                        label: Text((_newPhotoBytes != null || _hasImage)
                            ? s.servicesChangePhoto
                            : s.servicesUploadPhoto),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: AppSpacing.lg),
                Text(s.servicesAssignmentLabel, style: AppTextStyles.labelMedium),
                const SizedBox(height: AppSpacing.sm),
                SegmentedFilter<String>(
                  value: _assignmentMode,
                  onChanged: (v) => setState(() => _assignmentMode = v),
                  options: [
                    SegmentedFilterOption(value: 'auto', label: s.servicesAssignmentAuto),
                    SegmentedFilterOption(value: 'named', label: s.servicesAssignmentNamed),
                  ],
                ),
                if (_assignmentMode == 'named') ...[
                  const SizedBox(height: AppSpacing.sm),
                  if (_staff == null)
                    const Padding(
                        padding: EdgeInsets.symmetric(vertical: AppSpacing.sm),
                        child: AppLoadingIndicator())
                  else
                    Wrap(
                      spacing: 6,
                      runSpacing: 6,
                      children: _staff!.where((m) => m.active).map((m) {
                        final selected = _eligibleStaffIds.contains(m.id);
                        return _ToggleChip(
                          label: m.name,
                          selected: selected,
                          onTap: () => setState(() {
                            if (selected) {
                              _eligibleStaffIds.remove(m.id);
                            } else {
                              _eligibleStaffIds.add(m.id);
                            }
                          }),
                        );
                      }).toList(),
                    ),
                ],
                const SizedBox(height: AppSpacing.lg),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(s.servicesChecklistLabel, style: AppTextStyles.labelMedium),
                    TextButton.icon(
                      onPressed: _createStep,
                      icon: const Icon(Icons.add_rounded, size: 16),
                      label: Text(s.servicesStepAddTitle),
                    ),
                  ],
                ),
                const SizedBox(height: AppSpacing.xs),
                if (_steps == null)
                  const AppLoadingIndicator()
                else if (_steps!.where((st) => st.active).isEmpty)
                  Text(s.servicesChecklistEmpty,
                      style: AppTextStyles.caption.copyWith(color: context.appColors.textSecondary))
                else
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    children: _steps!.where((st) => st.active).map((st) {
                      final selected = _selectedStepIds.contains(st.id);
                      return _ToggleChip(
                        label: st.text,
                        selected: selected,
                        critical: st.severity == 'critical',
                        onTap: () => setState(() {
                          if (selected) {
                            _selectedStepIds.remove(st.id);
                          } else {
                            _selectedStepIds.add(st.id);
                          }
                        }),
                        onLongPress: context.read<NavProvider>().catalog.hasAll(['operations.update_procedure_step'])
                            ? () => _editStep(st)
                            : null,
                      );
                    }).toList(),
                  ),
                if (_steps != null && _steps!.where((st) => st.active).isNotEmpty) ...[
                  const SizedBox(height: 2),
                  Text(s.servicesStepEditHint,
                      style: AppTextStyles.caption.copyWith(color: context.appColors.textMuted)),
                ],
                const SizedBox(height: AppSpacing.lg),
                Text(s.servicesAdvancedTitle, style: AppTextStyles.labelMedium),
                const SizedBox(height: AppSpacing.xs),
                Text(s.servicesAdvancedHint,
                    style: AppTextStyles.caption.copyWith(color: context.appColors.textMuted)),
                const SizedBox(height: AppSpacing.sm),
                _OverrideField(
                  label: s.servicesFollowUpLabel,
                  own: _followUpOwn,
                  controller: _followUpController,
                  inheritedHint: (_reminderResolved.$1.followUpDays ?? 0) > 0
                      ? s.servicesFollowUpDays(_reminderResolved.$1.followUpDays!)
                      : s.servicesNoCycle,
                  onToggleOwn: (v) => setState(() => _followUpOwn = v),
                ),
                const SizedBox(height: AppSpacing.md),
                _OverrideField(
                  label: s.servicesPointsLabel,
                  own: _pointsOwn,
                  controller: _pointsController,
                  inheritedHint: _earnResolved.$1 > 0
                      ? s.servicesPointsPerVisit(_earnResolved.$1)
                      : s.servicesNoPrice,
                  onToggleOwn: (v) => setState(() => _pointsOwn = v),
                ),
                const SizedBox(height: AppSpacing.md),
                Text(s.servicesGroupLabel, style: AppTextStyles.bodySmall.copyWith(color: context.appColors.textSecondary)),
                const SizedBox(height: AppSpacing.xs),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    _ToggleChip(
                      label: s.servicesNoGroup,
                      selected: _group == null && !_addingNewGroup,
                      onTap: () => setState(() {
                        _group = null;
                        _addingNewGroup = false;
                      }),
                    ),
                    for (final g in widget.groupNames)
                      _ToggleChip(
                        label: g,
                        selected: _group == g,
                        onTap: () => setState(() {
                          _group = g;
                          _addingNewGroup = false;
                        }),
                      ),
                    _ToggleChip(
                      label: s.servicesNewGroup,
                      selected: _addingNewGroup,
                      onTap: () => setState(() => _addingNewGroup = true),
                    ),
                  ],
                ),
                if (_addingNewGroup) ...[
                  const SizedBox(height: AppSpacing.sm),
                  AppTextField(
                    labelText: s.servicesGroupNameHint,
                    controller: _newGroupController,
                  ),
                ],
                if (_error != null) ...[
                  const SizedBox(height: AppSpacing.md),
                  AppAlert(type: AlertType.error, message: _error!),
                ],
                const SizedBox(height: AppSpacing.lg),
                CapabilityGate(
                  requires: [widget.existing != null
                      ? 'operations.update_service'
                      : 'operations.create_service'],
                  child: PrimaryButton(
                    text: _uploadingPhoto ? s.servicesSaving : (_saving ? s.servicesSaving : s.servicesSave),
                    isLoading: _saving,
                    onPressed: _saving ? null : _submit,
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

class _ToggleChip extends StatelessWidget {
  const _ToggleChip({
    required this.label,
    required this.selected,
    required this.onTap,
    this.critical = false,
    this.onLongPress,
  });
  final String label;
  final bool selected;
  final bool critical;
  final VoidCallback onTap;
  final VoidCallback? onLongPress;

  @override
  Widget build(BuildContext context) {
    final dark = context.isDark;
    final accent = dark ? AppDarkColors.accent : AppColors.accent;
    return InkWell(
      onTap: onTap,
      onLongPress: onLongPress,
      borderRadius: BorderRadius.circular(AppRadius.sm),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: selected ? accent.withValues(alpha: 0.15) : context.appColors.surfaceAlt,
          borderRadius: BorderRadius.circular(AppRadius.sm),
          border: Border.all(color: selected ? accent : context.appColors.borderSubtle),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (critical) ...[
              const Icon(Icons.priority_high_rounded, size: 12, color: AppColors.danger),
              const SizedBox(width: 2),
            ],
            Text(label,
                style: AppTextStyles.caption.copyWith(
                    color: selected ? accent : context.appColors.textSecondary,
                    fontWeight: selected ? FontWeight.w700 : FontWeight.w400)),
          ],
        ),
      ),
    );
  }
}

/// One row of the "خاصة بهذه الخدمة" / "تتبع العام" switch (Services.tsx's own §10.8.1: a service
/// either FOLLOWS the general value or holds its own — never both at once). Switching to "own"
/// reveals the field pre-filled with the resolved value so typing a customisation starts from
/// what the service already effectively has, not from zero.
class _OverrideField extends StatelessWidget {
  const _OverrideField({
    required this.label,
    required this.own,
    required this.controller,
    required this.inheritedHint,
    required this.onToggleOwn,
  });
  final String label;
  final bool own;
  final TextEditingController controller;
  final String inheritedHint;
  final ValueChanged<bool> onToggleOwn;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context)!;
    final colors = context.appColors;
    return KbAnchor(
      id: 'services.override_field',
      child: Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Expanded(
          child: own
              ? AppTextField(labelText: label, controller: controller, keyboardType: TextInputType.number)
              : Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(label, style: AppTextStyles.bodySmall.copyWith(color: colors.textSecondary)),
                    const SizedBox(height: 2),
                    Text(s.servicesFollowsGeneral(inheritedHint),
                        style: AppTextStyles.caption.copyWith(color: colors.textMuted)),
                  ],
                ),
        ),
        const SizedBox(width: AppSpacing.sm),
        TextButton(
          onPressed: () => onToggleOwn(!own),
          child: Text(own ? s.servicesFollowGeneralAction : s.servicesCustomizeAction),
        ),
      ],
      ),
    );
  }
}

/// Lazily fetches and caches one service's own image bytes — never fetched unless
/// `hasImage`/a locally-picked photo says there is one, matching the route's own 404-when-absent
/// contract.
class _ServiceThumbnail extends StatefulWidget {
  const _ServiceThumbnail({required this.serviceId, this.size = 40});
  final String serviceId;
  final double size;

  @override
  State<_ServiceThumbnail> createState() => _ServiceThumbnailState();
}

class _ServiceThumbnailState extends State<_ServiceThumbnail> {
  Uint8List? _bytes;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final service = ServicesCatalogueService(apiClient: context.read<AuthProvider>().apiClient);
    final bytes = await service.fetchImage(widget.serviceId);
    if (mounted) setState(() => _bytes = bytes);
  }

  @override
  Widget build(BuildContext context) {
    if (_bytes != null) {
      return ClipRRect(
        borderRadius: BorderRadius.circular(AppRadius.sm),
        child: Image.memory(_bytes!, fit: BoxFit.cover, width: widget.size, height: widget.size),
      );
    }
    return SizedBox(
      width: widget.size,
      height: widget.size,
      child: _GlossySquare(
        radius: BorderRadius.circular(AppRadius.sm),
        child: SizedBox(width: widget.size, height: widget.size),
      ),
    );
  }
}
